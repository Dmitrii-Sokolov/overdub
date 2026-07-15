# overdub

Local-first, semi-automated pipeline for dubbing YouTube videos into Russian.

Download → transcribe → translate → synthesize → mux. Every stage runs on local
hardware — no cloud APIs, no per-minute billing. Built for batch processing of
hundreds of hours of single-speaker content.

## Pipeline

1. **Download** — `yt-dlp` fetches the video.
2. **Transcribe (STT)** — `faster-whisper` (large-v3) produces the English
   transcript with word timestamps; words are re-assembled into sentences with
   `[start, end]`. The sentence is the unit of translation, synthesis and sync.
3. **Translate** — local LLM (Qwen3-14B via Ollama) translates sentence by
   sentence with a rolling context window (previous EN sentences + their RU
   translations), prompted to keep length close to the original (it's dubbing,
   not prose). Output per sentence: raw RU for subtitles + normalized RU
   (numbers, acronyms, Latin terms spelled out) for TTS.
4. **Synthesize (TTS)** — Silero (v4_ru, native Russian, fixed voice `eugene`)
   generates Russian audio per sentence. No voice cloning — a single narrator
   voice for every video (cross-lingual cloning was dropped; see DECISIONS).
5. **Verify** — each synthesized segment is transcribed back with whisper (small)
   and compared against the normalized TTS text; mismatches trigger
   regeneration with a new seed. Runs on raw audio, before any speed-up.
6. **Mux** — `ffmpeg` fits each segment into its time slot (`atempo`, uncapped —
   extreme speed factors are logged, not fixed), pads with silence, assembles
   the RU track and muxes the final MKV. The original video stream is never
   re-encoded.

## Output layout (MKV)

| Stream | Content |
|---|---|
| Video | original (stream copy) |
| Audio 1 | original |
| Audio 2 | Russian dub |
| Subtitles 1 | English — original transcript (SRT) |
| Subtitles 2 | Russian — translation (SRT) |

The transcript and translation already exist as pipeline artifacts, so both are
embedded as subtitle tracks for free.

## Stack

| Stage | Tool | Notes |
|---|---|---|
| Download | yt-dlp | |
| STT | faster-whisper large-v3 | CUDA |
| Translation | Qwen3-14B Q4 via Ollama | OpenAI-compatible endpoint — swap-friendly |
| TTS | Silero v4_ru (CPU) | native RU, fixed voice `eugene`; pluggable engine adapter |
| Verification | faster-whisper small | ASR round-trip check |
| Mux | ffmpeg | atempo fitting, MKV output |

## Hardware targets

- **Primary:** NVIDIA RTX 4080 Mobile, 12 GB VRAM. Stages run sequentially per
  video with explicit model unload between them — heavy models don't fit
  simultaneously. (Per-stage batching across many videos — one model load per
  stage — is a Phase 2 option.)
- **Secondary (later):** Intel Arc B390 iGPU. whisper.cpp (SYCL/OpenVINO) and
  llama.cpp (SYCL) are proven there for STT/translation; Silero TTS already runs
  on CPU, so the synthesis stage is GPU-independent.

Throughput budget: ≤ x5 video duration. TTS is near-free (Silero on CPU, RTF
~0.02–0.3); the real cost is transcription + translation. Measure end-to-end on host.

## Constraints / assumptions

- Single speaker per video (covers ~95% of target content). No diarization.
- Local only — no cloud STT, translation, or TTS.
- Source is always English, output is always Russian.
- No tempo compression cap — segments are sped up as much as their slot
  requires; occasional broken segments are acceptable losses (PoC).
- Fixed TTS voice (Silero `eugene`) — no voice cloning; "same voice as the
  speaker" was dropped after the day-1 engine bake-off.

## Status

Research / proof of concept. Documentation phase, no code yet.
See `.claude/PLAN.md`.
