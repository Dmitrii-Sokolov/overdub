"""Translate stage (Phase 1): Qwen3-14B via Ollama, context-aware per sentence.

Sentences translated in order with a rolling context window (previous EN+RU pairs).
Output per sentence: text_ru (raw → subtitles) + text_tts (normalized → synthesis).
"""

from __future__ import annotations

from ..pipeline import Context


class TranslateStage:
    name = "translate"

    def done(self, ctx: Context) -> bool:
        return ctx.work.translation.exists()

    def run(self, ctx: Context) -> None:
        raise NotImplementedError(
            "translate — Phase 1: Ollama qwen3:14b, rolling context window, "
            "text_ru + normalized text_tts → translation.json"
        )
