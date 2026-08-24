# Re-site the chunked-translate threshold on characters

## Goal + AC

The route-B "send straight to the chunked translator" threshold is keyed on what actually binds
the per-video agent — OUTPUT VOLUME in characters — instead of sentence count. **The current
threshold is measured on the WRONG GRAIN (2026-08-05):** ~2000 SENTENCES, off a count over 227
drafts. A transcript of long sentences hits the wall sooner than one of clipped speech at the
same count, and the threshold as written cannot see the difference.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] Sum `len(text)` over `sentences.json` per video across the draft corpus, split by the same
  outcome, and quote whichever grain separates the two classes better.
- [ ] Decide what to do about the unmeasurable failure rate (see Findings) — either accept the
  floor and say so, or persist the `INCOMPLETE` fraction somewhere first.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. Also stale against
the dual-form markup (tasks/dual-form-seam-cost.md): the rule grows output volume, so the
threshold moves again once that is measured.

## Findings

The evidence behind the current ~2000: one partial in the corpus (`477qF6QNSvc`, 1550/2514),
zero partial at or below 2004, two failures among the four videos above it. What must NOT be
carried over is the 2-in-4 rate — it is a FLOOR, because a video that failed once and passed on
a retry leaves a complete draft behind and reads as a clean success; recovering the real rate
needs a record the pipeline does not keep today (the draft is overwritten).

**And 2000 is not a failure threshold** — the outcomes interleave (2259 failed, 2379 passed,
2514 failed, 2829 passed) and the largest transcript in the corpus is a single-agent success. It
is a "stop paying for the attempt" line resting on the clean lower half. Anything quoting it as
"videos over 2000 sentences fail" is wrong.
