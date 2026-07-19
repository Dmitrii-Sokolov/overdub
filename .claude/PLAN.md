# PLAN

## → Roadmap (reprioritized 2026-07-18; item 0 ear-check + Gemma migration → CHANGELOG)
Sample workdirs: `work/` (Silero baselines, read-only); `work-exp/context-earcheck/x7DfiXqSEdM/`
(item-0 ear-check, Qwen translate — PASSED); `work-exp/stats-batch/` (Qwen, 8/23 — batch STOPPED to
switch models); `work-exp/gemma-ab/` (Gemma, the same 8 — the A/B set). A/B report artifact
published (Qwen vs Gemma, 508 sentences). Report triage: any *_flag or speed_factor>1.8.

1. **Sonnet semi-automatic translate — live-run the primary route.** Verdict recorded
   2026-07-18 (DECISIONS): quality noticeably better, much faster, replaces the heaviest stage;
   both routes stay — Gemma = local in-pipeline default, Sonnet (subscription, cloud) = PRIMARY,
   in semi-automatic mode (sub-agents at the translate seam). Runbook: README "Running" route B.
   Open: harden the recipe on the first real batch beyond the spike (e.g. the remaining 15/23
   stats-batch videos). The in-pipeline Anthropic API flag stays approved but deferred — build
   only if the manual seam becomes the bottleneck.

2. **Whisper anti-repetition decoder params — measure, then adopt or reject.** The transcribe
   guard (shipped 2026-07-19) catches a collapsed alignment AFTER the fact; these params attack
   what CAUSES it. `no_repeat_ngram_size` and `repetition_penalty` sit at library defaults (0 and
   1 — off), so the repetition loop that feeds whisper's temperature fallback is unopposed, and
   that fallback is why the same audio yields a different transcript per run (measured: a "clean"
   video spanned 0.00–7.46% over 5 runs). This is the only lever that could NARROW the spread
   instead of catching its tail — which would also let the guard's PROVISIONAL 0.085 threshold
   become a real constant.
   Do NOT adopt blind: too small an `n` silently eats legitimate repetition ("very, very",
   refrains, list items with a shared opener) — the forbidden silent-loss class.
   Measurement design (agreed, deferred): `4szRHy_CT7s` (severe) + a healthy control, `n` in
   0/4/5/6, 3 repeat runs per combination (~24 runs, ~25-30 min), scored on THREE axes —
   floor_run_ratio, duplicate adjacent sentences, and TOTAL WORD COUNT vs the n=0 baseline.
   The third axis is the load-bearing one: fewer duplicates is the win, fewer words is the
   regression, and a single metric cannot tell them apart. Probe script kept at
   `scratchpad/floor_variance.py` (read-only, transcribes from work/<id>/source.wav, writes
   nothing back) — extend it with the `n` sweep rather than starting over.

Backlog (second tier): narrow the `translate:refusal` regex — `как (?:ии|модель|языковая)` fires on
ordinary Russian "как ИИ" = "how AI" (proven: all 6 refusal flags in the 12-video AI-Fluency batch
were false, e.g. "по мере того, как ИИ продолжает развиваться"). Written for the Gemma route where
refusals are real; on the Sonnet route it is pure noise that inflates the triage list. Require the
pronoun ("как ИИ, я") or the full "как языковая модель";
`--repair id,id --seed N` (point re-synth + remux; grain = the GROUP after
units); per-run terminology glossary; singing/music detection → keep original (no robot singing);
loudnorm/EQ on the dub; `--subs-only` fast path; cross-video stage pipelining (translate GPU ∥
synth/verify) if nights get tight;
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
A/B-driven; Qwen removed)** · **Sonnet A/B + verdict: semi-auto = primary route ✅ (2026-07-18)** ·
**Observability: run.json + timings.json + run_report.py digest + morning-triage HTML ✅ (2026-07-19)**.

Stack pins, verified APIs and setup: STACK.md + SETUP.md. Translation: Gemma-3-12B (Ollama),
`gemma3:12b`, local in-pipeline default by A/B 2026-07-18 (Qwen3-14B removed); PRIMARY route =
Sonnet semi-automatic (DECISIONS 2026-07-18, runbook README "Running"). TTS: ESpeech-TTS-1_RL-V2 (F5-TTS,
.venv-f5tts) — production by ear 2026-07-16; narrator = ESpeech demo reference (rights caveat in
README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
