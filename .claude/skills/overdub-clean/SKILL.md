---
name: overdub-clean
description: "Produce a readable text of each queued video in ITS OWN language, English or Russian (README route E) — transcribe, repair the ASR defects where the engine allows it, then clean the transcript chunk by chunk with Sonnet sub-agents and save it as work/<id>/clean.md. Minimal processing by contract: filler and false starts out, wording and sentence order untouched, nothing summarised and nothing translated. Fixed order: transcribe the queue (audio only), run --repair-asr auto when asr_engine is whisper, plan the chunk cut with scripts/build_clean.py --plan (which also detects the language), fan the chunks out through the clean-transcript workflow, join with build_clean.py, then hand the user a short Russian rundown. Trigger when the user wants to READ a video instead of watching it: 'текстовая версия', 'вычищенный транскрипт', 'сделай текст по видео', 'расшифровка', 'clean transcript', 'readable transcript', 'text of the video'. NOT a short summary (that is overdub-scout, route C), NOT dubbing (overdub-sonnet-batch, route B), and NOT a translation — a Russian video comes back as Russian text."
---

# overdub — clean transcript (route E)

Route E answers **"let me read this instead of watching it"**. The deliverable is the video's own
text — English or Russian, whichever the video is — cleaned enough to read: `work/<id>/clean.md`.

**Nothing here is translated, in either direction.** A Russian video produces Russian text; the
language is detected per video by `build_clean.py --plan` and carried to the sub-agents, which get a
different filler list for each. If the user wants a Russian video turned into English (or the
reverse), that is not this route and not any route in this repo today — say so rather than improvising.

**download (audio only) → transcribe → repair → clean → stop.** No translation, no TTS, no MKV,
no `source.mkv` on disk.

This route is defined by what it does NOT do. It is the only route whose output is roughly as long
as its input, and that is the point: a reader who wanted the short version would be reading a
scout summary. Every instruction below that looks pedantic about length is protecting exactly that.

**When NOT to use this skill.**
- The user wants to know **what is in** a video, briefly → `overdub-scout` (route C), ~200 words
  per video instead of the whole text.
- The user wants the videos **dubbed** → `overdub-sonnet-batch` (route B), the only route that ends
  in a dub.
- The user asks about **one** video that already has `work/<id>/clean.md` → read that file and
  answer from it. Do not re-run anything.

## What is cached

Two layers, and together they make a re-run over an already-processed queue cost seconds:

1. **The transcript** — the pipeline's own fast-skip. `download` and `transcribe` are done when
   `source.wav` and `sentences.json` exist, so E1 over a queue that was scouted or dubbed
   re-reads what is on disk and stops.
2. **The chunk drafts** — `work/<id>/clean/<from>-<to>.json`, one file per chunk, keyed on mtime
   against `sentences.json`. A chunk whose file is fresh is not re-spawned, so a failed wave costs
   only its failures.

`clean.json` and `clean.md` are **derived** and are never cache keys: `build_clean.py` rebuilds both
from the drafts in a fraction of a second. A present `clean.md` is not evidence that the chunks were
cleaned — the drafts are.

## E1 — Resolve the queue, then make sure every video has a transcript

**Read [`docs/queue-contract.md`](../../../docs/queue-contract.md) now, before anything else.**
Sections 1-3 are this step: who owns `queue.txt`, the `$ids` block and its three load-bearing
guards, the `# playlist:` freshness diff, and the rule that a queue is never shortened, lengthened
or interrupted by a model. Run §1 verbatim, and apply §2 as §1 directs — the trigger lives there,
not here.

Route-E specific: a duplicate id races two waves over **one set of chunk files**, which is the
worst form of that collision in the repo — hence `-Unique`.

