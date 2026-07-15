"""Silero v4_ru TTS engine — native Russian, fixed voice, CPU, deterministic.

Loaded via torch.hub (snakers4/silero-models, ~38 MB, cached in ~/.cache/torch/hub).
Output is written with soundfile, not torchaudio.save — torchaudio 2.11 routes save
through TorchCodec, so we sidestep that shifting backend entirely.
"""

from __future__ import annotations

from pathlib import Path

import soundfile as sf
import torch


class SileroEngine:
    LANGUAGE = "ru"
    MODEL_ID = "v4_ru"

    def __init__(self, voice: str = "eugene", sample_rate: int = 48000, device: str = "cpu") -> None:
        self.voice = voice
        self.sample_rate = sample_rate
        model, _ = torch.hub.load(
            "snakers4/silero-models", "silero_tts",
            language=self.LANGUAGE, speaker=self.MODEL_ID, trust_repo=True,
        )
        model.to(torch.device(device))
        self._model = model

    def synthesize(self, text: str, out_path: Path) -> None:
        audio = self._model.apply_tts(
            text=text,
            speaker=self.voice,
            sample_rate=self.sample_rate,
            put_accent=True,
            put_yo=True,
        )
        sf.write(str(out_path), audio.cpu().numpy(), self.sample_rate)
