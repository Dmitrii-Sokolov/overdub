# PLAN

## Phase 0 — skeleton ✅ done (see CHANGELOG)
CLI + flat-TOML config + per-video workdir + resumable stage runner + download
stage, all verified end-to-end. One venv (.venv-asr), `overdub` package.

## Phase 1 — MVP happy path (PoC target) ✅ done — turn-key URL→MKV, user ear-test passed
- [x] Day-1 TTS bake-off — done. Chatterbox rejected, Silero v4_ru/eugene
      adopted (see CHANGELOG + DECISIONS). Scripts: scripts/*_test.py
- [x] yt-dlp download stage (implemented in the Phase 0 skeleton)
- [x] faster-whisper large-v3 transcription with word timestamps
- [x] Sentence re-segmentation → sentences.json (word-level, guarded split,
      duration-aware overlong split). Designed + adversarially reviewed via
      workflows; verified on the sample (see CHANGELOG/DECISIONS)
- [x] Translation stage (Qwen3-14B via Ollama): per-sentence, ok-only rolling
      context, native /api/chat think:false; text_ru + normalized text_tts via
      deterministic normalize.py. Design + review workflows; verified on sample
      (see CHANGELOG/DECISIONS)
- [x] Silero per-sentence synthesis (v4_ru, `eugene`) via build_engine adapter →
      segments/*.wav + manifest.json; atomic per-wav, staleness-guarded resume.
      Design panel + adversarial review workflows; verified on sample (CHANGELOG/DECISIONS)
- [x] Assembly: atempo fit (uncapped, ffmpeg single-filter), place at absolute start,
      slot = [start, next.start), int16 buffer → dub_ru.wav; en.srt/ru.srt; speed factor
      logged UNCAPPED in report.json
- [x] ffmpeg mux: MKV — video copy + orig audio + RU dub (aac, default) + EN/RU SRT
- [x] Manual quality check — user validated the assembled output on a real video: dub audio
      present, positioned at the right timestamps, translation correct. Phase 1 PoC proven
      (URL→MKV, turn-key). Broaden to 2–3 more videos + edge content when convenient

## → Roadmap (consolidated 2026-07-16; user-confirmed order)
Phase 1 closed; RTF gate PASSED (39-min video ×0.75 realtime, translate = 80% of wall-clock).
Sample workdirs: `work/4szRHy_CT7s/`, `work/x7DfiXqSEdM/`. Report triage: any segment with
*_flag or speed_factor>1.8.
1. **F5Engine integration** — DONE except the default-engine flip (ear-check gated, Phase 3
   below). Remainder moved here: per-segment NATIVE speed from the slot budget (F5 `speed`
   instead of post-hoc atempo; ×1.6 verified at ≤0.022 sim cost) — deliberately out of the
   integration session's scope
2. **Proper nouns** — detect Latin/brand tokens → pronunciation dictionary → phonetic translit
   fallback → per-run cache ("но ман'с скй" garbage + english_echo false flags, id150/id189)
3. **Dub as overlay mix, not replacement**: ideally vocal-separate the original (Demucs, local)
   → ambience/music bed + RU dub; fallback — duck the full original track. Also dissolves the
   inter-phrase dead air (744 s of silence measured on the 39-min dub). Optional prosody helper:
   group adjacent sentences (gap <0.4 s) into one synth call
4. **Batch queue**: a file with N URLs → sequential turn-key runs, per-video resume on crash
5. **Stop switch**: a stop-file checked between stages/videos — overnight run halts cleanly by
   morning; no mid-stage save needed (stages are already atomic + resumable)
6. **Verify quality gap (babble detector)**: ASR round-trip is PROVEN blind to babble (0.93 sim
   on garbage audio) — add expected-vs-actual duration heuristic + optional local MOS (UTMOS)
7. **Optional cloud translation (Anthropic Sonnet)** — explicit opt-in flag, OFF by default;
   a deliberate exception to local-only (DECISIONS); translate is 80% of wall-clock, expect the
   largest single speed win + quality bump
8. **Gender-matched narrator** — median-F0 of source speech (~165 Hz threshold; the exact
   method used in the narrator bake-off) → pick M/F reference per video; needs a good female
   PD reference (not found yet); edge cases → default voice + report flag

Backlog (second tier): `--repair id,id --seed N` (point re-synth + remux); per-run terminology
glossary; singing/music detection → keep original (no robot singing); loudnorm/EQ on the dub;
`--subs-only` fast path; morning triage HTML for batches (flagged segments with players);
cross-video stage pipelining (translate GPU ∥ synth/verify) if nights get tight.

## Phase 2 — reliability (batch-ready)
- [x] ASR verification loop: whisper-small round-trip on raw (unsped) audio, compare
      normalize_for_compare(text_tts) vs the RU hypothesis (same fn both sides). Silero is
      deterministic → FLAG in report.json, no reseed. Char-level SequenceMatcher(autojunk=False)
      @ threshold 0.8. Built alongside Phase 1 (runs before assemble); verified on sample
- [ ] Batch mode: list of URLs, resume on crash; decide whether to switch the
      outer loop to per-stage batching (one model load per stage per batch) —
      only if per-video reload overhead actually matters
- [ ] Stop switch: stop-file checked between stages/videos (roadmap item 5)
- [ ] Overnight-run ergonomics: progress log, summary report, morning triage
      HTML (flagged segments with audio players)

## Phase 3 — TTS engine upgrade (bake-off #2 done; ESpeech adopted by ear)
- [x] Research sweep + adversarial verify of the July-2026 local RU TTS landscape →
      bakeoff/tts-research-2026-07.md (~20 engines; only Silero/ESpeech/Misha speak Russian)
- [x] Bake-off #2: bakeoff/listen.html (8 phrases × 5 engines) + full-video runs.
      ESpeech-TTS-1_RL-V2 unambiguous winner (mean sim 0.992, ×1.03, 0 flags on the sample
      video); Silero v5 > v4 but below F5; Misha good but NC-licensed. EN-voice cloning
      explored and dropped; RU-voice cloning works (DECISIONS 2026-07-16)
- [x] F5Engine behind the adapter — worker process in .venv-f5tts (venvs incompatible,
      measured), RUAccent + shim in the worker, seed/speed/nfe params, synth_key resume
      guard, manifest v2 (complete-marker + periodic flush). Design panel + adversarial
      review + smoke (DECISIONS 2026-07-16)
- [x] Reseed-retry — lives in SYNTHESIZE (manifest single-writer), keep-best by
      round-trip sim; mechanics proven on id43 (4 attempts, honest flag)
- [x] Ultra-short merge in transcribe (MIN_SENT_CHARS=15, gap ≤0.6 s, cumulative ≤1.5 s);
      unit-tested; validates on the next fresh video (control reuses frozen sentences)
- [x] Narrator decided: ESpeech demo reference (0.992 / 0 flags / ×1.03; rights caveat —
      fetch at setup, personal use only; PD fallbacks + speed-calibration in DECISIONS)
- [x] Control run on x7DfiXqSEdM (39 min) vs Silero baseline: flags 0 vs 1, sim mean
      0.9943 vs 0.986, atempo mean ×1.014 vs ×1.018, 0 retries. RTF gate MISSED:
      synth+verify ×0.65 vs ≤0.5 target (thermal-loaded; cold bake-off was 0.39);
      x5 budget still cleared ~3.8× full-pipeline
- [ ] Flip default tts_engine to "f5" (config.py + overdub.toml, own commit) — gated on
      the user ear check of work-exp/f5-control/x7DfiXqSEdM/output.mkv

## Phase 4 — Arc B390 path (optional)
- [ ] whisper.cpp SYCL/OpenVINO for STT
- [ ] llama.cpp SYCL for translation
- [ ] Silero-on-CPU as TTS; measure total throughput vs x5 budget

## Open questions
- ~~Similarity metric/threshold for verify~~ RESOLVED: char-level SequenceMatcher(autojunk=False)
  @ 0.8; on the clean sample min 0.875 / mean 0.988 / 0 flagged. Re-tune threshold on real content
- Silero stress errors on names/homographs — worth a `+`-stress dictionary pass?
- ~~RTF end-to-end~~ RESOLVED (2026-07-16, 39-min video): ×0.75 realtime total; translate 1404s
  (80%, RTF 0.60), transcribe 156s, synth 43s (Silero) / ~10 min projected (F5 @ RTF 0.39),
  verify 88s, rest seconds. x5 budget cleared 6.7× (Silero) / ~5× (F5). Bottleneck = translate;
  revisit sentence batching first if overnight runs get time-bound

Stack pins, verified APIs and setup: STACK.md + SETUP.md. TTS engine: ESpeech-TTS-1_RL-V2
(F5-TTS, .venv-f5tts) adopted by ear 2026-07-16, integration pending; narrator = ESpeech demo
reference (rights caveat in README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
