---
name: overdub-scout
description: "Scout an overdub queue (README route C) — the --scout pre-pass that downloads audio only, transcribes and summarizes each video WITHOUT dubbing it, so the user learns what is in a queue they have not watched. Fixed order: scout the batch, summarize each video with Sonnet sub-agents (~200 words: what it covers, what is most interesting in it), build work/scout-report.html (preview · title · what it is · what is most interesting, in queue order, plus a write-up per video), publish it as an Artifact and hand over the link. Trigger when the user wants to know what a queue CONTAINS: 'о чём эти видео', 'разведка по очереди', 'прогони разведку', 'что тут в очереди', 'scout the queue', '--scout', 'summaries only, no dub'. The route GRADES NOTHING and recommends nothing — it reports content and the user decides. NOT for dubbing: once the queue is chosen, hand off to the overdub-sonnet-batch skill (route B), the only route that ends in a dub."
---

# overdub — scout a queue (route C)

Scout answers **"what is in this, briefly"** before anything expensive runs:
**download (audio only) → transcribe → stop**, then one Sonnet sub-agent per video writes the
summary. No translation, no TTS, no MKV, no `source.mkv` on disk.

**The route assesses nothing** (2026-08-03, see DECISIONS). No grade, no watch/skip, no ranking,
no "стоит посмотреть" anywhere — in the artifacts, on the page, or in chat. It reports what each
video covers and what is most interesting in it; the reader decides. The moment a verdict appears,
this route is doing a job nobody asked it for and the user cannot argue with.

Three steps, in order. Do not reorder them and do not skip the gates — each
step's gate is what keeps a half-scouted queue from reading as a finished one.

**When NOT to use this skill.** If the queue is already chosen and the user wants it dubbed, go
straight to the `overdub-sonnet-batch` skill (route B), the only route that ends in a dub —
scouting then buys nothing and still costs the audio fetch and a sub-agent per video.

And if the user wants to READ the video rather than know what is in it — the full English text,
not a summary — that is the `overdub-clean` skill (route E). Route C compresses an hour into ~200
words; route E keeps the source's own length.

Nothing here writes `translation.json`, so a scouted video is not half-translated — it is
untranslated, and it re-enters the dubbing route with no cleanup (see "Promotion" below).

## S1 — Resolve the queue, then scout the batch

**Read [`docs/queue-contract.md`](../../../docs/queue-contract.md) now, before anything else.**
Sections 1-3 are this step: who owns `queue.txt`, the `$ids` block and its three load-bearing
guards, the `# playlist:` freshness diff, and the rule that a queue is never shortened, lengthened
or interrupted by a model. Run §1 verbatim, and apply §2 as §1 directs — the trigger lives there,
not here. They are the same for every route, and this skill deliberately keeps no second copy.

**Resolve the queue BEFORE the run, not after** (moved above the command 2026-07-24). These
checks used to sit under it, which made them audits of a fetch that had already happened.

Route-C specifics on top of the contract:

- S1 prints the workdir per video (`work dir: work\<id>`), so the ids the contract derived are
  visible against what actually ran.
- Without `-Unique` in the `$ids` block, two parallel sub-agents would race on the same
  `summary.md`.
