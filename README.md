# overdub

Local-first, semi-automated pipeline for dubbing YouTube videos into Russian.

Download → transcribe → translate → synthesize → verify → assemble → separate → mux.
Every stage but one runs on local hardware with no per-minute billing; the exception is
translation, which left the host at the seam and is written by Claude Sonnet sub-agents.
Built for batch processing of hundreds of hours of single-speaker content.

**This file is the MAP and the commands.** Rationale and measurements live in
`DECISIONS.md` (index) + `docs/decisions-log.md` (entries), open work in `BACKLOG.md`, host findings in `STACK.md`, install in
`SETUP.md`, and the step-by-step for each route in that route's skill under `.claude/skills/`.
Nothing here restates any of them — a number or a procedure copied into this file is a number or
a procedure that will be wrong here first.

## Pipeline

1. **Download** — `yt-dlp` fetches the video (audio-only under `--transcribe-only`). A thumbnail
   rides along with the fetch and is scaled to `work/<id>/thumb.jpg` for the report pages.
2. **Transcribe** — Parakeet-TDT 0.6b v3 (NVIDIA NeMo) produces the English transcript with word
   timestamps; words are re-assembled into sentences with `[start, end]`. The sentence is the unit
   of translation, synthesis and sync. It runs in `.venv-parakeet` as a subprocess worker and
   brings two needs of its own: a Silero VAD gate, without which it invents words on non-speech,
   and a coverage check that re-reads speech it dropped at a window boundary.
   `asr_engine = "whisper"` switches back to `faster-whisper` large-v3, which stays installed
   because verify uses it either way.
3. **Translate** — **produced at the seam, not in-process.** `work/<id>/translation.json` has to
   exist before the pipeline can continue, and Sonnet sub-agents write it (route B). Output per
   sentence: raw RU for subtitles + normalized RU for TTS. The rules and both schemas are
   [`translate-contract.md`](.claude/skills/overdub-sonnet-batch/references/translate-contract.md);
   the source of truth for the rules themselves is `SYSTEM` in `overdub/stages/translate.py`.
4. **Synthesize** — Silero v5_5_ru (`eugene`, CPU) renders Russian audio. One fixed narrator voice
   for every video, no cloning, no voice sample. Adjacent sentences group into render units for
   natural prosody. Silero is deterministic and has no native slot fitting, which shapes the two
   stages below: there is nothing to reseed, and timing fit is the pipeline's job.
5. **Verify** — the round-trip judge: each render unit is transcribed back with whisper-small and
   compared against the normalized TTS text. **It ships OFF** (`verify_roundtrip = false`) — it is
   an instrument to switch on after an engine, voice or normalization change, not a per-run cost.
   With it off `run.json` says `verify.roundtrip: false` and the digest prints `verify off`, never
   `verify 0`. The completeness text check is separate and always runs. Failures are flagged in the
   run report — never hidden, never blocking.
6. **Assemble** — `ffmpeg` fits each unit into its slot with `atempo`: speeding up is UNCAPPED
   (extreme factors are logged, not fixed), slowing an under-filled unit is bounded by
   `atempo_floor`. Both stay strictly inside the unit's own slot, so the dub's timeline — and
   picture sync — is unaffected by the setting.
7. **Separate** — htdemucs extracts a no-vocals bed from the original audio (`dub_mix = "bed"`,
   the production default; `replace`/`duck` skip this stage). Long audio is chunked with an
   overlap blend; the wall it works around is host RAM, see STACK.
8. **Mux** — dub loudness is aligned to the original and the final MKV is written. **The original
   video stream is never re-encoded.** Where the dub covers nothing, the ORIGINAL audio plays
   through instead of the bare bed.

Subtitles: `en.srt` carries the original timings (it transcribes the English track the MKV still
ships), while `ru.srt` follows the DUB — each cue opens where its audio actually landed, since
grouping makes a unit's speech continuous and a source-timed cue would drift from the voice
reading it. The reason the EN side is deliberately not re-timed is in `assemble._ru_cue_rows`.

## Routes

| | question it answers | ends in | driven by |
|---|---|---|---|
| **B** — dub | "voice this over in Russian" | MKV in `out/` | [`overdub-sonnet-batch`](.claude/skills/overdub-sonnet-batch/SKILL.md) |
| **E** — clean | "let me read it instead of watching" | `work/<id>/clean.md` | [`overdub-clean`](.claude/skills/overdub-clean/SKILL.md) |
| `--transcribe-file` | "I have a file, give me its text" | one `.md` beside the file | nothing; it is one command |

