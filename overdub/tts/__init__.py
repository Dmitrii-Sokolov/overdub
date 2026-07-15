"""Pluggable TTS engines. Silero is the chosen engine; others go behind TtsEngine."""

from __future__ import annotations

from ..config import Config
from .base import TtsEngine


def build_engine(cfg: Config) -> TtsEngine:
    if cfg.tts_engine == "silero":
        from .silero import SileroEngine

        return SileroEngine(voice=cfg.tts_voice, sample_rate=cfg.tts_sample_rate)
    raise ValueError(f"unknown tts_engine: {cfg.tts_engine!r}")
