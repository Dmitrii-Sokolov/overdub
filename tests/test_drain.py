"""Unit tests for scripts/drain.py — the per-video drain that runs beside the Sonnet wave.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_drain.py   (or via pytest)
Filesystem only; `drain_one` is replaced so no subprocess, GPU or network is touched.

The properties worth pinning are all about what the scheduler must NEVER do, because it runs
unattended beside a wave and every failure mode here is silent: it must not treat a half-written
draft as ready, must not consume a STOP that the pipeline is the one able to report, and must not
let a video it could not drain disappear — the queue is the human's and a scheduler never shortens
it (queue-contract §3).
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import drain  # noqa: E402
from overdub.pipeline import STOP_NAME  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

VIDS = [f"vid0000000{i}" for i in (1, 2)]
URLS = [f"https://youtu.be/{v}" for v in VIDS]


def _setup(tmp: Path) -> tuple[Path, Path]:
    """A queue file plus a config pointing work_root into tmp. Returns (queue, config)."""
    q = tmp / "queue.txt"
    q.write_text("\n".join(URLS) + "\n", encoding="utf-8")
    c = tmp / "overdub.toml"
    root = str(tmp / "work").replace("\\", "/")
    c.write_text(f'work_root = "{root}"\noutput_dir = "{str(tmp / "out").replace(chr(92), "/")}"\n',
                 encoding="utf-8")
    (tmp / "work").mkdir(parents=True, exist_ok=True)
    return q, c


def _work(tmp: Path, vid: str) -> WorkDir:
    return WorkDir.for_url(f"https://youtu.be/{vid}", tmp / "work")


def _draft(work: WorkDir, text: str) -> None:
    (work.root / "translation.draft.json").write_text(text, encoding="utf-8")


def _run(q: Path, c: Path, *extra: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = drain.main(["--queue", str(q), "--config", str(c),
                           "--timeout", "0.2", "--poll", "0.01", *extra])
    return code, buf.getvalue()


# --- the settle check ---------------------------------------------------------
def test_a_half_written_draft_is_not_ready() -> None:
    # The draft is written by a sub-agent through a shell redirect, so a poll can land mid-write.
    # Reading a torn file as ready costs a build against a truncated draft and burns the video.
    with tempfile.TemporaryDirectory() as d:
        w = _work(Path(d), VIDS[0])
        _draft(w, '[{"id": 0, "text_ru": "Прив')
        assert drain.draft_ready(w) is False


def test_an_absent_or_empty_draft_is_not_ready() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _work(Path(d), VIDS[0])
        assert drain.draft_ready(w) is False              # absent
        _draft(w, "[]")
        assert drain.draft_ready(w) is False              # present but carries nothing


def test_a_complete_draft_is_ready() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _work(Path(d), VIDS[0])
        _draft(w, json.dumps([{"id": 0, "text_ru": "Привет."}]))
        assert drain.draft_ready(w) is True


# --- already_built ------------------------------------------------------------
def test_a_translation_older_than_its_transcript_is_not_built() -> None:
    # A re-transcribe (or a repair) makes the existing translation describe a file that no longer
    # exists; draining on it would ship a dub keyed to the wrong ids.
    import os
    with tempfile.TemporaryDirectory() as d:
        w = _work(Path(d), VIDS[0])
        w.translation.write_text("[]", encoding="utf-8")
        w.sentences.write_text("[]", encoding="utf-8")
        os.utime(w.translation, (1_000_000, 1_000_000))
        os.utime(w.sentences, (2_000_000, 2_000_000))
        assert drain.already_built(w) is False
        os.utime(w.translation, (3_000_000, 3_000_000))
        assert drain.already_built(w) is True


# --- the loop -----------------------------------------------------------------
def test_a_video_with_a_draft_is_drained_and_one_without_stays_pending() -> None:
    # "Pending" is the whole point: the step-3 resume still owes that video, and nothing here
    # may decide otherwise.
    seen: list = []
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        q, c = _setup(tmp)
        _draft(_work(tmp, VIDS[0]), json.dumps([{"id": 0, "text_ru": "Привет."}]))
        real = drain.drain_one
        drain.drain_one = lambda url, work: (seen.append(work.root.name), (True, "drained"))[1]
        try:
            code, out = _run(q, c)
        finally:
            drain.drain_one = real
    assert code == 0
    assert seen == [VIDS[0]]
    assert "1 drained, 0 failed, 1 pending" in out
    assert VIDS[1] in out and "still owes it" in out


def test_a_failed_drain_is_reported_and_never_silently_dropped() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        q, c = _setup(tmp)
        for v in VIDS:
            _draft(_work(tmp, v), json.dumps([{"id": 0, "text_ru": "Привет."}]))
        real = drain.drain_one
        drain.drain_one = lambda url, work: (False, "pipeline exit 1: boom")
        try:
            code, out = _run(q, c)
        finally:
            drain.drain_one = real
    assert code == 1                                       # a failure reaches the exit code
    assert "0 drained, 2 failed" in out
    assert "boom" in out


def test_a_STOP_is_observed_and_not_consumed() -> None:
    # check_stop consumes at honor time and exactly one (stage, video) pair may observe it. This
    # scheduler reports nothing per video, so consuming here would swallow the operator's halt.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        q, c = _setup(tmp)
        _draft(_work(tmp, VIDS[0]), json.dumps([{"id": 0, "text_ru": "Привет."}]))
        (tmp / "work" / STOP_NAME).write_text("", encoding="utf-8")
        real = drain.drain_one
        drain.drain_one = lambda url, work: (True, "drained")
        try:
            code, out = _run(q, c)
        finally:
            drain.drain_one = real
        assert (tmp / "work" / STOP_NAME).exists()         # left for the pipeline to honor
    assert "STOP present" in out


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all drain tests passed")
