"""The separate stage's ffmpeg extract must survive an audio track past 4 GiB.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_separate_rf64.py   (or via pytest)

WHY THIS FILE EXISTS. WAV keeps its size in a 32-bit field, so at 176400 B/s (44.1k stereo
s16) the container overflows at 6h46m of source audio and ffmpeg writes a file whose header
no reader accepts. Measured 2026-08-11 on a route-B batch: 3 of 11 videos (6.95, 7.50 and
7.90 h) died at separate with demucs exit 1, while all 8 shorter ones passed.

That length threshold hides TWO walls, and this file only removes the first. With the flag in
place the 6.95 h video separated normally, while the 7.90 h one failed again on a 37.4 GiB
single CPU allocation — demucs holds the whole track in RAM and needs several float32 copies
of it (9.3 GB each at that length). So a green test here does NOT mean long videos separate;
it means the container stopped being the reason they do not.

The defect is invisible below the threshold, which is exactly why it needs a test: the flag
can be dropped from the argv and every ordinary video still separates fine. What is asserted
here is the flag AND its position — an ffmpeg output option placed after the output filename
is silently ignored, so a correct-looking edit that moves it past the path reintroduces the
bug in full.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overdub.config import Config                          # noqa: E402
from overdub.pipeline import Context                       # noqa: E402
from overdub.stages import separate as sep                 # noqa: E402
from overdub.workdir import WorkDir                        # noqa: E402

URL = "https://www.youtube.com/watch?v=aaaaaaaaaaa"


def _ffmpeg_argv(tmp: Path) -> list[str]:
    """Drive SeparateStage with every subprocess faked; return the ffmpeg call's argv."""
    cfg = Config(work_root=tmp / "work", demucs_python=Path(sys.executable))
    work = WorkDir.for_url(URL, cfg.work_root)
    work.source_video.write_bytes(b"")                     # only its existence is checked
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):                          # noqa: ANN001, ANN003
        calls.append(list(argv))
        if argv[0] == "ffprobe":
            # Under the chunk threshold on purpose: this file is about the single-pass extract.
            return SimpleNamespace(stdout="600.0\n")
        if "demucs.separate" in argv:
            # The stage raises unless the bed lands, so the fake has to produce one.
            stem = Path(argv[-1]).stem
            bed = Path(argv[argv.index("-o") + 1]) / "htdemucs" / stem / "no_vocals.wav"
            bed.parent.mkdir(parents=True, exist_ok=True)
            bed.write_bytes(b"")
        return None

    real_run, real_which = sep.subprocess.run, sep.shutil.which
    sep.subprocess.run = fake_run
    sep.shutil.which = lambda name: name                   # no ffmpeg on the test host
    try:
        sep.SeparateStage().run(Context(url=URL, cfg=cfg, work=work))
    finally:
        sep.subprocess.run, sep.shutil.which = real_run, real_which
    return next(c for c in calls if c[0] == "ffmpeg")


def test_extract_requests_rf64_auto() -> None:
    with tempfile.TemporaryDirectory() as d:
        ff = _ffmpeg_argv(Path(d))
    assert "-rf64" in ff, "the >4 GiB guard is gone — audio past 6h46m will write a broken WAV"
    assert ff[ff.index("-rf64") + 1] == "auto"


def test_rf64_flag_precedes_the_output_path() -> None:
    # ffmpeg applies output options only to the file that FOLLOWS them; after the path it is
    # parsed as an input-less no-op and the header silently stays 32-bit.
    with tempfile.TemporaryDirectory() as d:
        ff = _ffmpeg_argv(Path(d))
    assert ff.index("-rf64") < len(ff) - 1
    assert ff[-1].endswith("source_full.wav")


def test_extract_stays_44k_stereo_s16() -> None:
    # -rf64 auto must not have been bought by changing the format demucs is tuned on.
    with tempfile.TemporaryDirectory() as d:
        ff = _ffmpeg_argv(Path(d))
    for flag, want in (("-ac", "2"), ("-ar", "44100"), ("-c:a", "pcm_s16le")):
        assert ff[ff.index(flag) + 1] == want


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all separate rf64 tests passed")
