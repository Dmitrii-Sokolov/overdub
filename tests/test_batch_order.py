"""Unit tests for the batch traversal orders — stage-major (default) and --video-major.

Run: .venv-asr/Scripts/python.exe tests/test_batch_order.py   (or via pytest)
Filesystem only — no GPU, no engine, no worker, no network. The stages are fakes injected
into the driver, so what is under test is the RUNNER: traversal order, the cross-stage
status machine, STOP's consume-on-honor semantics, the finish sweep, session lifetime and
the engine cache key — never a real stage.

Guards the hazards the stage-major restructure introduces (DECISIONS 2026-07-19): a failure
at one stage must drop exactly one video and not cascade; a consumed STOP must halt the
WHOLE batch (continuing would leave the stop un-honored for the other 11 videos); the
finish sweep must roll up failed videos too, or the batch sweep serves yesterday's run.json
as if it were tonight's.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import cli, runreport  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.pipeline import STOP_NAME, StopRequested, check_stop  # noqa: E402

VIDS = [f"vid0000000{i}" for i in (1, 2, 3)]     # exactly 11 chars, or video_id() falls
URLS = [f"https://youtu.be/{v}" for v in VIDS]   # through to its url-hash branch


class FakeStage:
    """Full Stage protocol: name / done(ctx) / run(ctx). Appends (stage, video) to a shared
    trace — the traversal order IS the thing under test, so it is observable, not inferred.
    `stop_after` drops a STOP file after that video's run, the only way to land a stop on a
    chosen (stage, video) pair without racing a real operator."""

    def __init__(self, name, trace, *, fail_on=(), done_on=(), stop_after=(), probe=None):
        self.name, self._trace = name, trace
        self._fail, self._done, self._stop = set(fail_on), set(done_on), set(stop_after)
        self._probe = probe

    def done(self, ctx) -> bool:
        self._trace.append(("done?", self.name, ctx.work.root.name))
        return ctx.work.root.name in self._done

    def run(self, ctx) -> None:
        self._trace.append((self.name, ctx.work.root.name))
        if self._probe is not None:                    # session lifetime observation point
            ctx.session.get(("probe", self.name), self._probe)
        if ctx.work.root.name in self._stop:
            (ctx.cfg.work_root / STOP_NAME).write_text("", encoding="utf-8")
        if ctx.work.root.name in self._fail:
            raise RuntimeError(f"boom in {self.name}")


class _Closable:
    """Session entry that records its own release — session.clear() must call close()."""

    def __init__(self, closed: list) -> None:
        self._closed = closed

    def close(self) -> None:
        self._closed.append(True)


def _cfg(tmp: Path) -> Config:
    cfg = Config()
    cfg.work_root = tmp / "work"
    cfg.output_dir = tmp / "out"
    cfg.work_root.mkdir(parents=True, exist_ok=True)
    return cfg


def _runs(trace) -> list:
    """Only the run() entries — done() probes are asserted separately."""
    return [t for t in trace if len(t) == 2]


def _drive(tmp, stages, *, urls=None, force=False, only=None, finalize=None):
    """Run the stage-major driver with stdout/stderr captured (the fakes raise on purpose,
    so a real traceback would otherwise spray the test log). Returns (exit_code, output)."""
    cfg = _cfg(tmp)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = cli._run_batch_stage_major(
            urls if urls is not None else URLS, cfg, force=force, only=only,
            stages=stages, finalize=finalize if finalize is not None else (lambda ctx: "out.mkv"))
    return code, buf.getvalue()


# --- traversal order ---------------------------------------------------------------

def test_stage_major_is_stage_outer_video_inner() -> None:
    trace: list = []
    stages = [FakeStage(n, trace) for n in ("s1", "s2", "s3")]
    with tempfile.TemporaryDirectory() as d:
        code, _ = _drive(Path(d), stages)
    assert code == 0
    assert _runs(trace) == [(s, v) for s in ("s1", "s2", "s3") for v in VIDS]


def test_video_major_flag_restores_old_order() -> None:
    trace: list = []
    stages = [FakeStage(n, trace) for n in ("s1", "s2", "s3")]
    real_all, real_export = cli.all_stages, cli._export_output
    cli.all_stages = lambda cfg: stages          # _run_one builds the stage list itself, so
    cli._export_output = lambda ctx: "out.mkv"   # the seam here is the module global
    try:
        with tempfile.TemporaryDirectory() as d:
            cfg = _cfg(Path(d))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                code = cli._run_batch_video_major(URLS, cfg, force=False, only=None)
    finally:
        cli.all_stages, cli._export_output = real_all, real_export
    assert code == 0
    assert _runs(trace) == [(s, v) for v in VIDS for s in ("s1", "s2", "s3")]


def test_single_video_run_is_unchanged() -> None:
    """No --batch: one video through every stage, i.e. what stage-major degenerates to."""
    trace: list = []
    stages = [FakeStage(n, trace) for n in ("s1", "s2", "s3")]
    real_all, real_export = cli.all_stages, cli._export_output
    cli.all_stages = lambda cfg: stages
    cli._export_output = lambda ctx: "out.mkv"
    try:
        with tempfile.TemporaryDirectory() as d:
            cfg = _cfg(Path(d))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                name = cli._run_one(URLS[0], cfg, force=False, only=None)
    finally:
        cli.all_stages, cli._export_output = real_all, real_export
    assert name == "out.mkv"
    assert _runs(trace) == [("s1", VIDS[0]), ("s2", VIDS[0]), ("s3", VIDS[0])]


# --- cross-stage status machine ----------------------------------------------------

def test_failure_excludes_only_that_video() -> None:
    trace: list = []
    stages = [FakeStage("s1", trace), FakeStage("s2", trace, fail_on={VIDS[1]}),
              FakeStage("s3", trace)]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive(Path(d), stages)
    assert code == 1
    # v2 entered s2 (and raised there); it must never appear in s3, and v1/v3 are untouched
    assert ("s3", VIDS[1]) not in trace
    assert ("s3", VIDS[0]) in trace and ("s3", VIDS[2]) in trace
    assert f"[FAIL] {VIDS[1]}" in out


def test_first_failure_wins_and_survives_to_summary() -> None:
    trace: list = []
    stages = [FakeStage("s1", trace, fail_on={VIDS[1]}),
              FakeStage("s2", trace, fail_on={VIDS[1]}), FakeStage("s3", trace)]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive(Path(d), stages)
    assert code == 1
    line = next(ln for ln in out.splitlines() if ln.startswith(f"[FAIL] {VIDS[1]}"))
    assert "s1: RuntimeError: boom in s1" in line   # the FIRST error, not a cascade
    assert "s2" not in line


def test_all_videos_failing_does_not_abort_the_batch() -> None:
    trace: list = []
    stages = [FakeStage("s1", trace, fail_on=set(VIDS)), FakeStage("s2", trace)]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive(Path(d), stages)
    assert code == 1
    assert _runs(trace) == [("s1", v) for v in VIDS]      # nobody reaches s2
    assert "0 ok, 3 failed" in out                        # the summary still prints


def test_only_filters_stages_not_videos() -> None:
    trace: list = []
    stages = [FakeStage(n, trace) for n in ("s1", "s2", "s3")]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive(Path(d), stages, only={"s2"})
    assert code == 0
    assert _runs(trace) == [("s2", v) for v in VIDS]
    for v in VIDS:                                       # every video still reported
        assert f"[ok  ] {v}" in out


def test_force_bypasses_done_for_every_pair() -> None:
    trace: list = []
    stages = [FakeStage(n, trace, done_on=set(VIDS)) for n in ("s1", "s2")]
    with tempfile.TemporaryDirectory() as d:
        code, _ = _drive(Path(d), stages, force=True)
    assert code == 0
    assert _runs(trace) == [(s, v) for s in ("s1", "s2") for v in VIDS]
    assert not [t for t in trace if len(t) == 3]         # done() never consulted under --force


# --- STOP --------------------------------------------------------------------------

def test_stop_halts_both_loops_and_is_consumed() -> None:
    trace: list = []
    stages = [FakeStage("s1", trace), FakeStage("s2", trace, stop_after={VIDS[0]}),
              FakeStage("s3", trace)]
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        code, out = _drive(tmp, stages)
        stop_left = (tmp / "work" / STOP_NAME).exists()
    assert code == 3
    assert ("s2", VIDS[0]) in trace                      # the writer itself completed
    assert ("s2", VIDS[1]) not in trace and ("s2", VIDS[2]) not in trace
    assert not [t for t in _runs(trace) if t[0] == "s3"]  # the OUTER loop broke too
    assert not stop_left                                 # consume-on-honor
    # the two untouched videos are through s1 and no further — the summary says how far each
    # one actually got, because that is what tells the operator what a resume still owes
    assert "stopped after 's1'" in out


def test_stop_on_the_last_stage_still_exports_the_finished_videos() -> None:
    """A stop cannot un-finish a video that is already through every stage.

    The naive "mark every still-running job as stopped" loses them: they are through mux, their
    output.mkv is on disk, and gating export on status=="run" would report six ready videos as
    "not reached" and ship none of them. False diagnosis, not cosmetics.
    """
    trace: list = []
    exported: list[str] = []
    # stop_after drops the file AFTER that video's run, so it is observed at the NEXT pair:
    # written after VIDS[0] finishes the last stage, honored on VIDS[1]. That leaves VIDS[0]
    # through every stage at the moment of the stop — the case that used to be lost.
    stages = [FakeStage("s1", trace), FakeStage("s2", trace, stop_after={VIDS[0]})]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive(Path(d), stages,
                           finalize=lambda ctx: exported.append(ctx.work.root.name) or "out.mkv")
    assert code == 3                                     # the run still halted
    assert exported == [VIDS[0]]                         # ...and still shipped what was ready
    assert "stopped after 's1'" in out                   # VIDS[2] never entered the last stage


def test_stale_stop_does_not_noop_the_run() -> None:
    """check_stop consumes the file at honor time, so a second checkpoint passes cleanly —
    the property cli.main's startup sweep relies on."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / STOP_NAME).write_text("", encoding="utf-8")
        try:
            check_stop(root, "first")
            raise AssertionError("first check_stop must raise")
        except StopRequested:
            pass
        check_stop(root, "second")                       # must NOT raise


