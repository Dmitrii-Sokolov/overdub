"""Unit tests for the no-speech path: a video whisper heard nothing in still ships.

Run: .venv-asr/Scripts/python.exe tests/test_no_speech.py   (or via pytest)
Filesystem only. The property under test is CONVERGENCE — every URL in the queue yields a
container in out/ — and the line it must not cross: an ABSENT transcript is not an empty one and
still has to stop the run loudly.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.config import Config  # noqa: E402
from overdub.pipeline import Context  # noqa: E402
from overdub.stages.separate import SeparateStage  # noqa: E402
from overdub.stages.translate import TranslateStage  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

VID = "vid00000001"


def _ctx(tmp: Path, cfg: Config | None = None) -> Context:
    work = WorkDir(root=tmp / VID)
    work.root.mkdir(parents=True, exist_ok=True)
    cfg = Config() if cfg is None else cfg
    cfg.work_root = tmp
    return Context(url=f"https://youtu.be/{VID}", cfg=cfg, work=work)


def _quiet(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


def _raises(fn, *a) -> bool:
    try:
        _quiet(fn, *a)
        return False
    except RuntimeError:
        return True


# --- translate: the one case that degrades instead of raising --------------------------
def test_empty_transcript_writes_an_empty_translation() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.sentences.write_text("[]", encoding="utf-8")
        _quiet(TranslateStage().run, ctx)
        assert json.loads(ctx.work.translation.read_text(encoding="utf-8")) == []


def test_empty_transcript_says_so_out_loud() -> None:
    # Silence here would make a no-speech video indistinguishable from a dubbed one in the log.
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.sentences.write_text("[]", encoding="utf-8")
        _, out = _quiet(TranslateStage().run, ctx)
        assert "no speech" in out.lower()


def test_missing_transcript_still_raises() -> None:
    # The distinction the whole change rests on: transcribe never ran, so this video has NOT been
    # shown to have no speech. Shipping it would be the silent failure the stage exists to stop.
    with tempfile.TemporaryDirectory() as d:
        assert _raises(TranslateStage().run, _ctx(Path(d)))


def test_torn_transcript_still_raises() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.sentences.write_text("{not json", encoding="utf-8")
        assert _raises(TranslateStage().run, ctx)


def test_transcript_that_is_not_a_list_still_raises() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.sentences.write_text('{"sentences": []}', encoding="utf-8")
        assert _raises(TranslateStage().run, ctx)


def test_transcript_with_speech_and_no_translation_still_raises() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.sentences.write_text(
            json.dumps([{"id": 0, "text": "Hello.", "start": 0.0, "end": 1.0}]), encoding="utf-8")
        assert _raises(TranslateStage().run, ctx)


# --- separate: no dub, no bed ----------------------------------------------------------
def test_separate_skips_when_there_is_no_dub_to_lay_it_under() -> None:
    # The most expensive wasted stage on a no-speech video, and a music-only clip is the slowest
    # kind to separate — exactly the case this path is for.
    with tempfile.TemporaryDirectory() as d:
        cfg = Config()
        cfg.dub_mix = "bed"
        ctx = _ctx(Path(d), cfg)
        assert SeparateStage().done(ctx) is True


def test_separate_still_runs_when_a_dub_exists_without_a_bed() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = Config()
        cfg.dub_mix = "bed"
        ctx = _ctx(Path(d), cfg)
        ctx.work.dub_audio.write_bytes(b"RIFF")
        assert SeparateStage().done(ctx) is False


def test_separate_stays_a_no_op_outside_bed_mode() -> None:
    with tempfile.TemporaryDirectory() as d:
        cfg = Config()
        cfg.dub_mix = "replace"
        ctx = _ctx(Path(d), cfg)
        assert SeparateStage().done(ctx) is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all no-speech tests passed")
