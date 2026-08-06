"""Separate stage: Demucs vocal separation → source_bed.wav (bed mode only).

Produces the no-vocals ambience/music bed the "bed" dub_mix mode lays under the RU dub.
Runs htdemucs (hardcoded — no model knob) in its own venv (.venv-demucs) as a CLI
subprocess: demucs's torch pins must not gamble the ASR stack.

Extracts a 44.1 kHz STEREO wav from source.mkv first — the 16 kHz mono source.wav used for
STT is unusable for separation. ~3 GB VRAM; done() is a no-op unless cfg.dub_mix == "bed",
and the atomic source_bed.wav is the resume gate — separation runs once per video.

POSITION IS NOT FIXED (2026-08-06). Its only hard input is source.mkv, so the stage may run
any time after download — see done() for the gate that lets it. In the default stage-major
sweep it still sits between assemble and mux with nothing heavy co-resident; run it during
the translate seam instead and it shares the card with nothing, because the pipeline process
that held the Parakeet worker has already exited by then. What it must NOT be scheduled
beside is transcribe: demucs is the larger of the two GPU consumers, so overlapping them
delays the transcripts and therefore the whole batch's first translation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from ..pipeline import Context
from ..workdir import replace_retry


def _has_speech(work) -> bool:
    """Does sentences.json hold at least one sentence? Never raises.

    Missing, torn or empty all read as False — "no evidence a dub is coming". False is the
    conservative answer for the gate below: it costs a bed that the loud failure downstream still
    catches (mux raises on bed mode with a dub and no bed), where True would spend an htdemucs
    pass on the strength of a file nobody could parse."""
    try:
        return bool(json.loads(work.sentences.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


class SeparateStage:
    name = "separate"

    def done(self, ctx: Context) -> bool:
        if ctx.cfg.dub_mix != "bed":
            return True                                    # no-op unless the bed is wanted
        if ctx.work.source_bed.exists():
            return True
        # Will this video get a dub? Two pieces of evidence, and the stage runs on EITHER, because
        # they become available at different times and only the weaker one exists early:
        #
        #   dub_ru.wav — assemble has run and produced one. Definitive, and the only evidence
        #     there was until 2026-08-06.
        #   a non-empty transcript — the earliest signal, available right after transcribe. It is
        #     what lets separate run BEFORE assemble, which is the point: demucs is the only GPU
        #     work that depends on nothing but source.mkv, so it can fill the translate seam's
        #     idle GPU instead of sitting in the post-translate tail (PLAN, measured: 301.5 s of
        #     a 2438.6 s batch).
        #
        # Skipping still protects the expensive case it was built for. A no-speech video — a
        # music-only clip, the slowest kind to separate at up to 449 s — has an EMPTY transcript
        # and no dub, so it matches neither and is skipped exactly as before. What the transcript
        # arm newly exposes is narrower: a video with speech whose translation or synthesis then
        # fails pays one htdemucs pass for a bed nobody mixes. That is the accepted trade, and mux
        # does not mind — it requires the bed only when a dub exists.
        #
        # Still a done() rather than an early return in run() so a resume does not re-decide it
        # every sweep.
        return not (ctx.work.dub_audio.exists() or _has_speech(ctx.work))

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH — required for separate. "
                               "Install ffmpeg; overdub does not auto-install.")
        if not Path(cfg.demucs_python).exists():
            raise RuntimeError(
                f"demucs venv missing: {cfg.demucs_python} — create .venv-demucs per SETUP.md; "
                "overdub does not auto-install")
        if not ctx.work.source_video.exists():
            raise RuntimeError("source.mkv missing — run download before separate")

        full = ctx.work.root / "source_full.wav"           # 44.1k stereo, temp
        out_dir = ctx.work.root / "_demucs"
        try:
            t0 = time.perf_counter()
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(ctx.work.source_video),
                 "-vn", "-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le", str(full)],
                check=True,
            )
            extract_s = time.perf_counter() - t0
            t0 = time.perf_counter()
            subprocess.run(
                [str(cfg.demucs_python), "-m", "demucs.separate", "--two-stems", "vocals",
                 "-n", "htdemucs", "-d", "cuda", "-o", str(out_dir), str(full)],
                check=True,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            demucs_s = time.perf_counter() - t0
            bed = out_dir / "htdemucs" / full.stem / "no_vocals.wav"
            if not bed.exists():
                raise RuntimeError(f"demucs produced no bed at {bed}")
            replace_retry(bed, ctx.work.source_bed)        # atomic: a bed that exists is complete
        finally:
            full.unlink(missing_ok=True)
            shutil.rmtree(out_dir, ignore_errors=True)
        # detail.separate: work_sec is the ffmpeg EXTRACT — the one part that scales with audio
        # length (decode source.mkv → 44.1k stereo wav). The demucs subprocess is recorded beside it
        # but bills as OVERHEAD, not work: htdemucs load and inference are inseparable inside the CLI
        # subprocess, and DECISIONS 2026-07-19 measured the demucs wall's slope against audio length
        # at R²=0.000 — load-dominated, does not scale — so counting it as work overstated rtf_work
        # by the whole demucs wall (~13.2 s/video). overhead[separate] = wall − work_sec then lands
        # that load where it belongs. Never-raises, like every record_stage_detail caller.
        from .. import timings
        timings.record_stage_detail(ctx.work, "separate",
                                      work_sec=round(extract_s, 3),
                                      demucs_sec=round(demucs_s, 3))
        print("       source_bed.wav ← htdemucs no-vocals stem")
