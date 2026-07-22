---
name: overdub-sonnet-batch
description: "Run the overdub pipeline with Claude Sonnet as the translator (README route B, the primary translate route). Fixed order: transcribe the batch, translate and summarize each video with Sonnet sub-agents at the translate seam (writes translation.json via scripts/build_translation.py), resume the full pipeline, then produce a human-readable Russian triage report from scripts/run_report.py. Trigger when the user wants to dub a batch/video with Sonnet translation, 'прогони батч через Sonnet', 'переведи Sonnet-ом', 'route B', 'semi-auto translate', or asks how to run overdub with the cloud translator. NOT for the local Gemma route (that is fully turn-key: one --batch command). NOT for deciding WHAT to dub — that is the overdub-scout skill (route C)."
---

# overdub — Sonnet translation batch (route B)

The primary translate route (DECISIONS 2026-07-16 + 2026-07-18). Translation is just an
artifact (`work/<id>/translation.json`), so the pipeline stops cleanly at the translate seam
and resumes from it. Sonnet replaces only the LLM call; every downstream invariant stays
identical to the local Gemma route. **No Ollama needed.**

This skill is the orchestrator. Follow the four steps in order — do not improvise the order,
do not skip the helper, do not let a sub-agent hand-write `text_tts`.

## Preconditions (check, fail loud, do not auto-install)

- `.venv-asr` exists; `ffmpeg` on PATH; `yt-dlp` in `.venv-asr` (venv-first resolution, PATH
  fallback, missing → clear error). (`.venv-f5tts` + `.venv-demucs` are needed
  only from synthesize onward — step 3, not step 1/2.)
- A queue: `queue.txt` (one URL per line, `#` comments and blanks skipped) **or** a single URL.
- Run everything from the repo root `D:\code\overdub`. Never merge venvs.

## Scouting first? That is a different skill (README route C)

If the user has NOT decided what to dub — "что тут стоит дублировать", "прогони разведку",
"scout the queue" — that is the **`overdub-scout` skill**, not this one. It runs
`--scout` (download audio only → transcribe → stop), writes one summary per video and hands
back a recommend-only rundown. Load it instead of improvising a scout pass here.

A scouted queue re-enters THIS skill at **Step 1** with no cleanup: `transcribe` fast-skips on
the scout's `sentences.json` (the large-v3 pass is not repeated), `summary.md` is reused, and
`translate` has nothing yet so Step 2 runs normally. `download` DOES re-run — the full contract
needs `source.mkv` and scout never wrote one — re-fetching the audio bytes inside the merged
container: ~5% extra traffic, accepted (DECISIONS 2026-07-20). Do not try to save it by
hand-assembling an MKV from `source.wav`.

**The summarizer prompt in Step 2 below is shared with that skill.** Change it in one place and
change it in the other, or the two routes start producing different artifacts under one name.

## Step 1 — Transcribe the batch (no translation yet)

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt --only download transcribe
```

Single video: same command with the URL instead of `--batch queue.txt`.

Produces per video: `work/<id>/sentences.json` — a JSON list of `{id, text, start, end}`,
`id` contiguous from 0. That is the sub-agent's input.

**The id list comes from the QUEUE, never from a `work/` listing.** `<id>` is the 11-char
YouTube id inside each URL (step 1 also prints it per video: `work dir: work\<id>`):

```powershell
$lines = @(Get-Content queue.txt | ForEach-Object { $_.Trim() } |
  Where-Object { $_ -and -not $_.StartsWith('#') })
$ids = @($lines | ForEach-Object {
  if ($_ -match '(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})') { $Matches[1] } })
if ($ids.Count -ne $lines.Count) {
  throw "queue: $($lines.Count) URLs, $($ids.Count) matched ids - unmatched line(s), see below" }
$ids = @($ids | Select-Object -Unique)
```

Both guards are load-bearing. A URL the regex misses (e.g. a `/live/` link) is still
PROCESSED by the pipeline — `video_id()` hash-fallbacks it into a `work/<sha1>` dir — but
invisible to every gate below, which at step 3 means silent Gemma substitution for that
video: normalize the URL in queue.txt to a `watch?v=` form and restart from step 1.
Duplicate spellings of one video share a workdir and the CLI dedupes them (`cli.py`); without
`-Unique` two parallel sub-agents would race on the same draft file.

Do NOT enumerate `work/` directories — `work/` persists across batches and holds
stale/baseline workdirs; translating those wastes tokens and overwrites their
`translation.json` (experiment baselines are unrecoverable).

**Gate before step 2:** step 1 exited 0 and `work/<id>/sentences.json` exists for every id in
`$ids`. The batch continues past per-video failures (`FAIL` rows in the summary) — re-run the
same step-1 command until clean; completed stages fast-skip.

## Step 2 — Translate each video with a Sonnet sub-agent (+ summarize it)

**Resume filter first** — a prior interrupted step-2 run may have finished some videos
(helper-validated `translation.json` present); the mtime clause also catches drafts gone
stale via a re-transcribe:

```powershell
$todo = @($ids | Where-Object {
  $t = "work\$_\translation.json"
  -not (Test-Path $t) -or
    (Get-Item "work\$_\sentences.json").LastWriteTime -gt (Get-Item $t).LastWriteTime })
