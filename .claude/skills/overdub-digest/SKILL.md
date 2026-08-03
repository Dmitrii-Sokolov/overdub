---
name: overdub-digest
description: "Digest an overdub queue (README route D) — retell each video from its transcript WITHOUT grading or dubbing it, so the user can check they missed nothing while watching, or know what to expect before starting. Fixed order: make sure every queued video has a transcript (audio-only fetch, fast-skips whatever is already on disk), write one digest per video with Opus sub-agents (headline · thesis · what is covered · why and caveats · what stayed in the video), build work/digest-report.html, publish it as an Artifact, then hand the user a short Russian rundown. Trigger when the user wants the CONTENT of videos rather than a verdict: 'о чём это видео подробно', 'перескажи', 'что затронуто', 'пересказ очереди', 'digest the queue', 'summarize what is covered', 'я смотрел — что мог пропустить', 'что ожидать в видео'. NOT for deciding what is worth dubbing (that is the overdub-scout skill, route C) and NOT for dubbing (overdub-sonnet-batch, route B)."
---

# overdub — digest a queue (route D)

Route D answers **"what is actually in this video"** — not "is it worth my evening" (route C) and
not "dub it" (route B). Two reading moments, one artifact: after watching, to check nothing was
missed; before watching, to know what to expect.

**download (audio only) → transcribe → stop**, then one Opus sub-agent per video writes the digest.
No translation, no TTS, no MKV, no Ollama, no `source.mkv` on disk, and no grade — a retelling is
about the video, not a verdict on it.

Three steps, in order. Do not reorder them and do not skip the gates — each step's gate is what
keeps a half-digested queue from reading as a finished one.

**Before changing the prompt, read [`docs/digest-reference.md`](../../../docs/digest-reference.md)** —
the hand-written digest of `work/fGKNUvivvnc`, the one video where output can be SCORED (six named
findings, and the rule that a perfect match is not the target). It also records why the prompt's
examples describe an invented video and must stay that way.

**When NOT to use this skill.**
- The user wants to know **which** videos deserve a dub → `overdub-scout` (route C). A digest is
  longer, costs an Opus agent per video, and deliberately carries no verdict to sort on.
- The user wants the videos **dubbed** → `overdub-sonnet-batch` (route B) or a plain `--batch` run
  (route A).
- The user asks about **one** video that already has `work/<id>/digest.md` → just read that file
  and answer. Do not re-run anything; the digest on disk is the answer, and a second retelling
  from the transcript would be a second, unverifiable version of it.

Nothing here writes `translation.json`, so a digested video is not half-translated — it is
untranslated, and it enters the dubbing route with no cleanup (see "Promotion" below).

## What is cached, and what that buys

Three independent layers, and the point of all three is that **re-running the whole route on a
queue you have already digested costs seconds**, not an Opus wave:

1. **The transcript** — the pipeline's own fast-skip. `download` and `transcribe` are done when
   `source.wav` and `sentences.json` exist, so D1 over an already-scouted (or already-dubbed) queue
   re-reads what is on disk and stops. This is the same mechanism that makes route C's promotion
   free, and it is why route D is cheap on any queue that has been through C.
2. **The digest, in two independently cached halves** — because D2 is two passes (read, then
   compress) and they cost very differently. The read pass is the expensive one: it reads the whole
   transcript. The compress pass reads one small JSON. So the filter produces TWO lists:
   `digest.long.json` stale or missing → both passes; a fresh long digest whose
   `digest.draft.json` is missing or older → **compression only**. A change to the compressor's
   prompt therefore never re-pays the read. Both halves key on mtime, so a transcript that changed
   underneath (`--scout --force`, a `--repair-asr` pass) invalidates the long digest and everything
   derived from it.
3. **The page** — not cached and does not need to be: `digest_report.py` is pure string assembly
   over the artifacts, so rebuilding it is free and always reflects disk.

**The cache keys are the two AGENT artifacts, never the built `digest.json`** — the derived-artifact
rule, [`docs/queue-contract.md`](../../../docs/queue-contract.md) §5, with the sibling route's
measured case of a six-video report representing zero work. The build script guarantees a
well-formed artifact; that is exactly why a well-formed artifact proves nothing about whether the
agent ran.

