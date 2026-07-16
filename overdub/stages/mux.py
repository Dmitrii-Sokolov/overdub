"""Mux stage (Phase 1): ffmpeg assembles the final MKV.

Video stream-copied (NEVER re-encoded) + original audio (copied) + RU dub (aac 128k, set as
the DEFAULT track — this is a dubbing tool) + EN/RU SRT, each with language metadata. Explicit
per-stream maps (not -map 0) so extra source streams don't leak; strict -map 0:a:0 (no '?') so a
source without an audio track fails loud instead of silently relabeling the dub as a:0. aac is
chosen over libopus because the "external binaries not guaranteed" contract forbids gambling on
an optional encoder — every ffmpeg build ships aac. Atomic .mkv.tmp + os.replace so a killed
ffmpeg can't leave a partial output.mkv that satisfies done().
"""

from __future__ import annotations

import os
import shutil
import subprocess

from ..pipeline import Context


class MuxStage:
    name = "mux"

    def done(self, ctx: Context) -> bool:
        return ctx.work.output.exists()

    def run(self, ctx: Context) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH — required for mux. "
                               "Install ffmpeg; overdub does not auto-install.")
        w = ctx.work
        for p in (w.source_video, w.dub_audio, w.en_srt, w.ru_srt):
            if not p.exists():
                raise RuntimeError(f"mux input missing: {p} — run earlier stages first")
        tmp = w.output.with_suffix(".mkv.tmp")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(w.source_video), "-i", str(w.dub_audio),
                "-i", str(w.en_srt), "-i", str(w.ru_srt),
                "-map", "0:v:0", "-map", "0:a:0", "-map", "1:a:0", "-map", "2:0", "-map", "3:0",
                "-c:v", "copy", "-c:a:0", "copy", "-c:a:1", "aac", "-b:a:1", "128k", "-c:s", "srt",
                "-metadata:s:a:0", "language=eng", "-metadata:s:a:0", "title=Original",
                "-metadata:s:a:1", "language=rus", "-metadata:s:a:1", "title=Russian dub",
                "-metadata:s:s:0", "language=eng", "-metadata:s:s:1", "language=rus",
                "-disposition:a:0", "0", "-disposition:a:1", "default",
                "-f", "matroska", str(tmp),
            ],
            check=True,
        )
        os.replace(tmp, w.output)
        print(f"       → {w.output.name}")