Route B is the only route that ends in a dub. E leaves a video **untranslated, not
half-translated**, so it promotes into B with no cleanup.

## Running

Prereqs (SETUP.md): `.venv-asr`, `.venv-parakeet`, `.venv-demucs` (for the default bed mix),
`ffmpeg` on PATH. Silero runs inside `.venv-asr` and needs no assets under `models/`. `yt-dlp` is
resolved from `.venv-asr\Scripts` first, PATH second; both tools are preflighted with a clear
error instead of a raw WinError 2.

**Two documents own everything a route does not own itself.**
[`docs/queue-contract.md`](docs/queue-contract.md) is what routes B and E do IDENTICALLY —
resolving `queue.txt` into an id list, deciding whether that queue is still current, promoting it
between routes, fanning sub-agents out — and it is a mandatory read for whoever drives a route.
Each route's own skill owns its gates, resume filters and reports. The sections below carry the
COMMANDS and the artifact contract; they are deliberately not a second copy of either.

### Batch mechanics (shared by every route that ends in an MKV)

```powershell
# queue.txt: one URL per line; '#' comments and blank lines are skipped
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt
```

- Final MKVs land in `out/` as `"<title> [<video id>].mkv"`; per-video artifacts in `work/<id>/`.
  Single video: same command with a URL instead of `--batch`.
- **Interrupt/resume: re-run the same command** — completed stages fast-skip. Graceful stop:
  create `work/STOP`. Exit codes: 0 ok / 1 any fail / 2 usage / 3 stop-halt.
- **A batch runs stage-major**: every video through `download`, then every video through
  `transcribe`, and so on, so each model loads once per BATCH instead of once per video. The trade
  is that no MKV is finished until late in the run; a failed video drops out of the remaining
  stages without affecting the others, and the summary says which stage it died on. `--video-major`
  restores the old order and produces byte-identical audio. Download is the exception — it runs as
  a concurrent pre-pass (`download_concurrency`) before the sweep.
- **A MISSING artifact degrades; an INCONSISTENT one raises.** No translation → `en.srt` off the
  transcript and no dub; `mux` needs only `source.mkv` and ships whatever tracks exist. An EMPTY
  transcript is neither — a video with no speech gets `translation.json` as `[]` from the pipeline
  itself and ships without a dub, so a queue always converges. Artifacts that DISAGREE still raise:
  a lost track is reportable, a confidently wrong dub is not. Every degrade is stamped
  (`assemble.degraded`, `mux.tracks`, `run.json.degraded`, `needs_triage`) — the export filename is
  unchanged, so the report is the only record.

### Reports and triage

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\run_report.py --queue queue.txt    # text digest
.venv-asr\Scripts\python.exe -X utf8 scripts\queue_report.py --queue queue.txt  # the queue page
```

- `work/<id>/run.json` is the per-run rollup (timings/RTF, flag counts by type, speed distribution,
  `needs_triage`); `work/<id>/report.json` is the raw record behind it. For a batch the CLI also
  prints a sweep after the summary.
- `queue_report.py` writes **one page per queue**, `work/queue-report.html`: a card per video, and —
  once a queue is (partly) dubbed — the batch-table rows, the flagged units with
  an inline audio player each (expected vs whisper-heard, click to listen) and the source-anomaly
  block. Row order is the queue's, never sorted. Audio is base64-embedded by default; `--link`
  keeps the page small but ties it to this machine. **A published copy built with `--link` shows
  silent players by design: dub audio is never uploaded** (narrator rights, DECISIONS). The output
  is a body fragment, so it publishes as a Claude Artifact unchanged and still opens locally.
- **Two clocks per stage, and they answer different questions — do not sum them.** `timings.json`
  keeps `stages[x]` (the wall clock including the model load, i.e. what the run cost) and
  `detail[x]` (what the stage measured about ITSELF). `run.json.timings` publishes `rtf` off the
  full wall and `rtf_work` off the load-excluded total. **Compare builds on `rtf_work`; report cost
  as `rtf`.** The arithmetic that is legal on those two, and why, is DECISIONS 2026-07-22
  ("Overhead is SUBTRACTED per stage"); the fields themselves are documented in `overdub/timings.py`.
- `detail.transcribe` also carries the run's decode PROVENANCE (`asr_key`), which is not a timing
  at all: a later run WARNS when the stamped model, compute type or beam differs from the current
  config, because that run will fast-skip transcribe and keep the old transcript. Mechanics:
  `overdub/asr.py`.

### B. Dub a queue (the only route that ends in an MKV)

Translation is just an artifact, so the pipeline stops cleanly at the translate seam and resumes
from it.

```powershell
# 1. transcribe the batch — no translation yet
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --only download transcribe

