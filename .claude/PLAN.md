# PLAN

## → Roadmap (reprioritized 2026-07-18; item 0 ear-check + Gemma migration → CHANGELOG)
Sample workdirs: `work/` (Silero baselines, read-only); `work-exp/context-earcheck/x7DfiXqSEdM/`
(item-0 ear-check, Qwen translate — PASSED); `work-exp/stats-batch/` (Qwen, 8/23 — batch STOPPED to
switch models); `work-exp/gemma-ab/` (Gemma, the same 8 — the A/B set). A/B report artifact
published (Qwen vs Gemma, 508 sentences). Report triage: any *_flag or speed_factor>1.8.

1. **Translation completeness check** (NEW — now the top verify blind spot) — the ASR round-trip
   proves TTS fidelity to `text_ru`, NOT that `text_ru` fully covers the English. Gemma's tighter
   phrasing occasionally drops a word, unflagged (measured: Dmgujo id1, 3 of 4 adverbs). Same
   silent-loss class as the out-of-dict pronunciation echo. Cheap detector candidates: EN↔RU
   content-word count ratio, or a back-translation spot-check on length-ratio outliers.
2. **Finish the stats batch on Gemma** — 15 of 23 videos unrun (batch stopped at 8/23 to switch
   models). Re-run `--batch` on Gemma for the full stat set, incl. the two long stress-tests
   (Karpathy 3.5 h #18, Jensen 1.7 h #14) — watch those for whisper repetition loops (the
   context=True known risk) and atempo behaviour on long sources.
3. **Babble duration heuristic** (~1 d) — expected (canvas formula) vs actual unit duration →
   report flag; ASR round-trip proven blind to garbled-but-recognisable audio (id101 sim 1.0
   ear-bad; RyvXxApfHkk id12 = whisper CJK-garble both models dutifully "translated"). Value
   activates at batch scale. MOS/UTMOS deliberately NOT included — see Deferred.

Backlog (second tier): `--repair id,id --seed N` (point re-synth + remux; grain = the GROUP after
units); per-run terminology glossary; singing/music detection → keep original (no robot singing);
loudnorm/EQ on the dub; `--subs-only` fast path; morning triage HTML for batches (flagged segments
with players); cross-video stage pipelining (translate GPU ∥ synth/verify) if nights get tight;
fix the out/ export name collision (identical `<title> [<id>].mkv` across models overwrites — namespace
exports per run/model or per work_root).

Deferred — NOT near-term (revisit when a need surfaces): optional cloud translation (Anthropic,
opt-in, OFF by default — DECISIONS 2026-07-16; Gemma is now the local default it must not silently
replace); gender-matched narrator (median-F0 → M/F reference; blocked on a female PD reference);
multi-speaker violation detector (ECAPA vs dominant-voice centroid → report flag; full diarization
stays out of scope); UTMOS/MOS verification (high cost, low effect until batch stats prove the
duration heuristic insufficient); unit sim threshold re-tune (base 0.9 — revisit only if production
flags misbehave); Arc B390 path (whisper.cpp/llama.cpp SYCL, Silero-on-CPU or an unproven
F5/Gemma-on-XPU spike).

## Open questions
- **"Keep length" ↔ slow speech.** The SYSTEM prompt asks the LLM to keep RU CLOSE IN LENGTH to the
  EN so it fits the same time slot. Too long → atempo compresses (word-drop risk above ~1.3×); too
  short → the slot-fill stretch slows the speech (the "slightly slow / large inter-word gaps" the
  user heard on the item-0 dub) or leaves gaps. Gemma is tighter → marginally more stretch. Lever:
  RELAX the keep-length pressure for fuller RU (less stretch, more compression) — an experiment, a
  trade not a free win. `f5_speed_floor` caps max stretch at the cost of inter-phrase gaps.
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