Then run:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --scout
```

Single video: the URL instead of `--batch queue.txt`. `--scout` **is** "fetch audio, transcribe,
stop", which is exactly this route's input; route E has no mode of its own on purpose. Its per-video
line mentions `summary pending|ok` — that is route C's artifact and says nothing here.

**Gate before E2:**

```powershell
$ids | Where-Object { -not (Test-Path "work\$_\sentences.json") }   # must print nothing
```

## E2 — Repair the ASR defects, BEFORE anything is cleaned — whisper only

**Check the engine first. On the shipped default this step does not run at all:**

```powershell
.venv-asr\Scripts\python.exe -X utf8 -c "from overdub.config import Config; from pathlib import Path; print(Config.load(Path('overdub.toml')).asr_engine)"
```

- `parakeet` (the default) → **skip E2 and go to E3.** `--repair-asr` raises on any engine but
  whisper, by design: its accept gate is "two readings of the clip agree", which is vacuously true
  on a deterministic decoder, so it would splice unverified text while reporting it as verified
  (DECISIONS 2026-08-06). Parakeet re-reads its own uncovered spans inside the worker, before the
  transcript is written. Running the command anyway costs the batch a `RuntimeError`, not a repair.
  Say in the E4 rundown that the pass was skipped and why — a reader must not take a Parakeet
  transcript for a repaired one.
- `whisper` → run it:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --repair-asr auto
```

  One caveat that matters for a **Russian** queue: repair decodes its windows with
  `language=cfg.source_lang`, which is `en`. On a Russian video that produces garbage, so do not
  run whisper repair over a Russian queue — the config key means "what the dubbing pipeline
  expects", not "what this video is" (`.claude/INBOX.md` carries the open item).

**When it does run, the order is not negotiable, and it is enforced by the code rather than by
discipline.** A repair
splices new sentences into `sentences.json` and RENUMBERS every later id, so `invalidate_downstream`
deletes `clean/`, `clean.json` and `clean.md` along with the translate artifacts — a clean pass run
first is thrown away, silently and correctly. Repair first, clean second.

Why this route needs the repair when the dubbing routes tolerate skipping it: an ASR defect in a dub
goes past the ear in half a second, while in a text it sits on the page as a repeated line or a
garbled clause and reads as a broken tool. `auto` seeds itself from the two source detectors
(`rate_implausible`, `dup_adjacent`), re-reads each defect window twice in isolation and accepts only
on agreement — it never invents text, and a window whose readings disagree is left alone and
reported. It is idempotent: a repaired video's detectors go quiet, so re-running costs nothing.

Read what it prints. A window it REJECTED is a defect that is still in the transcript and will reach
the page; that is a note for the rundown in E4, not a reason to hand-edit anything.

## E3 — Plan the chunks, then fan them out

**The cut comes from the script, never from you:**

```powershell
$jobs = @()
foreach ($id in $ids) {
  $plan = .venv-asr\Scripts\python.exe -X utf8 scripts\build_clean.py "work\$id" --plan | ConvertFrom-Json
  if (-not $plan) { "[FAIL] $id — no plan (see the message above); skipped"; continue }
  foreach ($c in $plan.chunks) {
    $f = "work\$id\clean\$($c.from)-$($c.to).json"
    # resume filter: a draft newer than the transcript is done work
    if ((Test-Path $f) -and (Get-Item $f).LastWriteTime -gt (Get-Item "work\$id\sentences.json").LastWriteTime) { continue }
    $jobs += @{ video = $id; from = [int]$c.from; to = [int]$c.to; lang = $plan.lang }
  }
}
"$($jobs.Count) chunk(s) to clean · " + (($jobs.lang | Sort-Object -Unique) -join '+')
```

`build_clean.py` cuts on the longest pause near its target and the SAME function re-derives the cut
at join time, so a hand-written range would fail the join with ids belonging to no chunk. Use
`--chunk N` on both calls or on neither. The cut is the same for both languages — Russian sentences
average 79 characters against an English median of 80 (measured 2026-08-14), so 80 sentences lands
in the same place on either.

**`lang` comes from the plan and is never typed by hand.** It is `en` or `ru`, detected from the
transcript, and the workflow refuses a job without it. A video whose plan FAILED with "neither
clearly English nor clearly Russian" is a real decision to make, not a glitch: look at
`sentences.json` yourself, and if you can say what it is, re-run that video's plan with
`--lang en|ru`. If you cannot, leave it out of the wave and report it in E4.

**This step needs a session that has the `Workflow` tool, and never a hand fan-out** — both rules
and their measurements are [`docs/queue-contract.md`](../../../docs/queue-contract.md) §6. If you
do not have the tool: stop here and say so.

**DO NOT spawn the sub-agents yourself. Run the workflow:**

```
Workflow: {name: "clean-transcript",
           args: {jobs: [...$jobs], root: "D:\\code\\overdub"}}
```

It returns `{done, failed, dropped, total}`. **Verify from disk rather than from that account** — a
chunk it calls done can still be missing:

```powershell
$jobs | Where-Object { -not (Test-Path "work\$($_.video)\clean\$($_.from)-$($_.to).json") }
```

Must print nothing. Anything listed goes back into `$jobs` for another wave; every other chunk stays
on disk and is not re-paid for.

An agent that could not write and handed its array back as text: write that file yourself, verbatim.
That is not inventing one — the content came from the agent that read the range.