# 2. the seam: Sonnet sub-agents write work/<id>/translation.draft.json, then
.venv-asr\Scripts\python.exe -X utf8 scripts\build_translation.py "work\<id>"

# 3. resume — download/transcribe/translate fast-skip, the rest runs
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt
```

**Step 2 is what the skill exists for.** It fans the sub-agents out through a `Workflow`, applies
the resume filters, splits a transcript too long for one agent into chunks, and overlaps each
video's tail with the wave via `scripts/drain.py` instead of waiting for the whole wave to land.
Do not improvise it from this page.

The division of labour at the seam is the load-bearing part: **the sub-agent writes only judgement**
(`text_ru` and a `src` reading of the English source), and `build_translation.py` owns everything
mechanical — it copies `src_en`/timings from `sentences.json`, derives `text_tts` through the
pipeline's own normalizer (never the LLM's spelling, because verify compares through that same
function), gates each line, and enforces id-contiguity so a malformed draft fails loud instead of
reaching synthesize. Full schemas and the `src` vocabulary:
[`translate-contract.md`](.claude/skills/overdub-sonnet-batch/references/translate-contract.md).

### E. Clean a queue into readable text — no summary, no dub

The output is the video's own words, roughly as long as the source, cleaned enough to read:
`work/<id>/clean.md`.

**English or Russian, and the route detects which.** Nothing is translated here, so the source
language is whatever the video is; `build_clean.py --plan` stamps `lang` into the plan and
`--lang en|ru` overrides it. A transcript that is neither clearly one nor the other is **refused**
rather than guessed at. `cfg.source_lang` is deliberately not consulted — it means "what the
dubbing pipeline expects".

```powershell
# 1. transcribe the queue: audio-only download → transcribe → stop
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --transcribe-only
# 2. plan the cut (per video), fan the chunks out through the skill's workflow, then join
.venv-asr\Scripts\python.exe -X utf8 scripts\build_clean.py "work\<id>" --plan
.venv-asr\Scripts\python.exe -X utf8 scripts\build_clean.py "work\<id>"
```

`--transcribe-only` is its own mode, not a composition: combining it with `--only` or
`--repair-asr` is a usage error, refused before any side effect. Its fetch is `-f bestaudio` with
no `/best` fallback on purpose — a source with no audio-only format FAILS out of the pass rather
than quietly pulling a full video stream, and a 100-video queue costs a few GB instead of ~100 GB
in hour 0.

One sub-agent per CHUNK, not per video: this is the one route whose output is as long as its input,
and a per-video agent cleans the opening faithfully and compresses harder the further it goes with
nothing in the artifact saying which half you are reading. `build_clean.py` owns the cut and the
same function re-derives it at join time, so a plan and its assembler cannot disagree.

**This is the only checkable route in the repo, and the contract is what makes it so:** output and
input are the same language in the same sentence order, so **every id must come back**. An emptied
line is written `""`; an absent id fails the build, because the two are indistinguishable in a text
file afterwards. The join then warns — never blocks — on length ratios, dropped digit runs, dropped
capitalised terms, the share of emptied lines, and a chunk whose **script changed**. That last one
is what catches a translated chunk, and it is the only check that can: a translated chunk is
complete, correctly numbered and about the right length, so every other signal passes it.

The entity check is precise here for a reason that does **not** generalise: same-language cleaning
keeps a name a name. That is exactly the objection that deleted `completeness.entity_loss` on the
translate seam (DECISIONS 2026-08-01) — do not port these detectors there. It stays **Latin-only
even on Russian**, which is a measurement and not an oversight: on a Russian technical talk
(2026-08-14) the shipped pattern found 155 unique real terms, because the speaker says them in
English, while a Cyrillic extension added 23 of which about half were ASR debris.

`clean.md` carries a metadata header and timecoded paragraphs broken on the speaker's own pauses.
Those thresholds are hypotheses sited on speech rhythm, not measured constants.

### Transcribing a local file (any language)

One file in, one markdown document out — no URL, no queue, no dub:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --transcribe-file "D:\In\clip.mp4"
```

