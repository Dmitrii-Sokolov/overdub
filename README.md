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
4. **Synthesize (TTS)** — Silero v5_5_ru (`eugene`, CPU) renders Russian audio;
   it has been THE engine since 2026-07-25, chosen on speed and hardware cost
   with the quality difference accepted as a deliberate trade and later
   ear-confirmed on finished videos (DECISIONS 2026-07-25). One fixed narrator
   voice for every video, no per-speaker cloning and no voice sample needed.
   Adjacent sentences group into render units for natural prosody. Silero is
   DETERMINISTIC and has no native slot fitting, which shapes the two stages
   below: there is nothing to reseed, and timing fit is the pipeline's job.
   ESpeech-TTS-1_RL-V2 (F5-TTS, worker in `.venv-f5tts`) still runs behind
   `tts_engine = "f5"` and is what pre-2026-07-25 artifacts used; it brings back
   reference-clip narration and its own slot filling.
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
`models/`; `.venv-f5tts` and the F5 checkpoints matter only if you set
`tts_engine = "f5"`. `yt-dlp` is resolved from `.venv-asr\Scripts` first, PATH
second; both tools are preflighted with a clear error instead of a raw WinError 2.

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
- **Batch order.** A batch runs **stage-major**: every video through `download`,
  then every video through `transcribe`, and so on. Each model therefore loads
  once per BATCH instead of once per video (~72 s/video of pure model loading —
  see STACK "Measured cost model"). The trade is that no MKV is finished until
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

### B. Batch with Sonnet translation (semi-automatic — the primary route)

Translation is just an artifact (`translation.json`), so the pipeline stops
cleanly at the translate seam and resumes from it. No Ollama needed.

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

3. **Resume the batch** with the exact command from route A — download/
   transcribe/translate skip (artifacts exist), synthesize → verify → assemble
   → separate → mux run as usual.
   - Morning triage: same as route A — `work/<id>/run.json` (the per-run rollup)
     and `scripts/run_report.py --queue queue.txt` for the text digest,
     `scripts/scout_report.py --queue queue.txt` for the clickable page (flagged
     units + inline audio, a triage nav instead of a re-sort); raw flags in
     `work/<id>/report.json`. The `overdub-sonnet-batch` skill's Step 4 runs the
     digest and writes the Russian triage summary for you.

Both routes are good: Gemma gives good quality locally and slowly; Sonnet needs
a subscription and gives better quality in the cloud, much faster.

### C. Scout a queue before dubbing it (audio only)

A cheap pass over an unread queue — **download → transcribe → stop**. No
translation, no TTS, no MKV. It answers one question per video: is this worth
the dub? Run it before route A or B on any queue you have not read.

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
summarize stage and no Ollama involvement: after the scout pass one Sonnet
sub-agent per video reads `sentences.json` and writes two files —
`work/<id>/summary.md` (prose, shared with route B) and
`work/<id>/scout.draft.json` (`{quality, one_liner, highlight, paragraph}`, plus
an optional `author` — the judgement the report renders; `one_liner` says what
the video IS, `highlight` says what is most interesting IN it, and they are kept
apart because the scan table asks both questions at once). Its first action is to
touch `work/<id>/scout.started`, an empty marker whose mtime is how long that
agent's own run took. The sub-agent also reads `source.info.json`, so
channel and upload date are available to it — a transcript alone carries neither,
which would leave any staleness or author rule in the profile unenforceable.
`scripts/build_scout.py` then assembles `work/<id>/scout.json`, owning everything
deterministic (title, duration, sentence count, timings) and rejecting an
unknown grade outright — the same split of labour `build_translation.py`
enforces on route B.

