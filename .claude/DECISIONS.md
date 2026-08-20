# DECISIONS

Why we chose what we chose. Newest first — **append directly below the `---` that closes the Index,
never above it.** Entries are not rewritten to match today's code: when the code moves out from
under one it gets a `> SUPERSEDED <date>` line and stays, because the rejected alternative is the
part worth keeping. Content is cut in exactly three cases — pure scheduling that already lives in
`PLAN.md`; a generalised lesson promoted to `~/.claude/knowledge/`, where the entry keeps what it
decided HERE and points at the file instead of restating it; and prose that decides nothing that
still applies, i.e. a verdict on a retired component or a roadmap ordering both overtaken. The
third is the narrow one: a REJECTED alternative is never dead — it is the part worth keeping — so
only the verdict-on-what-shipped half goes. Every cut is stamped in place (`Trimmed <date>: …`)
rather than made silently.

**An appended entry is two edits: the entry and its line in the Index.** The Index is
hand-maintained and reads as complete whether or not it is — `tests/test_decisions_index.py`
is what keeps that honest.

The bottom third of the file is a forward-ordered archive of the founding week — see the ARCHIVE
divider. Look things up through this index, not by scrolling.

## Index

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

---

## 2026-08-20 — route B stops summarizing; the cheapest agent is the one not spawned

Route B spawned two sub-agents per video: a translator and a summarizer. The summarizer now runs
only when `sumIds` is passed explicitly, and the skill passes an empty list.

**What it cost, measured 2026-08-20** over five route-B runs (08-05, 08-06, 08-07 and both waves of
08-20), reading `usage` per turn out of the agent transcripts. Per-agent medians, all runs on
`claude-sonnet-5`, priced at list ($3/$15 per MTok, 1 h cache write ×2, cache read ×0.1):

```
translator  $1.52   output 25 366   cache write 124 527   cache read 775 972   11 turns
summarizer  $0.64   output  4 417   cache write  86 215   cache read 197 620    5-7 turns
```

42%, for the ONE artifact on this route that gates nothing, skips nothing and has no code reading a
verdict out of it (2026-07-19). On the 307-video queue that is ~$187 of summaries against ~$232 for
all the translation still outstanding.

**Why the summarizer is so expensive for a 200-word output.** Its output is 17% of a translator's,
but its cache WRITE is 69% of one — because cost tracks turns × context, not the text produced. Any
agent that reads a whole transcript pays for that transcript on every turn. This is the general
lesson and it outlives this decision: **the length of what an agent writes is nearly irrelevant to
what it costs.**

**What it costs us, stated plainly.** The digest's `- summary (N words):` block and the queue page's
«самое интересное» column are empty for a route-B batch. Both already render an absent summary as
nothing, so no surface breaks — the report simply loses its content half and keeps the quality half.
A video promoted from route C keeps the `summary.md` route C wrote (queue-contract §4).

**Rejected: keeping summaries on a cheaper model.** Haiku would cut the per-summary cost, but the
summary is read by a human deciding what to watch, and a worse one is worse at the only job it has.
Off is honest; cheap-and-degraded pretends the column still means something.

**NOT the reason, and it must not be read as one:** the summarizer prompt is currently killed by the
safety classifier — it routes `summary.md` through PowerShell because a harness hook denies subagent
`Write` on that path, and six agents died that way on 2026-08-20. That is a defect to fix on its own
merits. Had the prompt been healthy, this decision would be identical.

**The exit.** Pass `sumIds` and everything works as before — the workflow kept the capability, and
route C is untouched. Revisit if a report surface ever needs the content half enough to pay 42%.

## 2026-08-11 — the draft carries BOTH forms; one string can serve two consumers

`ru.srt` is built from `text_ru` and the synthesis from `text_tts`, and both were derived from
one string the translator wrote. The two consumers want different text, so every improvement to
one was a regression in the other — and this entry exists because that trade was made in BOTH
directions on a single day before the third option was seen.

Where it started: the translator was told to keep Latin and digits, "the normalizer handles the
rest". It cannot — though NOT for the reason first written down here, and the difference matters
enough to state plainly.

Silero does delete Latin script: measured 2026-08-11, three sentences synthesized with and
without a Latin word render byte-identical audio, same frame count, same hash. But that
deletion has never once fired in this pipeline. `text_tts = normalize_for_tts(text_ru)` and that
function is Cyrillic-only by contract — it is what makes it idempotent — so the engine has never
been handed a Latin character. The deletion is a live trap for anyone who hand-writes `text_tts`,
and nothing more.

The real defect was always the pronounce chain's fallback: a SPELLING-based scanner that INVENTS
a reading for every out-of-dict token. 756 invented readings over 261 distinct Latin tokens on
one video of the 2026-08-10 batch, none of which `verify` can hear. The batch also flagged 765
`english_echo` lines over 30537 sentences, because the corpus is dev streams and dense with code
identifiers. So the dub was not silent on those words — it said them wrong.

The first fix made `text_ru` Cyrillic-only. It worked for the dub and wrecked the subtitles, which
inherited spelled-out numbers and transliterated names. The cost was written down honestly and it
was still the wrong shape: the problem was never which form to prefer, it was serving two
consumers from one field.

**Decision: the DRAFT carries both forms inline as `[[written|spoken]]`, and
`build_translation.py` resolves it in two directions** — `written_form()` for `text_ru`,
`spoken_form()` then `normalize_for_tts` for `text_tts`. `translation.json` keeps exactly the
shape it had, so `assemble`, `verify` and every report are untouched; the markup lives only in
the draft.

REJECTED — letting Silero's Latin deletion do the cutting (write both forms plainly and rely on
the engine to drop one). It builds the design on an engine DEFECT, and it does not even work
cleanly: the deletion removes letters and leaves the parentheses, punctuation and digits behind,
and digits are the other thing the engine reads badly. Both extractions have to be deterministic
and neither may depend on what the engine happens to do with a script it dislikes.

REJECTED — a third field the agent writes. It would hand authorship of `text_tts` to the LLM, and
route B's hard guardrail is that `text_tts` is DERIVED: `verify` compares the ASR round-trip
against it through the same normalizer, so a hand-spelled value silently breaks verification. The
markup gives the helper better input without moving that boundary.

`[[…]]` and not `{…}` or `[…]`: this corpus is people talking about code, where single braces and
brackets genuinely occur in the prose.

**An end-to-end check changed the guidance.** An unmarked plain number came out right anyway —
the subtitle kept `5 минут` and the dub said «пять минут», because `normalize_for_tts` remains the
net under the markup. So marking is only required where the fallback actually errs: Latin, which
Silero deletes, and readings that are not mechanical (versions, ratios, `24/7`). Simple numbers
are better left unmarked — the digit is what a reader wants to see, and the normalizer already
says it correctly. That materially lowers the extra output volume this scheme costs.

Two side effects worth knowing. `english_echo` becomes meaningful again: it runs on the RESOLVED
written side, so a marked name is legitimate Latin while untranslated lowercase English prose
still flags — the Cyrillic-only version had effectively silenced it. And `tools/renorm_workdir.py`
can no longer re-derive `text_tts` from `text_ru`, because the spoken side is not recoverable from
the written one; it now warns and points at rebuilding from the draft, since silently re-deriving
would hand every marked name back to the fallback.

**This ships as a TRIAL, and the exit is named in advance.** The translator now writes both forms,
which costs output volume and therefore time at the seam. If translate becomes noticeably more
expensive or slower, look for another way — and the cheapest is to ROLL BACK to the previous
shape (plain Latin in `text_ru`, the normalizer doing what it can), which is one revert of this
entry's change and costs nothing else, because the markup lives only in the draft and
`translation.json` never changed shape. PLAN carries the watch item.

The other way, if a rollback is not wanted: make the fallback pronunciation-based instead of
spelling-based. Measured 2026-08-11 against espeak-ng, which is already installed on this host —
`button` → `bˈʌʔn̩` where the scanner says «буттон», `changes` → `tʃˈeɪndʒᵻz` where it says
«чанджс», `alchemy` → `ˈælkəmi` where it says «алчеми» (the `ch` is /k/, which no spelling rule
can know), and `AlchemySerializeField` splits into three correctly stressed words where the
scanner emits «алчемисериалайзфиелд». That would let the translator mark far less. It would NOT
replace the markup: subtitles need the original spelling regardless, and espeak gives `Odin` the
English reading «оудин» where the established Russian form for this library's name is «Один» —
a knowledge problem, not a phonetics one. It also means a third external binary, which the stack
rule currently forbids.

**NOT established.** What the second form costs in output VOLUME, which is what actually binds the
chunked translator (PLAN) — the 2000-sentence chunking threshold was calibrated before this and
has not been re-measured. No full batch has run under the rule yet: the only evidence is one
164-sentence video, where translate took 7.8 min of a 10.5 min run.

## 2026-08-11 — `separate` chunks long audio; the length threshold hid TWO walls

A route-B batch of 11 videos lost 3 at `separate`, all with demucs exit 1. The three were the
three longest (6.95, 7.50, 7.90 h) and all eight survivors were 5.89 h or under, so the length
threshold split the sample with no misclassification. That clean split argued for ONE cause. It
was two, stacked, and the second only became visible once the first was gone.

**Wall 1 — the container.** The stage extracts `source_full.wav` as pcm_s16le 44.1k stereo =
176400 B/s, and WAV keeps its size in a 32-bit field. Past 6h46m ffmpeg says
`Filesize 5016920142 invalid for wav, output file will be broken` and writes a header no reader
accepts. Fixed with `-rf64 auto`: a plain WAV header until the overflow point, RF64 after it.

