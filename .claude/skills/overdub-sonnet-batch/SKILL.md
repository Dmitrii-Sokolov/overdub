---
name: overdub-sonnet-batch
description: "Run the overdub pipeline with Claude Sonnet as the translator (README route B, the primary translate route). Fixed order: transcribe the batch, translate and summarize each video with Sonnet sub-agents at the translate seam (writes translation.json via scripts/build_translation.py), resume the full pipeline, then produce a human-readable Russian triage report from scripts/run_report.py. Trigger when the user wants to dub a batch/video with Sonnet translation, 'прогони батч через Sonnet', 'переведи Sonnet-ом', 'route B', 'semi-auto translate', or asks how to run overdub with the cloud translator. NOT for deciding WHAT to dub — that is the overdub-scout skill (route C)."
---

# overdub — Sonnet translation batch (route B)

The primary translate route (DECISIONS 2026-07-16 + 2026-07-18). Translation is just an
artifact (`work/<id>/translation.json`), so the pipeline stops cleanly at the translate seam
and resumes from it. Sonnet replaces only the LLM call; every downstream invariant stays
identical either side of the seam.

This skill is the orchestrator. Follow the four steps in order — do not improvise the order,
do not skip the helper, do not let a sub-agent hand-write `text_tts`.

## Preconditions (check, fail loud, do not auto-install)

- `.venv-asr` exists; `ffmpeg` on PATH; `yt-dlp` in `.venv-asr` (venv-first resolution, PATH
  fallback, missing → clear error). Silero (the engine since 2026-07-25) runs from `.venv-asr`
  itself — no separate TTS venv. `.venv-demucs` is needed from synthesize onward (step 3, not
  step 1/2) for the default `dub_mix = "bed"`.
- A queue: `queue.txt` (one URL per line, `#` comments and blanks skipped) **or** a single URL.
  A PLAYLIST url is neither. Everything about resolving it is
  [`docs/queue-contract.md`](../../../docs/queue-contract.md) §1-2, a MANDATORY READ before step 1.
- Run everything from the repo root `D:\code\overdub`. Never merge venvs.

## Scouting first? That is a different skill (README route C)

If the user has NOT decided what to dub — "что тут стоит дублировать", "прогони разведку",
"scout the queue" — that is the **`overdub-scout` skill**, not this one. It runs
`--scout` (download audio only → transcribe → stop), writes one summary per video and hands
back a recommend-only rundown. Load it instead of improvising a scout pass here.

A scouted queue re-enters THIS skill at **Step 1** with no cleanup; the mechanics are
[`docs/queue-contract.md`](../../../docs/queue-contract.md) §4.

**The summarizer prompt in Step 2 below is shared with that skill.** Change it in one place and
change it in the other, or the two routes start producing different artifacts under one name.

## Step 1 — Resolve the queue, then transcribe the batch (no translation yet)

**Read [`docs/queue-contract.md`](../../../docs/queue-contract.md) now, before anything else.**
Sections 1-3 are this step: who owns `queue.txt`, the `$ids` block and its three load-bearing
guards, the `# playlist:` freshness diff, and the rule that a queue is never shortened, lengthened
or interrupted by a model. Run §1 verbatim, and apply §2 as §1 directs — the trigger lives there,
not here.

**Resolve the queue BEFORE the command, not after** (moved above it 2026-07-24). These checks
used to sit under the run, which made them audits of a download that had already happened: a
malformed line was caught only once its bytes were spent.

Route-B specifics on top of the contract:

- Step 1 prints the workdir per video (`work dir: work\<id>`).
- A URL the `$ids` regex misses is invisible to every gate below, which **at step 3 means that
  video reaches the resume with no translation of its own** — it cannot be dubbed at all.
- Without `-Unique`, two parallel sub-agents race on the same draft file.
- Translating a stale `work/` dir also OVERWRITES its `translation.json`, and experiment baselines
  are unrecoverable — one more reason ids come from the queue.

Then run — **stamped**. Step 4 has to divide the queue's audio by the time the machine actually
spent, and no artifact records that (see step 4, "Capacity"). The stamp is three lines, costs
nothing, and reads the same whether the command runs in the foreground or the background:

```powershell
$t0 = Get-Date
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --only download transcribe
"STEP_ELAPSED_S=$([int]((Get-Date) - $t0).TotalSeconds)"
```

Single video: same command with the URL instead of `--batch queue.txt`.

Produces per video: `work/<id>/sentences.json` — a JSON list of `{id, text, start, end}`,
`id` contiguous from 0. That is the sub-agent's input.

**Gate before step 2:** step 1 exited 0 and `work/<id>/sentences.json` exists for every id in
`$ids`. The batch continues past per-video failures (`FAIL` rows in the summary) — re-run the
same step-1 command until clean; completed stages fast-skip.

### Step 1b — Repair the transcript BEFORE translating it (added 2026-07-25)

```powershell
$t0 = Get-Date
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --repair-asr auto
"STEP_ELAPSED_S=$([int]((Get-Date) - $t0).TotalSeconds)"
```

**Cheap, and this is the only position where it is cheap.** `auto` seeds on `dup_adjacent` +
`rate_implausible` read off `sentences.json` alone, loads whisper lazily (a clean sweep never
loads it at all), and is idempotent. Run here and the repaired text flows into translate,
synthesize and the subtitles. Run it after the batch instead — which is what the step-4 narrative
suggests for a single video — and every id renumbers, `invalidate_downstream` deletes
`translation.json`/`summary.md`, and that video pays a full re-translate + re-synthesize.

**What it is fixing.** Sentences whose slot is impossibly short for their text, because the SOURCE
timing is invented or the source itself is duplicated — `iWRmtPdFbGw#10` had a 0.46 s slot for
5.2 s of speech, `8zJlKmgMT44#130-133` were four ASR duplicates of one sentence sharing a 5.74 s
slot. That is a whisper defect, not long Russian, which is why repairing it BEFORE translate is
the cheap position: the seeds this sweep keys on (`rate_implausible` on the EN side) are exactly
what such units carry. A unit compressed past ×2 is degraded and past ×4 unintelligible, so the
sweep is worth running even though it usually does nothing.

*(The counts once quoted here — "17 units at ×1.8..×12.5, 10 of them seeded" — were recomputed
2026-07-25 and were wrong: 17 mixed a SENTENCE-row count with units, and ×12.5 was one sentence's
pre-repair figure, since repaired to 2.04. Over all of `work/` the real population is 7 units of
3575, worst 2.63 — and all of it measured at the old grouping. PLAN "Numbers to re-measure"
carries the correction; do not restate a population number here until a Silero batch exists.)*

Skip it only for a queue you have already repaired (`sentences.json` newer than the repair stamp).
A video whose digest `- asr:` line says `alignment collapse suspected` is never a skip.

## Step 2 — Translate each video with a Sonnet sub-agent (+ summarize it)

**Resume filters first** — a prior interrupted step-2 run may have finished some videos, and the
mtime clauses also catch artifacts gone stale via a re-transcribe or a `--repair-asr` pass. Two
filters, each keyed on its OWN artifact, because the two agents fail independently:

```powershell
$todo = @($ids | Where-Object {
  $t = "work\$_\translation.json"
  -not (Test-Path $t) -or
    (Get-Item "work\$_\sentences.json").LastWriteTime -gt (Get-Item $t).LastWriteTime })
$sumTodo = @($ids | Where-Object {
  $s = "work\$_\summary.md"
  -not (Test-Path $s) -or
    (Get-Item "work\$_\sentences.json").LastWriteTime -gt (Get-Item $s).LastWriteTime })
```

**A missing `translation.draft.json` OUTRANKS a present `translation.json`. Always** — the
derived-artifact rule, [`docs/queue-contract.md`](../../../docs/queue-contract.md) §5. Add the
video to `$todo` and re-translate it; do not reason your way out of the contradiction by opening
the derived file.

**Delete stale markers for the videos about to be respawned** (contract §7), or the fan-out check
below pairs a fresh run with the previous attempt's timestamps:

```powershell
@($todo + $sumTodo) | Select-Object -Unique |
  ForEach-Object { Remove-Item "work\$_\translate.started" -ErrorAction SilentlyContinue }
```

### DO NOT spawn the sub-agents yourself. Run the workflow.