```

**One sub-agent per video in `$todo`, spawned in parallel in waves of ~3 videos** (two agents
each — the translator below and the summarizer further down — so ~6 concurrent; the cap is on
AGENTS, not videos). They are independent, but an uncapped 30-video batch = 60 concurrent Sonnet
agents — cap the wave, wait for it, spawn the next. Use the Agent tool
(`general-purpose`, **`model: "sonnet"` — set it explicitly**: sub-agents otherwise inherit
the session model, silently swapping the translator; every quality verdict for this route is
Sonnet-specific, DECISIONS 2026-07-18/19). Each sub-agent does ONE thing: read
`sentences.json`, translate, and write
`work/<id>/translation.draft.json` = a JSON list
`[{"id": <int>, "text_ru": "<string>", "src": "<ok|…>"}, ...]`
covering **every** id. Nothing else — no `text_tts`, no `src_en`, no timings.

The full contract, the translation rules (mirrored from `SYSTEM` in
`overdub/stages/translate.py`), and the draft/output schemas are in
[`references/translate-contract.md`](references/translate-contract.md). **Read it, then paste
its "Translation rules" + "Source anomalies" + "Draft schema" sections verbatim into every
sub-agent prompt** so each agent translates under exactly the same rules as the local route.

Sub-agent prompt skeleton (fill `<id>`):

> You are a dubbing translator for the overdub pipeline. Read `D:\code\overdub\work\<id>\sentences.json`
> (list of `{id, text, start, end}`). Translate every sentence's `text` from English into natural,
> spoken Russian for a single-narrator voice-over, **in id order**, keeping a rolling memory of the
> previous sentences and your Russian for them so terminology/names/pronouns stay consistent.
> Follow these rules exactly: <paste "Translation rules" from references/translate-contract.md>.
> Write `D:\code\overdub\work\<id>\translation.draft.json` as
> `[{"id": 0, "text_ru": "...", "src": "ok"}, ...]`
> with one entry for EVERY id in sentences.json, in order. Output only `text_ru` and `src` — do
> NOT add text_tts, do NOT respell numbers, do NOT touch timings. For every sentence also judge
> the ENGLISH source: if it is garbled, self-contradictory, truncated mid-thought, duplicative of
> its neighbour, or an enumeration item that repeats or contradicts what came before, translate it
> **AS IS** — never repair or smooth it — and set `src` to the matching kind plus a short English
> `src_note` saying what looks wrong (rule 8 / the vocabulary table in the contract). Otherwise
> set `src` to `"ok"`. Every record gets a `src`. For long videos (300+ sentences) write the file
> incrementally — append batches of ~50 entries per edit, never one giant single-shot write.
> Report the count written and the count of non-`ok` sentences.

Then, for each video, assemble + validate the real artifact with the helper (it fills
`src_en`/timings, derives `text_tts` via the pipeline's own normalizer, gates each line through
`_is_bad`, and enforces id-contiguity — the contract is NOT left to the agent):

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\build_translation.py work\<id>
```

The helper **exits non-zero and loud** on any missing id, extra id, or non-contiguous set —
that is the safety net. If it fails, fix the draft (or re-run that one sub-agent) and re-run the
helper; do not proceed with a partial `translation.json`. It also clamps the `src` vocabulary,
prints each anomaly with its EN source at the seam, and reports how many records carried a `src`
at all — all as `[warn]`s: a source-anomaly problem is never a helper failure (a hard exit would
leave `translation.json` unwritten and hand that video to the silent Gemma path).

**A second sub-agent per video writes the ~200-word Russian summary.** Same input file, same wave,
same `general-purpose` + **`model: "sonnet"` — set it explicitly** (a summary written by an
inherited session model is not the artifact this route was verified with, DECISIONS 2026-07-18/19).
It is INFORMATIONAL — it gates nothing, skips nothing, and no code reads a verdict out of it
(decided 2026-07-19). Its own resume filter, keyed on its own artifact:

```powershell
$sumTodo = @($ids | Where-Object {
  $s = "work\$_\summary.md"
  -not (Test-Path $s) -or
    (Get-Item "work\$_\sentences.json").LastWriteTime -gt (Get-Item $s).LastWriteTime })
```