Verified rather than assumed, because the reader matters here: an RF64 probe file is REFUSED by
`sphn` (demucs's fast path — "end of stream") and read correctly by the ffmpeg reader demucs
falls back to. The path works, through the slower of its two readers.

REJECTED — W64 and FLAC. Both remove the size limit and FLAC would even keep the sphn fast path,
but both change the container for EVERY video. `-rf64 auto` is byte-identical below the
threshold, which is the smaller blast radius on a stage that was working for everything shorter.

**Wall 2 — memory, and this is the one that shapes the design.** With the container fixed, 6.95 h
separated normally and 7.90 h died on `DefaultCPUAllocator: not enough memory: you tried to
allocate 40135360512 bytes` on a 63.7 GB host. That figure is not opaque:
28441 s × 44100 × 2 ch × **4 sources** × 4 B = 40 135 357 440. htdemucs allocates its output
tensor for all four stems across the whole track **even under `--two-stems vocals`**, which only
discards the other three afterwards. Peak is therefore linear in duration — ~1.41 MB per second
of source — plus the input tensor and the copies around it.

REJECTED — `--segment`. It bounds the INFERENCE window, and what failed is the output buffer for
the entire track. It is the obvious first thing to reach for and it does not touch this.

REJECTED — dropping the bed for very long videos (degrade to `replace`). Cheap, but it makes the
output's character a function of duration, which is the kind of silent inconsistency the
degrade-vs-raise rule exists to avoid.

**Decision: cut the source into overlapping windows, separate each, blend back.**
`separate_chunk_sec = 3600` holds the four-stem term at 5.1 GB no matter how long the video is.
That is the actual property being bought — not headroom, but a ceiling that has stopped being a
function of duration. A larger chunk would only move the same wall further out.

Three implementation choices worth keeping:

- **One demucs invocation for every chunk, not one per chunk.** htdemucs is load-dominated
  (~13 s, `07-19`) and processes its tracks sequentially, so this pays the model load once while
  still peaking at a single chunk's allocation.
- **The blend is a weighted average under a linear ramp, never a crossfade.** A crossfade
  shortens the result by its own length at every cut, and the bed is laid under a dub whose
  timeline came from the transcript: a bed a few thousand frames short slides the music against
  the picture for the rest of the video, and nothing downstream measures it. Equal-power (sqrt)
  is wrong for a second reason — the two chunks are separations of the SAME seconds, so their
  overlap is correlated and a sqrt law bulges ~3 dB at every seam.
- **The stitch streams.** A whole-track accumulator would rebuild the exact allocation this
  entry exists to avoid: 7.9 h of float32 stereo is 10 GB before the weight array.

**Method note, because it invalidated the first version of the tests.** The natural fixture is a
"perfect separator" whose every chunk stem is exactly its slice of the source — and it cannot see
the blend at all. When both inputs agree, `a·w + b·(1−w)` collapses to `a` for ANY ramp direction
and ANY zone width. Mutation-checked: a reversed ramp and a halved blend zone both survived it,
and deleting the length pad survived too because tidy arithmetic never reaches the pad. Closing
them needed chunks that DISAGREE — a per-chunk DC signature, so the output's offset traces the
ramp itself — plus a deliberately truncated stem. One test was additionally passing for the wrong
reason: its "direction" check was per-sample monotonicity, and a reversed ramp slides back by
5.7e-7 per sample, under any tolerance loose enough to allow PCM_16 quantisation.

**Confirmed on real media the same day**, which is what promotes this from arithmetic to a
result: all three videos that had failed went through. 7.90 h → 8 chunks → 633.7 s, 7.50 h → 8
chunks → 646.9 s, 6.95 h → 7 chunks → 588.7 s, and a 4.35 h video that had always worked → 5
chunks → 341.4 s. That is ~80 s per chunk on every one of them, so the stage's cost is now linear
in duration with no cliff, where before it was linear up to a wall and infinite past it. Peak
VRAM held at 4.1 GB against the 37.4 GiB CPU allocation that used to kill the run.

**NOT established.** Whether the seams are inaudible — the tests measure a seam as a numeric
discontinuity, and in this project the ear is what adjudicates audio. The cuts land on the hour
marks (1:00:00, 2:00:00, …) of the three long videos, which is where to listen. `-rf64 auto` is
also unreachable while chunking is on and survives only as the net for `separate_chunk_sec = 0`.

## 2026-08-07 — `utilization.gpu` is not a load signal; the SM CLOCK is the one that decides

`host_guard` reported `GPU 35% util, 815/12282 MiB, 57 C, 210 MHz — idle`, and on the strength of
that 35% the orchestrator told the operator the card was busy and refused to measure. The operator
pushed back with Task Manager at 0%, 52 C and everything suspended. **The operator was right, and
the refutation was already inside the guard's own line: 210 MHz is the idle clock.**

NVIDIA's `utilization.gpu` is "the fraction of sample windows in which at least one kernel was
executing" — an occupancy-of-time figure, not a share of the machine. Periodic one-shot kernels
from the desktop compositor and suspended apps keep it in the tens of percent while the card does
no work at all and never leaves its idle clock. Measured the same session, under a real transcribe:
**210 MHz / 13.5 W at rest against 2445 MHz / 45 W under load.** The clock moves by an order of
magnitude; the utilisation number does not distinguish the two states.

**So the guard's thresholds are looking at the wrong instrument.** `BUSY_UTIL_PCT = 40` was
calibrated against a game holding the card at 98% and 8.6 GB, and it is fine for that. It cannot
see the case that actually corrupts a measurement here, and — worse — it printed the word `idle`
beside a number the reader then over-trusted in the opposite direction. Both failure directions in
one line.

What follows for anyone reading a host figure in this repo: **quote the SM clock, not the
utilisation.** An idle-clocked card is idle whatever the percentage says, and a card at its boost
clock is busy whatever the percentage says. Memory remains the second-best signal and is why the
guard catches a loaded model at all.

The guard is UNCHANGED as of this entry — the fix is a PLAN item, because changing a shipped
threshold deserves its own measurement rather than a same-session reflex.

## 2026-08-06 — the per-video trigger is a WATCHER beside the wave, and the pipeline did not move

The tail used to start only after the LAST agent finished: 1145.6 s of work queued behind a
787.9 s wave, with the machine idle through most of it. `scripts/drain.py` watches for each
video's `translation.draft.json`, and the moment one lands it builds that video's
`translation.json` and runs its pipeline to MKV — while the other agents are still writing.

**No pipeline change was needed, which was the open question.** `TranslateStage.done()` is
"translation.json exists", so a plain per-video `-m overdub <url>` already fast-skips download,
transcribe and translate and runs exactly the tail. The only missing piece was something to WAIT,
and no stage can be that: the drafts are written by sub-agents the orchestrator dispatches, so the
filesystem is the only thing that knows a video is ready. The drain is therefore a SCHEDULER — it
owns no artifact, enforces no contract, and every file it produces comes from the same code the
ordinary resume would have run. `run_pipeline` is untouched, and so is the batch's status machine.

**Serial over videos, deliberately.** The tail still contains `separate`, the one GPU stage left
in it. Draining one video at a time serializes that for free; a pool would have needed the GPU
queue this project has repeatedly decided not to build yet.

**Three things it may never do, each a silent failure if it did.** It must not read a half-written
draft as ready — the file arrives through a sub-agent's shell redirect, so readiness is a
successful JSON PARSE, not `exists()`; a torn read costs one more poll, while trusting it burns
the video on a build against a truncated draft. It must not consume a `work/STOP` — `check_stop`
consumes at honor time and exactly one (stage, video) pair may observe one, and this scheduler
reports nothing per video, so it observes and leaves the file. And it must not decide a video is
finished with: anything it could not drain is reported `pending` and left for the ordinary step-3
resume, because the queue is the human's (queue-contract §3).

**Rejected for now: dispatching the TRANSLATORS per video too.** It is the other half of the
trigger and it is worth much less than it looks — the wave ends on its slowest AGENT, which starts
when ITS transcript exists either way, so the win is bounded by the spread of the transcribe phase
(151.4 s over 10 videos) rather than by the wave. It also cannot use `Workflow` as it stands,
since the whole queue goes in one call by contract (§6).

## 2026-08-06 — Parakeet and htdemucs DO co-reside; and a re-download is not transcript-neutral

Two measurements taken while sizing the GPU mutex, one of which killed the mutex's premise and one
of which is about something else entirely.

**Co-residency: 9930 MiB of 12282 peak, no OOM.** `--only transcribe --force` and `--only separate`
were run as two concurrent processes and both completed their real work (28.8 s / 2055 words, and
16.2 s with the bed written). So "the Parakeet worker holds the card, therefore htdemucs must wait"
— the one real argument for a phase barrier, and the reason the mutex was framed as protecting
VRAM — **is not established on this host**. A scheduler may simply run them together.

What the number does NOT license: 19% headroom is thin, it is ONE pair of videos (10 and 12
minutes), and Parakeet's footprint is the length-dependent half. An unattended night over
arbitrary lengths has not been shown to fit, and this measurement cannot show it.

**The mutex has no call path to guard today.** The only concurrency in the codebase is the
download prefetch pool, and download holds no GPU; `run_pipeline` and the stage sweep are strictly
sequential, so no two GPU stages can meet inside one process. The live hazard is two PROCESSES
(the route-B runbook now asks the operator to start a second one), and a `threading.Lock` cannot
see across that boundary. The mutex therefore belongs to the per-video scheduler, not beside it —
building it now would be a lock that reads as protection and provides none.

**Longest-first ordering is inert for the same reason.** Every stage in the sweep is a full
barrier and the translate wave is fanned out once over the finished list, so the first translation
cannot start before the LAST transcript exists — no ordering of the sweep moves it. Sorting the
download pool would help, but on a first run no duration exists yet (`source.info.json` is written
BY download). Both are components of the scheduler, not steps toward it.

**Separately: re-downloading a video CHANGED its transcript.** `uFYLIdYXntk` read 2057 words /
149 sentences before its `source.mkv` was deleted and re-fetched, and 2055 / 150 after. Isolated
in one step — a second `--force` decode of the SAME file reproduced 2055 / 150 exactly, so the
decoder is deterministic and the input moved. This is evidence on the open backlog question about
reusing scout audio on promotion, which PLAN records as "believed benign, never checked": a
re-fetch is not transcript-neutral, at least not always. What is NOT established is why — the two
downloads were not compared for format or bytes, so "yt-dlp picked a different format" is the
likely explanation and not a measured one.

## 2026-08-06 — the download prefetch is a PRE-PASS, not a parallel branch inside the sweep

`download` is the only stage holding no GPU and bound by the network, and on the baseline it was
323.8 s of strictly serial fetching (13.3% of machine time) whose longest single video was 82 s —
so most of it was the queue, not the transfer. It now runs concurrently, `download_concurrency = 3`.

**Rejected: widening the stage-major loop to run its jobs in a pool.** That loop owns the STOP
semantics, the cross-stage status machine and per-video failure isolation — the batch's
convergence guarantees, and the most heavily pinned code in the repo. One stage's wall clock does
not buy a share of them. The pre-pass instead runs the SAME stage through the SAME `run_pipeline`,
so timings, spans and the artifact contract come from one code path, and the sweep is untouched
and remains the authority: anything the pre-pass fails to fetch simply has `done() == False` when
the sweep arrives, is refetched sequentially and reported as an ordinary FAIL row. Hence every
exception in it is swallowed — a prefetch failure costs a retry, never a video.

**Two things the concurrency forced, both non-obvious.** `check_stop` had to become thread-safe:
its invariant is that exactly ONE (stage, video) pair ever observes a STOP, which held for free
while checkpoints ran on one thread, and two racing threads would have reported two videos stopped
for one operator action. And a STOP observed during the pre-pass is deliberately NOT honored
there — the file is written back and handed to the sweep, because the pre-pass reports nothing per
video and owning the halt would leave the sweep running against a stop already made.

**`--force` opts out.** It makes `run_pipeline` skip `done()` entirely, so the sweep would fetch
every video a second time and the pre-pass would be pure waste. Everything this buys rests on the
sweep skipping what is on disk, which is exactly what `--force` switches off.

**The knob is low on purpose and this one carries a risk the other scheduling changes do not.**
Stage-major already delivers a queue to YouTube as one burst, and 2026-07-20 lost two videos of a
twelve-video batch to transient 403 / "Video unavailable" that both succeeded on a plain re-run.
Widening the pool makes the burst burstier. 3 is a guess bounded by that history, not a measured
optimum, and nothing above it has been tried.

## 2026-08-06 — `separate` is scheduled, not positioned: its gate asks whether a dub is COMING

`SeparateStage.done()` skipped whenever `dub_ru.wav` was absent, which pinned the stage after
assemble: the only evidence it accepted was the dub itself. That made the one piece of GPU work
with no dependency on the translation sit in the post-translate tail, while the card idled through
the entire Sonnet wave — 811.6 s of nothing on the 2026-08-06 baseline.

The gate now runs on EITHER the dub or a non-empty transcript, so the stage may run any time after
transcribe. Worth 301.5 s moved out of a 2438.6 s batch (12.4%), tail 1145.6 → 844.1 s — the
largest single scheduling win available and it does not touch the translate seam.

**What the weaker evidence costs, stated plainly.** A dub is proof; a transcript is a forecast. A
video with speech whose translation or synthesis then FAILS now pays one htdemucs pass for a bed
nobody mixes — that is the accepted trade. What it does not cost is the case the gate was built
for: the expensive one is a music-only clip (up to 449 s to separate), and that has an EMPTY
transcript, so it still matches neither arm and is still skipped. A torn transcript reads as "no
speech" for the same reason — guessing the other way spends a GPU pass on a file nobody could
parse, and mux still raises loudly if a dub later appears without a bed.

**Rejected: running it right after transcribe.** The obvious place is wrong. demucs is the BIGGER
of the two GPU consumers (301.5 s against transcribe's 151.4 s), so putting it beside transcription
delays every transcript and therefore the batch's first translation — which is the latency the
whole pipelining item exists to cut. The wave is the correct window precisely because the pipeline
process holding the Parakeet worker has already exited by then, so demucs shares the card with
nothing and the VRAM co-residency question never arises.

**The one new hazard: `timings.json` is now written by two processes at once.** The separate sweep
and `build_translation.py` both read-modify-write it, so a genuine overlap drops one stage entry
with no error and no flag. Held for now by an ordering rule in the route-B runbook (the sweep
finishes before the helper runs, and it takes ~40% of a wave). If that becomes awkward to hold by
hand the answer is a lock in `overdub/timings.py` — not a sixth copy of the rule.

## 2026-08-06 — the batch gets an absolute clock, and the first honest baseline retires the pipelining estimate

`timings.json` gained a third section, `spans[<stage>]`, carrying three ABSOLUTE stamps —
`enqueued` (the runner decided the stage must run), `started` (the body began, i.e. after any
gating) and `finished` — plus `work/runs.jsonl`, one append-only row per pipeline PROCESS with its
elapsed window, ids, audio and a `config_key`. `stages[x]` is untouched and stays a `perf_counter`
duration.

**Why three stamps and not two.** A duration cannot say WHEN a stage ran, so it cannot show two
videos overlapping, and it cannot separate waiting for a shared resource from working — both land
inside the one measurement. Once anything queues for the GPU, "transcribe 340 s" would be 40 s of
decode and 300 s of queue with nothing able to tell them apart after the fact. The two stamps
coincide today because nothing gates; the DEFINITIONS are what had to be fixed before a scheduler,
not after.

**Why additive and not a redefinition.** `total_wall_s` already changed scope once (2026-08-05, the
translate seam) and every timings.json on disk is keyed to `stages[x]`'s current meaning. A second
silent shift would make the corpus unreadable rather than merely incomplete. The two also fail
differently and that is worth having: `perf_counter` is monotonic and survives a clock step, the
stamps are comparable ACROSS videos and processes, which is the thing a duration can never be.

**The grain of `runs.jsonl` is one INVOCATION, not a batch or a night** — route B drives the
pipeline at least twice per queue (a pass to the seam, then a resume), so "batch" would silently
name two different spans in one series. `config_key` (`asr_key ++ synth_key`) travels with every
row because a series that quietly spans an engine or voice change is worse than no series.

### The baseline, 10 videos, 4.10 h of source

Machine time **2438.6 s** (step 1 479.4 + Sonnet wave 811.6 + step 3 1147.7) = **×6.05** audio per
unit of machine time. The attended SESSION span was 5700.6 s (×2.59) and the 3262 s difference is
the orchestrator's own analysis between steps — two different quantities, and only the first is
what a scheduler can move.

Per-stage cost as the UNION of spans, never the sum:

| stage | union | sum | share of machine |
|---|---|---|---|
| translate | 787.9 s | 4888.6 s (**6.20×**) | 32.3% |
| mux | 470.3 s | — | 19.3% |
| download | 323.8 s | — | 13.3% |
| synthesize | 320.7 s | — | 13.1% |
| separate | 301.5 s | — | 12.4% |
| transcribe | 151.4 s | — | 6.2% |
| assemble | 52.2 s | — | 2.1% |

**The double-count factor is not a constant.** PLAN carried 4.41× off a 6-video batch; this
10-video one reads 6.20×, because the overlap grows with the width of the fan-out. The warning is
"a sum lies more the wider the wave", never a coefficient. The pipeline's own digest printed
`translate 75.1%` against an honest 32.3%.

### What the baseline retired

**The tail does NOT fit inside the wave.** Tail (synthesize+verify+assemble+separate+mux) union
1145.6 s against a 787.9 s wave — **×1.45 too big**. The estimate in PLAN came off the 2026-08-06
6-video batch where the inequality ran the other way (565 s tail, 664 s wave), so the projected
~1.7× end-to-end is withdrawn: the machine must still do head 475.2 + tail 1145.6 = 1620 s, giving
**×1.50** against today's 2438.6 s.

**Running `separate` INSIDE the wave is confirmed by measurement, and it is the biggest single
lever.** demucs is 301.5 s of GPU work with no dependency on the translation, and the card is idle
for the whole 811.6 s wave. Moving it there drops the tail to 844.1 s and lifts the ceiling to
**×1.85** — worth 12.4% of the entire baseline on its own, more than every other overlap combined.

**`mux` is the biggest machine stage after translate** (19.3%, larger than download and transcribe
together) and it is ffmpeg and disk, not GPU. Whatever binds after pipelining, it is that.

Barrier cost, measured inside step 1 where no human time contaminates it: the first video finished
downloading after 12 s and waited **313 s** for the other nine before its transcribe was enqueued.

**One queue, so the ratios are not a population.** What generalises is the direction (a sum lies
with fan-out width; demucs fits in the wave); what does not is ×1.50 or ×1.85 — tail-to-wave
depends on what is in the queue, and ten ~25-minute videos is one shape of it.

## 2026-08-06 — the passthrough seam is inaudible; 30 ms stands

Ear verdict (operator, 2026-08-06): the cross-fade into the English original is not audible, and no
knob moved — `_PASS_FADE_S` stays at 30 ms per edge. Everything else about the feature was already
measured the same day (entry below); the ear was the one verdict the PCM check could not stand in
for, and it is the instrument that adjudicates quality here.

**What the verdict does NOT cover: the mask floor.** The three stamped videos carry spans of
5.7 / 9.8 / 19.9 s, each more than an order of magnitude above `_PASS_MIN_S` (0.25 s), so nothing
that floor drops was in what was heard — a listen to those spans cannot say anything about it in
either direction. It remains a guess, and one nothing has yet reported a defect against; hearing it
would mean lowering it and listening for the transients it exists to suppress, which is a different
measurement, not this one.

## 2026-08-06 — where the ASR heard nothing, the ORIGINAL audio plays

Where the transcript is empty the bed played music and room tone with the voice stripped out, so
speech the pipeline LOST sounded exactly like a deliberate pause. Over the spans transcribe stamps
as unrecovered, the original is now cross-faded in: the viewer hears an English voice and the
failure explains itself. Presentational by intent — the operator's ear could not make out ~70% of
those spans either (2026-08-06 batch), so there is nothing to transcribe and nothing to chase.

**The seam is `stages/mux.py`, not `stages/assemble.py`.** PLAN named assemble; assemble builds
the RU speech on a silent timeline and never sees the bed. The bed-vs-original layering exists
only in mux, so that is the one place a source swap can happen at all.

- **bed only, by decision.** Under `duck` the base already IS the original and no unit span covers
  an unrecovered hole, so it plays there at full level already — the swap would be a no-op laid
  over behaviour that is correct by construction. Under `replace` the original is deliberately
  absent; letting it back in for some spans would make the mode mean two things.
- **The mask subtracts the dub's own intervals.** A unit's slot runs to the NEXT unit's start, so
  the unit before a hole may place audio into it, and swapping there would put English under
  Russian. Not hypothetical: `fV8rxPt-QeU` has 20.1 s of uncovered speech and 19.9 s passed
  through — 0.2 s was the dub. The subtracted set is the pre-atempo superset the duck envelope
  already uses, so the error is always toward keeping the bed.
- 30 ms linear cross-fade per edge (the two sources differ in level and spectrum, not just
  content); pieces under 0.25 s are dropped, since they cannot carry a word and contribute only a
  transient per edge.
- `done()` re-muxes a container stamped before this existed, but **only when the video actually
  has spans** — the unconditional form would re-encode every workdir on disk to produce a
  byte-identical file.

**The acceptance criterion cannot be measured on the finished MKV, and that is the lesson.** "Every
other second is byte-identical" reads as a diff of the RU track; done that way it reports 193.5 s
changed over a 5.7 s mask, with differences running from the mask edge to the end of the file.
That is AAC: the codec reconstructs the waveform only approximately, so one changed sample shifts
quantization for every frame after it. Measured on the PCM MIX instead (mux run twice on
`3owcMLGx0NQ`, once with the mask forced empty): 0.676% of frames differ, first at 501.6000 s and
last at 501.6+5.68 s against a mask of 501.6-507.3, nothing outside it, peak and length identical.
Read the lossy artifact and you would have concluded the mix leaks everywhere; read the stage the
change is IN and it is exact. Generalises past this feature: any "did only the intended part
move" check must be taken upstream of a lossy encoder.

**PLAN's fixture did not exist.** It stated the 2026-08-06 batch "is stamped and is the working
fixture"; not one of 146 workdirs carried `hole_spans_unrecovered` — the three named videos were
transcribed before the stamp landed and had the COUNT only, which is exactly the absent-means-
unknown case. Recovered by re-running the VAD pass over the surviving `source.wav` + `words.json`,
which is the same second pass the worker ends with, and accepted only because it reproduced the
worker's own stamped count and seconds exactly on all three (1/5.7 s, 2/9.8 s, 2/20.1 s). A
recomputation that has to agree with a number the code already wrote is checkable; one that does
not is a fabrication with a plausible shape. The spans are cheaper to keep than to re-derive: this
worked only because `source.wav` survived, and a `work/` cleanup would have ended it.

## 2026-08-06 — Parakeet-TDT 0.6b v3 replaces whisper as the transcriber

`asr_engine = "parakeet"` is the shipped default. It runs in a third venv (`.venv-parakeet`) as a
subprocess worker holding one model per stage sweep, exactly the isolation demucs already has and
for a harder reason: `nemo_toolkit[asr]` resolves 137 packages and pins numpy *below* the
pipeline's (2.5.1 → 2.4.6).

**Measured on 165 videos / 47.9 h, whisper's own transcripts as the comparison.**

- Speed: RTF 0.0034 vs 0.087, ~25×. Transcribe is 30.5% of pipeline wall clock over 375 recorded
  runs, so the batch gets ~1.4× end to end. This reopens nothing: the closed "transcribe speed"
  axis was about levers INSIDE whisper, and reading that closure as "the stage is cheap" was simply
  wrong — the number was in `timings.json` the whole time.
- Text quality is a WASH, not a win. On the repair fixture, whisper 1.6% WER and Parakeet 2.7%; but
  that reference is whisper's own output with human repairs, so whisper is scored against a lightly
  edited copy of itself. Strip the two measurement artefacts (18 words where Parakeet declines to
  reproduce a whisper loop the human left in, 49 words of pure tokenisation like `ai driven` /
  `aidriven`) and Parakeet is 1.56%. Nobody wins on average.
- **The win is the absence of catastrophes.** In the 8 hand-repaired fixture windows — the places
  where whisper failed so badly a human intervened — whisper scores 23.3% and Parakeet 4.2%, better
  in all eight. Across the corpus 5977 words of whisper output are repetition loops Parakeet simply
  does not produce.

**What it costs, all of it measured rather than feared.**

- No VAD. Three silent videos returned 110, 32 and 6 invented words ("That's the seven three" ×15
  over 15 minutes). Silero VAD in the worker gates exactly those three and no healthy video.
- It drops real speech at window boundaries: 20 spans over 146 videos, largest 41 s / 125 words.
  Half survive every VAD setting tried, so it is the decoder, not the gate. The worker now finds
  uncovered speech spans and re-reads them — all five tested came back with MORE words than whisper
  had there, so the hole is a boundary artefact, not deafness.
- Proper nouns: 6 `Claude` → `Cloud` in one fixture video. Whisper had none there. (It also fixed 3
  `clawd` that whisper AND the human got wrong in another — no systematic winner, different
  failures.) This is the domain's own vocabulary, so it stays open in PLAN.
- Timestamps land on an 80 ms grid instead of ~20 ms.

**REJECTED: keeping `--repair-asr` on the new engine.** Its accept gate is "two independent
readings of the clip agree", which is evidence only because whisper's temperature fallback samples.
Greedy TDT is deterministic: the readings are byte-identical, the gate accepts unconditionally, and
"delete, do not invent" loses its only enforcer while every printed line still says the window was
verified. It refuses outright on any engine but whisper. A mode that cannot be wrong is not a safe
mode.

**REJECTED: leaving `_guard`/`floor_run_ratio` wired up.** It keys on words pinned to the 0.02 s
floor, and an 80 ms grid never puts one there — measured 0.0 on all 145 videos. It stays in the
whisper path and is not called from the Parakeet one. `_dehallucinate` is the opposite call and
DOES still run: the engine changed, that defect shape did not.

**REJECTED: `torch.cuda.empty_cache()` between chunks.** Tried to bound the VRAM peak; NeMo's TDT
decoder replays a CUDA graph holding the captured buffers' raw addresses, so freeing them killed
17/17 videos with `illegal memory access` — one poisoned context cascades through the whole batch.
The chunk size is the only knob for the peak, and the ceiling does not announce itself: at
20-minute chunks every long video pinned 10 813 MB of 12 282 and WDDM began spilling to system RAM
instead of failing — 100% utilisation at a twentieth of the throughput.

## 2026-08-06 — the YouTube JS runtime is a wheel inside `.venv-asr`, not a host binary

**The warning that started it.** `yt-dlp 2026.7.4` prints "No supported JavaScript runtime could be
found … YouTube extraction without a JS runtime has been deprecated, and some formats may be
missing" (`extractor/youtube/_video.py`). Four runtimes are supported — deno, node, quickjs, bun —
and only deno is on by default; the rest need `--js-runtimes RUNTIME[:PATH]`.

**Measured before deciding, on `PBGJ9bLN3NQ` (2026-08-06): 23 formats with the runtime, 23 without.**
So the "missing formats" half of the warning did NOT bind on the video that was checked, and this
change bought no format on it. What it buys is the deprecation: the jsless path is on its way out
upstream, and the fix is cheap now and a broken queue later. The 403s of 2026-07-20 are a plausible
second beneficiary and are NOT claimed as one — nothing was measured there.

**Decision.** `pyproject.toml` depends on `yt-dlp[default,deno]` instead of bare `yt-dlp`. `deno`
ships the runtime as a 41 MB wheel that lands in `.venv-asr\Scripts`; `default` pulls `yt-dlp-ejs`,
without which yt-dlp would fetch its JS components over the network per run (`--remote-components
ejs:npm`). Both were missing here because the dependency had no extras at all.

**Rejected: `--js-runtimes node` in the download stage.** Node 22 is already on this host, so it
looked free — that is exactly the trap. It would make a host-wide Node install a load-bearing
dependency that appears in NO manifest, next to a project rule that names ffmpeg and yt-dlp as the
only external binaries. The venv wheel keeps `pip install -e .` the whole story and survives a
machine change. Upstream also sandboxes deno and does not sandbox node, which is the tiebreaker for
running YouTube's own JS.

**Not touched: `download.py`.** No flag was added anywhere — deno is default-enabled, so resolution
happens because the binary is next to `sys.executable`. The stage keeps its two `subprocess.run`
argv lists exactly as they were, and the fix cannot drift out of sync with them.

## 2026-08-06 — a video with NO SPEECH ships without a dub instead of stopping the run

**The property being bought is CONVERGENCE: the list of URLs in is the list of containers out.**
Until now a no-speech video could not reach `out/` at all. `TranslateStage.run` raises when
`translation.json` is absent, and nothing could legally produce an empty one — the degraded
`assemble` branch needs the file to EXIST and be `[]`, `build_translation.py` refuses to run
without a draft, so a sub-agent was the only producer. The result was a queue that silently
returned fewer videos than it took, and 32 of 52 sub-agents on the 2026-08-04 batch translating
and summarizing nothing, because 16 of 26 transcripts were empty.

**Decision.** `TranslateStage.run` writes `[]` when `sentences.json` parses to an empty list, and
says so. `assemble` then takes its existing `no_transcript` exit, `separate` skips (nothing to lay
a bed under), and `mux` ships the container.

**Written in the PIPELINE, not in the route-B helper**, which is where INBOX had proposed it. The
pipeline is the only producer every route shares, so a no-speech video now needs no orchestrator
cooperation and no sub-agent on ANY route — and nothing hand-writes a completion artifact, which
queue-contract §3 forbids. The route-B skill drops those ids from the fan-out instead.

**The line, and it is the whole risk of this change: an ABSENT transcript is not an empty one.**
A video whose transcribe failed has no `sentences.json`, has NOT been shown to have no speech, and
must still stop the run — as must a torn file and one that is not a list. Treating those as
no-speech would ship them silently, which is exactly the class this stage was written to prevent.
`_load_sentences` returns `None` for all three and `[]` only for a real empty list; mutating that
distinction turns the guard off and the test suite catches it.

**Rejected: skipping the video entirely at the driver.** It would need a new "skip" concept in the
stage-major loop, and it would produce no container — losing the convergence property this change
exists to get.

**`separate` gates on the DUB, not on the transcript.** `dub_ru.wav` absent means there is nothing
to mix a bed under, whatever the reason (no speech, no translation, no synthesis), so one condition
covers all three. It is a ~3 GB-VRAM htdemucs pass at median 20 s and worst 449 s — and a
music-only clip, exactly the no-speech case, is the slowest kind to separate. Ordering assumption
stated in the code: the driver always runs `assemble` before `separate`.

## 2026-08-06 — the verify ROUND-TRIP ships OFF; the completeness check in the same stage stays ON

**Read by hand, all 24 of them.** Over the 149-video batch of 2026-08-06: 123 videos, 5852 render
units, **24 `low_similarity` flags = 0.41%**, no `empty_hyp`, no `missing_wav`, similarity median
0.991 and worst 0.631. Of the 24, **two were real dub defects** — `1WMbX0G3KZM` u127, where the
first of four sentences is absent from the audio entirely, and `1KEvpgu77V8` u1213, where Silero
held a final vowel into a long drone. Four more were the Latin-spelling class (`pronounce` owns
that, not TTS). The remaining ~18 were the metric failing on 1-3 word units, where one wrong token
sinks the score: "Эм..." heard as "М." scores 0.667 and is a correct render. Cost of the pass:
**0.94 h of GPU per 123-video batch, 11% of its stage wall.**

**Decision.** `verify_roundtrip = False`. The stage still runs: it writes `report.json`, keeps its
`synth_key`/`units_key` self-invalidation, and still runs the completeness text check — which costs
no GPU and shares the stage by placement, not by dependency (199 flags on the same batch, including
71 `num_loss`). Only the whisper-small load and the per-unit comparison are skipped, and the model
is not loaded at all, because that load IS the cost.

**Rejected: deleting the stage.** It would take completeness with it for no extra saving.

**Rejected: keeping it for units above ~3 words.** It would drop most of the noise and keep both
real catches, but the saving is small — short units are cheap and the time is in the long ones —
so it buys precision, not the 0.94 h the switch was asked for. Still the right shape if the
round-trip is ever turned back on by default.

**What this costs, stated plainly.** This was the only detector that HEARS the output; everything
else judges text. A defect like the unspoken sentence above is invisible to every other check.
The 0.41% therefore measures the ENGINE'S HEALTH on 2026-08-06 and nothing more — turn the switch
back on to re-measure after any engine, voice or normalization change, because with it off the
pipeline cannot tell a healthy Silero from a broken one.

**Not the stale-wav net, which was the reason to hesitate and turned out not to bind.** Verify's
reference comes from the current `translation.json`, so a wav rendered from an older translation
used to self-flag. But `synthesize.done()` already re-renders a unit whose joined `text_tts`
changed, so a re-translation still forces resynthesis with the round-trip off. The net was a
SECOND line, not the only one.

**`verify 0` must never appear for an unscanned run.** `report.json` carries
`verify.roundtrip`, `run.json` copies it, and the digest prints `verify off`. An absent stamp reads
as `true`, never `false` — every report written before the switch existed had an unconditional
round-trip, and defaulting the other way would relabel the whole corpus as never-checked. This is
the same rule `src` follows at the translate seam: not scanned is a different claim from clean.

## 2026-08-05 — route B gets a CHUNKED translator, as an escape hatch and not as the default

`7xTGNNLPyMI` (Karpathy, "Deep Dive into LLMs", 3.5 h, 2259 sentences) defeated the per-video
translator twice: 1200/2258 on 08-04 and 1500/2259 on 08-05, the second through the workflow with
the shipped prompt. Both stopped around two thirds in — an agent reading a 411 KB transcript and
then emitting ~250 KB of JSON. The skill already said not to respawn a third time; it had nothing
to offer instead, so a long video simply could not be dubbed.

**The MECHANISM is deliberately not decided here.** Context window and a turn/tool-use budget both
fit; INBOX (2026-08-04) argued the second from a stronger observation — a second wave that produced
ZERO new records and left drafts byte-identical to wave 1 — while the 08-05 retry did progress
(1200 → 1500). Chunking cuts transcript size, output volume and turn count simultaneously, so it is
the fix under either reading, and choosing between them was not on this change's critical path.
It IS on the path of anything narrower (a predicted safe size, a resume-from-partial), so that work
confirms the mechanism first.

Now it can: `--plan` cuts the transcript, one sub-agent takes each chunk into
`work/<id>/translate/<from>-<to>.json` in the ORDINARY draft record shape, and `--join`
concatenates them into `translation.draft.json` before the existing build runs untouched. Nothing
downstream of the seam moved a byte, which is the whole point — this is a different way to fill the
same draft, not a different contract.

**Rejected: making it the default.** The per-video agent sees the entire video at once and the
route's own prompt calls that its advantage. Chunking trades that for coverage, so it stays the
exception a measured `INCOMPLETE` earns.

**Rejected: parallel chunks.** The user's call, and the right one: chunk N reads the tail of chunk
N-1 and is told the file wins over its own instinct on any recurring term. A video that renames a
concept halfway through is worse than one that names it slightly awkwardly throughout. The price is
a serial chain per video — videos still run concurrently, so a queue does not pay it, a single long
video does.

**Rejected: a second chunking rule.** `plan_chunks` is imported from `build_clean.py` (route E)
rather than re-derived. Two copies of a boundary rule that must agree with itself is how the
planner and the join come to name files nobody wrote.

`DEFAULT_CHUNK = 400` is labelled in code as a HYPOTHESIS off one measurement, not a constant: it
sits ~4× under the observed ceiling with the whole-transcript read removed as well. Re-site it once
a wave of long videos exists.

One thing this cost, worth recording because it nearly shipped: the join was written with a fourth
coverage check (`is every sentence in some chunk`), it went green, and a mutation showed the test
covering it was passing for another reason entirely — the guard was unreachable, since `plan_chunks`
covers `0..n-1` by construction and `build()` re-validates the assembled draft anyway. Deleted, and
its one useful sentence (a repair renumbers ids, so the cut moves) folded into the missing-file
message, which is where that failure actually surfaces.

## 2026-08-03 — route D is DELETED and route C stops assessing; one route answers "what is in it"

Two routes were converging on one question and neither was allowed to answer it plainly. Route C
asked "does this earn an evening" and answered with a grade; route D asked "what is actually in
it" and answered with a document, at ~200k tokens per video across two Opus passes. The user's
call: keep ONE route, make it route C, and have it answer route D's question briefly.

**Route D is gone, not deprecated.** `overdub-digest/SKILL.md`, `digest-videos.js`,
`build_digest.py`, `digest_report.py`, `test_digest.py` and `docs/digest-reference.md` are
deleted. The two 07-30 entries below stay: what they RECORD — that a composing agent cannot be
given a length, and that the caps deleted the marginal finding first — is a lesson about prompting
under a length target, not a fact about a route. The measurements in them describe a route that no
longer exists, so nothing in them is a live number.

**Route C assesses nothing.** No `quality`, no closed vocabulary, no grade chip, no colour ladder,
no "стоит посмотреть" in the artifacts, on the page or in chat. `scout.draft.json` is
`{one_liner, highlight, paragraph}`, `build_scout.py` validates prose and nothing else, and the
page's header counts STATES (`отсканировано: N`) instead of verdicts.

**The precedent this closes.** Route C shipped a verdict twice and retired it twice: the personal
`watch`/`maybe`/`skip` collapsed toward "no" (0/1/9 on the first real queue, 07-20 below), and the
material grade that replaced it scored videos nobody asked to have scored. The 07-20 entry stays
as the record of the first retirement; this one records that the second axis went the same way,
for a related reason — a route that describes can be argued with, a route that ranks decides for
the reader.

**A finished row now carries no chip.** That is route D's own design rule (07-30 below: "a badge
on every row would be a column of one value") inherited by the surviving route. Chips are reserved
for states that demand an action — dub triage, and the unfinished-pipeline states.

**Two things deliberately NOT done.** Route E was not renumbered into the free letter D: "route E"
is load-bearing in its skill, the queue contract and `build_clean.py`, and a rename buys a
tidier alphabet for a real risk of drift. And existing `scout.json` files keep their `quality`
key — nothing migrates them, nothing reads it, a rebuild drops it, exactly as the `author` key
was handled earlier today.

Tests: `test_digest.py` deleted (-52). `test_unknown_quality_is_fatal` and
`test_the_grade_is_about_the_material_not_the_reader` are replaced by
`test_the_route_assesses_nothing` (which keeps the `_AUTHOR` / `_VERDICTS` tombstones and adds
`_QUALITY` to them) and `test_an_assessment_field_in_the_draft_is_ignored_not_persisted`. The
entry below names the older test by its old name; that is the file's normal drift, not an error
in it.

## 2026-08-03 — the viewer profile is REMOVED; scout grades the material and nothing else

`.claude/viewer-profile.md` and everything that read it are gone: the S0 preflight in the
`overdub-scout` skill, the `viewer-profile-prompt.md` reference that built the file, the
MANDATORY-FIRST-READ block and `PROFILE-MISSING` abort in `.claude/workflows/scout-summarize.js`,
and the `.gitignore` rule that kept the file out of the repo.

**What scout loses.** The profile was the only thing that made `highlight` answer "interesting to
THIS reader" rather than "interesting". Nothing replaces it — that was the decision, not an
oversight. Scout is now a pure assessment of the material on the three axes it already owned
(substance, currency, delivery), and the write-up is the same for everyone who runs it.

**The `author` axis died with it.** `trusted`/`new` existed solely to match a channel against the
profile's trusted-author list. With no list there is nothing to compare against, so `_AUTHOR` and
its clamp are out of `build_scout.py`, the `a-trust` marker and CSS are out of `scout_report.py`,
and the key is out of the summarizer prompt. `test_the_grade_is_about_the_material_not_the_reader`
now asserts `not hasattr(build_scout, "_AUTHOR")` alongside the older tombstones, so a
reintroduction fails loudly rather than quietly rendering a column of one value.

**Existing `scout.json` files keep their `author` key.** Nothing migrates them and nothing reads
it — the renderer simply ignores an unknown key. A rebuild drops it.

The 2026-07-20 entry below stays: it records why the verdict vocabulary became a grade, which is
still the live design and is the reason removing the profile costs as little as it does. Had scout
still shipped a personal `watch`/`maybe`/`skip`, this removal would have gutted it.

Suite: 641 → 639 (2 author tests removed, 1 assertion added).

## 2026-08-03 — `.claude/CHANGELOG.md` is RETIRED; measurements retire HERE instead

2204 lines of append-only history in which every entry restated a commit. What the file uniquely
carried — the batch stage-shares and the whole-pipeline RTF pair — was already marked void in PLAN
"Numbers to re-measure" (B) and (C), so retiring it lost nothing that was still true. Shipped work
is read from git history now, and `CLAUDE.md` says so where the artifact list used to be.

**This merges two of the four artifact roles, deliberately.** PLAN used to retire measurements to
CHANGELOG and rationale here; it now retires both here. The global framework calls role-mixing an
antipattern and is right about the usual case — but the property that made CHANGELOG worth keeping
is that its entries are DATED records of what was true when written, and this file already has it
(2026-07-22, the named-not-numbered entry: DECISIONS keeps its numbers precisely because rewriting
them would destroy that provenance). A separate file bought ordering and nothing else, against a
second place to look and a second place to drift.

**What it costs.** Every "CHANGELOG <date>" pointer degraded to a bare date when it was retargeted.
The date still works as a `git log --since/--until` key, but the reader has to know that — do not
add another one. And the GLOBAL `/summarize` command and the `project-artifacts` skill still route
shipped work to `.claude/CHANGELOG.md` unconditionally; neither knows a project can opt out. When
one offers to write the file, the answer is no: this repo's `CLAUDE.md` outranks both.

## 2026-08-01 — entity_loss DELETED, not demoted again

The detector flagged a Titlecase Latin token present in `src_en` and absent as a substring from
`text_ru`. It had already been advisory since the AI-Fluency batch (11 of 12 videos marked), so it
cost nothing in `needs_triage`. It is now gone from the code.

Measured on the 19-video batch of this date: **1179 flagged sentences, 654 distinct missing
tokens.** The user inspected the fires by hand (`work/entity_loss_review.txt`) and found the
translation correct in every case examined — 0 real losses.

Two things decided it, and the second is why demotion was not enough a second time:

1. **The test cannot be right about its own dominant input class.** The translation prompt PERMITS
   Russifying personal names, and a transliterated-and-declined name can never substring-match:
   `Ralf Koster` → «Рафа Костера», `Mihaly Csikszentmihalyi` → «Михая Чиксентмихайи». Both correct,
   both flagged. This is not a threshold to tune — it is the mechanism. A cheap filler stoplist
   (`Right` 61, `Thank` 38, `God` 21, `Mm`/`Um`/`Uh` 46 …) was measured at the SENTENCE grain and
   silences only 244 of 1179 (20.7%); the surviving 935 are person names with a long tail of 405
   tokens seen exactly once — the shape of a name list, not of a tunable signal.
2. **An advisory flag is not free.** It still costs a line in every offenders list and an embedded
   audio player on the listen page: `scout_report.py` embedded 1186 units and produced a 2012 MB
   `work/scout-report.html` that no browser opens. 1179 of those 1186 were this detector. The
   capability the page exists for — actually LISTENING to a flagged unit — was lost silently, with
   the script exiting 0.

Deleting the code does NOT destroy the series that would allow re-promotion: 19 `report.json` files
on disk keep `n_entity_loss` and the per-sentence flags, `work/entity_loss_review.txt` keeps every
instance with its EN/RU pair, and git keeps the implementation.

**The flag NAME stays in `_ADVISORY_COMPLETENESS` as a tombstone.** That set is subtractive
(`flags - _ADVISORY_COMPLETENESS`), so removing the name would promote a dead flag to ACTIONABLE
and light up `needs_triage` on every historical workdir. Found by the test written for exactly that
case, not by reasoning — see `test_legacy_report_with_entity_loss_still_reads`.

Do not reintroduce a substring test in `completeness.py`. A future entity detector needs a
person-vs-brand discriminator or a transliteration-aware match; neither is a threshold change.

Suite: 633 → 627 (8 entity tests removed, 2 added).

## 2026-07-30 — route D digests in TWO passes, because a composing agent cannot be given a length

Three runs over one video (`fGKNUvivvnc`, 59 min, 691 sentences, the source of the reference digest
the format was taken from). Same transcript every time; the only variable was how brevity was asked
for. Document size counts the five prose fields:

```
pass structure          brevity instruction        chars   points   cap truncations
single                  "1-3 sentences"           11,266     7            10
single                  "up to ~450 characters"   11,591     9            12
read + compress         "cut to a third of this"   4,041     5             0
```

**A character budget in a composing prompt does not bind: +3% against a predicted −70%.** The
mechanism is mechanical, not motivational — a model cannot count characters in output it has not
produced yet, and the budget line sits beside a concrete, actionable instruction in the same prompt
("put the mechanism, the number, the example, the counter-argument in each point"). The actionable
one wins. Replacing sentence counts with character budgets swapped one weak lever for another and
made the count worse (7 → 9 points).

**Then the caps did exactly the damage the length fight was supposed to prevent.** On the second run
a truncation deleted the «plan A / plan B» framing out of the tail of one point — the one finding of
the reference digest that the first run had missed entirely. A cap is not a style guard: it deletes
content, and because the concrete anchor usually sits at the END of a sentence, it deletes the
marginal finding first. Any "shave every field to fit" scheme has this property.

**Adopted: pass 1 optimises coverage with no length pressure, pass 2 owns the fit.** Compression is a
different task from composition — the editor HOLDS the text, so "cut this to a third" is arithmetic it
can perform rather than a guess about unwritten output. Measured on three videos of 8, 59 and 59
minutes: **2.87× / 2.88× / 2.89×**, spread 0.02, every field inside its cap, zero truncations, points
9→5 / 6→4 / 7→4 (all inside the duration ceiling), every surviving timestamp preserved — and the
«plan A / plan B» anchor kept in a point compressed 953 → 431 chars, i.e. exactly what the blind cap
had thrown away.

**The compressor is denied the transcript on purpose.** It reads only `digest.long.json`, so it can
lose material but cannot introduce any — a property that is checkable rather than merely instructed.
The cut ORDER is the load-bearing half of its prompt: whole overlapping points first, then framing and
hedging, then prose inside a point, and the concrete anchor last.

**Costs, named.** ~2× tokens per video (measured: ~100k read + ~107k compress on the 59-minute
reference). The read pass and the compress pass are cached SEPARATELY (`digest.long.json` /
`digest.draft.json`, two resume lists, `ids` vs `compressOnly`) precisely because the expensive half
must never be re-paid for a compressor tweak — on this pilot all three videos were re-compressed
against existing long drafts, with zero re-reads. `digest.long.json` is never deleted: diffing it
against the draft is the only way to see what compression cost, and it is what made this measurement
possible at all.

**The ratio is NOT a knob either, and the point count is.** Second round of measurement, same day,
after the read pass was freed of length pressure and started producing 19.6k chars for a 90-minute
video:

```
instruction to the compressor        result
"cut to one third"                   2.78x  2.85x  2.87x  2.88x  2.89x   (five videos, 5.7k-11.6k in)
"cut to one fifth"                   2.99x                               (same video, same 19.6k in)
point ceiling (4 / 6 / 8 by runtime) 11->6  9->5  7->4  6->4  5->3       (obeyed exactly, every run)
```

~2.9× is this edit task's own compression rate; the one-third instruction coincided with it, which is
why it looked like control. Ask for a fifth and you get a third. **What is obeyed literally is the
COUNTABLE STRUCTURAL instruction — the number of points — in five runs out of five.** So the size of
the page is governed by the ladder, and per-field character numbers are aspirations that push in the
right direction and settle nothing.

**Consequence, adopted: `_POINT_TEXT_MAX` is 900, above what the model writes, not at what we asked
for (450).** A cap set at the aspiration enforces style by DELETING CONTENT — that is the «plan A /
plan B» loss above, and it is not a trade worth making at any density. The cap goes back to catching a
runaway (a 3000-char "point"). The false tier ("over 12k input → cut to a fifth") was removed from the
compressor prompt rather than left in as decoration: an instruction that does not bind teaches the
next reader that it does.

**Where that leaves the sizes** (five videos, 2.9 to 90 minutes): 2,042 / 2,374 / 3,393 / 4,041 /
6,551 chars, i.e. 1.5-5 minutes of reading against 3-90 minutes of video, and monotone in runtime. The
reference document's ~2,000 for an hour is NOT reachable this way and is not being chased further: it
was written as a chat message, while this is a card on a page, and a 200-char bullet cannot answer
"did I miss anything" about an hour of material. **The one remaining lever that would work is lowering
the ladder for long videos (6 → 4 above an hour), and it costs coverage** — 11 real topics into 4
points. That is a user decision, one constant wide (`_POINTS_LADDER`), deliberately not taken here.

## 2026-07-30 — the digest is a SEPARATE route with a separate page, and it grades nothing

Route C's grade answers "does this earn an evening". A digest answers "what is in it" — and the two
were briefly one idea, so here is why they are not.

**A verdict and a retelling cannot share a page.** Put them side by side and every row asks the
reader which question they came for; worse, a grade next to a retelling reads as the retelling's
verdict, so the digest inherits an authority it did not earn. The scout page is scanned (six columns,
one row per video, a chip to sort your evening by); the digest page is READ (a document per video).
Merging them would also have forced one order to serve both jobs. So: `work/digest-report.html`,
its own fields, and route C untouched.

**No verdict field anywhere in route D, on purpose.** Not `quality`, not watch/skip, no ranking, and
the page never sorts. The one field that looks like advice — «Стоит смотреть, если» — is deliberately
an INVENTORY of what stayed in the video (the argument between two positions, a demo, code on screen,
tone) rather than a recommendation. The moment it becomes advice this route is a worse copy of route
C: it would be a personal verdict again, which is the thing 2026-07-20 already reversed once, and it
would collapse toward "no" for the same reason.

**Opus, where route C uses Sonnet.** A grade is a short judgement over a transcript and Sonnet is
measured as sufficient for it. A digest has to hold an hour of argument at once, decide what the
shape of it is, and choose which four to eight things earn a line — a harder job, and the one place
in this pipeline where the model choice shows up directly in the deliverable rather than in a number.
Set explicitly in the workflow: an inherited session model makes two runs of one queue incomparable.

**Points scale with the material (3-4 / 5-6 / 6-8 by runtime), and the band only warns.** A fixed
length was the alternative and it is worse in both directions: on a 20-minute tutorial it pads, and
on a three-hour panel it silently drops topics — which is the exact failure "did I miss anything" is
asked to protect against, made invisible. Since the count is editorial, `build_digest` warns outside
the band and refuses only at 20 (a transcript pasted back as bullets).

**Timestamps are collected because they can be CHECKED.** `at` is optional navigation, but it also
turns two failures into measurements the build script can catch: a marker past the end of the video
is a fabrication (dropped and said out loud), and a last marker inside the first 60% of the runtime
says the agent read the opening and stopped. Nothing else on the page can detect a front-loaded
digest — it looks complete, because it is complete about the part it read.

**Accepted costs, named rather than dismissed.** (1) `digest.draft.json` / `digest.json` / `digest.md`
are NOT in `invalidate_downstream`, exactly like `scout.json`: the staleness mechanism is D2's mtime
filter, which means a transcript repaired on the local Gemma route leaves a stale digest on disk until
the next D2 pass over that queue. Adding them to the target list would make the pipeline own a route-D
artifact and is a separate change with its own rationale. (2) The digest page reuses
`queueview.collect_entries`, so a queue of dubbed videos builds run rollups this page ignores — one
queue walk with one drop policy was worth more than saving that work. (3) `digest.md` duplicates the
page's content by construction; it is DERIVED from the same JSON in one deterministic function, which
is what keeps it from being a second version rather than a second format.

## 2026-07-28 — route B step 2 fans out through a Workflow: hand fan-out spends the orchestrator's context TWICE per video

The 117-video batch of 2026-07-27 finished its dubs and killed its orchestrator: context went
60k → 893k tokens (89% of a 1M window), step 4 never ran, and **84 of 117 summaries were never
written** — silently, because a context ceiling produces no FAIL row and no missing-artifact gate
fires on an informational file. Attribution over that transcript (`c9a89f27`, 1.75 M chars of
messages):

```
Agent prompts (108 spawns)        460,198 chars   26.3%   <- 87 translators, 403,364 of it
inbound teammate reports          422,373 chars   24.1%   <- mean 2.4k, worst 13,547
SendMessage to agents (40)         92,460 chars    5.3%
ALL tool_result (pipeline output) 185,816 chars   10.6%
```

**The 30 hours of video cost ~10% of the window; talking about them cost ~62%.** The mechanism is
not obvious and is the whole reason this is written down: a sub-agent isolates its OWN context, but
its prompt and its final report stay in the orchestrator's history **forever**. Fan-out by hand
therefore makes the orchestrator pay twice per video (~9.6k tokens) rather than not at all —
delegation that costs more than doing the work inline. The cost is strictly linear in queue length
against a constant window, so the ceiling (~95 videos) was arithmetic, not bad luck.

**Adopted: `.claude/workflows/translate-batch.js`, one call per resume-filtered queue.** Agent
results return to the SCRIPT, not to the model's context. Route C had already proved the pattern at
S2 and measured the second half of the bill — prompts generate at ~8.5 s per 1000 chars, so 403k
chars of translator prompt is ~57 min of pure typing per batch — and proved that wording cannot fix
it (an orchestrator reasoned "spawning six sub-agents in a single message", announced it, emitted
six messages anyway). Projected saving on the same batch: **~350k tokens, 39% of the window**;
per-spawn cost 9.6k → 5.6k; ceiling ~95 → ~165 videos.

**It does NOT make the cost constant** and must not be sold as such. What remains is the per-video
PowerShell checks, ad-hoc investigation agents (10 of the 108 spawns, and the right tool for a
one-off finding), and the orchestrator's own reasoning — ~5.6k tokens per video. Steps 1/3/4 were
left alone.

**Carried over from route C, with the reasoning intact rather than the code:** the prompt lives in
the script; the contract is READ off disk by the agent (9.1k chars/spawn) under a mandatory-read
rule with a `CONTRACT-MISSING` stop marker instead of a silent fallback; the agent's final text is
a STATUS LINE and the script `.slice(0,200)`s it anyway, because on 2026-07-27 the same instruction
produced a 13.5k-char essay about nine edited lines; the return value is a worklist by id; a
`translate.started` marker makes the fan-out verifiable from the filesystem rather than from the
run's account; and an empty `ids` throws instead of reporting success.

**Two things deliberately NOT carried over.** *Per-video timing in the report*: route C's
`build_scout.py` consumes `scout.started`, but the route-B equivalent would need a new artifact,
changes to `build_translation.py` and `run_report.py`, and their tests — for a number no surface
reads today. The marker is written and used only as the fan-out check. *A validate-and-retry loop
inside the workflow*: a workflow script has no filesystem or shell access, so `build_translation.py`
cannot run from it. The retry is three-beat instead — the agent verifies its own draft before
answering, the skill runs the helper after the workflow returns, and a second workflow call takes
whatever did not land.

**New, from measurement rather than from route C:** `Read` returns 2000 lines by default and 28 of
152 `sentences.json` files exceed it (largest 5930 lines / 988 sentences), so a naive read hands the
translator the first third of the video with no warning at all. This is the likeliest explanation
for 87 translator spawns over a 117-video queue: `build_translation.py`'s missing-id exit caught the
truncation and each catch cost a full respawn. The workflow prompt now requires reading on to the
last id and self-verifying coverage before answering.

**Confirmed on the first run, same day** (5-video queue, 2026-07-28): markers 3.5 s apart,
782/782 on a 4694-line transcript, `src` on 100% of records, step 2 costing the orchestrator 1428
chars. **The ~350k / ~5.6k-per-video projection above is NOT yet measured** — at four videos the
session is dominated by steps 1/3/4 and by manual debugging, so it stays a projection until an
ordinary batch re-measures it. What the run did establish is narrower and still worth having: the
share of the orchestrator's own traffic spent on step 2 went from 62% to 0.7%.

**And it revalidated the guard-porting decision twice in one run.** The caller passed `args` as a
STRING — route C's measured 8-of-8 mistake, reproduced on route B's first call — and the ported
parsing branch absorbed it. Then the one defect the run DID surface was in the part with no route-C
precedent: a status line parsed from the TRUNCATED answer with an anchored pattern. The general
lesson is why it earns an entry at all: **a cap that protects context must not also be the parse
window.** Truncation is a storage decision; classification has to read what actually arrived.

## 2026-07-28 — the tail degrades instead of failing: a missing translation or dub costs a TRACK, not the artifact

`mux` used to require four inputs (`source.mkv`, `dub_ru.wav`, `en.srt`, `ru.srt`) and raise
`mux input missing` on any of them; `assemble` read `translation.json` unguarded and raised on a
missing manifest. So a video whose translate or synthesize died produced **nothing** — the download
and the large-v3 transcribe were already paid for, and the run ended with an empty `out/` row.

**The rule adopted: a MISSING artifact degrades, an INCONSISTENT one still raises.** Missing means
"a stage upstream did not produce this" — degrade, announce, record. Inconsistent means "the
artifacts on disk disagree with each other" (non-contiguous ids, units that do not cover the ids, a
dub with no manifest to source its unit spans from, `dub_mix=bed` with no bed): those still raise,
because the never-drop invariants exist to stop a confidently WRONG dub, and losing a track is a
reportable outcome while shipping a mis-mixed one is not.

Concretely: `assemble` with no `translation.json` writes `en.srt` off `sentences.json`; with no
manifest it writes both srt tracks off `translation.json`'s SOURCE timings (there is no placement to
time cues against when there is no audio); neither builds a dub, both stamp `assemble.degraded`.
`mux` requires `source.mkv` alone and ships whatever else exists.

