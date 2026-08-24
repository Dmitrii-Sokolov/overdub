# Decisions log — the dated entries

The DETAIL half of the decisions record. `DECISIONS.md` at the repo root is the always-loaded
index; this file holds the dated entries it points at. Cite as "DECISIONS YYYY-MM-DD" anywhere in
the repo and resolve the date HERE. Newest first — **append new entries directly below the `---`
that closes this header.** Entries are not rewritten to match today's code: when the code moves
out from under one it gets a `> SUPERSEDED <date>` line and stays, because the rejected
alternative is the part worth keeping. Content is cut in exactly four cases — pure scheduling
that already lives in `BACKLOG.md` or a task file; a generalised lesson promoted to
`~/.claude/knowledge/`, where the entry keeps what it decided HERE and points at the file instead
of restating it; prose that decides nothing that still applies, i.e. a verdict on a retired
component or a roadmap ordering both overtaken; and — since 2026-08-24, the prune entry — a WHOLE
entry, when the code it describes is gone AND every lesson it holds is restated in a surviving
entry. The third is the narrow one: a REJECTED alternative is never dead — it is the part worth
keeping — so only the verdict-on-what-shipped half goes. Trims are stamped in place
(`Trimmed <date>: …`) and deletions are listed in the prune entry — neither is made silently.

**An appended entry is two edits: the entry here and its line in `DECISIONS.md`.** Both are
written at triage only; `tests/test_decisions_index.py` keeps the two files in sync.

The bottom third of the file is a forward-ordered archive of the founding week — see the ARCHIVE
divider. Look things up through the index, not by scrolling.

---

## 2026-08-24 — routes C and D leave the project; the second prune follows them through code and record

User decision: scouting a queue (route C) and digesting it (route D) are no longer goals of this
project, and route B's summarizer goes with them — the approaches themselves are not wanted, so
they leave the CODE and the RECORD, not just the roadmap.

