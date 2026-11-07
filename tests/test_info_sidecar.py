"""Unit tests for the yt-dlp metadata sidecar, which lives under two names.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_info_sidecar.py   (or via pytest)
Synthetic workdirs only: no GPU, no network, no media.

yt-dlp names the sidecar after the container it actually wrote: `source.info.json` on the mkv merge
path, `source.mkv.info.json` on the single-format '/b' fallback. A reader that knows only the first
name gets nothing on a '/b' workdir, and each reader degrades silently in its own way — mux and
separate size their RAM need at 0, so the concurrent sweep admits a long video beside the others;
the transcript status line reads the length off the last sentence; run.json falls back to ffprobe;
a clean.md comes out without its title. Every reader goes through WorkDir.info(), and the tests
below pin that each one does.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import build_clean  # noqa: E402
import queue_report  # noqa: E402
from overdub import cli, queueview, runreport, timings  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.pipeline import Context  # noqa: E402
from overdub.stages import mux, separate  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

VID = "vid00000001"
B_NAME = "source.mkv.info.json"                 # the '/b' fallback's name
META = {"title": "Single Format", "channel": "Chan", "upload_date": "20240520", "duration": 630}


def _work(tmp: Path) -> WorkDir:
    work = WorkDir(tmp / VID)
    work.root.mkdir(parents=True, exist_ok=True)
    return work


def _b_workdir(tmp: Path, meta: dict = META) -> WorkDir:
    """A workdir fetched through the '/b' fallback: the sidecar exists ONLY under its mkv name."""
    work = _work(tmp)
    (work.root / B_NAME).write_text(json.dumps(meta), encoding="utf-8")
    return work


def _sentences(work: WorkDir, last_end: float) -> None:
    work.sentences.write_text(json.dumps(
        [{"id": 0, "text": "First.", "start": 0.0, "end": 1.0},
         {"id": 1, "text": "Last.", "start": last_end - 1.0, "end": last_end}]), encoding="utf-8")


# --- the accessor -------------------------------------------------------------

def test_the_single_format_name_is_read() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _b_workdir(Path(d))
        assert work.info() == META
        assert work.source_duration() == 630.0


def test_the_merge_path_name_wins_when_both_exist() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _b_workdir(Path(d))
        work.info_json.write_text(json.dumps({"title": "Merged", "duration": 100}),
                                  encoding="utf-8")
        assert work.info()["title"] == "Merged"
        assert work.source_duration() == 100.0


def test_a_torn_or_non_object_first_name_does_not_hide_the_second() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _b_workdir(Path(d))
        for junk in ("{not json", "[1, 2]", "\xff"):
            work.info_json.write_text(junk, encoding="utf-8")
            assert work.info() == META, junk
            assert work.source_duration() == 630.0, junk


def test_no_sidecar_is_none_and_an_unknown_duration() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d))
        assert work.info() is None
        assert work.source_duration() == 0.0
        work.info_json.write_text(json.dumps({"duration": True}), encoding="utf-8")
        assert work.source_duration() == 0.0                     # a bool is not a length


# --- every reader ---------------------------------------------------------------

def test_ram_needs_are_sized_on_a_single_format_workdir() -> None:
    # The confirmed failure: a 0 here lets the concurrent mux sweep admit a long video beside the
    # others without budgeting for it.
    with tempfile.TemporaryDirectory() as d:
        work = _b_workdir(Path(d))
        assert mux.ram_need(work) > 0
        assert separate.ram_need(work, Config()) > 0


def test_status_line_takes_the_length_from_the_single_format_sidecar() -> None:
    # The last sentence ends at 10:00; the video runs 10:30. The status line must say what yt-dlp
    # says, like the transcript.md header written by the same call.
    with tempfile.TemporaryDirectory() as d:
        work = _b_workdir(Path(d))
        _sentences(work, 600.0)
        ctx = Context(url=f"https://youtu.be/{VID}", cfg=Config(), work=work)
        assert "10:30" in cli._transcript_status(ctx)
        assert "10:30" in cli._finalize_transcript(ctx)
        md = work.transcript_md.read_text(encoding="utf-8")
        assert md.startswith("# Single Format\n") and "Chan · 2024-05-20" in md


def test_title_comes_from_the_single_format_sidecar_without_a_network_call() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _b_workdir(Path(d))
        ctx = Context(url=f"https://youtu.be/{VID}", cfg=Config(), work=work)
        real = cli.subprocess.run

        def no_network(*a, **kw):
            raise AssertionError("_title_of went to the network despite a sidecar on disk")

        cli.subprocess.run = no_network
        try:
            assert cli._title_of(ctx) == "Single Format"
        finally:
            cli.subprocess.run = real


def test_run_report_takes_title_and_length_from_the_single_format_sidecar() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _b_workdir(Path(d))
        work.translation.write_text("[]", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            run = runreport.build_run_report(work, Config())
        assert run["title"] == "Single Format", run
        assert run["timings"]["video_sec_source"] == "info_json", run["timings"]


def test_the_run_window_counts_a_single_format_video() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _b_workdir(root)
        timings.record_run(root, [VID], started=timings.now_iso(), finished=timings.now_iso(),
                           order="single", config_key="k")
        row = json.loads((root / "runs.jsonl").read_text(encoding="utf-8").splitlines()[0])
        assert (row["audio_n"], row["audio_s"]) == (1, 630.0), row


def test_clean_doc_takes_its_header_from_the_single_format_sidecar() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _b_workdir(Path(d))
        _sentences(work, 2.0)
        work.clean_dir.mkdir(parents=True, exist_ok=True)
        (work.clean_dir / "0-1.json").write_text(json.dumps(
            [{"id": 0, "text": "First."}, {"id": 1, "text": "Last."}]), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = build_clean.main([str(work.root), "--lang", "en"])
        assert code == 0
        doc = json.loads(work.clean_doc.read_text(encoding="utf-8"))
        assert (doc["title"], doc["channel"], doc["upload_date"]) == (
            "Single Format", "Chan", "20240520"), doc


def test_queue_reports_take_title_and_length_from_the_single_format_sidecar() -> None:
    # A transcribed-only row has no run.json: its length and title come from the sidecar alone.
    with tempfile.TemporaryDirectory() as d:
        work = _b_workdir(Path(d))
        _sentences(work, 600.0)
        entries, _ = queueview.collect_entries(None, [work.root], Path(d))
        assert entries[0]["kind"] == "transcribed", entries[0]
        assert entries[0]["duration_sec"] == 630, entries[0]
        assert queue_report._views(entries)[0]["title"] == "Single Format"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all info-sidecar tests passed")
