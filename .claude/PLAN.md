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

## → Resume here (next session)
Phase 1 closed. RTF gate PASSED on a 39-min video (x7DfiXqSEdM): end-to-end ×0.75 realtime,
translate = 80% of wall-clock, x5 budget cleared 6.7×. Sample workdirs: `work/4szRHy_CT7s/`,
`work/x7DfiXqSEdM/`. Report triage: flag any segment with translate_flag/verify_flag/
assemble_flag or speed_factor>1.8. **Agreed order of work:**
1. Phase 3 below — F5Engine integration (ESpeech adopted by ear; DECISIONS 2026-07-16).
2. Proper-noun phonetics for TTS (brand dictionary + phonetic translit fallback) — the one
   systematic content defect: "но ман'с скй"-class garbage + english_echo false flags
   (x7DfiXqSEdM id150/id189). Perpendicular to the engine work.
3. Voice-over mix (ducked original under the dub) — dub covers ~68% of runtime, 744 s dead
   silence on the 39-min video. Deferred BY DESIGN until the TTS layer is settled: masking
   comes after the layers beneath are good.
4. Then Phase 2 batch mode (below). Process INBOX (transcribe/translate deferred items).

## Phase 2 — reliability (batch-ready)
- [x] ASR verification loop: whisper-small round-trip on raw (unsped) audio, compare
      normalize_for_compare(text_tts) vs the RU hypothesis (same fn both sides). Silero is
      deterministic → FLAG in report.json, no reseed. Char-level SequenceMatcher(autojunk=False)
      @ threshold 0.8. Built alongside Phase 1 (runs before assemble); verified on sample
- [ ] Batch mode: list of URLs, resume on crash; decide whether to switch the
      outer loop to per-stage batching (one model load per stage per batch) —
      only if per-video reload overhead actually matters
- [ ] Overnight-run ergonomics: progress log, summary report, flagged-segment
      list with speed factors

## Phase 3 — TTS engine upgrade (bake-off #2 done; ESpeech adopted by ear)
- [x] Research sweep + adversarial verify of the July-2026 local RU TTS landscape →
      bakeoff/tts-research-2026-07.md (~20 engines; only Silero/ESpeech/Misha speak Russian)
- [x] Bake-off #2: bakeoff/listen.html (8 phrases × 5 engines) + full-video runs.
      ESpeech-TTS-1_RL-V2 unambiguous winner (mean sim 0.992, ×1.03, 0 flags on the sample
      video); Silero v5 > v4 but below F5; Misha good but NC-licensed. EN-voice cloning
      explored and dropped; RU-voice cloning works (DECISIONS 2026-07-16)
- [ ] F5Engine behind the adapter: RUAccent inside the engine (+ token_type_ids shim),
      seed + speed params, .venv strategy (try main venv, else worker process);
      ultra-short-sentence mitigation (merge upstream or reseed)
- [ ] Reseed-retry in verify — F5 is seed-controllable, the retry path finally goes live
- [x] Narrator decided: ESpeech demo reference (0.992 / 0 flags / ×1.03; rights caveat —
      fetch at setup, personal use only; PD fallbacks + speed-calibration in DECISIONS)
- [ ] Control run on x7DfiXqSEdM (39 min): flag rate + RTF vs the Silero baseline

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

Stack pins, verified APIs and setup: STACK.md + SETUP.md. TTS engine settled:
Silero v4_ru, voice eugene (xenia backup); Chatterbox rejected (day-1 ear test).