**Code.** Deleted: `.claude/skills/overdub-scout/`, `.claude/workflows/scout-summarize.js`,
`scripts/build_scout.py`, `tasks/s2-artifact-route.md`, the summarizer half of
`translate-batch.js` (`sumIds`), and every `summary.md` / `scout.json` producer and reader
(`read_summary`, the digest's summary block, the page's scan table and content columns).
Two things route C was carrying SURVIVE because the remaining routes stand on them: the
audio-only fetch mode (route E's input) — renamed `--scout` → `--transcribe-only`,
`scout_stages` → `transcribe_only_stages`, workdir kind `scout` → `transcribed` — and the queue
page (route B's listen-to-flagged-units surface) — `scripts/scout_report.py` →
`scripts/queue_report.py`, output `work/queue-report.html`, now dub triage plus state cards and
nothing else. The 2026-07-21 rejection of that rename ("reference churn… revisit if the name
starts misleading") reached its named trigger: the route the name pointed at no longer exists.

**Record.** Entries DELETED under the prune rule (code gone AND every surviving lesson restated
elsewhere): both 2026-08-03 scout entries (route D deleted / viewer profile removed), the
2026-07-30 two-pass digest entry, the 2026-07-20 grades-the-material entry, and the 2026-08-20
route-B-summarizer entry (its one general lesson — cost tracks turns × context, not output
length — lives in the surviving 2026-08-20 entry). The 2026-07-25 TOOL entry moved to
`CLAUDE.md` at the user's call: it was a founding framing that predates the repo, never a
decision taken here, and CLAUDE.md is where a standing work-selection rule belongs. TRIMMED, at
the user's ask to squeeze the TTS cluster down to "engines tried, Silero chosen": the Silero-only
entry (host_guard story → `scripts/host_guard.py` + CLAUDE.md; stress/CMUdict →
`tasks/cmudict-transliteration.md` / `tasks/stress-audit.md`), the v5 audition (three ear defects
→ their successor line items), the two 07-16 F5/ESpeech entries merged into one, and the founding
entry's named first-pick tools (the day-1 TTS engine, the local translate LLM) cut — the day-1
bake-off entry remains the record of what was tried. The 2026-07-20 audio-only-mode entry is
retitled to the mechanism that survives it.

**Deliberately KEPT despite the deletions:** the queue-contract §5/§6 measurements that happened
on route C (labelled "the since-deleted scout route") — they are the evidence for rules that bind
routes B and E today, and evidence does not improve by forgetting where it was collected.

## 2026-08-24 — the log is PRUNED: dead-engine and dead-route entries deleted or trimmed

First deliberate deletion pass over this file, user-driven. The header's cut policy gains a
fourth case: a WHOLE entry may be deleted when the code it describes is gone AND every lesson it
holds is restated in a surviving entry. The whole pass: 536 lines replaced by 113 (the commit
diff is the exact record). Deleted under that rule: the F5
speed ledger + `f5_nfe` pair (levers of an engine closed by user decision 2026-07-25 — it is not
coming back, so "would be re-investigated from scratch" no longer paid for the pages), the
ESpeech narrator voice, Gemma-replaces-Qwen3 and Silero-v5-acknowledged (the local-LLM translate
era), the dead-air interim ear verdict (its final verdict is 2026-07-17), route D's
separate-page entry (the route died 2026-08-03), and the 2026-07-15 stack verification
(Chatterbox/Qwen/Ollama — none in the stack; the cuDNN-DLL gotcha lives in STACK.md). Trimmed to
their living organs: the ESpeech bake-off (EN-clone dropped by GOAL + "supports Russian is
marketing"), F5Engine BUILD (fd-dup capture, single-writer manifest, `synth_key`), the translate
design panel (the normalizer half), route D's two-pass entry (the composing/compressing split),
and dead-air BUILD's L1 paragraph. Deliberately KEPT despite dead surroundings: the day-1
Chatterbox/XTTS rejection (negative knowledge), the v5 audition (home of the voice ear-ranking
CLAUDE.md cites against `aidar`), and the local-only amendment (a founding-constraint change
never vanishes from this file). Every "DECISIONS YYYY-MM-DD" citation in the repo was checked to
still resolve after the cut.

## 2026-08-24 — DECISIONS splits: the index stays at the root, the entries move here

The 2026-08-24 migration entry below kept DECISIONS.md a single file (index + entries) to
protect date-cited lookups. The user overruled it the same day, and the counter-argument is the
format's own: DECISIONS.md is the always-in-context half of the record, and at 3100+ lines it
had none of that property — the index was load-bearing precisely because nobody could scroll the
file. So: `DECISIONS.md` = the thematic one-line index alone (~120 lines, small enough to always
load); `docs/decisions-log.md` = every dated entry, moved verbatim via `git mv` so history and
bytes are untouched. What survives from the superseded deviation: citations stay
"DECISIONS YYYY-MM-DD" (full dates resolve here, the index carries `MM-DD`), and the index keeps
its thematic sections instead of the format's flat `DATE | decision | reason` rows — at 100+
entries the grouping is what makes it scannable, and the labels already carry the reasons.
Index lines whose detail lives in a module doc or task file instead of this log carry a trailing
`→ <path>` link and are exempt from the index↔log sync check.

## 2026-08-24 — agent-docs replaces the 4-file framework; PLAN.md dissolves

> PARTLY SUPERSEDED 2026-08-24 — the "single file" deviation in the second paragraph lasted a
> day: the user chose the index/log split (see the entry above). The migration itself stands.

Chose the portfolio-wide agent-docs format (`BACKLOG.md` + `tasks/<slug>.md` + module
`CLAUDE.md` files + append-only `INBOX.md`, with BACKLOG and DECISIONS written only at triage)
over keeping the project-local 4-file framework — the portfolio had already migrated and this
project was the last holdout running its own spec. PLAN.md's content routed four ways: ordered
items → BACKLOG "Open" plus `tasks/` files carrying their accumulated context; measurement
fences that guard data still on disk (the F5-corpus identification pair, the `total_wall_s`
scope change) and standing pipeline constraints → `overdub/CLAUDE.md`; dead figures → the
retirement entry below; the publication-rights gate → README "Voices, cloning and the law".

**Deliberate deviation from the format:** DECISIONS.md stays a SINGLE file — the hand-maintained
one-line Index up top with dated entries as the detail — rather than a bare index with details
scattered into module docs. Dozens of "DECISIONS YYYY-MM-DD" citations in code comments, README,
STACK and the route skills resolve by grepping this file's dated entries; splitting would break
every one of them for zero benefit. `tests/test_decisions_index.py` keeps the index honest
either way. Reconsider if the index stops being maintained or triage starts skipping it.

## 2026-08-24 — retired with PLAN.md: F5-era stage shares and pre-07-22 wall-clock figures

PLAN "Numbers to re-measure" quarantined these as groups (B) and (C); with PLAN dissolved they
are retired here so the numbers stay greppable as DEAD. **Retired, do not re-quote:**

- **(B) F5-era batch stage shares:** synthesize 47.6% · transcribe 21.3% · download 9.8% ·
  verify 8.3% · mux 7.9% · separate 4.9%; batch RTF 0.451 (7.26 h → 3.27 h); the 2026-07-24
  36-run split (synthesize 52.6 + verify 7.6 + mux 7.4 + separate 4.8 = 72.7%); and the
  "3.3 h → ~1.9 h, RTF → ~0.26" projection, which extrapolated one video to a batch.
  Replacement: `tasks/retime-batch-silero.md`.
- **(C) pre-2026-07-22 stage-wall derivatives:** the ~72 s/video model-loading fixed cost, the
  2026-07-19 audition whole-pipeline RTF pair (Silero 0.14-0.17 vs F5 0.70-0.92 — unlabelled,
  two unquotable numbers), and every `breakdown_pct` of that era. Replacement: re-derive from
  `rtf_work` on the next pass.

The LIVE fences moved to `overdub/CLAUDE.md`, not here — they guard artifacts still on disk
(36 F5 manifests, 252 pre-08-05 timings.json) whose provenance exists only in the docs.

## 2026-08-20 — fewer turns per translator; the batching knob was not the one that mattered

An agent's cost tracks **turns × context**, not the text it produces: measured 2026-08-20 on 47
translators, cache traffic is 78% of a translator's tokens and output is 2.5%. So the target is the
turn count — median 11. This entry records what was actually in those 11, because the obvious answer
was wrong.

**What the turns were.** Mean tool calls per agent: Read 2.8 (contract, transcript, verify
read-back), PowerShell 1.0, Bash 1.0, Write 0.6, Edit 0.6 — about 6 tool turns, so ~5 turns carried
no tool call at all and were pure reasoning.

**The defect: 43 of 47 agents wasted two turns on a blocked call.** The marker instruction read
`Use PowerShell: New-Item ...`, and a shell NAME reads as a binary to invoke — so the agent called
Bash with `powershell -NoProfile -Command "New-Item ..."`, `hooks/block-shell-search.ps1` refused
the cross-wrap, and the agent recovered by using the PowerShell tool. That is 91% of agents paying
for one wrong word. The prompt now names the TOOL and says the wrapped form is blocked. General
lesson: **in a sub-agent prompt, name the tool, never the shell** — the agent has both a Bash tool
and a PowerShell tool, and a shell name does not select between them.

**Rejected as the lever: the batching instruction**, which is what the change set out to fix. It
said "for a long video (300+ sentences) write in batches of ~50", and it was not firing at all on
this queue — Write+Edit measured 1.2 calls per agent, median payload 7080 chars, because a typical
video here is ~130 sentences and never crossed the threshold. Changing it would have bought nothing
on the videos actually being run. It is still raised — one pass by default, split only above ~400
sentences and then into ~200 — but for LONG videos only, and the honest expected saving on a normal
batch is zero.

**What the batching change costs, accepted deliberately.** A draft written in one pass is lost
entirely when the agent dies mid-run, where batches left a partial file that parses — on 2026-08-20
that is exactly what preserved 230 sentences across three videos when a session limit killed the
wave. The user accepted that trade: the loss is one respawn for one video, against turns paid on
every video. The ~400-sentence split survives for a different reason — a single write that long
risks truncation, and a truncated array is invalid JSON, which is worse than a short one.

**NOT established:** what the ~5 reasoning turns cost or whether `effort: 'low'` would cut them.
The workflow does not set `effort`, so agents inherit the session's. Output is only 2.5% of tokens,
so the ceiling on that lever looks low, but thinking also lengthens the turn chain and that was not
measured. PLAN carries it.

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

## 2026-07-25 — Silero becomes the ONLY engine

Trimmed 2026-08-24 (the TTS cluster squeeze, user-driven): the lowpass forensics, the grouping
re-cut numbers, the host_guard retraction (restated at `scripts/host_guard.py` and in CLAUDE.md)
and the stress/CMUdict detail (carried by `tasks/cmudict-transliteration.md` /
`tasks/stress-audit.md`) are gone. What this entry still decides:

**User decision: F5/ESpeech is replaced by Silero v5_5_ru outright, on speed and hardware cost,
with the quality difference accepted as a deliberate trade.** Explicitly NOT a parallel-engine
setup — per-engine knobs were considered and declined; the shipped defaults are tuned for Silero
and the F5 path comes back out of git history if the switch fails. This reverses the 2026-07-16
ear verdict that made F5 production and Silero fallback. Later the same day the switch was
**ear-confirmed on finished MKVs** (quality sufficient where it is actually consumed) — a verdict
about the VOICE that does not close the slot holes: fill is a TIMING defect and stayed open
(`atempo_floor`, `tasks/slot-fit.md`).

Shipped with the switch, each by ear: `dub_lowpass_hz = 11000` (the "шипение" is vocoder noise
tracking the speech, not sibilance — one pass over the finished dub in `assemble`, post-verify,
outside `synth_key`); the grouping re-cut to 1.2/20/600 (the old constants were F5-shaped);
and SSML `<break>` restoration — built, measured, **REJECTED by ear** (it put back 8% of a hole
made by assembly while adding pauses the speaker never took; ships off at
`silero_ssml_breaks = False`). The price of the switch, named then and still true: Silero has no
`supports_target`, so timing fit is the pipeline's job now.

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

## 2026-07-20 — Audio-only fetch mode: its own flag, and a promoted video re-downloads

Born as the scout route's fetch step; the route was deleted 2026-08-24 and the mode survives as
route E's input (`--transcribe-only`, née `--scout` — retitled and trimmed in that pass). Each
choice below is cheap to "fix" later in exactly the direction that undoes the reason it exists.

**1. The mode fetches AUDIO ONLY, and a promoted video re-downloads.** `yt-dlp -f bestaudio` →
`source.wav`; no `source.mkv`, so `DownloadStage.done()` splits into an audio gate and the unchanged
video gate. The forcing constraint is disk, not time: a 100-video queue in
full mode wants ~100 GB in hour 0 (stage-major hoists all downloads to the front). A transcript
pass that cannot fit on the disk is not a transcript pass.

**Cost, named: promotion re-downloads the audio bytes inside the merged MKV — ~5% extra traffic,
paid on exactly the videos that were worth dubbing.** Accepted for zero new machinery: no cache, no
container surgery, no third gate. A second, subtler cost rides along — the promoted run OVERWRITES
`source.wav` with a differently-decoded file (ba[ext=m4a] out of the MKV, vs bestaudio's opus), while
`sentences.json` was read off the old bytes and `--repair-asr` will clip windows from the new ones.
Same YouTube master and same timeline, so this is believed benign; it has not been checked
(`tasks/reuse-audio-on-promotion.md`).

Rejected, all three for the same class of reason: **letting the video gate accept `source.wav`** —
mux then gets a container with no video stream, i.e. the failure lands eight hours later at the end
of a run; **skipping re-extraction when `source.wav` already exists** — saves the rewrite and leaves
a wav from a DIFFERENT fetch as the permanent input to a full run, which is a stale artifact served
as current; **a separate audio workdir** — two directories per video and a promotion step that has
to move files, to save a fetch that costs 5%.

**2. A dedicated flag, not `--only download transcribe`.** The flag selects a stage list that
constructs the truncation and the audio-only `DownloadStage` in one
expression. `--only` cannot express the audio-only download at all — that fact lives INSIDE the
stage — and `run_pipeline` checks STOP before the only/done filters, so an `--only` composition
would sweep 8 stages and grid 8 STOP checkpoints per video to do 2 stages of work.

**Cost, named: a flag that must be kept in sync with the stage list.** Adding a stage to
`all_stages` that belongs before transcribe will not appear in the truncated list, and nothing
enforces that it stays a strict PREFIX of the full pipeline — which it must, because a promoted
video re-enters the full pipeline on the artifacts these two stages produced. Mitigations, both
partial: the prefix property is pinned by a test, and the two facts that could actually corrupt a
run (truncation + download shape) are welded into one expression so they cannot drift apart. The
flag also has to be excluded by hand from every other mode — `--only` and `--repair-asr` both
needed a usage-error clause, and a third mode would need a third.

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

Trimmed 2026-08-24 (the TTS cluster squeeze): the three ear defects went — hiss closed by the
2026-07-25 lowpass, slot lag became the slot-fill line of work, expressiveness lives in
`tasks/input-prosody.md`. What stays decides:

**The 2026-07-15 bake-off tested the wrong release.** `v4_ru` was already superseded when it was
adopted; the adapter then hardcoded it, so every Silero verdict in this file up to then describes
an outdated model. `v5_5_ru` is audibly better and became the default; v4 stays reachable only to
reproduce pre-2026-07-19 runs.

**Ear ranking (user, 5 videos × 5 voices, one voice per video, v5_5_ru):**
- **kseniya, eugene — best.** These are the two to use.
- **xenia** — good voice, slightly unpleasant.
- **aidar, baya** — off-standard accent, sounds harder to follow; phonemes drift from ordinary
  Russian. Avoid.

**Speed is the headline: synthesis is 12-19× faster than F5 and CPU-only** (measured on the same
5 videos: synth 11-14 s vs 128-250 s), with round-trip similarity at near parity. This is the
measurement the 2026-07-25 engine decision then rested on; at the time the verdict was "quality
below F5, trade accepted for the fallback role, production stays F5".

**Migration lesson, load-bearing beyond this engine:** `cfg.silero_model` had to enter
`synth_key` — without it v5 would have silently reused v4 wavs under the same voice name, the
exact silent-staleness class the `synth_key` INVARIANT exists to prevent.

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

*(Trimmed 2026-08-24, user-driven: the named first-pick tools — the day-1 TTS engine and the
local translate LLM — are out of the stack and their paragraphs are gone; the day-1 bake-off
entry below keeps the record of what was tried and rejected.)*

**A cloning-capable engine as the first TTS engine**, with fallbacks behind a common interface;
if its Russian fails the ear test — switch, don't polish.

**Timing strategy: per-segment TTS + atempo up to x2.** Russian runs 15–25%
longer than English; an x2 compression budget covers ~99% of segments. The user
validated by ear that x2 is acceptable. No smarter time-borrowing logic in v1.

**Local translation via a local LLM server.** Operationally simpler than cloud
(no keys, no billing, offline), free at any volume. Quality loss vs frontier
models is acceptable for a dubbed track; upgrade path is a URL swap since
the server speaks the OpenAI protocol.

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
speaker (short reference clip from source audio). This is the
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
applies to the heavy models only (ASR / the local translate LLM / TTS).

**EN→RU fixed.** Source is always English, output always Russian. No language
detection or multi-language handling anywhere in the pipeline.

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
> translation runs through Sonnet sub-agents (route B). Trimmed 2026-08-24: the endpoint /
> `think: false` / sliding-context-window half was deleted with it. The NORMALIZER half below
> is LIVE.

**`text_tts` is derived, never model-written: `text_tts = normalize_for_tts(text_ru)` in
deterministic Python.** Rejected design B (the LLM emits `text_tts` too): a model-spelled
`text_tts` would diverge from the Python normalizer the verify stage applies to the ASR
hypothesis, silently depressing similarity on correct numeric dubs — the one silent-failure
class the project forbids. The normalizer must exist as a pure function for verify regardless;
reusing it as the sole `text_tts` source makes the round-trip exact *by construction*.

**Normalization is SAFETY-CRITICAL, not incidental.** Because verify normalizes both sides with
the same code, a magnitude bug (a number voiced with the wrong value) is architecturally
invisible to the round-trip — it self-agrees and passes unflagged. So the normalizer gets its
own direct ground-truth tests, not only round-trip coverage. The review caught three real
magnitude/mangling bugs, fixed + regression-tested: grouped thousands read as decimals
(`$1,999` → 1.999, ~1000× low; `10 000` → "десять ноль"), decimal ranges shredded (`3.5-4.5` →
"три.от пять…"), and Cyrillic `х`/`с` in the multiplier/Celsius classes mangling ordinary
Russian ("ось х 5", "90° севернее").

**num2words (ru locale) approved as a dependency** for Russian cardinal/ordinal spelling
(fiddly to hand-roll correctly); a stdlib 0..10⁹ speller stays as the import-fallback. Accepted
loss: num2words yields nominative case, so oblique numerals are occasionally voiced in the
wrong case — self-consistent for verify, so never false-flagged; audibly-rough-but-not-silent.

**Never-drop invariant (still the translate contract):** validate → retry → flagged English
fallback, never drop a sentence; id-contiguity enforced with `raise`, not `assert` (must
survive `python -O`); each record carries `src_en` so a re-tuned `sentences.json` (same id,
changed text) forces re-translation instead of reusing the stale RU — that equality is also
the resume key both routes rely on.

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

## 2026-07-16 — the F5/ESpeech era: bake-off #2 won by ear, EN-clone dropped, three surviving mechanics

> **SUPERSEDED 2026-07-25** — ESpeech/F5 was removed in favour of Silero v5_5_ru; `.venv-f5tts`
> is not a live dependency. Two 07-16 entries merged 2026-08-24 (the TTS cluster squeeze) into
> what outlives the engine.

**EN-reference cloning (the founding "same-voice" premise) was made to WORK — and DROPPED by
goal, not by failure.** The round-1 babble was a byte-ratio canvas artifact, both predicted fixes
verified on a full video (exact Latin ref transcript + speed set by byte-rate ratio → sim 0.980);
the approach is workable and could be polished further. **Decision (user): the project goal is a
quality Russian dub, not speaker identity — the direction is dropped.** Any revival argues with
that decision, not with the technique.

**Research lesson:** "supports Russian" in an engine's language list is marketing — of ~20 engines
swept with adversarial verification, only Silero/ESpeech/Misha credibly spoke Russian (the
Chatterbox lesson generalizes). The research trail (`bakeoff/`) was deleted 2026-08-03; what
survived it is the licence table in README, "Voices, cloning and the law".

Three mechanics from the F5Engine build that outlived it:

- **fd-level stdout capture in subprocess workers.** The worker's FIRST act is `os.dup(1)` +
  `os.dup2(2,1)` BEFORE heavy imports — Python-level `sys.stdout` rebinding does not survive
  native fd-1 writers, and a stray print into the JSONL protocol channel is a crash.
- **`segments/manifest.json` is single-writer (synthesize only).** assemble derives atempo
  factors from manifest `samples`, so a wav replaced by any other stage against a stale manifest
  is silent timing desync — the forbidden class. Ordering discipline can only narrow that
  window; single-writer eliminates it.
- **`synth_key` gates all wav reuse.** Everything that changes rendered audio enters one
  canonical string, with the INVARIANT that every new audio-affecting knob joins it — content
  hashes over mutable-path inputs, because stems lie. Still what protects against silently
  stale segment wavs (the v5 audition's `silero_model`-into-`synth_key` case is the proof).

## 2026-07-16 — Dead-air elimination: design panel + review (BUILD)

> **PARTLY SUPERSEDED 2026-07-25** — L1 slot-fill is written against F5's deterministic duration
> canvas and died with the engine; Silero's slot behaviour is a separate open item (PLAN). L2
> render units and L3 mix (duck/bed) are LIVE.

Panel (minimalist/contracts/audio + 3 judges) + 4-lens adversarial review (20 findings,
1 refuted, all fixed). Three composable layers against the measured 607-s underfill (an F5-era
figure whose decomposition was trimmed 2026-08-03; the live Silero baseline is 283 s of slot
silence on `8zJlKmgMT44`, in `2026-07-25 — atempo_floor = 0.75`):

**L1 slot-fill native speed — died with F5** (detail deleted 2026-08-24: it planned per-unit
`speed` off F5's deterministic duration canvas, stretch-to-SPAN-never-slot). Silero slot
behaviour became its own line of work: `atempo_floor` (2026-07-25) and `tasks/slot-fit.md`.

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
