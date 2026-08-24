# Promotion C→B, confirmed once

## Goal + AC

One scout→dub promotion is confirmed end to end on real media. Promotion = the SAME videos going
through route C and then route B: scout writes `sentences.json` and only `source.wav`, the human
trims the queue, the dub run then has to (i) fast-skip `transcribe` — the whole economic point,
or scouting pays for large-v3 twice — and (ii) re-run `download`, because the final MKV needs
`source.mkv` and scout never wrote one.
AC candidate (from PLAN 2026-08-24): scout 2 videos, dub the same 2, then read their `run.json` —
`timings.stages.transcribe` near zero and `download` clearly non-zero is the pass. Freeze at
pickup.

## Plan

- [ ] Scout a 2-video queue.
- [ ] Dub the same 2 videos through route B.
- [ ] Read both `run.json`: transcribe ≈ 0, download > 0 → pass.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. Every run so far has
been route C **or** route B, never C-then-B on one video, so neither half is observed. Ranked
high because both daily routes already depend on it working and nobody has looked.
