# PLAN

## → Roadmap (reprioritized 2026-07-18; item 0 ear-check + Gemma migration → CHANGELOG)
Sample workdirs: `work/` (Silero baselines, read-only); `work-exp/context-earcheck/x7DfiXqSEdM/`
(item-0 ear-check, Qwen translate — PASSED); `work-exp/stats-batch/` (Qwen, 8/23 — batch STOPPED to
switch models); `work-exp/gemma-ab/` (Gemma, the same 8 — the A/B set). A/B report artifact
published (Qwen vs Gemma, 508 sentences). Report triage: any *_flag or speed_factor>1.8.

1. **Sonnet cloud-translate A/B** (TOP PRIORITY) — build the opt-in Anthropic path (approved
   DECISIONS 2026-07-16, NOT yet in code — the translate stage is Ollama-only) behind an
   off-by-default flag, then A/B Claude Sonnet vs Gemma-3-12B on the same `sentences.json` (same
   method as Qwen→Gemma: reuse segmentation, only the translator varies). Local Gemma stays the
   default; cloud is opt-in, never a silent fallback. Watch length — whether Sonnet runs fuller or
   tighter shifts the slot-fill stretch (Open questions).

Backlog (second tier): `--repair id,id --seed N` (point re-synth + remux; grain = the GROUP after
units); per-run terminology glossary; singing/music detection → keep original (no robot singing);
loudnorm/EQ on the dub; `--subs-only` fast path; morning triage HTML for batches (flagged segments
with players); cross-video stage pipelining (translate GPU ∥ synth/verify) if nights get tight;
fix the out/ export name collision (identical `<title> [<id>].mkv` across models overwrites — namespace
exports per run/model or per work_root).

Deferred — NOT near-term (revisit when a need surfaces): babble duration heuristic (expected vs
actual unit duration → flag garbled-but-recognisable synth the ASR round-trip misses, e.g.
RyvXxApfHkk id12; value is at batch-reliability scale, not the current focus); translation
completeness check (round-trip is blind to a dropped word — same batch-scale insurance); gender-matched
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
A/B-driven; Qwen removed)**.

Stack pins, verified APIs and setup: STACK.md + SETUP.md. Translation: Gemma-3-12B (Ollama),
`gemma3:12b`, default by A/B 2026-07-18 (Qwen3-14B removed). TTS: ESpeech-TTS-1_RL-V2 (F5-TTS,
.venv-f5tts) — production by ear 2026-07-16; narrator = ESpeech demo reference (rights caveat in
README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
