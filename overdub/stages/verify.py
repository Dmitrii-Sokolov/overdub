"""Verify stage (Phase 2): whisper-small round-trip on raw (unsped) audio.

Transcribe each segment back, compare against text_tts (same normalizer both sides).
Silero is deterministic, so a failed segment is flagged in report.json, not reseeded.
"""

from __future__ import annotations

from ..pipeline import Context


class VerifyStage:
    name = "verify"

    def done(self, ctx: Context) -> bool:
        return ctx.work.report.exists()

    def run(self, ctx: Context) -> None:
        raise NotImplementedError(
            "verify — Phase 2: whisper-small round-trip vs text_tts, "
            "similarity threshold, flag failures → report.json"
        )
