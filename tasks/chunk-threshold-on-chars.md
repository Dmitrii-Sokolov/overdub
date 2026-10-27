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

**The stall signature, 2026-08-04** (5-video WL batch): `7xTGNNLPyMI` (2258 sentences) stopped at
1200 records and `477qF6QNSvc` (2514) at 1550 in BOTH waves; in wave 2 each wrote its
`translate.started` marker and produced zero new records — the drafts were byte-for-byte the
wave-1 partials. Both stalls near a round number, second attempt did no work: reads as a
turn/tool-use budget rather than a context overflow, unconfirmed. Same run: `kfM-yu0iQBk`
returned `OK` with a draft one id short (2828 of 2829) — an agent's status line is uncorrelated
with completeness; `build_translation.py`'s hard exit is the guardrail and must not be relaxed.

**A second failure signature, far below any threshold, 2026-09-14:** 4 of 38 videos failed with
`API Error: Claude's response exceeded the 64000 output token maximum` and wrote NO draft —
`Fp-4GmRpnDI` (375 sentences), `WFzoiq84AdY` (299), `lMjnjDiN3vE` (298), `ERg0j1fSyJE` (212). All
under `DEFAULT_CHUNK` (400, `build_translation.py`), so `--plan` with no `--chunk` gives one chunk
covering the whole video and fixes nothing. Not monotonic: `vcgr6oXBihs` (322) passed as a single
agent. Likely carriers: verbose `src` anomaly notes on garbled ASR — output volume, not sentence
count. Fixed ad hoc with `--chunk 100` on those four (12 chunks, all succeeded). The open choice:
drop the `--plan` default well below 400, or make the chunked path the RETRY of a hard-errored
single-agent attempt instead of a size guess made in advance.
