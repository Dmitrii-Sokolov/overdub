# Sentence rebuild loses endings — re-join at rebuild

## Goal + AC

The sentence rebuild stops cutting sentences in half where the ASR emits no terminal
punctuation. The defect is OURS, not whisper's: only re-joining at rebuild can fix it — repair
cannot help by construction. AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at
pickup.

## Plan

- [ ] Reproduce on the measured corpus (live Q&A: `2qrzI8YCVgI`, `Tu2cCEMwvHI`).
- [ ] Fix at `stages/transcribe` resegmentation.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration.

## Findings

166 of 388 source anomalies are `truncated`, clustered in live Q&A where whisper emits no
terminal punctuation. Same root, second symptom: `aVwxzDHniEw#67` = "is the derivative of a
Bezier curve?" in a 1.06 s slot — one sentence cut in half by the rebuild, and
`rate_implausible` does not fire (36 ch/s against a 40 bound). Distinct from the 143 `garbled` /
60 `dup_neighbour`, which really are whisper's.
