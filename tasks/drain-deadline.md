# `drain.py` leaves nothing ready behind and announces its exit

## Goal + AC

`scripts/drain.py` never exits with videos `pending` that were ready on disk, `--timeout` bounds
what it says it bounds, and the orchestrator learns the drain is over. AC: not frozen — fix at
pickup.

## Plan

- [ ] Deadline as "no progress for N s" rather than wall clock from start, or a final sweep
  after the deadline.
- [ ] Run it as a harness-tracked background command so its exit is announced (route-B skill).

## State

Not started. Routed from INBOX at triage 2026-10-27.

## Findings

**Measured on the 25-video queue of 2026-10-25** (20 translated, 5 already built): started
21:38 with `--timeout 3600`, last log write 01:04 — 3.4 h. It exited `18 drained, 0 failed,
7 pending` although all 7 were ready well before it quit: 3 per-video drafts complete at
21:52-21:54 (full id coverage, `build_translation.py` exits 0 on them), 4 chunked videos joined
22:03-22:19.

Mechanism: the loop is sweeps over the queue, `drain_one` blocks for a video's whole tail, and
the deadline is checked only BETWEEN sweeps. Each of the 7 was unready when the final sweep
reached it (early in queue order), became ready while the sweep was inside later tails, and the
deadline ended the loop before another sweep.

Cost: the pipeline sat idle 01:04 -> 06:40 until the step-3 resume was started by hand. The
process was a `Start-Process` child with no completion notification, so nothing told the
orchestrator it was over.
