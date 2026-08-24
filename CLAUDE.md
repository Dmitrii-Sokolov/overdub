# overdub — project instructions

YouTube→Russian dubbing pipeline.

Current stage: polishing. The pipeline must run turn-key
(URL in → final MKV out) with acceptable speed and quality; occasional broken
segments are tolerated.

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
  Intel Arc B390 iGPU.
- External binaries expected but not guaranteed: `ffmpeg` and `yt-dlp`, and
  nothing else — translation left the host at the seam, so no local LLM service
  is part of the stack (STACK Stage 2). Verify availability before assuming;
  fail with a clear message, don't auto-install. The download stage implements
  this: `yt-dlp` / `ffmpeg` resolve venv-`Scripts`-first, then PATH
  (`stages/download.py`, `_tool_exe`), and a missing tool raises a clear
  RuntimeError.

## Hard constraints

- the PRIMARY translate route is Sonnet in
  semi-automatic mode (sub-agents write translation.json at the translate seam;
  runbook: README "Running").
- **The DUBBING routes are EN→RU only.** Source audio is English, the dub is
  Russian; nothing detects a language on the way to an MKV. Two shipped routes
  are deliberately outside that constraint because they translate nothing, so
  the source language is whatever the material is: `--transcribe-file` asks the
  ASR (`transcribefile.py`, `language=None`) and route E detects per video
  (`build_clean.detect_lang`, `--lang en|ru` to override). Neither may be
  "fixed" by feeding it `cfg.source_lang` — that key means "what the dubbing
  pipeline expects" and forcing it onto a Russian source is already an open bug
  on the whisper repair path (INBOX).
- **Single-speaker assumption.** No diarization in v1.
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

yt-dlp → Parakeet-TDT 0.6b v3 → Claude Sonnet (semi-automatic, at the translate seam) →
Silero v5_5_ru → htdemucs no-vocals bed (dub_mix="bed" default) → ffmpeg.

**ASR is Parakeet since 2026-08-06** (`asr_engine`, DECISIONS). It runs in `.venv-parakeet` as a
subprocess worker — one process per stage sweep — because `nemo_toolkit[asr]` pins numpy below the
pipeline's. Three facts about it shape everything downstream:
**it has no VAD**, so the worker runs Silero itself and a video with no speech yields an empty
transcript rather than invented words (measured: 110, 32 and 6 invented words on three silent
videos without the gate); **it drops stretches of real speech** at window boundaries, so the worker
detects uncovered speech spans and re-reads them before writing anything (20 spans over 146 videos,
the largest 41 s); and **it was believed deterministic**, which is why `--repair-asr` refuses on
any engine but whisper — its accept gate is "two readings agree", vacuously true on a decoder that
cannot disagree with itself. **That premise is contested and the refusal rests on it**: two INBOX
measurements (2026-08-07, 2026-08-11) got differing word counts from one byte-identical wav. The
mode stays refused until the rate is measured — do not re-enable it, and do not restate
determinism as settled anywhere.
faster-whisper stays installed in `.venv-asr`: it is the verify round-trip's engine either way, and
`asr_engine = "whisper"` remains a supported fallback. That fallback is why the whisper-only
machinery still exists — but none of it runs on the Parakeet path, and that must stay explicit
rather than accidental: `_guard`/`floor_run_ratio` cannot fire on an 80 ms timestamp grid (measured
0.0 on all 145 videos), so the stage does not call them there instead of leaving a detector that
looks alive and protects nothing. `_dehallucinate` is the exception and DOES still run — Parakeet
produces the same repetition shape whisper does ("That's the seven three" ×15 on a silent file).

TTS engines are pluggable behind an adapter, and **Silero v5_5_ru (voice `eugene`) is THE engine** —
user decision on speed and hardware cost, quality difference accepted as a deliberate trade
(DECISIONS 2026-07-25). The switch is deliberately NOT a parallel-engine setup: per-engine knobs were
declined and shipped defaults are tuned for Silero. Two things Silero forces on the pipeline:
**it silently DELETES Latin script** (verified — a sentence with `Reddit` renders byte-identical to
the same sentence without the word), which is why `text_tts` is Cyrillic-by-contract via the
`pronounce` chain; and **it has no `supports_target`**, so slot fitting is the pipeline's job now.
That job is half done (2026-07-25): `atempo_floor` stretches under-filled units and closed 70% of
the measured silence, while sizing the TRANSLATION to the slot is still open (`tasks/slot-fit.md`). The
duration model those two share is `overdub.tts.voice_rate` / `target_chars` (both in
`overdub/tts/__init__.py`) and is keyed on `tts_voice` —
speaking rate is a VOICE fact (eugene 19.85 ru ch/s vs baya 14.41, measured 2026-07-25 over every
Silero manifest on disk — provenance at the constant) and an unmeasured voice
disables the model rather than borrowing a rate. Adapter default is v5_5_ru; v4_ru only to reproduce old runs
(DECISIONS 2026-07-19). No voice cloning — fixed narrator voice. Don't
hardcode engine specifics outside the engine adapter. Two venvs, never merge them:
`.venv-asr` (pipeline) and `.venv-demucs` (separate stage);
run the pipeline with `.venv-asr` python via `python -X utf8 -m overdub`.