# --- finish sweep -------------------------------------------------------------------

def test_finish_sweep_rolls_up_every_job_including_failed() -> None:
    """The regression this guards: a failed video that skips build_run_report leaves its
    PREVIOUS run.json on disk, and the batch sweep counts it as if it ran tonight."""
    seen: list = []
    real = runreport.build_run_report
    runreport.build_run_report = lambda work, cfg: seen.append(work.root.name)
    try:
        trace: list = []
        stages = [FakeStage("s1", trace, fail_on={VIDS[1]})]
        with tempfile.TemporaryDirectory() as d:
            _drive(Path(d), stages)
    finally:
        runreport.build_run_report = real
    assert seen == VIDS                                  # failed video included, in order


def test_export_runs_only_for_surviving_jobs() -> None:
    exported: list = []
    trace: list = []
    stages = [FakeStage("s1", trace, fail_on={VIDS[1]})]
    with tempfile.TemporaryDirectory() as d:
        code, _ = _drive(Path(d), stages,
                         finalize=lambda ctx: exported.append(ctx.work.root.name) or "out.mkv")
    assert code == 1
    assert exported == [VIDS[0], VIDS[2]]


# --- session lifetime + cache key ---------------------------------------------------

def test_session_is_cleared_between_stages() -> None:
    closed: list = []
    trace: list = []
    stages = [FakeStage(n, trace, probe=lambda: _Closable(closed)) for n in ("s1", "s2")]
    with tempfile.TemporaryDirectory() as d:
        _drive(Path(d), stages)
    # one object per stage SWEEP (get-or-create dedupes the three videos), released at the
    # end of that sweep — the invariant that keeps peak VRAM the MAX over models, not the sum
    assert len(closed) == len(stages)


