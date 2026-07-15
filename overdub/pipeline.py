"""Stage runner: sequential per video, resumable, skip-if-artifact-exists.

Every stage is artifact-driven — `done(ctx)` checks whether its output already
exists so a re-run resumes instead of redoing work. Stages can be run in
isolation via the CLI `--only` flag.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from .config import Config
from .workdir import WorkDir


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
        if only is not None and st.name not in only:
            continue
        if not force and st.done(ctx):
            print(f"[skip] {st.name}  (artifact exists)")
            continue
        print(f"[run ] {st.name}")
        t0 = time.perf_counter()
        st.run(ctx)
        print(f"[ok  ] {st.name}  {time.perf_counter() - t0:.1f}s")
