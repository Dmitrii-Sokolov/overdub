"""Synthesize stage: the TTS engine renders each sentence to segments/*.wav.

Feeds text_tts (NEVER text_ru — the normalized, TTS-safe field) through the TTS engine
adapter (overdub.tts.build_engine). One wav per id, on RAW audio before any atempo.
status:"failed" records are synthesized like any other (their text_tts is a real
EN-fallback transliteration; the translate flag persists in translation.json).

Reseed-retry (seed-capable engines only, i.e. F5): every fresh segment gets an in-stage
whisper-small round-trip (asr.roundtrip_similarity — the SAME function verify uses);
below cfg.similarity_threshold it is re-synthesized with seeds tts_seed+1..+tts_max_retries,
keeping the best attempt by similarity. The retry lives HERE and not in verify so that
segments/manifest.json stays single-writer: assemble derives atempo factors from manifest
`samples`, and a wav/manifest divergence is silent timing corruption. verify remains the
independent judge and the sole flagging authority for similarity. Silero (deterministic)
skips all of this — behavior identical to Phase 1.

Resumable: a wav is reused ONLY if the manifest-level synth_key matches the current config
(engine/voice/ref-content/model/nfe/speed/base-seed — everything that changes rendered
audio) AND its manifest text_tts matches the current one, so an engine switch or
re-translation re-synthesizes instead of serving stale audio. Atomic per-wav write
(tmp + os.replace) means a wav that exists is always complete. Before any wav mutates,
the on-disk manifest is downgraded to "complete": false (a crash mid-resynthesis must
not leave a complete:true manifest over divergent wavs); it is re-flushed atomically
after every _FLUSH_EVERY freshly synthesized segments (an interrupted overnight run
resumes from the last flush) and written "complete": true at the end — done() checks
that marker, and warns loudly if the artifact exists but synth_key changed.
"""

from __future__ import annotations

import gc
import json
import os
import sys
import time

import numpy as np
import soundfile as sf

from ..asr import load_whisper, roundtrip_similarity
from ..normalize import normalize_for_compare
from ..pipeline import Context
from ..tts import build_engine, engine_sample_rate, synth_key
from ..tts.base import TtsFatalError

_FLUSH_EVERY = 25


def _legacy_key(doc: dict) -> str:
    """Reconstruct synth_key for a pre-synth_key (Silero-era) manifest — reproduces the
    current silero key format exactly, so existing workdirs resume untouched."""
    return f"{doc.get('engine')}|{doc.get('voice')}|sr={doc.get('sample_rate')}"


def _replace(src, dst) -> None:
    """os.replace with a short bounded retry: the worker (another process) has just
    closed the file, and Windows real-time AV can hold it for a moment."""
    for attempt in range(3):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.1)


def _stat_wav(wav) -> "sf._SoundFileInfo":
    """sf.info with the same bounded AV-tolerance as _replace — the wav was just written
    by another process, and a transient read failure here must not diverge disk from
    manifest (a real wav recorded as samples=0 silently truncates in assemble)."""
    for attempt in range(3):
        try:
            return sf.info(str(wav))
        except Exception:
            if attempt == 2:
                raise
            time.sleep(0.1)


