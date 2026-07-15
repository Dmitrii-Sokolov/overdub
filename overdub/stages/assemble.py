"""Assemble stage (Phase 1): place each segment at its start ts, atempo-fit, pad → dub_ru.wav.

atempo is uncapped (extreme factors logged in report.json, not fixed). Also emits en.srt / ru.srt.
"""

from __future__ import annotations

from ..pipeline import Context


class AssembleStage:
    name = "assemble"

    def done(self, ctx: Context) -> bool:
        return ctx.work.dub_audio.exists()

    def run(self, ctx: Context) -> None:
        raise NotImplementedError(
            "assemble — Phase 1: atempo fit (uncapped) + silence pad → dub_ru.wav, "
            "log per-segment speed factor, write en.srt / ru.srt"
        )
