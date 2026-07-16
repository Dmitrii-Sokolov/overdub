"""TTS engine adapter interface. Every engine renders one text to one wav file."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TtsEngineError(RuntimeError):
    """Per-request synthesis failure — flaggable (synth_error); the stage moves on."""


class TtsFatalError(RuntimeError):
    """Systemic engine failure (worker crashing repeatedly, dead CUDA driver) — must
    escape the per-segment catch and fail the stage loudly instead of grinding out
    hundreds of synth_error flags overnight."""


class TtsEngine(Protocol):
    sample_rate: int
    supports_seed: bool
    supports_target: bool

    def synthesize(self, text: str, out_path: Path, *, seed: int | None = None,
                   target_sec: float | None = None, max_sec: float | None = None) -> float | None:
        """Render `text` to a mono wav at `out_path` (self.sample_rate).

        `seed=None` means the engine's configured base seed; deterministic engines ignore it.
        `target_sec`/`max_sec` (engines with supports_target only): the source span to fill
        and the slot cap — the engine picks a native speed to land near target_sec without
        exceeding max_sec (slot-fill; see f5.plan_speed). Returns the speed actually used,
        or None for engines without native speed."""
        ...

    def close(self) -> None:
        """Release engine resources (worker process, model refs). Idempotent."""
        ...
