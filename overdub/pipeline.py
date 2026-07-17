"""Stage runner: sequential per video, resumable, skip-if-artifact-exists.

Every stage is artifact-driven — `done(ctx)` checks whether its output already
exists so a re-run resumes instead of redoing work. Stages can be run in
isolation via the CLI `--only` flag.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .config import Config
from .workdir import WorkDir

STOP_NAME = "STOP"


class StopRequested(Exception):
    """STOP file seen at a checkpoint; str(exc) says where ("before stage 'x'")."""


def check_stop(work_root: Path, where: str) -> None:
    """O(1) stop-switch checkpoint: if work_root/STOP exists, consume it and raise.
    Consuming at honor time means a plain re-run resumes; the stale-file sweep at
    run start (cli.main) is the safety net for a crash between detect and unlink."""
    stop = work_root / STOP_NAME
    if not stop.exists():
        return
    try:
        stop.unlink()
    except OSError:
        print(f"[warn] could not remove {stop} — remove it manually")
    raise StopRequested(where)


@dataclass
class Context:
    url: str
    cfg: Config
    work: WorkDir


class Stage(Protocol):
    name: str

    def done(self, ctx: Context) -> bool: ...

    def run(self, ctx: Context) -> None: ...


def run_pipeline(
    ctx: Context,
    stages: list[Stage],
    *,
    force: bool = False,
    only: set[str] | None = None,
) -> None:
    for st in stages:
        # before the only/done filters: a stop halts at the next stage boundary even
        # through a run of [skip] lines (predictability beats racing to finish)
        check_stop(ctx.cfg.work_root, f"before stage '{st.name}'")
        if only is not None and st.name not in only:
            continue
        if not force and st.done(ctx):
            print(f"[skip] {st.name}  (artifact exists)")
            continue
        print(f"[run ] {st.name}")
        t0 = time.perf_counter()
        st.run(ctx)
        print(f"[ok  ] {st.name}  {time.perf_counter() - t0:.1f}s")
