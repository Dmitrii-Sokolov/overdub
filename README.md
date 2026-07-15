# overdub

Local-first, semi-automated pipeline for dubbing YouTube videos into Russian.

Download → transcribe → translate → synthesize → mux. Every stage runs on local
hardware — no cloud APIs, no per-minute billing. Built for batch processing of
hundreds of hours of single-speaker content.

## Pipeline

1. **Download** — `yt-dlp` fetches the video.
2. **Transcribe (STT)** — `faster-whisper` (large-v3) produces the English
   transcript with segment timestamps. These timestamps drive all downstream sync.
3. **Translate** — local LLM (Qwen3-14B via Ollama) translates EN→RU per segment,
   prompted to keep length close to the original (it's dubbing, not prose).
4. **Synthesize (TTS)** — Chatterbox Multilingual generates Russian audio per
   segment. Segments longer than their time slot are compressed with
   `ffmpeg atempo` (up to x2).
5. **Verify** — each synthesized segment is transcribed back with whisper (small)
   and compared against the source text; mismatches trigger regeneration.
6. **Mux** — `ffmpeg` assembles the final MKV. The original video stream is never
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
| TTS | Chatterbox Multilingual | first engine; Silero and XTTS-v2 planned behind the same interface |
| Verification | faster-whisper small | ASR round-trip check |
| Mux | ffmpeg | atempo fitting, MKV output |

## Hardware targets

- **Primary:** NVIDIA RTX 4080 Mobile, 12 GB VRAM. Stages run sequentially
  (transcribe all → translate all → synthesize all) — heavy models don't fit
  simultaneously.
- **Secondary (later):** Intel Arc B390 iGPU. whisper.cpp (SYCL/OpenVINO) and
  llama.cpp (SYCL) are proven there; Chatterbox on XPU is unproven — Silero on
  CPU is the fallback.

Throughput budget: ≤ x5 video duration. Expected on the 4080M: ~x1–1.5 with
Chatterbox including verification.

## Constraints / assumptions

- Single speaker per video (covers ~95% of target content). No diarization.
- Local only — no cloud STT, translation, or TTS.
- Tempo compression up to x2 is acceptable (validated by ear).

## Status

Documentation phase. No code yet. See `.claude/PLAN.md`.
