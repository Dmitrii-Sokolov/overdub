"""The DECISIONS.md Index is hand-maintained; this is what keeps it honest.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_decisions_index.py   (or via pytest)
A stale index is worse than no index — it reads as complete either way, and the one thing a
lookup table must never do is quietly stop covering the file. Matching is by DATE with
multiplicity, never by title: index labels are deliberate paraphrases of the headings, so string
equality would fail on correct data. The year is not compared for the same reason it is not
written in the index — MM-DD is what the index carries.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECISIONS = ROOT / ".claude" / "DECISIONS.md"

LINES = DECISIONS.read_text(encoding="utf-8").splitlines()

HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
TOMBSTONE = re.compile(r"^> \*\*(?:PARTLY )?SUPERSEDED")
DATED_TOMBSTONE = re.compile(r"^> \*\*(?:PARTLY )?SUPERSEDED \d{4}-\d{2}-\d{2}\*\*")


def _index_end() -> int:
    """Line of the `---` that closes the Index block — also the append point."""
    start = LINES.index("## Index")
    return next(i for i in range(start, len(LINES)) if LINES[i] == "---")


def _archive_start() -> int:
    return next(i for i, line in enumerate(LINES) if line.startswith("# ARCHIVE"))


def _headings(lo: int = 0, hi: int | None = None) -> list[tuple[int, str]]:
    hi = len(LINES) if hi is None else hi
    found = ((i, HEADING.match(LINES[i])) for i in range(lo, hi))
    return [(i, m.group(1)) for i, m in found if m]


def test_index_covers_every_entry() -> None:
    block = "\n".join(LINES[LINES.index("## Index"):_index_end()])
    indexed = Counter(re.findall(r"`(\d{2}-\d{2})`", block))
    present = Counter(date[5:] for _, date in _headings())
    unindexed = present - indexed
    dangling = indexed - present
    assert not unindexed and not dangling, (
        f"Index is out of sync with the entries.\n"
        f"  entries with no index line (by MM-DD, with multiplicity): {dict(unindexed)}\n"
        f"  index lines with no entry:                                {dict(dangling)}"
    )


def test_every_tombstone_carries_a_date() -> None:
    # An undated one is invisible to `grep 'SUPERSEDED 2026'` and cannot be ordered against the
    # entry it supersedes.
    undated = [(i + 1, LINES[i]) for i in range(len(LINES))
               if TOMBSTONE.match(LINES[i]) and not DATED_TOMBSTONE.match(LINES[i])]
    assert not undated, f"tombstones without a date: {undated}"


def test_the_index_precedes_every_entry() -> None:
    # The append rule points at the `---` closing the Index; an entry above it would break both
    # the rule and the newest-first scan below.
    assert _headings()[0][0] > _index_end()


def test_entries_above_the_archive_run_newest_first() -> None:
    dates = [date for _, date in _headings(hi=_archive_start())]
    assert dates == sorted(dates, reverse=True), "the main block is not newest-first"


def test_the_archive_runs_forward() -> None:
    dates = [date for _, date in _headings(lo=_archive_start())]
    assert dates == sorted(dates), "the founding archive is not oldest-first"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all decisions index tests passed")
