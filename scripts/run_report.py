"""Human-readable run-report digest (route A + route B morning triage).

Surfaces the per-run rollups (`work/<id>/run.json`) as a deterministic ENGLISH digest: one
block per video (header + timings + flags + offenders) plus a batch table and totals line. This
is the DATA the overdub-sonnet-batch skill agent reads to write its Russian triage narrative —
the script computes, the agent narrates.

Read-only, and thin by design: queue parsing, workdir classification and the batch-table cells
all come from overdub.runreport's shared data layer (collect_entries / batch_row /
batch_totals), so this script and the triage HTML can never again disagree about the same bytes
on disk (the queue-page merge). What is left here is the per-medium rendering: a dubbed video gets the
full block, a scouted or promoted-but-untranslated workdir gets an honest state header instead
of the old misleading "run the pipeline first" note, and an argv path with nothing to report is
a named skip, never a crash. The only non-zero exit is a usage error.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\run_report.py work\\<id> [work\\<id> ...]
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\run_report.py --queue queue.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub import runreport                              # noqa: E402
from overdub.config import Config                          # noqa: E402


def _transcript_line(e: dict) -> str:
    """The one data line under a scout/pending header: sentence count + duration. The duration
    clause is DROPPED when unknown — never rendered as "None" — and a sub-minute video reads
    "<1 min", mirroring the triage scout card. Cost is the point of both numbers: whether a
    video earns a dub is a question about length."""
    bits = [f"{e.get('n_sentences', 0)} sentences"]
    dur = e.get("duration_sec")
    if isinstance(dur, (int, float)):
        mins = int(round(dur / 60))
        bits.append(f"{mins} min" if mins else "<1 min")
    return "- " + " · ".join(bits)


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
    p.add_argument("--rebuild", action="store_true",
                   help="recompute run.json from the persisted artifacts instead of loading it "
                        "(run.json is derived data; use after a rollup schema change so older "
                        "runs gain the new fields)")
    args = p.parse_args(argv)

    cfg = Config.load(args.config)

    queue: list[str] | None = None
    if args.queue is not None:
        if not args.queue.is_file():
            p.error(f"queue file not found: {args.queue}")
        # Shared parse instead of a local copy: the old local _queue_ids did not dedup; the
        # shared one dedupes keeping first position — an improvement here (a doubled queue
        # line no longer prints the same video twice).
        queue = runreport.queue_ids(args.queue)
    if not args.workdirs and not queue:
        p.error("give at least one work/<id> dir and/or --queue FILE")

    entries, skipped = runreport.collect_entries(
        queue, args.workdirs, cfg.work_root, rebuild=args.rebuild, cfg=cfg)

    blocks: list[str] = []
    runs: list[dict] = []
    for e in entries:
        kind, summary = e["kind"], e["summary"]
        if kind == "run" and e["run"] is not None:
            blocks.append(runreport.render_run_report(e["run"], e["offenders"], summary))
            runs.append(e["run"])
        elif kind == "scout":
            # An honest state header instead of the old "run the pipeline first" note, which
            # told the operator to dub a video they had only asked to scout (the third
            # divergence the queue-page merge names). The summary IS the scout deliverable — attach it.
            block = (f"### {e['vid']}  [scouted — transcript only, no dub]\n"
                     + _transcript_line(e))
            if summary:
                block += "\n" + runreport.render_summary_block(summary)
            blocks.append(block)
        elif kind == "pending":
            block = (f"### {e['vid']}  [promoted — downloaded in full, "
                     f"translate has not started]\n" + _transcript_line(e))
            if summary:
                block += "\n" + runreport.render_summary_block(summary)
            blocks.append(block)
        else:
            # kind "run" whose rollup degraded to None (torn artifacts), or a queued id that
            # never downloaded — from_queue entries are never dropped, the queue is the
            # deliverable. Same block this script always printed for that shape.
            block = (f"### {e['vid']}  [no run.json — skipped]\n"
                     f"- no report.json / translation.json in {e['work'].root} "
                     f"(run the pipeline first)")
            if summary:
                block += "\n" + runreport.render_summary_block(summary)
            blocks.append(block)

    if blocks:
        print("\n\n".join(blocks))

    if runs:
        print("\n── batch " + "─" * 40)
        # ONE header source — runreport.BATCH_COLUMNS. No second list to drift.
        print(" | ".join(label for _key, label in runreport.BATCH_COLUMNS))
        for r in runs:
            row = runreport.batch_row(r)
            # video/title/triage are the per-medium ends of the row: this digest truncates the
            # title to 24 chars and prints yes/no where the HTML colours a cell. The ten data
            # cells between them are printed verbatim — the cross-surface contract.
            out = [row["video_id"], (row["title"] or "")[:24]]
            out += [text for _key, text in row["cells"]]
            out.append("yes" if row["needs_triage"] else "no")
            print(" | ".join(out))
        tot = runreport.batch_totals(runs)
        print(f"totals: wall {tot['total_wall']}s · throughput {tot['throughput']}"
              f" · {tot['n_triage']} need triage")

    if skipped:
        # argv paths that are neither a run nor a transcript (typo'd path / audio-only fetch):
        # named, never silently dropped — the same "skipped" semantics as the queue page.
        print(f"\nskipped (nothing to report): {', '.join(skipped)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
