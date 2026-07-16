"""report.json read-modify-write, co-owned by verify and assemble.

verify writes per-segment similarity + verify flags; assemble writes per-segment speed
factors. They run in separate stages and either may be re-run in isolation, so the merge
is BY SEGMENT ID and preserves the other stage's fields — a divergent merge that dropped a
foreign field would be a silent data loss, the one failure this pipeline forbids. This is the
same "centralize the correctness-critical shared transform" precedent as normalize.py.

Note: verify.done() must check the object's "verify" marker key, NOT report.exists() — an
--only assemble run creates report.json first, and an existence gate would then make verify
believe it had already run and skip verification forever.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # atomic save() makes a torn report unreachable in normal operation, so this means
            # external corruption. Warn — silently dropping the other stage's fields would be the
            # exact silent loss this module exists to prevent (it stays observable, not hidden).
            print(f"       [warn] {path.name} unreadable — rebuilding this stage's fields",
                  file=sys.stderr)
    return {"segments": []}


def upsert(rep: dict, sid: int, **fields) -> None:
    """Merge `fields` into the segment record for `sid`, leaving foreign keys untouched.
    Callers iterate ids in order and append on first sight, so the list stays id-sorted."""
    for rec in rep.setdefault("segments", []):
        if rec["id"] == sid:
            rec.update(fields)
            return
    rep["segments"].append({"id": sid, **fields})


def prune(rep: dict, live_ids: set[int]) -> None:
    """Drop segment records whose id is no longer in the run — after a re-tune shrinks the
    sentence count, stale records would otherwise linger as phantom (often flagged) segments in
    the report. Safe because both co-owners share the same translation.json id set, so pruning
    to the live ids can never remove a foreign stage's live fields."""
    rep["segments"] = [r for r in rep.get("segments", []) if r["id"] in live_ids]


def save(path: Path, rep: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
