# PLAN

## → Roadmap (reprioritized 2026-07-17; dead-air, batch+stop, proper-nouns, segmentation → CHANGELOG)
Sample workdirs: `work/4szRHy_CT7s/`, `work/x7DfiXqSEdM/` (Silero baselines, read-only),
`work-exp/f5-control/x7DfiXqSEdM/` (F5), `work-exp/bed-music/tJP6SKfo49c/` (bed check),
`work-exp/segfix/x7DfiXqSEdM/` (segmentation-cluster full run, condition=False — STALE once
the flag default flips; the ear-check MKV must be re-run with the flag on).
Report triage: any *_flag or speed_factor>1.8.
0. **Ear-check the whisper-context fix** (~46 min run, user-in-loop) — full --force pass on a
   fresh workdir with `whisper_condition_on_previous=True` (now the default) → confirm the
   "period mid-sentence" class is gone on the ear cases (id shifts again; reason from text).
   Code + experiment done (CHANGELOG/DECISIONS); only the binding ear verdict remains.
1. **Babble duration heuristic** (~1 d) — expected (canvas formula) vs actual unit duration →
   report flag; ASR round-trip is proven blind to garbled-but-recognizable audio (id101 sim 1.0,
   ear-bad). Value activates at batch scale — batch mode is live, first overnight runs will
   supply the calibration data. MOS scoring (UTMOS) deliberately NOT included — see Deferred

Backlog (second tier): `--repair id,id --seed N` (point re-synth + remux); per-run terminology
glossary; singing/music detection → keep original (no robot singing); loudnorm/EQ on the dub;
`--subs-only` fast path; morning triage HTML for batches (flagged segments with players);
cross-video stage pipelining (translate GPU ∥ synth/verify) if nights get tight.

Deferred — development ideas, explicitly NOT near-term (demoted 2026-07-17; revisit when a
need surfaces): optional cloud translation (Anthropic, opt-in, OFF by default — DECISIONS
2026-07-16); gender-matched narrator (median-F0 → M/F reference; blocked on a female PD
reference); multi-speaker violation detector (ECAPA embeddings vs dominant-voice centroid →
report flag; full diarization stays out of scope); UTMOS/MOS verification (high cost, low
effect until batch stats prove the duration heuristic insufficient); unit sim threshold
re-tune (base raised to 0.9 — revisit only if production flags misbehave); Arc B390 path
(whisper.cpp/llama.cpp SYCL, Silero-on-CPU or an unproven F5-on-XPU spike).

## Open questions
- Silero stress errors on names/homographs — worth a `+`-stress dictionary pass? (fallback
  engine only since the F5 default — low stakes)
- ~~Similarity metric/threshold for verify~~ RESOLVED: char-level SequenceMatcher(autojunk=False);
  per-sentence 0.8 (clean sample min 0.875 / mean 0.988), raised to 0.9 at unit level 2026-07-17
- ~~RTF end-to-end~~ RESOLVED (2026-07-16, 39-min video): ×0.75 realtime total; translate 1404s
  (80%, RTF 0.60), transcribe 156s, synth 43s (Silero) / ~10 min projected (F5 @ RTF 0.39),
  verify 88s, rest seconds. x5 budget cleared 6.7× (Silero) / ~5× (F5). Bottleneck = translate;
  revisit sentence batching first if overnight runs get time-bound

## Closed phases (details in CHANGELOG)
Phase 0 skeleton ✅ · Phase 1 MVP turn-key URL→MKV ✅ (ear-validated) · Phase 3 TTS engine
upgrade → F5/ESpeech ✅ · Dead-air group ✅ (2026-07-17) · Batch queue + stop switch ✅
(2026-07-17) · Proper nouns ✅ (ear 2026-07-17; audit triage → weekly INBOX processing).
Phase 2 (reliability/batch-ready) dissolved into the roadmap + backlog (triage HTML); its
ASR-verification item shipped back with Phase 1.

Stack pins, verified APIs and setup: STACK.md + SETUP.md. TTS engine: ESpeech-TTS-1_RL-V2
(F5-TTS, .venv-f5tts) — production default by ear 2026-07-16; narrator = ESpeech demo
reference (rights caveat in README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