## Tests

One command, from the repo root:

```powershell
.venv-asr\Scripts\python.exe -m pytest
```

Seconds, no GPU / network / media. `pytest` lives in `.venv-asr` only
(`pip install -e ".[dev]"`); config is `[tool.pytest.ini_options]` in
`pyproject.toml`. **Do not hand-roll a loop over `tests/*.py`** — that was the
state before 2026-07-20 and it produced invented result lines. Run it from the
repo root specifically: `testpaths` only applies there (pytest 8+), so from a
subdirectory you get "no tests ran", not the suite.

**Never write the suite SIZE into a document.** It moves with every commit, so
even a DATED copy is wrong within the day — three files carried three different
numbers on 2026-08-03. If a count is needed, take it from the run:
`-m pytest --collect-only -q` prints it without executing anything. A DECISIONS
entry recording a before/after ("641 → 639") is the one legitimate use. This is
the strict end of the general rule under "Artifacts".

A single file still runs standalone — `python -X utf8 tests/test_x.py` — and
prints its own summary. Keep that footer when adding a test file, and keep the
`sys.path.insert` preamble: it is the ONE mechanism that makes both entry points
work, and `pythonpath` in the ini would be a second one that can silently
diverge from it.

## Design rules

- ASR verification (whisper-small round-trip + normalized text similarity) runs on raw
  audio — before atempo — and is **OFF by default since 2026-08-06**
  (`verify_roundtrip`, DECISIONS). It measured 24 flags over 5852 units, of which
  two were real defects, for ~0.94 h of GPU per 123-video batch. Turn it back ON
  to re-measure after any engine, voice or normalization change: it is the only
  detector that HEARS the output, so its flag rate is a statement about the
  engine's health on that day and nothing else can produce one. With it off,
  `run.json` carries `verify.roundtrip: false` and the digest prints
  `verify off` — never `verify 0`, which would claim the audio was heard.
  Failed segments are flagged in the run report; for engines with a random seed,
  retry with a new seed up to N times first (Silero is deterministic — reseeding
  is a no-op, so its failures are flagged directly). The pipeline never blocks on
  a bad segment, never hides one. The completeness text check lives in the same
  stage and is unaffected by the switch.
- All intermediate artifacts (transcript, translation, per-segment audio) are
  persisted to the work dir. Every stage must be resumable and re-runnable in
  isolation — the pipeline is semi-automated by design.
- **A MISSING artifact degrades; an INCONSISTENT one raises** (2026-07-28, see
  DECISIONS). `assemble` with no translation writes `en.srt` off `sentences.json`
  and builds no dub; `mux` requires only `source.mkv` and ships whatever tracks
  exist. Since 2026-08-06 an EMPTY transcript is a third case and is neither:
  `TranslateStage` writes `translation.json` as `[]` itself and says so, because
  an empty translation is the CONSISTENT answer to a video with no speech, not a
  missing artifact. `separate` then skips too (no dub to lay a bed under) and the
  video ships without a dub — so a queue converges, every URL in yielding a
  container out. A transcript that is ABSENT rather than empty still raises: that
  video has not been shown to have no speech. Both announce it loudly and stamp it (`assemble.degraded`, `mux.tracks`,
  `run.json.degraded`, `needs_triage` true) — the export FILENAME is unchanged, so
  the report is the only record. Artifacts that DISAGREE (non-contiguous ids, units
  not covering the ids, a dub with no manifest, `bed` with no bed) still raise: a
  lost track is reportable, a confidently wrong dub is not.
- Translation unit is the sentence (rebuilt from word timestamps), never the
  raw ASR segment: sentences are translated in order with a rolling
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

`docs/queue-contract.md` — what routes B/C/E do IDENTICALLY: `queue.txt` ownership, the `$ids`
block and its three guards, the `# playlist:` freshness diff, promotion between routes, the
derived-artifact-is-not-evidence rule, `Workflow` fan-out and marker verification (B and C — route E
has no marker). A MANDATORY READ before driving any route, and the place to EDIT any of those
rules — it exists because each of them used to live in four skills at once, and a rule copied four
times drifts three ways.

`docs/repair-fixture.md` — the `--repair-asr` golden fixture: a reproducible real-media regression
test built from the 6 preserved `_pre-repair-sentences.json` / `sentences.json` pairs in `work/`.
Read it before changing anything in `overdub/repair.py`, before quoting a recall number for
`--repair-asr auto`, or before scoring the automation against the human transcripts — the human side
contains a known error and a deliberate override, so a perfect match is a red flag, not a win.
Two things it says that this line must not let you miss: the SIX `source.wav` are no longer in
`work/` (a disk cleanup took them; re-fetched into `work-exp/parakeet/fixture/`), and the mode it
tests is whisper-only since 2026-08-06, so the fixture runs only with `asr_engine = "whisper"`.

