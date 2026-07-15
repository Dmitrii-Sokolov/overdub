"""Pipeline configuration. Flat TOML (overdub.toml) overrides the defaults below."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    # work dir
    work_root: Path = Path("work")

    # language (fixed EN->RU for v1)
    source_lang: str = "en"
    target_lang: str = "ru"

    # STT — faster-whisper
    whisper_model: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    # translation — Qwen3-14B via Ollama (OpenAI-compatible)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen3:14b"
    num_ctx: int = 4096
    context_window: int = 4  # previous sentence pairs fed as rolling context

    # TTS — Silero
    tts_engine: str = "silero"
    tts_voice: str = "eugene"
    tts_sample_rate: int = 48000

    # verification — whisper-small round-trip
    verify_model: str = "small"
    similarity_threshold: float = 0.8

    @classmethod
    def load(cls, path: Path | None) -> "Config":
        cfg = cls()
        if path is None or not Path(path).exists():
            return cfg
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        for key, value in data.items():
            if not hasattr(cfg, key):
                print(f"[config] unknown key ignored: {key}")
                continue
            current = getattr(cfg, key)
            setattr(cfg, key, Path(value) if isinstance(current, Path) else value)
        return cfg
