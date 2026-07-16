"""Verify stage (Phase 2): whisper-small round-trip on raw (unsped) audio.

Transcribe each generated segment back to Russian and compare against text_tts with the SAME
normalizer on both sides (normalize_for_compare) — comparing against raw text_ru would loop
forever on every normalized token ("джи-пи-ю" vs "GPU"). Runs on RAW wavs, BEFORE any atempo,
so speed-up never pollutes the round-trip. Silero is deterministic, so a failed segment is
FLAGGED in report.json, not reseeded (unlike translate's retry loop).

Similarity is difflib's char-level SequenceMatcher ratio (autojunk=False — the default would
treat common Cyrillic letters as junk on the ~240-char sentences and silently skew the score).
Char-level tolerates Russian inflectional endings that a word-token metric would false-flag,
while gross skips/mumbles still move enough characters to trip the threshold.

verify ADDS its own flag; it never overwrites the translate flag (carried read-only as
translate_flag). report.json is co-owned with assemble via overdub.report (merge by id).
"""

from __future__ import annotations

import gc
import json
import sys
from difflib import SequenceMatcher

import soundfile as sf

from .. import report
from ..asr import load_whisper
from ..normalize import normalize_for_compare
from ..pipeline import Context


def _frames(wav) -> int:
    """Frame count of a wav, or 0 if it is missing or has an unreadable/torn header — so one
    corrupt segment is flagged (missing_wav), never crashes the whole verify stage. The pipeline
    never blocks on a bad segment."""
    try:
        return sf.info(str(wav)).frames
    except Exception:
        return 0


class VerifyStage:
    name = "verify"

    def done(self, ctx: Context) -> bool:
        # marker key, NOT report.exists() — assemble also writes report.json, and an existence
        # gate would make verify believe it had run and silently skip verification forever.
        p = ctx.work.report
        if not p.exists():
            return False
        try:
            return bool(json.loads(p.read_text(encoding="utf-8")).get("verify"))
        except Exception:
            return False                                   # torn/foreign report → re-run

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        segs = json.loads(ctx.work.translation.read_text(encoding="utf-8"))
        if [s["id"] for s in segs] != list(range(len(segs))):
            raise RuntimeError("translation ids not contiguous (verify never-drop)")
        # fail LOUD if run out of order (e.g. --only verify before synthesize): otherwise every
        # segment flags missing_wav, the "verify" marker is written, and done() then skips
        # verification forever — silently disabling the safety net. Mirrors assemble's guard.
        if not ctx.work.seg_manifest.exists():
            raise RuntimeError("segments/manifest.json missing — run synthesize before verify")

        model = load_whisper(cfg.verify_model, cfg.whisper_device, cfg.whisper_compute_type)
        rep = report.load(ctx.work.report)                 # preserve any assemble fields
        n_flag = 0
        try:
            for s in segs:
                sid = s["id"]
                wav = ctx.work.seg_wav(sid)
                ref = normalize_for_compare(s.get("text_tts") or "")
                sim: float | None = None
                vflag: str | None = None
                hyp = ""

                if not ref:
                    vflag = "empty_ref"                    # blocks the empty-vs-empty ratio==1.0 pass
                elif not wav.exists() or _frames(wav) == 0:
                    vflag = "missing_wav"
                else:
                    try:
                        parts, _info = model.transcribe(
                            str(wav), language=cfg.target_lang, beam_size=5,
                            vad_filter=False, condition_on_previous_text=False,
                        )
                        hyp = " ".join(p.text.strip() for p in parts).strip()
                    except Exception as e:
                        vflag = "unreadable_wav"
                        print(f"       [flag] id{sid}: unreadable_wav {e}", file=sys.stderr)
                    else:
                        hyp_n = normalize_for_compare(hyp)
                        if not hyp_n:
                            sim, vflag = 0.0, "empty_hyp"
                        else:
                            sim = SequenceMatcher(None, ref, hyp_n, autojunk=False).ratio()
                            vflag = None if sim >= cfg.similarity_threshold else "low_similarity"

                report.upsert(
                    rep, sid, status=s["status"], translate_flag=s.get("flag"),
                    similarity=(round(sim, 4) if sim is not None else None),
                    verify_flag=vflag, hypothesis=hyp,
                )
                if vflag:
                    n_flag += 1
                    tail = "" if sim is None else f" ({sim:.2f})"
                    print(f"       [flag] id{sid}: {vflag}{tail}", file=sys.stderr)
        finally:
            del model
            gc.collect()
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass

        report.prune(rep, {s["id"] for s in segs})         # drop phantom records from a shrunk re-tune
        rep["video_id"] = ctx.work.root.name
        rep["similarity_threshold"] = cfg.similarity_threshold
        rep["verify"] = {"model": cfg.verify_model, "n_segments": len(segs), "n_flagged": n_flag}
        report.save(ctx.work.report, rep)
        print(f"       {len(segs)} segments verified ({n_flag} flagged)")