```
Workflow: {name: "translate-batch", args: {ids: [...$todo], sumIds: [...$sumTodo], root: "D:\\code\\overdub"}}
```

Why never by hand, why the arrays must be real JSON, why the whole queue goes in ONE call, and what
to do when the `Workflow` tool is absent (stop and say so): **[`docs/queue-contract.md`](../../../docs/queue-contract.md)
§6**, which carries the 117-video measurement this step was rebuilt from. The workflow refuses an
empty fan-out rather than reporting success having translated nothing.

**First run, 2026-07-28 (5 videos):** markers 3.5 s apart, a 4694-line / 782-sentence transcript
returned 782/782, `src` on 100% of records in all four drafts, zero `_is_bad` flags, 5/5 muxed —
and step 2 cost the orchestrator 1428 chars against 62% of a window for the hand fan-out it
replaced. Nothing failed, so the `failed` / `incomplete` / second-wave branches below are still
unexercised code: read their output, do not assume it.

**The prompts live in `.claude/workflows/translate-batch.js`, not here.** Edit the script. The
translation contract is no longer pasted into anything either: the sub-agent reads
[`references/translate-contract.md`](references/translate-contract.md) off disk itself (9.1k chars
per spawn) under a MANDATORY-READ rule, and an agent that cannot read it returns `CONTRACT-MISSING`
and stops instead of translating to its own taste.

It returns `{done, failed, incomplete, unclear, total}`, all by id. `failed` is a dropped agent or
a `CONTRACT-MISSING`; `incomplete` is an agent that could not cover every id; `unclear` is a status
line that did not parse — **not a failure**, and the disk decides.

### Verify from disk, not from the run's account

Contract §7 — the rule and what a missing marker does and does not mean. The marker here is
`translate.started`:

```powershell
# 1. every spawned video got a marker — its absence means that agent never started
@($todo + $sumTodo) | Select-Object -Unique |
  Where-Object { -not (Test-Path "work\$_\translate.started") }     # must print nothing
# 2. the markers are SECONDS apart, not ~100 s — gaps near 100 s mean the fan-out did not happen
@($todo + $sumTodo) | Select-Object -Unique | Where-Object { Test-Path "work\$_\translate.started" } |
  ForEach-Object { (Get-Item "work\$_\translate.started").LastWriteTime } | Sort-Object |
  Select-Object -First 5
```

The same rule settles `unclear` — run the helper and let the artifact answer.

### Assemble and validate the real artifact

For every id in `$todo` (including `unclear` ones), run the helper — it fills `src_en`/timings,
derives `text_tts` via the pipeline's own normalizer, gates each line through `_is_bad`, and
enforces id-contiguity, so the contract is never left to the agent:

```powershell
$todo | ForEach-Object { .venv-asr\Scripts\python.exe -X utf8 scripts\build_translation.py "work\$_" }
```

The helper **exits non-zero and loud** on any missing id, extra id, or non-contiguous set — that is
the safety net, and it is why a truncated transcript read costs a respawn rather than half a dub.
It also clamps the `src` vocabulary, prints each anomaly with its EN source at the seam, and
reports how many records carried a `src` at all — all as `[warn]`s: a source-anomaly problem is
never a helper failure (a hard exit would leave `translation.json` unwritten and send that video
into the resume with nothing to dub from).

**Second wave for whatever did not land.** Re-run the workflow with just those ids — the failure is
per video, so the re-run is too:

```powershell
$again = @($ids | Where-Object { -not (Test-Path "work\$_\translation.json") -or
  (Get-Item "work\$_\sentences.json").LastWriteTime -gt (Get-Item "work\$_\translation.json").LastWriteTime })
```

**A second wave is for a DROPPED or `CONTRACT-MISSING` agent, not for an `INCOMPLETE` one.** An
`INCOMPLETE` video goes straight to the chunked path below — see the trigger there.

### When one agent cannot cover the video (added 2026-08-05)

**ONE `INCOMPLETE` on a video is the trigger. Do not re-run the per-video translator for it.**
Measured on `7xTGNNLPyMI` (Karpathy, 3.5 h, 2259 sentences): 1200/2258, then 1500/2259 on the
retry — an agent reading a 411 KB transcript and then emitting ~250 KB of JSON, stopping about two
thirds through. That retry cost 29 minutes for information the first attempt had already given
(2026-08-05); the rule used to ask for two rounds and it was wrong.

