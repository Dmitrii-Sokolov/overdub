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
Phase 1 is closed. All 7 stages work; `overdub <url>` runs URL→MKV turn-key. Sample kept at
`work/4szRHy_CT7s/` (translation.json + all wavs + output.mkv). Re-run any stage in isolation:
`python -m overdub "<url>" --only <stage> [--force]` (download/transcribe/translate skip if their
artifacts exist, so an isolated tail run does NOT re-fetch/re-ASR). Report triage:
`report.json` — flag any segment with translate_flag/verify_flag/assemble_flag or speed_factor>1.8.
**Highest-value next work, in order:**
1. Run 2–3 more real videos incl. number-heavy / acronym-heavy content — the normalizer is the
   only silent-failure surface left; listen for magnitude/stress errors.
2. Measure RTF end-to-end on a full-length (30–60 min) video against the x5 budget (whisper-large
   + Qwen are the unknowns; TTS/assemble are near-free).
3. Then Phase 2 batch mode (below). Process INBOX first (5 deferred items + download.py preflight).

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

## Phase 3 — TTS alternatives (only if eugene proves insufficient)
- [ ] Second engine behind the Phase-1 adapter
- [ ] F5-TTS adapter (modern, alive) — the option if voice matching / expressiveness
      is ever needed; NOT XTTS (dead, non-commercial, same cross-lingual accent risk)
- [ ] A/B listening test on the same fragment; pick default

## Phase 4 — Arc B390 path (optional)
- [ ] whisper.cpp SYCL/OpenVINO for STT
- [ ] llama.cpp SYCL for translation
- [ ] Silero-on-CPU as TTS; measure total throughput vs x5 budget

## Open questions
- ~~Similarity metric/threshold for verify~~ RESOLVED: char-level SequenceMatcher(autojunk=False)
  @ 0.8; on the clean sample min 0.875 / mean 0.988 / 0 flagged. Re-tune threshold on real content
- Silero stress errors on names/homographs — worth a `+`-stress dictionary pass?
- RTF partial: on host, synth 50 seg/~14s (Silero CPU), verify 50 seg/~20–31s (whisper-small CUDA),
  assemble+mux seconds. whisper-large + Qwen (translate ~0.8× realtime) remain the batch bottleneck
  — still unmeasured end-to-end against the x5 budget on a full-length video

Stack pins, verified APIs and setup: STACK.md + SETUP.md. TTS engine settled:
Silero v4_ru, voice eugene (xenia backup); Chatterbox rejected (day-1 ear test).