**Two kinds of timing, never summed together.** `*_sec` is the pipeline's wall
clock for a stage, model load included — what the run cost. `*_work_sec` is the
same stage measured from inside with the load and warmup excluded — what THAT
video cost, and the only one of the pair that compares across builds, because the
load lands on whichever video the sweep happened to start with (measured: 23.0 s
wall vs 17.3 s of work on a 2:22 video). Since 2026-07-22 `translate` and
`synthesize` report the same pair (see route A's triage bullet), so `run.json`
carries `rtf_work` beside `rtf`. `summarize_sec` is one agent's own
window from its marker, not the wave's — the wave start is shared by the whole
spawn, so it would bill an agent for time it spent queued. Per-video figures
overlap and their sum is meaningless; the report's strip carries only the wall
clocks. Nothing is ever self-reported by a model: the filesystem stamps it.

**The grade is about the MATERIAL, not about you.** `quality` (`high` / `medium` /
`low`) scores three things and only these: substance, currency, delivery. It is
deliberately not a "should you watch this" verdict — the first real queue came
back 0 watch / 1 maybe / 9 skip under one, because a personal verdict is a
decision taken for the reader and it collapses toward "no". A grade about the
material can be argued with; a verdict about a person cannot. An optional `author`
axis (`trusted`) is rendered only when the profile carries a trusted-author list.

**The viewer profile is context, not the criterion.** `.claude/viewer-profile.md`
— one person's stacks, what they already know, and what makes a video useless to
them — steers what gets named as the interesting part and what counts as already
known. It does not move the grade. The file is **gitignored** (personal); the
prompt that builds it from your own chat history is committed at
`.claude/skills/overdub-scout/references/viewer-profile-prompt.md`, and the skill
refuses to scout until the profile exists.

Then build the report — two lists over the same videos, **in queue order**:

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\scout_report.py --queue queue.txt
```

Writes `work/scout-report.html`: a grade tally and a timing strip (download,
transcribe, the summarize wave's wall clock, and the queue's own runtime — no
grand total, because two sums plus a wall clock do not add up to anything), a
scan table (№ · preview · title · runtime · what it is · what is most
interesting, the grade a chip opening that last cell), then a card per video with
the full paragraph. Order is the queue's, never sorted — the report is read next
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
table a dubbed-but-never-scouted row keeps its dub chip; its "о чём" falls back
to the first sentence of `summary.md` when one is on disk (2026-07-22), while
"самое интересное" stays a dash — that one is the scout's judgement and nothing
fills it in after the fact. Both cells dash out when neither artifact exists,
because a pipeline-state sentence in a content column is a defect, not a
fallback. A card never
fabricates dub metrics for an undubbed video — no audio player, no RTF, no
triage verdict, because none of those exist for it — and dubbed videos are
counted apart from scouted ones, never folded into one total or the throughput
figure. `scripts/run_report.py` prints the same numbers and summaries in the
text digest.

**Promotion** — trim `queue.txt` to the survivors and run the ordinary route A
or B command, without `--scout`. `transcribe` fast-skips on the scout's
`sentences.json`, so the large-v3 pass is not repeated; `download` re-runs
because the full contract needs `source.mkv`, which re-fetches the audio bytes
inside the merged container. That is ~5% extra traffic for zero new machinery,
accepted deliberately (DECISIONS 2026-07-20).

### D. Digest a queue — retell it, no grade and no dub

A different question from route C's. Scout asks **"does this earn an evening"**
and answers with a grade; a digest asks **"what is actually in it"** and answers
with a document. Two reading moments: after watching, to check nothing was
missed, and before, to know what to expect.

There is no new pipeline mode — the input is the same transcript, so D1 is the
route-C command and both stages fast-skip on anything already on disk:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --scout
```

A queue that has been through route C (or a dub) therefore costs seconds here.
Its per-video `summary pending|ok` line belongs to route C and says nothing
about a digest.

**Then TWO Opus passes per video**, orchestrated by the `overdub-digest` skill
(`.claude/workflows/digest-videos.js` fans them out as a pipeline, so each video
compresses the moment its own read returns):

1. **read** — reads `sentences.json` and `source.info.json`, writes
   `work/<id>/digest.long.json`: complete coverage, no length pressure at all.
2. **compress** — reads only that file (never the transcript, so it can lose
   material but cannot introduce any) and writes `work/<id>/digest.draft.json`:
   the same document cut to roughly a third.

The split is measured, not stylistic: a single pass cannot be given a length.
Sentence counts and character budgets both left the document at ~11.5k chars
against a predicted 3.5k, and the caps then deleted a finding out of a point's
tail — the one finding of the reference digest the run had otherwise missed
(DECISIONS 2026-07-30). Compression is a different task: the editor holds the
text, and across five videos it lands at ~2.9× (2.78 / 2.85 / 2.87 / 2.88 / 2.89)
with zero truncations.

**~2.9× is the model's own rate, not a setting** — asked for a fifth on a 19.6k
input, it produced 2.99×. The one instruction obeyed literally is the POINT COUNT
(11→6, 9→5, 7→4, 6→4, 5→3, every run inside the ladder), so document size is
governed by the ladder and the per-field character numbers are aspirations. That
is also why `_POINT_TEXT_MAX` sits at 900, above what the model writes rather than
at the 450 asked for: a cap set at the aspiration enforces style by deleting
content.

Cost is ~2× per video (~200k tokens: ~100k read + ~100k compress), and the two
passes are cached separately so a compressor change never re-pays the transcript
read. Resulting sizes, 2.9 to 90 minutes of video: 2.0k / 2.4k / 3.4k / 4.0k /
6.6k chars.

Both files carry the same five fields:

| field | what it is |
|---|---|
| `headline` | one line: format, runtime, who is speaking, subject |
| `thesis` | the central claim the whole video hangs off — the position, not the topic |
| `points` | `[{title, text, at?}]` — what is COVERED, with the mechanism/number/example. The compress pass keeps at most 4 up to ~25 min, 6 up to ~2 h, 8 beyond — **this ceiling is what actually sets the length of the page** |
| `context` | why the material exists, plus the honest caveats (what the speakers admit does not work, what is dated) |
| `not_covered` | what a digest CANNOT carry — the argument between two positions, a demo, code on screen, tone. An inventory of what stayed in the video, never a recommendation |

The read pass's first action is to touch `work/<id>/digest.started`, an empty
marker whose mtime, against the draft's, is what that video's whole D2 chain cost
— both passes, not one agent's window. **Opus for both, not Sonnet**
(DECISIONS 2026-07-30): a grade is a short judgement, a digest has to hold an
hour of argument at once, and deciding which point to drop is the judgement that
decides what the page says.

`scripts/build_digest.py work/<id> --wave-start <epoch>` then assembles
`work/<id>/digest.json` and renders `work/<id>/digest.md` — the same document as
a pasteable Markdown file, derived deterministically so the page and the file
cannot disagree. It owns everything factual (title, channel, upload date,
duration and its source, sentence count, timings) and rejects a draft that is
missing a field or whose `points` is not a well-formed list. **Route D grades
nothing**, so unlike `build_scout` there is no verdict vocabulary to typo.

Four of its checks are about the content, not the shape, and each names a
different pass to re-run:

- an `at` marker that does not parse is dropped (the point keeps its text);
- one past the end of the video is dropped **as fabricated**, and said out loud;
- a digest whose LAST marker sits in the first 60% of the runtime gets a
  warning — that is the "read the opening and stopped" failure, and it is
  invisible on the page, because such a digest looks complete about the part it
  did read;
- the point count is checked against the RUNTIME (≤25 min → 4, ≤2 h → 6, else 8;
  an unknown duration gets the top, since warning would be a guess). A flat
  3..8 band cannot express padding: 6 points on an 8-minute segment passed it
  silently on the first run.

It never falls back to `digest.long.json` when the draft is missing — shipping the
uncompressed version would be a format regression with no signal anywhere — and
names the compress pass instead.

Then build the page:

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\digest_report.py --queue queue.txt
```

Writes `work/digest-report.html`: a tally and a timing strip (download,
transcribe, the digest wave's wall clock, the queue's own runtime), a scan table
(№ · превью · название · время · что это · **темы** — the point titles joined,
the at-a-glance answer to "what is touched on"), then a card per video with the
whole document. Queue order, never sorted. A finished row carries **no chip**:
the page grades nothing, and a badge on every row would be a column of one
value. A queued video with no digest gets one of three explicit states —
`нет пересказа` (the sub-agent did not run), `не расшифровано`, `не скачано` —
each printed on stdout with the action that clears it. Body fragment, so it
publishes as a Claude Artifact unchanged and still opens locally.

**Caching, and the last rule is the one that matters.** The transcript is the
pipeline's own fast-skip. D2 is cached in two independent halves, because they
cost very differently: a stale or missing `digest.long.json` needs both passes
(`ids`), while a fresh long digest whose `digest.draft.json` is missing or older
needs **compression only** (`compressOnly`) — so a compressor tweak never
re-pays the transcript read. Both key on mtime against `sentences.json`, so a
`--scout --force` or `--repair-asr` transcript invalidates everything derived
from it. The page is pure assembly and free to rebuild. The keys are the two
AGENT artifacts, never the built `digest.json` — that file is derived and always
well-formed, which is exactly why its presence proves nothing about whether an
agent ran.

**Promotion** — a digested queue enters route A or B with no cleanup:
`transcribe` fast-skips, `download` re-runs for `source.mkv` (~5% extra
traffic), and the digest artifacts survive untouched.

### Repairing an ASR defect

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

~400 tests in ~5 s. No GPU, no network, no media, no model downloads — everything
is pure logic over temp dirs and injected stages, which is what makes a bare
`pytest` a safe thing to run at any time, including while a batch is on the GPU.

`pytest` is installed in `.venv-asr` only (`pip install -e ".[dev]"`); the other
two venvs run worker processes, not tests. Configuration is
`[tool.pytest.ini_options]` in `pyproject.toml`, and two settings there are
load-bearing rather than cosmetic: `testpaths` keeps collection out of the three
in-repo venvs (site-packages ships hundreds of its own suites), and
`python_files` is narrowed to `test_*.py` so pytest's default `*_test.py` does
not drag in the one-off audition scripts in `scripts/`.

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
| STT | faster-whisper large-v3 | CUDA |
| Translation | Gemma-3-12B via Ollama · Claude Sonnet (semi-auto) | local default · primary cloud route (DECISIONS 2026-07-18) |
| TTS | Silero v5_5_ru (`eugene`) | THE engine since 2026-07-25 — CPU, in `.venv-asr`, no voice sample, deterministic. Opt-in alternative: ESpeech-TTS-1_RL-V2 (F5-TTS) as a GPU worker in `.venv-f5tts`; v4_ru only to reproduce pre-2026-07-19 runs |
| Verification | faster-whisper small | ASR round-trip check |
| Separation | htdemucs (Demucs) | no-vocals bed for the mix, `.venv-demucs` |
| Mux | ffmpeg | atempo fitting, bed mix, MKV output |

## Hardware targets

- **Primary:** NVIDIA RTX 4080 Mobile, 12 GB VRAM. A model's lifetime is one
  stage sweep, so peak VRAM is the largest single model rather than the sum —
  which is what makes one model load per BATCH safe even on the Gemma route
  (~8-9 GB, the only model that makes 12 GB tight). Measured: whisper large-v3
  ~3.1 GB, htdemucs ~3.0, whisper-small ~0.5. **TTS costs no VRAM at all on the
  shipped engine** — Silero runs on CPU (the opt-in F5 worker holds ~0.8 GiB).
- **Secondary (deferred):** Intel Arc B390 iGPU. whisper.cpp (SYCL/OpenVINO) and
  llama.cpp (SYCL) are proven there for STT/translation; Silero-on-CPU makes the
  TTS side a non-question there. See PLAN deferred.

Throughput budget: ≤ x5 video duration — comfortably cleared. Batch wall-clock
is dominated by transcribe on the Sonnet route and by translation on the local
Gemma route (~45%); synthesis stopped being a factor when the engine moved to
Silero (RTF ~0.02-0.3 on CPU). **Stage-share numbers older than 2026-07-26
describe F5 and are void** — see PLAN "Numbers to re-measure" (B); the re-time
on Silero is an open item, so treat any percentage split here as unmeasured
until it lands.

## Constraints / assumptions

- Single speaker per video (covers ~95% of target content). No diarization.
- Local STT and TTS, always. Translation has two good routes (DECISIONS
  2026-07-18): local Gemma (in-pipeline default) and Claude Sonnet in
  semi-automatic mode — the primary route (subscription, better quality, much
  faster). Cloud is always explicit, never a silent fallback.
- Source is always English, output is always Russian.
- No tempo cap upward, a floor downward (`atempo_floor`, 0.75 since
  2026-07-25): a segment is sped up as much as its slot requires and an
  under-filled one is stretched toward its slot, both strictly inside that
  slot. Occasional broken segments are acceptable losses (PoC).
- Fixed narrator voice — Silero `eugene`, baked into the model, no reference
  clip. "Same voice as the speaker" (cloning the source speaker
  cross-lingually) was dropped after the day-1 engine bake-off.

## Voices, cloning and the law

**On the shipped engine this section is mostly moot.** Silero's narrator is
baked into the model — there is no reference clip, no voice sample on disk and
no third party's voice involved, so nothing below about cloning applies to a
default run. What DOES apply to it: the model's own licence is
non-commercial (CC BY-NC, per `bakeoff/tts-research-2026-07.md`; unverified
against the current model card), which is fine for personal listening and is a
gate for anything published.

Everything below concerns the **opt-in F5/ESpeech path** (`tts_engine = "f5"`),
which IS a zero-shot voice cloner: its narrator voice is defined by a short
reference clip (5–12 s + its exact transcript), not baked into the model. That
flexibility comes with rules. This section is not legal advice.

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
- **That path's narrator reference:** the demo clip from the ESpeech author's HF
  Space ([Den4ikAI/ESpeech-TTS](https://huggingface.co/spaces/Den4ikAI/ESpeech-TTS),
  `ref/example.mp3`) — the best-sounding voice across our narrator auditions.
  Its rights are **not clarified** (a real person's voice, unknown provenance),
  so the clip is not committed to this repository: it is fetched from the Space
  at setup time, and anything synthesized with it stays personal-use only.
  Public-domain alternatives (LibriVox readers) are recorded in
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
