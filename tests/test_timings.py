"""Unit tests for overdub/timings.py — the owner of work/<id>/timings.json and work/runs.jsonl.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_timings.py   (or via pytest)
Pure, no GPU, no network, no media. Two things are actually load-bearing here and both are
regressions waiting to happen:

  - the file has THREE sections now (stages / detail / spans) and each writer read-modify-writes
    the whole document. `stages` ate `detail` once by writing back only its own key; a third
    section triples the surface for that bug, so every writer is tested against the other two.
  - `spans` is ADDITIVE to `stages`, never a replacement. A test that only checked the span would
    pass while a "simplification" quietly redefined the float that 252 files on disk are keyed to.

The clock helpers are covered for SHAPE, not for the time they return: two producers write the
same field (the pipeline from its own clock, the translate seam from file mtimes) and a series
that mixes two formats is unsortable.
"""

from __future__ import annotations

import io
import contextlib
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import cli, timings  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.pipeline import Context, run_pipeline  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402


def _work(tmp) -> WorkDir:
    root = Path(tmp)
    root.mkdir(parents=True, exist_ok=True)
    return WorkDir(root)


def _doc(work) -> dict:
    return json.loads((work.root / "timings.json").read_text(encoding="utf-8"))


class _Stage:
    """Minimal Stage protocol: name / done(ctx) / run(ctx)."""

    def __init__(self, name, *, done=False, fail=False):
        self.name, self._done, self._fail = name, done, fail

    def done(self, ctx) -> bool:
        return self._done

    def run(self, ctx) -> None:
        if self._fail:
            raise RuntimeError("boom")


def _drive(tmp, stages):
    """run_pipeline over a real workdir with output captured, returning the WorkDir."""
    cfg = Config()
    cfg.work_root = Path(tmp)
    work = _work(Path(tmp) / "vid00000001")
    ctx = Context(url="https://youtu.be/vid00000001", cfg=cfg, work=work)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        run_pipeline(ctx, stages, force=False, only=None)
    return work


# --- record_stage_timing (moved here with the writers, 2026-08-06) -------------
def test_record_stage_timing_upsert_and_rounding() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _work(d)
        timings.record_stage_timing(work, "download", 12.3456)
        timings.record_stage_timing(work, "transcribe", 45.1)
        timings.record_stage_timing(work, "download", 10.0)   # upsert overwrites ONLY download
        data = _doc(work)
        assert data["stages"]["download"] == 10.0
        assert data["stages"]["transcribe"] == 45.1           # other stage preserved


def test_record_stage_timing_rounds_to_3dp() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _work(d)
        timings.record_stage_timing(work, "synthesize", 1.234567)
        assert _doc(work)["stages"]["synthesize"] == 1.235


# --- the three sections must not eat each other -------------------------------
def test_every_writer_preserves_the_other_two_sections() -> None:
    # The bug this guards is not hypothetical: `stages` used to be written back as the WHOLE
    # document and silently destroyed `detail` once a second section existed. Written in all
    # three orders would be six permutations; one full round in each direction is enough to
    # catch a writer that replaces instead of merges.
    with tempfile.TemporaryDirectory() as d:
        work = _work(d)
        timings.record_stage_detail(work, "transcribe", work_sec=61.2)
        timings.record_stage_span(work, "transcribe", enqueued="a", started="b", finished="c")
        timings.record_stage_timing(work, "transcribe", 88.1)
        doc = _doc(work)
        assert doc["stages"]["transcribe"] == 88.1
        assert doc["detail"]["transcribe"] == {"work_sec": 61.2}
        assert doc["spans"]["transcribe"]["started"] == "b"

        # ...and the reverse order, so no writer is only ever tested as the last one
        timings.record_stage_timing(work, "mux", 3.0)
        timings.record_stage_span(work, "mux", enqueued="x", started="y", finished="z")
        timings.record_stage_detail(work, "mux", work_sec=2.0)
        doc = _doc(work)
        assert doc["stages"]["mux"] == 3.0
        assert doc["spans"]["mux"]["finished"] == "z"
        assert doc["detail"]["mux"] == {"work_sec": 2.0}
        assert doc["stages"]["transcribe"] == 88.1        # the first round survived all of it


