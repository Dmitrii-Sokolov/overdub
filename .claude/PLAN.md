# PLAN

## Phase 0 — skeleton
- [ ] CLI entry point (single video URL → final MKV), config file
- [ ] Work-dir layout: per-video folder with stage artifacts (transcript.json,
      translation.json, segments/, final.mkv)
- [ ] Stage runner: each stage resumable, skippable if artifact exists

## Phase 1 — MVP happy path
- [ ] yt-dlp download stage
- [ ] faster-whisper large-v3 transcription (segment timestamps)
- [ ] Ollama translation stage (Qwen3-14B, dubbing-aware prompt)
- [ ] Chatterbox Multilingual per-segment synthesis — voice cloned from the
      original speaker (reference clip extracted from source audio)
- [ ] atempo fitting (cap x2) + track assembly
- [ ] ffmpeg mux: MKV with original audio + RU dub + EN/RU SRT subs
- [ ] Manual quality check on 2–3 real videos

## Phase 2 — reliability (batch-ready)
- [ ] ASR verification loop: whisper-small round-trip, similarity threshold,
      retry with new seed, flag-for-review fallback
- [ ] Batch mode: list of URLs, sequential stage batching (VRAM), resume on crash
- [ ] Overnight-run ergonomics: progress log, summary report, failed-segment list

## Phase 3 — TTS alternatives
- [ ] TTS engine interface; move Chatterbox behind it
- [ ] Silero adapter (CPU path)
- [ ] XTTS-v2 adapter
- [ ] A/B listening test on the same 2-minute fragment; pick default

## Phase 4 — Arc B390 path (optional)
- [ ] whisper.cpp SYCL/OpenVINO for STT
- [ ] llama.cpp SYCL for translation
- [ ] Silero-on-CPU as TTS; measure total throughput vs x5 budget

## Kill criteria
- Chatterbox Russian quality unacceptable after Phase 1 → switch default to
  XTTS-v2 or Silero (Phase 3 moves up, don't polish Chatterbox)
- Throughput worse than x5 duration on the 4080M → stop feature work, profile
- Cloned-voice accent unacceptable after Phase 1 ear test → fall back to one
  fixed Russian voice (cloning off), don't tune reference clips endlessly
- Verification loop rejects >20% of segments → rethink TTS choice before
  scaling to hundreds of hours

## Open questions
- Chatterbox variant/checkpoint to pin (Multilingual release, exact version)
- Similarity metric and threshold for ASR verification (WER? char-level?)
- Reference-clip selection for cloning: how to auto-pick a clean 6–10 s sample
  (speech only, no music/noise) from the source audio
