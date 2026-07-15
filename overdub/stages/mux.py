"""Mux stage (Phase 1): ffmpeg assembles the final MKV.

Video stream-copied (never re-encoded) + original audio + RU dub + EN/RU SRT.
"""

from __future__ import annotations

from ..pipeline import Context


class MuxStage:
    name = "mux"

    def done(self, ctx: Context) -> bool:
        return ctx.work.output.exists()

    def run(self, ctx: Context) -> None:
        raise NotImplementedError(
            "mux — Phase 1: ffmpeg -c:v copy + orig audio + RU dub + EN/RU SRT → output.mkv"
        )
