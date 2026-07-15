# overdub — project instructions

Local-first YouTube→Russian dubbing pipeline. Python. Every processing stage
must run on local hardware.

## Host environment

- Windows 11, PowerShell-first tooling.
- Primary GPU: NVIDIA RTX 4080 Mobile, 12 GB VRAM (CUDA). Secondary target:
  Intel Arc B390 iGPU — SYCL/OpenVINO paths (whisper.cpp, llama.cpp), unproven
  for PyTorch TTS.
- External binaries expected but not guaranteed: `ffmpeg`, `yt-dlp`, Ollama
  serving on localhost. Verify availability before assuming; fail with a clear
  message, don't auto-install.
- Laptop thermals: hundred-hour batches run overnight at sustained load —
  batch mode must survive interruption (resume) and should support a reduced
  power limit / cooldown pauses.

## Hard constraints

- **Local only.** No cloud STT/translation/TTS. The Ollama endpoint is
  localhost, not a hosted API.
- **Single-speaker assumption.** No diarization in v1.
- **12 GB VRAM budget.** Never load two heavy models at once; process in
  sequential batch stages with explicit model unload between stages.
- **Tempo compression cap: x2** (`atempo`). If a segment still doesn't fit,
  shorten the translation — don't compress harder.
- **Output is MKV** with original audio, RU dub, EN subs, RU subs. The original
  video stream is never re-encoded.

## Stack (v1)

yt-dlp → faster-whisper large-v3 → Qwen3-14B (Ollama) → Chatterbox Multilingual → ffmpeg.

TTS engines are pluggable: Chatterbox first; Silero and XTTS-v2 behind the same
interface later. Don't hardcode Chatterbox specifics outside the engine adapter.

## Design rules

- Every TTS segment goes through ASR verification (whisper-small round-trip +
  normalized text similarity). Failed segments regenerate with a new seed,
  max N retries, then get flagged for manual review — never silently kept.
- All intermediate artifacts (transcript, translation, per-segment audio) are
  persisted to the work dir. Every stage must be resumable and re-runnable in
  isolation — the pipeline is semi-automated by design.
- The translation prompt must state that this is dubbing and ask to keep
  length close to the original segment.
- TTS input must be normalized before synthesis: numbers, units, acronyms and
  Latin-script terms expanded to Russian words ("GPU" → "джи-пи-ю", "x2" →
  "в два раза") — neural TTS stumbles on raw digits and Latin tokens. Do it in
  the translation prompt or as a dedicated post-pass, but never feed raw text.

## Artifacts

Planning lives in `.claude/PLAN.md`, rationale in `.claude/DECISIONS.md`,
history in `.claude/CHANGELOG.md`, raw ideas in `.claude/INBOX.md`
(global 4-file framework).
