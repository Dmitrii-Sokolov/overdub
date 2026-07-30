# overdub — project instructions

Local-first YouTube→Russian dubbing pipeline. Python. Every processing stage
must run on local hardware.

Current stage: research / proof of concept. The pipeline must run turn-key
(URL in → final MKV out) with acceptable speed and quality; occasional broken
segments are tolerated, silent failures are not.

**The deliverable is the TOOL, never a particular video.** Every MKV in `work/`
and `out/` is a test fixture that happens to be watchable. So a defect in a
shipped video is an input signal about the pipeline, not a repair ticket:
fix the CLASS and let the next batch come out right. Do not re-run, re-repair,
re-translate or re-synthesize an individual video to make that video better —
the only thing that justifies touching a finished one is a MEASUREMENT that
generalizes (a number, an ear verdict, a fixture), and then the artifact is a
by-product, not the point. Same rule reversed: intermediate artifacts are
consumables, so anything that persists a generalizable finding (the golden
fixture, `_pre-repair-*.json` pairs, `work-exp/` baselines) outranks the videos
themselves. Rationale: DECISIONS 2026-07-25.

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
  ~3.1 GB, htdemucs ~3.0, whisper-small ~0.5 — and TTS costs nothing on the
  shipped engine (Silero is CPU; the opt-in F5 worker would add ~0.8). The
  default resident set is ~6.6 GB and fits. The one model that makes it tight is
  Gemma-3-12B (~8-9 GB), so on the local translate route free the others around
  it (`translate_unload` POSTs keep_alive:0); the Sonnet route never loads it at
  all. The old blanket "never load two heavy models at once" was an artifact of
  Gemma's size and blocked model reuse across a batch for no VRAM reason.
- **No tempo cap upward; a floor downward.** `atempo` speeds a segment up as
  much as its slot requires — uncapped, by design. Since 2026-07-25 it also
  SLOWS an under-filled unit toward its slot, bounded by `atempo_floor` (0.75,
  an ear verdict: degradation starts at 0.65). Both directions apply at
  assembly, always after verification, never before, and strictly inside the
  unit's own slot — the dub's timeline is identical at every floor, so picture
  sync never depends on this knob. Per-segment speed factor goes to the run
  report; audibly broken segments are acceptable losses, silent ones are not.
- **Output is MKV** with original audio, RU dub, EN subs, RU subs. The original
  video stream is never re-encoded. Since 2026-07-28 only the VIDEO is required:
  a missing dub or srt costs that track, not the artifact (see Design rules).

## Stack (v1)

yt-dlp → faster-whisper large-v3 → Gemma-3-12B (Ollama) → Silero v5_5_ru →
htdemucs no-vocals bed (dub_mix="bed" default) → ffmpeg.

TTS engines are pluggable behind an adapter, but **as of 2026-07-25 Silero v5_5_ru (voice `eugene`)
is THE engine, not the fallback** — user decision on speed and hardware cost, quality difference
accepted as a deliberate trade (DECISIONS 2026-07-25; reverses the 2026-07-16 verdict that made F5
production). The switch is deliberately NOT a parallel-engine setup: per-engine knobs were declined,
shipped defaults are tuned for Silero, and the F5 path comes back out of git history if it fails.
ESpeech-TTS-1_RL-V2 (F5-TTS, worker in `.venv-f5tts`) still works and is still what old runs used;
Chatterbox was rejected in the day-1 ear test. Two things Silero forces on the pipeline:
**it silently DELETES Latin script** (verified — a sentence with `Reddit` renders byte-identical to
the same sentence without the word), which is why `text_tts` is Cyrillic-by-contract via the
`pronounce` chain; and **it has no `supports_target`**, so slot fitting is the pipeline's job now.
That job is half done (2026-07-25): `atempo_floor` stretches under-filled units and closed 70% of
the measured silence, while sizing the TRANSLATION to the slot is still open (PLAN, "Slot fit"). The
duration model those two share lives in `overdub/tts/voice_rate` and is keyed on `tts_voice` —
speaking rate is a VOICE fact (eugene 19.85 ru ch/s vs baya 14.41) and an unmeasured voice
disables the model rather than borrowing a rate. Adapter default is v5_5_ru; v4_ru only to reproduce old runs
(DECISIONS 2026-07-19). No voice cloning — fixed narrator voice. Don't
hardcode engine specifics outside the engine adapter. Three venvs, never merge them:
`.venv-asr` (pipeline), `.venv-f5tts` (F5 worker), `.venv-demucs` (separate stage);
run the pipeline with `.venv-asr` python via `python -X utf8 -m overdub`.