`scripts/asr_probe.py` — the ASR decode-config probe (`--help` is the runbook; there is no
separate doc, deliberately). Two modes: `--variant` measures one decode variant against the
shipped config on the 6 fixture videos (counterbalanced block order, every variant twice, prints
the same-variant noise floor beside the cross-variant effect, then stops — no adoption rule in
code, the verdict comes from reading the word-stream diffs it writes); `--threads N` measures the
cross-video threading ceiling (N videos decoded concurrently through one `WhisperModel(num_workers=N)`
vs serially, wall-clock, mirrored, mean-based). Read it before quoting any transcribe-speed number.
Adopting a decode change also re-baselines `docs/repair-fixture.md` (the beam is shared with the
repair window). **It measures the WHISPER FALLBACK, not the shipped transcriber** — Parakeet took
that role on 2026-08-06 and has neither a beam nor context feedback, so none of the variants apply
to it; comparing the two engines is `scripts/parakeet_compare.py`. The whisper transcribe-speed
axis remains closed as of 2026-07-24 (all four levers measured, none adopted, fp16 large-v3 at its
practical ceiling), and the engine switch did not reopen it — that closure was always about levers
INSIDE whisper, never a claim that the stage is cheap. It is not: transcribe is 30.5% of pipeline
wall clock over 375 recorded runs (2026-08-06), which is what made a different ENGINE worth 1.4×
end to end.

`scripts/host_guard.py` — pre-flight check: is the GPU free enough to measure on? Run it (or call
`require_idle()`) BEFORE any timed work — `asr_probe.py` already gates both of its measuring paths
on it. Exists because a 2026-07-25 grouping A/B read verify at 347 s and 597 s against a 45 s
baseline and a whole conclusion was drawn from it; a game owned the card at 98%/86 C, and on a
free host the same arms came out 46-58 s, i.e. indistinguishable. Mirrored order does NOT save you
here: counterbalancing cancels slow drift, not a process that holds the card for the entire
session. `--allow-busy-gpu` opts out; a host without nvidia-smi forfeits the guarantee rather than
blocking work.

`docs/russian-tts-guide.md` — Russian-TTS reference (user-supplied July 2026, **cut down
2026-08-03 to what is neither shipped nor refuted**): the punctuation lever, `terms.tsv`, the SSML
tag surface, a listening checklist and a symptom → first-thing-to-check table. Read it before
tuning TTS quality or chasing an intonation/pronunciation complaint — and note that its two halves
are read differently. §1-3 are unpulled LEVERS, of which the biggest is not markup at all: it
attributes ~70% of prosody quality to the INPUT, flat ASR+MT punctuation being the main cause of
monotone output. §4-5 are an INSTRUMENT — the ear is what adjudicates quality in this project, and
that checklist is the only one in the repo. What is NOT in it any more, deliberately: anything the
code already does (normalization, `apply_tts` params, round-trip ASR), the CosyVoice column (no
cloning here, engine closed 2026-07-25), and the licences (now README, "Voices, cloning and the
law"). Two traps it carries: it praises `aidar`, which our own ear ranking rejects — the file says
so inline, ours wins; and `<break>` is NOT an unpulled lever, it was built and REJECTED by ear
(DECISIONS 2026-07-25) and ships off at `silero_ssml_breaks = False`.

## Artifacts — agent-docs format (since 2026-08-24)

Tasks live in `BACKLOG.md` (one line per task → `tasks/<slug>.md`, created lazily), rationale in
`DECISIONS.md`, raw capture in `INBOX.md` (append-only, `- [tag] DATE text`, emptied only by
`/triage`), module-local facts in `overdub/CLAUDE.md`. Shipped work is recoverable from git
history — there is no CHANGELOG file, and there is no PLAN.md any more (dissolved 2026-08-24,
DECISIONS). Two rules bind every session: findings and ideas are APPENDED to `INBOX.md` and
nothing there is reordered or rewritten; an executor never writes `BACKLOG.md` or `DECISIONS.md`
— that is `/triage` alone (the one exception: ticking your own BACKLOG line on completion).

**Deliberate deviation:** `DECISIONS.md` is a single file — a hand-maintained one-line Index
plus dated entries as the detail, guarded by `tests/test_decisions_index.py` — not the bare
index the format specifies. "DECISIONS YYYY-MM-DD" citations across code and docs resolve by
grep against the dated entries; keep citing that way.

**A measured number in prose carries its date, or it is not written.** Figures
rot silently while still reading as current: the ~72 s/video model-loading
saving outlived the stage walls it came off and was quoted in two files after
that, and the suite size was wrong in three. DECISIONS is the one place a bare
number is safe — an entry there is dated by construction and never re-read as
current. Everywhere else: date it inline, or point at the entry that does. This
covers code comments too — `scripts/asr_probe.py --help` is a runbook, and a
number in it rots exactly like one in a `.md`. One figure a date does NOT
rescue: the test-suite size, which is stale within the day, so it is not
written at all (see "Tests"). A number quoted in order to RETIRE it is not a
measurement in prose and needs no date of its own — mark it retired instead.
It follows that retiring a figure means grepping for the NUMBER, not for the
component it described — the component keeps its name across the change that
invalidated the measurement.