**Three sub-decisions that are not obvious:**

*The export name is UNCHANGED* (user decision). A dub-less MKV lands in `out/` as
`"<title> [<id>].mkv"`, indistinguishable from a real dub by name. The compensation is that the
degradation must be loud everywhere else: a `[warn] mux: DEGRADED` line, `mux.tracks` in
`report.json`, `assemble.degraded` + `mux.tracks` + a top-level `degraded` in `run.json`, and
`needs_triage` forced true — the first case where triage is decided by a property of the CONTAINER
rather than by a flag count. The alternative (a `(no dub)` marker in the filename) was rejected as
churn in a directory the operator sorts by title.

*The re-mux trigger is UPGRADE-ONLY.* `mux.done()` re-runs when a track has APPEARED since the
stamp, never when one has vanished. Symmetric would be wrong twice over: `work/<id>/` cleanup
deletes binaries after a successful mux (PLAN), and a hardlinked `work-exp/` baseline can arrive
with an mtime OLDER than `output.mkv` — the mtime check cannot see that one, which is why the
`tracks` stamp exists beside it rather than instead of it.

*`_write_srt` leaves an identical file untouched.* The degraded branch has no done() gate of its own
(the gate is the dub, which does not exist), so it re-runs on every resume. Rewriting the same bytes
would trip mux's make-style freshness check and re-encode a multi-GB container once per resume,
forever.

**Known boundary, stated rather than papered over.** Under the stage-major batch driver a stage that
RAISES marks the job `FAIL` and drops it from every later stage, so a translate crash (Ollama down)
still yields no MKV in that run — the degradation is reached by `--only assemble mux`, by
`--video-major`, or whenever the tail runs at all. Making the driver carry failed jobs into the tail
was considered and declined: it would turn a real TTS failure into an `ok` row with a silently empty
dub, which is the failure class this repo forbids.

## 2026-07-27 — `neg_loss` is demoted to advisory; the 2026-07-19 carve-out is paid off with a number

DECISIONS 2026-07-19 kept `neg_loss` actionable BY NAME, against the module's prefer-miss default,
at a stated price: *"an inverted negation is the most dangerous silent loss there is, and one false
positive per batch is a fair price for never missing one."* The price is now measured and it is not
one per batch.

**24 inspected fires, 0 real.** 19 on the 24-video batch of 2026-07-19 (all correct translations
carrying the negation lexically — "Hell no" → "Чёрта с два", "no matter what" → "вне зависимости
от"), 2 on the 7-video Silero batch of 2026-07-26, 3 on the 5-video batch the same day ("Nothing
except humans have talked" → "говорить умели только люди", "not widely known" → "малоизвестных",
"doesn't align properly" → "всё съезжает"). 27 fires exist across the 47 workdirs on disk, so 3
were never inspected — the inspected series and the corpus count are different populations and must
not be quoted as one number.

**What decided it was not the count but WHOSE list it was authoring.** Re-scored both 2026-07-26
batches against the shipped `_ADVISORY_COMPLETENESS` (the constant itself, not a copy of its logic):

| | was `needs_triage` | after | sole actionable flag on the difference |
|---|---|---|---|
| batch 1 (7 videos) | 2 | **0** | `neg_loss` on both |
| batch 2 (5 videos) | 4 | **1** | `neg_loss` on three of the four |

The one survivor is `NGOAUJtdk-4`, and it survives on 2 verify `low_similarity` units — a real
defect the flag had been sharing a list with. The user then listened to both batches and found them
fine, which is the same verdict arriving through the only instrument that actually adjudicates
this. A detector that marks 6 of 12 videos and is wrong every time is the `entity_loss` failure
(11 of 12) with a different name.

**Demoted, not deleted, and both halves are load-bearing.** `n_neg_loss` still prints, the offenders
list still names it, `flags_total` still counts it — because the only argument that could ever
re-promote it is the same series that demoted it, and a flag whose count stops appearing cannot
produce one. The DETECTOR keeps its prefer-fire stance too (`_NEG_POSITIVE_STEMS` stays): blunting
it would destroy the evidence rather than the noise.

**What would reopen this:** one confirmed inverted negation reaching a finished dub. That is a
single counter-example, not a rate — the 2026-07-19 argument about severity was never wrong, it
was just never paid for by this detector.

## 2026-07-26 — a mis-heard PRODUCT NAME is not sentence damage, and the contract had no rule for it

Found on the 5-video "Test 2" route-B batch. `vLIDHi-1PVU` is an Anthropic interview titled
*Designing Claude Code*, and whisper (large-v3, fp16, beam 5 — the shipped config, not beam 1)
heard **"Cloud" 16 times and "Claude" zero times**: `Cloud Code`, `Cloud Relations`, `cloud .ai`,
`cloud .md`, "multiple clouds". `02nFRuEo0bc` had the same slip once against 6 correct. So this is
the DECISIONS 2026-07-20 proper-noun class firing at the shipped beam, not only at beam 1.

**Two sub-agents, one class, opposite calls — and both were defensible.** `02nFRuEo0bc` translated
the literal "Cloud" and set `src=context_contradiction` (rule 8: translate as-is, report).
`vLIDHi-1PVU` normalised it to Claude across 35 records and marked them all `ok` (rule 5: brand
names are written the standard way, `runescape` → `RuneScape`). **Rules 5 and 8 collide on a
mis-HEARD name and the contract says which one wins nowhere.** That is the finding; the batch is
just where it surfaced.

**Decision — normalise the spelling, and flag every record you normalise.** The dub says the
product's real name (dubbing "Клауд Код" 35 times is a worse artifact than the transcript is a
damaged one), and `src` still carries the signal that the English was wrong. Both halves are
required: the fix without the flag is exactly the laundering DECISIONS 2026-07-19 exists to
prevent — a translation that reads perfectly, a `src` column of all-`ok`, and no surviving trace
that the source was damaged. As shipped here the second half took a second pass: the agent
reported the call in prose to the orchestrator (good) but wrote `ok` to disk (not good), and the
prose is not an artifact anything downstream reads.

**What it costs, measured, not estimated:**
- **27 of 28 `entity_loss` offenders on that video are now false**, caused by the fix itself — the
  detector finds "Cloud" in `src_en`, does not find it in `text_ru`, and calls it a lost entity.
  All advisory, `needs_triage` unmoved. A file-wide name normalisation will always read as mass
  entity loss; do not treat that count as a quality signal.
- **The finished MKV disagrees with itself.** `en.srt` is deliberately NOT re-timed and transcribes
  the original English track (`assemble.py:199`), so it keeps the defect: 15 × "Cloud" in `en.srt`
  against 35 × "Claude" in `ru.srt`, in one container. Normalising at the translate seam cannot
  reach the English side by construction.

**Therefore the real fix is upstream, at ASR, and it is NOT this decision.** `model.transcribe`
passes neither `initial_prompt` nor `hotwords` (`stages/transcribe.py:385`) — a name list would
close the class before translate, synthesis and both subtitle tracks. It changes source text, so
it belongs in `asr_key` beside the beam, and it must be measured on the six fixtures via
`asr_probe.py --variant` rather than adopted because it sounds right. PLAN carries it.

## 2026-07-25 — session retrospective: three times the arithmetic was right and the SHAPE was wrong

Trimmed 2026-08-03: the generalised half went to the knowledge file below. The three cases and
their outcomes stay.

The pattern repeated three times in one session, in three different layers, and only once was it
caught by the person who made it.

**The generalised lesson has been promoted to `~/.claude/knowledge/measurement-discipline.md`** —
grain, distribution-vs-total, provenance, "docs go stale by NUMBER not only by name", and the rule
that a mutation harness must score a collection error as INVALID rather than caught. None of it is
specific to this project, and that file loads in every session while this one does not. Do not
restate it here; what stays is what the session decided in overdub.

**1. Item 1(b), the pre-synthesis bar — NOT BUILT.** Premise: "17 units ship at cf ≥ 1.8, up to
×12.5, silently". Recomputed before writing code: 7 units of 3575, worst 2.63. The 17 mixed a
sentence-row count with a unit count, the ×12.5 was one sentence's pre-repair figure, "silently"
was false (three surfaces already print it), and all 36 workdirs were F5 at the old grouping — a
corpus describing a different engine than the one being fixed.

**2. Item 1(a), the slot fit — DEMOTED from blocker to polish.** Premise: "the translation is ~29%
too short, so make the translator write longer". The hole was DISTRIBUTED — many units each missing
a little — which a uniform multiplier answers far better than per-sentence length work. A floor on
`atempo` closed 70% of the silence in the assembly layer, with no prompt change and no
re-translation.

**3. The listening test for that floor — REDONE, verdict moved 0.85 → 0.75**, worth 79 seconds of
silence, twice the effect. A floor only binds units below it, so the 45 s window offered held two
units, one of which never reached the floor. Caught by the USER, who proposed the fix: one phrase,
four tempos, back to back. Full entry below, same date.

**One project defect worth its own line:** adversarial review found a shipped subtitle regression
(tail fragments opening 10.6 s after their audio) that the author's own verification missed —
the author measured cue DURATIONS and the defect was in cue DELAY.

## 2026-07-25 — `atempo_floor = 0.75`, and the listening test that produced it was the second one

Under-filled units are now stretched toward their slot, bounded by a floor. The floor is an EAR
number and the first attempt to obtain it was a bad test — worth recording, because the failure
mode will recur with any per-unit knob.

**The bad test:** a 45 s window of finished dub, assembled at each candidate floor, offered for
A/B. Everything sounded fine at every floor, and the user said so while adding that the test
looked wrong. It was. A floor only binds units whose own fill falls BELOW it, so it is not a
uniform slowdown — and that window held exactly TWO units (fill 0.67 and 0.79), one of which never
reached the floor at all. Most of the 45 s was the silence being measured. The test could not have
shown degradation if there had been any.

**The good test, proposed by the user:** one phrase, slowed to 100 / 80 / 65 / 50 %, back to back,
so the only variable is the factor. Three units, 17-18 s of natural speech each, 340-380 chars.
Verdict: degradation begins at the 0.65 step, consistent across all three. The default is set half
a step above the edge at **0.75**, not on it — other voices and other material will eat some of
that margin, and the knob is per-config so a specific run can go lower deliberately.

**What it buys, measured on `8zJlKmgMT44`** (assemble only, no re-synthesis): slot silence
283 → 84 s, a 70% cut, with 42 of 69 units pinned at the floor. The full curve: 0.85 → 163 s
(56 pinned), 0.80 → 123 s (50), 0.75 → 84 s (42), 0.70 → 50 s (29). Returns fall off below 0.70
because the remaining units stretch only to their own fill, not to the floor. The dub's duration
is IDENTICAL at every floor (1058.848 s) — stretching lives strictly inside a unit's slot, so
picture sync is untouched whatever the value.

**The consequence for the roadmap: item 1(a) stops being the blocker.** It existed to close 283 s
of holes; the floor closes 70% of that in the assembly layer, with no prompt change, no
re-translation and no re-synthesis. Sizing the translation to the slot is now a polish step that
removes the residue and the audible stretch — worth doing, not worth the risk of rushing, and that
risk is real (the `runaway` gate, four hand-synced copies of the length rule, and a resume key
that keeps a translation sized for a slot that `--repair-asr` has since changed).

**Why the effect exceeded the estimate.** The hole was assumed to be "the translation is ~29% too
short" and was actually DISTRIBUTED — many units each missing a little. A uniform multiplier
answers that shape far better than per-sentence length work does. The same error of form appeared
in item 1(b), whose numbers described a different population than the one being fixed: in both
cases the arithmetic was fine and the SHAPE of the problem was wrong.

## 2026-07-25 — what this repo produces is a TOOL; an individual video is never the deliverable

User framing, recorded because it is a work-selection criterion and not a mood: the repository is
building a pipeline, so **fixing a single video has no value in itself.** A defect in a shipped MKV
is an input signal about the tool — the correct response is to find the CLASS, fix the pipeline, and
let the next batch come out right. The video that exposed it stays broken, and that is not a debt.

**What this rules out**, concretely: re-running, re-repairing, re-translating or re-synthesizing a
finished video in order to improve THAT video; hand-patching a bad unit; "while I'm here" fixes to
artifacts in `work/`. What it does NOT rule out is the same operation performed for a MEASUREMENT
that generalizes. The distinction is not the action, it is what comes back. The 2026-07-25 repair of
the two worst videos was correct under this rule and would have been wrong under a slightly
different one: it returned atempo max 12.52 → 2.04 and 5.38 → 2.40, i.e. the evidence that Step 1b
belongs in the runbook — the two improved MKVs are a by-product nobody needed. Had the same work
been done because those two videos were the ones being watched, it would have been waste.

**Consequences that follow directly and are already in PLAN.** (1) Intermediate artifacts are
consumables, which is the argument for deleting `work/<id>/` binaries after mux (18.5 of 18.7 GB) —
re-synthesis is cheap next to disk bounding the queue size. (2) Anything that persists a
GENERALIZABLE finding outranks the videos: the golden fixture, the six `_pre-repair-*.json` pairs,
the `work-exp/` baselines. `work-exp/` has already lost three baseline sets to a cleanup while the
videos survived — exactly the wrong direction, and the reason the disk decision needs making before
the next cleanup makes it. (3) An ear check is a measurement, so listening is never the thing this
rule prohibits.

**Where the tension will show up.** A batch is also how the tool is judged, so "the batch shipped 24
watchable videos" reads like success and can quietly become the goal. The check is to ask what the
run RETURNED: a number, a flag distribution, a verdict, a fixture. A run that returns only artifacts
was a production run, and this repo does not do production runs yet.

## 2026-07-25 (later) — the Silero switch is ear-confirmed on finished videos, not just on clips

User verdict after listening to finished MKVs produced on the new engine: **quality is sufficient.**
This is what the switch was still owed. The engine decision itself was made on speed and hardware
cost with the quality difference accepted as a deliberate trade (entry below), and every ear check
supporting it until now was on bake-off clips and A/B arms — not on a shipped video end to end. The
trade is now verified where it is actually consumed.

What this does NOT close: the slot holes. Silero fills the median slot to 0.73 and leaves 267 s of
silence on `8zJlKmgMT44` — a TIMING defect, audible as pacing rather than as voice quality, and it
stays the open blocker (PLAN item 1). "The voice is good enough" and "the dub has holes in it" are
compatible statements about the same file; do not let this verdict be quoted against that item.

## 2026-07-25 — Silero becomes the ONLY engine; four Silero-shaped fixes land, one is rejected by ear

User decision: F5/ESpeech is replaced by Silero v5_5_ru outright, on speed and hardware cost, with
the quality difference accepted as a deliberate trade. Explicitly NOT a parallel-engine setup —
per-engine knobs were considered and declined; the shipped defaults are tuned for Silero and the F5
path comes back out of git history if the switch fails. This reverses the 2026-07-16 ear verdict
that made F5 production and Silero fallback.

**Vocoder hiss → `dub_lowpass_hz = 11000`, applied once to the finished track.** The complaint was
"шипение". Measured on `bakeoff/silero_v5_eugene/id147_long.wav` (the bake-off tree, deleted
2026-08-03 — cf75c07 has it): the sibilant band sits 19.9 dB
under the body, *quieter* relative to F5's 15.4 dB — so it was never sibilance, and `deesser` did
nothing. The spectrogram shows the real thing: a broadband noise carpet across 8-20 kHz, present on
vowels, without harmonic structure, and *absent in the pauses* — i.e. vocoder noise that tracks the
speech. That last fact is what rules out `afftdn`/`arnndn`/`anlmdn`: they remove a stationary floor,
and this is not one. Cutting the top removes it at no intelligibility cost (confirmed by ear, A/B).
Placement is deliberate: ONE pass over the whole dub in `assemble`, after verify, not folded into
the per-unit atempo call — that call only runs for units with `factor > 1.0`, so a per-unit filter
would leave un-sped units unfiltered and put a tembre step at those seams. It is out of `synth_key`
(post-verify, no resynthesis) but inside the assemble gate, and auto-skips when the cutoff is not
comfortably below Nyquist, so an F5 run at 24 kHz is never silently recoloured.

**Grouping re-cut 0.4/12/300 → 1.2/20/600 by ear.** `_GROUP_MAX_SPAN`/`_GROUP_MAX_CHARS` were
constants shaped for F5 ("~10 s ref + gen inside F5's trained ≤30 s regime") and they, not
`group_gap_max`, were what bound grouping: over 37 videos / 5401 sentences, raising the gap alone
0.4→1.2 moves 1.40→1.57 sentences per unit because refusals migrate to `span` (1822→2997). Now
config knobs. The 2.0/30/900 arm was also better than baseline but barely different from 1.2/20/600
while doubling the sync cost (p90 swallowed silence 2.62 s vs 1.28), so the middle arm won.
Grouping costs nothing in time — see the measurement note below.

**`<break>` restoration: built, measured, REJECTED (default off).** Grouping deletes inter-sentence
pauses, so restoring them as SSML `<break>` looked like the fix for the holes in the dub. It is a
correct mechanism aimed at the wrong problem, and the forensics say so: at the 5:15 hole the SOURCE
speech is continuous (largest word gap 0.95 s) and the hole is made by ASSEMBLY — unit [61,62] holds
a 15.76 s slot, speaks for 10.66 s, and the remaining 5.10 s is digital silence. `<break>` put back
0.44 s of that (8%) while ADDING pauses where the speaker had none; A/B was indistinguishable. Kept
in the code with the default off — it would earn its place if units with genuinely long pauses
appear. Coverage, for the record: 51 of 57 grouped units took markup (89%), 6 declined.

**THE open blocker is slot fill, and it is not an assembly-only fix.** Silero has no
`supports_target`, so nothing stretches speech to its slot and F5's `plan_speed` does not apply.
On `8zJlKmgMT44`: Silero fills the median slot to **0.73** against F5's **0.90**; 45 of 69 units
hold a hole >3 s, 21 hold >5 s, 267 s total against F5's 124 s. Closing the median hole needs a
**1.37×** slowdown — past `atempo`'s comfortable range — so the translation has to come out ~25-35%
longer (target duration into the translate prompt) with `atempo` <1 taking the remainder. This is
the price of the switch: the engine is cheaper, but timing fit is now ours to do.

**Measurement discipline: `scripts/host_guard.py`, and a retracted conclusion.** A grouping A/B read
verify at 347 s and 597 s against a 45 s baseline, and the conclusion "grouping makes Silero slower
than F5" was drawn from it and stated. Every number was an artifact — a game held the GPU at 98% and
86 C. Re-measured on an idle card, the arms are synth 22.8/28.2/25.3 s and verify 45.8/58.2/56.3 s,
i.e. indistinguishable; two identical baseline verify passes read 84.3 and 45.8, so the run-to-run
noise EXCEEDS the between-arm difference. The methodology was not the weak point: mirrored order
cancels slow drift, but a process that owns the card for the whole session is not drift, it is a
different machine, and counterbalancing cannot see it. Hence a pre-flight gate rather than a
post-hoc correction, wired into both measuring paths of `asr_probe.py`. Three hypotheses for the
"blow-up" were tested and all three falsified before the real cause was found (temperature
fallback: 0/8 fired; decoder repetition: hyp/ref 0.99; a stray round-trip in synthesize: only
created `if engine.supports_seed`, so Silero never had one).

**Stress on borrowed proper nouns: `+` marks, English stress wins, applied by hand for now.** Silero
honours a manual `+` before the stressed vowel — probed contrastively, `reddit_auto == reddit_I`
(the model says "редд+ит") while the marked form differs, so the mark works AND the automatic guess
is wrong there; on "кроссинг" auto already agrees, so a mark would be noise. `normalize_for_compare`
now deletes `+` before the punctuation pass — without that, "р+еддит" compares as two tokens and a
CORRECT reading scores as a defect, which is the one silent failure mode of dictionary stress.
CMUdict (`data/cmudict.dict`, 3.5 MB, in-repo, lazily loaded, feature simply off if absent) gives
the stressed vowel INDEX, and transfer needs no phoneme-to-letter alignment: mark the Nth Cyrillic
vowel where N is the index among vowel phonemes. On disagreement with Russian usage, English wins
(user call: predictable rule + dictionary exceptions beats a per-word judgement). The vowel-count
guard never fired across the probed corpus. **Deliberately NOT wired into `_resolve`:** of the top
60 invented tokens, only 10 disagree with Silero's own stress, and half of those would put a mark on
an already-broken transliteration (`execute → +эксекют`, `update → упд+ейт`) — accenting a defect
entrenches it. Automatic application waits on the transliteration fix.

**Next lever identified: phoneme-based transliteration.** CMUdict was fetched for stress and turns
out to answer the older question too — the letter rules guess at spelling what the dictionary knows
phonetically: `buy → буи` vs `B AY1`, `fields → фиелдс` vs `F IY1 L D Z`, `update → упдейт` vs
`AH0 P D EY1 T`. Coverage over the corpus's invented tokens is 79% of types and 77% of occurrences;
the absent tail is brands and neologisms (`mcp`, `anthropic`, `vercel`, `shadcn`, `tmux`), so the
letter rules stay as fallback rather than being retired.

## 2026-07-24 — The condition_on_previous claim SURVIVES measurement: cond stays operative, guard and hatch upheld

The causal claim held since 2026-07-17 — `condition_on_previous_text=True` produces repetition
loops, `=False` produces terminator-free blocks — was tested here for the first time, on the two
axes the 2026-07-19 note used, against the source it was built on plus the fixture six, 4 repeats
mirrored (`asr_probe.py --variant nocond`, cells `work-exp/asr-probe-cond/`). **The falsification
criterion fixed in advance did NOT fire**, so the claim stands, and the n=1 attribution is now
n=7×4.

**Loop half — cond=True → collapse — confirmed 7/7, stated at its real strength.** On every video
cond=True produces more degenerate 0.02 s stamps than cond=False (11-119 vs 0-1) and an inflated
max ch/s (70-294 vs ~22); on `4szRHy_CT7s` the ranges are disjoint (stamps 70-119 vs 0). Two
precisions the raw pass forces: (1) this is the ALIGNMENT-COLLAPSE signature the note actually
measured — degenerate stamps and ch/s — not textual repetition; the direct textual metric
`dup_pairs` is mostly 0. (2) It is STOCHASTIC: `2YCaBqP8muw` cond=True spanned ch/s 31-300 across
repeats, i.e. one draw came back clean. So cond=True does not always collapse, but it collapses far
more often than cond=False, which essentially never does (floor ~0% everywhere).

**Punct half — cond=False → terminator-free blocks — clear on the source, weak on healthy audio.**
`4szRHy_CT7s` cond=False longest terminator-free gap 35.8 s vs 16 s and term density 5.08 vs 5.7;
on the fixture six term density drops on cond=False on 5/7 but the longest-gap ranges mostly
overlap. The effect is real where the source is already problematic and marginal otherwise — which
is exactly the profile a per-source hatch fits.