def test_tts_cache_key_covers_synth_key_and_f5_python() -> None:
    from overdub import pipeline, tts

    silero = Config()
    silero.tts_engine = "silero"
    assert pipeline._tts_key(silero) == ("tts", tts.synth_key(silero))

    real = tts.synth_key                                 # the f5 branch needs assets on disk;
    tts.synth_key = lambda cfg: "SAME"                   # stub it out to isolate f5_python
    try:
        a, b = Config(), Config()
        a.tts_engine = b.tts_engine = "f5"
        b.f5_python = Path("/other/venv/python.exe")
        assert pipeline._tts_key(a) != pipeline._tts_key(b)   # synth_key does NOT cover it
    finally:
        tts.synth_key = real


def test_crash_budget_resets_per_video() -> None:
    """A reused engine must not hand the next video an inherited crash budget — but _rid is
    the live protocol id and must stay monotone."""
    from overdub.tts.f5 import F5Engine

    eng = F5Engine.__new__(F5Engine)                     # no worker spawn, no assets
    eng._crashes, eng._rid = 2, 7
    eng.begin_video()
    assert eng._crashes == 0
    assert eng._rid == 7


def test_synthesize_calls_begin_video_on_the_engine_it_got() -> None:
    """The test above proves begin_video() WORKS; this one proves synthesize CALLS it.

    Without this, deleting the call site leaves every test green while a reused engine hands
    the next video an inherited crash budget — the exact hazard the session introduced, and one
    that only shows up on a real batch whose previous video ended on 2 consecutive synth_errors.
    """
    import json
    import numpy as np
    import soundfile as sf
    from overdub.pipeline import Context
    from overdub.stages.synthesize import SynthesizeStage
    from overdub.workdir import WorkDir

    calls: list[str] = []

    class FakeEngine:
        sample_rate = 48000
        supports_seed = False                            # keeps whisper out of this test
        supports_target = False

        def begin_video(self) -> None:
            calls.append("begin_video")

        def synthesize(self, text, out_path, *, seed=None, **kw):
            sf.write(str(out_path), np.zeros(4800, dtype="float32"), self.sample_rate,
                     format="WAV", subtype="PCM_16")
            return 1.0

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / "segments").mkdir(parents=True)
        cfg = Config()
        cfg.tts_engine = "silero"                        # synth_key without F5 assets on disk
        cfg.tts_sample_rate = FakeEngine.sample_rate
        work = WorkDir(root=tmp)
        work.translation.write_text(json.dumps(
            [{"id": 0, "start": 0.0, "end": 1.5, "src_en": "en", "text_ru": "привет",
              "text_tts": "привет", "status": "ok", "attempts": 1}],
            ensure_ascii=False), encoding="utf-8")
        ctx = Context(url="u", cfg=cfg, work=work)
        ctx.session.tts_engine = lambda _cfg: FakeEngine()   # the call site under test
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            SynthesizeStage().run(ctx)

    assert calls == ["begin_video"], f"synthesize did not call begin_video (got {calls})"