def test_span_is_additive_and_never_replaces_the_duration() -> None:
    # spans[x] and stages[x] answer different questions and the float is what every timings.json
    # on disk is keyed to. A span must never be the only record of a stage that ran.
    with tempfile.TemporaryDirectory() as d:
        work = _work(d)
        timings.record_stage_timing(work, "verify", 5.5)
        timings.record_stage_span(work, "verify", enqueued="a", started="b", finished="c")
        doc = _doc(work)
        assert doc["stages"]["verify"] == 5.5
        assert set(doc["spans"]["verify"]) == {"enqueued", "started", "finished", "run_id"}


def test_span_upsert_keeps_other_stages() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _work(d)
        timings.record_stage_span(work, "download", enqueued="1", started="2", finished="3")
        timings.record_stage_span(work, "mux", enqueued="4", started="5", finished="6")
        timings.record_stage_span(work, "download", enqueued="7", started="8", finished="9")
        spans = _doc(work)["spans"]
        assert spans["download"]["enqueued"] == "7"
        assert spans["mux"]["enqueued"] == "4"


def test_span_carries_this_process_run_id() -> None:
    # The id is what lets a window be computed over the work THIS run did, instead of over
    # whatever timings a resumed workdir happens to hold from last week.
    with tempfile.TemporaryDirectory() as d:
        work = _work(d)
        timings.record_stage_span(work, "assemble", enqueued="a", started="b", finished="c")
        span = _doc(work)["spans"]["assemble"]
        assert span["run_id"] == timings.RUN_ID
        assert "clock" not in span


def test_a_foreign_clock_span_gets_no_run_id() -> None:
    # The translate seam's stamps are marker mtimes: they describe the Sonnet wave, not the
    # process that wrote the row. Stamping that row with the writer's id would fold the wave into
    # build_translation.py's own run — a group that never existed — so the id is withheld and the
    # ABSENCE is what tells a consumer this span belongs to no invocation.
    with tempfile.TemporaryDirectory() as d:
        work = _work(d)
        timings.record_stage_span(work, "translate", enqueued="a", started="b", finished="c",
                                  clock="translate.started/draft mtime")
        span = _doc(work)["spans"]["translate"]
        assert "run_id" not in span
        assert span["clock"] == "translate.started/draft mtime"


