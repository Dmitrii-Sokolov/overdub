# CHANGELOG

## 2026-07-16 — Phase 1 validated (user ear-test)
- User inspected the assembled output on a real video: RU dub audio present, positioned at the
  correct timestamps, translation correct. This is the Phase-1 quality gate — the pipeline is
  proven turn-key (URL→MKV) on real content, not just mechanically on the sample. Phase 1 closed;
  next up is Phase 2 (batch mode) after broader real-content passes + full-length RTF measurement

## 2026-07-15 — Pipeline tail: synthesize + verify + assemble + mux (Phase 1 complete, turn-key)
- Filled the last 4 stub stages → the pipeline now runs URL→MKV end-to-end. Design panel
  (3-bias) + adversarial review (4-lens + per-finding verify) workflows, per the project rhythm
- synthesize: build_engine (Silero eugene) renders text_tts → segments/NNNNN.wav + manifest.json;
  atomic per-wav (tmp+os.replace), staleness-guarded resume (text_tts + flag), 0-frame honest
  empty slot, sr-drift guard, never-drop contiguity
- verify: whisper-small round-trip on RAW wavs; char-level SequenceMatcher(autojunk=False) of
  normalize_for_compare(text_tts) vs RU hypothesis @ 0.8; deterministic → flag not reseed;
  done() checks the "verify" marker key (NOT report.exists()) so an out-of-order run can't
  silently disable verification; loud guard if run before synthesize
- assemble: place each clip at absolute round(start*sr) in an int16 buffer, slot = [start,
  next.start) (gap = pause headroom), atempo uncapped (ffmpeg single-filter 0.5–100), speed
  factor logged UNCAPPED; dub_ru.wav + en.srt/ru.srt; atomic dub written last
- mux: MKV = av1 video copy + orig aac + RU dub (aac 128k, DEFAULT track) + EN/RU SRT with
  language metadata; explicit per-stream maps; atomic .mkv.tmp
- new overdub/report.py: co-owned report.json (load/upsert/save/prune, merge-by-id) so verify
  and assemble never clobber each other's fields; + workdir.seg_wav; silero.py explicit format="WAV"
- Verified on the 50-sentence sample (each stage via --only): synth 50/0-flagged, verify mean
  sim 0.988 / 0 flagged, assemble 3 sped max ×1.23, mux → 5-stream MKV (video not re-encoded).
  Review: 13 findings → 11 kept (all PLAUSIBLE/low), 2 refuted; 8 cheap fixes applied, 1 → INBOX

## 2026-07-15 — Project founded
- Repository initialized, documentation written (README, CLAUDE.md, artifact files)
- Stack and constraints fixed: see DECISIONS.md founding entry

## 2026-07-15 — Stack installed + day-1 TTS bake-off
- Installed local stack on the RTX 4080 Mobile: Ollama 0.31.2 + qwen3:14b,
  faster-whisper (.venv-asr), verified CUDA in both venvs
- Multi-agent stack-verification pass → STACK.md + SETUP.md (verified APIs, VRAM)
- Day-1 ear test on a real video: Chatterbox RU rejected (unusable even without
  cloning); Silero v4_ru adopted — voice eugene, xenia backup. Cross-lingual
  cloning dropped (same-voice premise abandoned). See DECISIONS engine bake-off.
- Experiment scripts: scripts/{day1_smoke_test,no_ref_test,silero_test}.py

## 2026-07-15 — Phase 0 skeleton
- overdub package: CLI, flat-TOML config, per-video workdir, resumable stage
  runner (skip-if-exists, --only/--force); 7 stages (download real, rest stubs)
- TTS engine adapter + SileroEngine (torch.hub v4_ru/eugene, soundfile output)
- Consolidated to one venv (.venv-asr); .venv-tts retired; `pip install -e .`
- Verified end-to-end: `overdub <url> --only download` → source.mkv + source.wav

## 2026-07-15 — Transcribe stage (Phase 1)
- faster-whisper large-v3 → word timestamps → word-level sentence resegmentation
  → sentences.json (+ words.json for re-tuning). Design + adversarial review via
  two workflows (3-approach design panel; 4-lens review + verify)
- Shared asr.py: Windows cuDNN DLL discovery + whisper loader; cuDNN verified on host
- 885 words → 50 sentences in 32s (RTF ~0.08); contract validated (ids contiguous,
  no zero-duration slots, monotone non-overlapping, no stutter/dangling artifacts)

## 2026-07-15 — Translate stage (Phase 1)
- sentences.json → Qwen3-14B (Ollama) → translation.json: per-sentence, id order,
  rolling ok-only context window; text_ru (subtitles) + text_tts (normalized for TTS).
  Design + adversarial review via two workflows (3-approach panel; 4-lens review+verify)
- New overdub/normalize.py: deterministic digits/units/acronyms/Latin/symbols → spoken
  Russian; idempotent, Cyrillic-only output; normalize_for_compare reused by verify.
  num2words (ru) added; stdlib speller fallback. 9 unit tests (magnitude/range/collision)
- Native Ollama /api/chat + think:false (not /v1 — /no_think left content empty on
  truncated reasoning); ~5s/sentence, openai dependency dropped, stage now stdlib-only
- Robustness: validate→reseed-retry→flagged EN fallback (never drop); append-only
  translation.jsonl (fsync) resume keyed on src_en; contiguity enforced; atomic write
- Verified on the 50-sentence sample: 50/50 ok, 0 flagged, RU/EN length ratios ≤1.67
  (atempo-friendly), resume confirmed (47→50 in 19s). Review fixed 3 silent magnitude
  bugs in the normalizer (grouped thousands, decimal ranges, Cyrillic х/с collisions)
