"""Pluggable TTS engines behind the TtsEngine protocol (base.py)."""

from __future__ import annotations

from ..config import Config
from .base import TtsEngine


def build_engine(cfg: Config) -> TtsEngine:
    if cfg.tts_engine == "silero":
        from .silero import SileroEngine

        return SileroEngine(voice=cfg.tts_voice, sample_rate=cfg.tts_sample_rate,
                            model_id=cfg.silero_model, breaks=cfg.silero_ssml_breaks)
    raise ValueError(f"unknown tts_engine: {cfg.tts_engine!r}")


def engine_sample_rate(cfg: Config) -> int:
    """Engine output sample rate WITHOUT loading a model — synthesize's lazy/resume path
    needs it before any model exists."""
    return cfg.tts_sample_rate


# Measured ru chars/sec per Silero voice, and the fixed per-unit overhead that goes with them
# (2026-07-25, over every Silero manifest on disk). The rate is a VOICE fact, not an engine one:
# eugene runs 35% faster than baya, so a single engine-wide number would mis-size every slot on a
# voice change. eugene's own figure is the well-measured one (247 units, 2 videos, between-video
# spread 3.9% — smaller than the ±11% p05/p95 spread BETWEEN units, which is why more videos would
# not sharpen it). The others are one video each: usable, not audited.
#
# Why two parameters. Silero's rate is flat above ~60 chars (19.50 / 19.42 / 19.75 ch/s across the
# 60-120 / 120-250 / 250-500 buckets) but drops to 17.86 below it — short units carry edge padding
# that does not scale with text. Modelling that as a fixed 163 ms per unit removes the bias
# (pred/actual median 1.004, p05 0.888 vs 0.851 for the one-parameter form), and 12% of real units
# are short enough to care.
_VOICE_RATE = {                     # voice: (ru chars per second, fixed seconds per unit)
    "eugene": (19.85, 0.163),
    "xenia": (17.83, 0.163),
    "kseniya": (15.47, 0.163),
    "aidar": (14.87, 0.163),
    "baya": (14.41, 0.163),
}


def voice_rate(cfg: Config) -> tuple[float, float] | None:
    """(chars_per_sec, fixed_sec) for the configured voice, or None when unknown.

    None means "no duration model available", and every caller must treat it as a reason to keep
    the previous behaviour — NEVER as a reason to fall back to another voice's rate. A wrong rate
    silently mis-sizes every translation in the run, which is worse than not sizing them at all."""
    if cfg.tts_engine != "silero":
        return None
    return _VOICE_RATE.get(cfg.tts_voice)


def target_chars(slot_sec: float | None, cfg: Config) -> int | None:
    """How many ru characters the voice can say inside `slot_sec`, or None if unknowable.

    This is the number the translator aims at instead of imitating the English length — the
    source's pace varies enormously (CV 41.7%) while the engine's does not (CV ~5%), so "keep it
    about as long as the English" cannot fit slots that were never the same shape.

    Deliberately NOT clamped to a minimum: a slot too short for any sentence is a real signal, and
    swallowing it here would hide it from the caller that can act on it."""
    rate = voice_rate(cfg)
    if rate is None or slot_sec is None:
        return None
    cps, fixed = rate
    return max(0, round((slot_sec - fixed) * cps))


def synth_key(cfg: Config) -> str:
    """Canonical fingerprint of everything that changes rendered audio for the current
    config. The synthesize reuse guard compares it before serving any cached wav.

    INVARIANT: any new audio-affecting knob MUST enter this string — an omission is a
    silent-staleness bug by definition.
    """
    # model release is audio-affecting (v4_ru and v5_5_ru are different voices under the same
    # speaker name), so it MUST be in the key — see the INVARIANT above. Legacy manifests keyed
    # without it predate the knob and were all v4_ru; they re-render once, which is correct.
    # breaks= joins for the same reason the release does: with it on, a grouped unit renders
    # with its swallowed pauses back in, which is different audio from the same text. Legacy
    # manifests keyed without it re-render once, which is correct.
    return (f"silero|{cfg.silero_model}|{cfg.tts_voice}|sr={cfg.tts_sample_rate}"
            f"|breaks={int(cfg.silero_ssml_breaks)}")