## E4 — Join, then hand it over

```powershell
$ids | ForEach-Object {
  .venv-asr\Scripts\python.exe -X utf8 scripts\build_clean.py "work\$_" }
```

Writes `work/<id>/clean.json` (every sentence with its source beside the cleaned text, so the pass
stays auditable) and `work/<id>/clean.md` (the deliverable: a metadata header, then timecoded
paragraphs broken on the speaker's own pauses).

It **exits** on anything that makes the join untrustworthy — a missing chunk file, a chunk short of
ids, a chunk carrying foreign ids, an id in no chunk at all. Each names the chunk to re-run. The
last one usually means a stale plan against a repaired transcript: re-run E3 for that video.

Read its warnings — all of them are QUALITY signals and none block the build:

- `chunk N-M came back in a DIFFERENT SCRIPT` — that agent translated instead of cleaning. Re-run
  that chunk, and read the result before joining again: this is the one warning that is not a
  judgement call, because a translated chunk passes every other check here (complete, correctly
  numbered, right length). Expect it to be the failure mode of a mixed-language queue.
- `chunk N-M kept 43% of its source` — that agent summarised instead of cleaning. Re-run **that
  chunk**, not the video. This is the route's characteristic failure and the reason the ratio is
  measured per chunk.
- `the document kept 61% of the transcript` — the same defect spread thin, or a genuinely
  filler-heavy speaker. Check one chunk against `sentences.json` before deciding which.
- `N lines were emptied` — filler removal does not reach a quarter of the lines; a high share means
  an agent dropped content it judged uninteresting.
- `N number(s) ... absent` — a dropped figure. Precise in either language: cleaning leaves numbers
  verbatim.
- `N capitalised term(s) dropped` — noisier by design, because a name the agent CORRECTED lands here
  too. Triage hint, never a verdict. It is **Latin-only on Russian as well**, and that is measured,
  not forgotten (README route E) — so on a Russian video it reports the English terms and stays
  silent about Cyrillic names. On the `ru` path it doubles as the check on term restoration: a
  Cyrillic term the agent turned into `JSON` shows up here as a "dropped" Latin term only when the
  agent invented one, never when it corrected a spelling.

Then write the user a short **Russian** rundown: where the files are, how many videos and
paragraphs, which language each came out in, and anything the files cannot say for themselves — a
repair pass that was SKIPPED because the engine is Parakeet, a repair window that was rejected, a
chunk you re-ran, a video whose transcript was too thin to be worth reading. Offer the files with
`SendUserFile` if the user wants them in hand rather than on disk.

**Do not paste the transcript into chat.** The file is the artifact.

## Promotion — a cleaned queue entering another route

Nothing to clean up, and nothing here writes `translation.json`, so a cleaned video is untranslated
rather than half-translated. It enters route B at its Step 1 or route C at S2; the mechanics are
[`docs/queue-contract.md`](../../../docs/queue-contract.md) §4.

Going the other way, a queue that was scouted arrives here with its transcript already on disk, so
E1 costs seconds.

## Rules that are not negotiable

The queue rules — never shorten or lengthen it, never hand-write a draft from your own reading of
the transcript, a derived artifact is not evidence — are
[`docs/queue-contract.md`](../../../docs/queue-contract.md) §3 and §5; under §5 the evidence here
is the per-chunk drafts under `clean/`, never `clean.json` or `clean.md`. Route E adds six:

- **The language is detected, never assumed and never asked of the agents.** It comes from
  `build_clean.py --plan`, travels in the job, and picks the filler list the cleaner works against.
  A transcript the detector refuses is a video you look at yourself and then pass `--lang`, or leave
  out of the wave — the one thing that must not happen is a chunk cleaned against the wrong
  language's rules, because nothing in the finished document shows it.

- **Minimal processing is the contract, not a preference.** Filler and false starts out; wording,
  register, sentence order and sentence boundaries untouched. The moment this route starts
  rephrasing, it becomes a worse summary with a longer runtime.
- **Never merge, split or move text between ids.** Every id is anchored to a timestamp, paragraphs
  are assembled from the pauses afterwards, and a moved line makes the text disagree with the audio
  it claims to be.
- **An emptied line is written `""`; a missing id is a failure.** The two are indistinguishable in a
  text file after the fact, which is why the build refuses the second.
- **Repair before clean, always.** Reversing it deletes the clean pass, by design.
- **Writing down an agent's returned array is not hand-writing a draft.** That content came from
  the agent that read the range; inventing one from the transcript yourself is the §5 violation.
