"""The DECISIONS index is hand-maintained; this is what keeps it honest.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_decisions_index.py   (or via pytest)
Since 2026-08-24 the record is TWO files: `DECISIONS.md` at the root is the index, and
`docs/decisions-log.md` holds the dated entries (DECISIONS 2026-08-24, the split entry).
A stale index is worse than no index — it reads as complete either way, and the one thing a
lookup table must never do is quietly stop covering the log. Matching is by DATE with
multiplicity, never by title: index labels are deliberate paraphrases of the headings, so string
equality would fail on correct data. The year is not compared for the same reason it is not
written in the index — MM-DD is what the index carries. An index line ENDING in a `→ <path>`
link is exempt from the sync check: its detail lives in a module doc or task file, not in the
log. The path must contain a slash and close the line — a bare `→` inside a label ("0.8 → 0.9",
"48→16") is not a link and the line stays log-backed.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_LINES = (ROOT / "DECISIONS.md").read_text(encoding="utf-8").splitlines()
LOG_LINES = (ROOT / "docs" / "decisions-log.md").read_text(encoding="utf-8").splitlines()

HEADING = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
# The bold markers are optional on purpose: the log header documents the tombstone as
# `> SUPERSEDED <date>`, so a guard that only matched `> **SUPERSEDED` would pass silently on
# the exact form the file tells the author to write.
TOMBSTONE = re.compile(r"^> (?:\*\*)?(?:PARTLY )?SUPERSEDED")
DATED_TOMBSTONE = re.compile(r"^> (?:\*\*)?(?:PARTLY )?SUPERSEDED \d{4}-\d{2}-\d{2}")
LINKED_AWAY = re.compile(r"→ \S*/\S+$")   # trailing path link; a `→` inside a label is not one


def _archive_start() -> int:
    return next(i for i, line in enumerate(LOG_LINES) if line.startswith("# ARCHIVE"))


def _headings(lo: int = 0, hi: int | None = None) -> list[tuple[int, str]]:
    hi = len(LOG_LINES) if hi is None else hi
    found = ((i, HEADING.match(LOG_LINES[i])) for i in range(lo, hi))
    return [(i, m.group(1)) for i, m in found if m]


def test_index_covers_every_log_entry() -> None:
    log_backed = "\n".join(line for line in INDEX_LINES if not LINKED_AWAY.search(line))
    indexed = Counter(re.findall(r"`(\d{2}-\d{2})`", log_backed))
    present = Counter(date[5:] for _, date in _headings())
    unindexed = present - indexed
    dangling = indexed - present
    assert not unindexed and not dangling, (
        f"Index (DECISIONS.md) is out of sync with the log entries (docs/decisions-log.md).\n"
        f"  entries with no index line (by MM-DD, with multiplicity): {dict(unindexed)}\n"
        f"  index lines with no entry:                                {dict(dangling)}"
    )


def test_every_tombstone_carries_a_date() -> None:
    # An undated one is invisible to `grep 'SUPERSEDED 2026'` and cannot be ordered against the
    # entry it supersedes.
    undated = [(i + 1, LOG_LINES[i]) for i in range(len(LOG_LINES))
               if TOMBSTONE.match(LOG_LINES[i]) and not DATED_TOMBSTONE.match(LOG_LINES[i])]
    assert not undated, f"tombstones without a date: {undated}"


# Both order guards compare DATES, so they bind only where adjacent entries differ in date —
# most adjacent pairs share one and are unconstrained. That is the whole guarantee on offer: the
# log has no within-day ordering to check against, so these catch a block moved across a date
# boundary and nothing finer.
def test_entry_dates_above_the_archive_never_increase() -> None:
    dates = [date for _, date in _headings(hi=_archive_start())]
    assert dates == sorted(dates, reverse=True), "the main block is not newest-first"


def test_entry_dates_in_the_archive_never_decrease() -> None:
    dates = [date for _, date in _headings(lo=_archive_start())]
    assert dates == sorted(dates), "the founding archive is not oldest-first"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all decisions index tests passed")