- ASR on music produces an empty transcript (Parakeet's VAD gate, since 2026-08-06) or, on the
  whisper fallback, a hallucinated one. Under contract §3 that video is
  still scouted: the summary says plainly that there is no speech and what the transcript does
  contain — a finished row, not a failure and not a question for the user. An honest "тут нечего
  пересказывать", written INTO the summary, is the answer; a skipped video is a hole.

Then run:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --scout
```

Single video: the URL instead of `--batch queue.txt`.

`--scout` is its own mode: it does NOT compose with `--only` (usage error, exit 2, refused
before any side effect), and its download is audio-only — `work/<id>/source.wav` exists and
`work/<id>/source.mkv` deliberately does not. `--scout --force` is legal and re-runs the
large-v3 transcribe too, not just the fetch.

Produces per video `work/<id>/sentences.json` — a JSON list of `{id, text, start, end}`, `id`
contiguous from 0. That is the sub-agent's input, and it is the SAME artifact the dubbing route
produces, which is why a promoted video never re-transcribes.

One line per video in the batch summary:
`scouted · <duration> · <n> sentences · summary pending`.

**Gate before S2:** `work/<id>/sentences.json` exists for every id in `$ids`.

```powershell
$ids | Where-Object { -not (Test-Path "work\$_\sentences.json") }   # must print nothing
```

A video that failed drops out with a `FAIL` row — re-run the same S1 command (completed stages
fast-skip). One failure mode is by design: `-f bestaudio` has no `/best` fallback, so a source
with no audio-only format fails here rather than silently pulling a full video stream at ~20×
the bytes. That video is dubbed in full mode deliberately, or dropped from the queue.

## S2 — Summarize each scouted video

One sub-agent per video, Agent tool (`general-purpose`) + **`model: "sonnet"` — set it
explicitly** (a summary written by an inherited session model is not the artifact this route was
verified with, DECISIONS 2026-07-18/19).

**This step needs a session that has the `Workflow` tool, and never a hand fan-out** — both rules
and their measurements are [`docs/queue-contract.md`](../../../docs/queue-contract.md) §6. If you
do not have the tool: stop here and say so. There is deliberately no fallback for S2.

**Resume filter first**, keyed on its own artifact — a prior interrupted S2 may have finished
some videos, and the mtime clause catches summaries gone stale via a re-transcribe
(`--scout --force`, or a `--repair-asr` pass):

```powershell
$sumTodo = @($ids | Where-Object {
  $s = "work\$_\summary.md"; $d = "work\$_\scout.draft.json"
  -not (Test-Path $s) -or -not (Test-Path $d) -or
    (Get-Item "work\$_\sentences.json").LastWriteTime -gt (Get-Item $s).LastWriteTime })
```

**Both files are in the filter on purpose.** A video summarized by the DUBBING route has
`summary.md` and no draft; keying on the prose alone would skip it here and leave it as a
`не отсканировано` hole in the report — present, plausible, and silently missing its write-up.

**`summary pending` OUTRANKS a present `scout.json`. Always. Never the reverse** — the
derived-artifact rule, [`docs/queue-contract.md`](../../../docs/queue-contract.md) §5, whose
worked case IS this route (2026-07-21, a six-video report representing zero work). If S1 prints
`summary pending` for a video that has a complete-looking `scout.json`, **the video is NOT
done — summarize it.**

**Stamp the wave start before spawning anything** — it cannot be recovered afterwards, and it is
what the report's wall-clock figure for the whole wave is derived from:

```powershell
$waveStart = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
```

**Delete stale markers for the videos about to be respawned** (contract §7 — what the marker
measures and why a missing one is not a reason to re-run):

```powershell
$sumTodo | ForEach-Object { Remove-Item "work\$_\scout.started" -ErrorAction SilentlyContinue }
```

**DO NOT spawn the sub-agents yourself. Run the workflow** — contract §6 carries the measurement
that closes this, including the three route-C runs where the orchestrator announced a single
message and emitted six anyway:

```powershell
# args.ids is the RESUME-FILTERED list from above — never the whole queue
```
```
Workflow: {name: "scout-summarize", args: {ids: [...$sumTodo], root: "D:\\code\\overdub"}}
```

It returns `{done, failed, total}`. **`failed` is per video and actionable** — an agent the
runtime dropped. Re-run the workflow with just those ids.

**A summarizer can also die to the SAFETY CLASSIFIER, and that failure is nondeterministic.** The
prompt tells the sub-agent to write `summary.md` through PowerShell because a harness hook denies a
sub-agent's `Write` on that path; the classifier reads the workaround as routing around a permission
gate and kills the agent. Measured on route B, which runs the same prompt shape: one of 19 agents on
2026-08-01, then six on 2026-08-20. **Route C is the route that still summarizes by default, so it
carries this risk on every batch.** Treat it as an ordinary `failed` — respawn those ids — and do
NOT reword the workaround; the fix is to write with `Write` and lift the hook (INBOX carries it).
The completion check below is what catches a video the classifier ate.

**Verify from disk, not from the run's account** (contract §7). The marker is `scout.started`:

```powershell
# 1. every video got a marker — a missing one is a lost measurement, not a lost summary
$sumTodo | Where-Object { -not (Test-Path "work\$_\scout.started") }     # must print nothing
# 2. the markers are seconds apart, not ~100 s
$sumTodo | Where-Object { Test-Path "work\$_\scout.started" } |
  ForEach-Object { (Get-Item "work\$_\scout.started").LastWriteTime } | Sort-Object
```

Each sub-agent writes TWO files: `summary.md` (the ~200-word prose, unchanged — route B reuses
it on promotion) and `scout.draft.json` (`{one_liner, highlight, paragraph}` — the machine-consumed
fields the report renders). Then **`scripts/build_scout.py` assembles `work/<id>/scout.json`** —
same division of labour as `build_translation.py` on the dubbing route: the sub-agent writes only
prose, the helper owns everything deterministic (title, duration, sentence count, stage timings)
and rejects a draft with an empty or missing field. A malformed draft fails loud there and never
reaches the report.

```powershell
$sumTodo | ForEach-Object {
  .venv-asr\Scripts\python.exe -X utf8 scripts\build_scout.py "work\$_" --wave-start $waveStart }
```

**The sub-agent prompt lives in `.claude/workflows/scout-summarize.js`, not here.** It used to be
pasted into this file and re-typed by the orchestrator for every video; that is exactly the cost
the workflow removes, and two copies of one prompt drift. Edit the script.

The prose half of that prompt is **identical to the summarizer in
`.claude/workflows/translate-batch.js`** — if you change that half, change it there too, or the two
routes produce different artifacts under one name. Note that route B stopped RUNNING its copy on
2026-08-20 (`sumIds` ships empty, DECISIONS) — the prompt is still there and still shared, so the
sync rule stands; route C is now the only route that summarizes by default.

**Completion check — re-run the S1 command.** It is free (both stages fast-skip, seconds) and
every line flips to `summary ok`. A line still reading `summary pending` is a video whose
sub-agent did not finish — respawn it. Never hand-write `summary.md` or a `scout.draft.json` to
clear the line: that turns the pass's only completion signal into a lie, and a hand-written
write-up is one you invented rather than derived from the transcript.

## S3 — Build the report, publish it, hand over the link

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\scout_report.py --queue queue.txt
```

Writes `work/scout-report.html`: a header with the state tally (`отсканировано: N`, plus any
unfinished states) and the timing strip, then the **scan table** (№ · превью · название ·
длительность · о чём · самое интересное) and the **read cards** (same videos, same order, the full
write-up). A finished row carries **no chip** — the page assesses nothing, so a badge every
completed row wears would be a column of one value. Chips are reserved for states that demand an
action, and they carry both colour and text, so the page survives grayscale or a colour-blind
reader.

**Row order is the queue's order, never sorted.** The report is read next to the playlist it
came from, so position is information; a re-sorted row is a wrong row even when its fields are
right. (The morning-listen job — "what is broken" — is served by the triage nav block of
anchors that appears when dubbed videos need a listen, not by reordering the queue.)

A queued video with no `scout.json` renders as an explicit `не отсканировано` row and the script
says so on stdout. That is an unfinished S2 — re-run its sub-agent and rebuild, do not publish a
report with holes in it and hope they go unnoticed.

**A dubbed-but-never-scouted row is NOT that case, and must not be treated as one.** It has no
`scout.json` by design — it came off the dubbing route, which never runs S2 — so it keeps its dub
chip and borrows «о чём» and «самое интересное» from its `summary.md`, whose two paragraphs answer
exactly those two questions (2026-07-22). The row is complete as it stands.

**Then publish it as an Artifact** so it is readable from anywhere, not just this machine. The
file is deliberately a BODY FRAGMENT (inline `<style>`, no doctype/`<html>`/`<head>`/`<body>`)
because the publisher supplies that skeleton:

- `Artifact` with `file_path` = the generated `work/scout-report.html`, a `favicon`, and a
  one-sentence `description`.
- **Re-publishing the same queue: pass the previous artifact's `url`** so it updates in place
  and the link the user already has keeps working. Only a genuinely new queue gets a new URL.

**Then hand over the link and stop.** No rundown, no tally read out, no retelling of the videos
in chat — the page is the deliverable and it is the only version of it (2026-08-03). A chat
summary of the summaries is a second, unverifiable copy that diverges from what is on disk, and
naming videos you would drop is the recommendation this route exists not to make.

Two things do belong in chat, because the page cannot say them about itself: **holes** the script
named on stdout (which videos, and that they are unfinished S2, not weak videos), and a queue
whose summaries all came out suspiciously alike — that usually means the prompt is drifting, not
that the queue is uniform, so check two against their transcripts before publishing.

If the user then asks about ONE video, quote from its `summary.md` rather than re-deriving
anything from the transcript: the artifact on disk and the story you tell must be the same story.

## Promotion — handing a chosen queue to the dubbing route

The user trims `queue.txt` to what they want dubbed; that queue then enters the
`overdub-sonnet-batch` skill at its **Step 1** (route B). Mechanics — what fast-skips, what
re-runs, the ~5% traffic — are [`docs/queue-contract.md`](../../../docs/queue-contract.md) §4.

Videos the user dropped keep their scout artifacts in `work/<id>/` — a few MB each, and they
make a re-scout free. Deleting them is the user's call, not yours.

## Rules that are not negotiable

The queue rules — never shorten it, never lengthen it, never stop the run to ask about ONE video,
never treat a leftover `queue.txt` as a question, never forge a completion artifact — are
[`docs/queue-contract.md`](../../../docs/queue-contract.md) §3, and they bind here unchanged.
Route C adds four of its own:

- **The route assesses nothing.** No grade, no watch/skip, no ranking, no "стоит посмотреть" — in
  `scout.draft.json`, in `summary.md`, on the page or in chat. This is the specific shape §3 takes
  on a route whose whole output is a description: the user trims the queue, and they can only do
  that from what the videos ARE.
- **The page is the deliverable; chat gets the link.** Never re-tell the queue in the reply. The
  exceptions are holes and a drifting-prompt suspicion — facts about the RUN, not about the
  videos.
- **Never ground an answer in anything but the summaries.** If a summary is missing, say so and
  respawn its sub-agent; do not read the transcript yourself and improvise one — the artifact on
  disk and the story you tell the user must be the same story.
- **Never widen the scope to dubbing.** Scout stops at S3. If the user wants the queue dubbed in
  the same breath, hand off to the `overdub-sonnet-batch` skill explicitly rather than running
  synthesis from here.
