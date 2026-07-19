"""Human-readable run-report digest (route A + route B morning triage).

Surfaces the per-run rollups (`work/<id>/run.json`) as a deterministic ENGLISH digest: one
block per video (header + timings + flags + offenders) plus a batch table and totals line. This
is the DATA the overdub-sonnet-batch skill agent reads to write its Russian triage narrative —
the script computes, the agent narrates.

Read-only: it loads run.json if present, else builds it from the already-persisted artifacts via
runreport.build_run_report (which itself runs no model / no GPU / no network — one best-effort
ffprobe at most). A work dir with no readable run.json is a skipped ROW with a note, never a
crash; the only non-zero exit is a usage error.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\run_report.py work\\<id> [work\\<id> ...]
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\run_report.py --queue queue.txt
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub import runreport                              # noqa: E402
from overdub.config import Config                          # noqa: E402
from overdub.workdir import WorkDir                        # noqa: E402

# Same 11-char YouTube-id shape the skill / workdir.video_id use — queue URLs → work/<id>.
_YT_ID = re.compile(r"(?:v=|/shorts/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})")


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _queue_ids(path: Path) -> list[str]:
    """Parse 11-char YouTube ids from a queue file (utf-8-sig strips a PowerShell BOM; '#'
    comments and blanks skipped). Lines the regex misses are silently dropped here — this is a
    read-only digest, not the pipeline gate (the skill's step-1 gate is where an unmatched URL
    must fail loud)."""
    ids: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _YT_ID.search(line)
        if m:
            ids.append(m.group(1))
    return ids


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="run_report",
        description="Human-readable digest of per-run run.json rollups (overdub triage).")
    p.add_argument("workdirs", nargs="*", type=Path, metavar="work/<id>",
                   help="per-video work dirs")
    p.add_argument("--queue", type=Path, default=None,
                   help="queue file of URLs (ids → <work_root>/<id>)")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"),
                   help="TOML config (for work_root); built-in defaults if absent")
    args = p.parse_args(argv)

    cfg = Config.load(args.config)

    dirs: list[Path] = []
    seen: set[str] = set()

    def add(d: Path) -> None:
        key = os.path.normcase(os.path.abspath(str(d)))
        if key not in seen:
            seen.add(key)
            dirs.append(d)

    for wd in args.workdirs:
        add(wd)
    if args.queue is not None:
        if not args.queue.is_file():
            p.error(f"queue file not found: {args.queue}")
        for vid in _queue_ids(args.queue):
            add(cfg.work_root / vid)

    if not dirs:
        p.error("give at least one work/<id> dir and/or --queue FILE")

    blocks: list[str] = []
    runs: list[dict] = []
    for d in dirs:
        work = WorkDir(d)
        run = _load_json(work.root / "run.json")
        if run is None:
            run = runreport.build_run_report(work, cfg)
        if run is None:
            blocks.append(f"### {d.name}  [no run.json — skipped]\n"
                          f"- no report.json / translation.json in {d} (run the pipeline first)")
            continue
        report = _load_json(work.report)
        translation = _load_json(work.translation)
        offenders = runreport.summarize_offenders(report, translation) if report else []
        blocks.append(runreport.render_run_report(run, offenders))
        runs.append(run)

    print("\n\n".join(blocks))

    if runs:
        print("\n── batch " + "─" * 40)
        header = ("video", "title", "wall_s", "rtf", "tr", "vf", "cp", "spd_max", ">1.8", "triage")
        print(" | ".join(header))
        for r in runs:
            t = r.get("timings", {}) or {}
            sp = r.get("speed", {}) or {}
            row = (
                str(r.get("video_id")),
                (r.get("title") or "")[:24],
                str(t.get("total_wall_s", "")),
                str(t.get("rtf")),
                str((r.get("translate", {}) or {}).get("n_failed", 0)),
                str((r.get("verify", {}) or {}).get("n_flagged", 0)),
                str((r.get("completeness", {}) or {}).get("n_flagged", 0)),
                str(sp.get("max")),
                str(sp.get("n_over_1_8", 0)),
                "yes" if r.get("needs_triage") else "no",
            )
            print(" | ".join(row))
        total_wall = round(sum((r.get("timings", {}) or {}).get("total_wall_s", 0) or 0
                               for r in runs), 1)
        sum_video = sum(((r.get("timings", {}) or {}).get("video_sec") or 0) for r in runs)
        thru = f"×{sum_video / total_wall:.2f}" if total_wall > 0 else "n/a"
        n_triage = sum(1 for r in runs if r.get("needs_triage"))
        print(f"totals: wall {total_wall}s · throughput {thru} · {n_triage} need triage")

    return 0


if __name__ == "__main__":
    sys.exit(main())