## Tests

One command, from the repo root:

```powershell
.venv-asr\Scripts\python.exe -m pytest
```

~580 tests, ~6 s, no GPU / network / media. `pytest` lives in `.venv-asr` only
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
- **A MISSING artifact degrades; an INCONSISTENT one raises** (2026-07-28, see
  DECISIONS). `assemble` with no translation writes `en.srt` off `sentences.json`
  and builds no dub; `mux` requires only `source.mkv` and ships whatever tracks
  exist. Both announce it loudly and stamp it (`assemble.degraded`, `mux.tracks`,
  `run.json.degraded`, `needs_triage` true) — the export FILENAME is unchanged, so
  the report is the only record. Artifacts that DISAGREE (non-contiguous ids, units
  not covering the ids, a dub with no manifest, `bed` with no bed) still raise: a
  lost track is reportable, a confidently wrong dub is not.
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

`scripts/asr_probe.py` — the ASR decode-config probe (`--help` is the runbook; there is no
separate doc, deliberately). Two modes: `--variant` measures one decode variant against the
shipped config on the 6 fixture videos (counterbalanced block order, every variant twice, prints
the same-variant noise floor beside the cross-variant effect, then stops — no adoption rule in
code, the verdict comes from reading the word-stream diffs it writes); `--threads N` measures the
cross-video threading ceiling (N videos decoded concurrently through one `WhisperModel(num_workers=N)`
vs serially, wall-clock, mirrored, mean-based). Read it before quoting any transcribe-speed number.
Adopting a decode change also re-baselines `docs/repair-fixture.md` (the beam is shared with the
repair window). **The transcribe-speed axis is CLOSED (2026-07-24): all four levers measured, none
adopted — fp16 large-v3 on one GPU is at its practical ceiling (DECISIONS 2026-07-24). Do not
re-run these probes to "improve transcribe speed"; reopening needs different hardware or a smaller
model cleared by ear.**

`scripts/host_guard.py` — pre-flight check: is the GPU free enough to measure on? Run it (or call
`require_idle()`) BEFORE any timed work — `asr_probe.py` already gates both of its measuring paths
on it. Exists because a 2026-07-25 grouping A/B read verify at 347 s and 597 s against a 45 s
baseline and a whole conclusion was drawn from it; a game owned the card at 98%/86 C, and on a
free host the same arms came out 46-58 s, i.e. indistinguishable. Mirrored order does NOT save you
here: counterbalancing cancels slow drift, not a process that holds the card for the entire
session. `--allow-busy-gpu` opts out; a host without nvidia-smi forfeits the guarantee rather than
blocking work.

`docs/digest-reference.md` — the route-D scoring fixture (user-supplied, 2026-07-30): a hand-written
Russian digest of `work/fGKNUvivvnc`, the ONE video whose digest can be measured rather than admired.
Carries the six findings to count, the rule that a perfect match is a red flag (the reference author
watched the video; the pipeline reads an ASR transcript), and why the prompt's examples describe an
invented video — the first draft used this document's own headline and two bullet titles, handing the
agent two of the six answers on exactly the video used to judge it. Read it before changing anything
in `.claude/workflows/digest-videos.js` or quoting a recall number for route D.

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