## D1 — Resolve the queue, then make sure every video has a transcript

**Read [`docs/queue-contract.md`](../../../docs/queue-contract.md) now, before anything else.**
Sections 1-3 are this step: who owns `queue.txt`, the `$ids` block and its three load-bearing
guards, the `# playlist:` freshness diff, and the rule that a queue is never shortened, lengthened
or interrupted by a model. Run §1 and §2 verbatim.

Route-D specifics on top of the contract:

- Duplicate spellings of one video would race two sub-agents on one draft — hence `-Unique`.
- Under §3, a video with almost nothing to retell is still digested: an honest "there is nothing
  here to retell", written INTO the digest, is a finished row, while a skipped video is a hole.
  The digester prompt says this too.

Then run:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --scout
```

Single video: the URL instead of `--batch queue.txt`.

Yes, `--scout` — route D has no mode of its own on purpose. `--scout` **is** "fetch audio,
transcribe, stop", which is exactly route D's input, and both stages fast-skip on anything already
on disk (cache layer 1). It does NOT compose with `--only` or `--repair-asr` (usage error, exit 2,
refused before any side effect). `--scout --force` re-runs the large-v3 transcribe too — which
invalidates every digest of that video, and cache layer 2 will notice by mtime.

Its per-video line reads `scouted · <duration> · <n> sentences · summary pending|ok`. **That
`summary` word is route C's artifact, not this route's** — ignore it here; a `summary pending`
line says nothing about whether a digest exists.

**Gate before D2:** `work/<id>/sentences.json` exists for every id in `$ids`.

```powershell
$ids | Where-Object { -not (Test-Path "work\$_\sentences.json") }   # must print nothing
```

A video that failed drops out with a `FAIL` row — re-run the same D1 command (completed stages
fast-skip). One failure mode is by design: `-f bestaudio` has no `/best` fallback, so a source with
no audio-only format fails here rather than silently pulling a full video stream at ~20× the bytes.

## D2 — Digest each video, then compress it

**Two passes per video, both Opus, both explicit in the workflow.** Pass 1 reads the whole
transcript and writes `digest.long.json` — complete coverage, no length pressure at all. Pass 2
reads only that file and writes `digest.draft.json` — the same document cut to roughly a third.

**Why it is split, because a single pass looks obviously cheaper and does not work.** Same video
(`fGKNUvivvnc`, 59 min, 691 sentences), same transcript, only the brevity instruction changed:

```
sentence counts ("1-3 sentences")   11,266 chars   7 points   10 cap truncations
character budgets ("~450 chars")    11,591 chars   9 points   12 cap truncations
```

Zero reduction (+3%) against a predicted 3,500. A model cannot count characters while composing, and
the budget line loses to the concrete instruction beside it ("put the mechanism, the number, the
example in each point"). Then the caps did the damage the length fight was meant to prevent: a
truncation deleted the «plan A / plan B» framing out of one point's tail — the one finding of the
reference digest that the earlier run had missed entirely. **A cap deletes content, and it deletes
the marginal finding first.** An editor holding the text can count; a writer predicting its own
output cannot. Hence two passes (DECISIONS 2026-07-30).

Opus for both, and set it explicitly: an inherited session model makes two runs of one queue
incomparable, and compression is not the easy half — deciding which point to drop is the judgement
that decides what the page says.

**This step needs a session that has the `Workflow` tool** — and never a hand fan-out. Both rules,
and the measurements behind them, are
[`docs/queue-contract.md`](../../../docs/queue-contract.md) §6. If you do not have the tool: stop
here and say so.

**Resume filter first — this is cache layer 2, and it produces TWO lists:**

```powershell
function Fresher($a, $b) { (Get-Item $a).LastWriteTime -gt (Get-Item $b).LastWriteTime }
$digTodo = @(); $compressTodo = @()
foreach ($id in $ids) {
  $s = "work\$id\sentences.json"; $l = "work\$id\digest.long.json"; $d = "work\$id\digest.draft.json"
  if (-not (Test-Path $l) -or (Fresher $s $l)) { $digTodo += $id }        # read pass needed
  elseif (-not (Test-Path $d) -or (Fresher $l $d)) { $compressTodo += $id }  # compression only
}
"digTodo: $($digTodo -join ', ')"; "compressTodo: $($compressTodo -join ', ')"
```

Keyed on the two AGENT artifacts and on mtime, never on `digest.json` — see "What is cached" above.
A video appears in **at most one** list: the read pass always runs its own compression.

**Delete stale markers for every video about to be respawned — both lists:**

```powershell
($digTodo + $compressTodo) | ForEach-Object {
  Remove-Item "work\$_\digest.started" -ErrorAction SilentlyContinue }
