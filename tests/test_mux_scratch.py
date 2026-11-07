"""What the final mux encode leaves on disk — tmpdir, fake ffmpeg, tiny wavs, no media.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_mux_scratch.py   (or via pytest)

The encode is nearly all of mux's wall clock, and with mux_concurrency > 1 several of them run
at once. The three extraction wavs (dub, original, bed — 48 kHz stereo PCM) are fully read into
memory before the mix is built and never read again, so they must be off the disk before the
encode starts: on a long video each is gigabytes, and keeping them through the encode multiplies
the scratch by the number of concurrent muxes.

And an interrupt during the encode must not leave ffmpeg running behind it: the child is killed
and reaped, and the interrupt — not a cleanup error — is what reaches the caller.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.config import Config                                    # noqa: E402
from overdub.pipeline import Context                                 # noqa: E402
from overdub.stages import mux as mux_mod                            # noqa: E402
from overdub.workdir import WorkDir                                  # noqa: E402

SR = 24000
_SCRATCH = ("_mix_dub48.wav", "_mix_orig48.wav", "_mix_bed48.wav")


def _tone(seconds: float, sr: int, channels: int) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    mono = (0.3 * np.sin(2 * np.pi * 220 * t)).astype("float32")
    return np.stack([mono] * channels, axis=1) if channels > 1 else mono


def _fake_extract(src, dst, *, sr=mux_mod._MIX_SR, ch=2) -> None:
    sf.write(str(dst), _tone(2.0, sr, ch), sr, subtype="PCM_16")


def _dub_workdir(td: str) -> Context:
    """A complete dub workdir for dub_mix=bed: video, bed, manifest and an audible dub."""
    work = WorkDir.for_url("https://youtu.be/aaaaaaaaaaa", Path(td))
    ctx = Context(url="u", cfg=Config(), work=work)
    work.source_video.write_bytes(b"video")
    work.source_bed.write_bytes(b"bed")
    work.seg_manifest.parent.mkdir(parents=True, exist_ok=True)
    work.seg_manifest.write_text(json.dumps(
        {"units": [{"ids": [0], "start": 0.0, "end": 1.0, "samples": SR, "text_tts": "Один."}],
         "sample_rate": SR, "complete": True}), encoding="utf-8")
    sf.write(str(work.dub_audio), _tone(2.0, SR, 1), SR, subtype="PCM_16")
    return ctx


def _no_media_tools(monkeypatch) -> None:
    monkeypatch.setattr(mux_mod.shutil, "which", lambda _name: "ffmpeg")
    monkeypatch.setattr(mux_mod, "_extract", _fake_extract)
    monkeypatch.setattr(mux_mod.host, "pin", lambda _proc, _mask: False)


def test_extraction_wavs_are_gone_before_the_encode_starts(monkeypatch) -> None:
    _no_media_tools(monkeypatch)
    seen: dict[str, bool] = {}

    class _Encode:
        def __init__(self, argv):
            root = Path(argv[-1]).parent
            seen.update({name: (root / name).exists() for name in (*_SCRATCH, "_mix_ru.wav")})
            self.returncode = None

        def wait(self):
            self.returncode = 1                            # stop here: the snapshot is the test
            return 1

    monkeypatch.setattr(mux_mod.subprocess, "Popen", _Encode)
    with tempfile.TemporaryDirectory() as td:
        ctx = _dub_workdir(td)
        with pytest.raises(subprocess.CalledProcessError):
            mux_mod.MuxStage().run(ctx)
        left = sorted(p.name for p in ctx.work.root.glob("_mix_*"))
    assert seen == {"_mix_dub48.wav": False, "_mix_orig48.wav": False, "_mix_bed48.wav": False,
                    "_mix_ru.wav": True}, seen
    assert left == [], left                                # and the finally still clears the mix


class _Interrupt(BaseException):
    """Takes KeyboardInterrupt's path through the code, but a regression fails this one test
    instead of aborting the whole pytest session."""


def test_an_interrupt_during_the_encode_kills_ffmpeg_and_stays_the_error(monkeypatch) -> None:
    # A bare Popen + wait has no handler: the interrupt left ffmpeg running, and on Windows the
    # finally's unlink of the mix wav that ffmpeg still held raised PermissionError OVER the
    # interrupt — the batch logged a failed mux and moved on while the orphan kept encoding.
    _no_media_tools(monkeypatch)
    calls: list[str] = []

    class _Encode:
        def __init__(self, argv):
            # a live ffmpeg holds its input open, which on Windows blocks deleting it
            self._held = open(Path(argv[-1]).parent / "_mix_ru.wav", "rb")
            self.returncode = None

        def wait(self):
            calls.append("wait")
            if self.returncode is None:
                raise _Interrupt
            return self.returncode

        def kill(self):
            calls.append("kill")
            self._held.close()
            self.returncode = 1

    monkeypatch.setattr(mux_mod.subprocess, "Popen", _Encode)
    with tempfile.TemporaryDirectory() as td:
        ctx = _dub_workdir(td)
        with pytest.raises(_Interrupt):
            mux_mod.MuxStage().run(ctx)
        left = sorted(p.name for p in ctx.work.root.glob("_mix_*"))
    assert calls == ["wait", "kill", "wait"], calls        # killed, then reaped
    assert left == [], left


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
