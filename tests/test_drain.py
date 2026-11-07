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


def _sentences(work: WorkDir, n: int) -> None:
    work.sentences.write_text(
        json.dumps([{"id": i, "text": "Hi.", "start": i, "end": i + 1} for i in range(n)]),
        encoding="utf-8")


def _full_draft(work: WorkDir, n: int) -> None:
    """A draft covering every id — what readiness actually requires."""
    _sentences(work, n)
    _draft(work, json.dumps([{"id": i, "text_ru": "Привет."} for i in range(n)]))


class _FakeMuxes(drain.MuxPool):
    """MuxPool without children: a started mux exits on the next reap with `result`."""
    started: list = []
    result = (True, "drained")

    def start(self, url: str, need: int) -> None:
        _FakeMuxes.started.append((url, len(self.running)))
        self.running[url] = (None, None, need)

    def reap(self, block: bool = False):
        out = [(u, *_FakeMuxes.result) for u in self.running]
        self.running.clear()
        return out


class _HeldMuxes(drain.MuxPool):
    """MuxPool without children whose muxes run until the drain WAITS for one (a blocking reap).
    `on_wait` fires at that moment — where an operator's STOP lands while the drain waits."""
    started: list = []
    on_wait = None

    def start(self, url: str, need: int) -> None:
        _HeldMuxes.started.append(url)
        self.running[url] = (None, None, need)

    def reap(self, block: bool = False):
        if not block:
            return []
        if _HeldMuxes.on_wait is not None:
            _HeldMuxes.on_wait()
        out = [(u, True, "drained") for u in self.running]
        self.running.clear()
        return out


def _run(q: Path, c: Path, *extra: str, pool=_FakeMuxes) -> tuple[int, str]:
    buf = io.StringIO()
    real = drain.MuxPool
    drain.MuxPool = pool
    pool.started = []
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            code = drain.main(["--queue", str(q), "--config", str(c),
                               "--timeout", "0.2", "--poll", "0.01", *extra])
    finally:
        drain.MuxPool = real
    return code, buf.getvalue()


# --- readiness is COVERAGE, not parseability ----------------------------------
def test_a_VALID_but_PARTIAL_draft_is_not_ready() -> None:
    # The regression this exists for, measured 2026-08-07: a sub-agent builds the draft in
    # batches and rewrites the whole file each time, so every intermediate state is well-formed
    # JSON holding a prefix. A parse-only check waved two of ten videos through, the build then
    # exited on the missing ids, and both were reported failed while their agents still worked.
    with tempfile.TemporaryDirectory() as d:
        w = _work(Path(d), VIDS[0])
        _sentences(w, 165)
        _draft(w, json.dumps([{"id": i, "text_ru": "Привет."} for i in range(100)]))
        assert drain.draft_ready(w) is False
        _full_draft(w, 165)
        assert drain.draft_ready(w) is True


def test_a_half_written_draft_is_not_ready() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _work(Path(d), VIDS[0])
        _sentences(w, 3)
        _draft(w, '[{"id": 0, "text_ru": "Прив')
        assert drain.draft_ready(w) is False


def test_an_absent_or_empty_draft_is_not_ready() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _work(Path(d), VIDS[0])
        _sentences(w, 3)
        assert drain.draft_ready(w) is False              # absent
        _draft(w, "[]")
        assert drain.draft_ready(w) is False              # present but carries nothing


def test_a_draft_without_a_transcript_to_check_against_is_not_ready() -> None:
    # Nothing to compare coverage to is UNKNOWN, never "complete" — the same missing-vs-empty
    # discipline the rest of the repo keeps.
    with tempfile.TemporaryDirectory() as d:
        w = _work(Path(d), VIDS[0])
        _draft(w, json.dumps([{"id": 0, "text_ru": "Привет."}]))
        assert drain.draft_ready(w) is False


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
        _full_draft(_work(tmp, VIDS[0]), 3)
        real = drain.drain_one
        drain.drain_one = lambda url, work, stages: (seen.append(work.root.name), (True, "tail"))[1]
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
            _full_draft(_work(tmp, v), 3)
        real = drain.drain_one
        drain.drain_one = lambda url, work, stages: (False, "pipeline exit 1: boom")
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
        drain.drain_one = lambda url, work, stages: (True, "tail")
        try:
            code, out = _run(q, c)
        finally:
            drain.drain_one = real
        assert (tmp / "work" / STOP_NAME).exists()         # left for the pipeline to honor
    assert "STOP present" in out


