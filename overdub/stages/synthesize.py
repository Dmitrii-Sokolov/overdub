"""Synthesize stage (Phase 1): Silero (eugene) renders each sentence to segments/*.wav.

Feeds text_tts (NEVER text_ru — the normalized, TTS-safe field) through the TTS engine
adapter (overdub.tts.build_engine) so the engine can be swapped later. One wav per id, on
RAW audio before any atempo. status:"failed" records are synthesized like any other (their
text_tts is a real EN-fallback transliteration; the translate flag persists in translation.json).

Resumable: an existing wav is reused ONLY if its manifest text_tts matches the current one, so
a re-translated segment re-synthesizes automatically instead of serving stale audio (mirrors
translate.py's src_en-unchanged guard). Atomic per-wav write (tmp + os.replace) means a wav
that exists is always complete. The manifest is rebuilt each run from the wavs on disk.
"""

from __future__ import annotations

import gc
import json
import os
import sys

import numpy as np
import soundfile as sf

from ..pipeline import Context
from ..tts import build_engine


class SynthesizeStage:
    name = "synthesize"

    def done(self, ctx: Context) -> bool:
        return ctx.work.seg_manifest.exists()

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        segs = json.loads(ctx.work.translation.read_text(encoding="utf-8"))
        if [s["id"] for s in segs] != list(range(len(segs))):
            raise RuntimeError("translation ids not contiguous (synthesize never-drop)")

        # prior manifest → per-id (text_tts, flag), so an unchanged & previously-valid segment
        # can be skipped — but a prior synth_error is always retried (never cached as done)
        prior: dict[int, tuple[str | None, str | None]] = {}
        if ctx.work.seg_manifest.exists():
            try:
                doc = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
                for e in doc.get("segments", []):
                    prior[e["id"]] = (e.get("text_tts"), e.get("flag"))
            except Exception:
                pass                                       # torn manifest → rebuild from wavs

        engine = None                                      # lazy: a pure resume never loads Silero
        sr = cfg.tts_sample_rate
        out: list[dict] = []
        n_flag = 0
        try:
            for s in segs:
                sid = s["id"]
                wav = ctx.work.seg_wav(sid)
                text = (s.get("text_tts") or "").strip()
                flag: str | None = None

                prev = prior.get(sid)
                if (wav.exists() and prev is not None
                        and prev[0] == s.get("text_tts") and prev[1] != "synth_error"):
                    flag = prev[1]                          # resume: unchanged & valid — carry prior flag (e.g. empty_tts)
                elif not text:
                    sf.write(str(wav), np.zeros(0, dtype="float32"), sr)   # honest empty slot
                    flag = "empty_tts"
                else:
                    try:
                        if engine is None:
                            engine = build_engine(cfg)
                            sr = engine.sample_rate
                        tmp = wav.with_suffix(".wav.tmp")
                        engine.synthesize(text, tmp)
                        os.replace(tmp, wav)               # atomic: a wav that exists is complete
                    except Exception as e:
                        print(f"       [flag] id{sid}: synth_error {e}", file=sys.stderr)
                        sf.write(str(wav), np.zeros(0, dtype="float32"), sr)
                        flag = "synth_error"

                try:
                    info = sf.info(str(wav))
                    frames, srate = info.frames, info.samplerate
                except Exception as e:                     # corrupt/torn (kept) wav → flag, don't crash
                    if flag is None:
                        print(f"       [flag] id{sid}: synth_error {e}", file=sys.stderr)
                        flag = "synth_error"
                    frames, srate = 0, sr
                if frames and srate != sr:                 # silent sample-rate drift guard (readable wav only)
                    raise RuntimeError(f"id{sid} wav sr {srate} != engine sr {sr}")
                if flag:
                    n_flag += 1
                out.append({
                    "id": sid, "path": f"segments/{sid:05d}.wav",
                    "samples": frames, "duration": round(frames / sr, 3),
                    "sample_rate": srate, "start": s["start"], "end": s["end"],
                    "text_tts": s.get("text_tts"), "flag": flag,
                })
        finally:
            del engine
            gc.collect()

        if [e["id"] for e in out] != list(range(len(segs))):
            raise RuntimeError("segment ids not contiguous (synthesize never-drop)")
        doc = {
            "sample_rate": sr, "engine": cfg.tts_engine, "voice": cfg.tts_voice,
            "count": len(out), "n_flagged": n_flag, "segments": out,
        }
        tmp = ctx.work.seg_manifest.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, ctx.work.seg_manifest)
        print(f"       {len(out)} segments → manifest.json ({n_flag} flagged)")