**The beam counter-evidence is resolved, not ignored.** The beam probe had shown a loop appear at
beam 5 / cond=True and vanish at beam 1 / cond=True, i.e. moving with BEAM while the flag held.
This pass moves the flag at beam 5 and gets collapse on cond=True across 7 videos. Both factors are
operative; "cond is not sufficient" (PLAN's phrasing) was right, "cond is not the variable" would
have been wrong. No contradiction.

**Consequences — everything that rested on the claim is UPHELD; no pipeline code changed.**
`TranscribeStage._guard` (default cond=True, re-run once with cond=False when the floor ratio
exceeds `transcribe_floor_run_max`) is confirmed by its own mechanism: cond=True drives the floor
to 8-12% on 4szRHy/RyvXxApfHkk/W4Ua6X and cond=False takes it to 0%, so the retry does exactly what
it claims. The `overdub.toml` per-source hatch is justified. The 2026-07-22 batched-inference
demotion (b) keeps its argument — batching hardcodes cond=False and cond IS operative — on the
narrower, now-measured basis that the punctuation cost bites on problem sources rather than
universally.

**Side finding, recorded but NOT acted on.** cond=False is 1.60× faster (fixture TOTAL 258→161 s)
and clean on the floor (0% everywhere) — cond=True is itself the collapse source, not a guard
against it. This does not reopen the transcribe-speed axis: cond=False is rejected on PUNCTUATION
(now measured on the source it hurts), not on speed. The pipeline pays the cond=True cost — slower,
plus guard re-runs on collapse-prone videos — deliberately, to buy punctuation the resegmenter
needs.

## 2026-07-24 — Transcribe-speed axis closed: fp16 large-v3 on one GPU is at its practical ceiling

The four levers named on 2026-07-22 (`int8_float16`, beam 5→1, `num_workers`, distil-large-v3) are
resolved; none is adopted. The reason is one fact measured four ways — on this host the fp16
large-v3 decode already saturates the GPU, so any lever that keeps both the model and the single
card has no idle room to reclaim.

**int8_float16 — measured 0.81× (24% SLOWER), rejected.** Fixture six, control beside it, mirrored
order, timed around `transcribe_words`. This is NOT the silent CTranslate2 downgrade the roadmap
warned about (a fallback to fp16 reads as ~1.0× with identical text): int8 executes and the text
differs, the answer is just negative. Ada's fp16 tensor cores are the fast path already, and
`int8_float16` adds a per-layer quantize/dequantize cost for no compute win. int8 pays off on CPU,
on pre-Ada GPUs without strong fp16, or when VRAM is the bound — none hold (large-v3 ~3.1 GB in a
12 GB budget). Quality also drifts into beam 1's rejected class (fused sentences, dropped
terminators, "research center" → "workshop"). Cells `work-exp/asr-probe-int8/`.

**Cross-video threading — measured, real, closed as not worth adopting.** The `num_workers`
plumbing from the same-day 2026-07-22 split was finally driven: `asr_probe.py --threads N` decodes
N videos concurrently through one `WhisperModel(num_workers=N)` vs serially, wall-clock, mirrored,
mean-based. N=2 = 1.15× (a first single-pair read of 1.28× was a lucky draw; parallel walls span
58-83 s), N=3 = 0.85× — a NET LOSS, because under 3-way contention each decode inflates ~4×
(45 → 160-214 s) and the block runs longer than three serial decodes. Contention is super-linear
in N: Windows has no MPS, so `num_workers` is WDDM time-slicing, not concurrent kernels; the
ceiling is N=2 and it is shallow. Decode is preserved (sim ~1.0), so the objection is economic,
not quality — ~12% of a pass, 42-74% wall dispersion (unpredictable overnight stage time), and
adopting it would parallelise the transcribe stage out of its stage-major shape, breaking resume,
`_guard`, and the just-built per-video `detail.transcribe` accounting (`work_sec` inflates ~1.7×
under contention, so `rtf_work` stops meaning what it means now). Cells
`work-exp/asr-probe-threads-n{2,3}/`.

**beam (rejected 2026-07-22) and distil complete the set.** distil-large-v3 was rejected by
DECISION, not measurement: it is the one lever with real speedup potential, but its likely failure
mode — degraded timestamps with unchanged text — is invisible to the probe's sim axis (alignment
heads for `word_timestamps` are unconfirmed in `Systran/faster-distil-whisper-large-v3`), so
clearing it costs an ear cycle, not a probe run, and is not worth spending while output is good.

**Method note, the durable part.** Every prior in this branch was wrong until measured: int8 was
"the cheapest win" and returned a 24% loss; threading was "won't help" and helped ~15%; the 1.28×
first read shrank to 1.15× on four repeats. And the probe's own rollup used `min`, which on a
drift-confounded host hands the latest (drift-fastest) block to whichever mode owns it — switched
to `mean`, which the mirrored order makes drift-neutral. On a monotonically drifting machine,
average the mirrored pair; never take the best.

**What reopens the axis** (recorded so it is not re-litigated): a SECOND GPU for the transcribe
stage — real parallelism with no contention, unlike `num_workers` on one card; a non-Ada or CPU
host where int8 pays off; or distil-large-v3 cleared by an ear session. Not another probe here.

## 2026-07-22 — Batched inference is a DIFFERENT DECODE, not a faster one: roadmap lever (b) demoted

The roadmap carried `faster_whisper.BatchedInferencePipeline` as speed lever (b) with one caveat —
"unproven here, check `word_timestamps` survives it". Both halves are wrong, and the source
answers them with no GPU (faster-whisper 1.2.1, `.venv-asr/Lib/site-packages/faster_whisper/`;
line numbers below are `transcribe.py` at that version).

**`word_timestamps` survives. `condition_on_previous_text` does not.** The batched `transcribe()`
accepts `condition_on_previous_text: bool = True` in its signature (`:277`) and then builds
`TranscriptionOptions` with `condition_on_previous_text=False` hardcoded (`:547`) — the caller's
argument is read by nothing. Word timestamps, meanwhile, are passed straight through (`:545`) and
applied (`:161-162`). So the one question the roadmap wrote down was aimed at the parameter that
is fine, while the parameter that matters is silently overridden behind a signature that says it
is configurable. Three more values are decided for the caller in the same construction:
`hallucination_silence_threshold=None` (`:546`), `max_initial_timestamp=0.0` (`:552`), and VAD's
`max_speech_duration_s` forced to `chunk_length` — 30 s, from the feature extractor (`:394`,
`:400`) — with a caller-supplied value popped and overwritten rather than honoured (`:404-409`).

**That flag is what buys this pipeline its punctuation, so losing it is not a side effect.**
DECISIONS 2026-07-17: with `condition_on_previous_text=False` long stretches came back as 60-206 s
terminator-free blocks that the overlong-splitter bisected mid-phrase — the ROOT of the "period
mid-sentence" class. Turning it True is the fix that closed that class, and it ships True
(`whisper_condition_on_previous`). Batched mode also makes `TranscribeStage._guard` inert: the
guard's entire remedy is "re-run once with that flag off", so under batching the retry is the same
decode as the first pass — it can only cost a second ASR pass, never repair anything.

**Consequence, and it alters the roadmap: lever (b) is DEMOTED, not rejected.** It is no longer
comparable to `int8_float16` / beam 1 / distil-large-v3, which change how fast the same decode
runs. It changes the decode itself, on axes this project chose deliberately and paid for once
already. It is therefore admissible only AFTER the other levers, and only against the same quality
gates plus the punctuation axes specifically — terminator density and the longest terminator-free
stretch, which is the 2026-07-17 defect class stated as a measurement. It is correspondingly
absent from `scripts/asr_probe.py`'s variant table. Note
what this does to the reported multi-× speedups elsewhere: they are measured on a decode that has
no cross-chunk conditioning and a 30 s VAD ceiling, i.e. on a configuration this pipeline
previously measured and rejected on output quality — the number is real and it is not our number.

**The threading lever is the one that PRESERVES the flag, and the reason is structural.** The
sequential `transcribe()` keeps `last_speech_timestamp` as a LOCAL (`:1152`); `BatchedInferencePipeline`
keeps it on `self` (`:117`). So the sequential path is the thread-safe one, which is exactly what
`WhisperModel(num_workers=N)` → ctranslate2 `inter_threads` (`:695`, docstring `:654-657`) asks
for: N concurrent `transcribe()` calls, each with its own options, the flag intact. Cross-video
threading and batching are not two flavours of the same idea — one keeps the decode and buys
parallelism, the other buys throughput by changing the decode. The `num_workers` plumbing is
recorded in the same-day entry on the decode-config split; what is NOT built is a driver that
calls it from more than one thread, so this lever is unmeasured today (PLAN records the coverage
gap).

## 2026-07-22 — The ASR decode config is a key, the verifier is not: role-split compute type, one shared beam, and a provenance stamp

"Transcribe speed" is the last bottleneck (907 s per pass over the 6-video queue, 2:53:44 of
audio, RTF 0.087, 79% of a scout pass) and the four candidate levers — `int8_float16`, beam 5→1,
`num_workers`, distil-large-v3 — were all unreachable for the same reason: **the decode config was
hardcoded, so there was nothing to A/B and nothing on disk saying which config produced a
transcript.** This entry is the plumbing that makes an experiment possible; it changes no
behaviour on an unchanged `overdub.toml`.

**`verify_compute_type` is independent of `whisper_compute_type`, not inherited from it.**
`Session.whisper` passed one compute type to both large-v3 and whisper-small, so a single TOML
flip would have moved the round-trip verifier along with the transcriber. The verifier is this
pipeline's MEASURING INSTRUMENT — it decides which units are flagged and which clear
`similarity_threshold` — and an instrument that moves with the thing it measures cannot detect a
regression in it: the experiment would read its own measurement error as a result. An "inherit
unless overridden" sentinel was rejected precisely because it would still drag the verifier along
by default, i.e. it would not fix the problem at all. The resolver is `cfg.compute_type_for(role)`
keyed on ROLE and not on model name, because `verify_model` is itself a key: pointing it at
large-v3 must not silently inherit the transcriber's experimental compute type. Unknown role
raises — a closed 2-element enum with 4 call sites makes a typo a programming error, not a
runtime scenario. For the same reason verify's beam is a NAMED CONSTANT (`asr.VERIFY_BEAM_SIZE`)
rather than a key: verify is ~0.3 s/unit and is not on the critical path this lever is shortening,
so it holds still by construction.

**One beam key, shared by the stage and `--repair-asr`, and `transcribe_words` requires it.**
There is deliberately no `repair_beam_size`. Repair's whole contract is *delete, do not invent* —
its output must be indistinguishable IN KIND from the surrounding transcript — and a second beam
key is a licence for it not to be: a window decoded at beam 5 spliced into a transcript decoded at
beam 1 is a different kind of artifact from its neighbours, which is the exact drift the shared
`transcribe_words` body exists to prevent. The parameter is keyword-only with NO default, because
a default is how one of the two call sites silently keeps beam 5 while the other moves: green
suite, wrong media.

**`asr_key` + a refusal in `TranscribeStage.done()` — this is the hole that made an adoption
unverifiable.** There was zero on-disk provenance for the decode config (report.json records only
`verify_model`, run.json records nothing), so two runs at different beam sizes were
indistinguishable after the fact. The key is now stamped into `timings.json` `detail.transcribe`,
and it is a readable string rather than a hash on purpose: a mismatch message that names the two
configs is actionable, one that names two hex digests is not. It carries the
`condition_on_previous` INTENT, not the pass actually taken — `_guard` may re-run with the flag
off, and that is a per-run reaction to the audio, not a config change. `done()` now raises on a
mismatch because both ways an ASR config change can land are silently wrong: on an existing
workdir it is a no-op (`[skip] transcribe`, and the operator believes a beam-1 run happened), and
forced it rewrites `sentences.json` while `TranslateStage.done()` is bare existence — pairing a
NEW transcript with the OLD `translation.json`, which synthesize's congruence gate cannot see
because it compares the manifest against the translation, not against sentences. Refusing is right
here even though this repo flags rather than blocks: a flag leaves an audibly bad segment, whereas
continuing produces a run that LOOKS clean and is not. Pre-stamp workdirs have no key and are
accepted unchanged — this must not invalidate the existing corpus. Rejected: auto-calling
`WorkDir.invalidate_downstream()`, which deletes user artifacts on a config typo, in a codebase
where an unknown config key is a print and not an error.

**`num_workers` is a loader keyword, not a Config key.** `WhisperModel(num_workers=N)` becomes
ctranslate2's `inter_threads` (faster-whisper 1.2.1 `transcribe.py:695`) and the sequential
`transcribe()` path is the thread-safe one (it keeps `last_speech_timestamp` local at 1152, where
`BatchedInferencePipeline` keeps it on `self` at 117). But `run_pipeline` is strictly sequential,
so a cfg key would have no consumer — it exists only so `scripts/asr_probe.py` can measure the
cross-video-threading ceiling through the one loader that registers the CUDA DLL dirs and warms
the model. It is absent from the session cache key for the same reason (the session never varies
it); if it ever becomes a knob it must enter that key. What DOES enter the key now is the BEAM,
because `_warm` tunes kernels for a beam — an instance warmed at 5 is not interchangeable with one
warmed at 1, and a key that omitted it would hand an in-process A/B two references to one build.

`scripts/lv_pick_refs.py:30` is left on `load_whisper("large-v3")` loader defaults by design: it
is a one-off reference-picking tool, not pipeline code, and pinning it to cfg would give it an
opinion it does not need.

## 2026-07-22 — Measuring ASR inverts `exp_nfe_sweep`'s premise; and the host drifts, which is a different problem from noise

**Status note, same day.** The harness this entry was written for (`exp_asr_sweep.py`, its region
scorer and its runbook) was deleted hours later and replaced by `scripts/asr_probe.py`. The reason
was written up in `CHANGELOG.md`, retired from this repo in f68291f — read it with
`git show f68291f^:.claude/CHANGELOG.md`. The premise below outlived it and is the reason the probe
exists in the shape it does; the two-corpus machinery described further down did not, because the
probe runs one corpus and says so. Read this for the premise, not for the file layout.

`exp_nfe_sweep`'s central premise is FALSE for ASR and the instrument is inverted accordingly. F5
is deterministic for a fixed (text, seed, speed, nfe), so that harness buys coverage with more
texts and repeats a cell only to *falsify* determinism. **Whisper's temperature fallback samples:
the same audio at the same settings returns a different transcript, a different word count and a
different wall time.** There is therefore no axis with a zero expectation here — the role
`duration_s` played there is played by a MEASURED NOISE FLOOR, control-vs-control, and repeats are
a first-class axis rather than a check. The project's own record of what happens without one is
`config.py`'s `transcribe_floor_run_max`: a 5-run sample looked cleanly separable and a sixth
independent sample put the mid video above the severe video's entire range. A single run proves
nothing about any lever in this file.

