# Next-batch watchlist

## Goal + AC

Standing observations to check when the next ordinary batch passes by — they are not gates and
none blocks a run. The task closes when each row has been looked at once on a real batch (and
re-opens with new rows as triage adds them). AC: the list below, each row observed or retired.

## Plan

- [ ] `--repair-asr auto`'s fixture recall (5/12) and the `RyvXxApfHkk#11` 246-vs-35.9 ch/s
  discrepancy are unreconciled (DECISIONS 2026-07-20, provenance).
- [ ] Listen to a repaired unit in a finished MKV once — repair moves a TTS unit boundary, so
  `atempo` on that unit moves too; a property of the step, not of the video.
- [ ] The `Tu2cCEMwvHI` 116.7 s download outlier is undiagnosed (6-13 s for the rest of that
  queue).
- [ ] On a route-B run check `needs_triage` — after the 2026-07-27 demotion the two
  shipped-config batches re-score to 0/7 and 1/5, so the next batch is the first one whose rate
  is measured rather than re-scored; if it drifts back toward N/N, look at what is padding it
  before adding a detector. (First data point: the 2026-08-04 @9fingergames batch measured
  2 of 10 among videos WITH speech — the padding was the no-speech class; INBOX carries the
  entry.)
- [ ] The `- pronounce:` line (ranged 9..248 per video; a video near 200 names the tokens the
  dictionary still lacks).
- [ ] **Uncovered speech: watch the `gap` column.** The worker stamps `holes` /
  `hole_words_recovered` / `holes_unrecovered`, `run.json` carries them, an unrecovered span sets
  `needs_triage` (2026-08-06). What no one has is a rate: every hole measured on the 165-video
  corpus was recovered on the second read, so `holes_unrecovered > 0` has **never actually fired
  on real media** and its precision is unknown. If it stays at zero across a few batches, that is
  the answer, not a reason to loosen it.
- [ ] **`translate-batch` unexercised paths** (first real use 2026-07-28 held: markers 3.5 s
  apart, 782/782 ids, `src` on 100% of records, step 2 cost the orchestrator 1428 chars): (i) the
  projected ~5.6k tokens/video is a projection, not measured — at 4 videos steps 1/3/4 and manual
  debugging dominate; (ii) the `failed` / `incomplete` / second-wave branches have never
  executed. Fold both into the next ordinary batch rather than staging a run for them.

## State

Open, passive — worked only when a batch runs. Imported from PLAN.md at the 2026-08-24
agent-docs migration.
