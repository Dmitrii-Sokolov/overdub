# PLAN

## Phase 0 — skeleton
- [ ] CLI entry point (single video URL → final MKV), config file
- [ ] Work-dir layout: per-video folder with stage artifacts (sentences.json,
      translation.json, segments/, final.mkv)
- [ ] Stage runner: per-video loop, stages sequential within a video, each
      stage resumable, skippable if artifact exists

## Phase 1 — MVP happy path (PoC target)
- [ ] Day-1 Chatterbox A/B ear test (before any pipeline code):
      scripts/day1_smoke_test.py — ~2-min RU synthesis over {EN ref, RU ref}
      × cfg_weight {0.0, 0.5}, one wav per config + printed RTF. Listen: is
      EN-ref RU natural enough to survive a whisper-small round-trip? If not →
      fall back to a fixed RU reference or another engine (see DECISIONS).
      (API verified live against chatterbox-tts 0.1.7 — see STACK.md.)
- [ ] yt-dlp download stage
- [ ] faster-whisper large-v3 transcription with word timestamps
- [ ] Sentence re-segmentation: words + punctuation → sentences with
      [start, end]; split overlong sentences (>~15 s) on clause boundaries
- [ ] Translation stage (Qwen3-14B via Ollama): sentence-by-sentence with
      rolling context window (previous EN+RU pairs), dubbing-aware prompt,
      outputs text_ru (subtitles) + text_tts (normalized for synthesis)
- [ ] Chatterbox Multilingual per-sentence synthesis — voice cloned from the
      original speaker (reference clip extracted from source audio)
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

## Phase 3 — TTS alternatives
- [ ] TTS engine interface; move Chatterbox behind it
- [ ] Silero adapter (CPU path)
- [ ] XTTS-v2 adapter
- [ ] A/B listening test on the same 2-minute fragment; pick default

## Phase 4 — Arc B390 path (optional)
- [ ] whisper.cpp SYCL/OpenVINO for STT
- [ ] llama.cpp SYCL for translation
- [ ] Silero-on-CPU as TTS; measure total throughput vs x5 budget

## Open questions
- Similarity metric and threshold for ASR verification (WER? char-level?)
- Reference-clip selection for cloning: how to auto-pick a clean 6–10 s sample
  (speech only, no music/noise) from the source audio
- RTF unverified on the RTX 4080 Mobile for every GPU stage (only third-party /
  different-GPU numbers exist) — measure on host before trusting the x5 budget

Stack pins, verified APIs and setup: STACK.md + SETUP.md (checkpoint question
resolved — chatterbox-tts 0.1.7, ChatterboxMultilingualTTS, t3_model="v3").
