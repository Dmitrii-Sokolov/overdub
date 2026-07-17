"""Pipeline configuration. Flat TOML (overdub.toml) overrides the defaults below."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    # work dir
    work_root: Path = Path("work")
    # export — title-named final MKVs: "<title> [<video id>].mkv" (hardlink/copy of output.mkv)
    output_dir: Path = Path("out")

    # language (fixed EN->RU for v1)
    source_lang: str = "en"
    target_lang: str = "ru"

    # STT — faster-whisper
    whisper_model: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    whisper_condition_on_previous: bool = True   # feed prior text as context so whisper
                                                 # PUNCTUATES properly. False left 60-206 s
                                                 # terminator-free blocks that the resegmenter
                                                 # bisected mid-phrase (the "period mid-sentence"
                                                 # class, DECISIONS 2026-07-17). Measured safe:
                                                 # no repetition-loop on the music video. Flip
                                                 # to False only if a source makes whisper loop

    # translation — Qwen3-14B via Ollama native /api/chat (think:false; see stages/translate.py)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    num_ctx: int = 4096
    context_window: int = 4          # previous OK sentence pairs fed as rolling context
    ollama_timeout_s: float = 120.0
    translate_temperature: float = 0.2
    translate_top_p: float = 0.9
    translate_seed: int = 42
    translate_max_retries: int = 3
    translate_max_tokens: int = 512  # ramble/echo guard
    translate_max_len_ratio: float = 3.0   # runaway guard: text_ru chars vs source
    latin_ratio_max: float = 0.30    # english-echo detector (Latin fraction of alpha chars)
    translate_context_char_cap: int = 2400  # drop oldest ctx pairs beyond this (KV knife-edge)
    translate_unload: bool = True    # POST keep_alive:0 after the stage to free VRAM

    # TTS — engine selection + seed policy
    tts_engine: str = "f5"           # "f5" (production, Phase-3 ear check 2026-07-16) | "silero" (fallback)
    tts_voice: str = "eugene"        # silero-only
    tts_sample_rate: int = 48000     # silero-only (F5 sr is engine-owned: 24000)
    tts_seed: int = 42               # base seed (seed-capable engines); retries use seed+attempt
    tts_max_retries: int = 3         # reseed attempts after the first try (seed-capable engines)

    # TTS — F5/ESpeech (worker process in .venv-f5tts; see overdub/tts/f5.py)
    f5_python: Path = Path(".venv-f5tts/Scripts/python.exe")
    f5_ckpt: Path = Path("models/espeech-rlv2/espeech_tts_rlv2.pt")
    f5_vocab: Path = Path("models/espeech-rlv2/vocab.txt")
    f5_ref_audio: Path = Path("models/refs/ref_espeech_demo.wav")
    f5_ref_text: Path = Path("models/refs/ref_espeech_demo.txt")
    f5_nfe: int = 48                 # 32 is ~30% faster; quality delta not ear-checked yet
    f5_speed: float = 1.0            # base narrator pace (narrator calibration, DECISIONS)
    f5_speed_floor: float = 0.75     # max stretch: min per-unit speed as a MULTIPLIER of
                                     # f5_speed (slot-fill; 1.0 disables stretching)
    f5_speed_ceil: float = 1.1       # max native compression multiplier before atempo tops
                                     # up. Ear 2026-07-16: native ≥~1.3 DROPS words mid-word
                                     # (atempo never does) — keep ≲1.15; 1.0 disables

    # dead-air / mix (see DECISIONS 2026-07-16 dead-air entry + 2026-07-17 ear verdict)
    group_gap_max: float = 0.4       # join adjacent sentences into one render unit when the
                                     # inter-sentence gap ≤ this (s); 0.0 disables grouping
    dub_mix: str = "bed"             # "replace" | "duck" | "bed" (no-vocals stem at original
                                     # level under the dub — production default by ear)
    demucs_python: Path = Path(".venv-demucs/Scripts/python.exe")  # bed mode only

    # verification — whisper-small round-trip
    verify_model: str = "small"
    similarity_threshold: float = 0.9      # unit-level gate (0.8 → 0.9, 2026-07-17: units are
                                           # long joined strings that dilute local defects —
                                           # the 17:02 word-drop scored 0.836 and passed 0.8)
    similarity_threshold_compressed: float = 0.9   # stricter gate for natively compressed
                                                   # units (word-drop risk; unit_sim_threshold)

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
