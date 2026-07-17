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

## → Roadmap (reprioritized 2026-07-16 evening; user-confirmed after the F5 ear check)
Sample workdirs: `work/4szRHy_CT7s/`, `work/x7DfiXqSEdM/` (Silero baselines, read-only),
`work-exp/f5-control/x7DfiXqSEdM/` (F5). Report triage: any *_flag or speed_factor>1.8.
1. **Dead-air: verdict "ощутимо лучше" — iterate the mix layer** (mechanism validated:
   in-span silence 607→204 s, id101 perfect in its group, 0 flags, atempo unused).
   Remaining, in order:
   - [x] 2026-07-17: f5_speed_ceil → 1.1 + stricter sim gate 0.9 for compressed units
         (shared unit_sim_threshold in synthesize+verify); bed → 0 dB, dub_mix default →
         "bed" (ear verdict: vocal removal at original level only; duck-depth retest and
         bed-RMS census/auto-fallback CANCELLED — see DECISIONS 2026-07-17)
   - [ ] point re-listen 17:00–17:05 (ex-cutoff unit [135-137]) + former gap spots on the
         resynthesized control
   - [ ] bed sanity-check on a MUSIC-HEAVY video (speech-only source: stem ≈ silence →
         bed ≈ replace; residual in-span silence accepted)
2. **Proper nouns** — detect Latin/brand tokens → pronunciation dictionary → phonetic translit
   fallback → per-run cache. F5 softened the class (id189: 0.95 vs Silero 0.661) but ear says
   "No Man's Sky" is still bad (id150); all worst control-run sims are this class
3. **Batch queue**: a file with N URLs → sequential turn-key runs, per-video resume on crash
4. **Stop switch**: a stop-file checked between stages/videos — overnight run halts cleanly
5. **Verify quality gap (babble detector)**: ASR round-trip blindness now CONFIRMED on real
   content by ear — id101 scored sim 1.0 yet sounds bad. Expected-vs-actual duration heuristic
   + optional local MOS (UTMOS)
6. **Optional cloud translation (Anthropic Sonnet)** — explicit opt-in flag, OFF by default
   (DECISIONS). Note: translate is no longer 80% of wall-clock — F5 synth grew it to a
   ~45/45 co-bottleneck; the win is smaller but still the largest single one
7. **Gender-matched narrator** — median-F0 of source speech (~165 Hz) → M/F reference per
   video; needs a good female PD reference (not found yet); edge cases → default voice + flag

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

## Phase 3 — TTS engine upgrade ✅ done (closed 2026-07-16, see CHANGELOG)

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
