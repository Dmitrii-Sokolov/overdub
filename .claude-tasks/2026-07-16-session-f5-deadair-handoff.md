# Session handoff — 2026-07-16: F5Engine integration + dead-air elimination

Full-context conspectus for the next agent. Everything below is committed (through
`03fbf5a` + one DECISIONS/INBOX/PLAN docs commit after it). Read together with
`.claude/PLAN.md` (open work), `.claude/DECISIONS.md` (four new 2026-07-16 entries),
`.claude/CHANGELOG.md` (two new entries + Phase 3 closure).

## What this session shipped (two feature arcs, both ultracode: panel → impl → adversarial review)

### Arc 1: F5/ESpeech is now the production TTS engine (Phase 3 CLOSED)
- `overdub/tts/f5.py` — F5Engine adapter; spawns a persistent worker in `.venv-f5tts`
  (torch 2.8; the pipeline venv `.venv-asr` is torch 2.11 — MERGING THEM IS DEAD, measured:
  numpy downgrade + ~110 packages + torchcodec ABI risk). JSONL over stdio; worker does
  fd-level `dup2(2,1)` BEFORE heavy imports (tqdm/banners would corrupt the protocol);
  reader-thread + Queue timeouts (240 s startup / 120 s request, constants); id-echo;
  respawn-once per request; 3 consecutive failures (transport OR ok:false — sticky CUDA
  context) → TtsFatalError escapes the per-segment catch and kills the stage loudly.
- `overdub/tts/f5_worker.py` — standalone script, .venv-f5tts deps only, RUAccent turbo3.1
  + token_type_ids ONNX shim inside; handshake returns sample_rate/ref_sec/ref_bytes;
  reply returns speed_eff (F5 forces local_speed 0.3 for gen texts <10 UTF-8 bytes).
- Reseed-retry lives in SYNTHESIZE (not verify): in-stage whisper-small round-trip via the
  shared `asr.roundtrip_similarity` (ONE function, verify uses the same — sims can never
  drift); < cfg.similarity_threshold → seeds tts_seed+1..+tts_max_retries, keep-best.
  Rationale: manifest stays single-writer; assemble derives atempo from manifest samples.
- Silero remains the fallback engine (`tts_engine = "silero"`), byte-identical Phase-1 path.
- Default flipped: `tts_engine = "f5"` in config.py + overdub.toml (user ear check passed).
- Phase-3 control (39-min x7DfiXqSEdM, F5 vs Silero baseline): flags 0 vs 1, sim 0.9943 vs
  0.986, atempo ×1.014 vs ×1.018. RTF gate missed (synth+verify ×0.65 vs ≤0.5 target —
  thermal; cold bake-off was 0.39); x5 throughput budget still cleared ~3.8×.

### Arc 2: dead-air elimination (user's top priority after the ear check)
Measured cause (control video): 665 s silence = 607 s RU-underfill (fast ESpeech narrator
ends each sentence before the EN span ends; dub buffer is digital zero) + 68 s real gaps
(median 0.14 s). NOT a timing bug. Three composable layers:
- **L1 slot-fill native speed** — `plan_speed()` in `overdub/tts/f5.py` (pure, tested):
  stretch to the SOURCE SPAN (floor 0.75×base, set by a pre-registered bench rule; canvas
  formula `out ≈ ref_sec·gen_bytes/ref_bytes/speed`, raw pre-accent bytes both sides,
  measured error ≤1.5% incl. group-shaped texts), neutral when the free gap absorbs the
  spill, native-compress ≤ceil 1.6 before atempo. Caps are MULTIPLIERS of f5_speed; both
  are in synth_key.
- **L2 render units** — `build_units()` in `overdub/stages/synthesize.py`: adjacent
  sentences group when gap ≤ cfg.group_gap_max (0.4 s), span ≤12 s, joined ≤300 chars;
  empty-text singletons break chains; gap_max ≤ 0 disables. ONE wav per unit at
  `seg_wav(first_id)`. Manifest v3: doc key `"units"` (entries carry ids/target_sec/
  max_sec/speed/seed/attempts/synth_sim), `units_of()` adapts legacy "segments" docs as
  singleton units. Report records stay PER SENTENCE id (contiguity guard) with group_id.
  verify's reference text joins from CURRENT translation.json (stale-translation net).
- **L3 dub_mix knob** (`replace|duck|bed`, default replace) — mixing in MUX, numpy at 48 k
  stereo: duck = sample-exact envelope (−15 dB `_DUCK_GAIN`, ramps 50/300 ms, intervals =
  unit spans EXTENDED to placed audio, merged <1 s); bed = htdemucs no-vocals at −6 dB via
  the new `separate` stage (CLI subprocess in `.venv-demucs`, 45 s for 39 min, artifact
  `source_bed.wav`); ALL modes RMS-align dub loudness to the original ±6 dB (was +4.0 dB).
  Empty/failed units deliberately NOT ducked (honest EN fallback).