```

For `$digTodo` this is the ordinary reason (contract §7). For `$compressTodo` it matters MORE, and
the reason is worth knowing — the marker belongs to a read pass that ran in an earlier session, so
keeping it would make `digest_sec` span from that session's start to this compression's end and
bill hours of idle time as digest work. Deleting it costs the timing (`build_digest` warns, and the
page marks the wave a floor) and buys an honest unknown instead of a wrong measurement.

**Stamp the wave start before spawning anything** — it cannot be recovered afterwards, and the
page's wall-clock figure for the wave is derived from it:

```powershell
$waveStart = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
```

**DO NOT spawn the sub-agents yourself. Run the workflow:**

```powershell
# both lists are RESUME-FILTERED — never pass the whole queue
```
```
Workflow: {name: "digest-videos",
           args: {ids: [...$digTodo], compressOnly: [...$compressTodo], root: "D:\\code\\overdub"}}
```

It returns `{done, failed, failedDigest, failedCompress, dropped, total}`. **The split is the point:**
a `failedDigest` id goes back into `ids` (both passes), a `failedCompress` id into `compressOnly`
(the cheap half only). Re-running the wrong one pays for the transcript read twice.

**Verify from disk, not from the run's account** (contract §7). Three things, and the first two go
missing quietly:

```powershell
# 1. the read pass landed for everything that needed it
$digTodo | Where-Object { -not (Test-Path "work\$_\digest.long.json") }    # must print nothing
# 2. the compress pass landed for BOTH lists — this is the real completion check
($digTodo + $compressTodo) |
  Where-Object { -not (Test-Path "work\$_\digest.draft.json") }           # must print nothing
# 3. markers exist and are seconds apart, not ~100 s (a ~100 s gap means the fan-out did not happen)
($digTodo + $compressTodo) | Where-Object { Test-Path "work\$_\digest.started" } |
  ForEach-Object { (Get-Item "work\$_\digest.started").LastWriteTime } | Sort-Object
```

A video with a `digest.long.json` and no `digest.draft.json` is the one state to read carefully: the
expensive half is DONE and only compression is missing. Put it in `compressOnly` — never in `ids`.
`build_digest` says so too rather than leaving you to notice.

An agent that could not write and handed its fields back as text: write the file yourself from its
answer, verbatim — `digest.long.json` for a read pass, `digest.draft.json` for a compression. That is
not the same as inventing one: the content came from the agent that did the reading.

Then **assemble the artifacts** — `scripts/build_digest.py` reads `digest.draft.json` only and owns
everything deterministic (title, channel, upload date, duration, sentence count, stage timings, the
`at`-marker validation), and renders `digest.md` from the same document so the page and the pasteable
file can never disagree:

```powershell
($digTodo + $compressTodo) | ForEach-Object {
  .venv-asr\Scripts\python.exe -X utf8 scripts\build_digest.py "work\$_" --wave-start $waveStart }
```

It never falls back to `digest.long.json`, even when one is sitting right beside the missing draft:
publishing the uncompressed version would be a format regression with no signal anywhere, so this
fails loudly and names the compress pass instead.

Read its warnings — three are about the CONTENT, and each names a different pass to re-run:

- `last point marker at Ns of an Ms video` — the digest probably covers the opening and stops. That
  is the one failure "did I miss anything" cannot survive, and it is invisible on the page. This is
  the READ pass: re-run the id in `ids`.
- `'at' … is past the video's Ns — dropped as fabricated` — an invented timestamp. One dropped
  marker is cosmetic; several from one video mean its digest deserves a skim against the transcript
  before you publish it. Also the read pass (the compressor may not re-time anything).