def test_a_torn_timings_file_costs_a_warning_not_a_stage() -> None:
    # Never-raises is the whole contract: observability must not be able to fail a run.
    with tempfile.TemporaryDirectory() as d:
        work = _work(d)
        (work.root / "timings.json").write_text("{not json", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            timings.record_stage_span(work, "mux", enqueued="a", started="b", finished="c")
        assert _doc(work)["spans"]["mux"]["started"] == "b"
        assert "unreadable" in buf.getvalue()


# --- clock helpers: SHAPE, not the value --------------------------------------
def test_both_clock_producers_write_one_parseable_utc_shape() -> None:
    # The pipeline reads its own clock; the translate seam can only read file mtimes. Two
    # formatters for one field is how a series becomes unsortable.
    for stamp in (timings.now_iso(), timings.iso_from_epoch(1_700_000_000.5)):
        assert stamp.endswith("+00:00")
        parsed = datetime.fromisoformat(stamp)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0
    assert timings.iso_from_epoch(0) == "1970-01-01T00:00:00.000+00:00"


def test_elapsed_is_none_rather_than_zero_when_a_stamp_will_not_parse() -> None:
    # 0.0 would read as an instantaneous run and be silently averaged into a throughput figure.
    assert timings._elapsed_s("1970-01-01T00:00:00.000+00:00",
                              "1970-01-01T00:00:12.500+00:00") == 12.5
    assert timings._elapsed_s("nonsense", "1970-01-01T00:00:00.000+00:00") is None
    assert timings._elapsed_s(None, None) is None


# --- runs.jsonl ---------------------------------------------------------------
def _rows(root) -> list[dict]:
    return [json.loads(ln) for ln in
            (root / "runs.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_record_run_appends_rather_than_overwriting() -> None:
    # The series IS the artifact — a writer that truncated would leave exactly one night on disk
    # and look like it was working.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for order in ("stage-major", "single"):
            timings.record_run(root, ["vid00000001"], started=timings.now_iso(),
                               finished=timings.now_iso(), order=order, config_key="k")
        rows = _rows(root)
        assert [r["order"] for r in rows] == ["stage-major", "single"]


def test_record_run_counts_only_the_durations_it_actually_found() -> None:
    # A partial audio sum must be visible as partial: audio_s over n videos would overstate the
    # audio-per-hour ratio this file exists to support, and nothing downstream could contradict it.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "vid00000001").mkdir(parents=True)
        (root / "vid00000001" / "source.info.json").write_text(
            json.dumps({"duration": 300.0}), encoding="utf-8")
        (root / "vid00000002").mkdir(parents=True)          # no info.json at all
        timings.record_run(root, ["vid00000001", "vid00000002"], started=timings.now_iso(),
                           finished=timings.now_iso(), order="stage-major", config_key="k")
        row = _rows(root)[0]
        assert row["n"] == 2
        assert row["audio_n"] == 1
        assert row["audio_s"] == 300.0
        assert row["ids"] == ["vid00000001", "vid00000002"]
        assert row["config_key"] == "k"
        assert row["run_id"] == timings.RUN_ID


def test_record_run_elapsed_comes_from_the_two_stamps() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        timings.record_run(root, [], started="2026-08-06T10:00:00.000+00:00",
                           finished="2026-08-06T10:25:37.000+00:00",
                           order="stage-major", config_key="k")
        assert _rows(root)[0]["elapsed_s"] == 1537.0


def test_record_run_never_raises_on_an_unwritable_root() -> None:
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        timings.record_run(Path("no") / "such" / "root", ["v"], started=timings.now_iso(),
                           finished=timings.now_iso(), order="single", config_key="k")
    assert "could not record the run window" in buf.getvalue()


# --- the pipeline wiring ------------------------------------------------------
def test_a_stage_that_ran_gets_both_a_duration_and_a_span() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _drive(d, [_Stage("download")])
        doc = _doc(work)
        assert "download" in doc["stages"]
        span = doc["spans"]["download"]
        assert span["enqueued"] <= span["started"] <= span["finished"]
        assert span["run_id"] == timings.RUN_ID


def test_a_skipped_stage_writes_no_span() -> None:
    # Same rule the duration already follows: a resumed run must keep the span of the run that
    # did the work, not overwrite it with a window in which nothing happened.
    with tempfile.TemporaryDirectory() as d:
        work = _drive(d, [_Stage("download", done=True)])
        assert not (work.root / "timings.json").exists()


def test_a_stage_that_raised_writes_no_span() -> None:
    # A failed stage has no meaningful window, and recording one would put a completed-looking
    # entry beside a stage that produced nothing.
    with tempfile.TemporaryDirectory() as d:
        cfg = Config()
        cfg.work_root = Path(d)
        work = _work(Path(d) / "vid00000001")
        ctx = Context(url="https://youtu.be/vid00000001", cfg=cfg, work=work)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                run_pipeline(ctx, [_Stage("mux", fail=True)], force=False, only=None)
            except RuntimeError:
                pass
        assert not (work.root / "timings.json").exists()


# --- the run window (cli wiring) ----------------------------------------------
def test_the_window_is_recorded_even_when_the_run_blows_up() -> None:
    # A halted or crashed run still consumed the wall clock it consumed. Writing only the clean
    # ones would bias every throughput figure downward while the series looked complete.
    with tempfile.TemporaryDirectory() as d:
        cfg = Config()
        cfg.work_root = Path(d)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf), contextlib.suppress(RuntimeError):
            with cli._run_window(cfg, ["vid00000001"], "single"):
                raise RuntimeError("boom")
        row = _rows(Path(d))[0]
        assert row["order"] == "single"
        assert row["ids"] == ["vid00000001"]
        assert row["elapsed_s"] is not None


def test_config_key_degrades_to_unknown_instead_of_raising() -> None:
    # Its one caller evaluates it inside a finally: raising there would replace whatever was
    # already unwinding, turning a lost timing into a lost run.
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        assert cli._config_key(object()) == "unknown"
    assert "fingerprint unavailable" in buf.getvalue()
    assert cli._config_key(Config()) != "unknown"        # and a real config still fingerprints


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all timings tests passed")