**Why it stops is NOT established, and chunking does not depend on knowing.** Context window and a
turn/tool-use budget both predict this shape, and INBOX raised the second on 2026-08-04 with the
sharper evidence for it: on that batch the SECOND wave wrote its marker and then produced ZERO new
records, leaving drafts byte-identical to wave 1. The 2026-08-05 retry did make progress
(1200 → 1500), so the two runs do not even agree on the shape. Chunking cuts transcript size, output
volume and turn count at once, which is why it works either way — but do not repeat the window
explanation as fact, and do not design anything narrower on it without confirming the mechanism.

**Above ~2000 sentences, skip the per-video attempt entirely and start here.** Corpus of 227
route-B drafts, counted 2026-08-05: exactly one partial (`477qF6QNSvc`, 1550/2514). At or below
2004 sentences — 223 drafts, zero partial. Above it, four videos, two of which failed:

| sentences | video | outcome on the per-video translator |
|---|---|---|
| 2259 | `7xTGNNLPyMI` | INCOMPLETE twice (1200, then 1500) |
| 2379 | `cc5l66FwpQ4` | complete |
| 2514 | `477qF6QNSvc` | INCOMPLETE (1550) |
| 2829 | `kfM-yu0iQBk` | returned `OK` one id SHORT (2828/2829); completed after a re-run |

**So this is not a failure threshold and must not be quoted as one** — the outcomes do not order by
size: 2379 sailed through while both 2259 and 2514 stalled. 2000 is where the odds stop paying for
the attempt, resting on the clean lower half (0 of 223), not on any claim that a bigger video will
fail. INBOX said "do NOT site a size threshold on this sample" on 2026-08-04 and that warning is
about a FAILURE threshold; this is not one, and the disclaimer above is the whole reason it may be
written down at all.

Note what the 2829 row actually shows, because it is the more useful lesson: **an agent's own
completeness status is uncorrelated with completeness.** It said `OK` and was short, and
`build_translation.py`'s hard exit was the only thing between that and a dub missing a sentence.
That is the guardrail earning its keep, and the argument against ever relaxing it.

Two things make the rate above 2004 a FLOOR, both worth knowing before the number is trusted
further: a video that failed once and passed on a retry is indistinguishable from a clean success
afterwards (the draft is overwritten), and **sentence count is a proxy for what actually binds,
which is output VOLUME in characters** — PLAN carries the re-measurement.

Switch that video to one agent per CHUNK. The seam does not move: each agent writes the ordinary
draft record shape into `work/<id>/translate/<from>-<to>.json`, and `--join` concatenates them into
`translation.draft.json` before building `translation.json` exactly as before.

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\build_translation.py "work\<id>" --plan
```

Feed that cut to the workflow, adding `prev` (the previous chunk's file name) to every job but the
first — that is what carries terminology across a boundary:

```
Workflow: {name: "translate-chunks", args: {root: "D:\\code\\overdub", jobs: [
  {video: "<id>", from: 0, to: 371},
  {video: "<id>", from: 372, to: 810, prev: "0-371.json"}, ...]}}
```

Chunks of one video are CHAINED (chunk N reads N-1's tail for terminology); different videos run in
parallel. Then join and build in one command — same helper, same contract, same `[warn]`s:

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\build_translation.py "work\<id>" --join
```

Three things that bite:

- **`--chunk N` must match between `--plan` and `--join`**, or the join looks for file names nobody
  wrote. Pass it to neither and both use the same default.
- **A `--repair-asr` pass renumbers every id, so the cut moves and the chunk files on disk go
  stale.** `invalidate_downstream` deletes them for you; the join's missing-file message names this
  as one of its two causes.