# --- summary ------------------------------------------------------------------------

def test_summary_counts_and_exit_codes() -> None:
    trace: list = []
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive(Path(d), [FakeStage("s1", trace)])
    assert code == 0 and "3 ok, 0 failed, 0 unfinished" in out

    trace = []
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive(Path(d), [FakeStage("s1", trace, fail_on={VIDS[1]})])
    assert code == 1 and "2 ok, 1 failed, 0 unfinished" in out

    trace = []
    stages = [FakeStage("s1", trace, stop_after={VIDS[0]}), FakeStage("s2", trace)]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive(Path(d), stages)
    assert code == 3 and "0 ok, 0 failed, 3 unfinished" in out


def _seed_run_jsons(cfg) -> None:
    """A run.json per video — without one the batch-sweep block prints nothing at all."""
    for v in VIDS:
        (cfg.work_root / v).mkdir(parents=True, exist_ok=True)
        (cfg.work_root / v / "run.json").write_text(
            json.dumps({"video_id": v, "timings": {"total_wall_s": 1.0, "video_sec": 2.0}}),
            encoding="utf-8")


def test_summary_stamps_the_order_it_ran() -> None:
    """Two batches in one work_root are only comparable WITHIN an order: under stage-major a
    model's load time lands on whichever video went first in that stage, so the per-video RTF
    in the sweep means something different. Unstamped, the two read as comparable."""
    trace: list = []
    stages = [FakeStage("s1", trace)]
    real_all, real_export = cli.all_stages, cli._export_output
    real_build = runreport.build_run_report
    cli.all_stages = lambda cfg: stages
    cli._export_output = lambda ctx: "out.mkv"
    # stubbed: the real rollup DELETES run.json when a workdir has neither report.json nor
    # translation.json (its "reset workdir must not serve a stale rollup" branch), which would
    # eat the seeds below. The stamp, not the rollup, is what this test is about.
    runreport.build_run_report = lambda work, cfg: None
    try:
        with tempfile.TemporaryDirectory() as d:
            cfg = _cfg(Path(d))
            _seed_run_jsons(cfg)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                cli._run_batch_stage_major(URLS, cfg, force=False, only=None, stages=stages,
                                           finalize=lambda ctx: "out.mkv")
            assert "batch sweep (stage-major)" in buf.getvalue()

        with tempfile.TemporaryDirectory() as d:
            cfg = _cfg(Path(d))
            _seed_run_jsons(cfg)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                cli._run_batch_video_major(URLS, cfg, force=False, only=None)
            assert "batch sweep (video-major)" in buf.getvalue()
    finally:
        cli.all_stages, cli._export_output = real_all, real_export
        runreport.build_run_report = real_build


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all batch-order tests passed")
