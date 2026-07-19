# PLAN

## → Roadmap (reprioritized 2026-07-18; item 0 ear-check + Gemma migration → CHANGELOG)
Sample workdirs: `work/` (Silero baselines, read-only); `work-exp/context-earcheck/x7DfiXqSEdM/`
(item-0 ear-check, Qwen translate — PASSED); `work-exp/stats-batch/` (Qwen, 8/23 — batch STOPPED to
switch models); `work-exp/gemma-ab/` (Gemma, the same 8 — the A/B set). A/B report artifact
published (Qwen vs Gemma, 508 sentences). Report triage: any *_flag or speed_factor>1.8.

1. **Run report / observability — measure and log what the pipeline loses and spends.**
   Logging today is partial: `report.json` carries per-segment verify/assemble fields
   (similarity, verify_flag, translate_flag, tts_speed/seed/attempts, synth_sim) + a `verify`
   rollup (n_flagged/retried/repaired); `translation.json` carries translate status/flags;
   `pronounce_audit.json` triages Latin tokens. GAPS: stage wall-clock is printed to stdout
   (`[ok] Xs`) but never persisted; no per-RUN rollup (timings, RTF, stage breakdown), no
   speed-distribution aggregate (median/p95/max, count>1.8), no completeness metric, no
   batch-level sweep — triage is manual (grep report for *_flag / speed>1.8). Build a per-run
   `run.json` (feeding the backlog morning-triage HTML) that should include:
   - **timings** — per-stage wall-clock persisted; end-to-end RTF (wall / video duration); stage breakdown %.
   - **flag counts by type** — translate (empty/echo/runaway/refusal/no_cyrillic), verify
     (low_similarity/missing_wav/empty_hyp/…), completeness (num_loss/neg_loss/entity_loss/length).
   - **speed distribution** — median/p95/max tts_speed, count > 1.8 (today's manual triage bar).
   - **completeness aggregates** — numbers/entities/negations dropped EN→RU (from the A+B pass below).
   - **retry/repair** — n_retried, n_repaired (already in the verify marker → roll up to run level).
   - **batch sweep** — across videos: which need triage, total wall, throughput.
   *In progress now (the completeness data source):* a cheap deterministic completeness check
   (approaches A+B, no LLM/VRAM) — length-ratio outlier + hard-loss of numbers, negations and
   Latin named-entities EN→RU — written as non-blocking per-segment flags in `report.json` at
   verify. Rationale: the primary route (Sonnet) is completeness-clean (read-through found none);
   this is minimal insurance catching the fact-inverting losses (a dropped `not`/number) that are
   otherwise silent, on both routes. The heavy semantic check (LLM judge / embeddings) was
   evaluated and rejected as PoC over-engineering (DECISIONS 2026-07-19).

2. **Sonnet semi-automatic translate — live-run the primary route.** Verdict recorded
   2026-07-18 (DECISIONS): quality noticeably better, much faster, replaces the heaviest stage;
   both routes stay — Gemma = local in-pipeline default, Sonnet (subscription, cloud) = PRIMARY,
   in semi-automatic mode (sub-agents at the translate seam). Runbook: README "Running" route B.
   Open: harden the recipe on the first real batch beyond the spike (e.g. the remaining 15/23
   stats-batch videos). The in-pipeline Anthropic API flag stays approved but deferred — build
   only if the manual seam becomes the bottleneck.

Backlog (second tier): `--repair id,id --seed N` (point re-synth + remux; grain = the GROUP after
units); per-run terminology glossary; singing/music detection → keep original (no robot singing);
loudnorm/EQ on the dub; `--subs-only` fast path; morning triage HTML for batches (flagged segments
with players); cross-video stage pipelining (translate GPU ∥ synth/verify) if nights get tight;
fix the out/ export name collision (identical `<title> [<id>].mkv` across models overwrites — namespace
exports per run/model or per work_root). — tail (lowest priority, keep for later): translation
completeness check (EN↔RU content-word ratio / back-translation on outliers) — no current evidence
the model drops words on short sentences, but cheap insurance if it ever does; babble duration
heuristic (expected-vs-actual unit duration → flag garbled synth the ASR round-trip misses) — output
is good now, ADD IT before any narrator-voice or TTS-engine change.

Deferred — NOT near-term (revisit when a need surfaces): gender-matched
narrator (median-F0 → M/F reference; blocked on a female PD reference);
multi-speaker violation detector (ECAPA vs dominant-voice centroid → report flag; full diarization
stays out of scope); UTMOS/MOS verification (high cost, low effect until batch stats prove the
duration heuristic insufficient); unit sim threshold re-tune (base 0.9 — revisit only if production
flags misbehave); Arc B390 path (whisper.cpp/llama.cpp SYCL, Silero-on-CPU or an unproven
F5/Gemma-on-XPU spike).

## Open questions
- **"Keep length" ↔ slow speech.** The SYSTEM prompt asks the LLM to keep RU CLOSE IN LENGTH to the
  EN so it fits the same slot; every sentence is then fitted to its slot (atempo compress if long,
  F5 slot-fill stretch if short). Measured Gemma vs Qwen (508 segs): Gemma ~2% shorter (raw
  audio/slot 0.981 vs 0.997), stretched on 46% of segments vs 39%, mean tts_speed 0.977 vs 0.989,
  leftover silence 1.2% vs 0.8% — its tightness pushes marginally toward the slow-speech end. Lever:
  RELAX the keep-length pressure for fuller RU (less stretch, more compression) — a trade, not free.
  `f5_speed_floor` caps max stretch at the cost of inter-phrase gaps.
- Silero stress on names/homographs — a `+`-stress dictionary pass? (fallback engine only, low stakes)
- ~~Similarity metric/threshold~~ RESOLVED: char-level SequenceMatcher(autojunk=False); unit-level 0.9.
- ~~RTF end-to-end~~ RESOLVED (2026-07-16): translate is the bottleneck. Gemma adds ~16% there.

## Closed phases (details in CHANGELOG)
Phase 0 skeleton ✅ · Phase 1 MVP turn-key URL→MKV ✅ · Phase 3 TTS → F5/ESpeech ✅ · Dead-air ✅ ·
Batch queue + stop switch ✅ · Proper nouns ✅ · Segmentation cluster + whisper-context ROOT fix ✅ ·
**Item 0 whisper-context ear-validated ✅ (2026-07-18)** · **Gemma-3-12B migration ✅ (2026-07-18,
A/B-driven; Qwen removed)** · **Sonnet A/B + verdict: semi-auto = primary route ✅ (2026-07-18)**.

Stack pins, verified APIs and setup: STACK.md + SETUP.md. Translation: Gemma-3-12B (Ollama),
`gemma3:12b`, local in-pipeline default by A/B 2026-07-18 (Qwen3-14B removed); PRIMARY route =
Sonnet semi-automatic (DECISIONS 2026-07-18, runbook README "Running"). TTS: ESpeech-TTS-1_RL-V2 (F5-TTS,
.venv-f5tts) — production by ear 2026-07-16; narrator = ESpeech demo reference (rights caveat in
README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