**There is NO helper script for this one, deliberately.** The summary derives no machine-consumed
field, so there is no contract for a helper to own — unlike `text_tts` / `src_en` / id-contiguity,
which is exactly why `build_translation.py` is not optional. The digest and the queue page (`scout_report`) read
`summary.md` directly and sanitize it on read (heading markers stripped, runaway text truncated,
empty treated as absent), so a malformed summary can never break either surface.

Sub-agent prompt skeleton (fill `<id>`):

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

## Step 3 — Resume the full pipeline

**Gate before resuming (do not skip):** `work/<id>/translation.json` must exist for EVERY id
in `$ids`:

```powershell
$ids | Where-Object { -not (Test-Path "work\$_\translation.json") }   # must print nothing
```

A video missing it does NOT fail loudly at resume — its translate stage runs the LOCAL Gemma
path: with Ollama up it is silently translated by Gemma (a silent route substitution; the
batch still reports ok), without Ollama it fails with a misleading "Ollama not reachable —
start the daemon" (the real fix is step 2 for that video, not starting Ollama).

Also preflight the synthesis prerequisites now, before an overnight run — exact paths, not
"the folder exists" (defaults from `overdub/config.py`; check `overdub.toml` for `f5_*` /
`demucs_python` overrides). The ref clip is deliberately NOT in the repo (fetched at setup,
SETUP.md) — a missing file here fails the first synthesize hours into the night:

```powershell
@('.venv-f5tts\Scripts\python.exe', '.venv-demucs\Scripts\python.exe',
  'models\espeech-rlv2\espeech_tts_rlv2.pt', 'models\espeech-rlv2\vocab.txt',
  'models\refs\ref_espeech_demo.wav', 'models\refs\ref_espeech_demo.txt') |
  Where-Object { -not (Test-Path $_) }   # must print nothing
```

(`.venv-demucs` is needed for the default `dub_mix = "bed"`.)

Then the exact command from the local route (no `--only`). `TranslateStage.done()` is
`translation.json exists`, so download/transcribe/translate fast-skip; synthesize → verify →
assemble → separate → mux run as usual:

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub --batch queue.txt
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

Keep it short and honest: name what the digest flags, don't soften a `TRIAGE` into "всё хорошо".
A clean batch is a one-liner ("N видео, все чистые, X ч звука за Y мин"); a flagged batch leads
with the videos and segments that need a listen.

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

- **Never let a sub-agent write `text_tts`.** It MUST come from
  `normalize_for_tts` (the helper does this). Verify compares the ASR round-trip against
  `text_tts` through the same normalizer — a hand-spelled value silently breaks verification.
- **`src_en` must equal `sentences.json[i].text` verbatim** — the helper copies it, so never
  let the agent supply it. It is the resume/congruence key.
- **The helper is not optional.** It is the only thing validating the contract on the resume
  path (`TranslateStage.done()` only checks that the file exists — a malformed hand-written
  `translation.json` would sail straight into synthesize and produce garbage or crash there).
- **A missing `translation.json` at step 3 is a silent route substitution, not an error.**
  The resume runs the local Gemma path for that video (silently, if Ollama is up) — hence the
  mandatory every-id check before resuming, and hence ids from the queue, never from `work/`.
- If `sentences.json` is re-transcribed (e.g. `--force transcribe`), the drafts are stale —
  re-run step 2 for that video (the `$todo` mtime clause catches this automatically).
- **A missing `summary.md` is never a reason not to resume.** Do NOT add a `summary.md` clause to
  the step-3 gate: the summary is informational in v1 (decided 2026-07-19) — it gates
  nothing and skips nothing, and a gate here would be exactly the model-decides-what-to-drop
  behaviour that decision rejected. That gate exists to catch a silent Gemma substitution; widening
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
- **A scout pass never shortens the queue by itself.** S3 recommends; the human drops videos.
  Same reasoning as the two bullets above and the same rule the summary was built under
  (CHANGELOG 2026-07-20): a model silently deciding a video is not worth dubbing is
  indistinguishable, downstream, from the pipeline losing it. Also never hand-write a
  `summary.md` to clear a `summary pending` line — that line is the pass's only completion
  signal, and forging it is the silent failure in miniature.
- **Source anomalies gate nothing.** Do not add a `src` clause to the step-3 gate, do not let
  them delay a resume, and do not treat a `[warn]` from the helper as a failure — same reasoning
  as the summary bullet above (DECISIONS 2026-07-20, D2). They are advisory in v1 and do not move
  `needs_triage`; their action is `--repair-asr`, taken deliberately by a human. Promote them
  into `needs_triage` only after one batch has measured their fire rate — an unmeasured detector
  promoted early is how `entity_loss` came to mark 11 of 12 videos.
