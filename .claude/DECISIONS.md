# DECISIONS

## 2026-07-15 — Founding decisions

**Local-only pipeline.** Target volume is hundreds of hours; cloud TTS pricing
(ElevenLabs ≈ dollars per 20 min) makes remote synthesis economically absurd at
this scale. Local compute is a sunk cost. Trade-off accepted: local Russian TTS
quality is below ElevenLabs.

**Chatterbox Multilingual as the first TTS engine.** MIT license, actively
developed (Resemble AI), voice cloning + emotion control, strongest English
results in blind tests. Known risk: Russian is 6–7/10 with slight accent
artifacts. Silero (native Russian, flat but bulletproof) and XTTS-v2 (best
Russian among cloners, but dead project) come later behind a common interface.
If Chatterbox Russian fails the ear test — switch, don't polish (see PLAN kill
criteria).

**Timing strategy: per-segment TTS + atempo up to x2.** Russian runs 15–25%
longer than English; an x2 compression budget covers ~99% of segments. The user
validated by ear that x2 is acceptable. No smarter time-borrowing logic in v1.

**Local translation (Qwen3-14B via Ollama).** Operationally simpler than cloud
(no keys, no billing, offline), free at any volume. Quality loss vs frontier
models is acceptable for a dubbed track; upgrade path is a URL swap since
Ollama speaks the OpenAI protocol.

**ASR round-trip verification for every TTS segment.** Neural TTS hallucinates
(skips, repeats, mumbles). At hundreds of hours nobody will listen for defects
— the pipeline must catch them itself. Whisper-small transcribes each generated
segment; text mismatch → regenerate with a new seed.

**MKV container with dual subtitles.** Transcript (EN) and translation (RU)
already exist as pipeline artifacts — embedding both as subtitle tracks is
free. MKV over MP4: native SRT support, multiple audio tracks without
container quirks.

**Single-speaker assumption for v1.** Covers ~95% of target content.
Diarization (whisperX + pyannote) would multiply complexity by 2–3x — deferred
until actually needed.

**Rejected: Microsoft local voices.** Windows Narrator natural voices have no
ru-RU voice at all (verified 2026-07); legacy SAPI5 "Irina" is unusable.
Neural Dmitry/Svetlana are cloud-only (edge-tts) — violates local-only.

**Name: overdub.** Real audio-engineering term — laying a new track over an
existing recording, which is literally the final pipeline step.

**Voice cloning first, fixed voice as rollback.** Phase 1 clones the original
speaker (Chatterbox, short reference clip from source audio). This is the
riskiest quality axis — accent artifacts are strongest when cloning from an
English reference — but the payoff (preserved speaker identity) is highest, and
the rollback is trivial: one fixed Russian voice for everything. Decide by ear
after Phase 1; per kill criteria, don't tune reference clips endlessly.

**Custom orchestrator instead of pyVideoTrans / VideoLingo / Pandrator.**
Ready-made dubbing tools cover the happy path but not this project's core
requirements: ASR verification loop, resumable hundred-hour batches, dual
subtitle embedding, local-only pluggable TTS. They stay useful as reference
implementations for stage wiring and edge cases:
[pyVideoTrans](https://github.com/jianchang512/pyvideotrans),
[Pandrator](https://github.com/lukaszliniewicz/Pandrator).
