# Promotion into route B, confirmed once

## Goal + AC

One transcript→dub promotion is confirmed end to end on real media. Promotion = the SAME videos
going through `--transcribe-only` (route E's fetch step) and then route B: the transcript pass
writes `sentences.json` and only `source.wav`, the human trims the queue, the dub run then has to
(i) fast-skip `transcribe` — the whole economic point, or the pre-pass pays for transcription
twice — and (ii) re-run `download`, because the final MKV needs `source.mkv` and the audio-only
pass never wrote one.
AC candidate (from PLAN 2026-08-24): transcribe 2 videos audio-only, dub the same 2, then read
their `run.json` — `timings.stages.transcribe` near zero and `download` clearly non-zero is the
pass. Freeze at pickup.

## Plan

- [ ] Run a 2-video queue through `--transcribe-only`.
- [ ] Dub the same 2 videos through route B.
- [ ] Read both `run.json`: transcribe ≈ 0, download > 0 → pass.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration; reworded 2026-08-24
when the scout route was deleted — the mechanics under test (audio-only fetch → full dub) are
route E's promotion path and did not change. Every run so far has exercised one half or the
other, never both on one video, so neither half is observed. Ranked high because both routes
already depend on it working and nobody has looked.
