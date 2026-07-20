"""Unit tests for scout mode — `--scout` = download (AUDIO ONLY) → transcribe → stop.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_scout.py   (pytest is not installed in
any of the three venvs; every test file in this repo is a self-driving script.)

Filesystem only — no GPU, no network, no ffmpeg, no yt-dlp, no media. subprocess.run is
monkeypatched inside overdub.stages.download and writes plausible files, so what is under test
is the CONTRACT (which argv, which artifacts, which gate) and never a real fetch.

The failure classes guarded here, in the order they would actually bite:

  SILENT FULL DOWNLOAD — `-f bestaudio` must carry no '/best' tail. The fallback pulls a
    progressive VIDEO stream at ~20x the bytes, i.e. scout doing the exact thing it exists to
    prevent, on the one machine whose D: has 81 GB free.
  DESYNCHRONIZED MODE — a truncated stage list with a FULL download (100 GB for a triage pass)
    or a full list with an audio-only download (mux fails eight hours in). scout_stages
    constructs both facts in one expression; tests 6-8 pin that they stay one fact.
  TORN source.wav — both done() gates are bare existence checks, so an interrupted extraction
    leaves a truncated wav that every later resume accepts as complete. Scout is the first
    gate in the pipeline with no sibling artifact to contradict it.
  A NO-OP FLAG — --scout beside --only or --repair-asr would silently do nothing at 2am.
  A LOST TRANSCRIPT ON PROMOTION — the re-download rewrites source.wav; nothing downstream may
    notice, and sentences.json must survive untouched or the scout pass paid for nothing.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import cli  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.pipeline import Context, run_pipeline  # noqa: E402
from overdub.stages import all_stages, scout_stages  # noqa: E402
from overdub.stages.download import DownloadStage  # noqa: E402
from overdub.stages.transcribe import TranscribeStage  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

VIDS = [f"vid0000000{i}" for i in (1, 2, 3)]     # exactly 11 chars, or video_id() falls
URLS = [f"https://youtu.be/{v}" for v in VIDS]   # through to its url-hash branch
URL = URLS[0]


def _quiet(fn, *a, **kw):
    """The modes print their whole report; a test log does not need it."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


def _exits(fn, *a, **kw) -> bool:
    try:
        _quiet(fn, *a, **kw)
    except SystemExit:
        return True
    return False


