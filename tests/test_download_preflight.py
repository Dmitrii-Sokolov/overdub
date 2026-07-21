"""Unit tests for download._tool_exe — the external-tool preflight resolver.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_download_preflight.py   (or via pytest)

No subprocess, no network, no real tools: REAL shutil.which over dummy .exe files in tmp
dirs, with sys.executable and PATH monkeypatched around each call. What is under test is
the RESOLUTION ORDER — the dir next to the running python (the venv Scripts dir) must
shadow PATH, because two yt-dlp binaries were installed and a bare argv[0] picked the
older PATH one (running .venv-asr\\Scripts\\python.exe does not activate the venv) — and
the failure mode: a RuntimeError that NAMES the tool, instead of subprocess's raw
WinError 2 with no hint of which binary was missing.
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.stages.download import _tool_exe  # noqa: E402


@contextlib.contextmanager
def _resolver_env(venv_dir: Path, path_dir: Path):
    """sys.executable → a fake python inside venv_dir (the file need not exist — the
    resolver only takes .parent of it); PATH → path_dir ALONE, so nothing installed on
    the host machine can leak into a resolution and flip a test green or red. PATHEXT is
    left untouched: shutil.which's .exe suffixing IS part of what the resolver relies on,
    so neutering it would test a different function. Restored in finally — sys.executable
    is process-global state, and _tool_exe reads it at call time by contract."""
    real_exe, real_path = sys.executable, os.environ.get("PATH", "")
    sys.executable = str(venv_dir / "python.exe")
    os.environ["PATH"] = str(path_dir)
    try:
        yield
    finally:
        sys.executable = real_exe
        os.environ["PATH"] = real_path


def _dirs(tmp: str) -> tuple[Path, Path]:
    venv_dir = Path(tmp) / "venv" / "Scripts"
    path_dir = Path(tmp) / "elsewhere"
    venv_dir.mkdir(parents=True)
    path_dir.mkdir(parents=True)
    return venv_dir, path_dir


def test_venv_adjacent_exe_wins_over_path() -> None:
    # The finding this whole module exists for: with a binary in BOTH places, the one
    # next to sys.executable (2026.07.04 in .venv-asr) must win over PATH (2026.03.17).
    with tempfile.TemporaryDirectory() as d:
        venv_dir, path_dir = _dirs(d)
        (venv_dir / "yt-dlp.exe").write_bytes(b"")
        (path_dir / "yt-dlp.exe").write_bytes(b"")
        with _resolver_env(venv_dir, path_dir):
            assert Path(_tool_exe("yt-dlp")) == venv_dir / "yt-dlp.exe"


def test_falls_back_to_path_when_absent_next_to_python() -> None:
    # ffmpeg is the everyday case: never pip-installed into the venv, always on PATH.
    with tempfile.TemporaryDirectory() as d:
        venv_dir, path_dir = _dirs(d)
        (path_dir / "yt-dlp.exe").write_bytes(b"")
        with _resolver_env(venv_dir, path_dir):
            assert Path(_tool_exe("yt-dlp")) == path_dir / "yt-dlp.exe"


def test_missing_everywhere_raises_naming_the_tool() -> None:
    # The message must carry the tool name — "WinError 2" without a name once meant
    # bisecting a five-tool pipeline by hand to find out WHICH binary was missing.
    with tempfile.TemporaryDirectory() as d:
        venv_dir, path_dir = _dirs(d)                    # both exist, both empty
        with _resolver_env(venv_dir, path_dir):
            try:
                _tool_exe("yt-dlp")
            except RuntimeError as e:
                assert "yt-dlp" in str(e)
            else:
                raise AssertionError("_tool_exe found a yt-dlp in two empty dirs")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all download preflight tests passed")
