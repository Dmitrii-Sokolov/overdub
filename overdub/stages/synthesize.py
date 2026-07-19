"""Synthesize stage: the TTS engine renders each RENDER UNIT to segments/*.wav.

A render unit is one or more adjacent sentences from translation.json grouped for natural
prosody (dead-air design, DECISIONS 2026-07-16): consecutive sentences join while the
inter-sentence gap is ≤ cfg.group_gap_max, the unit's source span stays ≤ _GROUP_MAX_SPAN
and its joined text_tts ≤ _GROUP_MAX_CHARS. Empty-text sentences form singleton units and
break chains. The unit wav lives at seg_wav(first_id); translation ids stay the reporting
grain everywhere downstream (verify/assemble fan unit facts out per sentence id).

Slot-fill: engines with supports_target (F5) receive target_sec = the unit's SOURCE SPAN
and max_sec = its slot [start, next_unit.start) and pick a native speed (stretch to fill
the span / neutral when the free gap absorbs the spill / mild compress before atempo tops
up — see tts.f5.plan_speed). The chosen speed is recorded per unit.

Reseed-retry (seed-capable engines): in-stage whisper-small round-trip of the unit wav vs
the joined text_tts (asr.roundtrip_similarity — the SAME function verify uses); below
cfg.similarity_threshold, retry with seeds tts_seed+1..+tts_max_retries keeping the best.
The retry lives HERE so segments/manifest.json stays single-writer (assemble derives
atempo from manifest samples). verify remains the independent judge.

Resumable: a unit wav is reused ONLY if the manifest synth_key matches the current config
AND the prior unit has the same member ids, the same joined text_tts, no synth_error flag,
and (for supports_target engines) the same span/slot to 3 dp — so an engine/knob switch, a
re-translation of any member, or a timing shift re-renders exactly the affected units.
Manifest schema: doc has "units" (legacy per-sentence "segments" docs are adapted read-side
as singleton units by units_of()); "complete" marker + periodic flush semantics unchanged.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time

import numpy as np
import soundfile as sf

from ..asr import roundtrip_similarity
from ..normalize import normalize_for_compare
from ..pipeline import Context
from ..tts import engine_sample_rate, synth_key
from ..tts.base import TtsFatalError
from ..workdir import replace_retry

_FLUSH_EVERY = 25          # fresh units between mid-run manifest flushes (crash resume)
_GROUP_MAX_SPAN = 12.0     # unit source-span cap (s): ~10 s ref + gen stays inside F5's
                           # trained ≤30 s regime and mostly single-chunk
_GROUP_MAX_CHARS = 300     # joined text_tts cap: internal-chunking insurance


def build_units(segs: list[dict], gap_max: float) -> list[dict]:
    """Group adjacent sentences into render units. Pure, deterministic, unit-tested.
    Returns [{ids, start, end, text}] covering every sentence id exactly once, in order."""
    units: list[dict] = []
    for s in segs:
        text = (s.get("text_tts") or "").strip()
        u = units[-1] if units else None
        if (gap_max > 0 and text and u is not None and u["text"]
                and s["start"] - u["end"] <= gap_max
                and s["end"] - u["start"] <= _GROUP_MAX_SPAN
                and len(u["text"]) + 1 + len(text) <= _GROUP_MAX_CHARS):
            u["ids"].append(s["id"])
            u["end"] = s["end"]
            u["text"] = f"{u['text']} {text}"
        else:
            units.append({"ids": [s["id"]], "start": s["start"], "end": s["end"], "text": text})
    return units


def unit_sim_threshold(cfg, speed: float | None) -> float:
    """Per-unit similarity gate — ONE function for synthesize's reseed loop AND verify
    (same discipline as roundtrip_similarity: the two sides can never drift). Natively
    compressed units (speed above the base narrator pace) must clear the stricter bar:
    F5 compression ≥~1.3 DROPS words outright while ASR sim can still scrape past the
    base threshold (the 17:02 mid-word cutoff shipped at 0.836 vs gate 0.8)."""
    if speed is not None and speed > cfg.f5_speed + 1e-6:
        return max(cfg.similarity_threshold, cfg.similarity_threshold_compressed)
    return cfg.similarity_threshold


def units_of(doc: dict) -> list[dict]:
    """Units from a manifest doc; legacy per-sentence "segments" docs adapt to singleton
    units so old workdirs stay readable by verify/assemble without migration."""
    if "units" in doc:
        return doc["units"]
    return [{**e, "ids": [e["id"]], "text_tts": e.get("text_tts")}
            for e in doc.get("segments", [])]


def _legacy_key(doc: dict) -> str:
    """Reconstruct synth_key for a pre-synth_key (Silero-era) manifest."""
    return f"{doc.get('engine')}|{doc.get('voice')}|sr={doc.get('sample_rate')}"


_replace = replace_retry             # shared AV-tolerant atomic flip (workdir.replace_retry)


def _stat_wav(wav):
    """sf.info with the same bounded AV-tolerance as _replace."""
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
        if not doc.get("complete", True):
            return False
        # congruence gate: a complete manifest must match what the CURRENT translation
        # would have it render — otherwise `--force --only translate` + a plain rerun
        # skips this stage over stale wavs (the one forbidden silent class; bit the
        # renorm A/B). Compares the manifest's OWN units against current text only, so
        # a group_gap_max change stays WARN-only below and never surprise-regroups.
        try:
            segs = json.loads(ctx.work.translation.read_text(encoding="utf-8"))
            by_id = {s["id"]: (s.get("text_tts") or "").strip() for s in segs}
            units = units_of(doc)
            stale = sorted(i for u in units for i in u["ids"]) != sorted(by_id) or any(
                " ".join(by_id[i] for i in u["ids"]).strip() != (u.get("text_tts") or "").strip()
                for u in units)
            if stale:
                print("       [info] synthesize: translation changed since manifest — "
                      "re-synthesizing stale units", file=sys.stderr)
                return False
        except Exception:
            pass                                           # unreadable translation.json →
                                                           # keep the legacy gate (never crash)
        try:                                               # best-effort staleness warnings —
            key = synth_key(ctx.cfg)                       # done() must never crash the skip path
            prior_key = doc.get("synth_key") or _legacy_key(doc)
            if prior_key != key:
                print(f"       [warn] synthesize: artifact exists but synth key changed\n"
                      f"              ({prior_key} → {key}) — rerun with --force to resynthesize",
                      file=sys.stderr)
            elif doc.get("group_gap_max", 0.0) != ctx.cfg.group_gap_max:   # legacy docs = per-sentence
                print(f"       [warn] synthesize: group_gap_max changed "
                      f"({doc.get('group_gap_max')} → {ctx.cfg.group_gap_max}) — "
                      "rerun with --force to regroup", file=sys.stderr)
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
        units = build_units(segs, cfg.group_gap_max)
        if sorted(i for u in units for i in u["ids"]) != list(range(len(segs))):
            raise RuntimeError("units do not cover translation ids (synthesize never-drop)")

        # prior manifest → reusable units, gated by synth_key
        prior: dict[tuple, dict] = {}
        if ctx.work.seg_manifest.exists():
            try:
                doc = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
                prior_key = doc.get("synth_key") or _legacy_key(doc)
                if prior_key == key:
                    prior = {tuple(u["ids"]): u for u in units_of(doc)}
                else:
                    print(f"       [info] synth key changed ({prior_key} → {key}) — full resynthesis")
            except Exception:
                pass                                       # torn manifest → rebuild from wavs

        supports_target = cfg.tts_engine == "f5"           # engine fact, known without loading

        def slot_of(i: int) -> float | None:
            return (units[i + 1]["start"] - units[i]["start"]) if i + 1 < len(units) else None

        def reusable(i: int) -> bool:
            u = units[i]
            p = prior.get(tuple(u["ids"]))
            if (p is None or not ctx.work.seg_wav(u["ids"][0]).exists()
                    or p.get("text_tts") != u["text"] or p.get("flag") == "synth_error"):
                return False
            if supports_target and u["text"]:
                slot = slot_of(i)
                if (round(p.get("target_sec") or -1, 3) != round(u["end"] - u["start"], 3)
                        or round(p.get("max_sec") or -1, 3) != round(slot if slot is not None else -1, 3)):
                    return False
            return True

        need = [i for i, u in enumerate(units) if not reusable(i) and u["text"]]

        # wavs are about to mutate: downgrade the on-disk manifest to complete:false first,
        # keeping the reusable units so a crash mid-resynthesis still resumes from them
        if need and ctx.work.seg_manifest.exists():
            self._write_manifest(ctx, cfg, key, sr,
                                 [prior[tuple(units[i]["ids"])] for i, u in enumerate(units)
                                  if reusable(i)], complete=False)

        engine = None
        verifier = None
        if need:                                           # unchanged gate: an all-reusable
            # batch never reaches this line, so no worker is ever spawned — the session is
            # get-or-create at the USE SITE precisely to keep that laziness
            engine = ctx.session.tts_engine(cfg)           # outside the per-unit try: fail LOUD
            engine.begin_video()                           # reused engine: reset the crash
                                                           # budget, which counts CONSECUTIVE
                                                           # failures within ONE video
            if engine.sample_rate != sr:
                raise RuntimeError(f"engine sr {engine.sample_rate} != expected {sr}")
            if engine.supports_seed:
                verifier = ctx.session.whisper(cfg, cfg.verify_model)

        out: list[dict] = []
        fresh_since_flush = 0
        # no local teardown: the engine and the verifier belong to the session, whose
        # lifetime is one stage SWEEP (pipeline.Session). For a single video that sweep ends
        # with this stage, i.e. exactly the old finally block; in a stage-major batch the
        # next video reuses the same warm worker.
        for i, u in enumerate(units):
            lead = u["ids"][0]
            wav = ctx.work.seg_wav(lead)
            slot = slot_of(i)
            target = u["end"] - u["start"]
            flag: str | None = None
            seed_used: int | None = None
            speed_used: float | None = None
            attempts = 0
            synth_sim: float | None = None

            prev = prior.get(tuple(u["ids"]))
            if reusable(i):
                flag = prev.get("flag")
                seed_used = prev.get("seed")
                speed_used = prev.get("speed")
                attempts = prev.get("attempts") or 0
                synth_sim = prev.get("synth_sim")
            elif not u["text"]:
                sf.write(str(wav), np.zeros(0, dtype="float32"), sr)   # honest empty slot
                flag = "empty_tts"
                fresh_since_flush += 1
            else:
                fresh_since_flush += 1
                kw = {"target_sec": target, "max_sec": slot} if supports_target else {}
                try:
                    tmp = wav.with_suffix(".wav.tmp")
                    speed_used = engine.synthesize(u["text"], tmp, seed=cfg.tts_seed, **kw)
                    seed_used, attempts = (cfg.tts_seed if engine.supports_seed else None), 1
                    if verifier is not None:
                        ref_norm = normalize_for_compare(u["text"])
                        best: float | None = None
                        if ref_norm:
                            try:
                                best, _hyp, _hn = roundtrip_similarity(
                                    verifier, tmp, ref_norm, cfg.target_lang)
                            except Exception as e:         # round-trip broke, audio didn't
                                print(f"       [warn] u{lead}: round-trip failed ({e}) — "
                                      "keeping audio, verify will judge", file=sys.stderr)
                        if best is not None:
                            need_sim = unit_sim_threshold(cfg, speed_used)
                            for k in range(1, cfg.tts_max_retries + 1):
                                if best >= need_sim:
                                    break
                                retry_tmp = wav.with_suffix(".wav.retry")
                                try:
                                    engine.synthesize(u["text"], retry_tmp,
                                                      seed=cfg.tts_seed + k, **kw)
                                    sim_k, _h, _n = roundtrip_similarity(
                                        verifier, retry_tmp, ref_norm, cfg.target_lang)
                                except TtsFatalError:
                                    raise
                                except Exception as e:
                                    print(f"       [warn] u{lead}: retry seed "
                                          f"{cfg.tts_seed + k} failed ({e})", file=sys.stderr)
                                    attempts += 1
                                    continue
                                attempts += 1
                                if sim_k > best:           # keep-best: retry never makes it worse
                                    _replace(retry_tmp, tmp)
                                    best, seed_used = sim_k, cfg.tts_seed + k
                                else:
                                    retry_tmp.unlink(missing_ok=True)
                            synth_sim = round(best, 4)
                            if attempts > 1:
                                tail = ("ok" if best >= need_sim
                                        else "still low")
                                print(f"       [retry] u{lead}: {attempts} attempts, "
                                      f"best {best:.3f} (seed {seed_used}) — {tail}")
                    _replace(tmp, wav)
                except TtsFatalError:
                    raise
                except Exception as e:
                    print(f"       [flag] u{lead}: synth_error {e}", file=sys.stderr)
                    sf.write(str(wav), np.zeros(0, dtype="float32"), sr)
                    flag = "synth_error"
                    seed_used = speed_used = synth_sim = None

            try:
                info = _stat_wav(wav)
                frames, srate = info.frames, info.samplerate
            except Exception as e:                         # unreadable wav → flag AND zero it so
                if flag is None:                           # disk and manifest agree
                    print(f"       [flag] u{lead}: synth_error {e}", file=sys.stderr)
                    flag = "synth_error"
                try:
                    sf.write(str(wav), np.zeros(0, dtype="float32"), sr)
                except Exception:
                    wav.unlink(missing_ok=True)            # missing beats divergent
                frames, srate = 0, sr
            if frames and srate != sr:
                raise RuntimeError(f"u{lead} wav sr {srate} != engine sr {sr}")
            out.append({
                "ids": u["ids"], "path": f"segments/{lead:05d}.wav",
                "samples": frames, "duration": round(frames / sr, 3),
                "sample_rate": srate, "start": u["start"], "end": u["end"],
                "target_sec": (round(target, 3) if u["text"] else None),
                "max_sec": (round(slot, 3) if slot is not None else None),
                "text_tts": u["text"], "flag": flag, "speed": speed_used,
                "seed": seed_used, "attempts": attempts, "synth_sim": synth_sim,
            })
            if fresh_since_flush >= _FLUSH_EVERY:
                self._write_manifest(ctx, cfg, key, sr, out, complete=False)
                fresh_since_flush = 0

        if sorted(i for e in out for i in e["ids"]) != list(range(len(segs))):
            raise RuntimeError("unit ids not contiguous (synthesize never-drop)")
        n_flag, n_retried = self._write_manifest(ctx, cfg, key, sr, out, complete=True)
        # regrouping moves unit leaders: unlink stale NNNNN.wav files whose id is no longer
        # a lead, or a later --only verify/assemble could pick up orphan audio
        leads = {e["ids"][0] for e in out}
        for p in ctx.work.segments_dir.glob("[0-9][0-9][0-9][0-9][0-9].wav"):
            if int(p.stem) not in leads:
                p.unlink(missing_ok=True)
        print(f"       {len(segs)} sentences → {len(out)} units → manifest.json "
              f"({n_flag} flagged, {n_retried} retried)")

    @staticmethod
    def _write_manifest(ctx, cfg, key, sr, out, *, complete: bool) -> tuple[int, int]:
        n_flag = sum(1 for e in out if e.get("flag"))
        n_retried = sum(1 for e in out if (e.get("attempts") or 0) > 1)
        # units_key: content fingerprint of what was actually rendered — a SAME-synth_key
        # resynthesis (e.g. --force) still changes it, so the downstream self-heal gates
        # (verify/assemble) can never skip over refreshed wavs
        uk = hashlib.sha1(json.dumps(
            [(e["ids"], e.get("text_tts"), e.get("samples")) for e in out],
            ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
        doc = {
            "sample_rate": sr, "engine": cfg.tts_engine,
            "voice": cfg.f5_ref_audio.stem if cfg.tts_engine == "f5" else cfg.tts_voice,
            "synth_key": key, "units_key": uk, "complete": complete,
            "group_gap_max": cfg.group_gap_max, "base_speed": cfg.f5_speed,
            "n_units": len(out), "n_flagged": n_flag, "n_retried": n_retried, "units": out,
        }
        tmp = ctx.work.seg_manifest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, ctx.work.seg_manifest)
        return n_flag, n_retried
