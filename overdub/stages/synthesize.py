"""Synthesize stage (Phase 1): Silero (eugene) renders each sentence to segments/*.wav.

Uses the TTS engine adapter (overdub.tts) so the engine can be swapped later.
"""

from __future__ import annotations

from ..pipeline import Context


class SynthesizeStage:
    name = "synthesize"

    def done(self, ctx: Context) -> bool:
        return ctx.work.seg_manifest.exists()

    def run(self, ctx: Context) -> None:
        raise NotImplementedError(
            "synthesize — Phase 1: Silero (overdub.tts) per-sentence text_tts "
            "→ segments/*.wav + manifest.json"
        )
