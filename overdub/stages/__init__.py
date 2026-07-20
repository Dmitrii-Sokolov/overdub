"""Pipeline stages, in execution order."""

from __future__ import annotations

from ..config import Config
from ..pipeline import Stage
from .assemble import AssembleStage
from .download import DownloadStage
from .mux import MuxStage
from .separate import SeparateStage
from .synthesize import SynthesizeStage
from .transcribe import TranscribeStage
from .translate import TranslateStage
from .verify import VerifyStage


def all_stages(cfg: Config) -> list[Stage]:
    return [
        DownloadStage(),
        TranscribeStage(),
        TranslateStage(),
        SynthesizeStage(),
        VerifyStage(),
        AssembleStage(),
        SeparateStage(),   # no-op unless dub_mix == "bed" (done() gates on the mode)
        MuxStage(),
    ]


def scout_stages(cfg: Config) -> list[Stage]:
    """The scout list: fetch audio, transcribe, stop (DECISIONS 2026-07-20).

    A LIST, not `only={"download","transcribe"}`. run_pipeline checks STOP BEFORE the
    only/done filters, so an --only composition would still sweep 8 stages per video and grid
    8 STOP checkpoints to do 2 stages of work; the header-suppression branch in the stage-major
    driver exists to hide exactly that noise. Semantically `only` means "run these", not "the
    pipeline ends here" — and it cannot express the audio-only download at all, because that
    lives INSIDE the stage.

    The audio-only DownloadStage and the truncation are constructed HERE, together, in one
    expression. That is the point: the two facts can never desynchronize into "truncated list
    + full download" (100 GB for a triage pass) or "full list + audio-only download" (mux
    fails at the end of an eight-hour run).

    Must stay a strict PREFIX of all_stages: a promoted video re-enters the full pipeline on
    the artifacts these two produced. Pinned by tests/test_scout.py.

    Under stage-major ONE DownloadStage instance serves every video of the batch. Safe: stages
    carry no per-instance state beyond `audio_only`, which is a constant for the whole run.

    `cfg` is unused; it is accepted for symmetry with all_stages so the call site in cli stays
    a single expression.
    """
    return [DownloadStage(audio_only=True), TranscribeStage()]
