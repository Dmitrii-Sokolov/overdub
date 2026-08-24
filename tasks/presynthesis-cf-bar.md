# Pre-synthesis bar on the compression factor — parked

## Goal + AC

PARKED 2026-07-27: a gate that flags units whose compression factor will exceed the 1.8 bar
BEFORE synthesis. **Trigger to reopen: a batch that actually produces units over the bar.**
There is currently nothing to catch: the two shipped-config batches top out at cf 1.22 and
`work-silero-v5` at 1.790 — ZERO units at or over 1.8.

## Plan

(none — parked; the constraints below are what a revival must not re-derive)

## State

Parked. Imported from PLAN.md at the 2026-08-24 agent-docs migration. Do not build on the
numbers above without re-measuring — they are the reason the task is parked, not a design input.

## Findings

Build constraints kept so a revival does not re-derive them:

- Merging cannot fix an offender anyway — every candidate needed a merged span of 20.1-36.6 s
  against `group_span_max` 20.0, so the lever is the CAP.
- A constant-rate predictor is too coarse to gate on: worst-case predicted/actual 0.715 forces a
  1.29 threshold → ~8.4 flags per 24-video batch against ~0.65 real ones — the bar mostly flags
  its own error.
- Dropping a unit is forbidden by four never-drop invariants; merging self-heals (units keyed by
  id-tuple); and `done()` compares the manifest's own units rather than a fresh partition, so a
  regroup returns True and never applies without a partition check.
