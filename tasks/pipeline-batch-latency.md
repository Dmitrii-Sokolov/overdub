# Pipeline the batch instead of running it stage by stage

## Goal + AC

Shorten the time until the FIRST video reaches its post-translate tail, so that tail overlaps the
translation of the next video. **The objective is a LATENCY, not a stage speed-up** (user,
2026-08-06): no stage on this list is being optimized — translate is the longest and is
deliberately out of scope, and the rest are near their practical ceilings.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

What is left, in order:

- [ ] **`mux` — the next lever, and nobody has ever looked at it.** 19.3% of machine time on the
  baseline, more than download and transcribe together, pure ffmpeg and disk. Now that the overlap
  is taken it is what binds. Profile before optimising: nothing is known about where its time goes.
- [ ] **A clean end-to-end batch figure.** Every phase has been measured on its own; the batch
  total has not, because transcribe's wall varies 35× on identical work
  (tasks/transcribe-wall-variance.md) and pollutes any total it appears in. That task gates this
  step.
- [ ] **Acceptance — the artifacts must not move.** Never run, and its original phrasing is now
  broken: it assumed Parakeet was deterministic, and it is not (INBOX 2026-08-07). Re-phrase
  before running it. Bit-stability has to be established per artifact first — `source_bed.wav`
  has never been shown to be stable either — or the comparison reads noise as a regression.
- [ ] **Per-video dispatch of the TRANSLATORS** — the trigger's other half, deliberately not
  built. The wave ends on its slowest agent, which starts when ITS transcript exists either way,
  so the win is bounded by the spread of the transcribe phase (151.4 s over 10 videos,
  2026-08-07) and not by the wave. It also cannot use `Workflow` as it stands: the whole queue
  goes in one call by contract (`docs/queue-contract.md` §6). Do the arithmetic on a real batch
  before building it.
- [ ] **A GPU mutex and LONGEST-first ordering — PARTS of a future scheduler, not steps toward
  one.** No two GPU stages can meet inside one process today, so a mutex would guard nothing; the
  live hazard is two PROCESSES, which an in-process lock cannot see. Ordering is inert for the
  same structural reason: every sweep stage is a full barrier. When a scheduler does arrive, the
  ordering argument is transcribe at RTF 0.0103 against a tail at 0.0777 (2026-08-07) — 7.5×
  apart — so the long pole goes first. Check rather than assume that the tail scales with
  duration per video, and that a long video's CHUNKED translation is not itself the slowest agent.

## State

Not started under this file. Imported from PLAN.md at the 2026-08-24 agent-docs migration.
The overlap half already shipped (see Findings); what binds now is mux, gated behind the
transcribe-wall variance for any end-to-end figure.

## Findings

**Standing constraints for any work here live in `overdub/CLAUDE.md`** (GPU co-residency,
verify_roundtrip as a third consumer, the `timings.json` read-modify-write hazard, and the two
rules about summing/attributing batch numbers). Read them before touching the sweep.

**What shipped** (git history + DECISIONS 2026-08-06/07 carry the numbers): the instrument
(`spans[<stage>]`, `work/runs.jsonl`), the baseline, the concurrent download pre-pass, `separate`
moved into the translate wave, and `scripts/drain.py` — the per-video trigger, which needed no
pipeline change at all. All confirmed on real media; the drain measured ×1.40 on the wave+tail
phase (10 videos, 2026-08-07) with 10 drained, 0 failed, 0 pending. **The ~1.7× projection this
item opened with is withdrawn** — it came off a batch where the tail fitted inside the wave, and
on the 10-video baseline the inequality runs the other way.