def _stop_during_a_wait(*, mux_width: int, ram) -> tuple[list, int, str, bool]:
    """Two ready videos; the operator writes STOP while the drain waits on the first video's mux.
    Returns (videos whose tail ran, exit code, output, STOP still on disk)."""
    from overdub import host
    seen: list = []
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        q, c = _setup(tmp)
        with c.open("a", encoding="utf-8") as f:
            f.write(f"mux_concurrency = {mux_width}\n")
        for v in VIDS:
            _full_draft(_work(tmp, v), 3)
        stop = tmp / "work" / STOP_NAME
        real_one, real_ram = drain.drain_one, host.available_ram
        drain.drain_one = lambda url, work, stages: (seen.append(work.root.name), (True, "tail"))[1]
        host.available_ram = ram
        _HeldMuxes.on_wait = lambda: stop.write_text("", encoding="utf-8")
        try:
            code, out = _run(q, c, pool=_HeldMuxes)
        finally:
            drain.drain_one, host.available_ram = real_one, real_ram
            _HeldMuxes.on_wait = None
        return seen, code, out, stop.exists()


def test_a_STOP_made_while_waiting_for_RAM_starts_no_tail() -> None:
    # Unreadable RAM: the second tail waits for the first mux. A STOP written during that wait used
    # to be checked only at the top of the loop, so the next tail child started, removed the file
    # as stale at its own startup, and the rest of the queue drained as if nobody had asked.
    seen, code, out, kept = _stop_during_a_wait(mux_width=4, ram=lambda: None)
    assert seen == [VIDS[0]]
    assert kept
    assert _HeldMuxes.started == [URLS[0]]
    assert "1 drained, 0 failed, 1 pending" in out and "before the STOP" in out
    assert code == 0


def test_a_STOP_made_while_waiting_for_a_mux_slot_starts_no_mux() -> None:
    # One mux slot: the second video's tail runs beside the first mux, then waits for the slot.
    # The mux child would remove a STOP written during that wait just the same.
    seen, code, out, kept = _stop_during_a_wait(mux_width=1, ram=lambda: 2**40)
    assert seen == VIDS
    assert kept
    assert _HeldMuxes.started == [URLS[0]]                 # the second mux never started
    assert "1 drained, 0 failed, 1 pending" in out
    assert code == 0


def test_a_tail_halted_by_STOP_stops_the_drain_and_is_not_a_failure() -> None:
    # The tail child honors a STOP at a stage boundary, consumes it and exits 3. Read as a plain
    # failure, the drain went on to the next video with the file already gone.
    seen: list = []
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        q, c = _setup(tmp)
        for v in VIDS:
            _full_draft(_work(tmp, v), 3)
        real = drain.drain_one
        drain.drain_one = lambda url, work, stages: (seen.append(work.root.name),
                                                     (None, "tail halted by STOP"))[1]
        try:
            code, out = _run(q, c)
        finally:
            drain.drain_one = real
    assert seen == [VIDS[0]]
    assert "0 drained, 0 failed, 2 pending" in out and "honored the STOP" in out
    assert code == 0


