# DECISIONS

One line per decision; the dated entries live in `docs/decisions-log.md` — cite as
"DECISIONS YYYY-MM-DD" and resolve the date there. Written at triage only: an appended decision
is two edits, the line here and the entry in the log, and `tests/test_decisions_index.py` keeps
the two files in sync. A line ENDING in a `→ <path>` link is one whose detail lives in a module
doc or task file instead of the log (a bare `→` inside a label is not a link). Deliberate deviation from the flat `DATE | decision | reason`
shape: grouped by topic, newest first inside a group — at 100+ entries the thematic grouping is
what makes the index scannable, and the labels carry the reasons (rationale: DECISIONS
2026-08-24, the split entry).

**Scout — route C**
- `08-03` route D deleted; scout answers "what is in it", and grades nothing
- `08-03` viewer profile removed; nothing personalizes the grade
- `07-21` one queue page: scout report is the base, triage merged in
- `07-21` scout preview: 160px, inlined once, no 2x source
- `07-20` grades the MATERIAL, not the reader
- `07-20` scout mode: audio-only fetch, no local summarizer, own flag

**Digest — route D**
- `07-30` digests in TWO passes (a composing agent cannot be given a length)
- `07-30` separate route, separate page, grades nothing

**Translate**
- `08-20` the translator writes in one pass, and the marker names the TOOL — 43 of 47 paid a blocked retry
- `08-20` route B stops summarizing; the summarizer cost 42% of a translator and gated nothing
- `08-11` the draft carries BOTH forms — subtitles get the spelling, the dub gets the reading
- `08-05` route B gets a chunked translator, as an escape hatch (chained chunks, not parallel)
- `07-28` route B step 2 fans out through a Workflow
- `07-18` Sonnet semi-automatic is the PRIMARY route
- `07-19` 4-way bake-off † · `07-18` Gemma replaces Qwen3 † · `07-15` translate stage BUILD †

**TTS / synthesize**
- `07-25` **Silero is the ONLY engine** — the entry that supersedes the whole F5 cluster
- `07-25` ear-confirmed on finished videos (and what it does NOT close)
- `07-25` `atempo_floor = 0.75`
- `07-19` Silero v5 audition · `07-18` Silero v5 acknowledged
- `07-15` day-1 bake-off: Chatterbox rejected
- `07-19` F5 speed ledger † · `07-19` `f5_nfe` 48→16 † · `07-16` F5Engine BUILD † ·
  `07-16` ESpeech bake-off † · `07-16` ESpeech narrator voice †

**ASR / transcribe**
- `08-06` **Parakeet-TDT replaces whisper as the transcriber** — and what the switch costs
- `07-24` `condition_on_previous` survives measurement
- `07-24` transcribe-speed axis closed (fp16 large-v3 at its ceiling)
- `07-22` batched inference is a DIFFERENT decode, not a faster one
- `07-22` the decode config is a key, the verifier is not
- `07-20` isolated-window re-ASR has a measured cost · `07-20` `--repair-asr` exits 0
- `07-19` repairing a whisper hallucination · `07-19` collapsed alignment: guard the cause
- `07-17` segmentation cluster · `07-17` whisper punctuation is the ROOT fix
- `07-15` word-level sentence resegmentation

**Verify / completeness**
- `08-01` `entity_loss` DELETED, not demoted again
- `07-27` `neg_loss` demoted to advisory
- `07-26` a mis-heard PRODUCT NAME is not sentence damage
- `07-19` `dup_adjacent` + `rate_implausible` · `07-19` completeness check, 4 detectors †
- `07-19` triage signal: narrow `refusal`
- `07-17` base similarity gate 0.8 → 0.9
- `07-16` verify is ASR-BLIND, confirmed on real content

**Mix / dead air**
- `08-06` the passthrough seam is inaudible by ear (and what that verdict does NOT cover)
- `08-06` uncovered speech plays the ORIGINAL; the seam is mux, not assemble
- `07-17` dead air CLOSED by ear (final) · `07-17` compression back to atempo, bed is the mode
- `07-16` dead-air elimination BUILD † · `07-16` interim ear verdict

**Pipeline, batch, artifacts**
- `08-24` DECISIONS splits: the index stays at the root, the entries move to docs/decisions-log.md
- `08-24` agent-docs replaces the 4-file framework; PLAN dissolves into BACKLOG + tasks/
- `08-11` `separate` CHUNKS long audio; the length threshold hid a container wall and a memory wall
- `08-06` the per-video trigger is a WATCHER beside the wave; the pipeline did not move
- `08-06` Parakeet and htdemucs DO co-reside; a re-download is not transcript-neutral
- `08-06` the download prefetch is a PRE-PASS, not a parallel branch inside the sweep
- `08-06` `separate` is SCHEDULED, not positioned: its gate asks whether a dub is coming
- `08-06` the JS runtime is a WHEEL in the venv (deno), not a host binary and not Node
- `08-06` a no-speech video ships without a dub; the queue converges
- `08-06` verify round-trip ships OFF (2 real defects in 24 flags); completeness stays
- `08-03` CHANGELOG.md retired; measurements retire to DECISIONS
- `07-28` the tail DEGRADES instead of failing: a miss costs a track, not the artifact
- `07-19` stage-major is the default batch order · `07-19` the VRAM rule is a budget
- `07-17` batch queue + stop switch · `07-19` run report: two non-obvious `run.json` choices
- `07-15` pipeline tail design panel

**Measurement & method** — the entries most likely to save you a day
- `08-24` RETIRED with PLAN: F5-era stage shares + pre-07-22 wall-clock figures
- `08-07` `utilization.gpu` is not a load signal; quote the SM CLOCK
- `08-06` **the batch gets an absolute clock**; the first honest baseline retires the ~1.7× estimate
- `07-25` retrospective: three times the arithmetic was right and the SHAPE was wrong
- `07-22` measuring ASR inverts the sweep's premise; and the HOST DRIFTS
- `07-22` overhead is SUBTRACTED per stage, never summed across kinds
- `07-22` the roadmap is named, not numbered, because the numbers were lying
- `07-21` an agent's report of what it DID is not evidence; the transcript is
- `07-20` two kinds of timing, kept apart; the filesystem does the stamping
- `07-19` measurement gotchas that will recur · `07-19` `no_repeat_ngram_size` REJECTED

**Scope & founding constraints**
- `07-25` what this repo produces is a TOOL; a video is never the deliverable
- `07-15` founding decisions · `07-15` PoC reframe · `07-15` stack verification
- `07-17` proper nouns: pronunciation chain
- `07-16` local-only constraint amended †

† carries a `SUPERSEDED` header — the code it describes is gone or changed. Read the header first.