class SynthesizeStage:
    name = "synthesize"

    def done(self, ctx: Context) -> bool:
        if not ctx.work.seg_manifest.exists():
            return False
        try:
            doc = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
        except Exception:
            return False                                   # torn manifest → re-run
        if not doc.get("complete", True):                  # legacy manifests: only written complete
            return False
        try:                                               # best-effort staleness warning: done()
            key = synth_key(ctx.cfg)                       # must never crash the skip path
            prior_key = doc.get("synth_key") or _legacy_key(doc)
            if prior_key != key:
                print(f"       [warn] synthesize: artifact exists but synth key changed\n"
                      f"              ({prior_key} → {key}) — rerun with --force to resynthesize",
                      file=sys.stderr)
        except Exception:
            pass
        return True

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        segs = json.loads(ctx.work.translation.read_text(encoding="utf-8"))
        if [s["id"] for s in segs] != list(range(len(segs))):
            raise RuntimeError("translation ids not contiguous (synthesize never-drop)")

        key = synth_key(cfg)
        sr = engine_sample_rate(cfg)

        # prior manifest → per-id entries, reusable ONLY under an identical synth_key —
        # an engine/voice/ref/knob switch must never serve stale audio
        prior: dict[int, dict] = {}
        if ctx.work.seg_manifest.exists():
            try:
                doc = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
                prior_key = doc.get("synth_key") or _legacy_key(doc)
                if prior_key == key:
                    prior = {e["id"]: e for e in doc.get("segments", [])}
                else:
                    print(f"       [info] synth key changed ({prior_key} → {key}) — full resynthesis")
            except Exception:
                pass                                       # torn manifest → rebuild from wavs

        def reusable(s: dict) -> bool:
            e = prior.get(s["id"])
            return (ctx.work.seg_wav(s["id"]).exists() and e is not None
                    and e.get("text_tts") == s.get("text_tts") and e.get("flag") != "synth_error")

        need = [s for s in segs if not reusable(s) and (s.get("text_tts") or "").strip()]

        # wavs are about to mutate: a complete:true manifest must not stay live over them —
        # a crash mid-resynthesis would otherwise resume as done() with divergent pairing.
        # The downgraded manifest keeps the key-validated reusable entries so resume survives.
        if need and ctx.work.seg_manifest.exists():
            self._write_manifest(ctx, cfg, key, sr,
                                 [prior[s["id"]] for s in segs if reusable(s)], complete=False)

        # engine + verifier are built OUTSIDE the per-segment try: a worker that cannot
        # start must fail the stage in one loud error, never as N synth_error flags
        engine = None
        verifier = None
        if need:
            engine = build_engine(cfg)
            if engine.sample_rate != sr:
                raise RuntimeError(f"engine sr {engine.sample_rate} != expected {sr}")
            if engine.supports_seed:
                verifier = load_whisper(cfg.verify_model, cfg.whisper_device,
                                        cfg.whisper_compute_type)

        out: list[dict] = []
        fresh_since_flush = 0
        try:
            for s in segs:
                sid = s["id"]
                wav = ctx.work.seg_wav(sid)
                text = (s.get("text_tts") or "").strip()
                flag: str | None = None
                seed_used: int | None = None
                attempts = 0
                synth_sim: float | None = None

                prev = prior.get(sid)
                if reusable(s):
                    flag = prev.get("flag")                # resume: carry flag + retry bookkeeping
                    seed_used = prev.get("seed")
                    attempts = prev.get("attempts") or 0
                    synth_sim = prev.get("synth_sim")
                elif not text:
                    sf.write(str(wav), np.zeros(0, dtype="float32"), sr)   # honest empty slot
                    flag = "empty_tts"
                    fresh_since_flush += 1
                else:
                    fresh_since_flush += 1
                    try:
                        tmp = wav.with_suffix(".wav.tmp")
                        engine.synthesize(text, tmp, seed=cfg.tts_seed)
                        seed_used, attempts = (cfg.tts_seed if engine.supports_seed else None), 1
                        if verifier is not None:
                            ref_norm = normalize_for_compare(text)
                            best: float | None = None
                            if ref_norm:
                                try:
                                    best, _hyp, _hn = roundtrip_similarity(
                                        verifier, tmp, ref_norm, cfg.target_lang)
                                except Exception as e:     # round-trip broke, audio didn't:
                                    print(f"       [warn] id{sid}: round-trip failed ({e}) — "
                                          "keeping audio, verify will judge", file=sys.stderr)
                            if best is not None:
                                for k in range(1, cfg.tts_max_retries + 1):
                                    if best >= cfg.similarity_threshold:
                                        break
                                    retry_tmp = wav.with_suffix(".wav.retry")
                                    try:
                                        engine.synthesize(text, retry_tmp, seed=cfg.tts_seed + k)
                                        sim_k, _h, _n = roundtrip_similarity(
                                            verifier, retry_tmp, ref_norm, cfg.target_lang)
                                    except TtsFatalError:
                                        raise
                                    except Exception as e:  # failed attempt: keep current best
                                        print(f"       [warn] id{sid}: retry seed {cfg.tts_seed + k}"
                                              f" failed ({e})", file=sys.stderr)
                                        attempts += 1
                                        continue
                                    attempts += 1
                                    if sim_k > best:       # keep-best: retry never makes it worse
                                        _replace(retry_tmp, tmp)
                                        best, seed_used = sim_k, cfg.tts_seed + k
                                    else:
                                        retry_tmp.unlink(missing_ok=True)
                                synth_sim = round(best, 4)
                                if attempts > 1:
                                    tail = ("ok" if best >= cfg.similarity_threshold
                                            else "still low")
                                    print(f"       [retry] id{sid}: {attempts} attempts, "
                                          f"best {best:.3f} (seed {seed_used}) — {tail}")
                        _replace(tmp, wav)                 # atomic: a wav that exists is complete
                    except TtsFatalError:
                        raise                              # engine/driver is down — fail the stage
                    except Exception as e:
                        print(f"       [flag] id{sid}: synth_error {e}", file=sys.stderr)
                        sf.write(str(wav), np.zeros(0, dtype="float32"), sr)
                        flag = "synth_error"
                        seed_used, synth_sim = None, None

                try:
                    info = _stat_wav(wav)
                    frames, srate = info.frames, info.samplerate
                except Exception as e:                     # unreadable wav → flag AND zero it so
                    if flag is None:                       # disk and manifest agree (a real wav
                        print(f"       [flag] id{sid}: synth_error {e}", file=sys.stderr)
                        flag = "synth_error"               # recorded as samples=0 would silently
                    try:                                   # truncate mid-sentence in assemble)
                        sf.write(str(wav), np.zeros(0, dtype="float32"), sr)
                    except Exception:
                        wav.unlink(missing_ok=True)        # missing beats divergent: verify flags it
                    frames, srate = 0, sr
                if frames and srate != sr:                 # silent sample-rate drift guard
                    raise RuntimeError(f"id{sid} wav sr {srate} != engine sr {sr}")
                out.append({
                    "id": sid, "path": f"segments/{sid:05d}.wav",
                    "samples": frames, "duration": round(frames / sr, 3),
                    "sample_rate": srate, "start": s["start"], "end": s["end"],
                    "text_tts": s.get("text_tts"), "flag": flag,
                    "seed": seed_used, "attempts": attempts, "synth_sim": synth_sim,
                })
                if fresh_since_flush >= _FLUSH_EVERY:      # crash resume: F5 makes this stage ~20×
                    self._write_manifest(ctx, cfg, key, sr, out, complete=False)
                    fresh_since_flush = 0
        finally:
            if engine is not None:
                engine.close()
            del engine, verifier
            gc.collect()
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass

        if [e["id"] for e in out] != list(range(len(segs))):
            raise RuntimeError("segment ids not contiguous (synthesize never-drop)")
        n_flag, n_retried = self._write_manifest(ctx, cfg, key, sr, out, complete=True)
        print(f"       {len(out)} segments → manifest.json ({n_flag} flagged, {n_retried} retried)")

    @staticmethod
    def _write_manifest(ctx, cfg, key, sr, out, *, complete: bool) -> tuple[int, int]:
        # summary counters derived from the entries (never incremental state): a resume
        # that reuses retried segments must not report n_retried=0 over attempts>1 entries
        n_flag = sum(1 for e in out if e.get("flag"))
        n_retried = sum(1 for e in out if (e.get("attempts") or 0) > 1)
        doc = {
            "sample_rate": sr, "engine": cfg.tts_engine,
            "voice": cfg.f5_ref_audio.stem if cfg.tts_engine == "f5" else cfg.tts_voice,
            "synth_key": key, "complete": complete,
            "count": len(out), "n_flagged": n_flag, "n_retried": n_retried, "segments": out,
        }
        tmp = ctx.work.seg_manifest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, ctx.work.seg_manifest)
        return n_flag, n_retried
