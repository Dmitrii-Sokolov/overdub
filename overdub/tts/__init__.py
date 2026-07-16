"""Pluggable TTS engines behind the TtsEngine protocol (base.py)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..config import Config
from .base import TtsEngine


def build_engine(cfg: Config) -> TtsEngine:
    if cfg.tts_engine == "silero":
        from .silero import SileroEngine

        return SileroEngine(voice=cfg.tts_voice, sample_rate=cfg.tts_sample_rate)
    if cfg.tts_engine == "f5":
        from .f5 import F5Engine

        return F5Engine(python=cfg.f5_python, ckpt=cfg.f5_ckpt, vocab=cfg.f5_vocab,
                        ref_audio=cfg.f5_ref_audio, ref_text=cfg.f5_ref_text,
                        nfe=cfg.f5_nfe, speed=cfg.f5_speed, default_seed=cfg.tts_seed)
    raise ValueError(f"unknown tts_engine: {cfg.tts_engine!r}")


def engine_sample_rate(cfg: Config) -> int:
    """Engine output sample rate WITHOUT loading a model. synthesize's lazy/resume path
    must not stamp Silero's 48 kHz onto an F5 manifest (empty slots, sr-drift guard)."""
    if cfg.tts_engine == "f5":
        from .f5 import F5Engine

        return F5Engine.sample_rate
    return cfg.tts_sample_rate


def synth_key(cfg: Config) -> str:
    """Canonical fingerprint of everything that changes rendered audio for the current
    config. The synthesize reuse guard compares it before serving any cached wav.

    INVARIANT: any new audio-affecting knob MUST enter this string — an omission is a
    silent-staleness bug by definition. The F5 narrator reference is fetched at setup
    and never committed, so its identity is the CONTENT hash, not the path: identical
    path with different bytes is a different voice.
    """
    if cfg.tts_engine == "f5":
        for p in (cfg.f5_ref_audio, cfg.f5_ref_text, cfg.f5_ckpt, cfg.f5_vocab):
            if not Path(p).exists():                       # same crafted message as F5Engine —
                raise RuntimeError(                        # not a bare FileNotFoundError
                    f"F5 asset missing: {p} — fetch it at setup (see SETUP.md); "
                    "overdub does not auto-download")
        h = hashlib.sha1()
        h.update(Path(cfg.f5_ref_audio).read_bytes())
        h.update(Path(cfg.f5_ref_text).read_bytes())
        ckpt, vocab = Path(cfg.f5_ckpt), Path(cfg.f5_vocab)
        return (f"f5|{Path(cfg.f5_ref_audio).stem}:{h.hexdigest()[:8]}"
                f"|ckpt={ckpt.stem}:{ckpt.stat().st_size}"     # model identity: name+size, not a
                f"|vocab={vocab.stem}:{vocab.stat().st_size}"  # content hash of a 2.7 GB file
                f"|sr=24000|nfe={cfg.f5_nfe}|speed={cfg.f5_speed}|seed={cfg.tts_seed}")
    return f"silero|{cfg.tts_voice}|sr={cfg.tts_sample_rate}"
