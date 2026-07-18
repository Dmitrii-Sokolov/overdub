# overdub

Local-first, semi-automated pipeline for dubbing YouTube videos into Russian.

Download → transcribe → translate → synthesize → verify → assemble → mux.
Every stage runs on local
hardware — no cloud APIs, no per-minute billing. Built for batch processing of
hundreds of hours of single-speaker content.

## Pipeline

1. **Download** — `yt-dlp` fetches the video.
2. **Transcribe (STT)** — `faster-whisper` (large-v3) produces the English
   transcript with word timestamps; words are re-assembled into sentences with
   `[start, end]`. The sentence is the unit of translation, synthesis and sync.
3. **Translate** — sentence by sentence with a rolling context window
   (previous EN sentences + their RU translations), prompted to keep length
   close to the original (it's dubbing, not prose). Output per sentence: raw RU
   for subtitles + normalized RU (numbers, acronyms, Latin terms spelled out)
   for TTS. Two good routes (DECISIONS 2026-07-18): **local** — Gemma-3-12B via
   Ollama, the in-pipeline default (good quality, free, offline, slow);
   **primary** — Claude Sonnet in semi-automatic mode (sub-agent workflow;
   subscription, better quality, much faster — it replaces the pipeline's
   heaviest stage). See "Running" below.
4. **Synthesize (TTS)** — ESpeech-TTS-1_RL-V2 (F5-TTS, worker process in its
   own venv) renders Russian audio. Adjacent sentences group into render units
   for natural prosody; native speed slot-fills each unit's time span. The
   narrator is a fixed reference clip (see "Voices" below) — one voice for every
   video, no per-speaker cloning. Each fresh unit is round-tripped through
   whisper-small in-stage; low similarity triggers reseed-retry (keep-best).
   Silero v4_ru (`eugene`, CPU) is the fallback engine.
5. **Verify** — the independent judge: every render unit is transcribed back
   with whisper-small and compared against the normalized TTS text (the same
   normalizer on both sides); failures are flagged in the run report — never
   hidden, never blocking. Runs on raw audio, before any speed-up.
6. **Separate + Mux** — htdemucs extracts a no-vocals bed from the original
   audio; the RU track is the dub laid over that bed at original level
   (`dub_mix = "bed"`, production default; `replace`/`duck` available). `ffmpeg`
   fits each unit into its slot (`atempo`, uncapped — extreme speed factors are
   logged, not fixed), aligns dub loudness to the original and muxes the final
   MKV. The original video stream is never re-encoded.

## Running

Prereqs (SETUP.md): `.venv-asr` + `.venv-f5tts` (+ `.venv-demucs` for the
default bed mix), F5 assets under `models/`, `ffmpeg`/`yt-dlp` on PATH.

### A. Batch with local translation (Gemma) — fully turn-key

Needs Ollama serving `gemma3:12b` on localhost. Agent or human:

```powershell
# queue.txt: one URL per line; '#' comments and blank lines are skipped
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt
```

- Final MKVs land in `out/` as `"<title> [<video id>].mkv"`; per-video
  artifacts in `work/<id>/`. Single video: same command with a URL instead of
  `--batch`.
- Interrupt/resume: re-run the same command — completed stages fast-skip.
  Graceful stop: create `work/STOP`. Exit codes: 0 ok / 1 any fail / 2 usage /
  3 stop-halt.
- Morning triage: `work/<id>/report.json` — any `*_flag`, or
  `speed_factor > 1.8`.

### B. Batch with Sonnet translation (semi-automatic — the primary route)

Translation is just an artifact (`translation.json`), so the pipeline stops
cleanly at the translate seam and resumes from it. No Ollama needed.

1. **Transcribe the batch:**

   ```powershell
   .venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --only download transcribe
   ```

   → per video: `work/<id>/sentences.json`.

2. **Translate with Sonnet sub-agents** (one per video). Each agent reads
   `sentences.json` and writes `work/<id>/translation.json` under the translate
   contract:
   - a JSON list, one record per sentence, id-contiguous:
     `{id, start, end, src_en, text_ru, text_tts, status: "ok", attempts: 1}`;
   - translation rules = the `SYSTEM` prompt in `overdub/stages/translate.py`
     (keep RU close in length, game/brand names stay Latin, numbers stay
     digits, rolling context);
   - `text_tts` MUST come from Python — `overdub.normalize.normalize_for_tts(text_ru)`
     — never spelled by the LLM (verify compares through the same normalizer);
   - gate each line with `overdub.stages.translate._is_bad` before accepting.

3. **Resume the batch** with the exact command from route A — download/
   transcribe/translate skip (artifacts exist), synthesize → verify → assemble
   → separate → mux run as usual.

Both routes are good: Gemma gives good quality locally and slowly; Sonnet needs
a subscription and gives better quality in the cloud, much faster.

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
| Translation | Gemma-3-12B via Ollama · Claude Sonnet (semi-auto) | local default · primary cloud route (DECISIONS 2026-07-18) |
| TTS | ESpeech-TTS-1_RL-V2 (F5-TTS) | GPU worker in `.venv-f5tts`; pluggable adapter; Silero v4_ru (CPU) is the fallback |
| Verification | faster-whisper small | ASR round-trip check |
| Separation | htdemucs (Demucs) | no-vocals bed for the mix, `.venv-demucs` |
| Mux | ffmpeg | atempo fitting, bed mix, MKV output |

## Hardware targets

- **Primary:** NVIDIA RTX 4080 Mobile, 12 GB VRAM. Stages run sequentially per
  video with explicit model unload between them — heavy models don't fit
  simultaneously. (Per-stage batching across many videos — one model load per
  stage — is a Phase 2 option.)
- **Secondary (deferred):** Intel Arc B390 iGPU. whisper.cpp (SYCL/OpenVINO) and
  llama.cpp (SYCL) are proven there for STT/translation; F5 on XPU is an
  unproven spike — Silero (CPU) would be the safe TTS there. See PLAN deferred.

Throughput budget: ≤ x5 video duration — measured ~×1.3 realtime end-to-end on
the host (budget cleared ~3.8×). Translation is the bottleneck on the local
route (~45% of wall-clock; the Sonnet route removes it); synthesis+verify is
the co-bottleneck (F5 at ~0.7 GiB VRAM).

## Constraints / assumptions

- Single speaker per video (covers ~95% of target content). No diarization.
- Local STT and TTS, always. Translation has two good routes (DECISIONS
  2026-07-18): local Gemma (in-pipeline default) and Claude Sonnet in
  semi-automatic mode — the primary route (subscription, better quality, much
  faster). Cloud is always explicit, never a silent fallback.
- Source is always English, output is always Russian.
- No tempo compression cap — segments are sped up as much as their slot
  requires; occasional broken segments are acceptable losses (PoC).
- Fixed narrator voice (an F5 reference clip) — "same voice as the speaker"
  (cloning the source speaker cross-lingually) was dropped after the day-1
  engine bake-off; Silero `eugene` is the fallback narrator.

## Voices, cloning and the law

The TTS engine is a zero-shot voice cloner: the narrator voice is defined by a
short reference clip (5–12 s + its exact transcript), not baked into the model.
That flexibility comes with rules. This section is not legal advice.

- **Every voice sample shipped in or referenced by this repository is public
  domain** — cut from [LibriVox](https://librivox.org) recordings, which their
  volunteer readers explicitly dedicate to the public domain. The same voices
  have powered open TTS research datasets (LibriTTS, M-AILABS) for a decade.
- **If you want to use anyone else's voice, study the law of your jurisdiction
  first.** EU member states and Canada protect a person's voice from
  unauthorized *public* use (personality rights in the EU, the appropriation
  of personality tort and Quebec Civil Code art. 36 in Canada). From August
  2026 the EU AI Act additionally requires published synthetic media that
  resembles a real person to be labeled as AI-generated. Russia has a pending
  bill (draft art. 152.3 of the Civil Code) to the same effect.
- **Purely personal, private use is generally outside these regimes** (GDPR
  household exemption, private-copying exceptions, publication-based torts) —
  synthesizing a voice for your own local listening is broadly tolerated,
  provided the reference clip comes from a lawful source. Publishing the
  result is a different matter entirely: don't, unless the voice is yours,
  licensed, or public domain.
- **Default narrator reference:** the demo clip from the ESpeech author's HF
  Space ([Den4ikAI/ESpeech-TTS](https://huggingface.co/spaces/Den4ikAI/ESpeech-TTS),
  `ref/example.mp3`) — the best-sounding voice across our narrator auditions.
  Its rights are **not clarified** (a real person's voice, unknown provenance),
  so the clip is not committed to this repository: it is fetched from the Space
  at setup time, and anything synthesized with it stays personal-use only.
  Public-domain fallback narrators (LibriVox readers) are recorded in
  `.claude/DECISIONS.md` and re-creatable with `scripts/lv_pick_refs.py`.
- **Repository policy:** only public-domain reference samples are committed
  here, and the documentation stays person-agnostic — no instructions for
  cloning any specific individual's voice.

## Status

Research / proof of concept — the pipeline runs turn-key (URL in → MKV out) on
real videos, batch mode included. Closed: Phase 1 MVP, the F5/ESpeech engine
migration, dead-air elimination, batch queue + stop switch, proper-noun
pronunciation, the segmentation root fix, and the Gemma-3-12B translator swap
(2026-07-18). Current roadmap: `.claude/PLAN.md`; rationale history:
`.claude/DECISIONS.md`. Setup: `SETUP.md`; verified stack facts: `STACK.md`.
