---
name: overdub-scout
description: "Scout an overdub queue (README route C) — the --scout pre-pass that downloads audio only, transcribes and grades each video WITHOUT dubbing it, so the user can decide what earns their time and a full dub. Fixed order: scout the batch, grade the MATERIAL (substance/currency/delivery) and summarize each video with Sonnet sub-agents, build work/scout-report.html (grade · preview · title · what it is · what is most interesting, in queue order, plus a write-up per video), publish it as an Artifact, then hand the user a recommend-only Russian rundown. Trigger when the user has a queue they have not watched: 'разведка по очереди', 'что тут стоит дублировать', 'прогони разведку', 'scout the queue', '--scout', 'summaries only, no dub', 'о чём эти видео'. NOT for dubbing — once the queue is chosen, hand off to the overdub-sonnet-batch skill (route B), the only route that ends in a dub."
---

# overdub — scout a queue (route C)

Scout answers **"is this worth dubbing"** before anything expensive runs:
**download (audio only) → transcribe → stop**, then one Sonnet sub-agent per video writes the
summary. No translation, no TTS, no MKV, no `source.mkv` on disk.

Three steps, in order. Do not reorder them and do not skip the gates — each
step's gate is what keeps a half-scouted queue from reading as a finished one.

**When NOT to use this skill.** If the queue is already chosen, scouting buys nothing and still
costs the audio fetch and a sub-agent per video — go straight to the `overdub-sonnet-batch`
skill (route B), the only route that ends in a dub. Scout is for a queue nobody has watched.

And if the question is **what is IN the video** rather than whether it earns an evening — a
retelling, "did I miss anything", "what should I expect" — that is the `overdub-digest` skill
(route D). A scout summary is ~200 words with a grade attached; a digest is a document with no
verdict in it. Answering a digest request with a scout pass produces a grade nobody asked for and
a summary too short to check anything against.

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
- Whisper on music produces an empty or hallucinated transcript. Under contract §3 that video is
  still scouted: it comes out a `low` with the reason named — a finished row, not a failure and
  not a question for the user. The GRADE is the answer to "what do we do with this".

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
`не отсканировано` hole in the report — present, plausible, and silently missing its verdict.

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

**Verify from disk, not from the run's account** (contract §7). The marker is `scout.started`:

```powershell
# 1. every video got a marker — a missing one is a lost measurement, not a lost summary
$sumTodo | Where-Object { -not (Test-Path "work\$_\scout.started") }     # must print nothing
# 2. the markers are seconds apart, not ~100 s
$sumTodo | Where-Object { Test-Path "work\$_\scout.started" } |
  ForEach-Object { (Get-Item "work\$_\scout.started").LastWriteTime } | Sort-Object
```

Each sub-agent writes TWO files: `summary.md` (the ~200-word prose, unchanged — route B reuses
it on promotion) and `scout.draft.json` (the machine-consumed judgement the report renders).
Then **`scripts/build_scout.py` assembles `work/<id>/scout.json`** — same division of labour as
`build_translation.py` on the dubbing route: the sub-agent writes only judgement, the helper
owns everything deterministic (title, duration, sentence count, stage timings, and the
verdict-vocabulary check). A malformed draft fails loud there and never reaches the report.

```powershell
$sumTodo | ForEach-Object {
  .venv-asr\Scripts\python.exe -X utf8 scripts\build_scout.py "work\$_" --wave-start $waveStart }
```

**The sub-agent prompt lives in `.claude/workflows/scout-summarize.js`, not here.** It used to be
pasted into this file and re-typed by the orchestrator for every video; that is exactly the cost
the workflow removes, and two copies of one prompt drift. Edit the script.

The prose half of that prompt is **identical to the summarizer in the `overdub-sonnet-batch`
skill's Step 2** — if you change that half, change it there too.

**Completion check — re-run the S1 command.** It is free (both stages fast-skip, seconds) and
every line flips to `summary ok`. A line still reading `summary pending` is a video whose
sub-agent did not finish — respawn it. Never hand-write `summary.md` or a `scout.draft.json` to
clear the line: that turns the pass's only completion signal into a lie, and a hand-written
verdict is one you invented rather than derived from the transcript.

