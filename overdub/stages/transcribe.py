"""Transcribe stage (Phase 1): faster-whisper large-v3 → word timestamps → sentences.json.

Words are re-assembled into sentences with [start, end]; overlong sentences split
on clause boundaries. The sentence is the unit of translation, synthesis and sync.
"""

from __future__ import annotations

from ..pipeline import Context


class TranscribeStage:
    name = "transcribe"

    def done(self, ctx: Context) -> bool:
        return ctx.work.sentences.exists()

    def run(self, ctx: Context) -> None:
        raise NotImplementedError(
            "transcribe — Phase 1: faster-whisper large-v3 (word_timestamps) "
            "→ sentence re-segmentation → sentences.json"
        )