- **A present `translation.draft.json` is not evidence on this path** — it is derived from the chunk
  files ([`docs/queue-contract.md`](../../../docs/queue-contract.md) §5, which spells out that route
  B's draft changes sides depending on which translator ran).

This is the escape hatch, not the default: the per-video agent sees the whole video at once, which
is this route's stated advantage, and chunking trades some of it for coverage.

### The summary half

Same wave, same workflow, own resume filter, own artifact. It is INFORMATIONAL — it gates nothing,
skips nothing, and no code reads a verdict out of it (decided 2026-07-19). **There is NO helper
script for it, deliberately**: it derives no machine-consumed field, so there is no contract for a
helper to own — unlike `text_tts` / `src_en` / id-contiguity, which is exactly why
`build_translation.py` is not optional. The digest and the queue page (`scout_report`) read
`summary.md` directly and sanitize it on read (heading markers stripped, runaway text truncated,
empty treated as absent), so a malformed summary can never break either surface.

The prose half of that prompt is **identical to the summarizer in
`.claude/workflows/scout-summarize.js`** (route C / S2) — if you change one, change the other, or
the two routes produce different artifacts under one name.

## Step 3 — Resume the full pipeline

**Gate before resuming (do not skip):** `work/<id>/translation.json` must exist for EVERY id
in `$ids`:

```powershell
$ids | Where-Object { -not (Test-Path "work\$_\translation.json") }   # must print nothing
```

A video missing it has nothing for the resume to dub from — the translate seam is the only
producer of `translation.json`, so the fix is always step 2 for that video.

Also preflight the synthesis prerequisites now, before an overnight run — the point is that a
missing piece fails the first synthesize HOURS into the night, so check it while a human is
awake. Defaults come from `overdub/config.py`; read `overdub.toml` for `tts_engine`, `tts_voice`,
`silero_model` and `demucs_python` overrides before assuming which branch applies.

**Silero (the default engine).** There is no asset to fetch — the release is pulled through
`torch.hub` on first use and cached under `~/.cache/torch/hub`. That is exactly the failure worth
pre-empting: a cold cache plus no network fails at the first unit, at night. Warm it and prove
the voice loads in one shot:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -c "from pathlib import Path; from overdub.config import Config; from overdub.tts import build_engine, voice_rate; cfg=Config.load(Path('overdub.toml')); e=build_engine(cfg); print('tts ok:', cfg.tts_engine, cfg.tts_voice, cfg.silero_model, '| rate', voice_rate(cfg))"
.venv-demucs\Scripts\python.exe -c "import demucs; print('demucs ok')"    # for dub_mix = 'bed'
```

Go through `build_engine` rather than calling `torch.hub` by hand: it is the path synthesize
actually takes, so it loads whatever `overdub.toml` selects (including `trust_repo=True`, without
which hub blocks on an interactive prompt) and it fails on the same error the night run would.

Read the printed line, do not just check that it printed. `rate` must NOT be `None`: the slot
arithmetic is keyed on `tts_voice` and disables itself on a voice it has not measured, so a typo
there costs the fit silently rather than loudly. The shipped voice is `eugene` — the only one
whose rate is well measured; aidar, baya, kseniya and xenia carry one-video figures.

Then the full pipeline command (no `--only`). `TranslateStage.done()` is
`translation.json exists`, so download/transcribe/translate fast-skip; synthesize → verify →
assemble → separate → mux run as usual:

```powershell
$t0 = Get-Date
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt
"STEP_ELAPSED_S=$([int]((Get-Date) - $t0).TotalSeconds)"
```

- Final MKVs land in `out/`; per-video artifacts in `work/<id>/`.
- Interrupt/resume: re-run the same command — completed stages fast-skip. Graceful stop:
  create `work/STOP`. Exit codes: 0 ok / 1 any fail / 2 usage / 3 stop-halt.
- Morning triage: `work/<id>/report.json` — any `*_flag`, or `speed_factor > 1.8`. Translate
  flags also surface as `status:"failed"` lines in `translation.json`; `pronounce_audit.json`
  (the helper writes it, parity with the local route) lists what the pipeline invented for
  out-of-dict Latin names — the one silent-loss class verify cannot catch.

## Step 4 — Human-readable report

Once the resume (step 3) finishes, render the per-run digest, then write the user a concise
Russian triage summary from it. The script produces the DATA; **your job is the human narrative
in Russian.**

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\run_report.py --queue queue.txt
```

Single video: pass `work\<id>` instead of `--queue queue.txt`. The script reads each
`work/<id>/run.json` (the pipeline wrote it on resume; it rebuilds any that is missing), prints a
per-video block (header + timings + flags + offenders), a batch table, and a totals line. It is
read-only and never crashes on a missing run.json — a dir with none is a skipped row.

Then summarize for the user in Russian, grounded ONLY in that output (do not invent numbers):

- **Per video:** clean vs needs-a-look (the `[TRIAGE]`/`[clean]` marker); RTF + wall time; the
  flag headline (translate / verify / completeness counts); and any speed offenders ≥ 1.8×
  (`n>1.8`, and the offender ids/reasons the block lists).
- **The summary, when present:** the digest prints it as a `- summary (N words):` section per video
  and the queue page (scout_report) shows it on the card above the audio units. Use it as the
  *content* half of your narrative
  (what the video is about, is it worth the user's time) alongside the *quality* half the flags
  give you — quote or paraphrase it instead of re-deriving one, say nothing about a video that has
  none, and never let it soften a `TRIAGE` marker.
- **Source anomalies, when present:** name the video and the ids, quote the notes, and say the
  next action out loud — `--repair-asr <ids>` on that single video, then re-run step 2 for it
  (`explicit_seeds` range-checks the ids; a repair renumbers every later id and
  `invalidate_downstream` deletes `translation.draft.json`, `translation.json` and `summary.md`,
  so explicit-id repair is NOT idempotent — re-derive ids before a second pass). Never fold them
  into the quality half of your narrative: they are a claim about the TRANSCRIPT, not about the
  dub. If the `src` column reads `-`, say "не проверялось", never "чисто".
- **Batch totals:** total wall across videos, aggregate throughput, and WHICH video_ids need
  eyes (the `need triage` list) — so the user knows what to open first, not just that something
  is off.
- **Capacity:** the audio-per-hour-of-machine-time ratio, computed from the step stamps — see
  the subsection below. It is the only figure in the report that answers "how much fits in a
  night", and the digest's `throughput` is not it.

Keep it short and honest: name what the digest flags, don't soften a `TRIAGE` into "всё хорошо".
A clean batch is a one-liner ("N видео, все чистые, X ч звука за Y мин"); a flagged batch leads
with the videos and segments that need a listen.

### Capacity — how much video fits in a night (added 2026-08-02)

**The digest's `throughput` cannot answer that and must never be quoted as if it could.** It is
Σ(`video_sec`) / Σ(`total_wall_s`), and `total_wall_s` is the SUM OF THE SEVEN STAGE TIMERS —
verified by adding up `vWidan8ggGo`'s seven stages, which reproduce its `total_wall_s` exactly.
Everything between the timers is invisible to it: process starts, the gaps between invocations,
and on this route the whole Sonnet translate wave, which is not a stage at all — `translate`
appears in the `stages` map of NO `run.json` on disk (checked over all 193 of them, 2026-08-02;
re-check the property, not the count, if you need it again).

So compute the real ratio from the stamps. Three `STEP_ELAPSED_S=` lines (steps 1, 1b, 3) plus
step 2's workflow `duration_ms ÷ 1000`. The queue's audio comes off the run reports:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -c "import json,pathlib,sys; print('audio_s=%.0f' % sum(json.loads((pathlib.Path('work')/i/'run.json').read_text(encoding='utf-8'))['timings']['video_sec'] for i in sys.argv[1:]))" @ids
```

Report it as `аудио X ч / машина Y ч = ×Z`, then turn it into the number the user actually plans
with: **за 8-часовую ночь пройдёт ~8×Z часов исходного видео.**

**List the four addends you summed.** A total with no addends is indistinguishable from a
remembered one, and this is the one figure in the report that no artifact can contradict.

Say once what the ratio excludes: the human's pauses between steps and the orchestrator's own
thinking time between commands. It is therefore the MACHINE ceiling and reads slightly high for
an attended session. When the steps ran back to back, quote the session span (first start → last
end) beside it — the two agreeing within a few percent is the evidence that nothing idled.

Measured 2026-08-02 on a 2-video queue, 3.22 h of audio: digest `throughput ×4.13`, actual
machine time 4532 s = **×2.56** (session span 4618 s = ×2.51). Split: step 1 1148 s · step 1b
41 s · **step 2 1676 s** · step 3 1667 s — the translate wave was the largest single line item at
37% of the batch and appears in no existing number. Planning a night on ×4.13 overbooks it by
~60%.

**When the batch has flagged units, also offer the clickable page** — one HTML with an inline
audio player per flagged unit (expected vs whisper-heard, click to listen), so the user can
actually LISTEN instead of reading ids:

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\scout_report.py --queue queue.txt
```

Writes `work/scout-report.html` (audio base64-embedded → portable, every player works; the
videos needing a listen sit in the nav block at the top, in queue order — the page never
re-sorts the queue). Mention the path in your summary. Skip it for a fully clean batch
(nothing to listen to).

## Guardrails (the failure modes this skill exists to prevent)

The queue-wide ones live in [`docs/queue-contract.md`](../../../docs/queue-contract.md) and bind
here unchanged: never shorten the queue or forge a completion artifact (§3), a stale
`# playlist:` header is not freshness (§2), a derived artifact is not evidence (§5), never
hand-spawn a fan-out (§6). Route-B's own:

- **Never let a sub-agent write `text_tts`.** It MUST come from
  `normalize_for_tts` (the helper does this). Verify compares the ASR round-trip against
  `text_tts` through the same normalizer — a hand-spelled value silently breaks verification.
- **`src_en` must equal `sentences.json[i].text` verbatim** — the helper copies it, so never
  let the agent supply it. It is the resume/congruence key.
- **The helper is not optional.** It is the only thing validating the contract on the resume
  path (`TranslateStage.done()` only checks that the file exists — a malformed hand-written
  `translation.json` would sail straight into synthesize and produce garbage or crash there).
- **A truncated transcript read is silent on the agent's side.** `Read` returns 2000 lines by
  default and 28 of 152 `sentences.json` files exceed that (largest 5930 lines / 988 sentences),
  so a naive read hands the translator the first third of the video with no warning. Only
  `build_translation.py`'s missing-id exit catches it, one full respawn later. The workflow's
  prompt requires reading on to the last id; keep that requirement if you edit it.
- **A missing `translation.json` at step 3 means that video cannot be dubbed at all.** The seam is
  its only producer — hence the mandatory every-id check before resuming, and hence ids from the
  queue, never from `work/`.
- If `sentences.json` is re-transcribed (e.g. `--force transcribe`), the drafts are stale —
  re-run step 2 for that video (the `$todo` mtime clause catches this automatically).
- **A missing `summary.md` is never a reason not to resume.** Do NOT add a `summary.md` clause to
  the step-3 gate: the summary is informational in v1 (decided 2026-07-19) — it gates
  nothing and skips nothing, and a gate here would be exactly the model-decides-what-to-drop
  behaviour that decision rejected. That gate exists to catch a missing translation; widening
  it would let a failed summarizer block a dub that has everything it needs. Both report surfaces
  treat an absent summary as normal and render nothing.
- **Never let a sub-agent silently repair a garbled source.** DECISIONS 2026-07-19: on
  `RyvXxApfHkk` id11 Sonnet turned ASR garbage into plausible Russian on the first pass, hiding
  it from everything downstream — `rate_implausible` and `dup_adjacent` are blind to a semantic
  garble that carries no timing anomaly and no repeated span, so the reading pass is the only
  detector that sees it. A good translator is a defect BLEACHER by default; the better it is,
  the more reliably it hides source damage. It only helps when asked to REPORT rather than
  smooth — a prompt requirement, not a property of the model. This is compensation for an
  observability regression this route itself introduced, not a bonus detector. `src` is required
  on every record precisely so a skipped anomaly pass shows up as `not scanned` instead of as a
  clean-looking empty report.
- **Source anomalies gate nothing.** Do not add a `src` clause to the step-3 gate, do not let
  them delay a resume, and do not treat a `[warn]` from the helper as a failure — same reasoning
  as the summary bullet above (DECISIONS 2026-07-20, D2). They are advisory in v1 and do not move
  `needs_triage`; their action is `--repair-asr`, taken deliberately by a human. Promote them
  into `needs_triage` only after one batch has measured their fire rate — an unmeasured detector
  promoted early is how `entity_loss` came to mark 11 of 12 videos.
