# The queue contract — shared by every route

Everything routes B, C and E do **identically**: resolving the queue into an id list, deciding
whether that queue is still current, promoting a queue from one route to another, and fanning
sub-agents out. It lives here once because it used to live in four skills at once, and a rule
copied four times is a rule that drifts three ways: on 2026-07-28 the translate contract was
de-duplicated out of `overdub-sonnet-batch/SKILL.md` and PLAN's inventory of where it lived was
still naming that file five days later.

**This file is a MANDATORY READ before section 1 of any route skill.** An orchestrator that cannot
read it stops and says so rather than improvising the guards — every one of them exists because a
real run lost videos without it.

The route skills own what differs: the pipeline command, the artifacts, the gates, the report.

**Section numbers are a join key.** The four skills, README and `.claude/PLAN.md` cite this file by
number, and renumbering breaks none of those references visibly — it just points them somewhere
else. Numbering is therefore APPEND-ONLY: a new section goes at the end. Renaming a heading is free.

Do not trust that list to be current — it was wrong in both directions on 2026-08-03, naming
CLAUDE.md (which cites this file by PATH, never by §) while missing PLAN.md. Before renumbering,
re-derive it: `git grep -n '§[0-9]'` over the repo, then check each hit resolves to the heading it
means.

---

## 1. `queue.txt` belongs to the RUN, and the id list comes from it

`queue.txt` is gitignored, hand-authored INPUT, rewritten every session by design. A leftover queue
from the previous run is **not context for this one and never a question to put to the user**:

- **The user named a new playlist, or handed over a list of videos** — overwrite it silently,
  carrying no id over. Back it up first, so overwriting costs nothing to be wrong about:
  ```powershell
  if (Test-Path queue.txt) { New-Item -ItemType Directory -Force work | Out-Null
    Copy-Item queue.txt work\queue-prev.txt -Force }
  ```
  That backup is a within-run undo, not an artifact — nothing reads it and a `work/` cleanup may
  take it. The freshness rule in §2 does NOT apply here: there is nothing to compare against, only
  a previous run's decision to discard.
- **The user named the SAME playlist, or named nothing at all** — keep the file and apply §2.

**And it is never deleted at the end.** Promotion (§4) is the human trimming this file to the
survivors, and the report scripts take it as `--queue queue.txt`.

If the user handed over a PLAYLIST rather than a list of videos, expand it — the queue is a list of
videos, always — and record where it came from as the first line:

```powershell
$pl = @(.venv-asr\Scripts\yt-dlp.exe --flat-playlist --print "%(id)s" <playlist-url>)
```

```
# playlist: <название плейлиста> | <url плейлиста>
https://www.youtube.com/watch?v=...
```

Only the first such line is read; the pipeline skips it as a comment (`queueview.queue_playlist`).
The reports name it at the top and link the title.

**The id list comes from the QUEUE, never from a `work/` listing.** `<id>` is the 11-char YouTube
id inside each URL:

```powershell
$lines = @(Get-Content queue.txt | ForEach-Object { $_.Trim() } |
  Where-Object { $_ -and -not $_.StartsWith('#') })
$ids = @($lines | ForEach-Object {
  if ($_ -match '(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})') { $Matches[1] } })
if ($ids.Count -ne $lines.Count) {
  throw "queue: $($lines.Count) URLs, $($ids.Count) matched ids - unmatched line(s), see below" }
$lines | Where-Object { $_ -match '[?&]list=' }    # must print nothing — see below
$ids = @($ids | Select-Object -Unique)
```

All three guards are load-bearing:

- **A URL the regex misses** (e.g. a `/live/` link) is still PROCESSED by the pipeline —
  `video_id()` hash-fallbacks it into a `work/<sha1>` dir — but is invisible to every gate the
  route runs, so it silently never gets its sub-agent, its translation or its summary.
- **A line carrying `&list=` is the worse case, because the regex gate WAVES IT THROUGH** — the
  video id matches — and then `yt-dlp` follows the playlist: the download stage passes no
  `--no-playlist` and `-o` is a fixed `source.*` path (`stages/download.py`), so dozens of videos
  are fetched over one workdir. Verified 2026-07-24 on a real `watch?v=…&list=…` URL.
- **Duplicate spellings** of one video share a workdir and the CLI dedupes them (`cli.py`); without
  `-Unique` two parallel sub-agents race on the same draft file.

Both bad-URL cases: normalize the line in `queue.txt` to a bare `watch?v=<id>` form and restart
from the route's first step.

**Do NOT enumerate `work/` directories.** `work/` persists across batches and holds stale and
baseline workdirs; processing those wastes tokens and overwrites their artifacts (experiment
baselines are unrecoverable).

---

## 2. The `# playlist:` header is PROVENANCE, not a live link

It records the playlist as it was when the queue was written. **A header URL matching the playlist
the user just named proves NOTHING about what is in `queue.txt` now** — the playlist may have grown
since. Whenever the user points at a playlist, by URL or by "тот же плейлист", re-expand it into
`$pl` and diff, right after the `$ids` block:

