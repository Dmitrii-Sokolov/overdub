---
name: overdub-scout
description: "Scout an overdub queue (README route C) — the --scout pre-pass that downloads audio only, transcribes and grades each video WITHOUT dubbing it, so the user can decide what earns their time and a full dub. Fixed order: scout the batch, grade the MATERIAL (substance/currency/delivery) and summarize each video with Sonnet sub-agents, build work/scout-report.html (grade · preview · title · what it is · what is most interesting, in queue order, plus a write-up per video), publish it as an Artifact, then hand the user a recommend-only Russian rundown. Trigger when the user has a queue they have not watched: 'разведка по очереди', 'что тут стоит дублировать', 'прогони разведку', 'scout the queue', '--scout', 'summaries only, no dub', 'о чём эти видео'. NOT for dubbing — once the queue is chosen, hand off to the overdub-sonnet-batch skill (route B) or a plain --batch run (route A)."
---

# overdub — scout a queue (route C)

Scout answers **"is this worth dubbing"** before anything expensive runs:
**download (audio only) → transcribe → stop**, then one Sonnet sub-agent per video writes the
summary. No translation, no TTS, no MKV, no Ollama, no `source.mkv` on disk.

A preflight and three steps, in order. Do not reorder them and do not skip the gates — each
step's gate is what keeps a half-scouted queue from reading as a finished one.

**When NOT to use this skill.** If the queue is already chosen, scouting buys nothing and still
costs the audio fetch and a sub-agent per video — go straight to the `overdub-sonnet-batch`
skill (route B) or a plain `--batch` run (route A). Scout is for a queue nobody has watched.

Nothing here writes `translation.json`, so a scouted video is not half-translated — it is
untranslated, and it re-enters the dubbing route with no cleanup (see "Promotion" below).

## S0 — Preflight: the viewer profile (do this FIRST, before touching the queue)

```powershell
Test-Path .claude\viewer-profile.md
```

**If it exists, read it now** and carry it into S2 — nothing else in this preflight applies.

**If it does not exist, STOP and put the choice to the user before running anything.** Do not
scout first and sort the profile out later: S1 is the expensive half (a download and a
large-v3 pass per video) and it would be spent on a pass that cannot produce usable verdicts.
And never proceed by rating on generic video quality — a verdict with no basis looks exactly
like a grounded one in the report, which is the failure this whole file is built to avoid.

Offer exactly two ways forward, in this order:

1. **Generate it from their own history.** The prompt is committed at
   [`references/viewer-profile-prompt.md`](references/viewer-profile-prompt.md). Read that file
   and hand the user the part below its `---` separator, ready to paste into a fresh chat on
   claude.ai. **This cannot be done from here:** Claude Code has no access to their conversation
   history, profile or memory, which are the whole point of the exercise. Do not offer to write
   the profile yourself from what you can see in this session — that produces a plausible file
   with no evidence behind it, the worst of the three outcomes. When they come back with the
   result, write it to `.claude/viewer-profile.md` verbatim.
2. **Take a file they already have.** If they hand over a path or paste the contents, write it
   to `.claude/viewer-profile.md` as is. Do not "improve" it, do not reformat it into the
   section headings above — the summarizer reads it as free text, and an unfamiliar shape is
   the author's choice, not a defect. Only say something if it is empty or is clearly not a
   profile.

`.claude/viewer-profile.md` is **gitignored** — one person's skills and gaps, not repo content.
The prompt that builds it is committed. So a fresh clone has the tool and not the data, which is
the intended state: this preflight will fire for the next person too.

## S1 — Scout the batch

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

**If the user handed over a PLAYLIST rather than a list of videos**, record where the queue came
from as the first line of `queue.txt`, before expanding it:

```
# playlist: <название плейлиста> | <url плейлиста>
https://www.youtube.com/watch?v=...
```

The report names it at the top and links the title. Nothing else depends on the line — it is a
comment, so the pipeline skips it exactly as it always has — but without it the report is a list
of videos with no answer to "which playlist was this". Only the first such line is read.

**The id list comes from the QUEUE, never from a `work/` listing.** `<id>` is the 11-char
YouTube id inside each URL (S1 also prints it per video: `work dir: work\<id>`):

```powershell
$lines = @(Get-Content queue.txt | ForEach-Object { $_.Trim() } |
  Where-Object { $_ -and -not $_.StartsWith('#') })
$ids = @($lines | ForEach-Object {
  if ($_ -match '(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})') { $Matches[1] } })
if ($ids.Count -ne $lines.Count) {
  throw "queue: $($lines.Count) URLs, $($ids.Count) matched ids - unmatched line(s), see below" }
$ids = @($ids | Select-Object -Unique)
```

