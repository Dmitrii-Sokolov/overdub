"""Silero RU TTS engine — native Russian, fixed voice, CPU, deterministic.

Loaded via torch.hub (snakers4/silero-models, cached in ~/.cache/torch/hub). Model release
is a config knob (`silero_model`): "v4_ru" (~38 MB, the long-standing default) or "v5_5_ru"
(~139 MB). Both expose the same five speakers — aidar, baya, kseniya, eugene, xenia — so a
release swap keeps every voice name valid.

v5 REJECTS Latin script (its symbol table is Cyrillic-only; Latin is silently stripped by the
model's own regex). That is safe here only because `text_tts` is Cyrillic-by-contract — the
pronounce chain transliterates every kept-Latin name before synthesis. Verified across the
12-video AI-Fluency batch: zero Latin characters in any `text_tts`. If that contract ever
loosens, v5 needs an out-of-alphabet filter; v4 tolerates the same input.

Output is written with soundfile, not torchaudio.save — torchaudio 2.11 routes save
through TorchCodec, so we sidestep that shifting backend entirely.
"""

from __future__ import annotations

from pathlib import Path

import soundfile as sf
import torch


class SileroEngine:
    LANGUAGE = "ru"
    MODEL_ID = "v4_ru"               # default release; overridden per-run by cfg.silero_model
    supports_seed = False            # deterministic: same text → same audio, reseed is a no-op
    supports_target = False          # no native speed — atempo does all timing fit

    def __init__(self, voice: str = "eugene", sample_rate: int = 48000, device: str = "cpu",
                 model_id: str | None = None) -> None:
        self.voice = voice
        self.sample_rate = sample_rate
        self.model_id = model_id or self.MODEL_ID
        model, _ = torch.hub.load(
            "snakers4/silero-models", "silero_tts",
            language=self.LANGUAGE, speaker=self.model_id, trust_repo=True,
        )
        model.to(torch.device(device))
        self._model = model

    def synthesize(self, text: str, out_path: Path, *, seed: int | None = None,
                   target_sec: float | None = None, max_sec: float | None = None) -> None:
        audio = self._model.apply_tts(
            text=text,
            speaker=self.voice,
            sample_rate=self.sample_rate,
            put_accent=True,
            put_yo=True,
        )
        # explicit format="WAV": callers pass atomic temp paths (…/00007.wav.tmp) whose
        # extension soundfile cannot infer a container from, so never rely on the suffix.
        sf.write(str(out_path), audio.cpu().numpy(), self.sample_rate, format="WAV", subtype="PCM_16")

    def begin_video(self) -> None:
        pass                     # no per-video failure state to reset (no worker, no seed)

    def close(self) -> None:
        pass