def test_drain_one_reads_exit_3_as_a_STOP_and_checks_STOP_before_the_tail() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        w = _work(tmp, VIDS[0])
        calls: list = []
        real = drain._run
        try:
            drain._run = lambda argv: (calls.append(argv), (0 if len(calls) == 1 else 3, "[stop] x"))[1]
            ok, detail = drain.drain_one(URLS[0], w, ["synthesize"])
            assert ok is None and "STOP" in detail and len(calls) == 2
            # a STOP written during the build: the tail child would delete it, so it never starts
            calls.clear()
            (tmp / "work" / STOP_NAME).write_text("", encoding="utf-8")
            ok, detail = drain.drain_one(URLS[0], w, ["synthesize"])
            assert ok is None and len(calls) == 1
            assert (tmp / "work" / STOP_NAME).exists()
        finally:
            drain._run = real


def test_a_mux_child_halted_by_STOP_is_neither_drained_nor_failed() -> None:
    class _Proc:
        returncode = 3

        def poll(self):
            return 3

    pool = drain.MuxPool(width=2, admits=_admits(10))
    log = tempfile.TemporaryFile(mode="w+", encoding="utf-8")
    log.write("[stop] STOP file honored\n")
    pool.running["u"] = (_Proc(), log, 0)
    assert pool.reap() == [("u", None, "mux exit 3: [stop] STOP file honored")]


# --- mux in the background ----------------------------------------------------
def test_the_tail_stops_before_mux_and_mux_runs_in_the_background() -> None:
    # mux needs no GPU, so it is split off the serial tail; the tail must still run every OTHER
    # stage, or a video would reach mux without its dub
    got: list = []
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        q, c = _setup(tmp)
        for v in VIDS:
            _full_draft(_work(tmp, v), 3)
        real = drain.drain_one
        drain.drain_one = lambda url, work, stages: (got.append(list(stages)), (True, "tail"))[1]
        try:
            code, out = _run(q, c)
        finally:
            drain.drain_one = real
    assert code == 0
    assert "mux" not in got[0] and {"synthesize", "assemble", "separate"} <= set(got[0])
    assert [u for u, _n in _FakeMuxes.started] == URLS
    assert "2 drained, 0 failed, 0 pending" in out


def test_a_failed_background_mux_is_a_failed_video() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        q, c = _setup(tmp)
        _full_draft(_work(tmp, VIDS[0]), 3)
        real = drain.drain_one
        drain.drain_one = lambda url, work, stages: (True, "tail")
        _FakeMuxes.result = (False, "mux exit 1: encoder died")
        try:
            code, out = _run(q, c)
        finally:
            drain.drain_one = real
            _FakeMuxes.result = (True, "drained")
    assert code == 1
    assert "encoder died" in out and "0 drained, 1 failed, 1 pending" in out


def _admits(free):
    """host.ram_admission's rule over a host reporting `free` bytes beyond the headroom (None:
    unreadable)."""
    from overdub import host
    real = host.available_ram
    host.available_ram = lambda: None if free is None else host._RAM_HEADROOM + free
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return host.ram_admission()
    finally:
        host.available_ram = real


def test_the_mux_pool_admits_by_ram_and_always_one() -> None:
    pool = drain.MuxPool(width=4, admits=_admits(10))
    assert pool.fits(50)                                   # nothing running: always admitted
    pool.running["a"] = (None, None, 6)
    assert pool.fits(4) and not pool.fits(5)               # 6 + 5 > 10
    # the next video's tail is checked the same way, but is never refused by the width cap
    pool.running["b"] = (None, None, 0)
    pool.width = 2
    assert pool.fits_beside(4) and not pool.fits_beside(5) and not pool.fits(0)
    pool = drain.MuxPool(width=1, admits=_admits(10))
    pool.running["a"] = (None, None, 0)
    assert not pool.fits(0)                                # the width cap holds under a budget


def test_unreadable_ram_runs_the_drain_serially() -> None:
    # The host contract is "a host we cannot read runs as before", and before the background pool
    # the drain muxed inline: no second mux, and no tail beside a running one.
    pool = drain.MuxPool(width=4, admits=_admits(None))
    assert pool.fits(10**12)                               # nothing running: still admitted
    pool.running["a"] = (None, None, 0)
    assert not pool.fits(0) and not pool.fits_beside(0)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all drain tests passed")
