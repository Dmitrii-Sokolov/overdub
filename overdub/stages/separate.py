"""Separate stage: Demucs vocal separation → source_bed.wav (bed mode only).

Produces the no-vocals ambience/music bed the "bed" dub_mix mode lays under the RU dub.
Runs htdemucs (hardcoded — no model knob) in its own venv (.venv-demucs) as a CLI
subprocess: demucs's torch pins must not gamble the ASR stack.

Extracts a 44.1 kHz STEREO wav from source.mkv first — the 16 kHz mono source.wav used for
STT is unusable for separation. ~3 GB VRAM, standalone between assemble and mux (nothing
heavy is co-resident). done() is a no-op unless cfg.dub_mix == "bed"; the atomic
source_bed.wav is the resume gate — separation runs once per video.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from ..pipeline import Context
from ..workdir import replace_retry


class SeparateStage:
    name = "separate"

    def done(self, ctx: Context) -> bool:
        if ctx.cfg.dub_mix != "bed":
            return True                                    # no-op unless the bed is wanted
        if not ctx.work.dub_audio.exists():
            # Nothing to lay a bed UNDER. assemble ran before this stage and degraded (no speech,
            # no translation, no synthesis), so mux will ship the original audio untouched and a
            # ~3 GB-VRAM htdemucs pass would render an ambience track nobody mixes. Costs the most
            # of any wasted stage here: median 20 s, worst 449 s, and a music-only video — exactly
            # the no-speech case — is the slowest kind to separate.
            #
            # Reads as done() rather than an early return in run() so a resume does not re-decide
            # it every sweep. Safe because the driver always runs assemble first; an `--only
            # separate` before assemble would skip the bed, and the dub that appeared later would
            # then meet mux's bed-with-no-bed raise, which is the loud failure, not a silent one.
            return True
        return ctx.work.source_bed.exists()

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
