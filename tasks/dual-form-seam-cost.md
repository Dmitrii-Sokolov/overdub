# Dual-form seam cost — measure, and roll back if too high

## Goal + AC

**The dual-form seam is ON TRIAL.** Shipped 2026-08-11 (DECISIONS): the translator writes
`[[written|spoken]]`, so it emits both forms and the seam's output volume grows. Take the seam's
wall and its char volume on the first real batch under the rule and compare against the
pre-08-11 runs.

**The decision rule is set in advance, so the measurement cannot be argued with after the fact:
if translate is noticeably more expensive or slower, try something else, and the FIRST thing to
try is a rollback.** Reverting is cheap by construction — the markup lives only in the draft and
`translation.json` never changed shape, so it is one revert of the contract + prompts + the
resolver, and nothing downstream knows the difference. The other direction is
tasks/cmudict-transliteration.md, which would let the translator mark far less instead of not at
all.

## Plan

- [ ] First real batch under the rule: record the translate wall and the draft char volume.
- [ ] Compare against pre-08-11 runs; apply the pre-set decision rule.

## State

Not started — waiting on the next ordinary batch. Imported from PLAN.md at the 2026-08-24
agent-docs migration. The only reading so far is one 164-sentence video — translate 7.8 min of a
10.5 min run, 154 marked spans, 469 s wave (2026-08-11) — which is not a baseline for anything:
no full batch has run under the rule.

## Findings

Two things this measurement must not conflate. Output VOLUME is what binds the chunked
translator, not sentence count — so the 2000-sentence chunking threshold is also stale until
this is read (tasks/chunk-threshold-on-chars.md). And the 08-11 seam figures were taken with
`translate.started` present; a video whose wave was not timed reports the OLD meaning of
`total_wall_s` and is not comparable (`overdub/CLAUDE.md`, total_wall_s scope).
