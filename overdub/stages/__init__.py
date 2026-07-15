"""Pipeline stages, in execution order."""

from __future__ import annotations

from ..config import Config
from ..pipeline import Stage
from .assemble import AssembleStage
from .download import DownloadStage
from .mux import MuxStage
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
        MuxStage(),
    ]
