"""Unit tests for the pre-flight host guard — pure, no GPU, no nvidia-smi.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_host_guard.py   (or via pytest)
The two fixture rows are REAL readings from 2026-07-25, the session that made this guard
necessary: the same laptop with a game on the card and without it. Contract: the busy host is
refused, the quiet one passes, a single utilisation spike does not trip the gate (the quiet
host genuinely read 27% once), and a host we cannot inspect is never reported as busy — an
absent nvidia-smi must forfeit the guarantee, not block the work.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from host_guard import BUSY_MEM_MIB, parse_row, verdict  # noqa: E402

BUSY = "98, 8634, 12282, 86, 1740"        # D2R holding the card
IDLE = "27, 1347, 12282, 61, 390"         # same host, game closed


def test_parses_a_real_row() -> None:
    assert parse_row(IDLE) == {"util": 27, "mem_used": 1347, "mem_total": 12282,
                               "temp": 61, "sm_clock": 390}


def test_unparseable_rows_are_none() -> None:
    assert parse_row("[N/A], [N/A], [N/A], [N/A], [N/A]") is None
    assert parse_row("27, 1347") is None
    assert parse_row("") is None


def test_busy_host_is_refused() -> None:
    v = verdict([parse_row(BUSY)] * 3)
    assert v["busy"] and v["known"]
    assert str(BUSY_MEM_MIB) in v["reason"]


def test_idle_host_passes() -> None:
    v = verdict([parse_row(IDLE)] * 3)
    assert not v["busy"] and v["known"]


def test_single_util_spike_does_not_trip_the_gate() -> None:
    # Desktop compositor spikes to 95% for one sample on an otherwise free card: the median
    # keeps it quiet, and memory stays low.
    rows = [parse_row(IDLE), parse_row("95, 1400, 12282, 62, 800"), parse_row(IDLE)]
    assert not verdict(rows)["busy"]


def test_memory_uses_max_not_median() -> None:
    # A load that frees memory between samples must still be caught.
    rows = [parse_row(IDLE), parse_row("30, 9000, 12282, 70, 900"), parse_row(IDLE)]
    assert verdict(rows)["busy"]


def test_unknown_host_is_not_busy() -> None:
    v = verdict([])
    assert not v["busy"] and not v["known"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all host guard tests passed")