- `'…' is N chars, capped at M` — the COMPRESSOR overshot its budget, and the cap is now cutting
  prose mid-sentence on the page. Re-run the id in `compressOnly`; it is the cheap half, and leaving
  the truncation costs whatever sat at the end of that field — measured 2026-07-30, that was the
  digest's only mention of «plan A / plan B». A handful of these across a batch is the signal that
  the compressor's budget needs revisiting, not that one video is unusual.

**The sub-agent prompt lives in `.claude/workflows/digest-videos.js`, not here** (contract §6).
Edit the script.

## D3 — Build the page, publish it, hand it over

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\digest_report.py --queue queue.txt
```

Writes `work/digest-report.html`: a header with the tally and the timing strip, then a **scan table**
(№ · превью · название · длительность · что это · темы) and the **digests** (same videos, same
order, the full retelling — headline, thesis, «Ключевые находки», «Зачем и оговорки», «Стоит
смотреть, если»).

**Row order is the queue's order, never sorted.** The page is read next to the playlist it came
from, so position is information; a re-sorted row is a wrong row even when its fields are right.

A queued video with no digest renders as an explicit state row — `нет пересказа` (D2 unfinished),
`не расшифровано` (D1 unfinished), `не скачано` (the fetch failed) — and the script names each on
stdout with the action it needs. Do not publish a page with holes in it and hope they go unnoticed;
each state has a different fix, which is why they are three labels and not one.

**Then publish it as an Artifact** so it is readable from anywhere. The file is deliberately a BODY
FRAGMENT (inline `<style>`, no doctype/`<html>`/`<head>`/`<body>`) because the publisher supplies
that skeleton:

- `Artifact` with `file_path` = the generated `work/digest-report.html`, a `favicon`, and a
  one-sentence `description`.
- **Re-publishing the same queue: pass the previous artifact's `url`** so it updates in place and
  the link the user already has keeps working. Only a genuinely new queue gets a new URL.

Finally, write the user a short **Russian** rundown in chat: the link first, then the tally (how
many digested, how many holes and which), then anything the page cannot say for itself — a video
whose transcript was too thin to digest, a coverage warning you decided to accept, a queue whose
digests all came out suspiciously alike (that usually means the prompt is drifting, not that the
queue is uniform — check two against their transcripts before trusting the shape).

**Do not re-tell the videos in chat.** The page is the artifact and it is the only version of the
retelling; a chat summary of a summary is a second, unverifiable copy that will diverge from the
file on disk. If the user asks about one video, quote from its `digest.md`.

## Promotion — a digested queue entering the dubbing route

Nothing to clean up. That queue enters `overdub-sonnet-batch` at its **Step 1** (route B), or a
plain `--batch` run (route A); the mechanics are
[`docs/queue-contract.md`](../../../docs/queue-contract.md) §4. The digest artifacts survive the
dub untouched, and are **not** refreshed by a `--repair-asr` pass either — which is what cache
layer 2's mtime check is for.

## Rules that are not negotiable

The queue rules — never shorten or lengthen it, never forge a draft to fill a gap, a
`# playlist:` header is provenance and not freshness, a derived artifact is not evidence — are
[`docs/queue-contract.md`](../../../docs/queue-contract.md) §2-3 and §5. Route D adds four:

- **A digest never grades and never recommends.** No `quality`, no watch/skip, no ranking, and the
  page never sorts. "Стоит смотреть, если" is an inventory of what stayed in the video, not a
  verdict — the moment it becomes advice, this route is a worse copy of route C.
- **Every claim comes from the transcript.** No fact, name or number that is not in it. The ASR
  transcript is itself imperfect, so an obviously garbled term is written as what was evidently
  meant and never silently upgraded into a fact; a transcript too thin to digest is reported as
  such, in the digest, not skipped.
- **Never publish the long digest as the digest, and never edit either file by hand to fit.**
  `digest.long.json` is the read pass's record; the page renders the compressed draft. Copying the
  long one over the draft ships a document 3× the intended length with no signal anywhere, and
  trimming a field by hand destroys the only evidence of what compression cost.
- **Never widen the scope to dubbing or grading.** Route D stops at D3. If the user wants the queue
  dubbed, hand off to `overdub-sonnet-batch` explicitly; if they want to know what is worth dubbing,
  hand off to `overdub-scout`.
