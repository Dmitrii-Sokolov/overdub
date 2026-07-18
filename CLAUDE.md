# overdub — project instructions

Local-first YouTube→Russian dubbing pipeline. Python. Every processing stage
must run on local hardware.

Current stage: research / proof of concept. The pipeline must run turn-key
(URL in → final MKV out) with acceptable speed and quality; occasional broken
segments are tolerated, silent failures are not.

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

- **Local by default.** No cloud STT or TTS, ever. The Ollama endpoint is
  localhost, not a hosted API. One approved exception — cloud translation
  (DECISIONS 2026-07-16 + 2026-07-18): the PRIMARY translate route is Sonnet in
  semi-automatic mode (sub-agents write translation.json at the translate seam;
  runbook: README "Running"); the local Gemma path remains the in-pipeline
  default and must keep working; cloud is always explicit, never a silent
  fallback.
- **EN→RU only.** Source audio is always English, the dub is always Russian.
  No language detection, no multi-language handling.
- **Single-speaker assumption.** No diarization in v1.
- **12 GB VRAM budget.** Never load two heavy models (whisper large-v3,
  Gemma-3-12B, TTS) at once; explicit model unload between stages. Exception:
  whisper-small (~0.5 GB) stays co-resident with the TTS engine during
  synthesis + verification.
- **No tempo cap.** `atempo` speeds segments up as much as their slot
  requires, applied at assembly — always after verification, never before.
  Per-segment speed factor goes to the run report; audibly broken segments
  are acceptable losses, silent ones are not.
- **Output is MKV** with original audio, RU dub, EN subs, RU subs. The original
  video stream is never re-encoded.

## Stack (v1)

yt-dlp → faster-whisper large-v3 → Gemma-3-12B (Ollama) → ESpeech/F5-TTS →
htdemucs no-vocals bed (dub_mix="bed" default) → ffmpeg.

TTS engines are pluggable behind an adapter: ESpeech-TTS-1_RL-V2 (F5-TTS, worker
process in `.venv-f5tts`) is the production engine (ear check 2026-07-16); Silero
v4_ru (voice `eugene`, `xenia` backup) is the fallback; Chatterbox was rejected in
the day-1 ear test (see DECISIONS). No voice cloning — fixed narrator voice. Don't
hardcode engine specifics outside the engine adapter. Three venvs, never merge them:
`.venv-asr` (pipeline), `.venv-f5tts` (F5 worker), `.venv-demucs` (separate stage);
run the pipeline with `.venv-asr` python via `python -X utf8 -m overdub`.

## Design rules

- Every TTS segment goes through ASR verification (whisper-small round-trip +
  normalized text similarity), always on raw audio — before atempo. Failed
  segments are flagged in the run report; for engines with a random seed, retry
  with a new seed up to N times first (Silero is deterministic — reseeding is a
  no-op, so its failures are flagged directly). The pipeline never blocks on a
  bad segment, never hides one.
- All intermediate artifacts (transcript, translation, per-segment audio) are
  persisted to the work dir. Every stage must be resumable and re-runnable in
  isolation — the pipeline is semi-automated by design.
- Translation unit is the sentence (rebuilt from word timestamps), never the
  raw whisper segment: sentences are translated in order with a rolling
  context window (previous EN sentences + their RU translations). The prompt
  must state that this is dubbing and ask to keep length close to the
  original — no tempo cap doesn't mean no effort.
- TTS input must be normalized before synthesis: numbers, units, acronyms and
  Latin-script terms expanded to Russian words ("GPU" → "джи-пи-ю", "x2" →
  "в два раза") — neural TTS stumbles on raw digits and Latin tokens. Do it in
  the translation prompt or as a dedicated post-pass, but never feed raw text.
  Keep both fields per sentence: `text_ru` (raw translation → subtitles) and
  `text_tts` (normalized → synthesis); ASR verification compares against
  `text_tts` with the same normalizer applied to both sides.

## Artifacts

Planning lives in `.claude/PLAN.md`, rationale in `.claude/DECISIONS.md`,
history in `.claude/CHANGELOG.md`, raw ideas in `.claude/INBOX.md`
(global 4-file framework).
