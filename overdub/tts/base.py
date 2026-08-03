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
    supports_breaks: bool

    def synthesize(self, text: str, out_path: Path, *, seed: int | None = None,
                   target_sec: float | None = None, max_sec: float | None = None,
                   gaps: list[float] | None = None) -> float | None:
        """Render `text` to a mono wav at `out_path` (self.sample_rate).

        `seed=None` means the engine's configured base seed; deterministic engines ignore it.
        `target_sec`/`max_sec` (engines with supports_target only): the source span to fill
        and the slot cap — the engine picks a native speed to land near target_sec without
        exceeding max_sec (slot-fill). Returns the speed actually used,
        or None for engines without native speed.

        `gaps` (engines with supports_breaks only): the ORIGINAL inter-sentence silences a
        grouped unit swallowed, len(gaps) == members - 1. Grouping buys a continuous contour
        by deleting those pauses, which is exactly what makes the dub drift ahead of the
        picture and pile silence at the end of each slot; an engine that can place pauses
        puts them back where the speaker had them. `text` stays the plain joined string —
        it is what verify compares against, and it must never carry markup."""
        ...

    def begin_video(self) -> None:
        """Reset per-video failure state on a REUSED engine.

        A stage-major batch keeps one engine across the whole synthesize sweep, but the
        crash budget counts CONSECUTIVE failures within ONE video: without this reset a
        video that merely flagged 2 synth_errors hands the next video a budget of 1, and
        that video dies with TtsFatalError blaming a worker that is perfectly healthy.
        Engines with no such state implement it as a no-op (same shape as close())."""
        ...

    def close(self) -> None:
        """Release engine resources (worker process, model refs). Idempotent."""
        ...