```powershell
Compare-Object $pl $ids | ForEach-Object {
  "{0}: {1}" -f $(if ($_.SideIndicator -eq '<=') { 'playlist only' } else { 'queue only' }),
               $_.InputObject }
```

Hand the difference to the USER; never resolve it yourself:

- **playlist only** — either the playlist grew, or a human deliberately dropped that video
  (promotion trims the queue to the survivors). Those two are indistinguishable from here. Name the
  ids, ask, wait for an answer.
- **queue only** — normal (removed or private upstream). Say it once and carry on; never drop the
  line by yourself.

Concluding from the header that the queue is current drops every video added since, with **no FAIL
row, no flag and no missing artifact to detect it** — those videos were never in `$ids` to begin
with. Measured on the real queue 2026-07-24: `queue.txt` held 6 ids while the playlist held 23.

---

## 3. Never shorten, lengthen or interrupt the queue by yourself

**A model silently dropping a video is indistinguishable, downstream, from the pipeline losing
it — and unlike a lost video, nothing reports it.**

- **A video that looks wrong for this route is still an ordinary queue entry.** A music video, an
  instrumental cut, a live set, a talk with almost no speech, a two-minute clip, something that
  turns out not to be in English: process it like the rest. Do not stop to ask about one.
  Measured 2026-07-26 on `VHRhSDawKVA` ("… (Instrumental)"): whisper returned a single hallucinated
  "Thank you." over the music, the translator sub-agent flagged it `src=garbled` with exactly that
  reason, and the video muxed clean in 11 s with `needs_triage: false` — the pipeline's own report
  already said everything the question to the user would have asked, and it said it in an artifact
  instead of in chat.
- What goes IN the queue is the human's decision, and no route takes it for them. The reports
  describe what the videos are; nothing in this repo ranks them or drops one.
- **Never hand-write a completion artifact** (`summary.md`, a draft, a chunk) to clear a "pending"
  line. That line is the pass's only completion signal, and forging it is the silent failure in
  miniature.

---

## 4. Promotion — one route's queue entering another

No cleanup, ever. Nothing outside route B writes `translation.json`, so a scouted or cleaned
video is **untranslated, not half-translated**.

- `transcribe` **fast-skips** on the existing `sentences.json` — the large-v3 pass is not repeated,
  which is the whole economic point of a cheap pre-pass.
- `translate` has nothing yet, so route B's Step 2 runs normally.
- `summary.md` survives and is reused — the transcript it describes did not change.
- `download` **does re-run** for the dubbing routes: the full contract needs `source.mkv` and no
  audio-only route ever wrote one, so the audio bytes are re-fetched inside the merged container.
  ~5% extra traffic, accepted deliberately (DECISIONS 2026-07-20). **Do NOT try to save it by
  hand-assembling an MKV from `source.wav`.**
- Artifacts of the route being left behind (scout, clean) survive untouched. They are also
  not refreshed by a `--repair-asr` pass — that is what each route's mtime cache check is for.

Videos the user dropped keep their artifacts in `work/<id>/` — a few MB each, and they make a
re-run free. Deleting them is the user's call.

---

## 5. A DERIVED artifact is never evidence that work happened

Every route has the same shape: a sub-agent writes a **draft**, a `build_*.py` helper assembles the
**built** artifact from it. The helper guarantees the built file is well-formed — which is exactly
why a well-formed built file proves nothing about whether the agent ran.

| route | the agent's draft (the evidence) | derived, proves nothing |
|---|---|---|
| B | `translation.draft.json` | `translation.json` |
| C | `scout.draft.json` | `scout.json` |
| E | `clean/<from>-<to>.json` | `clean.json`, `clean.md` |

**A missing draft OUTRANKS a present built artifact. Always. Never the reverse.** Do not resolve
the contradiction by opening the built file and finding it consistent — it will always be
consistent. Re-run the agent. The built artifacts are also NOT in `invalidate_downstream`'s target
list, so nothing upstream clears them for you.

MEASURED 2026-07-21, and this is why the rule is written this hard: a scout run was set up for a
controlled re-measurement by deleting `summary.md`, `scout.draft.json` and `scout.started` while
leaving `scout.json` in place. S1 correctly reported `summary pending` ×6. The orchestrator noticed
the contradiction, investigated `build_scout.py` and the invalidation logic, concluded the
`scout.json` files were "консистентны и полны", skipped the summarizer step entirely, rebuilt the
report from the stale artifacts and **published a flawless-looking six-video report representing
zero work**. No "не отсканировано" row anywhere — the one signal a reader would have caught. The
diligence was real; the tie-break was the only thing missing.

---

## 6. Fan out through a `Workflow`, never by hand

**Hand fan-out is not a slower alternative, it is the failure mode the workflows exist to remove.**
Two independent measurements, from opposite ends:

Route C, three runs over one 6-video queue on 2026-07-21 — six `Agent` calls in six separate
messages every time:

```
run 1  prompt 21,507 chars   spawn gap 103 s   spawn total 514 s   wave 842 s
run 2  prompt 19,329 chars   spawn gap  86 s   spawn total 428 s   wave 647 s
run 3  prompt 23,689 chars   spawn gap 123 s   spawn total 614 s   wave 774 s
```

Run 3 settles it: the orchestrator explicitly reasoned *"spawning six sub-agents in a single
message"*, announced it out loud, and then emitted six messages anyway. **Read, understood,
acknowledged, not executed — so no wording fixes this.** The cadence tracks PROMPT SIZE at roughly
8.5 s per 1000 characters, because the orchestrator generates the whole prompt token by token once
per video; and the wave came to `spawn total + the last agent's own window`, so making the agents
faster bought nothing.

Route B, the 117-video batch of 2026-07-27:

```
translator prompts   87 spawns   403,364 chars   (median 4.5k, generated token by token)
inbound reports     123 msgs     270,832 chars   (mean 2.4k, worst 13,547 for a 9-line fix)
SendMessage out      40 calls     92,460 chars
idle_notification   133 blocks    15,794 chars
orchestrator context  60k -> 893k tokens, ~350k of it the traffic above
```

That run died at 89% of a 1M window. Step 4 never ran, and **84 of 117 summaries were silently
never written** — no FAIL row, no flag, nothing in chat. A sub-agent isolates its OWN context, but
its prompt and its final report stay in the orchestrator's history forever, so hand fan-out makes
the orchestrator pay TWICE per video (~9.6k tokens) instead of not at all.

`Workflow` removes both costs: `parallel()` is deterministic fan-out that does not depend on a
model emitting N blocks, and the script assembles the prompt instead of generating it.

**This needs a session that HAS the `Workflow` tool.** It is not available to sub-agents (verified
three ways, 2026-07-21), so a sub-agent — and presumably a headless or scheduled run — cannot
perform a fan-out step. **If you do not have the tool: stop and say so.** Do not substitute
anything; the only fallback available is the hand fan-out above, and a slow path that looks like
success is worse than an honest refusal.

Pass list arguments as **real JSON arrays, not a stringified list** (`args: {ids: [...]}`, never
`args: "{\"ids\": …}"`). The scripts parse a string anyway, so it costs nothing — do it right
regardless, because the guard is a net and not a contract. Always pass the RESUME-FILTERED list,
never the whole queue.

The whole queue goes in ONE call — the runtime caps concurrency (~16 agents) and queues the rest,
so per-wave barriers only add idle time. Route B spawns two agents per VIDEO, so a queue past
~450 videos would approach the 1000-agent-per-workflow backstop; split it there, not before. Route E
spawns per CHUNK — count chunks, not videos, and the ceiling arrives far sooner.

**The prompts live in `.claude/workflows/*.js`, not in the skills.** Edit the script — two copies
of one prompt drift, and re-typing a prompt per video is exactly the cost the workflow removes.

---

## 7. Verify from disk, not from the run's account

On routes B and C the fan-out sub-agents touch an empty marker file as their **first action**
(`translate.started`, `scout.started`). **Route E has none and needs none** — its
drafts are per-chunk already, so E3 verifies the chunk file itself and collects no per-video
timing, and everything below is about the other two. Two checks, the first of which goes missing
quietly:

```powershell
# 1. every spawned video got a marker — its absence means that agent never started
$spawned | Where-Object { -not (Test-Path "work\$_\<marker>") }     # must print nothing
# 2. the markers are SECONDS apart, not ~100 s — gaps near 100 s mean the fan-out did not happen
$spawned | Where-Object { Test-Path "work\$_\<marker>" } |
  ForEach-Object { (Get-Item "work\$_\<marker>").LastWriteTime } | Sort-Object
```

**Delete stale markers for the videos about to be respawned**, or a re-run pairs a fresh draft with
the previous attempt's timestamp and reports the gap between runs as work.

This check exists because on 2026-07-20 an orchestrator's own account of a wave was wrong in both
specifics it offered — it reported one call with six blocks, and a blocked `Write` the transcript
did not contain — while the completion times it reported were accurate. **An agent's report of what
it OBSERVED is worth more than its report of what it DID.** The same rule settles an ambiguous
status line: run the helper and let the artifact answer.

**A missing marker is not a failure to re-run.** The agent wrote the real artifacts and skipped its
first instruction; the work is good and only that video's timing is gone. The `build_*` helper
warns per video and the report marks the wave with a `+` to say it is a floor — but nothing re-runs
an agent for a timing, and doing so by hand would discard valid work to recover a number. Measured
2026-07-21: 1 of 6 agents did this.

The **wave start** (`$waveStart`, stamped before spawning anything and unrecoverable afterwards) is
NOT the per-video time: it is shared by every agent in the spawn, so for an agent that waited behind
the concurrency cap it measures the queue, not the work. The per-video number comes from that
agent's own marker. The two are different measurements and the reports keep them apart.
