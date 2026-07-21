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
  message, don't auto-install. The download stage implements this: `yt-dlp` /
  `ffmpeg` resolve venv-`Scripts`-first, then PATH (`stages/download.py`,
  `_tool_exe`), and a missing tool raises a clear RuntimeError.
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
- **12 GB VRAM budget — a budget, not a prohibition** (revised 2026-07-19, see
  DECISIONS). Keep the resident total under it and account for what is loaded;
  co-residency is allowed when the arithmetic works. Measured: whisper large-v3
  ~3.1 GB, htdemucs ~3.0, F5/ESpeech worker ~0.8, whisper-small ~0.5 — all four
  at once is ~7.4 GB and fits. The one model that makes it tight is
  Gemma-3-12B (~8-9 GB), so on the local translate route free the others around
  it (`translate_unload` POSTs keep_alive:0); the Sonnet route never loads it at
  all. The old blanket "never load two heavy models at once" was an artifact of
  Gemma's size and blocked model reuse across a batch for no VRAM reason.
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
(voice `eugene`, `kseniya` backup) is the fallback — slightly lower quality but needs
no voice sample (adapter default v5_5_ru; v4_ru only to reproduce old runs, DECISIONS 2026-07-19);
Chatterbox was rejected in the day-1 ear test (see DECISIONS). No voice cloning — fixed narrator voice. Don't
hardcode engine specifics outside the engine adapter. Three venvs, never merge them:
`.venv-asr` (pipeline), `.venv-f5tts` (F5 worker), `.venv-demucs` (separate stage);
run the pipeline with `.venv-asr` python via `python -X utf8 -m overdub`.

## Tests

One command, from the repo root:

```powershell
.venv-asr\Scripts\python.exe -m pytest
```

405 tests, ~5 s, no GPU / network / media. `pytest` lives in `.venv-asr` only
(`pip install -e ".[dev]"`); config is `[tool.pytest.ini_options]` in
`pyproject.toml`. **Do not hand-roll a loop over `tests/*.py`** — that was the
state before 2026-07-20 and it produced invented result lines. Run it from the
repo root specifically: `testpaths` only applies there (pytest 8+), so from a
subdirectory you get "no tests ran", not the suite.

A single file still runs standalone — `python -X utf8 tests/test_x.py` — and
prints its own summary. Keep that footer when adding a test file, and keep the
`sys.path.insert` preamble: it is the ONE mechanism that makes both entry points
work, and `pythonpath` in the ini would be a second one that can silently
diverge from it.

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

## Reference

`docs/repair-fixture.md` — the `--repair-asr` golden fixture: a reproducible real-media regression
test built from the 6 preserved `_pre-repair-sentences.json` / `sentences.json` pairs in `work/`.
Read it before changing anything in `overdub/repair.py`, before quoting a recall number for
`--repair-asr auto`, or before scoring the automation against the human transcripts — the human side
contains a known error and a deliberate override, so a perfect match is a red flag, not a win.

`docs/russian-tts-guide.md` — Russian-TTS working reference (user-supplied, July 2026): model
comparison, input preparation (punctuation, normalization, stress dictionary, chunking), Silero
SSML surface, a listening checklist, and a symptom → first-thing-to-check table. Read it before
tuning TTS quality, changing engines, or chasing an intonation/pronunciation complaint. Two
things in it we do not yet use: Silero accepts SSML (`<speak> <p> <s> <prosody> <break>`) while
our adapter sends plain `text=`, and it attributes most prosody quality to the INPUT — flat
ASR+MT punctuation being the main cause of monotone output.

## Artifacts

Planning lives in `.claude/PLAN.md`, rationale in `.claude/DECISIONS.md`,
history in `.claude/CHANGELOG.md`, raw ideas in `.claude/INBOX.md`
(global 4-file framework).
