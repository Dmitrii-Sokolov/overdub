"""Download stage: yt-dlp fetches the video, ffmpeg extracts a 16k mono WAV for STT."""

from __future__ import annotations

import subprocess

from ..pipeline import Context


class DownloadStage:
    name = "download"

    def done(self, ctx: Context) -> bool:
        return ctx.work.source_video.exists() and ctx.work.source_audio.exists()

    def run(self, ctx: Context) -> None:
        w = ctx.work
        # video kept intact (stream-copied at mux time — never re-encoded)
        subprocess.run(
            [
                "yt-dlp",
                "-f", "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b",
                "--merge-output-format", "mkv",
                "-o", str(w.source_video),
                ctx.url,
            ],
            check=True,
        )
        # 16 kHz mono WAV — feeds whisper and reference/segment work
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(w.source_video),
                "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                str(w.source_audio),
            ],
            check=True,
        )
