# PLAN

## Phase 0 — skeleton
- [ ] CLI entry point (single video URL → final MKV), config file
- [ ] Work-dir layout: per-video folder with stage artifacts (sentences.json,
      translation.json, segments/, final.mkv)
- [ ] Stage runner: per-video loop, stages sequential within a video, each
      stage resumable, skippable if artifact exists

## Phase 1 — MVP happy path (PoC target)
- [x] Day-1 TTS bake-off — done. Chatterbox rejected, Silero v4_ru/eugene
      adopted (see CHANGELOG + DECISIONS). Scripts: scripts/*_test.py
- [ ] yt-dlp download stage
- [ ] faster-whisper large-v3 transcription with word timestamps
- [ ] Sentence re-segmentation: words + punctuation → sentences with
      [start, end]; split overlong sentences (>~15 s) on clause boundaries
- [ ] Translation stage (Qwen3-14B via Ollama): sentence-by-sentence with
      rolling context window (previous EN+RU pairs), dubbing-aware prompt,
      outputs text_ru (subtitles) + text_tts (normalized for synthesis)
- [ ] Silero per-sentence synthesis (v4_ru, fixed voice `eugene`) behind a thin
      TTS engine adapter so alternatives can be A/B'd later
- [ ] Assembly: atempo fitting (uncapped), silence padding, RU track;
      per-segment speed factor logged
- [ ] ffmpeg mux: MKV with original audio + RU dub + EN/RU SRT subs
- [ ] Manual quality check on 2–3 real videos

## Phase 2 — reliability (batch-ready)
- [ ] ASR verification loop: whisper-small round-trip on raw (unsped) audio,
      compare against text_tts (same normalizer on both sides), retry with
      new seed, keep best-scoring attempt + flag in report after max retries
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
- Similarity metric and threshold for ASR verification (WER? char-level?)
- Silero stress errors on names/homographs — worth a `+`-stress dictionary pass?
- RTF unverified on the RTX 4080 Mobile for whisper + Qwen (TTS is CPU/near-free)
  — measure end-to-end on host before trusting the x5 budget

Stack pins, verified APIs and setup: STACK.md + SETUP.md. TTS engine settled:
Silero v4_ru, voice eugene (xenia backup); Chatterbox rejected (day-1 ear test).
