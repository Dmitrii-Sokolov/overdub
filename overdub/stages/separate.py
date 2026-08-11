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


SR = 44100                                                 # htdemucs's rate; the bed matches it


def _probe_duration(src: Path) -> float:
    """Source duration in seconds, off ffprobe. Raises — the chunk plan cannot be guessed."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(src)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def _plan_chunks(duration: float, chunk_s: int, overlap_s: float) -> list[tuple[float, float]]:
    """(start, end) of every extraction window, in seconds, in order.

    Each window carries its core [i*chunk_s, (i+1)*chunk_s) plus overlap_s of context on both
    sides, clamped to the track. The cores tile the track exactly once — the overlap is extra
    material for the blend and never moves a boundary — so the stitched bed is the length of
    the source whatever the chunking is.
    """
    out = []
    i = 0
    while i * chunk_s < duration:
        core_a = i * chunk_s
        core_b = min((i + 1) * chunk_s, duration)
        out.append((max(0.0, core_a - overlap_s), min(duration, core_b + overlap_s)))
        i += 1
    return out


def _extract_chunks(src: Path, dst_dir: Path, plan: list[tuple[float, float]]) -> list[Path]:
    """Decode one 44.1k stereo wav per window. Seeks before -i, so each is a cheap partial read."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for n, (a, b) in enumerate(plan):
        p = dst_dir / f"part_{n:03d}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.6f}", "-t", f"{b - a:.6f}",
             "-i", str(src), "-vn", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le", str(p)],
            check=True,
        )
        paths.append(p)
    return paths


def _stitch_bed(stems: list[tuple[Path, float]], dest: Path, duration: float,
                overlap_s: float) -> None:
    """Blend the per-chunk no-vocals stems back into one bed of the ORIGINAL length.

    Streamed, and that is not a style choice: an accumulator for the whole track would rebuild
    the very allocation chunking exists to avoid (7.9 h of float32 stereo is 10 GB before the
    weight array). Only the window being written is ever resident.

    The blend is a WEIGHTED AVERAGE under a linear ramp, not an equal-power crossfade. Both
    chunks are separations of the same seconds of audio, so their overlap is correlated and a
    sqrt law would push the seam ~3 dB loud; averaging is also self-normalising, which keeps the
    ramps from having to be exactly complementary at the clamped first and last windows.
    """
    import numpy as np
    import soundfile as sf

    total = int(round(duration * SR))
    span = int(round(2 * overlap_s * SR))                  # a blend zone is overlap on both sides
    with sf.SoundFile(dest, "w", samplerate=SR, channels=2, subtype="PCM_16") as out:
        pos = 0                                            # frames of the bed already written
        for i, (stem, start) in enumerate(stems):
            head = int(round(start * SR))                  # where this stem sits on the timeline
            last = i + 1 == len(stems)
            # The blend zone opens where the NEXT window opens and runs one overlap past the cut.
            blend_a = total if last else int(round(stems[i + 1][1] * SR))
            blend_b = total if last else min(total, blend_a + span)
            with sf.SoundFile(stem) as f:
                if blend_a > pos:                          # this stem alone owns [pos, blend_a)
                    f.seek(min(max(0, pos - head), len(f)))
                    solo = f.read(blend_a - pos, dtype="float32", always_2d=True)
                    out.write(solo)
                    pos += len(solo)
                if last or blend_b <= blend_a:
                    continue
                f.seek(min(max(0, blend_a - head), len(f)))
                fading = f.read(blend_b - blend_a, dtype="float32", always_2d=True)
            with sf.SoundFile(stems[i + 1][0]) as nxt:
                rising = nxt.read(len(fading), dtype="float32", always_2d=True)
            n = min(len(fading), len(rising))
            if not n:
                continue
            w = np.linspace(1.0, 0.0, n, dtype=np.float32)[:, None]
            out.write(fading[:n] * w + rising[:n] * (1.0 - w))
            pos += n
        if pos < total:            # short by a rounding frame or a truncated stem: pad, never clip
            out.write(np.zeros((total - pos, 2), dtype=np.float32))


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
        for tool in ("ffmpeg", "ffprobe"):                 # ffprobe reads the duration the plan
            if shutil.which(tool) is None:                 # is cut from; same package as ffmpeg
                raise RuntimeError(f"{tool} not found on PATH — required for separate. "
                                   "Install ffmpeg; overdub does not auto-install.")
        if not Path(cfg.demucs_python).exists():
            raise RuntimeError(
                f"demucs venv missing: {cfg.demucs_python} — create .venv-demucs per SETUP.md; "
                "overdub does not auto-install")
        if not ctx.work.source_video.exists():
            raise RuntimeError("source.mkv missing — run download before separate")

        full = ctx.work.root / "source_full.wav"           # 44.1k stereo, temp
        out_dir = ctx.work.root / "_demucs"
        part_dir = ctx.work.root / "_parts"
        try:
            t0 = time.perf_counter()
            duration = _probe_duration(ctx.work.source_video)
            chunk_s = cfg.separate_chunk_sec
            if chunk_s and duration > chunk_s:
                plan = _plan_chunks(duration, chunk_s, cfg.separate_overlap_sec)
                parts = _extract_chunks(ctx.work.source_video, part_dir, plan)
                starts = [a for a, _ in plan]
                print(f"       {duration / 3600:.2f}h → {len(parts)} chunk(s) "
                      f"of {chunk_s}s (+{cfg.separate_overlap_sec:g}s overlap)")
            else:
                # -rf64 auto: WAV stores its size in a 32-bit field, so at 176400 B/s (44.1k
                # stereo s16) anything past 6h46m overflows it. Unreachable while chunking is
                # on — it is the net for cfg.separate_chunk_sec = 0.
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", str(ctx.work.source_video),
                     "-vn", "-ac", "2", "-ar", str(SR), "-c:a", "pcm_s16le",
                     "-rf64", "auto", str(full)],
                    check=True,
                )
                parts, starts = [full], [0.0]
            extract_s = time.perf_counter() - t0
            t0 = time.perf_counter()
            # Every chunk in ONE invocation: htdemucs is load-dominated (~13 s, DECISIONS
            # 2026-07-19) and processes its tracks one at a time, so this pays that load once
            # instead of per chunk while keeping the peak allocation at a single chunk's.
            subprocess.run(
                [str(cfg.demucs_python), "-m", "demucs.separate", "--two-stems", "vocals",
                 "-n", "htdemucs", "-d", "cuda", "-o", str(out_dir), *[str(p) for p in parts]],
                check=True,
                env={**os.environ, "PYTHONUTF8": "1"},
            )
            demucs_s = time.perf_counter() - t0
            stems = [(out_dir / "htdemucs" / p.stem / "no_vocals.wav", s)
                     for p, s in zip(parts, starts)]
            missing = [str(s) for s, _ in stems if not s.exists()]
            if missing:
                raise RuntimeError(f"demucs produced no bed at {', '.join(missing)}")
            if len(stems) == 1:
                replace_retry(stems[0][0], ctx.work.source_bed)   # atomic: a bed that exists is
            else:                                                 # complete
                tmp = ctx.work.root / "_bed.wav"
                _stitch_bed(stems, tmp, duration, cfg.separate_overlap_sec)
                replace_retry(tmp, ctx.work.source_bed)
        finally:
            full.unlink(missing_ok=True)
            shutil.rmtree(out_dir, ignore_errors=True)
            shutil.rmtree(part_dir, ignore_errors=True)
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
