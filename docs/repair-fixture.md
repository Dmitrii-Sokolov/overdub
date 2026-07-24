# The `--repair-asr` golden fixture

A reproducible real-media regression test for isolated-window ASR repair. It exists because the
window-clipping and timestamp-rebasing paths are the one part of `overdub/repair.py` that **no unit
test executes** — every test injects the ASR seam. This is how you exercise the real thing.

Written 2026-07-20, after the first run. Findings from that run: DECISIONS 2026-07-20.

## Why it is "golden"

In July 2026 a human manually repaired defect windows across 6 videos using exactly the method
`--repair-asr` now automates. Both sides survive in `work/<id>/`:

| file | what it is |
|---|---|
| `_pre-repair-sentences.json` | the DEFECTIVE transcript — the input |
| `sentences.json` | the human-verified repaired transcript — the comparison |

(Since 2026-07-21 a repair also writes `_pre-repair-translation.json` — the preserved
source-anomaly worklist, overwritten per repair. It is NOT part of the fixture pairs.)

The 6 ids: `2YCaBqP8muw`, `DmgujoZ1mmk`, `RyvXxApfHkk`, `W4Ua6XFfX9w`, `W5cga7xipRI`, `ytEN_iAk09c`.
All six `source.wav` are present, ~75 MB total.

## It is a signal, not an oracle — read this before scoring anything

Three separate reasons the human side is not ground truth:

1. **It contains at least one error.** At `DmgujoZ1mmk` 2:42.90 the human wrote `you want it to use`;
   the speaker says `you wanted to use`, confirmed by ear 2026-07-20. The automation "differed" and
   was RIGHT. **"Differs from the human" is not a synonym for "wrong."**
2. **One human repair was a deliberate override, not a mechanical merge.** `Anthropics Cloud Models`
   → `Anthropic's Claude models` (DECISIONS 2026-07-19). The automation is bound by
   *delete, do not invent*, so it must NOT reproduce this. **A 7/7 match is a red flag, not a win** —
   it would mean the automation is fabricating text.
3. **The provenance has two unreconciled discrepancies.** DECISIONS records `RyvXxApfHkk#11` at
   246 ch/s but the backup measures 35.9 (below the post-repair batch max, so the backup may not be
   the true pre-repair state), and "7 repairs" is recorded against 12 distinct on-disk diff blocks.

Consequence: use it to **detect changes in behaviour** between two versions of the code, not to
compute an absolute correctness score.

## Running it

**Never write into `work/`.** It holds irreplaceable baselines, several already lost to a disk
cleanup. Copy out, run against the copy.

1. Build a scratch work root: one dir per id, containing that video's `source.wav` plus its
   `_pre-repair-sentences.json` **renamed to** `sentences.json`.
2. Point the pipeline at it with a scratch TOML overriding `work_root`.
3. Dry run first — confirms the right dirs and that nothing triggers a download:
   `--repair-asr auto --repair-dry-run`
4. Real pass: `--repair-asr auto`
5. Diff each resulting `sentences.json` against `work/<id>/sentences.json` (read-only).

Cost, measured 2026-07-20: 5 windows × 2 readings = 10 large-v3 passes in ~26 s wall, model loaded
once for the sweep. The "~1 minute per window" figure in DECISIONS 2026-07-19 describes the old
manual script, which paid a fresh model load per invocation.

**The baseline below is conditional on a decode config.** It was measured at
`whisper_model = "large-v3"`, `whisper_compute_type = "float16"`, `whisper_beam_size = 5`,
`whisper_condition_on_previous = true`. Since 2026-07-22 the beam is a config key
(`whisper_beam_size`) shared by the stage and the repair window, so a fixture run under a
different decode config measures a **different thing**: its window count, acceptance rate and the
"5 of 12" recall figure are not comparable to the numbers here. Re-running the fixture is part of
adopting any transcribe lever — record the decode config next to the result.

That conditionality is now enforced rather than trusted: `--repair-asr` reads the `asr_key`
stamped in each workdir's `timings.json` and REFUSES a video whose model, compute type or beam
differs from the current config (`repair.check_decode_config`), because a window decoded at
another width splices in a sentence of a different kind from its neighbours. The 6 preserved
fixture workdirs predate the stamp and are accepted unchanged. After a real pass the stamp reads
`cond=mixed` with an `asr_repair_windows` count — the spliced windows are the clipped `cond=False`
reading, so the transcript is no longer one uniform decode and the file says so.

## Baseline to compare against (run of 2026-07-20)

- 5 windows derived across 4 videos; all 5 accepted; gate agreed 5/5; texts byte-identical across
  two independent runs (good stability evidence).
- 2 windows reproduced the human result exactly (`W5cga7xipRI` 22-24, `ytEN_iAk09c` 6-8).
- 1 differed only in sentence split, same words (`2YCaBqP8muw` 16-18).
- 1 confirmed **regression**: `2YCaBqP8muw` 42-45 turned `Claude` into `Cloud`; the word is
  enunciated clearly, so this is context loss on clean speech. Both readings agreed, so the gate
  could not object.
- 1 confirmed **improvement** over the human: `DmgujoZ1mmk` 31-33 (see above).
- 2 videos derived ZERO windows (`RyvXxApfHkk`, `W4Ua6XFfX9w`) — both are the detector-blind class
  DECISIONS 2026-07-19 predicted, and both printed as clean. Recall over known regions: **5 of 12**,
  soft for the reasons above.
- Timestamps: monotone in all 6 files, zero overlaps, zero inversions, max delta vs human inside a
  repaired window 0.71 s. Repaired first sentences start exactly `CLIP_PAD_SEC` (0.25 s) early,
  systematically and harmlessly.

## What it still cannot tell you

Whether the dub SOUNDS right. Repair changes sentence boundaries, so it changes TTS unit boundaries
and the `atempo` of the affected unit. That only shows up after `repair → resume` on a real batch.
