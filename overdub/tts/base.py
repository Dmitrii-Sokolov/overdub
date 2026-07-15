"""TTS engine adapter interface. Every engine renders one text to one wav file."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TtsEngine(Protocol):
    sample_rate: int

    def synthesize(self, text: str, out_path: Path) -> None:
        """Render `text` to a mono wav at `out_path` (self.sample_rate)."""
        ...
