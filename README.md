# overdub

Local-first, semi-automated pipeline for dubbing YouTube videos into Russian.

Download → transcribe → translate → synthesize → verify → assemble → mux.
Every stage but one runs on local hardware, with no per-minute billing; the
exception is translation, which left the host at the seam and is written by
Claude Sonnet sub-agents (step 3 below). Built for batch processing of
hundreds of hours of single-speaker content.

## Pipeline

1. **Download** — `yt-dlp` fetches the video.
2. **Transcribe (STT)** — Parakeet-TDT 0.6b v3 (NVIDIA NeMo) produces the English
   transcript with word timestamps; words are re-assembled into sentences with
   `[start, end]`. The sentence is the unit of translation, synthesis and sync.
   It has been the engine since 2026-08-06 (`asr_engine`, DECISIONS), running in
   `.venv-parakeet` as a subprocess worker — ~25× faster than whisper large-v3
   and, more to the point, free of whisper's repetition loops. It brings two
   needs of its own: a Silero VAD gate, without which it invents words on
   non-speech, and a coverage check that re-reads speech it dropped at a window
   boundary. `asr_engine = "whisper"` switches back to `faster-whisper`
   large-v3, which stays installed because verify uses it either way.
3. **Translate** — sentence by sentence with a rolling context window
   (previous EN sentences + their RU translations), prompted to keep length
   close to the original (it's dubbing, not prose). Output per sentence: raw RU
   for subtitles + normalized RU (numbers, acronyms, Latin terms spelled out)
   for TTS. Translation runs at the seam: Claude Sonnet in semi-automatic mode
   (sub-agent workflow — it replaces the pipeline's heaviest stage). See
   "Running" below.
4. **Synthesize (TTS)** — Silero v5_5_ru (`eugene`, CPU) renders Russian audio;
   it has been THE engine since 2026-07-25, chosen on speed and hardware cost
   with the quality difference accepted as a deliberate trade and later
   ear-confirmed on finished videos (DECISIONS 2026-07-25). One fixed narrator
   voice for every video, no per-speaker cloning and no voice sample needed.
   Adjacent sentences group into render units for natural prosody. Silero is
   DETERMINISTIC and has no native slot fitting, which shapes the two stages
   below: there is nothing to reseed, and timing fit is the pipeline's job.
5. **Verify** — the independent judge: every render unit is transcribed back
   with whisper-small and compared against the normalized TTS text (the same
   normalizer on both sides); failures are flagged in the run report — never
   hidden, never blocking. Runs on raw audio, before any tempo change in either
   direction. On a seed-capable engine a low-similarity unit is re-rendered with
   a new seed (keep-best); on Silero a failure is flagged directly, since
   re-rendering the same text returns the same audio.
6. **Separate + Mux** — htdemucs extracts a no-vocals bed from the original
   audio; the RU track is the dub laid over that bed at original level
   (`dub_mix = "bed"`, production default; `replace`/`duck` available). `ffmpeg`
   fits each unit into its slot with `atempo`: speeding up is UNCAPPED (extreme
   factors are logged, not fixed), slowing an under-filled unit is bounded by
   `atempo_floor` (0.75). Both stay strictly inside the unit's own slot, so the
   dub's timeline — and picture sync — is unaffected by the setting. Then dub
   loudness is aligned to the original and the final MKV is muxed. The original
   video stream is never re-encoded.

   Subtitles: `en.srt` carries the original timings (it transcribes the English
   track the MKV still ships), while `ru.srt` follows the DUB — each cue opens
   where its audio actually landed, since grouping makes a unit's speech
   continuous and a source-timed cue would drift from the voice reading it.

## Running

Prereqs (SETUP.md): `.venv-asr` + `.venv-demucs` (for the default bed mix),
`ffmpeg` on PATH. Silero runs inside `.venv-asr` and needs no assets under
`models/`. `yt-dlp` is resolved from `.venv-asr\Scripts` first, PATH
second; both tools are preflighted with a clear error instead of a raw WinError 2.

Everything the routes do IDENTICALLY — resolving `queue.txt` into an id list,
deciding whether that queue is still current, promoting it from one route to
another, fanning sub-agents out — is [`docs/queue-contract.md`](docs/queue-contract.md),
and it is a mandatory read for whoever drives a route. The sections below describe
what each route does DIFFERENTLY.

### A. Batch mechanics (shared by every route below)

The pipeline command itself. Translation is not produced in-process — it has to
exist as `work/<id>/translation.json` first (route B), and the run resumes from
that seam. Everything in this section applies to every route that ends in an MKV.

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
- **Batch order.** A batch runs **stage-major**: every video through `download`,
  then every video through `transcribe`, and so on. Each model therefore loads
  once per BATCH instead of once per video. The saving was measured at ~72 s/video
  in 2026-07, but that figure came off pre-2026-07-22 stage walls and is retired —
  see PLAN "Numbers to re-measure" (C); quote a fresh one off `rtf_work` or none at
  all. The trade is that no MKV is finished until
  late in the run; a failed video drops out of the remaining stages without
  affecting the others, and the summary says which stage it died on. Pass
  `--video-major` to restore the old order (each video through every stage before
  the next) — it is the escape hatch, and it produces byte-identical audio.
- Morning triage: the per-run rollup `work/<id>/run.json` (timings/RTF, flag counts by
  type, speed distribution, `needs_triage`) — or the raw `work/<id>/report.json` for any
  `*_flag` / `speed_factor > 1.8`. For a batch, the CLI prints a sweep after the summary;
  `scripts/run_report.py [work\<id> ...] [--queue queue.txt]` renders the text digest
  (per-video block + batch table), and `scripts/scout_report.py [--queue queue.txt] [--link]`
  writes `work/scout-report.html` — one page per queue with the flagged units and an inline
  audio player per unit (expected vs whisper-heard, click to listen); the videos needing a
  listen are surfaced by a nav block of anchors, never by re-sorting the queue. Audio is
  base64-embedded by default (portable page, every player works); `--link` keeps the page
  small but ties it to this machine — relative paths next to `work/`, absolute ones when
  `--out` sits on another drive. A published copy built with `--link` shows silent players
  by design: dub audio is never uploaded (narrator rights, DECISIONS).
- Two clocks per stage, and they answer different questions (do not sum them). `timings.json`
  keeps `stages[x]` — the wall clock including the model load, i.e. what the run actually cost —
  and `detail[x]` — what the stage measured about ITSELF. `transcribe`, `translate` and
  `synthesize` report `work_sec` with their load excluded, plus the counter that explains an
  outlier: `asr_passes` (the alignment guard re-runs ASR), `n_api` (a resumed translate touches
  the network for nothing), `n_rendered` (a resumed synthesize re-renders a FRACTION of the
  units, so its wall clock describes a fraction of the video). `detail.transcribe` also carries
  the run's decode PROVENANCE, which is not a timing at all: `asr_key`
  (`model|compute_type|beam=N|cond=B` — what actually decoded, so the alignment guard's cond=False
  retry is recorded as `cond=False`, and a spliced `--repair-asr` transcript as `cond=mixed`) plus
  `asr_repair_windows`. A later run WARNS when the stamped model, compute type or beam differs
  from the current config — that run will fast-skip transcribe and keep the old transcript, which
  is the thing worth knowing; a cond-only difference reports more quietly, because cond is a
  documented per-source escape hatch and the alignment guard sets it by itself. Workdirs made
  before 2026-07-22 carry no stamp and are accepted silently, so the warning only ever fires on
  transcripts produced after it existed. `run.json.timings` publishes
  `rtf` off the full wall and `rtf_work` off the load-excluded total, with `work_coverage` /
  `work_complete` saying how much of the pass is accounted for — the five stages without a
  `detail` entry make `rtf_work` an upper bound today, and the digest marks it `RTF~` when so.
  Compare builds on `rtf_work`; report cost as `rtf`.

### B. Batch with Sonnet translation (semi-automatic — the dubbing route)

Translation is just an artifact (`translation.json`), so the pipeline stops
cleanly at the translate seam and resumes from it.

1. **Transcribe the batch:**

   ```powershell
   .venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --only download transcribe
   ```

   → per video: `work/<id>/sentences.json`.

2. **Translate with Sonnet sub-agents** (one per video), orchestrated by the
   `overdub-sonnet-batch` skill. Each sub-agent reads `sentences.json` and writes
   ONLY a draft `work/<id>/translation.draft.json` = `[{id, text_ru, src}, ...]` (`src` is
   the sub-agent's reading of the ENGLISH source — required on every record, `"ok"` when it
   is sound, plus a one-line English `src_note` when it is not; vocabulary in
   `.claude/skills/overdub-sonnet-batch/references/translate-contract.md`); then
   `scripts/build_translation.py work/<id>` assembles `translation.json` under the
   contract:
   - a JSON list, one record per sentence, id-contiguous:
     `{id, start, end, src_en, text_ru, text_tts, status: "ok", attempts: 1}`;
   - translation rules = the `SYSTEM` prompt in `overdub/stages/translate.py`
     (keep RU close in length, game/brand names stay Latin, numbers stay
     digits, rolling context);
   - the helper owns the fragile part so the contract never rides on the LLM: it
     fills src_en/timings from `sentences.json`, derives `text_tts` via
     `overdub.normalize.normalize_for_tts` (verify compares through the same
     normalizer — never let the LLM spell it), gates each line through
     `overdub.stages.translate._is_bad`, and enforces id-contiguity (a malformed
     draft fails loud, never reaches synthesize).

   In the same wave, a second Sonnet sub-agent writes `work/<id>/summary.md` — a
   ~200-word Russian triage blurb read straight from the file by the digest and
   the queue page (`scout_report`); it is informational and gates nothing, and there is no helper
   script for it.

3. **Resume the batch** with the exact command from section A — download/
   transcribe/translate skip (artifacts exist), synthesize → verify → assemble
   → separate → mux run as usual.
   - Morning triage: same as section A — `work/<id>/run.json` (the per-run rollup)
     and `scripts/run_report.py --queue queue.txt` for the text digest,
     `scripts/scout_report.py --queue queue.txt` for the clickable page (flagged
     units + inline audio, a triage nav instead of a re-sort); raw flags in
     `work/<id>/report.json`. The `overdub-sonnet-batch` skill's Step 4 runs the
     digest and writes the Russian triage summary for you.

This is the only dubbing route: translation is produced by sub-agents at the
seam, and the pipeline runs everything either side of it.

### C. Scout a queue before dubbing it (audio only)

A cheap pass over an unread queue — **download → transcribe → stop**. No
translation, no TTS, no MKV. It answers one question per video: is this worth
the dub? Run it before route B on any queue you have not read.

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --scout
```

- **Audio only.** `yt-dlp -f bestaudio` → `work/<id>/source.wav` (16 kHz mono,
  exactly what whisper eats). `source.mkv` is never written, so a 100-video
  queue costs a few GB instead of ~100 GB in hour 0 — full-mode queue size is
  bounded by free disk, not by patience. There is no `/best` fallback on
  purpose: a source with no audio-only format FAILS out of the scout pass
  rather than quietly pulling a full video stream.
- **A preview rides along with every fetch** — audio-only and full alike since
  2026-07-22. yt-dlp writes the thumbnail sidecar while it is already talking to
  YouTube, and the download stage scales it to `work/<id>/thumb.jpg` at 160 px
  offline. It is cosmetic: a failure anywhere in that chain costs a row its
  picture and nothing else. Workdirs downloaded before that date have no preview
  until they are re-fetched; a scout pass backfills one over the network
  (`build_scout.py`), the dub route does not.
- Single video: same command with a URL instead of `--batch`. `--force`
  re-fetches (and re-transcribes). `--scout` is its own mode, not a
  composition — `--scout --only …` and `--scout --repair-asr …` are usage
  errors, refused before any side effect.
- Per video the summary line reads
  `scouted · 12:34 · 210 sentences · summary pending|ok`. Re-running the
  identical command is the completion check for the whole pass: both stages
  fast-skip, so it takes seconds and just re-reads what is on disk.

**The summary is written at the seam, not by the pipeline.** There is no
summarize stage: after the scout pass one Sonnet
sub-agent per video reads `sentences.json` and writes two files —
`work/<id>/summary.md` (prose, shared with route B) and
`work/<id>/scout.draft.json` (`{one_liner, highlight, paragraph}` — the fields the
report renders; `one_liner` says what
the video IS, `highlight` says what is most interesting IN it, and they are kept
apart because the scan table asks both questions at once). Its first action is to
touch `work/<id>/scout.started`, an empty marker whose mtime is how long that
agent's own run took. The sub-agent also reads `source.info.json`, so
channel and upload date are available to it — a transcript alone carries neither,
and the upload date is what lets the write-up say how old the material is.
`scripts/build_scout.py` then assembles `work/<id>/scout.json`, owning everything
deterministic (title, duration, sentence count, timings) and rejecting a draft
with a missing or empty field — the same split of labour `build_translation.py`
enforces on route B.

**Two kinds of timing, never summed together.** `*_sec` is the pipeline's wall
clock for a stage, model load included — what the run cost. `*_work_sec` is the
same stage measured from inside with the load and warmup excluded — what THAT
video cost, and the only one of the pair that compares across builds, because the
load lands on whichever video the sweep happened to start with (measured: 23.0 s
wall vs 17.3 s of work on a 2:22 video). Since 2026-07-22 `translate` and
`synthesize` report the same pair (see section A's triage bullet), so `run.json`
carries `rtf_work` beside `rtf`. `summarize_sec` is one agent's own
window from its marker, not the wave's — the wave start is shared by the whole
spawn, so it would bill an agent for time it spent queued. Per-video figures
overlap and their sum is meaningless; the report's strip carries only the wall
clocks. Nothing is ever self-reported by a model: the filesystem stamps it.

**The route assesses nothing** (2026-08-03, see DECISIONS). No grade, no
watch/skip, no ranking — not in the artifacts, not on the page, not in chat. It
reports what each video covers and what is most interesting in it; trimming the
queue is the reader's call, made from what the videos ARE. Two earlier attempts
at a verdict are the reason: a per-reader watch/maybe/skip collapsed toward "no"
(0 / 1 / 9 on the first real queue), and the material grade that replaced it
scored a video nobody had asked to have scored.

Then build the report — two lists over the same videos, **in queue order**:

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\scout_report.py --queue queue.txt
```

Writes `work/scout-report.html`: a state tally (`отсканировано: N`, plus any
unfinished state under its own name) and a timing strip (download,
transcribe, the summarize wave's wall clock, and the queue's own runtime — no
grand total, because two sums plus a wall clock do not add up to anything), a
scan table (№ · preview · title · runtime · what it is · what is most
interesting), then a card per video with
the full paragraph. **A finished row carries no chip** — the page assesses
nothing, so a badge every completed row wears would be a column of one value;
chips are reserved for states that demand an action. Order is the queue's, never
sorted — the report is read next
to the playlist it came from, so position is information. A queued video with no
`scout.json` gets
an explicit "не отсканировано" row rather than vanishing. The output is a body
fragment (inline `<style>`, no `<html>`/`<head>`), so it publishes as a Claude
Artifact unchanged and still opens locally.

The same page carries the dub side once a queue is (partly) promoted — there is
one page per queue now, not a scout page plus a separate triage page. A dubbed
video adds the batch-table row (the exact cell strings the text digest prints),
its flagged units with inline audio and the source-anomaly block; a
promoted-but-untranslated one shows an honest "в работе" state. In the scan
table a dubbed-but-never-scouted row keeps its dub chip; both "о чём" and "самое
интересное" fall back to `summary.md`, whose two paragraphs answer exactly those
two questions (2026-07-22). Both cells dash out when neither artifact exists,
because a pipeline-state sentence in a content column is a defect, not a
fallback. A card never
fabricates dub metrics for an undubbed video — no audio player, no RTF, no
triage verdict, because none of those exist for it — and dubbed videos are
counted apart from scouted ones, never folded into one total or the throughput
figure. `scripts/run_report.py` prints the same numbers and summaries in the
text digest.

**Promotion** — trim `queue.txt` to what you want dubbed and run route B, without
`--scout`. Mechanics (what fast-skips, what re-runs, the ~5% extra traffic):
[`docs/queue-contract.md`](docs/queue-contract.md) §4 —
the same block for every route, kept in one place.

### E. Clean a queue into readable English text — no summary, no dub

The question is **"let me read this instead of watching it"**. Route C
compresses an hour into ~200 words; this one does not: the output is the video's
own English, roughly as long as the source, cleaned enough to read. Deliverable:
`work/<id>/clean.md`.

E1 is the same transcript command as C and D (`--scout`), so a queue that has
been through either costs seconds here. Then, and **before anything is cleaned**:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --repair-asr auto
```

The order is enforced by the code, not by discipline: a repair renumbers every
id, so `invalidate_downstream` deletes `clean/`, `clean.json` and `clean.md`
along with the translate artifacts. Repair matters more here than on the dubbing
routes — a repetition loop passes the ear in half a second, but sits on the page
as a repeated paragraph.

**Then one Sonnet sub-agent per CHUNK**, orchestrated by the `overdub-clean`
skill (`.claude/workflows/clean-transcript.js`). Per chunk, not per video,
because this is the one route whose output is as long as its input: a per-video
agent cleans the opening faithfully and compresses harder the further it goes,
and nothing in the artifact says which half you are reading. ~80 sentences is
~7k characters of output, where the task stays mechanical.

`scripts/build_clean.py --plan` owns the cut (target 80, slid to the longest
pause nearby) and the same function re-derives it at join time, so a plan and its
assembler cannot disagree. Each agent writes `work/<id>/clean/<from>-<to>.json`
as `[{id, text}]` for its own range only.

The contract is what makes this route checkable, and it is the only route in the
repo that is: output and input are the same language in the same sentence order,
so **every id must come back**. An emptied line is written `""` (pure filler);
an absent id fails the build, because the two are indistinguishable in a text
file afterwards. `build_clean.py` then joins, exits on any missing / foreign /
duplicated id, and warns — never blocks — on the quality signals: per-chunk and
whole-document length ratio (a chunk that summarised instead of cleaning shows up
as its own number), dropped digit runs, dropped capitalised terms, and the share
of emptied lines.

The entity check is precise here for a reason that does **not** generalise: EN→EN
keeps a name a name, so a substring test is right about its dominant input class.
That is exactly the objection that deleted `completeness.entity_loss` on the
translate seam (DECISIONS 2026-08-01) — do not port these detectors there.

`clean.md` carries a metadata header and timecoded paragraphs broken on the
speaker's own pauses (≥1.0 s, or ~900 chars without one; a stamp every ~2 min).
Both thresholds are hypotheses sited on speech rhythm, not measured constants.

**Caching** — the per-chunk drafts, keyed on mtime against `sentences.json`, so a
failed wave costs only its failures. `clean.json` and `clean.md` are derived and
are never cache keys: a present `clean.md` proves nothing about whether an agent
ran.

**Promotion** — nothing to clean up; a cleaned video is untranslated, not
half-translated. It enters route B at the top or route C at S2
([`docs/queue-contract.md`](docs/queue-contract.md) §4).

### Repairing an ASR defect

**Whisper-only since 2026-08-06.** `--repair-asr` refuses when `asr_engine` is
anything else: its accept gate is "two independent readings of the clip agree",
which is evidence only because whisper's temperature fallback samples. Parakeet
decodes greedily and deterministically, so the two readings are byte-identical,
the gate accepts unconditionally, and the mode would splice unverified text
while reporting it as verified (DECISIONS 2026-08-06). On the default engine the
equivalent job is done inside the transcribe worker, which finds speech spans it
left uncovered and re-reads them before writing anything — see `holes` and
`hole_words_recovered` in the run report. Everything below applies with
`asr_engine = "whisper"` set.

When whisper collapses — a repetition loop, or a sentence stamped onto an
impossible span — the fix is not a full re-transcription (1/4 in the manual
trial) but an isolated re-read of the defect window (7/7). Run it after
`--only download transcribe` and before translating; dry-run first:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --repair-asr auto --repair-dry-run
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --repair-asr auto
```

Repair clips the window out of `source.wav`, reads it twice (with context
feedback off and on) and **accepts only if the two readings say the same
words**. On accept it merges the window into its own reading, renumbers every
id so they stay contiguous, keeps the original at
`work/<id>/_pre-repair-sentences.json` (written once, never clobbered),
preserves the source-anomaly worklist at `work/<id>/_pre-repair-translation.json`
(byte-exact `translation.json`, overwritten on every repair; its ids predate the
renumbering), and deletes exactly the artifacts downstream of `sentences.json`. It never re-runs a
stage itself — the next ordinary run redoes translate → mux honestly, and
completed stages still fast-skip. `words.json` is deliberately left alone: it is
the raw record of what the ASR actually did.

A **rejection means the two readings disagreed**, i.e. whisper is still guessing
there. Re-running reproduces it exactly, so it needs ears, not a retry — listen
to the span and fix the text by hand if it matters.

`--repair-asr 23,24,25` takes explicit ids (single video only). It is **stronger
than `auto`**, not a legacy convenience: the two detectors behind `auto` are
blind to a hallucinated word that splits one sentence into two plausible halves,
so "no defect windows" is not "the transcript is clean". Note that an accepted
repair renumbers ids — re-derive them before a second explicit pass.

## Tests

```powershell
.venv-asr\Scripts\python.exe -m pytest
```

Seconds, not minutes. No GPU, no network, no media, no model downloads — everything
is pure logic over temp dirs and injected stages, which is what makes a bare
`pytest` a safe thing to run at any time, including while a batch is on the GPU.

**The suite size is not written down anywhere on purpose** (the rule and its
rationale live in CLAUDE.md, "Tests" — this is the command half). The run itself
is the only answer, and it costs seconds; `--collect-only -q` gives it without
executing anything:

```powershell
.venv-asr\Scripts\python.exe -m pytest --collect-only -q
```

`pytest` is installed in `.venv-asr` only (`pip install -e ".[dev]"`);
`.venv-demucs` runs a worker process, not tests. Configuration is
`[tool.pytest.ini_options]` in `pyproject.toml`, and what is load-bearing there
rather than cosmetic is collection scope: `testpaths` and `norecursedirs` keep
the in-repo venvs out, since site-packages ships hundreds of its own suites and
a bare `pytest` without them takes minutes to fail inside someone else's code.

**Run it from the repo root.** `testpaths` only applies when the invocation
directory is the rootdir (pytest 8+), so elsewhere you get "no tests ran".

Every file also stays directly runnable and prints its own summary:

```powershell
.venv-asr\Scripts\python.exe -X utf8 tests\test_scout_report.py
```

Both entry points work off the same `sys.path.insert` preamble inside each test
file — there is deliberately no `pythonpath` in the ini, because a second
mechanism could silently diverge from the first.

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
| STT | Parakeet-TDT 0.6b v3 (NeMo) | CUDA, `.venv-parakeet` subprocess worker; Silero VAD gate + uncovered-speech re-read |
| STT fallback | faster-whisper large-v3 | CUDA, `asr_engine = "whisper"` |
| Translation | Claude Sonnet (semi-auto, at the seam) | sub-agents write `translation.json`; the pipeline resumes from it |
| TTS | Silero v5_5_ru (`eugene`) | THE engine — CPU, in `.venv-asr`, no voice sample, deterministic; v4_ru only to reproduce pre-2026-07-19 runs |
| Verification | faster-whisper small | ASR round-trip check |
| Separation | htdemucs (Demucs) | no-vocals bed for the mix, `.venv-demucs` |
| Mux | ffmpeg | atempo fitting, bed mix, MKV output |

## Hardware targets

- **Primary:** NVIDIA RTX 4080 Mobile, 12 GB VRAM. A model's lifetime is one
  stage sweep, so peak VRAM is the largest single model rather than the sum,
  which is what makes one model load per BATCH safe. Measured: Parakeet ~8.8 GB
  at 10-minute chunks (2026-08-06 — and the chunk size is the ONLY thing
  bounding that; see SETUP.md for what happens at the ceiling), whisper
  large-v3 ~3.1 GB, htdemucs ~3.0, whisper-small ~0.5. **TTS costs no VRAM at
  all** — Silero runs on CPU.
- **Secondary (deferred):** Intel Arc B390 iGPU. whisper.cpp (SYCL/OpenVINO) and
  llama.cpp (SYCL) are proven there for STT/translation; Silero-on-CPU makes the
  TTS side a non-question there. See PLAN deferred.

Throughput budget: ≤ x5 video duration — comfortably cleared. Batch wall-clock
is dominated by transcribe; synthesis is not a factor (RTF ~0.02-0.3 on CPU).
Stage-share percentages have not been re-measured on the current configuration —
see PLAN "Numbers to re-measure", and treat any split quoted here as unmeasured
until that lands.

## Constraints / assumptions

- Single speaker per video (covers ~95% of target content). No diarization.
- Local STT and TTS, always. Translation is Claude Sonnet in semi-automatic
  mode, at the seam — always explicit, never a silent fallback.
- Source is always English, output is always Russian.
- No tempo cap upward, a floor downward (`atempo_floor`, 0.75 since
  2026-07-25): a segment is sped up as much as its slot requires and an
  under-filled one is stretched toward its slot, both strictly inside that
  slot. Occasional broken segments are tolerated; silent ones are not.
- Fixed narrator voice — Silero `eugene`, baked into the model, no reference
  clip. "Same voice as the speaker" (cloning the source speaker
  cross-lingually) was dropped after the day-1 engine bake-off.

## Voices, cloning and the law

**There is no voice cloning in this pipeline, so most of the usual questions do
not arise.** Silero's narrator is baked into the model — no reference clip, no
voice sample on disk, no third party's voice involved. This section is not legal
advice.

**What does apply: the model's own licence is non-commercial.** This is the
project's record of it — the fact used to live only in `docs/russian-tts-guide.md`
and would have died with that file.

| release | licence | cost of using it |
|---|---|---|
| `v5_5_ru` — **what ships** (`eugene`) | **CC BY-NC** | automatic stress, correct Russian out of the box |
| `v5_cis_base` + the ~30 `ru_*` voices | **MIT** | you set the stresses yourself |

NC is fine for personal listening and is a hard gate on anything published; it was
accepted for personal use (user, 2026-07-27). **Both rows are unverified against the
current model card — re-check before any distribution.** If NC ever binds,
`v5_cis_base` is the escape hatch: same engine family, so the adapter would not
change — only the voice and the stress preprocessor, which this pipeline is already
building toward (CMUdict + the stress audit). See PLAN, "Publication rights".

- **If you ever add a voice that is not the model's own, study the law of your
  jurisdiction first.** EU member states and Canada protect a person's voice from
  unauthorized *public* use (personality rights in the EU, the appropriation of
  personality tort and Quebec Civil Code art. 36 in Canada). From August 2026 the
  EU AI Act additionally requires published synthetic media that resembles a real
  person to be labeled as AI-generated. Russia has a pending bill (draft art.
  152.3 of the Civil Code) to the same effect.
- **Repository policy:** the documentation stays person-agnostic — no
  instructions for cloning any specific individual's voice.

## Status

Polishing — the pipeline runs on real videos, batch mode
included, with translation supplied at the seam. Closed: Phase 1 MVP, dead-air
elimination, batch queue + stop switch, proper-noun pronunciation, and the
segmentation root fix. Current roadmap: `.claude/PLAN.md`; rationale history:
`.claude/DECISIONS.md`. Setup: `SETUP.md`; verified stack facts: `STACK.md`.