- **Self-healing done() chain**: verify/assemble gate on synth_key AND units_key (content
  fingerprint — catches same-key --force resynth) stamped in report.json; mux gates on
  dub_mix/synth_key stamps + make-style mtime deps (dub_ru.wav / source_bed.wav newer than
  output.mkv → re-mux). Discipline: ARTIFACT flips before STAMP everywhere (review: the
  reverse turns a failed os.replace into permanently-served stale audio). Flipping dub_mix
  in the TOML re-runs exactly mux. synthesize.done() stays WARN-only on key change
  (auto-resynth would surprise; use --force --only synthesize).
- Control result (L1+L2): in-span silence 607→204 s (−66%), 315 sentences → 256 units,
  0 flags, 0 retries, atempo UNUSED (0 sped), unit sim mean 0.9939, synth 996 s (was 1409 —
  fewer calls). 242 units stretched, 123 at floor 0.75, 9 compressed.

## Ear verdicts (user, binding)
Round 1 (engine): approved → default F5. id101 "Хорошо." (ultra-short) bad → drove dead-air
priority. Round 2 (mix outputs, `work-exp/f5-control/x7DfiXqSEdM/output_{replace,duck,bed}.mkv`):
- **"В целом ощутимо лучше"** — the dead-air mechanism is validated.
- id101 inside its group: PERFECT (grouping = the structural ultra-short fix, ear-confirmed).
- **DEFECT @17:02**: unit [135,136,137] — 3 short sentences, EN span 2.76 s, RU ~4 s →
  native compression ×1.327 → MID-WORD CUTOFF; synth_sim 0.8361 scraped past 0.8, no retry.
  Lesson: atempo compresses uniformly and never drops words; F5 native compression ≥~1.3
  DOES. The bake-off "×1.6 at ≤0.022 sim" measured ASR similarity, not word survival.
- Duck −15 dB too shallow (EN interferes). Bed inapplicable on this speech-only source
  (no music → no-vocals stem ≈ silence → dead air returns) — re-check on music-heavy video.

## Next steps (PLAN roadmap item 1, exact order)
1. `f5_speed_ceil` → ~1.0–1.15 (compression back to atempo) + stricter sim gate for
   compressed units (e.g. speed>1.15 → require ≥0.9 or retry/flag). Resynth control
   (--force --only synthesize, ~17 min), point re-listen 17:00–17:05.
2. Duck depth: `_DUCK_GAIN` in mux.py → −22..−25 dB; re-mux (seconds), re-listen.
3. Bed on a music-heavy video; likely production shape = bed-RMS census → auto duck-fallback.
4. Flip dub_mix default (own commit). Then roadmap item 2: proper nouns.

## Operational map (for whoever picks this up)
- venvs: `.venv-asr` (pipeline, faster-whisper, Silero), `.venv-f5tts` (F5 worker),
  `.venv-demucs` (separate stage). NEVER merge. Run pipeline with `python -X utf8 -m overdub`.
- Experiment configs + workdirs (gitignored): `work-exp/f5-smoke.toml` (50-sentence sample,
  4szRHy_CT7s), `work-exp/f5-control.toml` (39-min x7DfiXqSEdM; currently dub_mix="bed" —
  set the mode you need), `work-exp/f5-retrytest.toml`, `work-exp/silero-regress.toml`.
  Baselines `work/4szRHy_CT7s`, `work/x7DfiXqSEdM` are READ-ONLY Silero references.
- Benches: `work-exp/stretch-bench/` (12 single + 12 group wavs, speeds 0.7–1.0, sims in
  session log; scripts in the session scratchpad — re-create if needed, ~40 lines each).
- Key metrics live in each workdir's report.json (`assemble.in_span_silence_sec`,
  per-record combined_factor/tts_speed/group_id) and segments/manifest.json (units).
- Known deferred items: INBOX sections "Dead-air review deferrals" + "Ear verdict" (unit
  sim threshold re-tune, --repair grain, keep-length prompt ↔ stretch interaction,
  translate «причина»×3 repetition, streamed mixing for multi-hour sources).
- Process rhythm used (works well): design panel (3 biases + 3 lens judges) → synthesize
  composite in main loop → implement → 4-lens adversarial review with per-finding
  refutation → fix all → smoke on the sample → control on the 39-min video → user ear.