Writes `D:\In\clip.transcript.md` (override with `--out`): a header carrying the runtime and the
`asr_key` that decoded it, then one timecoded line per sentence. A file with no speech gets a
document that says so, never an empty one.

**Not EN→RU.** There is no translation here, so the source language is whatever the file happens to
be: Parakeet detects it and cannot be told otherwise, and on `asr_engine = "whisper"` the decode
asks for whisper's own detector rather than `source_lang`.

It runs no stages and owns no workdir — every stage-selecting flag (`--force`, `--only`,
`--transcribe-only`, `--repair-asr`) is refused rather than ignored, and nothing is left behind
but the document.
Sentence splitting is the transcribe stage's own `resegment`, so a sentence here is a sentence
there.

### Repairing an ASR defect

**Whisper-only.** `--repair-asr` refuses when `asr_engine` is anything else: its accept gate is
"two independent readings of the clip agree", which is evidence only because whisper's temperature
fallback samples (DECISIONS 2026-08-06). On the default engine the equivalent job is done inside
the transcribe worker, which finds speech spans it left uncovered and re-reads them before writing
anything — see `holes` and `hole_words_recovered` in the run report. Everything below applies with
`asr_engine = "whisper"` set.

When whisper collapses — a repetition loop, or a sentence stamped onto an impossible span — the fix
is not a full re-transcription but an isolated re-read of the defect window. Run it after
`--only download transcribe` and before translating; dry-run first:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --repair-asr auto --repair-dry-run
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --repair-asr auto
```

Repair clips the window out of `source.wav` — widened by whole SENTENCES, because a collapsed
sentence's own span is bogus — reads it twice (context feedback off and on) and **accepts only if
the two readings say the same words**. On accept it merges the window into its own reading verbatim
(**delete, do not invent**), renumbers every id so they stay contiguous and never drops one, keeps
the original at `work/<id>/_pre-repair-sentences.json` (written once, never clobbered), preserves
the source-anomaly worklist at `work/<id>/_pre-repair-translation.json`, and deletes exactly the
artifacts downstream of `sentences.json`. Timestamps land on the absolute timeline of `source.wav`,
not the clip's. It never re-runs a stage itself — the next ordinary run redoes translate → mux
honestly. `words.json` is deliberately left alone: it is the raw record of what the ASR actually
did.

A **rejection means the two readings disagreed**, i.e. whisper is still guessing there. Re-running
reproduces it exactly, so it needs ears, not a retry.

`--repair-asr 23,24,25` takes explicit ids (single video only). It is **stronger than `auto`**, not
a legacy convenience: the two detectors behind `auto` are blind to a hallucinated word that splits
one sentence into two plausible halves, so "no defect windows" is not "the transcript is clean".
An accepted repair renumbers ids — re-derive them before a second explicit pass.

Regression testing this path: [`docs/repair-fixture.md`](docs/repair-fixture.md).

## Tests

```powershell
.venv-asr\Scripts\python.exe -m pytest
```

Seconds, not minutes. No GPU, no network, no media, no model downloads — everything is pure logic
over temp dirs and injected stages, which is what makes a bare `pytest` safe to run at any time,
including while a batch is on the GPU.

**Run it from the repo root**: `testpaths` only applies when the invocation directory is the
rootdir (pytest 8+), so elsewhere you get "no tests ran". `pytest` is installed in `.venv-asr` only
(`pip install -e ".[dev]"`); configuration is `[tool.pytest.ini_options]` in `pyproject.toml`,
where what is load-bearing rather than cosmetic is collection scope — `testpaths` and
`norecursedirs` keep the in-repo venvs out.

**The suite size is not written down anywhere on purpose** (the rule and its rationale are in
CLAUDE.md, "Tests"). The run is the only answer, and `--collect-only -q` gives it without executing
anything. Every file also stays directly runnable and prints its own summary
(`python -X utf8 tests\test_queue_report.py`); both entry points work off the same
`sys.path.insert` preamble inside each test file, and there is deliberately no `pythonpath` in the
ini, because a second mechanism could silently diverge from the first.

## Output layout (MKV)

| Stream | Content |
|---|---|
| Video | original (stream copy) |
| Audio 1 | original |
| Audio 2 | Russian dub |
| Subtitles 1 | English — original transcript (SRT) |
| Subtitles 2 | Russian — translation (SRT) |

The transcript and translation already exist as pipeline artifacts, so both are embedded as
subtitle tracks for free. Since 2026-07-28 only the VIDEO is required: a missing dub or srt costs
that track, not the artifact.

## Stack

| Stage | Tool | Notes |
|---|---|---|
| Download | yt-dlp | player client is pinned — see STACK |
| STT | Parakeet-TDT 0.6b v3 (NeMo) | CUDA, `.venv-parakeet` subprocess worker; Silero VAD gate + uncovered-speech re-read |
| STT fallback | faster-whisper large-v3 | CUDA, `asr_engine = "whisper"` |
| Translation | Claude Sonnet (semi-auto, at the seam) | sub-agents write `translation.json`; the pipeline resumes from it |
| TTS | Silero v5_5_ru (`eugene`) | THE engine — CPU, in `.venv-asr`, no voice sample, deterministic |
| Verification | faster-whisper small | round-trip check, **ships off** |
| Separation | htdemucs (Demucs) | no-vocals bed for the mix, `.venv-demucs` |
| Mux | ffmpeg | atempo fitting, bed mix, MKV output |

## Hardware

- **Primary:** NVIDIA RTX 4080 Mobile, 12 GB VRAM. A model's lifetime is one stage sweep, so peak
  VRAM is the largest single model rather than the sum — which is what makes one model load per
  BATCH safe. **TTS costs no VRAM at all** (Silero runs on CPU). Per-model budgets, the chunk-size
  ceiling that does not announce itself, and the host RAM wall in `separate`: STACK.md.
- **Secondary (deferred):** Intel Arc B390 iGPU. See BACKLOG (`tasks/weaker-hardware.md`).

Design budget: batch wall-clock ≤ ×5 video duration, comfortably cleared. It is dominated by
transcribe; synthesis is not a factor. Any stage-share split you need comes off a fresh run, not
off this page — the F5-era split is retired (DECISIONS 2026-08-24).

## Constraints / assumptions

- Single speaker per video (covers ~95% of target content). No diarization.
- Local STT and TTS, always. Translation is Claude Sonnet in semi-automatic mode, at the seam —
  always explicit, never a silent fallback.
- **The dubbing routes are EN→RU.** Route E and `--transcribe-file` translate nothing and are
  deliberately outside that: they take the source in its own language.
- No tempo cap upward, a floor downward: a segment is sped up as much as its slot requires and an
  under-filled one is stretched toward its slot, both strictly inside that slot. Occasional broken
  segments are tolerated; silent ones are not.
- Fixed narrator voice, baked into the model, no reference clip. Cloning the source speaker
  cross-lingually was dropped after the day-1 engine bake-off.

## Voices, cloning and the law

**There is no voice cloning in this pipeline, so most of the usual questions do not arise.**
Silero's narrator is baked into the model — no reference clip, no voice sample on disk, no third
party's voice involved. This section is not legal advice.

**What does apply: the model's own licence is non-commercial.** This is the project's record of it.

| release | licence | cost of using it |
|---|---|---|
| `v5_5_ru` — **what ships** (`eugene`) | **CC BY-NC** | automatic stress, correct Russian out of the box |
| `v5_cis_base` + the ~30 `ru_*` voices | **MIT** | you set the stresses yourself |

NC is fine for personal listening and is a hard gate on anything published; it was accepted for
personal use (user, 2026-07-27). **Both rows are unverified against the current model card —
re-check before any distribution.** If NC ever binds, `v5_cis_base` is the escape hatch: same
engine family, so the adapter would not change — only the voice and the stress preprocessor, which
this pipeline is already building toward.

- **If you ever add a voice that is not the model's own, study the law of your jurisdiction first.**
  EU member states and Canada protect a person's voice from unauthorized *public* use (personality
  rights in the EU, the appropriation of personality tort and Quebec Civil Code art. 36 in Canada).
  From August 2026 the EU AI Act additionally requires published synthetic media that resembles a
  real person to be labeled as AI-generated. Russia has a pending bill (draft art. 152.3 of the
  Civil Code) to the same effect.
- **Repository policy:** the documentation stays person-agnostic — no instructions for cloning any
  specific individual's voice.

## Status

Polishing — the pipeline runs on real videos, batch mode included, with translation supplied at the
seam. Current roadmap: `BACKLOG.md` (details in `tasks/`); rationale history: `DECISIONS.md` → `docs/decisions-log.md`; raw capture:
`INBOX.md`. Setup: `SETUP.md`; verified host facts: `STACK.md`.
