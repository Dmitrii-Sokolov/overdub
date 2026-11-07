"""Unit tests for overdub/host.py's RAM admission rule — the one both mux schedulers share.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_host.py   (or via pytest)
No hardware is read: available_ram is replaced, so what is under test is the rule alone.
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import host  # noqa: E402


def _admission(free):
    """ram_admission() on a host reporting `free` (None: unreadable). Returns (admits, stderr)."""
    real = host.available_ram
    host.available_ram = lambda: free
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            return host.ram_admission(), err.getvalue()
    finally:
        host.available_ram = real


def test_nothing_running_is_always_admitted() -> None:
    admits, _ = _admission(host._RAM_HEADROOM + 10)
    assert admits([], 10**12)                              # too large for the budget: runs alone


def test_admits_while_the_running_needs_plus_this_one_fit_the_budget() -> None:
    admits, _ = _admission(host._RAM_HEADROOM + 10)
    assert admits([3, 3], 4) and not admits([3, 3], 5)
    assert admits([0], 10) and not admits([0], 11)         # a zero-need job still counts as running


def test_the_headroom_comes_off_the_free_ram() -> None:
    admits, _ = _admission(host._RAM_HEADROOM - 1)         # less free than the headroom: budget 0
    assert admits([1], 0) is False and admits([0], 0) is True


def test_the_budget_is_read_once_not_per_admission() -> None:
    # a job that has started but not yet allocated would make a live re-reading look free
    calls = []
    real = host.available_ram
    host.available_ram = lambda: calls.append(1) or host._RAM_HEADROOM + 10
    try:
        admits = host.ram_admission()
        for _ in range(3):
            admits([5], 5)
    finally:
        host.available_ram = real
    assert len(calls) == 1


def test_unreadable_ram_admits_one_job_at_a_time_and_says_so() -> None:
    # before the concurrent paths existed the work ran serially; an unreadable host runs as before
    admits, err = _admission(None)
    assert admits([], 10**12)
    assert not admits([0], 0)
    assert "one at a time" in err


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all host tests passed")
