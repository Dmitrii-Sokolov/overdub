# Transcribe's wall varies 35× on identical work

## Goal + AC

The variance is explained (or bounded) so transcribe figures become quotable again. Until then
**no transcribe wall figure is quotable, and the closed 2026-07-24 transcribe-speed axis must
not be re-measured against** — that closure assumed a stable wall. This also gates the clean
end-to-end batch figure in tasks/pipeline-batch-latency.md.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] Start a clean series from a fresh workdir — the spans for the diagnostic videos are
  contaminated by the two `--force` re-runs.
- [ ] A repeat-decode harness answers this AND the Parakeet-determinism question (INBOX) for one
  price — run them together, behind `scripts/host_guard.py`.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. 5-6% of machine time,
so it changes no decision — but it makes any transcribe figure unquotable until understood, and
it is why the 2026-08-07 end-to-end comparison was scoped to the wave and the tail.

## Findings

Measured 2026-08-07: `IOMCDpzpNaQ` (617 s of audio) recorded `work_sec` of **6.8 s** (as the
10th video of a warm 10-video sweep), then **238.2 s**, **32.7 s** and **22.4 s** on three later
decodes of the same file. At batch level the same day: transcribe summed 151.2 s on the baseline
and 539.3 s on a re-run of the same ten videos.

Ruled OUT: a busy card (clocks and power measured healthy under load, DECISIONS 2026-08-07) and
a changed input (`vad_speech_sec` identical to 0.1 s on all ten, so the VAD saw the same audio).
Partial candidate: first-use CUDA kernel compilation, which a warm sweep amortises and an
isolated run pays in full — but it does not explain the FIRST video of the re-run being slow
too.