def _usage_error(fn, *a, **kw) -> str:
    """argv that must die at the argparse gate. Returns the captured stderr.

    Deliberately NOT _exits: every guarded path in main() ends in sys.exit(), so "it raised
    SystemExit" is true whether or not the guard exists. Drop (args.scout, "--scout") from the
    repair-exclusion tuple and control reaches sys.exit(_run_repair(...)) — which, on a workdir
    with no sentences.json and ids=None, calls the missing transcript a legitimate '[skip]' and
    returns 0. _exits() reports True either way: a green test for a deleted feature, i.e. the
    exact silent no-op this file's docstring forbids. argparse exits 2 and _run_repair only ever
    returns 0/1/3, so the CODE separates them; the message is asserted too, so the test pins
    WHICH guard fired rather than merely "some usage error".
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fn(*a, **kw)
        except SystemExit as e:
            code = e.code
        else:
            raise AssertionError("expected a usage error, but the call returned normally")
    assert code == 2, f"expected argparse's exit code 2, got {code!r} — the guard did not fire"
    return buf.getvalue()


def _cfg(tmp: Path) -> Config:
    cfg = Config()
    cfg.work_root = tmp / "work"
    cfg.output_dir = tmp / "out"
    cfg.work_root.mkdir(parents=True, exist_ok=True)
    return cfg


def _cfg_file(tmp: Path) -> Path:
    """A real TOML pointing work_root/output_dir INTO tmp.

    Load-bearing: Config() defaults work_root to ./work, and any test that reaches _run_one
    goes through WorkDir.for_url → mkdir(parents=True). Without this every such test would
    quietly pollute the repo's real work/ directory.
    """
    p = tmp / "overdub.toml"
    root = str(tmp / "work").replace("\\", "/")
    out = str(tmp / "out").replace("\\", "/")
    p.write_text(f'work_root = "{root}"\noutput_dir = "{out}"\n', encoding="utf-8")
    return p


def _ctx(tmp: Path, *, url: str = URL) -> Context:
    cfg = _cfg(tmp)
    return Context(url=url, cfg=cfg, work=WorkDir.for_url(url, cfg.work_root))


def _sentences(work: WorkDir, n: int = 3) -> None:
    work.sentences.write_text(json.dumps(
        [{"id": i, "text": f"s{i}", "start": float(i), "end": float(i) + 1.0} for i in range(n)],
        ensure_ascii=False), encoding="utf-8")


class _Recorder:
    """Stands in for a batch driver: records the kwargs main() dispatched with, returns 0."""

    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, urls, cfg, **kw):
        self.calls.append((list(urls), kw))
        return 0


class FakeStage:
    """Full Stage protocol, appending (stage, video) to a shared trace. done() probes are
    recorded as 3-tuples so "never even PROBED" is assertable, not merely "never ran"."""

    def __init__(self, name, trace):
        self.name, self._trace = name, trace

    def done(self, ctx) -> bool:
        self._trace.append(("done?", self.name, ctx.work.root.name))
        return False

    def run(self, ctx) -> None:
        self._trace.append((self.name, ctx.work.root.name))


def _runs(trace) -> list:
    return [t for t in trace if len(t) == 2]


# --- CLI contract -------------------------------------------------------------------

def test_scout_with_only_is_a_usage_error() -> None:
    # Not merely "it exited": the guard must fire BEFORE any side effect, so the work_root the
    # config names must not exist afterwards. --only cannot express an audio-only download, so
    # honouring the composition would deliver the mode's opposite.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfgp = tmp / "overdub.toml"
        root = str(tmp / "work").replace("\\", "/")
        cfgp.write_text(f'work_root = "{root}"\n', encoding="utf-8")
        assert _exits(cli.main, [URL, "--scout", "--only", "transcribe", "--config", str(cfgp)])
        assert not (tmp / "work").exists()


def test_scout_with_repair_asr_is_a_usage_error() -> None:
    # Repair runs no stages, so --scout beside it is a flag that silently does nothing.
    # Both orderings, because argparse order must not decide whether a no-op is caught.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cfgp = _cfg_file(tmp)
        for argv in ([URL, "--scout", "--repair-asr", "auto"],
                     [URL, "--repair-asr", "auto", "--scout"]):
            err = _usage_error(cli.main, argv + ["--config", str(cfgp)])
            assert "--scout does not apply to --repair-asr" in err
        # fires before any side effect — the unguarded fall-through reaches WorkDir.for_url,
        # which mkdirs. Mirrors the --only test's assertion.
        assert not (tmp / "work").exists()


def test_scout_with_force_is_legal() -> None:
    # --force with --scout re-runs BOTH stages (run_pipeline bypasses done() for the whole
    # list), not just the fetch. Legal, and the help text says so.
    rec = _Recorder()
    real = cli._run_batch_stage_major
    cli._run_batch_stage_major = rec
    try:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            q = tmp / "queue.txt"
            q.write_text("\n".join(URLS), encoding="utf-8")
            assert _exits(cli.main, ["--batch", str(q), "--scout", "--force",
                                     "--config", str(_cfg_file(tmp))])
    finally:
        cli._run_batch_stage_major = real
    assert len(rec.calls) == 1
    assert rec.calls[0][1]["scout"] is True and rec.calls[0][1]["force"] is True


def test_scout_with_video_major_and_no_batch_is_still_a_usage_error() -> None:
    # --scout must not sneak a single-video run past the pre-existing --video-major guard.
    with tempfile.TemporaryDirectory() as d:
        cfgp = _cfg_file(Path(d))
        assert _exits(cli.main, [URL, "--scout", "--video-major", "--config", str(cfgp)])


def test_scout_single_url_reaches_the_scout_driver() -> None:
    seen: list = []
    real = cli._run_one
    cli._run_one = lambda url, cfg, **kw: seen.append((url, kw)) or None
    try:
        with tempfile.TemporaryDirectory() as d:
            _quiet(cli.main, [URL, "--scout", "--config", str(_cfg_file(Path(d)))])
    finally:
        cli._run_one = real
    assert len(seen) == 1
    assert seen[0][0] == URL and seen[0][1]["scout"] is True


# --- stage list ---------------------------------------------------------------------

def test_scout_stage_list_is_download_then_transcribe() -> None:
    assert [s.name for s in scout_stages(Config())] == ["download", "transcribe"]


def test_scout_stage_list_is_a_strict_prefix_of_all_stages() -> None:
    # A promoted video re-enters the FULL pipeline on the artifacts these two produced. If the
    # scout list ever stops being a prefix, promotion resumes onto a workdir built by a
    # different sequence and the fast-skips stop meaning what they say.
    cfg = Config()
    assert ([s.name for s in scout_stages(cfg)]
            == [s.name for s in all_stages(cfg)][:2])


def test_scout_download_is_audio_only_and_the_full_one_is_not() -> None:
    # The desynchronization guard: truncated list + full download = 100 GB for a triage pass;
    # full list + audio-only download = mux failing at the end of an eight-hour run.
    cfg = Config()
    assert scout_stages(cfg)[0].audio_only is True
    assert all_stages(cfg)[0].audio_only is False


def test_scout_runs_no_stage_after_transcribe() -> None:
    """Through cli.main, so what is pinned is that main SELECTS the scout list.

    Patching cli.scout_stages (not cli.all_stages) is the point: patching the latter would
    leave scout untested and the assertion green.
    """
    trace: list = []
    scouts = [FakeStage(n, trace) for n in ("download", "transcribe")]
    full = scouts + [FakeStage(n, trace) for n in
                     ("translate", "synthesize", "verify", "assemble", "separate", "mux")]
    real_scout, real_all = cli.scout_stages, cli.all_stages
    cli.scout_stages = lambda cfg: scouts
    cli.all_stages = lambda cfg: full
    try:
        with tempfile.TemporaryDirectory() as d:
            _quiet(cli.main, [URL, "--scout", "--config", str(_cfg_file(Path(d)))])
    finally:
        cli.scout_stages, cli.all_stages = real_scout, real_all
    assert _runs(trace) == [("download", VIDS[0]), ("transcribe", VIDS[0])]
    # not even a done() PROBE for a later stage — an --only composition would have swept all 8
    assert not [t for t in trace if len(t) == 3 and t[1] not in ("download", "transcribe")]


# --- download gate ------------------------------------------------------------------

def test_video_gate_requires_both_artifacts() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        st = DownloadStage()
        ctx.work.source_audio.write_bytes(b"wav")
        assert st.done(ctx) is False                     # wav alone is not a video
        ctx.work.source_audio.unlink()
        ctx.work.source_video.write_bytes(b"mkv")
        assert st.done(ctx) is False                     # mkv alone is not enough either
        ctx.work.source_audio.write_bytes(b"wav")
        assert st.done(ctx) is True


def test_audio_gate_is_satisfied_by_source_wav_alone() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.source_audio.write_bytes(b"wav")
        assert DownloadStage(audio_only=True).done(ctx) is True
        assert not ctx.work.source_video.exists()


def test_scout_download_fast_skips_when_source_wav_exists() -> None:
    # Resume: a second --scout pass over the same queue must cost seconds, not a re-fetch.
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.source_audio.write_bytes(b"wav")
        st = DownloadStage(audio_only=True)

        def boom(_ctx):
            raise AssertionError("scout download re-ran despite source.wav being present")

        st.run = boom
        _, out = _quiet(run_pipeline, ctx, [st])
    assert "[skip] download" in out


# --- download argv / artifacts ------------------------------------------------------

def _fake_ytdlp(calls, tmp_root: Path, *, ext: str = "webm", sidecar: bool = True,
                extra: list[str] | None = None):
    """subprocess.run stand-in: records argv and writes what the real tool would leave behind."""
    def run(argv, **kw):
        calls.append(list(argv))
        if argv[0] == "yt-dlp":
            out = Path(argv[argv.index("-o") + 1])
            media = Path(str(out).replace("%(ext)s", ext))
            media.write_bytes(b"\0" * 1234567)
            if sidecar:
                (media.parent / f"{media.name}.info.json").write_text(
                    json.dumps({"title": "Scouted Title", "duration": 2530.0}), encoding="utf-8")
            for name in (extra or []):
                (media.parent / name).write_bytes(b"\0" * 10)
        else:                                            # ffmpeg
            Path(argv[-1]).write_bytes(b"RIFFfake")
        return subprocess.CompletedProcess(argv, 0)
    return run


def _with_fake_subprocess(fn):
    """Swap subprocess.run inside the download module only — nothing else in the process."""
    from overdub.stages import download as dl
    real = dl.subprocess.run
    try:
        return fn(dl)
    finally:
        dl.subprocess.run = real


def test_scout_ytdlp_argv() -> None:
    calls: list = []
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))

        def body(dl):
            dl.subprocess.run = _fake_ytdlp(calls, ctx.work.root)
            _quiet(DownloadStage(audio_only=True).run, ctx)

        _with_fake_subprocess(body)
        yt = next(c for c in calls if c[0] == "yt-dlp")
        fmt = yt[yt.index("-f") + 1]
        assert fmt == "bestaudio"
        # '/best' would silently pull a full progressive VIDEO stream — the mode's opposite,
        # at ~20x the bytes. A hard FAIL is the correct outcome for a source without an
        # audio-only format.
        assert "/best" not in fmt and "/b" not in fmt
        assert "--merge-output-format" not in yt
        assert yt[yt.index("-o") + 1].endswith("source.audio.%(ext)s")
        assert not ctx.work.source_video.exists()        # never a container
        assert ctx.work.source_audio.exists()
        # Retries are part of the contract, not an incidental flag: a 12-video batch arrives at
        # YouTube as one burst (stage-major hoists every download into the first minutes), and
        # the two videos lost that way on 2026-07-20 both succeeded on a plain re-run. Backing
        # off inside the run spends seconds to save a human-initiated retry.
        assert yt[yt.index("--retries") + 1] == "10"
        assert yt[yt.index("--extractor-retries") + 1] == "5"
        assert yt[yt.index("--retry-sleep") + 1].startswith("exp=")


def test_scout_ffmpeg_argv_and_atomic_write() -> None:
    calls: list = []
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))

        def body(dl):
            dl.subprocess.run = _fake_ytdlp(calls, ctx.work.root)
            _quiet(DownloadStage(audio_only=True).run, ctx)

        _with_fake_subprocess(body)
    ff = next(c for c in calls if c[0] == "ffmpeg")
    for pair in (("-ac", "1"), ("-ar", "16000"), ("-c:a", "pcm_s16le")):
        assert ff[ff.index(pair[0]) + 1] == pair[1]
    # -f wav is NOT cosmetic, and this pairing is the whole reason it exists: the output path
    # ends in ".tmp", from which ffmpeg cannot infer a muxer, so it exits non-zero before
    # writing anything (verified: exit 127 on ffmpeg 7.1.1). subprocess.run is faked in every
    # test in this file, so this assertion is the only thing standing between the repo and a
    # download stage that fails on its very first REAL invocation — in both modes. Asserting
    # the tmp name alone once pinned an argv that ffmpeg rejected outright.
    assert ff[ff.index("-f") + 1] == "wav"
    # ffmpeg writes a .tmp; source.wav only ever appears via replace_retry, so an interrupted
    # extraction can never leave a truncated file that done() accepts as complete. Matched by
    # membership, not final position — a flag appended after the path must not make this vacuous.
    assert any(a.endswith("source.wav.tmp") for a in ff)


def test_torn_extraction_leaves_no_source_wav() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))

        def body(dl):
            def run(argv, **kw):
                if argv[0] == "yt-dlp":
                    media = Path(str(argv[argv.index("-o") + 1]).replace("%(ext)s", "webm"))
                    media.write_bytes(b"\0" * 100)
                    return subprocess.CompletedProcess(argv, 0)
                Path(argv[-1]).write_bytes(b"RIFF")       # a SHORT tmp, then death
                raise subprocess.CalledProcessError(1, argv)

            dl.subprocess.run = run
            try:
                _quiet(DownloadStage(audio_only=True).run, ctx)
            except subprocess.CalledProcessError:
                pass

        _with_fake_subprocess(body)
        # the gate must stay False, so a re-run redoes the extraction instead of transcribing
        # a truncated wav and shipping a short sentences.json with nothing ever saying so
        assert not ctx.work.source_audio.exists()
        assert DownloadStage(audio_only=True).done(ctx) is False


def test_scout_info_json_is_normalized() -> None:
    # Left as source.audio.webm.info.json, NOTHING reads it: _title_of pays a 30 s networked
    # lookup per video (~50 min over a 100-video queue) and a promoted run.json silently
    # downgrades video_sec_source from "info_json" to ffprobe/sentences.
    calls: list = []
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))

        def body(dl):
            dl.subprocess.run = _fake_ytdlp(calls, ctx.work.root)
            _quiet(DownloadStage(audio_only=True).run, ctx)

        _with_fake_subprocess(body)
        assert ctx.work.info_json.exists()
        assert not list(ctx.work.root.glob("source.audio*.info.json"))
        doc = json.loads(ctx.work.info_json.read_text(encoding="utf-8"))
        assert doc["title"] == "Scouted Title" and doc["duration"] == 2530.0

        # and _title_of finds it WITHOUT a subprocess call of its own
        import overdub.cli as c
        real = c.subprocess.run
        c.subprocess.run = lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("_title_of made a network call despite a normalized info.json"))
        try:
            assert cli._title_of(ctx) == "Scouted Title"
        finally:
            c.subprocess.run = real


def test_scout_info_json_prefers_the_fresh_sidecar() -> None:
    # _title_of's backfill writes {"title": ...} and nothing else. Keeping that over the fetch's
    # full sidecar would drop `duration` and re-introduce exactly the video_sec_source downgrade
    # the normalization exists to prevent, so the rename is unconditional.
    calls: list = []
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.info_json.write_text(json.dumps({"title": "Stale Backfill"}), encoding="utf-8")

        def body(dl):
            dl.subprocess.run = _fake_ytdlp(calls, ctx.work.root)
            _quiet(DownloadStage(audio_only=True).run, ctx)

        _with_fake_subprocess(body)
        doc = json.loads(ctx.work.info_json.read_text(encoding="utf-8"))
    assert doc["title"] == "Scouted Title"
    assert doc["duration"] == 2530.0


def test_scout_fails_loud_on_an_ambiguous_media_glob() -> None:
    # Picking the first would transcribe whichever container sorted lowest — and one of the two
    # is by definition not what yt-dlp just fetched.
    calls: list = []
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))

        def body(dl):
            dl.subprocess.run = _fake_ytdlp(calls, ctx.work.root, extra=["source.audio.m4a"])
            try:
                _quiet(DownloadStage(audio_only=True).run, ctx)
            except RuntimeError as e:
                return str(e)
            raise AssertionError("ambiguous source.audio.* glob did not raise")

        msg = _with_fake_subprocess(body)
    assert "source.audio.m4a" in msg and "source.audio.webm" in msg


def test_scout_cleans_a_stale_audio_file_before_fetching() -> None:
    calls: list = []
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        (ctx.work.root / "source.audio.m4a").write_bytes(b"orphan")   # crashed prior fetch

        def body(dl):
            dl.subprocess.run = _fake_ytdlp(calls, ctx.work.root)
            _quiet(DownloadStage(audio_only=True).run, ctx)

        _with_fake_subprocess(body)                       # must not hit the one-file invariant
        assert not (ctx.work.root / "source.audio.m4a").exists()
        assert ctx.work.source_audio.exists()


# --- promotion ----------------------------------------------------------------------

def test_promotion_does_not_retranscribe() -> None:
    # The REAL TranscribeStage.done(), not a fake: the whole point of scouting is that the
    # expensive large-v3 pass is paid once. done() is a bare sentences.json existence check —
    # no mtime, no key stamp, no dependency on source.wav.
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.source_audio.write_bytes(b"wav")
        _sentences(ctx.work)
        before = (ctx.work.sentences.read_bytes(), ctx.work.sentences.stat().st_mtime_ns)
        st = TranscribeStage()
        assert st.done(ctx) is True

        def boom(_ctx):
            raise AssertionError("promotion re-ran transcribe")

        st.run = boom
        _, out = _quiet(run_pipeline, ctx, [st])
        after = (ctx.work.sentences.read_bytes(), ctx.work.sentences.stat().st_mtime_ns)
    assert "[skip] transcribe" in out
    assert before == after


def test_promotion_refetches_because_source_mkv_is_missing() -> None:
    # Deliberate, DECISIONS 2026-07-20: ~5% extra traffic buys zero new machinery. Do NOT
    # "fix" this by letting the video gate accept source.wav — mux would get a container with
    # no video stream.
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.source_audio.write_bytes(b"wav")
        _sentences(ctx.work)
        assert DownloadStage().done(ctx) is False


def test_promotion_download_does_not_invalidate_the_transcript() -> None:
    # The re-download REWRITES source.wav. No done() anywhere compares its mtime (mux keys on
    # output/dub_audio/source_bed, separate is a bare existence check), so the rewrite must
    # cascade into exactly zero re-runs.
    calls: list = []
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.source_audio.write_bytes(b"OLD BYTES")
        _sentences(ctx.work)
        ctx.work.words.write_text("[]", encoding="utf-8")
        sent_before = ctx.work.sentences.read_bytes()

        def body(dl):
            dl.subprocess.run = _fake_ytdlp(calls, ctx.work.root)
            _quiet(DownloadStage(audio_only=True).run, ctx)

        _with_fake_subprocess(body)
        assert ctx.work.source_audio.read_bytes() != b"OLD BYTES"   # genuinely rewritten
        assert ctx.work.sentences.read_bytes() == sent_before
        assert ctx.work.words.exists()
        assert TranscribeStage().done(ctx) is True


def test_repair_invalidates_summary_md() -> None:
    # Pins summary.md's place in invalidate_downstream's target list against a future edit
    # moving it to the survivors: the summarizer's only input is sentences.json, so a repair
    # makes the prose describe a transcript that no longer exists.
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.source_audio.write_bytes(b"wav")
        _sentences(ctx.work)
        ctx.work.summary.write_text("Стоит смотреть.", encoding="utf-8")
        removed, failed = ctx.work.invalidate_downstream()
        assert "summary.md" in removed and not failed
        assert not ctx.work.summary.exists()
        assert ctx.work.source_audio.exists() and ctx.work.sentences.exists()


# --- batch orders, summary, exit codes ----------------------------------------------

def _drive_main(tmp: Path, argv_extra: list[str], scouts, full):
    """cli.main over a 3-URL queue with both stage lists patched. Returns (code, output).

    _export_output is deliberately NOT patched. Scout's finalize is _scout_status, so the real
    _export_output is never reached anyway — but patching it to a success value is what lets a
    mutant that reverts `finalize` to _export_output return "out.mkv" and keep every assertion
    below green. The scout-status feature could then be deleted wholesale with a green suite.
    """
    q = tmp / "queue.txt"
    q.write_text("\n".join(URLS), encoding="utf-8")
    real_scout, real_all = cli.scout_stages, cli.all_stages
    cli.scout_stages = lambda cfg: scouts
    cli.all_stages = lambda cfg: full
    code = None
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                cli.main(["--batch", str(q), "--scout", "--config", str(_cfg_file(tmp))]
                         + argv_extra)
            except SystemExit as e:
                code = e.code
    finally:
        cli.scout_stages, cli.all_stages = real_scout, real_all
    return code, buf.getvalue()


def test_scout_runs_in_stage_major_order() -> None:
    trace: list = []
    scouts = [FakeStage(n, trace) for n in ("download", "transcribe")]
    with tempfile.TemporaryDirectory() as d:
        code, _ = _drive_main(Path(d), [], scouts, scouts + [FakeStage("mux", trace)])
    assert code == 0
    assert _runs(trace) == [(s, v) for s in ("download", "transcribe") for v in VIDS]


def test_scout_runs_in_video_major_order() -> None:
    trace: list = []
    scouts = [FakeStage(n, trace) for n in ("download", "transcribe")]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive_main(Path(d), ["--video-major"], scouts,
                                scouts + [FakeStage("mux", trace)])
    assert code == 0
    assert _runs(trace) == [(s, v) for v in VIDS for s in ("download", "transcribe")]
    # video-major picks _scout_status too, via _run_one — BOTH drivers must cover the finalize
    # wiring, or a revert in one order hides behind the other order's test
    assert out.count("scouted · ") == 3


def test_clean_scout_batch_exits_zero() -> None:
    # Absence of output.mkv is NOT a failure in scout mode — the whole contract is that there
    # is none. No new exit codes: 0/1/2/3 keep their meanings.
    trace: list = []
    scouts = [FakeStage(n, trace) for n in ("download", "transcribe")]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive_main(Path(d), [], scouts, scouts)
    assert code == 0
    assert "3 ok, 0 failed, 0 unfinished" in out
    # POSITIVE: every row came from _scout_status. The bare `not in` below cannot pin the
    # finalize CHOICE on its own — _export_output returning any truthy name satisfies it too,
    # so without this the whole scout-status feature could be reverted with a green suite.
    assert out.count("scouted · ") == 3
    assert "(no output.mkv)" not in out


def test_scout_failure_exits_1_and_stop_exits_3() -> None:
    """The shared _summarize contract must survive the 2-stage list."""
    from overdub.pipeline import STOP_NAME

    class Failing(FakeStage):
        def run(self, ctx):
            super().run(ctx)
            if ctx.work.root.name == VIDS[1]:
                raise RuntimeError("boom")

    class Stopping(FakeStage):
        def run(self, ctx):
            super().run(ctx)
            if ctx.work.root.name == VIDS[0]:
                (ctx.cfg.work_root / STOP_NAME).write_text("", encoding="utf-8")

    trace: list = []
    scouts = [FakeStage("download", trace), Failing("transcribe", trace)]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive_main(Path(d), [], scouts, scouts)
    assert code == 1 and "2 ok, 1 failed" in out

    trace = []
    scouts = [Stopping("download", trace), FakeStage("transcribe", trace)]
    with tempfile.TemporaryDirectory() as d:
        code, out = _drive_main(Path(d), [], scouts, scouts)
    assert code == 3 and "STOP file honored" in out


def test_scout_summary_line_reports_sentences_and_summary_state() -> None:
    # The completion check for a whole scout pass: re-running the identical --scout command
    # fast-skips both stages and flips `pending` to `ok` once the Sonnet summarizer has run.
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        _sentences(ctx.work, n=431)
        ctx.work.info_json.write_text(json.dumps({"duration": 2530.0}), encoding="utf-8")
        line = cli._scout_status(ctx)
        assert "scouted" in line and "431 sentences" in line and "summary pending" in line
        assert "42:10" in line                            # 2530 s, M:SS
        assert "no output.mkv" not in line
        ctx.work.summary.write_text("Стоит смотреть.", encoding="utf-8")
        assert "summary ok" in cli._scout_status(ctx)


def test_scout_status_calls_an_empty_summary_pending() -> None:
    # exists() is not the boundary. A summarizer interrupted at the seam leaves a zero-byte (or
    # whitespace-only) summary.md, which read_summary strips back to None. Reporting that as
    # "ok" stops the operator re-running --scout and makes this line disagree with the triage
    # page, which routes the same file through read_summary and says "no summary.md yet". Two
    # reporters, one truth, and the optimistic one is the one that ends the scout pass.
    # The prose case above cannot see this: there, exists() and read_summary() agree.
    #
    # NOT covered, deliberately: a heading-only "## Заголовок" reads as ok. _HEADING strips the
    # marker and KEEPS the text, so read_summary returns "Заголовок" — non-empty. Both reporters
    # still agree, which is the invariant that matters here; "the summarizer wrote a title and
    # died" is a content judgement neither surface can make from bytes on disk.
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        _sentences(ctx.work)
        for content in ("", "   \n\n", "#\n\n##\n"):    # zero-byte, blank, bare markers only
            ctx.work.summary.write_text(content, encoding="utf-8")
            assert ctx.work.summary.exists()                  # the file IS there...
            assert "summary pending" in cli._scout_status(ctx), repr(content)   # ...and empty


def test_scout_status_reports_an_unreadable_transcript_instead_of_raising() -> None:
    # _scout_status is the stage-major driver's `finalize`; raising there would turn a
    # perfectly scouted video into a FAIL row.
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        ctx.work.sentences.write_text("{not json", encoding="utf-8")
        assert cli._scout_status(ctx) == "scouted · no readable sentences.json"


def test_scout_status_falls_back_to_sentence_ends_for_duration() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        _sentences(ctx.work, n=5)                         # last end = 5.0
        assert "0:05" in cli._scout_status(ctx)


def test_scout_finish_sweep_writes_no_run_json_and_no_output() -> None:
    # The property the scout CARD in triage_html depends on: build_run_report returns None and
    # self-clears run.json when report.json and translation.json are both absent, which is
    # exactly a scout workdir's shape.
    trace: list = []
    scouts = [FakeStage(n, trace) for n in ("download", "transcribe")]
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        code, _ = _drive_main(tmp, [], scouts, scouts)
        assert code == 0
        for v in VIDS:
            assert not (tmp / "work" / v / "run.json").exists()
            assert not (tmp / "work" / v / "output.mkv").exists()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all scout tests passed")
