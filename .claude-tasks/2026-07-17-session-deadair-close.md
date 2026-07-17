# Session handoff — 2026-07-17: dead-air closed by ear, roadmap reset

Compact conspectus; details live in the four artifacts (DECISIONS: four 2026-07-17
entries, CHANGELOG: 2026-07-17 closure entry, PLAN: reprioritized roadmap). Supersedes
the "Next steps" section of 2026-07-16-session-f5-deadair-handoff.md.

## What this session shipped

- `053b29a` fix: f5_speed_ceil 1.6 → 1.1 + `similarity_threshold_compressed` 0.9 via ONE
  shared `unit_sim_threshold()` (synthesize reseed loop + verify). Lesson behind it: ASR sim
  measures char overlap, NOT word survival — F5 native compression ≥~1.3 drops words while
  atempo never does.
- `87c31d9` feat: `_BED_GAIN` −6 → 0 dB, `dub_mix` default → "bed"; `.venv-demucs` gitignored.
- `e010944` chore: base `similarity_threshold` 0.8 → 0.9 (units are long joined strings; the
  17:02 defect scored 0.836 and passed 0.8; both runs min ≥ 0.926).
- `4a57490`/`ec1468b`/`58831e3` docs/plan: dead-air closure + reprioritization.

## Ear verdicts (user, binding)

- L3 bed on the music-heavy check: "работает идеально".
- 17:02 ex-cutoff after the ceil fix: "исправлено сносно".
- Residual artifacts "примерно соответствуют необычным интонациям и запинкам оригинала" →
  dead-air problem group CLOSED.

## Config state after this session

`f5_speed_ceil=1.1`, `similarity_threshold=0.9`, `similarity_threshold_compressed=0.9`,
`dub_mix="bed"` (default), `_BED_GAIN=1.0` (0 dB). tts_engine="f5" (since 2026-07-16).

## Decided positions from the Q&A (don't re-litigate)

- "Measure silence instead of predicting duration" — REJECTED: cutoffs leave no silence to
  measure (compressed canvas is fully voiced, words just missing); atempo already derives
  from measured samples; prediction (err ≤1.5%) only picks the speed knob pre-synthesis.
- Babble detector ≠ bad-reference problem: it is verify's blind spot (garbage scored 0.93,
  id101 scored 1.0 ear-bad). Urgency dropped post-grouping; value activates at batch scale.
- Multi-speaker: full diarization out of scope; if ever needed, the v1 shape is a
  violation detector (ECAPA embeddings vs dominant-voice centroid → report flag), ~1 d.
  ESpeech RU cloning (bake-off #2) would enable true multi-voice later — separate project.
- Phase 4 (Arc B390): deferred indefinitely. Silero is the only CPU-viable TTS
  (43 s / 39-min video on CPU vs F5 RTF 0.39 on the 4080); F5-on-XPU = unproven 2-5 d spike.
  ROI questionable while the 4080 clears the x5 budget (~3.8×).
- UTMOS: high cost / low effect until batch stats prove the duration heuristic insufficient.

## Effort estimates (from this session's discussion)

proper nouns 1-2 d · batch queue 0.5-1 d · stop switch hours · duration heuristic ~1 d ·
UTMOS +1-2 d (deferred) · cloud translate ~1 d (deferred) · gender narrator: hours of code +
unbounded PD-reference search (deferred) · multi-speaker detector ~1 d (deferred) ·
Arc B390 3-7 d (deferred) · sim re-tune: closed (0.9).

## Operational map

- Workdirs: `work-exp/f5-control/x7DfiXqSEdM/` — output.mkv IS the current state (bed@0dB,
  ceil 1.1); the old `output_{replace,duck,bed}.mkv` copies are STALE, ignore them.
  `work-exp/bed-music/tJP6SKfo49c/` — 3.6-min music-heavy bed check (stem −29 dBFS,
  active 99%), ran turn-key on the flipped defaults incl. auto separate stage.
  `work/*` = read-only Silero baselines.
- Venvs unchanged: `.venv-asr` (pipeline) / `.venv-f5tts` (F5 worker) / `.venv-demucs`
  (separate). Run: `.venv-asr\Scripts\python.exe -X utf8 -m overdub <url> --config <toml>`.
- Next task (roadmap 1): proper nouns — start by collecting the worst-sim records from both
  workdirs' report.json as the test corpus; candidate cheap path: ask Qwen for Cyrillic
  pronunciations inline during translate + dictionary overlay + per-run cache.