## S3 — Build the report, publish it, hand the decision to the human

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\scout_report.py --queue queue.txt
```

Writes `work/scout-report.html`: a header with the grade tally and the timing strip, then the
**scan table** (№ · превью · название · длительность · о чём · самое интересное — оценка это чип,
открывающий последнюю колонку, а не подпись к названию) and
the **read cards** (same videos, same order, the full write-up). The grade carries both colour
and text, so the page survives being read in grayscale or by someone colour-blind.

**Row order is the queue's order, never sorted.** The report is read next to the playlist it
came from, so position is information; a re-sorted row is a wrong row even when its fields are
right. (The morning-listen job — "what is broken" — is served by the triage nav block of
anchors that appears when dubbed videos need a listen, not by reordering the queue.)

A queued video with no `scout.json` renders as an explicit `не отсканировано` row and the script
says so on stdout. That is an unfinished S2 — re-run its sub-agent and rebuild, do not publish a
report with holes in it and hope they go unnoticed.

**A dubbed-but-never-scouted row is NOT that case, and must not be treated as one.** It has no
`scout.json` by design — it came off the dubbing route, which never runs S2 — so it keeps its dub
chip, borrows «о чём» from the first sentence of its `summary.md` (2026-07-22) and leaves «самое
интересное» a dash, since that one is the scout's own judgement. Running S2 over it would produce
a grade nobody asked for; the row is complete as it stands.

**Then publish it as an Artifact** so it is readable from anywhere, not just this machine. The
file is deliberately a BODY FRAGMENT (inline `<style>`, no doctype/`<html>`/`<head>`/`<body>`)
because the publisher supplies that skeleton:

- `Artifact` with `file_path` = the generated `work/scout-report.html`, a `favicon`, and a
  one-sentence `description`.
- **Re-publishing the same queue: pass the previous artifact's `url`** so it updates in place
  and the link the user already has keeps working. Only a genuinely new queue gets a new URL.

Finally, write the user a short **Russian** rundown in chat, grounded ONLY in `scout.json` —
never re-derived from the transcript. Lead with the link, then the tally (сколько high/medium/
low), then name the videos you would drop and why, and flag anything the report cannot say for
itself (a suspiciously uniform set of grades usually means the prompt is drifting, not that the
queue is uniform — check a few against the transcripts before trusting the shape).

**Recommend; never decide.** Trimming the queue is the human's call — the grades gate nothing,
exactly as the summary gates nothing on the dubbing route, and a model quietly shortening a
queue is the failure this whole mode exists to prevent.

## Promotion — handing the survivors to the dubbing route

The user trims `queue.txt` to the survivors; that queue then enters the `overdub-sonnet-batch`
skill at its **Step 1** (route B). Mechanics — what fast-skips, what re-runs, the ~5% traffic —
are [`docs/queue-contract.md`](../../../docs/queue-contract.md) §4.

Videos the user dropped keep their scout artifacts in `work/<id>/` — a few MB each, and they
make a re-scout free. Deleting them is the user's call, not yours.

## Rules that are not negotiable

The queue rules — never shorten it, never lengthen it, never stop the run to ask about ONE video,
never treat a leftover `queue.txt` as a question, never forge a completion artifact — are
[`docs/queue-contract.md`](../../../docs/queue-contract.md) §3, and they bind here unchanged.
Route C adds three of its own:

- **S3 recommends; the human drops videos.** The grades gate nothing, exactly as the summary gates
  nothing on the dubbing route. This is the specific shape §3 takes on a route whose whole output
  is a recommendation.
- **Never ground the rundown in anything but the summaries.** If a summary is missing, say so
  and respawn its sub-agent; do not read the transcript yourself and improvise one — the
  artifact on disk and the story you tell the user must be the same story.
- **Never widen the scope to dubbing.** Scout stops at S3. If the user wants the survivors
  dubbed in the same breath, hand off to the `overdub-sonnet-batch` skill explicitly rather
  than running synthesis from here.
