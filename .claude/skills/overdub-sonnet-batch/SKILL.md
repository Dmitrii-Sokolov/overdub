---
name: overdub-sonnet-batch
description: "Run the overdub pipeline with Claude Sonnet as the translator (README route B, the primary translate route). Fixed 3-step order: transcribe the batch, translate each video with a Sonnet sub-agent at the translate seam (writes translation.json via scripts/build_translation.py), then resume the full pipeline. Trigger when the user wants to dub a batch/video with Sonnet translation, 'прогони батч через Sonnet', 'переведи Sonnet-ом', 'route B', 'semi-auto translate', or asks how to run overdub with the cloud translator. NOT for the local Gemma route (that is fully turn-key: one --batch command)."
---

# overdub — Sonnet translation batch (route B)

The primary translate route (DECISIONS 2026-07-16 + 2026-07-18). Translation is just an
artifact (`work/<id>/translation.json`), so the pipeline stops cleanly at the translate seam
and resumes from it. Sonnet replaces only the LLM call; every downstream invariant stays
identical to the local Gemma route. **No Ollama needed.**

This skill is the orchestrator. Follow the three steps in order — do not improvise the order,
do not skip the helper, do not let a sub-agent hand-write `text_tts`.

## Preconditions (check, fail loud, do not auto-install)

- `.venv-asr` exists; `ffmpeg` + `yt-dlp` on PATH. (`.venv-f5tts` + `.venv-demucs` are needed
  only from synthesize onward — step 3, not step 1/2.)
- A queue: `queue.txt` (one URL per line, `#` comments and blanks skipped) **or** a single URL.
- Run everything from the repo root `D:\code\overdub`. Never merge venvs.

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
$ids = Get-Content queue.txt | ForEach-Object {
  if ($_ -match '(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})') { $Matches[1] } }
```

Do NOT enumerate `work/` directories — `work/` persists across batches and holds
stale/baseline workdirs; translating those wastes tokens and overwrites their
`translation.json` (experiment baselines are unrecoverable).

**Gate before step 2:** step 1 exited 0 and `work/<id>/sentences.json` exists for every id in
`$ids`. The batch continues past per-video failures (`FAIL` rows in the summary) — re-run the
same step-1 command until clean; completed stages fast-skip.

## Step 2 — Translate each video with a Sonnet sub-agent

**One sub-agent per video, spawned in parallel** (they are independent). Use the Agent tool
(`general-purpose`, **`model: "sonnet"` — set it explicitly**: sub-agents otherwise inherit
the session model, silently swapping the translator; every quality verdict for this route is
Sonnet-specific, DECISIONS 2026-07-18/19). Each sub-agent does ONE thing: read
`sentences.json`, translate, and write
`work/<id>/translation.draft.json` = a JSON list `[{"id": <int>, "text_ru": "<string>"}, ...]`
covering **every** id. Nothing else — no `text_tts`, no `src_en`, no timings.

The full contract, the translation rules (mirrored from `SYSTEM` in
`overdub/stages/translate.py`), and the draft/output schemas are in
[`references/translate-contract.md`](references/translate-contract.md). **Read it, then paste
its "Translation rules" + "Draft schema" sections verbatim into every sub-agent prompt** so
each agent translates under exactly the same rules as the local route.

Sub-agent prompt skeleton (fill `<id>`):

> You are a dubbing translator for the overdub pipeline. Read `D:\code\overdub\work\<id>\sentences.json`
> (list of `{id, text, start, end}`). Translate every sentence's `text` from English into natural,
> spoken Russian for a single-narrator voice-over, **in id order**, keeping a rolling memory of the
> previous sentences and your Russian for them so terminology/names/pronouns stay consistent.
> Follow these rules exactly: <paste "Translation rules" from references/translate-contract.md>.
> Write `D:\code\overdub\work\<id>\translation.draft.json` as `[{"id": 0, "text_ru": "..."}, ...]`
> with one entry for EVERY id in sentences.json, in order. Output only text_ru — do NOT add
> text_tts, do NOT respell numbers, do NOT touch timings. For long videos (300+ sentences)
> write the file incrementally — append batches of ~50 entries per edit, never one giant
> single-shot write. Report the count written.

Then, for each video, assemble + validate the real artifact with the helper (it fills
`src_en`/timings, derives `text_tts` via the pipeline's own normalizer, gates each line through
`_is_bad`, and enforces id-contiguity — the contract is NOT left to the agent):

```powershell
.venv-asr\Scripts\python.exe -X utf8 scripts\build_translation.py work\<id>
```

The helper **exits non-zero and loud** on any missing id, extra id, or non-contiguous set —
that is the safety net. If it fails, fix the draft (or re-run that one sub-agent) and re-run the
helper; do not proceed with a partial `translation.json`.

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

Also preflight the synthesis prerequisites now, before an overnight run: `.venv-f5tts` and
the F5 assets under `models/` exist; `.venv-demucs` exists (needed for the default
`dub_mix = "bed"`).

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
  re-run step 2 for that video.