Both guards are load-bearing. A URL the regex misses (e.g. a `/live/` link) is still PROCESSED
by the pipeline — `video_id()` hash-fallbacks it into a `work/<sha1>` dir — but invisible to
every gate below, so it silently never gets summarized: normalize the URL in `queue.txt` to a
`watch?v=` form and restart from S1. Duplicate spellings of one video share a workdir and the
CLI dedupes them (`cli.py`); without `-Unique` two parallel sub-agents would race on the same
`summary.md`.

Do NOT enumerate `work/` directories — `work/` persists across batches and holds stale and
baseline workdirs. Summarizing those wastes tokens on videos nobody queued.

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
verified with, DECISIONS 2026-07-18/19). Spawn in waves of ~6.

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

**Stamp the wave start before spawning anything** — it is the only clock the per-video
summarize timing has, and it cannot be recovered afterwards:

```powershell
$waveStart = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
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

**Feed every sub-agent `.claude/viewer-profile.md` whole** — the file S0 confirmed. Paste its
CONTENTS into each prompt rather than pointing the sub-agent at the path: a sub-agent that
cannot read it rates on generic quality and says nothing about having done so, which is exactly
the ungrounded verdict S0 exists to prevent. If you somehow reach this step without the file,
go back to S0; do not improvise one.

Sub-agent prompt skeleton (fill `<id>`) — the prose half is **identical to the summarizer in the
`overdub-sonnet-batch` skill's Step 2**; if you change that half, change it there too:

> You are a triage summarizer for the overdub pipeline. Read
> `D:\code\overdub\work\<id>\sentences.json` (list of `{id, text, start, end}` — the COMPLETE
> English transcript, in order) and write `D:\code\overdub\work\<id>\summary.md`: a summary in
> RUSSIAN of about 200 words. The reader has NOT watched the video and is deciding whether to. So
> answer two things, in prose: (a) is this worth watching at all, and for whom — say so plainly,
> including "смотреть не стоит" if that is the honest read; (b) what is the single most interesting
> thing in it / what to look out for, and roughly where (use the `start` timestamps, `M:SS`).
> Ground every claim in the transcript — do not invent facts, names, or numbers that are not there,
> and if the transcript is too garbled or thin to judge, say that instead of guessing. Plain
> paragraphs only: no markdown headings, no bullet lists, no title, no preamble like "Вот краткое
> содержание" — the file's whole content is the summary text. Read the file in one pass; write it
> in one pass.
>
> Also read `D:\code\overdub\work\<id>\source.info.json` — the yt-dlp metadata sidecar. Take
> `title`, `channel`, `upload_date` (`YYYYMMDD`) and `description` from it. The transcript alone
> carries none of these, and without them a profile's staleness rules and any author rule are
> dead letters. Treat `description` as the author's own framing, i.e. promotional: useful for
> what the video CLAIMS to be, never as evidence that it delivers. **If the file is absent or
> carries only a title, say so in the paragraph and do not infer an age** — an invented upload
> date is worse than an acknowledged gap.
>
> Then write `D:\code\overdub\work\<id>\scout.draft.json`, a JSON OBJECT (not a list) with these
> keys:
> - `quality` — one of exactly `"high"` / `"medium"` / `"low"`. **Judge the MATERIAL, not the
>   reader.** Three things and only these three: substance (is there real information, with
>   mechanism, numbers, method — or is it one tip padded out), currency (is what it shows still
>   true, judged from `upload_date` and from what it demonstrates), and delivery (density,
>   structure, whether the presenter knows the subject). `high` = strong on all three.
>   `medium` = solid but undercut by one of them. `low` = fails on substance, or is superseded,
>   or the delivery makes it not worth extracting from. **Do NOT factor in whether this
>   particular person should watch it** — a well-made video on a topic they do not need is
>   still well made. When torn, choose the lower grade and name the reason in `highlight`.
>   (Superseded 2026-07-20: this used to be a personal watch/maybe/skip verdict and the first
>   real queue came back 0/1/9. A grade about the material can be checked; a verdict about a
>   person cannot.)
> - `author` — OPTIONAL, `"trusted"` or `"new"`. Emit it ONLY if the profile carries a
>   non-empty list of trusted authors and you can match `channel` against it. With no such list
>   there is nothing to compare against: omit the key entirely rather than labelling everything
>   `"new"`, which would add a column of one repeated value.
> - `one_liner` — ONE sentence in Russian, what the video is about. It goes in a table cell;
>   keep it under ~140 characters and do not restate the title.
> - `highlight` — ONE sentence in Russian: **the most interesting or useful thing IN the video**,
>   plus what decided the grade. A different question from `one_liner` and it must not repeat
>   it: "разбор оркестрации агентов" says what the video is, "замеры с описанной методологией и
>   разбор случаев, где схема ломается" says what you would actually get out of it. For a `low`,
>   name the concrete defect rather than a mood. Under ~200 characters.
>   **Add "требует концентрации" here when the video needs undivided attention** (a deep dive
>   you have to follow with practice, rather than something that survives being background
>   listening). This used to be a separate enum and 28 of 30 videos took the same value, so it
>   is now a clause that appears only when it is true.
>   This is the ONE field where the viewer profile is allowed to steer: what counts as
>   "interesting" and what is already known to this reader come from it. The GRADE does not.
> - `paragraph` — the full write-up in Russian, what is actually covered and why it earned that
>   grade. Name the concrete thing that decided it (what specifically is dated, thin or strong).
>   This is what the person reads when the one-liner interests them. **Split it into 2–3 paragraphs separated by a BLANK LINE**, where
>   the meaning turns — a wall of text is what this field looked like before and it was hard to
>   read. The split is yours: the renderer honours blank lines and never invents its own, so an
>   unsplit block simply renders as one paragraph.
>
> VIEWER PROFILE (the person deciding what to watch) — judge relevance against THIS, and quote
> nothing from it back into the summary:
>
> <<< paste the entire contents of D:\code\overdub\.claude\viewer-profile.md here >>>

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
**scan table** (№ · превью · название с оценкой · о чём · самое интересное + длительность) and
the **read cards** (same videos, same order, the full write-up). The grade carries both colour
and text, so the page survives being read in grayscale or by someone colour-blind.

**Row order is the queue's order, never sorted.** The report is read next to the playlist it
came from, so position is information; a re-sorted row is a wrong row even when its fields are
right. (This is the opposite of `triage_html.py`, which sorts the worst first on purpose — that
page answers "what is broken", this one answers "what is in my queue".)

A queued video with no `scout.json` renders as an explicit `не отсканировано` row and the script
says so on stdout. That is an unfinished S2 — re-run its sub-agent and rebuild, do not publish a
report with holes in it and hope they go unnoticed.

**Then publish it as an Artifact** so it is readable from anywhere, not just this machine. The
file is deliberately a BODY FRAGMENT (inline `<style>`, no doctype/`<html>`/`<head>`/`<body>`)
because the publisher supplies that skeleton:

- `Artifact` with `file_path` = the generated `work/scout-report.html`, a `favicon`, and a
  one-sentence `description`.
- **Re-publishing the same queue: pass the previous artifact's `url`** so it updates in place
  and the link the user already has keeps working. Only a genuinely new queue gets a new URL.

Finally, write the user a short **Russian** rundown in chat, grounded ONLY in `scout.json` —
never re-derived from the transcript. Lead with the link, then the tally (сколько watch/maybe/
skip), then name the videos you would drop and why, and flag anything the report cannot say for
itself (a suspiciously uniform set of grades usually means the prompt is drifting, not that the
queue is uniform — check a few against the transcripts before trusting the shape).

**Recommend; never decide.** Trimming the queue is the human's call — the grades gate nothing,
exactly as the summary gates nothing on the dubbing route, and a model quietly shortening a
queue is the failure this whole mode exists to prevent.

## Promotion — handing the survivors to the dubbing route

The user trims `queue.txt` to the survivors. That queue then enters the `overdub-sonnet-batch`
skill at its **Step 1** (route B), or a plain `--batch` run (route A), with no further ceremony
and no cleanup of the scout artifacts:

- `transcribe` **fast-skips** on the scout's `sentences.json` — the large-v3 pass is not
  repeated, which is the whole economic point of scouting first.
- `translate` has nothing yet, so route B's Step 2 runs normally.
- `summary.md` survives and is reused — the transcript it describes did not change.
- `download` **does re-run**: the full contract needs `source.mkv` and scout never wrote one, so
  the audio bytes are re-fetched inside the merged container. ~5% extra traffic, accepted
  deliberately (DECISIONS 2026-07-20). Do NOT try to save it by hand-assembling an MKV from
  `source.wav`.

Videos the user dropped keep their scout artifacts in `work/<id>/` — a few MB each, and they
make a re-scout free. Deleting them is the user's call, not yours.

## Rules that are not negotiable

- **A scout pass never shortens the queue by itself.** S3 recommends; the human drops videos. A
  model silently deciding a video is not worth dubbing is indistinguishable, downstream, from
  the pipeline losing it — and unlike a lost video, nothing reports it.
- **Never hand-write a `summary.md`** to clear a `summary pending` line. That line is the pass's
  only completion signal, and forging it is the same silent failure in miniature.
- **Never ground the rundown in anything but the summaries.** If a summary is missing, say so
  and respawn its sub-agent; do not read the transcript yourself and improvise one — the
  artifact on disk and the story you tell the user must be the same story.
- **Never widen the scope to dubbing.** Scout stops at S3. If the user wants the survivors
  dubbed in the same breath, hand off to the `overdub-sonnet-batch` skill explicitly rather
  than running synthesis from here.