**MEASURED THE SAME DAY, and it splits that premise in two.** Not all of the run-to-run movement
is sampling noise. On a clean HEAD worktree, shipped config, three repeats over the fixture six:
block 3 ran **8-29% faster than block 1 on all six videos, in the same direction every time**.
That is a monotone within-session drift, and it behaves nothing like noise — averaging does not
remove it, more repeats only tighten a biased estimate, and only counterbalanced block order
cancels it (mirrored pairs, hence the probe's even-`--repeats` advice). Text sampling noise and
wall-clock drift are therefore two separate problems needing two separate defences: repeats for
the first, ordering for the second. An earlier conclusion that "the machine is ~3× noisier than
any lever, so nothing under 50% is measurable here" conflated them and is RETRACTED — int8 and
distil remain measurable. Two further facts: HEAD drifts as much as the changed code, so none of
this is our doing; and the direction is OPPOSITE to the RTF 0.39-cold / ~0.60-hot record in the
2026-07-19 gotchas entry, which points at thermal throttling. Cause unidentified. Controlled for,
not modelled — and if a future measurement depends on it, identify it first.

**Two corpora, and five structural barriers between them.** `fixture` (the 6 repair-fixture ids,
41:06) is the only corpus with human-verified references, so it is the only place a quality score
means anything — and its 4-12 min videos are the wrong SHAPE for a speed claim about 20-36 min
production sources. `queue` (the 6 production ids, 2:53:44) is where the 907 s / RTF 0.087 baseline
lives and has no human references. Convention was not enough to keep the two apart, so: `--corpus`
is required with no default; `--out` defaults per corpus; the rollup emits a literal STRING, not a
number, for `speedup_vs_control` on `fixture`; `region_score` and `watch` are `None` on `queue`;
and the fixture report prints its `work_sec` column under a "DIAGNOSTIC ONLY" header. A reader
cannot lift a speed number off the quality corpus or a quality verdict off the speed corpus.

**Separability is interval-disjointness over repeats, not a t-test.** At R=3..5 a distributional
assumption is unearned, and this project has already been burned by a 5-run sample that looked
separable. Disjoint [min,max] intervals is the weakest claim defensible from this many
observations and is falsifiable by one more repeat; the corpus verdict additionally requires 4 of
6 videos separable with agreeing sign, and prints the literal `"not separable"` in place of any
ratio otherwise. Control is a full variant re-run at the head of every repeat round, so the
thermal/order confound is bracketed by construction rather than by a bolt-on recheck, and one
model instance is loaded per (repeat, variant) block — never interleaved by beam inside one
instance, because `_warm` tunes kernels for a beam and a shared instance would charge one
variant's mis-tune to the other's first video.

**The region score is a REGRESSION DETECTOR, not a ranking, and the watch list is the reason it
is not enough.** The 12 scored regions were harvested from full-file large-v3's own defects, so
the control arm reproduces them by construction and its own score is expected to be near zero —
the comparison of interest is variant vs control, never variant vs 12. That makes the score
structurally blind to a NEW failure on clean speech, which is exactly what cheap presets are most
likely to produce and exactly what `Claude`→`Cloud` was (2026-07-20: clearly enunciated, both
readings agreed, the stability gate could not object). The watch list plus the full-file
`sim_vs_control` are the independent metric; publish a verdict only when both agree. A region is
the on-disk diff block and never a repair window — that single rule dissolves two of the three
reported fixture "poisonings", leaving one genuine case (the `Anthropic's Claude models` override,
which no automation bound by *delete, do not invent* may reproduce) excluded from the headline
count and carrying its reason.

**The decision rule is fixed BEFORE the first run and printed by `--dry-run`**: separably faster
on `queue`; `sim_vs_control` on `fixture` not separably below the control-vs-control band;
`floor_ratio` under `transcribe_floor_run_max` in every repeat, `max_term_gap_sec` never past 60 s
(the DECISIONS 2026-07-17 defect class), `term_density` never past its alarm; and every watch entry
passing. "Cannot tell" counts as PASS on the quality axis — that is what stops a noisy instrument
from vetoing a lever — and as FAIL on the speed axis, because an unproven speedup is not a
speedup.

## 2026-07-22 — Overhead is SUBTRACTED per stage, never summed across kinds; and partial coverage is declared

2026-07-20 established that `stages[x]` (wall) and `detail[x]` (work) both stay and are never
summed together. Completing the accounting needed one thing that entry did not settle: how to get
a per-RUN load-excluded figure without violating it.

**The legal operation is `stages[x] − detail[x].work_sec`, and its legality is that both numbers
describe the SAME stage.** That difference is the stage's overhead — a model load, a worker spawn,
a preflight — and summing overheads with each other is fine. What is forbidden is a hybrid total
that adds a wall clock for one stage to a work figure for another and calls the result a cost.
So `total_work_s` is `total_wall − Σ known overheads`, never a sum of mixed kinds, and `rtf` is
left exactly as it was: it is what the run cost, and deleting it to promote `rtf_work` would
repeat the mistake 2026-07-20 rejected (publishing one number makes the other unrecoverable).

**Partial coverage travels WITH the number, as `work_coverage` + `work_complete`.** Five stages
still report no `detail`, so `total_work_s` is an upper bound. The alternative — withhold the
figure until every stage is instrumented — was rejected because the three heavy stages are where
the optimization work is, and a number that says how complete it is beats no number. `separate`
is the next one worth instrumenting and the reason is already measured: its slope against audio
length is R²=0.000, so its entire wall is load, and `rtf_work` currently overstates by ~13.2 s
per video for that reason alone.

**A `work_sec` ABOVE its stage wall is DROPPED, not clamped to zero.** The pair can straddle two
sessions — `record_stage_timing` only writes for stages that actually ran, while an earlier
session's `detail` survives in the same file — and a negative difference is the file saying the
two halves do not describe one run. Clamping would report that stage as pure work, which is a
fabricated fact; dropping it says the overhead is unknown, which is true. Pinned by a test whose
name is the decision.

**Correction, and it reverses a claim the roadmap made about itself.** The old accounting item
said every recorded speed number was suspect, "including `nfe` 48→16's 2.16×". That is wrong
about that number. `scripts/exp_nfe_sweep.py` times each cell around `engine.synthesize` alone
and records `startup_s` separately, so the worker spawn was never billed to a video — the figure
needs no re-check, and the 2026-07-19 ledger entry stands. What IS wall-clock contaminated is
everything derived from stage walls before this change: the ~72 s/video fixed cost, the
Silero-vs-F5 whole-pipeline RTF pair, every `breakdown_pct`. **The general lesson is the one worth
keeping: a blanket "distrust all recorded numbers" is itself an unverified claim, and it cost
this item its credibility on the one number it named.** Check what a harness actually measured
before condemning its output.

## 2026-07-22 — The roadmap is named, not numbered, because the numbers were lying

Roadmap items are now slugs (Transcribe speed, Timing accounting, …) and 34 "PLAN item N"
references across 12 code and test files were renamed to their topic.

**The numbers were not merely stale, they were ambiguous in the present tense.** PLAN was re-cut
three times in a week and the code comments never moved with it, so "PLAN item 1" simultaneously
pointed at the F5 speedup (`exp_nfe_sweep.py`), the source-anomaly pass (`runreport.py`), proper
nouns (DECISIONS 2026-07-18) and transcribe (PLAN today). A reader following one of those
pointers landed on an unrelated item and had no way to tell.

**The fix is not better numbering, it is removing the pointer's dependency on ordering.** A
comment that says "the queue-page merge" or "the source-anomaly pass" names a thing that exists
whatever the roadmap does next; renumbering cannot break it, and the reference degrades to a
searchable phrase rather than a wrong index. Rejected: stable ids that never get reused (a second
vocabulary to maintain, and it still says nothing about WHAT is referenced); and leaving the
numbers with a "as of <date>" suffix (correct, but every reader still has to reconstruct a dead
roadmap to use it).

**DECISIONS keeps its numbers deliberately** — as did CHANGELOG, before it was retired. They are
dated records of what was true when written, and rewriting them to today's vocabulary would
destroy exactly the provenance that makes them worth keeping. Only PLAN — the forward-looking
file — and live code comments were converted. `.claude-tasks/` session records were left alone for
the same reason.

## 2026-07-21 — One queue page: the scout report is the base, the triage page merged into it

PLAN item 2 (reconcile the renderers) could be closed two ways: a shared data layer under two
thin renderers, or one merged surface. The user chose the merge with the scout report as the
base — its formatting is the one tuned on real queues — and dub data as ADDED layers on the
same cards. What made it coherent: the shared derivation layer (`runreport.collect_entries` /
`batch_row`) was built FIRST either way; the merge is a presentation decision on top, and the
text digest still exists (it feeds the route-B skill agent), so cross-surface agreement had to
be solved regardless.

Settled tensions, for the record: (1) the two pages answered different questions with opposite
orderings — queue order won as the page-wide law (position is information), and the morning-listen
job is served by a triage nav block with anchors, never by re-sorting; (2) the completeness number
is `n_actionable` everywhere, advisory shown separately, with the pre-schema `n_flagged` fallback
shared by every surface — «completeness 0» beside «completeness 5» on the same bytes was the
original bug; (3) a card never fabricates dub metrics for a non-dubbed video, and a torn dub
rollup OUTRANKS the grade chip («без свода») — a healthy-looking graded card over broken artifacts
is the silent failure this repo exists to prevent. Rejected: renaming to `queue_report.py`
(reference churn across two skills and the published-artifact flow buys only naming honesty;
revisit if the "scout" name starts misleading operators). Reconsider the merge itself only if the
page grows a second job that fights queue order, or embedded audio makes the published artifact
impractically heavy.

A repair now preserves `translation.json` (the source-anomaly worklist — PLAN item 4) before
`invalidate_downstream` deletes it. The two backups deliberately differ in retention.
`_pre-repair-sentences.json` is write-once: its job is the golden fixture, the TRUE original
before the FIRST repair. The translation backup's job is the operator's NEXT action — the
worklist that motivated THIS repair — so it must track the latest pre-repair state: write-once
would keep a stale report while destroying a fresh one, which is exactly the loss the feature
exists to prevent. Consequence to remember: ids inside the preserved report predate the
renumbering the repair just performed (the runtime backup line says so). Rejected alternative:
extracting only the anomaly rows — a byte-exact copy keeps every field the operator might want
and costs one small file.

## 2026-07-21 — The scout preview: 160px, inlined once, and no 2x source

Three choices about one thumbnail, recorded because each was argued and reversed at least once,
and all three would otherwise be re-litigated from the same wrong intuitions.

**160px, and no 2x source for hi-DPI.** It was briefly 320 rendered at 160, on the reasoning that
the file is then a retina source. Rejected on what the image IS: a scan-table preview is glanced
at to recognize a video, not studied. Three quarters of the page was being spent on detail nobody
looks for. If a future change wants the preview LARGER, `_THUMB_W` must move with the CSS — the
test enforces a ceiling (render no wider than the stored file), not an equality, so the narrow
direction stays free.

**The preview is a CSS background, not an `<img>`, and the lost `loading="lazy"` is the price.**
It appears twice per video, a `data:` URI is bytes rather than a reference, and CSS is the only
place in a static self-contained page where one blob can be declared once and used twice. The
cheaper alternative — drop the preview from the read cards — saves identical bytes with zero code
and was offered and declined; the cards keep their picture. Consequence to remember: a background
box has no intrinsic size, hence `aspect-ratio`, hence `jpeg_size` parsing real dimensions instead
of assuming 16:9 (ffmpeg scales with a derived height, so the ratio follows the source, and a 4:3
frame guessed as 16:9 gets cropped).

**Artifact page weight is not worth optimizing much further.** At 6 videos the report is now ~79
KB and the images ~31 KB of it. The remaining lever is the text, and the saved-page bundle is
dominated by claude.ai's shell (185 KB) which we do not control. Revisit only if queues reach
~100 videos.

**Method note, more durable than any of the above.** Every intuition in this thread was wrong
until measured: "320px triples the page" (wrong, never measured), "the dedupe is free" (free in
bytes, not in code — it cost a JPEG parser and lazy loading), "only re-running Sonnet can rebuild
the report" (wrong — the summaries survived in the saved HTML), and the user's own "стало меньше,
но совсем чуть-чуть" (the report had halved; the bundle they measured was 58% claude.ai's). The
page is cheap to weigh. Weigh it before arguing about it.

## 2026-07-21 — An agent's report of what it DID is not evidence; the transcript is

Trimmed 2026-08-03: three paragraphs restating the knowledge-file rule below are gone. What stays
is the one line of evidence and what the incident changed in this project.

The first wave under the `scout.started` marker produced a contradiction worth recording, because
the wrong resolution of it would have sent the next month of optimization at the wrong target. The
markers said the six sub-agents' first writes were 102 s apart; asked directly, the orchestrator
described a single fanned-out call, in good faith and in detail. The transcript showed six separate
assistant messages, one block each.

**The generalised rule has been promoted to
`~/.claude/knowledge/claude-code/agent-orchestration.md`, section "An agent's report of what it DID
is not evidence"** — what an agent reports it OBSERVED is reliable, what it reports it DID is not;
verify control flow against an artifact it did not author; do not try to fix a fan-out by wording
the instruction harder. That file loads in every session and is not overdub-specific. Do not
restate it here.

> **PARTLY SUPERSEDED 2026-07-21** — the mechanism fix below lasted hours. Constraining the wording
> ("~6 `tool_use` blocks in ONE message") is the very thing this entry's own evidence says does not
> work, and it was replaced the same day by a deterministic `Workflow` fan-out (aae24b1,
> `.claude/workflows/scout-summarize.js`), which does not depend on a model choosing to emit N
> blocks. The markers, the disk-side check and the roadmap inversion below all still hold.

**What it changed in this project.** Per-video markers stay and no timing is ever self-reported by
a model — the marker design is the only reason any of this was visible from outside the run. S2 was
rewritten to constrain the MECHANISM (~6 `tool_use` blocks in ONE message) rather than the wave
size, and to prescribe the disk-side marker check. And the roadmap inverted: with the fan-out fixed,
summarization stops being the scout bottleneck — on this queue 842 s → ~254 s against 723 s of
transcribe. The next wall is the GPU, not the agents.

## 2026-07-20 (evening) — Two kinds of timing, kept apart; and the filesystem does the stamping

PLAN item 2 asked for model-load time to be separated from processing time. The obvious fix —
subtract the load from the stage wall clock — is wrong, because the two numbers answer different
questions and both are wanted.

**`stages[x]` and `detail[x]` both stay, and are never summed together.** The wall clock
including the load is what the run actually cost; that is the honest answer to "how long did
this batch take". The load-excluded figure is what one VIDEO cost; that is the only answer that
compares across builds, because stage-major amortises one load across a sweep and it lands on
whichever video happened to be first. Publishing one of them would have made the other
unrecoverable. Rejected alternative: divide the load across the batch's videos. That invents a
per-video cost nobody paid and makes a 1-video run incomparable to a 30-video one.

**The warmup is in `load_whisper`, and it is the minor half — recorded so nobody re-litigates
it.** Measured on this machine: large-v3 loads in 3.3-3.6 s, and its first decode runs 0.472 s
against 0.30 s steady-state, i.e. kernel autotuning costs ~0.17 s. So the warmup removes ~0.17 s
of contamination and costs ~0.4 s per load — break-even in time, worth it only because it makes
the first video of a sweep comparable to the rest. The distortion that actually mattered was the
3.3 s load, and `work_sec` excludes that without a warmup at all. It lives in `load_whisper`
rather than in the transcribe stage because the session hands one model to transcribe, verify
and the synthesize reseed loop alike: that is the one place that runs exactly once per load.

**Per-agent summarize time comes from a marker file the agent touches, not from anything it
says.** The objection that killed the first attempt at this (a model's claim about its own
runtime is unverifiable and routinely invented) applies to a start time exactly as much as to a
duration, so the sub-agent's only instruction is to create an empty `scout.started` — the OS
supplies the timestamp. Rejected alternative: have the orchestrator stamp each agent's spawn.
It does not work, and the reason is worth keeping: agents queue behind the concurrency cap, so
spawn time measures the queue, not the work. Known and accepted floor: the marker lands after
the agent's first tool round-trip, so a 20-minute window reads seconds short — it errs downward
and degrades to ABSENT rather than to a wrong number.

**The wave's wall clock is now summed per wave instead of spanned across the queue.** The old
`max(draft) − min(start)` was correct only for a queue summarized in one shot. A resumed queue is
the normal case — the skill re-summarizes only what needs it, so carried-forward videos keep an
older wave's start forever — and the span then included the idle hours between waves. This is
the same error as the per-video duration that was deleted this morning, one level up: a wall
clock presented as work. Fixed the same way, by measuring only what was running.

**Cost, paid knowingly:** no `summarize_sec` and only one `transcribe_work_sec` exist on disk.
Every prior workdir has neither, and neither is backfilled from the wall clock — that would
restate the model load as the video's cost, which is the exact confusion this whole entry is
about. The baseline for measuring any optimization does not exist until the next full pass.

## 2026-07-20 — Scout grades the material, not the reader (a personal verdict cannot be checked)

Scout shipped with a `watch`/`maybe`/`skip` verdict judged against `.claude/viewer-profile.md`.
The first real queue came back **0 / 1 / 9**, and the second axis (`focus`/`background`) took the
same value on **28 of 30** videos. Both were replaced the same day.

**The measurement is not the argument — the checkability is.** A 9-of-10 skip rate could mean the
queue was genuinely poor. What decided it is that there is no way to find out: a verdict about
whether *this person* should watch *this video* has no referent outside the model's guess, so it
cannot be argued with, corrected, or regression-tested. "Is this well made, current, and densely
delivered" can be. That is the whole reason the axis moved onto the material.

**The verdict also collapsed by construction.** The profile's own rule says to prefer `maybe`
when uncertain and reserve `skip` for a named ground — and the run still produced 9 skips, i.e.
the model was finding grounds it would not have found for a question about the material. A
decision taken FOR the reader drifts toward "no", because "no" is the safe answer for an agent
that cannot know.

**The profile was demoted, not deleted.** It still decides what counts as the interesting part
and what counts as already-known — the two places where knowing the reader genuinely helps. It
no longer touches the grade. Rejected alternative: drop the profile entirely and grade purely on
the material. That loses the "do NOT recommend an introduction to what I already know" section,
which is the single most valuable thing in the file and cannot be derived from a transcript.

**The cost, paid knowingly:** every `scout.json` and every `scout.draft.json` on disk carries the
old vocabulary, so the 30 already-scouted videos need their S2 re-run — not a rebuild. Also
unresolved: nothing has yet confirmed a live sub-agent can hold the distinction between "quality
of the material" and "useful to me". That confusion is exactly what produced 0/1/9, and the
mitigation is a calibration pass (PLAN, pre-batch checks), not more prompt text.

## 2026-07-20 — Scout mode: audio-only fetch, no local summarizer, its own flag

Three choices, one per axis. Recorded together because each is cheap to "fix" later in exactly the
direction that undoes the reason it exists, and because each one's cost is real and named rather
than argued away.

**1. Scout fetches AUDIO ONLY, and a promoted video re-downloads.** `yt-dlp -f bestaudio` →
`source.wav`; no `source.mkv`, so `DownloadStage.done()` splits into an audio gate and the unchanged
video gate. The forcing constraint is disk, not time: D: has 81 GB free, and a 100-video queue in
full mode wants ~100 GB in hour 0 (stage-major hoists all downloads to the front). A triage pass that
cannot fit on the disk is not a triage pass.

**Cost, named: promotion re-downloads the audio bytes inside the merged MKV — ~5% extra traffic,
paid on exactly the videos that were worth dubbing.** Accepted for zero new machinery: no cache, no
container surgery, no third gate. A second, subtler cost rides along — the promoted run OVERWRITES
`source.wav` with a differently-decoded file (ba[ext=m4a] out of the MKV, vs the scout's opus), while
`sentences.json` was read off the old bytes and `--repair-asr` will clip windows from the new ones.
Same YouTube master and same timeline, so this is believed benign; it has not been checked, and it is
in PLAN's backlog rather than dismissed.

Rejected, all three for the same class of reason: **letting the video gate accept `source.wav`** —
mux then gets a container with no video stream, i.e. the failure lands eight hours later at the end
of a run; **skipping re-extraction when `source.wav` already exists** — saves the rewrite and leaves
a wav from a DIFFERENT fetch as the permanent input to a full run, which is a stale artifact served
as current; **a separate scout workdir** — two directories per video and a promotion step that has
to move files, to save a fetch that costs 5%.

**2. No local summarizer. The summary stays a Sonnet sub-agent at the seam.** Rejected: a
Gemma/Ollama summarize stage inside the pipeline. It would have made scout self-contained, and the
2026-07-20 summary entry had already established the read-boundary sanitizing that makes an
LLM-written prose blob safe to render.

**Cost, named: scout is NOT turn-key on the local route, which is the one property route A has that
route B does not.** Route A is one command; a scout pass is a command plus an agent fan-out, so a
Gemma-only operator gets `sentences.json` and a page full of `summary pending` and no way to finish.
Paid because the alternative is worse in a way this project has already measured: the summary's whole
job is "should a human spend an hour on this", and Gemma-3-12B is the model we A/B'd into second
place for translation (2026-07-18). A ~200-word judgement call written by the weaker model would be
read as if written by the stronger one. Adding a Gemma summarizer stays available — it is additive,
it needs no schema change, and this decision is not a bar on it. It just was not built blind.

**3. A dedicated `--scout` flag, not `--only download transcribe`.** `--scout` selects
`scout_stages()`, which constructs the truncated list and the audio-only `DownloadStage` in one
expression. `--only` cannot express the audio-only download at all — that fact lives INSIDE the
stage — and `run_pipeline` checks STOP before the only/done filters, so an `--only` composition
would sweep 8 stages and grid 8 STOP checkpoints per video to do 2 stages of work.

**Cost, named: a flag that must be kept in sync with the stage list.** Adding a stage to
`all_stages` that belongs before transcribe will not appear in `scout_stages`, and nothing enforces
that scout stays a strict PREFIX of the full pipeline — which it must, because a promoted video
re-enters the full pipeline on the artifacts these two stages produced. Mitigations, both partial:
the prefix property is pinned by a test, and the two facts that could actually corrupt a run
(truncation + download shape) are welded into one expression so they cannot drift apart. The flag
also has to be excluded by hand from every other mode — `--only` and `--repair-asr` both needed a
new usage-error clause, and a third mode would need a third.

## 2026-07-20 — `--repair-asr` exits 0 when every window was rejected (decided, not defaulted)

**Kept as is.** A rejection is a decided, reproducible outcome — the gate looked and said no — not a
failure, and a nonzero code would poison the batch contract "re-run the same command to retry the
failed videos" by making every clean re-run look broken. Rejected alternative: exit 2 or 4 on
all-rejected, so a shell `&&` chain stops. **The named risk is real but currently hypothetical:** a
`repair && resume` wrapper would proceed to dub an unimproved transcript silently, which is the one
place this repo's no-silent-failures rule is bent. It is hypothetical because no such wrapper
exists and the README prescribes a dry run first. **Reconsider the moment anyone chains repair into
an automated pipeline** — at that point the honest fix is a distinct exit code, not a louder
message, because a wrapper cannot read stderr prose. Logged rather than patched so the bend is
conscious and has a named trigger instead of being rediscovered as a bug.

## 2026-07-20 — Isolated-window re-ASR has a measured cost: the clip loses context and can regress proper nouns

`--repair-asr` automates the method this file blessed on 2026-07-19. Replaying the 6 preserved
`_pre-repair-sentences.json` fixtures through it — real audio, real large-v3 — found something no
amount of code review could, because it is a property of the METHOD, not of the implementation.

**The regression, verified byte-for-byte on disk.** `2YCaBqP8muw`, window ids 42-45:

| source | text |
|---|---|
| pre-repair (full-file ASR) | `...a very specific style you want **Claude** to follow...` |
| human ground truth | `...a very specific style you want **Claude** to follow...` |
| `--repair-asr auto` output | `...a very specific style you want **Cloud** to follow...` |

The input was RIGHT and the repair made it WRONG. Three things had to line up, and all three are
by-design behaviours we shipped deliberately:

1. That sentence carried **no detector flag**. It entered the window only because `widen()` grew the
   span to reach `repair_window_min_sec = 8.0`.
2. The replaced id range must be co-extensive with the audio window — otherwise a reading overwrites
   sentences it only partially heard — so a clean neighbour gets rewritten from the window's reading.
3. **Both readings agreed**, so the gate accepted. cond=True and cond=False agreed *on the wrong
   word*.

**The general principle, which is the point of this entry: a clipped 8-18 s window has strictly less
context than the full file, so window re-ASR is not uniformly an improvement — it is a TRADE.** It
buys freedom from the repetition loop (`condition_on_previous_text` has no prior to loop on) and
pays in whatever the surrounding minutes were disambiguating. Proper nouns are the first thing to
go, and it failed on exactly the brand name the single sanctioned human override of 2026-07-19
exists to protect. ~~Second instance the same run: `DmgujoZ1mmk` id 32~~ — **RETRACTED, see the ear
check below: that one was the automation being RIGHT.**

**This does not retract the 2026-07-19 gate — it bounds it.** `readings_agree` proves STABILITY,
never correctness; that was always in the docstring. What the fixture adds is that the scope of the
evidence and the scope of the claim differ: agreement is measured over the WHOLE window, but only
the SEED ids carry a defect hypothesis. For every other sentence the repair silently prefers a
second, less-informed opinion over a first, better-informed one. Shipped mitigation (2026-07-20):
`WindowResult.collateral` + a `[warn] collateral edit on unflagged id(s)` line and a per-video
counter, so a net-negative substring can no longer report as a bare "1 accepted, 0 rejected". That
makes it visible. **It does not make it safe — ears remain the final authority, and a repaired
window now deserves the same listen a flagged one gets.**

**Measured recall: `auto` reached 5 of the 12 human-repaired regions on disk.** Both videos this
file already named as detector-blind produced ZERO windows and printed as clean:
`RyvXxApfHkk` id 11 at 35.9 ch/s and `W4Ua6XFfX9w` id 21 at 26.8 ch/s, both under the physically
grounded 40 ch/s bound. That is the 2026-07-19 prediction confirmed, not a new failure — and it is
the standing argument for the reading pass at the translate seam (roadmap item 1), which is the only
thing that sees these. **Do not lower `_RATE_MAX_CPS` to chase them**; the bound is sited on human
speech physics (corpus p99 34.26), and lowering it trades a blind spot for false positives.

**What held.** The `delete, do not invent` invariant: nothing was fabricated anywhere, and the
automation correctly did NOT reproduce the human's `Anthropic's Claude models` override. Timestamps
are sound — monotone in all 6 files, zero overlaps, zero inversions, max delta vs human inside a
repaired window 0.71 s. The feared silent mis-rebasing of the clip onto the absolute timeline does
not exist. Repaired first sentences start exactly `CLIP_PAD_SEC` (0.25 s) early, systematically and
harmlessly — `clip_span` clamps t0 to the previous sentence's end, so that span is silence by
construction.

**Correction to 2026-07-19's cost figure.** "~1 minute per window" described the manual script,
which paid a fresh large-v3 load per invocation. The automation loads the model once per sweep:
10 readings in 25.7 s wall, ~2.6 s each — **20× cheaper than documented**. Any argument that leans
on repair being expensive (including "don't always dry-run first") is now void.

### Ear check, same day — one finding inverted, one confirmed, and the golden fixture demoted

Three windows listened to against `work/<id>/source.wav`. The result changes the scoreboard, and
in one case reverses it.

| window | what the ear says | verdict |
|---|---|---|
| `DmgujoZ1mmk` @ 2:42.90 | the speaker really says **`you wanted to use`** | **automation RIGHT, human golden WRONG** |
| `2YCaBqP8muw` @ 4:08.43 | **`Claude` is spoken clearly** | regression CONFIRMED, and the worse variant |
| `2YCaBqP8muw` @ 2:00.87 | a very short pause, no word clipped | pad safe, but running at the edge |

**The retraction matters more than the confirmation.** The `DmgujoZ1mmk` case was recorded above,
and adjudicated by an independent reviewer, as collateral damage — a clean sentence degraded by
widening. It was the opposite: the windowed re-ASR **corrected an error the human made** during the
manual repair. So:

- **Widening is not purely a liability.** It rewrites unflagged neighbours, and at least once that
  rewrite was an improvement. The `[warn] collateral edit` line is correctly framed as *look at
  this*, not as *this is damage* — do not "fix" it into a rejection.
- **The golden fixture's ground truth is a human's manual work, and it contains at least one
  error.** "Differs from the human" is therefore not a synonym for "wrong", and the 5-of-12 recall
  figure inherits that softness. This is the second independent reason to distrust the fixture's
  provenance (see below) — treat it as a strong signal, never as an oracle.
- Net over the 5 derived windows: **one confirmed regression, one confirmed improvement**, the rest
  matching or benign. The alarm in this entry's opening stands as a description of the FAILURE MODE,
  not of the hit rate.

**The confirmed regression is the bad kind.** `Claude` is enunciated clearly, and the clipped window
still mis-heard it while both readings agreed. So this is not "hard audio decoded differently" — it
is context loss on clean speech, exactly as the trade above predicts.

**Targeted fix now motivated by evidence, not theory.** `faster_whisper.WhisperModel.transcribe`
(1.2.1, verified installed) accepts `hotwords` and `initial_prompt`. Seeding the window call with
proper nouns harvested from the surrounding transcript would restore the lexical context the clip
threw away. Crucially this is NOT a re-run of the thing we disabled: `condition_on_previous_text`
loops because it feeds the model's OWN rolling output back to it, whereas a fixed hotword list adds
no autoregressive path. Cheap, and it attacks the measured failure directly. Not built — roadmap.

**The pad is safe but has no margin.** At 2:00.87 the inter-sentence pause is short, and
`CLIP_PAD_SEC = 0.25` consumes essentially all of it. No word is clipped — `clip_span` clamps t0 to
the previous sentence's end, so a shorter gap simply yields a smaller shift — but note the
downstream consequence: the repaired unit gains 0.25 s and the PRECEDING unit loses that much
inter-unit pause in `assemble`, i.e. a marginally higher `atempo` on one segment. Benign today;
worth remembering if the pad is ever raised.

**Fixture provenance — two discrepancies, unresolved, flagged rather than smoothed.** This file
records `RyvXxApfHkk#11` at 246 ch/s; the preserved backup measures 35.9, which is below the 39.36
POST-repair batch maximum. That backup may therefore not be the true pre-repair state. And this file
says "7 repairs" where the on-disk pre-vs-ground-truth diff contains 12 distinct blocks, 6 of them
in `W4Ua6XFfX9w` alone (whose ground truth is hand-spliced window repair — its first 16 sentences
are byte-identical in text AND timestamps to the pre-repair file, so it was never fully re-ASR'd).
Both numbers above are computed from what is on disk. **Treat the recall figure as approximate and
the 246 ch/s record as suspect until someone reconciles them.**

## 2026-07-19 — F5 speedup: the full lever ledger, including the ones that do NOT exist

> **SUPERSEDED 2026-07-25** — the F5/ESpeech engine was removed (see "Silero becomes the ONLY
> engine"); every lever below is unreachable. Kept for the levers proven NOT to exist, which is
> the half that would otherwise be re-investigated from scratch.

Roadmap item 1 named four levers. Two of them were already done by somebody else and one cannot
run on this host — findings that cost a day to establish and would cost another day to re-derive.
This table is the point of the entry: **half the value of this work is knowing what not to try.**

| Lever | Verdict | Why |
|---|---|---|
| `f5_nfe` 48 → 16 | **ADOPTED**, 2.16× per unit | Cost is exactly linear in nfe (Euler, one DiT forward per step). 16 is EPSS-tuned; 48 and 32 both fall through to naive `linspace`, so the once-planned 48→32 was the one step down the library gives no help with. Ear-checked on a full video. |
| stage-major batch | **ADOPTED**, ~72 s/video → ~72 s/batch | Model loading was a quarter of those stages' wall clock. Byte-identity verified 39/39. |
| half precision (fp16) | **ALREADY ON** — no lever | `f5_tts` casts the model itself for vocos on sm≥7 (`utils_infer.py:191-198`); the fp32 checkpoint is cast down at load. The vocoder deliberately stays fp32 (`utils_infer.py:507` lifts the mel back). Nothing to enable; bf16 pointless since fp16 has run in production for 13 workdirs. |
| `torch.compile` | **UNAVAILABLE on this host** | No Triton in `.venv-f5tts`, and `torch/utils/_triton.py` returns False on ImportError, so inductor cannot build CUDA kernels. Not a tuning problem — do not design around it. Would need a Triton-on-Windows story first. |
| cross-unit batching | **MIRAGE** | `infer_batch_process` builds a batch of ONE per text (`utils_infer.py:483`) and merely threads them onto one CUDA stream. Real batching needs `attn_mask_enabled=True`, which our `MODEL_CFG` leaves False (`dit.py:189`) — short units would attend over the longest unit's padding, which is WRONG OUTPUT, not a numerical delta. Enabling it materialises a b×heads×n×n mask the library itself warns against without `flash_attn`, which is not installed. |
| TF32 | placebo | Only affects fp32 matmuls; the DiT is fp16. |
| `cudnn.benchmark` | likely harmful | Input shape changes almost every unit (duration is derived from text bytes), so it would re-search algorithms per shape. |
| SDPA / `no_grad` / `inference_mode` | already in use | `no_grad` is doubled (`cfm.py:83` decorator + `utils_infer.py:496` context). At batch=1 the mask is None, so the fast kernel already applies. |
| VRAM parking (model→CPU between videos) | **NOT NEEDED** | Solved more generally by stage-major, which makes peak VRAM the MAX over models rather than their sum. Kept as a concept only for a future route that needs Gemma co-resident. |
| shorter reference clip | **DEFERRED**, bundled with the narrator swap | Real: F5 denoises `ref + gen` and discards the ref part (`utils_infer.py:508`); ref is 9.164 s against a ~7 s mean unit, so over half the compute is thrown away. But it MULTIPLIES with nfe — after 16 it is worth ~158 s/batch instead of ~477 — and it changes speaker conditioning, i.e. the voice, so it needs an ear session that the rights-clear narrator replacement already owes. |
| demucs multi-file invocation | **DEFERRED** with reason | Worth ~13.2 s × N (the stage is nothing but model loading — slope against audio length is R²=0.000). Its CLI takes several files per call, but that needs the batch known upfront, which fights per-video resume. Needs a `Stage` protocol change; not worth it inside this change. |

**Meta-lesson, the one worth carrying to the next optimization.** Four levers were named from
reading our own config comments. Investigation showed two were already applied by the library, one
was impossible, and one was structurally wrong — and it surfaced a fifth (EPSS) that nobody had
named, which turned out to be the one that mattered. **Read the dependency's source before planning
against its knobs.** The `~30% faster` note that sat in `overdub.toml` for weeks was both an
overstatement (23-26% at stage level) and pointed at the wrong step count.

## 2026-07-19 — Measurement gotchas that cost time and will recur

Recorded because each one silently produces a WRONG number rather than an error.

**Resumed runs poison `stage_s`, and nothing in the JSON says so.** 5 of 12 workdirs have
`timings.json` values covering only the units re-rendered in the last session (`DmgujoZ1mmk`:
71.9 s for 31 units when only 12 were fresh). Visible ONLY by comparing segment wav mtimes against
the timings file. Anyone regressing over all 12 rows gets garbage. Filter to cold single-session
workdirs first.

**Regression cannot split fixed from marginal cost here — direct measurement can.** Predictors are
collinear (r(calls, audio_s)=0.977), so the two-predictor coefficient flips sign, and the intercept
swings −11.7 → 140.3 s on dropping one point, with standard errors of 33-53 s on a ~35 s quantity.
Do NOT quote a regression intercept as the startup cost. What worked: `engine.synthesize` renames
its tmp file, preserving mtime, so `stage_s − (last_mtime − first_mtime)` isolates the fixed cost
directly — 34.8 s median, range 29.3-36.0 over 6 videos, independent of unit count.

**A saturated metric predicts a clean table, which is not a pass.** Round-trip similarity has no
room left to move (corpus median 0.995, min 0.924, zero units under the 0.9 gate, zero reseed
retries ever fired). A green metric table was the PREDICTED outcome of the nfe sweep and carried
almost no information. Worse, sim ROSE slightly at lower nfe — a flatter reading is easier for ASR,
so the direction is not even monotone in quality. Any harness in this regime must say so in its own
output rather than let green numbers imply a verdict.

**Blind A/B needs a positive control.** Without rows whose correct answer is known, "cannot tell"
is indistinguishable from a broken bench playing the same file on both sides — and the decision
rule (indistinguishable ⇒ adopt the faster setting) would then ship a degraded default off a test
that never played the candidate.

**Adversarially review a measurement BEFORE spending the GPU time.** The review of
`exp_nfe_sweep.py` found five must-fix issues, two of them unrecoverable after the fact: a stratum
that ranked by text LENGTH and so selected AGAINST its own property (the corpus's 41%-Latin unit
was excluded; selected density 0.022 vs the pool's 0.056), and a missing per-cell timestamp without
which the block-order/thermal confound could never be estimated. Same discipline that the rejected
`no_repeat_ngram_size` sweep taught the hard way.

## 2026-07-19 — stage-major is the default batch order; STOP no longer lands on a video boundary

**Decision.** `--batch` runs stages outer / videos inner. The old order stays behind
`--video-major`, not as a deprecation path but as a genuine escape hatch: it shares
`run_pipeline`, `_export_output` and `_summarize` with the new driver, so it can isolate an
ordering bug from a stage-contract bug. Flag name rejected alternatives: `--no-stage-major`
(double negation in `dest` and at every use), `--legacy-order` ("legacy" promises a removal that
is not coming), `--per-video` (not paired with the default's name), `--serial`/`--sequential`
(both orders are sequential — it hints at parallelism that does not exist).

**Accepted cost: the first finished MKV now arrives near the END of the batch.** These are
overnight runs; throughput is what matters. Any design that trades throughput back to get an
early first output was rejected on that ground.

**STOP now halts the batch in a HETEROGENEOUS state — write this down, it is the surprising one.**
`check_stop` CONSUMES the file at honor time, so exactly ONE (stage, video) pair can ever observe
a given STOP. Under video-major that landed on a whole-video boundary. Under stage-major it lands
mid-sweep, so the batch stops with (say) 12 videos transcribed, 5 translated and 0 synthesized.
The driver therefore breaks BOTH loops and marks every still-pending job `stop` with
"not reached (stopped at 'X')" — continuing to the next video would leave the rest of the batch
running against an already-deleted STOP, i.e. the stop silently un-honored for 11 of 12 videos.
Re-run is safe: `check_stop` fires BEFORE the stage body, so a stopped video left no partial
artifact, and resume is per-(stage, video) re-evaluation of `done()`.

**Why a session and not batch-long residency.** A model's lifetime is one stage sweep, so peak
VRAM is the MAX over models rather than their sum — which is precisely what lets the local Gemma
route (~8-9 GB) keep the whole budget with no parking or eviction policy. Nothing is pinned across
a stage boundary. Consequence accepted: whisper-small goes 2N loads → 2 per batch, not → 1;
getting the last one would mean holding 0.5 GB alongside Gemma to save ~1.5 s. No.

**Two independent mechanisms protect the next video from a dead F5 worker,** and neither subsumes
the other: `begin_video()` covers the SUCCESSFUL path (a `TtsEngineError` is caught per unit, never
escapes, and would otherwise leave a nonzero crash count behind), while `session.clear()` on a
failed stage covers the POISONED path (a `TtsFatalError` escapes and the engine object is thrown
away whole). `clear()` is deliberately called OUTSIDE the `except` block — while a handler is
active the traceback pins the stage frame and every model local to it, so collecting there frees
nothing.

**Engine cache key = `synth_key(cfg)` + resolved `f5_python`.** `synth_key` is the project's
canonical "what changes rendered audio" fingerprint and carries an INVARIANT that every new
audio-affecting knob enters it, so reusing it means this key cannot silently fall behind. It is
wider than worker identity (seed/speed/floor/ceil are per-request), which costs nothing since cfg
is loaded once per process. `f5_python` is appended because `synth_key` does NOT cover it and a
different venv is a different worker process. Recomputed per video on purpose: it hashes the
ref-audio BYTES, the only thing that would notice a narrator reference rewritten mid-batch.

**Demucs multi-file input: DEFERRED, with reason.** Its CLI takes several files per invocation and
its slope against audio length is statistically zero (R²=0.000), so the whole win is model loading
— but collecting it needs `run_batch(ctxs)`, i.e. extending the `Stage` protocol for one stage, and
it fights per-video resume head-on (`done()` gates on a per-video `source_bed.wav`; one call for 12
files is all-or-nothing inside that window). Ceiling is 13.2 s × (N−1) ≈ 2.4 min on 12 videos.

## 2026-07-19 — `f5_nfe` 48 → 16 ADOPTED; and two of four speed levers were already dead

> **SUPERSEDED 2026-07-25** — F5 was removed; `f5_nfe` no longer exists in the config or the
> code. Kept for the two levers measured dead, so they are not re-proposed.

**Ear verdict (user, full 5.7-minute video `RyvXxApfHkk`, nfe=48 vs nfe=16 side by side):** the
only defects heard — noise and odd intonation — are present in the nfe=48 render TOO, so they are
properties of the engine and the input, not of the step count. Adopted.

**Why 16 and not the 32 the roadmap had planned.** Cost is EXACTLY linear in nfe (Euler solver,
one DiT forward per step — `torchdiffeq/fixed_grid.py`), but `CFM.sample` runs `use_epss=True` by
default and `get_epss_timesteps` (`model/utils.py:206-218`) carries tuned schedules ONLY for
n in {5,6,7,10,12,16}; everything else falls through to a naive `linspace`. So **48 and 32 are
both untuned**, and the planned 48→32 was the one step down that buys no help from the library,
while 16 is a designed operating point at 3× fewer forwards. Measured over 40 real production
units × 4 step counts: 48→32 = 1.43×, 48→16 = **2.16×**, 48→12 = 2.29× — 12 adds only 6% over 16
and sits at the edge of the tuned grid, so 16 is the pick.

**Metrics could not sign this off, and said so up front.** Round-trip similarity is saturated in
this regime (corpus: median 0.995, min 0.924, zero units under the 0.9 gate, zero reseed retries
ever fired), so a clean table was the PREDICTED outcome carrying almost no information — the
harness prints that warning rather than letting green numbers imply a verdict. sim even rose
slightly at lower nfe, which means nothing: a flatter reading is EASIER for ASR. Same lesson as
id101 (sim 1.0, judged bad by ear, 2026-07-16).

**What the run did prove objectively:** timing math is untouched. Max combined compression
identical to 3 dp (1.292 vs 1.292) and the dub track byte-identical in length, exactly as
predicted — F5's duration canvas and `plan_speed` are both nfe-independent by construction.
Determinism was also re-verified as a falsifiable premise: 12/12 cells byte-identical on re-render
across BOTH schedule paths (naive at 48, EPSS at 16), which is what licensed the no-repeat-cells
design in the first place.

**Two levers PLAN named turned out not to exist.** (a) *Half precision* is already on — f5_tts
picks fp16 itself for vocos on sm≥7 (`utils_infer.py:191-198`), the checkpoint is fp32 and gets
cast down at load; the vocoder stays fp32 deliberately. (b) *torch.compile* is unavailable: no
Triton in `.venv-f5tts`, so inductor cannot build CUDA kernels on this host. Also placebo here:
TF32 (the DiT is fp16), `cudnn.benchmark` (input shape changes per unit), SDPA/no_grad (already
used, doubly). (c) *Cross-unit batching* is a mirage — `infer_batch_process` builds a batch of ONE
per text and merely threads them; real batching needs `attn_mask_enabled=True`, which our
`MODEL_CFG` leaves False, so short units would attend over the longest unit's padding (wrong
output, not a numerical delta), and enabling it materialises a b×heads×n×n mask the library itself
warns against without flash_attn, which is not installed.

**What remains, re-ranked.** The reference clip is the next real lever: F5 denoises `ref + gen`
and then DISCARDS the ref part (`utils_infer.py:508`), and the ref canvas is 9.164 s against a
~7 s mean unit — over half the compute is thrown away. But it MULTIPLIES with nfe, so adopting 16
first cuts its value from ~477 s to ~158 s per 12-video batch, and it changes speaker conditioning
(i.e. the voice), so it is bundled with the rights-clear narrator replacement rather than run as
its own ear session. Harness kept at `scripts/exp_nfe_sweep.py` (`--pages-only` regenerates the
blind A/B pages with no GPU).

## 2026-07-19 — The VRAM rule is a budget, not a prohibition

**Changed in CLAUDE.md:** "Never load two heavy models at once; explicit model unload between
stages" → keep the resident total under 12 GB and account for it.

**Why the old rule was wrong in general and right in one case.** Measured sizes: whisper large-v3
~3.1 GB, htdemucs ~3.0, F5 worker ~0.8, whisper-small ~0.5. All four resident is ~7.4 GB of 12 —
it fits with ~4.6 GB spare. The single model that creates the squeeze is Gemma-3-12B at ~8-9 GB.
So the blanket prohibition generalised one model's size into a law, and that law was blocking
model reuse across a batch for no VRAM reason at all.

**What it was costing.** Per-video fixed cost measured by regression over 12 workdirs: transcribe
~22.2 s (large-v3 load), synthesize ~34.8 s (worker spawn + model), separate ~13.2 s, verify
~1.5 s — about 72 s per video, ~13 minutes on a 12-video batch, roughly a quarter of those stages'
wall time. `separate` is the starkest: its slope against audio length is statistically ZERO
(R²=0.000), i.e. the stage is nothing but model loading. whisper-small is also loaded TWICE per
video today (synthesize's reseed verifier, then verify).

**The rule is relaxed, but the preferred fix is stage-major batching, not residency.** Running the
batch stage-outer/video-inner makes peak VRAM the MAX over models instead of their sum, so each
model loads once per batch and the Gemma route stays safe without any parking or eviction policy.
It also keeps a model's lifetime inside one stage, avoiding the failure-isolation trap of a
batch-scoped engine (today a dead worker kills one video; a cached one would poison the next).
Known costs, to be handled rather than dismissed: export moves after the mux stage, STOP is checked
per (stage, video), per-video status must survive across stages so one failure does not cascade,
and the first finished MKV arrives near the END of the batch instead of after ~5 minutes — fine
for overnight runs, worse for a two-video run, so it should be `--batch` only.

## 2026-07-19 — `no_repeat_ngram_size` REJECTED; and the guard threshold's separation is gone

**Measured, not argued: 60 ASR runs** (3 videos × n in 0/4/5/6 × 5 repeats), scoring floor ratio,
adjacent duplicate sentences, and word count vs the n=0 baseline.

**No consistent direction, so it is not adopted.**
- Severe (`4szRHy_CT7s`) — the only win: floor 11.07% → 8.2%, dups 2 → 0 at n=6; words −1.1/−1.3%.
- Borderline (`RyvXxApfHkk`) — WORSE on every axis: floor 6.13% → 13.51%, dups 0 → 2, words +11.5%.
  More words *with* more duplicates means the ban did not suppress the loop, it pushed the decoder
  into a different repeating shape.
- Healthy control (`Y0KidGr9Z2Y`) — n=4 damages a clean video: 0.13% → 4.44%.

A knob that helps one source, harms another and destabilises a third is not a fix.

**The third axis was badly designed, and that is worth recording.** "Word count drops ⇒ the ban ate
real speech" is ambiguous exactly where it matters: removing a duplicated sentence ALSO drops the
count, and that is a win. So the −1.3% on the severe video is unreadable — it could be the deleted
duplicate or eaten text, and this metric cannot tell them apart. Settling this properly needs a
CONTENT comparison against a reference transcript, not a word tally.

**Bigger finding — the guard threshold's "clean separation" does not survive more data.** The
n=0 cells are a second, independent 5-run sample of the same three videos. `RyvXxApfHkk` reached
**15.82%**, above the severe video's whole range (9.3-11.9%) and more than double its own maximum
in the earlier session (7.52%). The 7.52 → 9.33 pp gap that `transcribe_floor_run_max = 0.085`
was calibrated into does not exist at n=60. The threshold stays PROVISIONAL and its comment
understates the problem: this is not a narrow gap, it is overlapping populations. The guard
remains justified as catastrophe insurance (the severe video is above threshold in every sample
ever taken) and is confirmed unreliable for borderline cases. Recalibration must come from the
`asr.floor_ratio` series now accumulating in run.json, not from another hand-run probe.

## 2026-07-19 — Triage signal: narrow `refusal`, and stop advisory flags from deciding it

**`translate:refusal` was matching ordinary prose.** The pattern `как (?:ии|модель|языковая)`
was written for the Gemma route, where refusals are real. But "как ИИ" is also plain "how AI",
and on AI-subject content that is everywhere: ALL SIX refusal flags in the 12-video AI-Fluency
batch were false — e.g. "по мере того, как ИИ продолжает развиваться". Narrowed to require the
first-person clause a real refusal carries (`как ИИ, я …`). "языковая модель" alone is likewise
not a marker in this domain ("работает как языковая модель" is a normal sentence). Validated: 0
false positives on all 6 real cases plus 2 constructed traps, 0 misses on 8 genuine refusals in
both languages. All 12 translations rebuilt; refusal flags went 6 → 0.

**The deeper problem was not the regex — it was pooling.** `needs_triage` was
`any flag at all > 0`, so `speed ×8.79` (unintelligible audio) and `entity_loss` on the surname
Дейкин (cosmetic) carried identical weight. The batch reported **11 of 12 videos needing a
look**, which conveys exactly as much as reporting none. Fixing the regex alone would only have
made it 10 of 12.

**Completeness flags are now split by what a human can act on.** `entity_loss` and
`length_short` are ADVISORY: still counted, still printed, but they no longer decide
`needs_triage`. This is not a workaround — completeness.py's own docstring names personal-name
Russification as `entity_loss`'s dominant IRREDUCIBLE false positive (no cheap brand-vs-person
discriminator exists) and calls `length_short` the deliberately coarse weak signal. Narrowing
the detectors instead would trade a real loss class (a dropped brand name) for quieter output.
`num_loss` and `neg_loss` stay actionable — an inverted negation is the most dangerous silent
loss there is, and one false positive per batch is a fair price for never missing one.

**Result: 11 → 2 videos needing triage** on the same run data, and the two left are real
(a `neg_loss`, and an `english_echo` that would send Latin script into the synthesizer).
`run.json` now carries `flags_actionable` / `flags_advisory` alongside `flags_total`, so the
advisory stream stays available for trends without polluting the decision.

## 2026-07-19 — Silero v5 audition: v4 was tested BY MISTAKE; v5 is the fast fallback

**The 2026-07-15 bake-off tested the wrong release.** `v4_ru` was already superseded when it was
adopted; the adapter then hardcoded it, so every Silero verdict in this file up to now describes
an outdated model. `v5_5_ru` is audibly better and is now the default. v4 stays reachable only to
reproduce pre-2026-07-19 runs.

**Ear ranking (user, 5 videos × 5 voices, one voice per video, v5_5_ru):**
- **kseniya, eugene — best.** These are the two to use.
- **xenia** — good voice, slightly unpleasant.
- **aidar, baya** — off-standard accent, sounds harder to follow; phonemes drift from ordinary
  Russian. Avoid.

**Verdict: quality is below F5/ESpeech and the user accepts that trade for speed, for now.**

**Speed is the headline: synthesis is 12-19× faster and CPU-only.** Measured on the same
translations as the F5 run (5 videos): synth 11-14 s vs F5's 128-250 s; whole-pipeline RTF
0.14-0.17 vs 0.70-0.92. Synthesis stops being the bottleneck (verify and separate now dominate)
and the GPU is left free. Objective quality is near parity — mean round-trip similarity
0.979-0.992 vs F5's 0.985-0.991, zero verify flags, zero segments over ×1.8, `xenia` fully clean.
The old worry that Silero would trip the 0.9 gate did NOT reproduce: sample min was 0.920. That
worry was measured on v4 — another consequence of the wrong-release mistake.

**Metrics did not predict the ear here, again.** 0.99 similarity means "the words are present",
not "it sounds good" — the id101 precedent (sim 1.0, judged bad by ear, 2026-07-16) holds. The
three defects below are all invisible to every metric the pipeline computes.

**Three defects found by ear, none of them caught by verify:**
1. **Noise / hiss, "cheap microphone", voices do not ring** like a trained announcer. Candidate
   fix is post-processing — denoise, compression, EQ — not an engine change.
2. **No expressiveness.** Tone never varies; sentence after sentence lands on the same contour and
   the result is soporific. v5_5 is reported to support varied intonation; unexplored.
3. **Dub lags the subtitles and the English speech.** MEASURED asymmetry against the F5 baseline:
   clip-duration/source-span median 0.93 and 0.87 (Silero) vs 0.98 and 0.98 (F5), with more units
   overflowing the slot (7 vs 4, and 7 vs 0). Mechanism: Silero declares `supports_target=False`,
   so nothing asks the engine to hit the source span — F5 receives `target_sec` = the span and
   lands on it natively, while Silero renders at its own pace and only assemble's `atempo`
   intervenes, and only once a clip exceeds the SLOT (span + following pause), never the span
   itself. Inside a grouped unit the per-sentence offsets then drift both ways. The user's own
   proposed remedy — tempo-fit the already-rendered chunk — points at exactly this: fit to the
   SPAN, not only to the slot, for engines without native targeting. NOT yet fixed.

**Migration cost was small, and the code stays.** Two changes: `cfg.silero_model` (release id
passed to `torch.hub`, replacing the hardcoded `MODEL_ID`) and — load-bearing — that id added to
`synth_key`. Without the second, v5 would have silently reused v4 wavs under the same voice name:
the exact silent-staleness class the `synth_key` INVARIANT exists to prevent. The v5 Cyrillic-only
caveat needed no filter: `text_tts` is Cyrillic by contract and measured clean (0 Latin characters
across all 12 batch videos), because the pronounce chain transliterates kept-Latin names before
synthesis. Full suite green.

**Production default stays F5.** This audition changes the fallback's identity and quality, not
the primary engine.

## 2026-07-19 — Collapsed ASR alignment: guard the cause, not the harm

**The defect.** `4szRHy_CT7s` dubbed one slot at 294 char/s (atempo ×8.79, unintelligible).
Root cause sat two stages upstream of the symptom: `condition_on_previous_text=True` fed
whisper's decoder into a repetition loop, which took the word alignment down with it. Whisper
returned unusable word timings, `flatten`'s monotone clamp + `MIN_WORD_DUR` floor manufactured
plausible-looking ones (0.02 s per word, 44 in a row), and every stage below trusted them. The
floor is correct — a zero-length word divides by zero in atempo — but it converted "no timing"
into "false timing" and recorded nothing.

**Timings are an input to SYNTHESIS, not just to assembly.** F5 receives each unit's span as a
native-speed target (`supports_target`), so a collapsed stretch makes the engine compress until
it DROPS words — `unit_sim_threshold` exists precisely because compression ≥~1.3 loses words
while ASR similarity still scrapes past the base gate. So bad timings cost lost speech, not
fast speech, and verify can miss it. That is why the guard must sit at transcribe.

**Guard the cause.** Downstream harm cannot be predicted at transcribe time: it depends on the
Russian text (which does not exist until translate) and on unit grouping absorbing free gaps —
measured, a sentence at 178 char/s still finished at ×1.37 because the following gap swallowed
the spill. So `floor_run_ratio` scores the DATA defect (chained floor-stamped words) and
`_guard` re-runs once with context feedback off, keeping the retry only if it at least halves
the ratio (the flag earns its keep on punctuation — see 2026-07-17 — and a marginal win does
not justify losing it).

**Whisper is not deterministic here, and that reframes the threshold.** `temperature` is a
fallback LIST, so the decoder samples and the same audio yields different transcripts per run.
Measured over 5 repeat runs each of 3 videos: severe 9.33–11.38% (fired 5/5), mid 3.82–7.52%,
"clean" 0.00–7.46%. The control video — 0.0% on its original run — hit 7.46% with a 30-word
chain on run 3. There is no such thing as a sick VIDEO, only a sick RUN. The first threshold
(0.06) would therefore have fired on a healthy source and traded away punctuation for nothing;
it is now 0.085, inside a separating gap only 1.8 pp wide on n=5 and marked PROVISIONAL.

**Consequence accepted:** the guard is reliable insurance against a CATASTROPHE (severe case
caught 5/5) and unreliable as a borderline detector (mid case 2/5). Claiming otherwise would be
false. `run.json` now carries `asr.floor_ratio` on EVERY run so the threshold can be recalibrated
from a real distribution instead of single samples.

**Still open:** `no_repeat_ngram_size` / `repetition_penalty` are at library defaults (0 and 1 —
i.e. off). They attack the repetition loop that FEEDS the temperature fallback, so they are the
only lever that could narrow the run-to-run spread rather than catch its tail. Not adopted
blind: a too-small n mangles legitimate repetition silently, which is the forbidden class.

---

# ARCHIVE — the founding period (2026-07-15 → 07-19), in FORWARD order

Everything ABOVE this line runs newest-first. Everything BELOW runs oldest-first: it was written
as a build journal over the first five days and never re-sorted. The two halves overlap on
2026-07-19, so an entry from that date can be in either.

The split is documented rather than fixed because re-sorting 1100 lines of the repo's most
load-bearing document buys ordering and risks content. The index at the top is the lookup path;
physical order is not.

**Append new entries directly below the `---` that closes the Index, never here.**

## 2026-07-15 — Founding decisions

**Local-only pipeline.** Target volume is hundreds of hours; cloud TTS pricing
(ElevenLabs ≈ dollars per 20 min) makes remote synthesis economically absurd at
this scale. Local compute is a sunk cost. Trade-off accepted: local Russian TTS
quality is below ElevenLabs.

**Chatterbox Multilingual as the first TTS engine.** MIT license, actively
developed (Resemble AI), voice cloning + emotion control, strongest English
results in blind tests. Known risk: Russian is 6–7/10 with slight accent
artifacts. Silero (native Russian, flat but bulletproof) and XTTS-v2 (best
Russian among cloners, but dead project) come later behind a common interface.
If Chatterbox Russian fails the ear test — switch, don't polish (see PLAN kill
criteria).

**Timing strategy: per-segment TTS + atempo up to x2.** Russian runs 15–25%
longer than English; an x2 compression budget covers ~99% of segments. The user
validated by ear that x2 is acceptable. No smarter time-borrowing logic in v1.

**Local translation (Qwen3-14B via Ollama).** Operationally simpler than cloud
(no keys, no billing, offline), free at any volume. Quality loss vs frontier
models is acceptable for a dubbed track; upgrade path is a URL swap since
Ollama speaks the OpenAI protocol.

**ASR round-trip verification for every TTS segment.** Neural TTS hallucinates
(skips, repeats, mumbles). At hundreds of hours nobody will listen for defects
— the pipeline must catch them itself. Whisper-small transcribes each generated
segment; text mismatch → regenerate with a new seed.

**MKV container with dual subtitles.** Transcript (EN) and translation (RU)
already exist as pipeline artifacts — embedding both as subtitle tracks is
free. MKV over MP4: native SRT support, multiple audio tracks without
container quirks.

**Single-speaker assumption for v1.** Covers ~95% of target content.
Diarization (whisperX + pyannote) would multiply complexity by 2–3x — deferred
until actually needed.

**Rejected: Microsoft local voices.** Windows Narrator natural voices have no
ru-RU voice at all (verified 2026-07); legacy SAPI5 "Irina" is unusable.
Neural Dmitry/Svetlana are cloud-only (edge-tts) — violates local-only.

**Name: overdub.** Real audio-engineering term — laying a new track over an
existing recording, which is literally the final pipeline step.

**Voice cloning first, fixed voice as rollback.** Phase 1 clones the original
speaker (Chatterbox, short reference clip from source audio). This is the
riskiest quality axis — accent artifacts are strongest when cloning from an
English reference — but the payoff (preserved speaker identity) is highest, and
the rollback is trivial: one fixed Russian voice for everything. Decide by ear
after Phase 1; per kill criteria, don't tune reference clips endlessly.

**Custom orchestrator instead of pyVideoTrans / VideoLingo / Pandrator.**
Ready-made dubbing tools cover the happy path but not this project's core
requirements: ASR verification loop, resumable hundred-hour batches, dual
subtitle embedding, local-only pluggable TTS. They stay useful as reference
implementations for stage wiring and edge cases:
[pyVideoTrans](https://github.com/jianchang512/pyvideotrans),
[Pandrator](https://github.com/lukaszliniewicz/Pandrator).

## 2026-07-15 — PoC reframe and timing simplification

**Project stage: research / proof of concept.** Goal is a turn-key pipeline
(URL in → MKV out) proving feasibility; speed and quality must be acceptable,
not production-grade. Kill criteria removed from PLAN — nothing gates; results
are evaluated by ear at the end of Phase 1.

**No tempo cap (supersedes founding x2 decision).** Segments are sped up as
much as their slot requires, at assembly. The translation-shortening feedback
loop is dropped entirely — a few audibly broken segments per video are
acceptable losses for a PoC. Verification runs on raw audio before atempo, so
speed-up never pollutes the verify loop. Per-segment speed factor is logged in
the run report for triage (factor > ~1.8 ≈ candidate for "broken"). The
keep-length prompt instruction stays — it keeps typical factors near 1.0–1.4
for free.

**Context-aware sentence translation.** Whisper segments are not translation
units — they cut mid-thought and lose coreference. Word timestamps → sentence
re-segmentation → sentences translated in order with a rolling context window
(previous EN sentences + their RU translations). Rejected alternative:
whole-transcript translation — better prose, but re-aligning free-form RU text
to timestamps is a hard problem; 1:1 sentence mapping keeps sync trivial.

**Two text fields per sentence.** `text_ru` (raw translation → subtitles) and
`text_tts` (normalized: numbers/acronyms/Latin → Russian words → TTS input).
ASR verification compares against `text_tts` with the same normalizer applied
to both sides — comparing whisper output against raw text would loop forever
on every normalized token ("джи-пи-ю" vs "GPU").

**Per-video loop for PoC.** The stage runner processes one video through all
stages (≈3 model load/unloads per video — minutes of overhead, noise next to
synthesis time). Per-stage batching (one model load per stage per batch) is
deferred to Phase 2; artifact-driven resumable stages make the switch a loop
reorder, not a rewrite.

**VRAM constraint amended.** whisper-small (~0.5 GB) is co-resident with the
TTS engine during synthesis + verification; the one-heavy-model-at-a-time rule
applies to whisper large-v3 / Qwen3-14B / TTS.

**EN→RU fixed.** Source is always English, output always Russian. No language
detection or multi-language handling anywhere in the pipeline.

## 2026-07-15 — Stack verification (pre-code multi-agent research pass)

Verified the whole stack against primary sources before writing pipeline code
(5 researchers + adversarial refutation of risky claims + synthesis, ~960k
tokens). Full reference: STACK.md, SETUP.md. Decision-relevant outcomes:

**Chatterbox EN-ref → RU: CONDITIONAL GO, not settled.** Mechanics verified —
Russian is officially supported, `ChatterboxMultilingualTTS` + `generate()`
signature confirmed, V3 checkpoint loads, 0.5B fits 12 GB. But the core value
proposition — an English reference producing natural Russian — is REFUTED in
its strong form: Resemble AI's own docs state a language-mismatched reference
inherits its accent *by default*, and `cfg_weight=0.0` only *minimizes*, never
eliminates, the bleed. Issue #360: even a native RU reference drifts to an
English accent + broken stress after ~5 generations. No ear-test / round-trip
evidence for EN-ref→RU exists. Day-1 is therefore a load-bearing A/B ear test
(EN-ref vs RU-ref × cfg_weight 0.0/0.5), not a formality. Fallback if EN-ref
fails: fixed RU reference (loses same-voice) or Silero/XTTS behind the adapter.
The per-segment ASR round-trip is exactly the safety net for this — it's why
CONDITIONAL and not NO-GO.

**Corrections that change implementation:**
- Chatterbox 0.1.7 `from_pretrained` takes only `device` — the researched
  `t3_model="v3"` arg does NOT exist in this version (verified live via
  inspect.signature; the research over-inferred it). Corrected in code + STACK.
- Chatterbox hard-pins `torch==2.6.0` / `transformers==5.2.0` → isolated TTS
  venv (`.venv-tts`); ASR stack in `.venv-asr`. Forced by Chatterbox's pins,
  not by whisper (faster-whisper + torch can share one venv).
- Qwen3-14B Q4_K_M in 12 GB is knife-edge: pin `num_ctx` ≤ 8K (4K per segment).
  Ollama preallocates KV for the *full* num_ctx, and Windows sysmem fallback
  turns overflow into a silent 5–30× slowdown, not a clean OOM.
- faster-whisper does NOT "never OOM" — batching can hit 19 GB; keep batch/beam
  conservative. Windows CTranslate2 needs `os.add_dll_directory` for cuDNN 9.

**Refuted worries (safe to rely on):** Ollama `/v1` honors `seed`; `qwen3:14b`
carries the think toggle (thinking goes to `message.thinking`, not `content`) —
keep the regex strip only as a fallback; atempo equal-split keeps exact duration.

**RTF is unmeasured** on the RTX 4080 Mobile for every GPU stage (only
third-party / different-GPU numbers exist) — measure on host before trusting
the x5 throughput budget.

## 2026-07-15 — Day-1 engine bake-off: Chatterbox rejected, Silero adopted

Ran the day-1 ear test on real audio before writing pipeline code. Outcome
overturns two founding decisions.

**Chatterbox REJECTED.** Cloning from an English reference produced unusable
Russian (heavy accent + artifacts), as the vendor docs warned. Critically, even
WITHOUT a reference (built-in voice, `audio_prompt_path=None`) the Russian was
still bad — so it's the engine's ceiling, not just cross-lingual cloning. No
point tuning it. RTF was fine (~0.76–0.83 on the 4080M), but quality gates, not
speed. Incidental findings: the researched `t3_model="v3"` arg does not exist in
chatterbox-tts 0.1.7 (from_pretrained takes only `device`); `russian_text_stresser`
was unavailable so stress was skipped; several segments hit repetition/EOS-forcing.

**Silero v4_ru ADOPTED (voice `eugene`, `xenia` backup).** Native Russian, clean
and intelligible, deterministic, ~38 MB, runs on CPU at RTF ~0.02–0.3 (zero VRAM).
Host ear test of all 5 voices: eugene best, xenia acceptable; aidar/kseniya poor,
baya has sibilant hiss. Loaded via torch.hub (snakers4/silero-models), `apply_tts`
with built-in stress (put_accent/put_yo).

**Consequences (supersede founding decisions):**
- **"Voice cloning first, fixed voice as rollback" is DEAD.** Cross-lingual
  cloning on local models doesn't deliver clean Russian (Chatterbox failed; XTTS
  is the same category and would fail the same way). Same-voice premise dropped:
  every video gets one fixed narrator voice.
- **"Chatterbox Multilingual as first TTS engine" is superseded** by Silero.
- **XTTS rejected** without testing: dead project (Coqui folded), non-commercial
  license, same cross-lingual accent risk. The modern cloner, if expressiveness
  is ever needed, is F5-TTS — not XTTS.
- **The two-venv split collapses.** `.venv-tts` existed only for Chatterbox's
  torch==2.6.0 / transformers==5.2.0 pins. Silero needs only torch+torchaudio, so
  it can share the ASR venv; `.venv-tts` can be retired.
- **Verify-loop retry changes.** Silero is deterministic — a failed round-trip
  can't be fixed by reseeding. Failed segments are flagged, not regenerated.
- **VRAM budget eases.** With TTS on CPU, the only heavy-model contention is
  whisper-large ↔ Qwen; Stage 3 (Silero + whisper-small) barely touches VRAM.

## 2026-07-15 — Transcribe: word-level sentence resegmentation (BUILD, stdlib)

The sentence is the unit of translation/synthesis/timing. Chose a hand-rolled,
stdlib-only word-level resegmenter over buying pysbd: pysbd returns char spans
(forcing a fragile char→word remapping — the actually-hard part), is frozen since
2021, and the input (whisper large-v3 on English speech) is well-punctuated, so the
accuracy gap is small and a wrong boundary is bounded + recoverable (the overlong
splitter caps length; Phase-2 ASR verify catches garbage). Whisper segment ends are
demoted to a *pause prior*, used only to choose a good overlong-split cut point.

Adversarial review (multi-agent) fixed three real defects: zero-duration slots
(would divide-by-zero in atempo), 2–3× whisper stutters leaking into translation
('and and', 'situations. situations.'), and overlong-split cuts stranding bare
function words. Deferred as cosmetic: sub-word spacing ('decision -making') — Qwen
and TTS are robust to it and no timing/id contract is touched.

**Contract for the future assemble stage (surfaced by the review):** sentences.json
timings are monotone and NON-OVERLAPPING, but NOT gap-free — inter-sentence gaps are
legitimate pause headroom for the RU dub. assemble must anchor each RU clip at its
own `start`, NEVER butt-join clips, or it destroys sync and the pause budget.

## 2026-07-15 — Translate stage: design panel + review (BUILD)

> **PARTLY SUPERSEDED 2026-07-25** — the in-process Ollama/qwen translate path is gone;
> translation runs through Sonnet sub-agents (route B). Everything below about the endpoint,
> `think: false` and the sliding context window is archive. The NORMALIZER half is LIVE:
> `normalize_for_tts`, the same-function-on-both-sides verify symmetry, and the magnitude-bug
> class it was built to make visible.

Design settled by a 3-approach multi-agent panel (simplicity vs quality vs
robustness biases) + lens judges + synthesis, then an adversarial review pass.

**F1/F2 — LLM returns `text_ru` only; `text_tts = normalize_for_tts(text_ru)` in
deterministic Python.** Rejected design B (LLM emits `text_tts` too, JSON/delimited):
qwen's seed is not bit-exact, so an LLM-spelled `text_tts` would diverge from the
Python normalizer the verify stage applies to the ASR hypothesis, silently depressing
similarity on correct numeric dubs — the one silent-failure class the project forbids.
The normalizer must exist as a pure Python function for verify regardless; reusing it
as the sole `text_tts` source makes the round-trip exact *by construction*.

**F3 — inlined CONTEXT block in a single user message, only `status=="ok"` pairs**
(a failed English fallback never poisons the next sentence's context). Ollama `/v1`
is stateless per request, so multi-turn buys no server cache for a sliding window;
inlining gives exact, snapshot-testable control. One call per sentence, id order —
NO batching (batching risks a silent sentence merge/drop).

**F4 — validate → reseed+temp-bump retry → flagged English fallback, never drop.**
Append-only `translation.jsonl` (flush+fsync) for crash resume; contiguity enforced
(`raise`, not `assert` — a never-drop invariant must survive `python -O`); atomic
`os.replace`. Each record carries `src_en` so a re-tuned `sentences.json` (same id,
changed text) forces re-translation instead of reusing the stale RU.

**Endpoint correction — native Ollama `/api/chat` with `think: false`, NOT OpenAI
`/v1` + `/no_think`.** Empirically on the host: qwen3:14b ignores an in-prompt
`/no_think` on many samples, and its reasoning (routed to a `reasoning` field) is
truncated by `num_predict`, leaving `message.content` EMPTY (finish_reason=length).
The native `think: false` toggle reliably disables thinking — ~3× faster (5s vs 16s
per sentence, no wasted reasoning tokens) and cleaner output. This drops the `openai`
dependency; the stage is now stdlib-only (urllib). STACK.md's `/v1` sketch is
superseded for this stage.

**Normalization is SAFETY-CRITICAL, not incidental.** Because verify normalizes both
sides with the same code, a magnitude bug (a number voiced with the wrong value) is
architecturally invisible to the round-trip — it self-agrees and passes unflagged. So
the normalizer gets its own direct ground-truth tests, not only round-trip coverage.
The review caught three real magnitude/mangling bugs, now fixed + regression-tested:
grouped thousands read as decimals (`$1,999` → 1.999, ~1000× low; `10 000` → "десять
ноль"), decimal ranges shredded (`3.5-4.5` → "три.от пять…"), and Cyrillic `х`/`с` in
the multiplier/Celsius classes mangling ordinary Russian ("ось х 5", "90° севернее").

**num2words (ru locale) approved as a dependency** for Russian cardinal/ordinal
spelling (fiddly to hand-roll correctly); a stdlib 0..10⁹ speller stays as the
import-fallback. Accepted PoC loss: num2words yields nominative case, so oblique
numerals are occasionally voiced in the wrong case — self-consistent for verify, so
never false-flagged; audibly-rough-but-not-silent.

**Contract for downstream stages (synthesize / verify — for whoever builds them next):**
`translation.json` is a list of `{id, start, end, src_en, text_ru, text_tts,
status ("ok"|"failed"), attempts, flag?}`, id-contiguous with `sentences.json`.
- **synthesize** feeds `text_tts` (NEVER `text_ru`) to Silero — one wav per id, on RAW
  audio before any atempo. `en.srt`/`ru.srt` come from `src_en`/`text_ru`.
- **verify** MUST `from ..normalize import normalize_for_compare` and compare it applied to
  `text_tts` vs the whisper-small RU hypothesis — the SAME function on both sides, or numeric
  dubs false-flag. Silero is deterministic, so a failed round-trip is flagged, not reseeded.
- `status:"failed"` records are already flagged by translate (bad/echoed translation, EN
  fallback in `text_ru`); verify adds its own low-similarity flag on top, never overwrites.
- The 245 s/50-sentence throughput (~0.8× realtime, translate alone) is the batch-scale
  bottleneck created by the deliberate one-call-per-sentence (no-batching) safety choice —
  revisit batching FIRST if overnight runs get time-bound, not the normalizer or context scheme.

## 2026-07-15 — Pipeline tail (synthesize / verify / assemble / mux): design panel + review

Settled by a 3-bias design panel (minimalist / robust / timing-correctness) + synthesis, then a
4-lens adversarial review with per-finding refutation. The six load-bearing decisions:

**atempo slot = `[start_i, start_{i+1})`, not `[start_i, end_i]`.** Every clip is anchored at its
own absolute start, so consuming the following inter-sentence gap only delays the start of
*silence*, never the next sentence (independently anchored). `[start, next.start)` therefore
strictly dominates: it spends free pause before pitch-warping ("no tempo cap" ≠ "no effort").
Last segment: unbounded, factor 1.0 (nothing follows to protect; the dub may outlast the video —
MKV tolerates it). Shorter-than-slot clip → factor 1.0, place raw, remainder stays silent.

**Timeline = pre-allocated int16 buffer, absolute-offset disjoint blit, single per-segment
atempo.** Each clip written at `round(start*sr)` truncated to its slot → zero cumulative drift;
disjoint slots make direct assignment lossless (Silero writes PCM_16). ffmpeg 7.1.1 atempo range
is 0.5–100 as a *single* filter — no chaining ever. Rejected: streaming SoundFile writer (its
"100 h = 69 GB" is a per-*batch* strawman; one video ≤ ~700 MB int16 and streaming reintroduces
cursor-drift + butt-join complexity that absolute placement eliminates by construction);
float32 buffer (2× memory, no gain — disjoint, no summing).

**report.json is co-owned via `overdub/report.py` (merge-by-id), and `verify.done()` checks the
`"verify"` marker key — NOT `report.exists()`.** The marker fix is the highest-value guard in the
whole tail: with an existence gate, an `--only assemble` run (which creates report.json first)
would make `verify.done()` True forever → verification silently never runs, the one forbidden
failure. A single `upsert` preserving foreign keys stops verify/assemble clobbering each other;
`prune` drops phantom records after a re-tune shrinks the sentence count.

**verify similarity = char-level `SequenceMatcher(autojunk=False).ratio()`** on the two normalized
strings. Char-level tolerates Russian inflectional endings (`фреймворк` vs `фреймворка` → 0.947,
where a word-token metric gives 0.0 and false-flags every short segment), while gross skips still
move enough chars to trip 0.8. `autojunk=False` is mandatory — the default treats common Cyrillic
letters as junk on ≥200-char strings (sentences reach MAX_CHARS=240) and silently skews the score.

**synthesize uses the existing `build_engine(cfg)`** (the factory already existed — the minimalist
"hardcode Silero" was wrong); resume reuses a wav iff `text_tts` unchanged AND the prior flag is
not `synth_error` (transient errors always retry; mirrors translate's src_en-unchanged guard).

**mux dub codec = native `aac 128k` mono, RU dub as the DEFAULT track.** aac ships in every ffmpeg
build; the "external binaries not guaranteed" contract forbids gambling on optional `libopus`
(a one-flag post-PoC upgrade). Video is `-c:v copy`, non-negotiable. Atomic `.mkv.tmp` + os.replace
so a killed ffmpeg can't leave a partial output that satisfies `done()`.

**Review outcome:** 13 findings → 11 kept (ALL verified down to PLAUSIBLE/low, 0 CONFIRMED,
0 critical), 2 refuted (one misread `.strip()`; one invented a non-monotone-timing scenario the
transcribe contract provably forbids). 8 cheap robustness fixes applied — the seg_manifest guard
in verify, `sf.info` wrapped so a corrupt wav flags instead of crashing the stage (never block on
a bad segment), a loud RuntimeError on a zero-segment (speech-free) source, uncapped speed-factor
logging (the ≤100 clamp applies only to the ffmpeg arg), resume flag-carry, report.prune, a
report.load corruption warning, and a `missing_audio` flag. Deferred: download.py has no
`shutil.which` preflight (pre-existing, out of scope) → INBOX.

**Real bug found by *running* it, not by review:** `sf.write` cannot infer WAV format from an
atomic `…/NNNNN.wav.tmp` path → every segment failed `synth_error` on the first run. Fixed by
making SileroEngine write with explicit `format="WAV"`. Lesson: soundfile format inference keys on
the file extension, so any caller passing a temp/suffixless path must pass `format=` explicitly.

## 2026-07-16 — TTS bake-off #2: ESpeech (F5-TTS RU) wins by ear; voice cloning explored, EN-clone dropped

> **SUPERSEDED 2026-07-25** — ESpeech/F5 was removed in favour of Silero v5_5_ru. Kept for the
> EN-clone rejection, which is a result about the technique rather than about this engine.

**Ear verdict (user, real pipeline output on 4szRHy_CT7s):** ESpeech-TTS-1_RL-V2 with the
author's demo reference is the unambiguous leader over Silero v4 (current), Silero v5, Misha
F5-RU v2 and every cloning variant. Objective metrics agree: mean sim 0.992, 0 verify flags,
mean atempo ×1.03, 0 segments over ×1.8 — timing at Silero-v4 level with far better voice.
Research trail: bakeoff/tts-research-2026-07.md — **deleted 2026-08-03 with the rest of
`bakeoff/`; what survived it is the licence table in README, "Voices, cloning and the law"**
(multi-agent sweep of ~20 engines + adversarial
verification; only Silero/ESpeech/Misha credibly speak Russian — "supports Russian" in a language
list is marketing, the Chatterbox lesson generalizes). Engine switch is finalized by the F5Engine
adapter integration + a full-length control run (PLAN Phase 3).

**Russian voice cloning WORKS and becomes the narrator mechanism.** F5 is a zero-shot cloner:
the fixed narrator is now a config-level reference-clip choice, decoupled from the engine. A
9.7 s phone-video clip of the user's own voice scored best-of-day similarity (0.994, 0 flags);
timbre close but not identity-level — the expected zero-shot ceiling from a compressed 10 s
reference. Reference recipe: fast, clear, neutral-prosody diction in a quiet room — the
reference's pace transfers to the synthesis, so a brisk speaker buys free atempo headroom
(this is exactly why the fast-talking ESpeech demo reference got mean ×1.03).

**EN-reference cloning (the founding "same-voice" premise): possible, fixable — DROPPED by goal.**
- Round-1 failure was NOT accent. F5 sizes its generation canvas by UTF-8 *byte* ratio
  (`utils_infer.py`: `len(text.encode("utf-8"))`); a Latin reference (1 B/char) against Cyrillic
  gen text (2 B/char) doubles the canvas and the model fills the surplus with babble that
  whisper ignores (a verify blind spot) while atempo compresses ×2.11 (36/50 segments broken).
- Both predicted fixes verified on the full video: exact Latin transcript + `speed≈1.7`
  (byte-rate ratio) → mean sim 0.980, ×1.28, 1/50 over threshold; Cyrillic phonetic ref
  transcript → 0.950 (hand-written phonetics add alignment noise — the speed fix is better).
  Formula if ever revived: exact Latin ref transcript + `speed = ref_byte_rate / 0.045 s/B`
  (measured RU rate), or per-segment `fix_duration`.
- Residual defects by ear: end-of-sentence babble ("эр" at nearly every period — per-sentence
  canvas slack lands at the tail), one mid-sentence artifact on a long sentence, and a
  "1930s-recording" character: degraded-mic timbre + slightly off Russian pronunciation
  inherited from the EN reference.
- **Decision (user): the approach is workable and could be polished further, but the project
  goal is a quality Russian dub, not speaker identity — the direction is dropped.**

**Engine-integration note regardless of cloning:** ultra-short sentences garble/echo the
reference tail (id43 "Решениям.", 0.6 s → "Together"); known F5 short-text class. Mitigate by
merging ultra-short sentences upstream or reseed-retry when the F5Engine lands.

## 2026-07-16 — Narrator voice: ESpeech demo reference adopted; voice experiments closed

> **SUPERSEDED 2026-07-25** — the ESpeech reference voice went with the engine. The narrator is
> now Silero v5_5_ru, which takes no reference sample at all.

**Decision (user, ear, full-video runs):** the fixed narrator is the ESpeech author's demo
reference (HF Space `Den4ikAI/ESpeech-TTS`, `ref/example.mp3`) — best across every audition round:
mean sim 0.992, 0 flags, mean atempo ×1.03 on the sample video. Rights unclarified (a real
person's voice, unknown provenance) → the clip is NOT committed; fetched from the Space at setup;
outputs stay personal-use only (README "Voices, cloning and the law").

**PD fallbacks, re-creatable with `scripts/lv_pick_refs.py` (refs deleted from disk, sources
recorded here):** LibriVox readers, all Public Domain Mark — tovarisch
(`obyknovennayaistorya_1912_librivox`; best PD result: 0.985 / 0 flags), Kazbek
(`vekhi_2011_librivox`; bass ~109 Hz), Mark Chulsky (`carousel_2511_librivox`; 826 sections
available via librivox.org/reader/8086).

**Speed calibration validated as a config mechanism.** Slow narrators (Chulsky ×1.8 natural pace)
compensated via F5 `speed` to mean atempo ×1.03–1.08 at ≤0.022 sim cost — reference pace is no
longer a disqualifier; `speed` goes into the F5Engine config.

**Celebrity-voice references (personal-use experiment) closed by the user — "сложно добиться
качества".** Round-1 YouTube interview refs → artifacts/stutter across ALL ten voices: noise,
room reverb, conversational fillers and garbled whisper transcripts of noisy speech all clone
straight into the synthesis. Round-2 studio narrations improved but still under the bar.
Repo policy unchanged: PD samples only, person-agnostic docs.

**id43 confirmed a third time** (ultra-short "Решениям.", 0.6 s → hallucinated round-trips in 2 of
4 narrator runs) — merge-ultra-short-sentences upstream + reseed-retry are REQUIRED F5Engine
integration items, not nice-to-haves.

## 2026-07-16 — F5Engine integration: design panel + adversarial review (BUILD)

> **SUPERSEDED 2026-07-25** — this engine was removed; nothing below describes code that exists,
> and `.venv-f5tts` is not a live dependency. Kept for three mechanics that outlived it: the
> fd-level `os.dup(1)`/`os.dup2(2,1)` before heavy imports, the single-writer manifest invariant
> (a second writer means silent timing desync), and `synth_key`, which is still what gates all
> wav reuse.

Settled by a 3-bias design panel (minimalist / operability / quality) + 3 lens judges
(contracts / windows-ops / scope), synthesis by the main session; then a 4-lens adversarial
review with per-finding refutation (16 findings kept, 0 refuted, all fixed). Load-bearing calls:

**Worker process in `.venv-f5tts`, never f5-tts into `.venv-asr` (unanimous).** pip dry-run
evidence: resolver keeps torch 2.11 but downgrades numpy 2.5.1→2.4.6 under working
ctranslate2/onnxruntime, adds ~110 packages (gradio, wandb, datasets), and pulls torchcodec
0.15 built against torch 2.8 — an ABI gamble inside the venv every stage depends on.
Worker mechanics: JSONL over stdio; the worker's FIRST act is fd-level
`os.dup(1)` + `os.dup2(2,1)` BEFORE heavy imports (Python-level sys.stdout rebinding does not
survive native fd-1 writers); stderr inherited (live progress, no pipe deadlock class); config
via argv (Task-Manager-visible); reader-thread + Queue timeouts (the only sane Windows pipe
timeout; constants in f5.py, not config); per-request id echo (protocol corruption == crash);
respawn+resend once per request; EVERY consecutive failure — transport, respawn handshake, or
an ok:false reply (sticky CUDA context dies per-request while the process lives — review
finding) — counts toward a 3-strike TtsFatalError that escapes the per-segment catch. Startup
~30 s measured (imports 17 s + RUAccent 6 s + model 3 s); warm synth ~×1.1 of audio duration;
0.7 GiB VRAM.

**Reseed-retry lives in SYNTHESIZE, not verify (2 of 3 judges, over the scope judge's
objection).** Deciding invariant: segments/manifest.json stays single-writer — assemble derives
atempo factors from manifest `samples`, so a verify-side wav replacement with a stale manifest
is silent timing desync, the forbidden class; ordering discipline can only narrow that window,
single-writer eliminates it. Every fresh F5 segment gets an in-stage whisper-small round-trip
via `asr.roundtrip_similarity` (ONE function shared with verify — same-transform-both-sides,
the normalize.py precedent); < threshold → seeds tts_seed+1..+3, keep-best by similarity.
Accepted costs: double ASR round-trip (~+90 s / 39-min video), whisper-small coupled into
synthesize (loud failure, co-residency pre-blessed). Verify stays a pure judge — sole
similarity-flagging authority, byte-identical Silero path. Proven mechanics (micro-test,
threshold 0.9 / seed 7): id43 retried 4 attempts, best 0.875 kept (seed 9), honestly flagged.

**synth_key gates all wav reuse.** Everything that changes rendered audio enters one canonical
string: engine | ref-stem:content-sha1[:8] (the narrator ref is fetched-at-setup and mutable at
a stable path — stems lie) | ckpt+vocab name:size (review catch: a checkpoint swap must not
serve stale wavs) | sr | nfe | speed | base seed. Legacy Silero manifests reconstruct their key
read-side (zero migration). Manifest v2 adds per-segment seed/attempts/synth_sim and a
"complete" marker: the manifest is downgraded to complete:false BEFORE any wav mutates and
flushed every 25 fresh segments (review catch: a crash mid-resynthesis must not leave a
complete:true manifest over divergent wavs; F5 makes the stage ~20× longer than Silero, so
mid-stage interruption is now a real overnight event).

**Ultra-short mitigation = merge upstream in transcribe (char-criterion) + reseed as the net.**
MIN_SENT_CHARS=15 on EN chars — the failure mechanism is F5's UTF-8-byte duration canvas, so
chars, not seconds, are causal; MERGE_GAP_MAX=0.6 s; cumulative absorption of a merge chain
capped at 1.5 s (review catch); merged range must pass the existing _too_long. Pure pass
between _split_overlong and id assignment; unit-tested with synthetic word lists. Existing
workdirs keep their segmentation (done() gates on sentences.json); a --force transcribe on an
old workdir shifts ids after the first merge → src_en mismatches cascade into near-full Qwen
re-translation (~23 min on a 39-min video) — correct (stale RU must die) but expensive, don't
--force transcribe casually.

**Config surface minimal.** Engine-agnostic tts_seed/tts_max_retries + 7 f5_* keys; no
device/timeout knobs; the retry gate reuses similarity_threshold (no second threshold to
drift). `tts_engine` default stays "silero" until the Phase-3 control run + user ear check
pass; the flip is its own commit.

**Control-run gates fixed by the judges' fact-check (all three designers were wrong twice).**
The ultra-short "Решениям." is id43 of the SAMPLE video (4szRHy_CT7s), not the control video
(its ultra-short is id101 "Хорошо.", 0.22 s); and the Silero baseline's single flag is id189 —
a proper-noun-class failure whose text_tts is identical under F5, so it will likely flag again
regardless of engine. Gates are therefore ABSOLUTE (flag rate ≤ 2% of 315 after retries, id189
pre-registered as expected-to-flag; baseline comparison advisory), plus mean sim ≥ 0.985,
mean atempo ≤ 1.10, synth+verify RTF ≤ 0.5×, and the binding user ear check.

## 2026-07-16 — Dead-air ear verdict (user): noticeably better overall; mix modes iterate

**Overall: ощутимо лучше** — the dead-air mechanism (slot-fill + units) is validated by ear.
id101 ("Хорошо.", the ultra-short that failed as a lone segment) is now PERFECT inside its
group — L2 grouping confirmed as the structural fix for the ultra-short class.

**Defect found (17:02, unit [135,136,137]):** three short sentences in a 2.76 s EN span,
RU needed ~4 s → native compression ×1.327 → mid-word cutoff (first phrase truncated, next
begins). synth_sim 0.8361 scraped past the 0.8 threshold — no retry, no flag. LESSON:
post-hoc atempo compresses uniformly and never drops words; F5 NATIVE compression at
≥~1.3 does drop them, and char-similarity on long joined strings under-penalizes the loss.
Fix direction: native speed stays for STRETCHING only (safe direction, ear-validated);
compression returns to atempo (f5_speed_ceil → ~1.0–1.15), plus a stricter sim gate for
any compressed unit. The ×1.6-at-≤0.022-sim bake-off number measured ASR similarity, not
word survival — it over-promised for compression.

**Duck: mechanism right, depth wrong** — −15 dB leaves the EN original too audible. Retest
at −22..−25 dB (module constant). **Bed: content-dependent, inapplicable here** — this
video is nearly music-free, so the no-vocals stem is near-silence and the dead-air feel
returns. Re-check on a music-heavy source before judging the mechanism; a bed-RMS census
with automatic duck-fallback is the likely production shape. dub_mix default stays
"replace" until the duck depth retest.

## 2026-07-16 — Dead-air elimination: design panel + review (BUILD)

> **PARTLY SUPERSEDED 2026-07-25** — L1 slot-fill is written against F5's deterministic duration
> canvas and died with the engine; Silero's slot behaviour is a separate open item (PLAN). L2
> render units and L3 mix (duck/bed) are LIVE.

Panel (minimalist/contracts/audio + 3 judges) + 4-lens adversarial review (20 findings,
1 refuted, all fixed). Three composable layers against the measured 607-s underfill (an F5-era
figure whose decomposition was trimmed 2026-08-03; the live Silero baseline is 283 s of slot
silence on `8zJlKmgMT44`, in `2026-07-25 — atempo_floor = 0.75`):

**L1 slot-fill native speed — parent-side pure `plan_speed()` (2/3 judges).** F5's duration
canvas is deterministic (`out ≈ ref_sec·gen_bytes/ref_bytes/speed`, raw pre-accent bytes both
sides — stress-mark inflation cancels; bench: |err| ≤ 1.5% even on group-shaped 300-char
texts). Three branches: stretch to the SPAN (never the slot — real pauses stay pauses),
neutral when the free gap absorbs the spill (the DECISIONS gap-headroom principle), native
compress ≤ ceil before atempo tops up. Caps are MULTIPLIERS of f5_speed (narrator-pace
recalibration shifts the window); floor 0.75 by the pre-registered bench rule (0.7 passed
sims down to 0.95+, ship +0.05 margin). Retries reuse the same speed — keep-best compares
identical canvases. Worker reports EFFECTIVE speed (F5 forces 0.3 under 10 UTF-8 bytes).

**L2 render units — group at SYNTHESIS, not transcribe (unanimous rejection of widening the
transcribe merge: per-sentence subtitles are binding, and re-segmentation would cascade into
full re-translation).** build_units: gap ≤ 0.4 s, span ≤ 12 s (F5 trained regime, judges'
correction of the 18–24 s drafts), joined ≤ 300 chars; empty-text singletons break chains.
Manifest v3 "units" as the single structural truth; verify/assemble read units, never
recompute. Non-negotiable correction from the contracts judge: verify's reference text joins
from CURRENT translation.json — referencing the manifest would kill the stale-translation
net. Per-sentence report records with group_id keep translation-id contiguity verbatim.

**L3 dub_mix knob (replace/duck/bed), mixing in MUX.** Duck = explicit sample-exact numpy
envelope (−15 dB, ramps 50/300 ms, intervals merged < 1 s) — beats sidechaincompress on
determinism (no program-dependent pumping, no compressor keyed by F5 breaths); the
cmdline-length argument against envelopes was factually void (-filter_complex_script), the
decision is purely perceptual. Duck intervals = unit spans EXTENDED to placed audio (review:
the slot-fill neutral branch deliberately spills RU past the span — that tail must not ride
over full-level EN). Bed = htdemucs no-vocals at −6 dB, own .venv-demucs, CLI subprocess,
44.1 k stereo extract (the 16 k mono STT wav is unusable). ALL modes RMS-align the dub to
the original's speech loudness (±6 dB cap) — otherwise the A/B measures loudness, not
mechanism. Empty/failed units are deliberately NOT ducked: full-level EN there is the
honest fallback (on the ear checklist).

**Self-healing done() chain (review-driven).** verify/assemble gate on synth_key AND
units_key (content fingerprint — same-key --force resynthesis is otherwise invisible);
mux gates on dub_mix/synth_key stamps plus make-style mtime deps (re-assembled dub → re-mux).
Ordering discipline: the ARTIFACT flips before the stamp, everywhere — review confirmed
stamp-first turns a failed os.replace (the documented AV hold) into permanently-served
stale audio. Ear-loop consequence: flipping dub_mix in the TOML re-runs exactly mux.

**Known accepted losses (named, not hidden):** group-level similarity dilutes per-sentence
sensitivity at the same 0.8 threshold (re-tune queued — PLAN open question); subtitle cues
keep source timings while grouped audio renders continuously (drift bounded by the 12 s
span cap; on the ear checklist); --repair granularity becomes the unit, not the sentence.

## 2026-07-16 — Verify is ASR-blind, confirmed on real content (id101)

Trimmed 2026-08-03: the rest of this entry was an F5-era ear verdict and a roadmap reorder, both
dead. One data point survives and it is load-bearing.

**id101 ("Okay.", ultra-short) scored a round-trip similarity of 1.0 and the ear said bad.** The
ASR-blindness of verify is therefore CONFIRMED on real content, not only on synthetic babble: a
round trip can agree with itself perfectly over audio a listener rejects. The ultra-short class
needs structural fixes (merge/grouping), not retry luck.

## 2026-07-16 — Local-only constraint amended: optional cloud-translate mode approved

> **SUPERSEDED 2026-07-18** — cloud translation stopped being an opt-in exception two days later:
> the Sonnet route became PRIMARY. Kept because it records an amendment to a FOUNDING constraint,
> which is the one class of decision that must never vanish from this file.

**User decision:** an explicitly opt-in cloud translation mode (Anthropic API, Sonnet-class) is
a permitted exception to the founding local-only constraint. Rationale: translate is 80% of
wall-clock (RTF 0.60, the only real bottleneck) and the likeliest quality ceiling; a cloud pass
would give the largest single speed win while keeping quality. Boundaries: OFF by default, a
deliberate flag (no silent fallback to cloud), local Qwen path remains the default and must keep
working; STT/TTS stay local unconditionally. CLAUDE.md hard-constraints section amended to match.

## 2026-07-17 — Compression back to atempo; bed at original level is THE mix mode (ear)

**f5_speed_ceil 1.6 → 1.1 + stricter gate for compressed units.** The 17:02 defect (unit
[135-137], native ×1.327, mid-word cutoff at synth_sim 0.836) confirmed the bake-off blind
spot: ASR similarity measures character overlap, not word survival — F5 native compression
≥~1.3 drops words outright, while atempo compresses uniformly and never drops any. Native
compression is now capped at 1.1×base (mild pace-up, safely under the observed word-drop
regime); everything above tops up via atempo at assembly. Any unit rendered above base pace
must clear `similarity_threshold_compressed = 0.9` — ONE shared `unit_sim_threshold()` used
by both synthesize's reseed loop and verify (same one-function discipline as
`roundtrip_similarity`, so the two gates can never drift).

**Mix mode (user ear, binding): bed WITHOUT attenuation; duck and replace are worse.**
`_BED_GAIN` −6 dB → 0 dB; `dub_mix` default flips to "bed". The planned duck-depth retest
(−22..−25 dB) and the bed-RMS-census/auto-duck-fallback idea are cancelled. Named accepted
residual: on near-music-free sources the no-vocals stem is ≈silence, so bed degrades to
replace and the remaining in-span silence (204 s on the control) stays silent — accepted,
L1+L2 already removed two thirds. A sanity-check on a music-heavy video stays on the plan.

**L1 "measure instead of predict" (user question, answered — rejected):** cutoffs leave no
silence to measure — a compressed canvas is fully voiced with words missing; only content
verification catches it (and did: 0.836, gate was just too lax). Measurement already sits
where it can: atempo derives from actual wav samples, in_span_silence is reported, every
unit round-trips through ASR. The canvas prediction (err ≤1.5%) only picks the speed knob
BEFORE synthesis; a synth-measure-resynth loop would ~double GPU time (242/256 units
stretched) to correct a ≤1.5% error.

## 2026-07-17 — Dead-air closed by ear (final verdict)

**User verdict:** L3 bed on the music-heavy check (tJP6SKfo49c) works perfectly; the 17:02
cutoff fix is acceptable; the remaining artifacts roughly correspond to the source's own
unusual intonations and stutters — i.e. they mirror the original delivery, they are not
pipeline defects. The dead-air problem group is CLOSED. Accepted residuals, named: 203.8 s
in-span silence on the speech-only control (bed ≈ replace there — no stem to carry) and
delivery-correlated artifacts. Roadmap top is now proper nouns (PLAN item 1).

## 2026-07-17 — Base similarity gate raised 0.8 → 0.9

Trimmed 2026-08-03: this entry also carried a near-term roadmap, a UTMOS deferral and a PLAN
restructuring. All three are scheduling, long since consumed. The threshold decision is live —
`similarity_threshold` is still read in four files.

**Base `similarity_threshold` 0.8 → 0.9 (user).** Units are long joined strings that dilute
local defects — the 17:02 word-drop scored 0.836 and passed the per-sentence-calibrated 0.8;
both runs of the day sat comfortably above 0.9 (unit min 0.926 / 0.9415). Further tuning
deferred entirely until production flags misbehave. Known side effect, accepted: more flags on
the lower-similarity engine path (Silero's per-sentence sample min was 0.875 — it was the
fallback then and is the only engine now) — flags are warnings, the pipeline never blocks.

## 2026-07-17 — Batch queue + stop switch (BUILD)

Settled by a 2-bias design panel (minimal-diff / overnight-operability) + judge, then 4-lens
adversarial review with 2-skeptic per-finding verification (13 findings, 11 confirmed, all
fixed). Load-bearing calls:

**Exit codes are the batch API: 0 ok / 1 any fail / 2 usage / 3 stop-halt.** An overnight
wrapper must distinguish "stopped" from "broke" without parsing stdout; fail wins over halt.
KeyboardInterrupt is deliberately caught nowhere — the operator pressing Ctrl+C is at the
console; a partial-summary handler is 4 lines for near-zero value.

**STOP is consumed at honor time, not at catch site.** `check_stop(work_root, where)` in
pipeline.py unlinks then raises — a plain re-run always resumes. The startup sweep in cli.main
reuses the same helper (a stale file can never silently no-op the run); if the unlink fails
persistently (AV hold / open handle), startup aborts loudly instead of re-halting at the first
boundary with a misleading message. Checkpoint sits BEFORE the only/done filters — a stop
halts at the next stage boundary even through a run of [skip] lines. The between-videos
checkpoint was removed by review: run_pipeline's "before stage 'download'" check fires first
thing for every video and covers the same gap (accepted observable change: a between-videos
stop prints the next video's header and reports as its "stop" row).

**Export = hardlink with copy fallback; persisted title is never refreshed.** Same-volume
hardlink is free at MKV sizes; .tmp + replace_retry keeps the flip atomic in both paths.
Naming stability beats freshness for an archive dir; stale exports of the same video id are
glob-cleaned (the offline-fallback→online-backfill rename case). Named accepted residual:
an export left open in a player without FILE_SHARE_DELETE can block a later re-mux's
os.replace of output.mkv (loud FAIL, batch continues) — documented in the code, not worked
around with always-copy.

**Review catches worth remembering:** yt-dlp encodes piped stdout in the locale ANSI codepage,
not UTF-8 — the title backfill runs with PYTHONUTF8=1 in the child env or Cyrillic titles
mangle on stock Windows (this host works only because ACP=65001); with `-o source.mkv` the
info-json sidecar is `source.info.json` on the mkv merge path but `source.mkv.info.json` on
the single-format `/b` fallback — both probed; UnicodeDecodeError from a torn info.json is a
ValueError, NOT an OSError/JSONDecodeError — the guard catches (OSError, ValueError) or a
torn file blocks the backfill forever; queue files from PowerShell 5.1 carry a BOM that
str.strip() does not remove — read with utf-8-sig.

**Config surface: exactly one new key (`output_dir`, default `out/`).** Stop-file name,
120-char title cap and 30 s backfill timeout are constants — knobs without a demonstrated
tuner are dead config surface. Per-stage batching (one model load per stage per batch)
explicitly NOT built — revisit only if per-video model reload overhead is measured to matter.

## 2026-07-17 — Proper nouns: pronunciation chain (BUILD)

**Chain: PHRASES → WORDS → plural tail → case-gated acronyms → letter names → rule
transliteration (`overdub/pronounce.py`), wired into normalize as passes 0a/0b + the pass-6
resolver.** Phrases run FIRST on raw text (keys may contain digits/apostrophes, so they must
precede every numeric pass); a phrase earns a slot only when word-by-word composition cannot
produce the target ("no man's sky" — the id150 ear case). The fallback replaced the naive
per-letter translit with an ordered left-to-right practical-transcription scanner (~74 rules),
killing the sky→скй class structurally: every corpus output word ≥3 chars must contain a vowel
(tested). Committed contested readings: хейло, энвидиа, пайтон, твитч, uh→э-э (EN hesitation
as RU filler keeps slot timing). The roadmap's "per-run cache" is reinterpreted as the
AUDIT-ONLY artifact `pronounce_audit.json` (written by translate, read by nobody):
normalize_for_tts must stay pure/deterministic — a run-scoped resolution cache would desync
verify's two sides, the forbidden silent class. A/B on a renormed copy of the f5-control run
(tools/renorm_workdir.py; 31/315 records changed) is the acceptance path; expect verify flag
counts to RISE — the old low count was the masking bug (broken translit self-agreed in the
round-trip at sim 0.93–0.97, only id189 ever flagged).

## 2026-07-17 — Segmentation cluster (BUILD): the seg_end "pause" was a whisper VAD artifact

**Root cause, measured not guessed.** The user ear-reported two mid-phrase splits; the
Measure phase (running resegment() on the persisted words.json — the offline re-tune lever the
stage was built for) disproved the obvious "it's the 15 s cap" reading: both emitted spans were
recursion LEAVES with `_too_long`=False. The real defect: `_split_overlong` branch 1 treated
`W.seg_end` (last word of a whisper segment) as a speaker pause, but 73% of corpus seg_ends
carry a 0.000 s gap to the next word — whisper ends segments mid-phrase on a VAD/window
boundary. Both bugs cut at gap 0.000, the point chosen purely by time-midpoint proximity
('survival' beat 'games' by 0.030 s, severing "survival | exploration crafting games"). Branch 1
made ~90% of all cuts and 95% were fake pauses.

**Fix = a real-silence gate, not a bigger dictionary.** `MIN_PAUSE_SEC=0.20` on branch 1
(measured plateau: any value 0.10–0.50 fixes both bugs, total spread one span — a plateau, not
a fit); `_ok_cut` veto (no cut ends on a bare function word, none inside a hyphen-split
compound) applied to ALL THREE branches — a filter in 1/2, a sort *preference* in 3 so branch 3
always cuts and termination is preserved. `_CONJ`→`_CUT_BEFORE` drops the ambiguous
subordinators (that/which/who/as/if/when/where/…): once branch 1 is gated, the next-word test
jumps ~11→~110 cuts and cutting before "that" severs verb-from-object — the id150 cascade class
(review finding, critical). Item E shipped ('.'+seg_end before a lowercase word is a boundary;
11/11 genuine on corpus, decimals can't reach it).

**C and D rejected on evidence, not deferred lightly.** Tolerance band (C): does not fix bug A
(the cut is at depth 1 on a 70 s parent, far above any 16.5 s band), and it breaches F5's 12 s
unit cap while letting `_merge_short` rebuild long sentences (it calls `_too_long`). Run-on
recovery (D, Capital-after-lowercase): ~5% precision, cuts inside «Call of|Duty»; the only safe
variant (seg_end AND gap≥0.2) fires once in 7,483 words — N=1 cannot calibrate a rule whose
dangerous variants sit one predicate away. The ear reported A/B/F/G; C/D were our ideas.

**Item F (names stay Latin) — accepted silent-loss class, named.** The translate prompt now
mandates Latin script + canonical casing for game/brand/platform/company names so pronounce.py
owns them; personal names stay Russian (Qwen renders Джонсон/Миямото well, the rule
transliterator mangles them). ACCEPTED COST: an out-of-dict game/company name (Bungie→бунджи,
Bethesda→бетесда) now hits the rule fallback and — per pronounce.py's own docstring — self-agrees
through verify unflagged. The 3-video corpus (the dict was fit to it) cannot exercise this; the
only detector is promoting `pronounce_audit.json` to a pre-batch operator gate (INBOX). This is
the deliberate trade for making Qwen's previously-unrecoverable Cyrillic transliteration
(«Ранескэпом») recoverable and auditable.

**Item F residual (dangling verbs) accepted, not fixed.** `_ok_cut` still vetoes only the
16-word `_STOP` set, so a cut can end on a bare verb/pronoun ("you have" / "i think"; ~9 corpus
cuts). Accepted: a dangling verb → a dangling verb is strictly better than the fake-pause cut it
replaced, and widening _STOP is a large unmeasured change that risks more midpoint fallbacks.

**Upstream cause bigger than the whole cluster (both designs flagged it).** x7 has 6
terminator-free ranges >60 s (worst 206 s / 2968 chars → ~19 bisected sentences) because the
whisper call sets `condition_on_previous_text=False`. The gap-gate makes those bisections
defensible, not correct; re-enabling context or a punctuation-restore pass would retire the
class. → PLAN backlog + INBOX (measure the hallucination risk that turned it off).

**Cascade cost restated (DP10).** Both transcribe id-shift and the prompt change invalidate all
four corpus workdirs' translations (~23 min re-translate/video). assemble's cue split is
display-only — it never touches sentences.json/ids/timings. After a fresh --force transcribe the
ear-session ids shift by −2 past id102 (id149→147, id150→148, id188→186, id189→187): reason from
text, not the old numbers.

## 2026-07-17 — Whisper punctuation context: the segmentation ROOT fix (ear-driven, measured)

**The cluster fix was damage control; this is the cause.** Ear check of the segfix run: the
"period mid-sentence" defect the user heard was frequent (fragment-opening sentences 181/314).
Layered trace of a single case (id148, condition=False): whisper's EN `sentences.json` text ends
`...and then you have` — last char `e`, NO period; Qwen's `text_ru` ends `...у вас есть.` — with a
period. So the FULL STOP is written by Qwen, but the BOUNDARY (where the phrase is severed) is
`_split_overlong`'s, firing because whisper returned a 60-206 s terminator-free block. Qwen
translates 1:1 and cannot merge across units — it inherits the break, it does not create it.

**Root proven by a single-variable experiment.** Changed ONLY the whisper flag
`condition_on_previous_text` False→True (Qwen and the splitter untouched) and re-ran ASR on the
ear video: max terminator-free raw range 206.1 s → 27.2 s, sentences 314 → 427 (real
boundaries), sents >15 s = 0, and both ear cases became whole in ONE sentence ("...met through
Xbox Live or through... a forum or YouTube"; "...you have so many of these like survival
exploration crafting... Minecraft, Valheim, No Man's Sky"). Since only whisper changed, the
break was whisper's punctuation gap, not Qwen — a Qwen fix (e.g. "don't end a fragment with a
period") would not help: the thought is still split into two synth units with a pause between.

**Hallucination risk (why the flag was off) measured, not assumed.** condition=True is known to
loop on low-signal audio; that is why it was False. A/B on the music video (the worst case for
looping): longest identical-token run = 3 (ordinary words), zero nonsense loops, max sentence
9.3 s. Safe on both poles measured (clean monologue + music, N=2). Shipped as a Config flag
`whisper_condition_on_previous` (default True), NOT hardcoded — a future source that loops can
set it False without a code change; the gap-gate/`_CUT_BEFORE` cluster stays as the fallback
splitter for genuinely long single sentences.

**Consequence for the cluster.** With context on, `_split_overlong` rarely fires (max sentence
14.2 s on the ear video), so the 31-agent cluster is now second-order. It is NOT reverted (fake
VAD-pause cuts were objectively worse and other videos will have real >15 s sentences), but the
priority lesson stands: Measure surfaced the 206 s blocks and they were filed to backlog instead
of tested first — the one-line flag outperformed the whole cluster. Test the root before
polishing the symptom.

## 2026-07-18 — Gemma-3-12B replaces Qwen3-14B as the translation model

> **SUPERSEDED 2026-07-25** — neither model is in the pipeline; the local-LLM translate path was
> removed entirely. Kept for the comparison method, not for the winner.

**Decision: Gemma-3-12B is the default translator; Qwen3-14B is removed entirely — not kept even
as an option.** The user's standing observation ("Qwen местами сыпется") was confirmed and fixed.

**Evidence: an 8-video A/B on identical segmentation.** Both models were fed the SAME
`sentences.json` (the 8 videos the Qwen stats batch had finished), so the only variable is the
translator — the demucs bed and everything downstream are byte-identical. 508 sentences. Objective:
RU/EN length ratio (dubbing fit) median 1.062 vs 1.086 (Gemma tighter → less atempo stretch);
translate flags 4 vs 6; verify round-trip sim ~0.991 vs ~0.988 (≈); lower mean max speed-factor.
Qualitative (user read ~100 phrases, all better on Gemma; + a divergence scan): Qwen's real
defects were absent in Gemma — "эффективное/эффективное" duplicated on "effectively, efficiently"
(twice), an untranslated "fluent" left in Latin, "Интеллектуальная грамотность" for "AI fluency".

**Cost accepted: ~16% slower.** Same 508 sentences: 5.30 vs 4.58 s/sentence (1.08–1.21× per
video). translate is the pipeline bottleneck, so end-to-end ≈ +8–10%. At 100-hour batch scale that
is real (+~1–1.5 h/overnight) but the quality jump dominates. (Counter-intuitive for 12B<14B;
thinking is not the cause — Qwen ran think:false, Gemma has none — it is Gemma-3 arch/tokenisation.)

**Gemma-3 API differences forced a code change, not a config swap.** Gemma 3 has no thinking mode
(Ollama HTTP-400s if a "think" key reaches it) and its chat template rejects a system role. The
translate stage now folds SYSTEM into the single user turn and sends no "think" key — replacing
Qwen's native `think:false` + separate system message. It was built first as two config flags
(`ollama_system_role`/`ollama_send_think`) for a clean A/B that kept the Qwen wire-request
byte-identical (proven); once Gemma won, the flags AND the Qwen branch were removed (YAGNI). Default
`ollama_model` qwen3:14b → gemma3:12b (~7.5 GB VRAM loaded, was ~8.6 GB).

## 2026-07-18 — Silero v5 acknowledged: the good no-sample TTS option

**User verdict:** Silero v5 is also good as TTS — quality slightly below F5/ESpeech, but it
needs NO narrator reference clip: zero voice-sample setup, zero rights questions (the F5
narrator carries the README rights caveat). Recorded as a first-class alternative, not just
a legacy fallback; the engine choice is now: F5/ESpeech = best quality + needs a reference,
Silero = slightly lower quality + no sample. The in-code adapter still loads v4_ru — bumping
to v5 (`v5_5_ru` via torch.hub) is a small change with one caveat: v5 rejects Latin script
(text_tts is Cyrillic-only by the normalize contract already; add an out-of-alphabet filter
per the bake-off note). → INBOX chore. Bake-off history unchanged: ESpeech led v5 by ear
(2026-07-16); this verdict upgrades v5's standing as the no-sample option.

## 2026-07-18 — Sonnet verdict (user read-through): both translation routes stay; Sonnet semi-automatic is the PRIMARY route

**User verdict on the 508-sentence A/B read-through:** Sonnet's quality is noticeably
better and its speed significantly higher (~3× serial, order-of-magnitude in parallel) —
and, notably, it replaces the pipeline's heaviest, longest stage (translate is the local
bottleneck). Both routes are declared good and both stay:
- **Gemma-3-12B (local)** — good quality, free, offline, slow; remains the in-pipeline
  default. The local path must keep working (hard constraint unchanged).
- **Claude Sonnet (cloud)** — requires a subscription; better quality, much faster.

**Primary route: Sonnet in SEMI-AUTOMATIC mode** — the sub-agent workflow proven by the
A/B spike (transcribe in-pipeline → Sonnet sub-agents write translation.json under the
translate contract → pipeline resumes from synthesize), NOT an in-pipeline API
integration. The approved opt-in Anthropic API path (2026-07-16) stays approved but is no
longer the next step — build it only if the semi-automatic seam's manual step becomes the
bottleneck. Cloud translation remains explicit and per-run, never a silent fallback.
Runbook for both routes: README "Running".

**Top blind spot after this: translation COMPLETENESS is unmeasured.** verify's ASR round-trip
checks TTS fidelity to `text_ru`, not that `text_ru` is a complete translation of the English.
Gemma's tightness occasionally drops a word (measured: 1 of 3 adverbs on Dmgujo id1) and nothing
flags it — same silent-loss class as the out-of-dict pronunciation echo. A completeness check is now
the highest-value verify upgrade (PLAN roadmap 1).

## 2026-07-19 — 4-way translate bake-off on x7DfiXqSEdM: Gemma prompt-bundle dropped, Sonnet isolation dropped

> **PARTLY SUPERSEDED 2026-07-25** — the Gemma arms went with the local translate path. The
> Sonnet findings still describe the live route.

Single-video A/B/C/D on one frozen `sentences.json` (x7DfiXqSEdM, 427 sentences, ~39 min,
first-person vlog monologue on social gaming), same input, four translators:
1. **gemma-base** — current SYSTEM prompt (shipping local default).
2. **gemma-impr** — the four-change bundle from `.claude/gemma-translate-ab-brief.md`:
   completeness-first reframe (#1) + forward lookahead of the next 1-2 EN sentences (#2) +
   1-2 few-shot examples inside SYSTEM (#3) + anti-repetition rule (#4). Ran on a FRESH workdir
   (the brief's stale-`src_en`-reuse trap) via a branch build of `translate.py`.
3. **sonnet-v1** — Sonnet sub-agent, `general-purpose` type (Tools:*), whole document in context.
4. **sonnet-iso** — Sonnet sub-agent, a custom isolated `overdub-translator` type (Read/Write only),
   built to test whether a narrow agent translates cleaner than the broad one.

**Objective metrics** (all four: 427 sentences, 0 `_is_bad` flags):

| variant | len ratio med | >1.5× slots | name_loss* | digit_loss* |
|---|---|---|---|---|
| gemma-base | 0.98 | 2 | 29 | 6 |
| gemma-impr | 1.06 | **20** | 27 | 5 |
| sonnet-v1  | 0.93 | 1 | 21 | **0** |
| sonnet-iso | 0.95 | 1 | 21 | 0 |

\* noisy heuristic (EN names/digits absent from RU); valid for cross-variant comparison, not absolute.
Pairwise differ-counts: base↔impr 345/427, v1↔iso 344/427 (81%), v1↔gemma-base 411/427 (96%) —
engine choice moves the translation far more than any prompt/agent tweak.

**User read-through verdict:**
- **Gemma base vs impr → PARITY on text, base wins for the video.** impr makes no outright errors
  (base occasionally mistranslates), but builds clumsier, harder-to-parse sentences. Net: the bundle
  is not worth it. The mechanical cause is change #1 (completeness reframe): it inflated length
  (+7% median, **×10 more >1.5× slots: 2→20**) without recovering meaning in the target spots (the
  `[46]` "medium of a game" drop it was meant to fix survived) — it just added filler and register
  stiffness. **DROPPED; branch `gemma-completeness-ab` discarded, `translate.py` unchanged.**
- **Sonnet v1 vs iso → difference small, v1 slightly more natural** (iso calques the English a touch
  more often). Isolation does NOT improve translation quality; its only value is operational
  (narrow tool-set, determinism, tokens). Not worth a second agent type. **iso agent DROPPED; the
  `overdub-sonnet-batch` skill stays on `general-purpose`.**
- **Sonnet vs Gemma → Sonnet is the clear winner** — more accurate and more natural speech. On this
  lifestyle vlog the gap is clear; on the earlier science-pop read-through it was even wider
  (content-dependent). Confirms Sonnet = PRIMARY route (DECISIONS 2026-07-18).

**Kept:** the semi-automatic Sonnet-route infrastructure — `.claude/skills/overdub-sonnet-batch/`
(fixed transcribe → sub-agent draft → resume order) + `scripts/build_translation.py` (sub-agent
writes only `{id, text_ru}`; the helper fills src_en/timings, derives `text_tts` via the pipeline's
own `normalize_for_tts`, gates each line through `_is_bad`, enforces id-contiguity — so the translate
contract never rides on an LLM's discipline). Validated on this 427-sentence run.

**Completeness stays the top blind spot but the prompt-bundle is NOT the fix** (this experiment
falsified it). The verify-side completeness check (PLAN roadmap 1) remains the right lever.
Caveat: n=1 video, lifestyle content — indicative, not a multi-content-type A/B.

## 2026-07-19 — Completeness check (verify-side, deterministic A+B) — shipped, all 4 detectors kept

> **PARTLY SUPERSEDED 2026-08-01** — the title no longer holds. `entity_loss` was DELETED and
> `neg_loss` demoted to advisory 2026-07-27; `dup_adjacent` and `rate_implausible` are live.

After rejecting the LLM-judge / embedding semantic check as PoC over-engineering (the analysis
earlier this day), built the cheap deterministic A+B insurance via an ultracode workflow (8 agents:
understand → build → adversarial verify → synthesize). New pure module `overdub/completeness.py` —
four NON-BLOCKING per-sentence detectors written to `report.json` at verify:
- **num_loss** — a digit run in src_en absent from text_ru (leans on the keep-digits rule;
  `normalize._n2w` suppresses legitimately spelled-out numbers).
- **neg_loss** — an EN negation marker with no RU не/ни/без in text_ru (guards meaning INVERSION,
  the worst silent loss).
- **entity_loss** — a Titlecase Latin name in src_en absent from text_ru (leans on keep-Latin-names).
- **length_short** — len(text_ru)/len(src_en) < `completeness_len_ratio_min` (0.45) with a 30-char
  src guard (catches a catastrophic clause drop the precise signals miss).
- **dup_adjacent** — *(added later the same day, PLAN item 0c — listed here so this enumeration
  stays complete)* two ADJACENT **src_en** sentences with char-level
  `SequenceMatcher(autojunk=False).ratio() > 0.80`, first member > 25 chars. The only
  CROSS-SENTENCE detector, so it lives in a module-level `duplicate_adjacent(texts)` rather than
  in `check()` (whose `(src_en, text_ru, cfg)` signature cannot express it); `verify.py` appends
  the flag and writes `completeness_duplicate_of`. Catches an **ASR** defect, not a translation
  one — whisper's repetition loop emits a line twice and the dub says it twice.
Integrated as a separate segs loop in `verify.run()` (after the whisper model frees, before
`report.save`); rollup `rep["completeness"]`. 21 tests, no regression.

**Real-data validation (x7DfiXqSEdM, 854 sentence-checks across Gemma + Sonnet): 31 fires, 0 true
losses, all FP.** But the two precise signals stayed SILENT on the clean data — num_loss Sonnet
0/427, length_short 0/854 — which is exactly the intended "silent until a real loss happens"
insurance (they fire on a genuinely dropped number/clause; this content simply has none).
entity_loss is ~100% FP (Russified personal names — Jimmy Carter, Bruce Lee — which the naming rule
PERMITS; translated titles; Capitalized common words) with ~0 recall on EN→RU: structurally noisy,
no cheap person-vs-brand discriminator exists. neg_loss is 100% FP here too (lexical negation:
`not good`→`плохо`) but guards the meaning-inverting class at 0.5%.

**User decision: KEEP ALL FOUR as-is** (triage-only, non-blocking). entity's noise (~3% of
sentences) is accepted for the chance of catching a genuinely dropped brand. This is the FIRST
data source for the run-report / observability item (PLAN 1). The heavy semantic check stays
rejected.

### Addendum (same day, PLAN item 0c) — 5th detector + a negation-regex fix

**`dup_adjacent` is ACTIONABLE, not advisory — justified by PRECISION, not hit rate.** PLAN
argued actionable from "found real defects in 2 of 12 videos"; that figure belongs to the
session's ad-hoc audit, not to this rule. Measured over all 13 workdirs (1101 sentences, 1028
eligible pairs): **exactly 1 fire, a true positive** (`ytEN_iAk09c` 7/8 — byte-identical lines,
the second spanning 0.32 s), i.e. 1 of 13 videos, precision 1.0. Unlike `entity_loss`, whose
dominant FP the docstring calls IRREDUCIBLE, this one's FPs are *decidable* — a human reading both
members can always tell an echo from two distinct sentences. That difference, not frequency, is
what splits the two across `_ADVISORY_COMPLETENESS` (deliberately left untouched: any name absent
from it is actionable by set difference).

**Correction to a first draft of this entry**, which called the FP mode "deliberate verbatim
repetition, rare and instantly recognised". That is the *rarest* mode, not the dominant one. At
0.80 a pair may differ in ~12% of its characters, so the reachable FP is single-token substitution
across a shared frame: enumerations (0.89), before/after and free/paid contrasts (0.92-0.93),
CPU/GPU swaps (0.98). Worst shape — a polarity flip in an identical frame, "You should use this…"
/ "You should not use this…" = 0.96 — is emphatically NOT instantly recognised, and a triager who
"resolves" it by deleting one member inverts the meaning. Measured zero times in this batch's 1028
pairs, so it is genre exposure (explainer prose) rather than an observed defect; a conversational
or instructional corpus would fire far more. The docstring now names this as the dominant FP with
the read-both-members warning, and a test pins the firing boundary so the near-miss control test
is not misread as "parallelism is safe". Actionable status stands — decidable-on-inspection is
still the right bar — but it rests on a correct account of what the flag will show a human.

**Second signal added the same day: CONTAINMENT, because ratio alone was worth a third of what
PLAN assumed.** PLAN justified the actionable status with "found real defects in 2 of 12 videos",
but that figure belonged to an ad-hoc script doing PARTIAL substring matching, while the method
PLAN actually recorded was `ratio > 0.80`. The formula in PLAN was a lossy transcription of what
had worked — and the ratio rule finds **1** of this corpus's 3 repetition defects, not 2. Worth
recording as a process failure, not just a metric one: the finding survived into PLAN, the method
that produced it did not.
Containment (`longest common substring / len(shorter)`) targets the RESTART shape, where whisper
re-speaks part of the previous line and continues — the shared span is large but the new tail
drags the symmetric ratio down. Measured over all 13 workdirs / 1028 eligible pairs: **3 fires,
all true positives** (ytEN_iAk09c 7/8 containment 1.0000; x7DfiXqSEdM 298/299 0.9677;
2YCaBqP8muw 16/17 0.9167), loudest benign pair 0.7188 — a 0.20-wide empty band. `_DUP_RATIO_MIN`
is kept rather than replaced: it is the better-grounded of the two, and the signals are OR-ed.
**0.85 is labelled a HYPOTHESIS in the code, not a measured constant** — it rests on 3 positives,
and the surrounding comments deliberately do NOT read like `_DUP_RATIO_MIN`'s, which earns the
stronger claim. Re-validate as the corpus grows.
Still missed by construction: NON-adjacent loops (the scan is pairwise; a duration/wps check is
the orthogonal answer — INBOX) and semantic garbles that repeat no span (the four-Ds recap,
containment 0.44).

## 2026-07-19 — Repairing a whisper hallucination: isolated-window re-ASR, not a full re-run

**Full-file re-transcription is not a repair method for this class.** All four known-defective
videos were re-run with `--force --only transcribe` on the theory (PLAN 0a) that whisper's
non-determinism would shake the defect loose. It fixed **1 of 4**. The other three reproduced the
same defect on the same audio, one came back worse (a new 0.28 s collapsed segment), and a fourth
gained a fresh garble containing CJK characters. These are not decoder noise — they are stable
responses to specific passages, and re-rolling the dice costs a full ASR pass to mostly lose.

**What works: re-transcribe the WINDOW, not the file.** The repetition loop is fed by
`condition_on_previous_text`; a clipped 8-18 s window has no prior context to loop on. Applied to
all 7 defect regions across 6 videos, every window returned a clean reading, **identical under
both `condition_on_previous_text=True` and `False`** — the stability check that says the reading
is the audio and not another sampling artifact. Cost is ~1 minute per window against ~50 s for a
full file, and it repairs instead of re-rolling.

**Repair discipline — delete, do not invent.** Every replacement text is the isolated window's
OWN output; the defect is always that whisper emitted extra sentences where the window shows one,
so each repair MERGES a run into the single verified sentence and renumbers to keep ids
contiguous (the invariant `duplicate_adjacent` and `implausible_rate` both rely on). Exactly one
correction overrode ASR rather than deleting: `Anthropics Cloud Models` → `Anthropic's Claude
models`, flagged in the repair script, on the grounds that this is Anthropic's own course about
Claude and a wrong brand name would reach both the dub and `pronounce`.

**Result: 7 repairs, and both ASR detectors go silent on the batch.** `rate_implausible` max fell
from 246 to 39.36 ch/s (under the 40 threshold — zero fires); `dup_adjacent` fires zero times
across the 12 queue videos. Originals preserved at `work/<id>/_pre-repair-sentences.json`;
`words.json` is deliberately NOT rewritten — it is the raw record of what the ASR actually did,
and `asr.floor_ratio` should keep reporting that these files had a collapse.

**A THIRD defect class, found by a translator sub-agent reading the text — not by any detector.**
`W4Ua6XFfX9w` ids 19/20 read "Description goes beyond distinction." / "just writing prompts."
The isolated window says it is one sentence: "Description goes beyond just writing prompts." A
hallucinated word (`distinction` for `just`) split one sentence in two. **Both detectors are blind
to this shape by construction**: each half sits at a plausible ~26 ch/s (well under the 40 bound)
and the two are not similar to each other, so neither `rate_implausible` nor `dup_adjacent` can
see it. Only reading the text finds it.
**This settles the "Tier 2" question the 0d audit raised.** The translate seam is not a nice-to-
have extra detector — it is the ONLY thing that catches semantic garbles carrying no timing
anomaly and no repeated span. Both classes that survived every deterministic detector in this
batch (this one, and the `RyvXxApfHkk` self-referential nonsense) were caught by an LLM reading
the source, and in the same pass the agents also flagged `CLAWD`/`anthropics` ASR mis-spellings
nobody had logged. The deterministic detectors remain worth having — they are cheap, they
localise precisely, and they run before any model — but the honest architecture is
deterministic detectors PLUS a reading pass, not one or the other.
**Counter-note against over-trusting it:** the same property makes the translator dangerous.
`RyvXxApfHkk` id11's garbage was silently REPAIRED into plausible Russian by Sonnet on the first
pass (PLAN 0e), hiding it from everything downstream. A reading pass helps only when it is asked
to REPORT anomalies rather than to smooth them over — that is a prompt requirement, not a
property of the model.

**Caveat worth keeping honest:** this is hand-editing ASR output. It is defensible here because
every edit is grounded in a second, cleaner ASR reading of the same audio rather than in judgement
about what was probably said — but it is a semi-automatic operator action, not something the
pipeline does for itself. Automating it (detect → re-ASR the window → merge) is the obvious next
step and is NOT built.

## 2026-07-19 — `dup_adjacent` + `rate_implausible` (continued)

**Third signal, and the best one in the file: `rate_implausible` (signal D).** A source sentence
whose chars/second exceeds `_RATE_MAX_CPS = 40` cannot have been spoken in its own span — the
signature of a whisper alignment collapse. Unlike every other threshold here, this one is sited on
a PHYSICAL bound rather than corpus separation: human speech tops out near 25-30 ch/s, and the
corpus agrees (1100 sentences, median 16.75, p95 23.97, p99 34.26, fastest benign 39.4). The
defects sit at 70-246 ch/s — an order of magnitude clear.
**7 fires / 1100 sentences, 7 true positives, 0 false.** Highest precision of anything in this
module, and it is the only detector that reads TIMING instead of text.

**What it found that nothing else could.** Two videos that every text-based signal reported
`[clean]` carry real collapsed segments: `DmgujoZ1mmk#32` (93 chars in 0.88 s) and
`W5cga7xipRI#23` (66 chars in 0.94 s). Batch triage went 2 → 4 videos, and the two additions are
real. It also catches garble that repeats NOTHING (`RyvXxApfHkk#11`, "The LLM is used to analyze
and categorize data, like the LLM, or LLM." in 0.28 s) — invisible to every similarity metric —
and, structurally, repetition loops that are NON-ADJACENT, which `dup_adjacent` cannot see by
construction. The two detectors are complementary; neither subsumes the other, and the tests pin
that claim.

**The strategic lesson, worth more than the detector.** Three text-similarity detectors were built
before anyone measured duration, and duration beat all of them on precision, recall, and grounding
— with less code. `_dehallucinate` in `transcribe.py` had been using near-zero duration as an
artifact signal at the WORD level since the beginning; nobody lifted it to the sentence level.
When the next detector is proposed, ask what physical invariant the defect violates before
reaching for a text comparison.

**Threshold 0.80 is a module constant, NOT a Config knob.** Every threshold in 0.70..0.95 yields
the identical single fire; the true positive (1.0000) sits in a 0.30-wide empty band above the
loudest benign pair (0.6977). A knob would advertise a tuning problem that does not exist. The
25-char guard is INERT on this batch (identical fire set at guard 0..40) — kept as a structural
guard for conversational corpora, explicitly not presented as validated.

**KNOWN MISS, documented on purpose:** this catches the verbatim-ECHO class only. Whisper
RESTARTS (a truncated line re-spoken differently) score 0.35–0.70 — `x7DfiXqSEdM` 298/299 is
0.6977, sitting between two benign pairs at 0.6667 — so no usable threshold separates them. The
`W4Ua6XFfX9w` four-Ds garble (0.5882) is a duplicated HEAD TOKEN across an enumeration, a
different defect. A clean `dup_adjacent` does not mean "no repetition defects here".

**Deliberate PLAN deviation, named rather than hidden:** PLAN says the check "must run on
sentences.json". It reads `src_en` from the already-in-memory translation.json instead. Same
bytes — both translate routes copy `src_en` verbatim (`translate.py:252`, `build_translation.py:87`)
and `translate.py:241` uses that equality as its resume key, so verbatimness is an enforced
invariant, not an assumption. Buys zero new I/O and zero new failure modes (missing/torn
sentences.json, id desync).

**`_RU_NEG_RE`: `без(?![а-я])` → `бе[зс](?!опасн|платн|условн|обидн|конечн|ед)[а-я]*`.** The real
bug was ASYMMETRY, broader than PLAN's framing ("scans for без with a з"): не/ни matched as
prefixes while без matched only as a standalone word, hiding **voiced** bound prefixes too. без/бес
is ONE marker split by voicing assimilation.

**A first cut widened it to a bare `бе[зс][а-я]*` and that was wrong — recorded because the error
is instructive, not because the numbers were bad.** On the corpus it looked free (neg_loss 3 → 2,
removing exactly the target FP `W4Ua6XFfX9w#32`, zero additions). Its justification was that
"non-negative бе[зс]- lexis (беседа, бешеный) has ZERO occurrences", but those two words are
absent from the corpus while the бе[зс]- lexis that IS present is безопасн-×18. The predicate was
ETYMOLOGICAL (privative origin) where the detector needs SEMANTIC (polarity): безопасный means
*safe*, so counting it as surviving negation makes "it is not safe" → "это безопасно" — a textbook
inversion — read as a kept negation and pass silently. Eight such constructions were caught by the
old regex and missed by the bare widening. A test was even added pinning one ("I don't like this
conversation." → "Мне нравится эта беседа.", negation genuinely dropped) as an *accepted miss*,
telling future maintainers that an inversion miss is fine for the one detector that exists to
catch inversions.

**The general lesson, which outlives this regex:** the module-wide "over-matching only ever causes
a MISS, the safe direction" rule does NOT apply to `neg_loss`. `completeness.py` anchors
prefer-miss to "the weak length signal most of all", and DECISIONS 2026-07-19 carves neg_loss out
by name — *"an inverted negation is the most dangerous silent loss there is, and one false positive
per batch is a fair price for never missing one."* For this detector a MISS is the failure mode the
detector exists to prevent. Citing the module docstring to justify lowering its sensitivity was
circular: the regex, the docstring sentence licensing it, and the pinning test all landed together.

**Shipped form subtracts positive-polarity stems** (`_NEG_POSITIVE_STEMS`). Re-measured over the
same 1101 sentences: **identical to the bare widening — 2 fires, the same two**, target FP still
removed, **zero new false positives**. So the correction is free on observed data and closes a
LATENT hole; the accepted cost is a flagged correct translation ("not dangerous" → "безопасно"),
which is the trade DECISIONS already priced. Both directions are now pinned by tests, including
one asserting the inversion IS caught.

**Rejected in the same pass:** adding `"i don't know"` to `_NEG_IDIOMS` (it would convert one FP
into a systemic miss over real negation — `_NEG_IDIOMS` is excised unconditionally before the
scan); an enumeration-head detector and a timing/chars-per-second detector (both real, both with
their own FP surface and tests — INBOX, not this commit).

**Artifacts do not self-heal:** `work/W4Ua6XFfX9w/report.json` keeps its stale neg_loss and
`ytEN_iAk09c` gains its dup flag only after a re-run of verify. No resynthesis needed — the
completeness loop never touches audio.

## 2026-07-19 — Run report (observability): two non-obvious choices in run.json

Built the per-run rollup (`overdub/runreport.py` → `work/<id>/run.json`, PLAN item 1). Two calls
worth recording; the rest is mechanical aggregation of already-persisted artifacts.

**RTF denominator source priority: info_json > ffprobe > sentences.** RTF (wall / video duration)
needs a duration, and the pipeline never stored one as a first-class field. Priority: (1)
yt-dlp's `source.info.json` "duration" — authoritative, already on disk, zero cost; (2) a
best-effort `ffprobe` on the source media — recovers the metadata-backfill path (info.json holds
only a title) at the cost of one guarded subprocess, the ONLY external call runreport is allowed;
(3) the last `sentences.json` "end" — always present once transcribe ran, but it UNDERSHOOTS
(trailing silence/music after the final sentence isn't counted), so it slightly inflates RTF —
acceptable as a last resort, and `video_sec_source` is stamped in run.json so the number is never
read blind. No duration at all → RTF null, never a fabricated denominator.

**Speed distribution metric = `combined_factor`, not raw `tts_speed`.** The distribution
(median/p95/max, count ≥ 1.8) is over `combined_factor` = native F5 compression × atempo top-up,
the REAL compression a listener hears — matching assemble's own `n_over_1_8_combined` triage bar
(DECISIONS 2026-07-17: native ≥~1.3 drops words, atempo tops up the rest; the combined figure is
the one that means "candidate broken"). Raw `tts_speed` alone misses the atempo half and
`speed_factor` (atempo demand) alone misses the native half — neither is the number the 1.8 bar
was calibrated against. Aggregated over UNIT leaders (report records fan out per sentence sharing
a `group_id`; dedup first-seen), so the count is units, not member sentences.
