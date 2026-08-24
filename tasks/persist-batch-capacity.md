# Persist the batch capacity measurement

## Goal + AC

The audio ÷ machine-time ratio route B's step 4 computes survives the session: append-only
`work/capacity.jsonl` written by step 4 — queue ids, `audio_s`, the four step seconds, and a
config fingerprint. Today it survives only in a chat message (added 2026-08-02: 2 videos, digest
said ×4.13, the machine did ×2.56) and every night is planned off a single sample.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] `work/capacity.jsonl`, written by route-B step 4.
- [ ] Include the config fingerprint — it is load-bearing: the point is comparing nights, and a
  series that silently spans an engine or grouping change is exactly the trap `run.json` is
  already in (no engine field in any of them — 193 checked 2026-08-02 — so its own provenance is
  only recoverable from git history).
- [ ] Do NOT fold it into `run.json` — that file is per-video and this quantity is per-batch
  (`run.json` carries no timestamp and `timings.json` has no batch level).

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration.
