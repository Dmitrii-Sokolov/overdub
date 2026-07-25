# PLAN

## → Roadmap (re-cut 2026-07-20 evening — route C is in production; its throughput leads now)

**Where the project stands.** Route C (scout) has been run repeatedly on real queues and works:
audio-only fetch, transcribe, Sonnet grading, published report. It is the route in daily use, so
its cost is the thing worth attacking. The grade quality is ACCEPTABLE on real material — no
longer an open item (see Deferred for the improvement question). Route B (Sonnet dub) is the
primary dubbing route and unchanged. What is NOT settled is speed: the summarize wave dominates
scout, and until this evening there was no per-video number to optimize against.

**Updated 2026-07-22.** The timing accounting is finished as a mechanism: `synthesize` and
`translate` now carry `detail` entries beside their stage walls, and `run.json` publishes
`rtf_work` alongside `rtf`. So "measure one lever at a time against a stored baseline" — which
the transcribe item asks for — now has an instrument that a resumed run or a batch position
cannot quietly corrupt. One claim in the old accounting item was itself wrong and is corrected
below: the `nfe` 48→16 = 2.16× figure was never wall-clock contaminated.

Sample workdirs: `work/` (33 dirs — Silero baselines, the AI-Fluency batch, and the scouted
queues, read-only).
**Corrected 2026-07-20 — the rest of this line was stale:** `work-exp/context-earcheck/`,
`work-exp/stats-batch/` and `work-exp/gemma-ab/` NO LONGER EXIST on disk (`work-exp/` holds only
`nfe-sweep/` and `nfe16/`). The Qwen-vs-Gemma A/B set and the 8/23 stats-batch workdirs are gone;
the published A/B report artifact (508 sentences) is the only surviving record of that comparison,
and the stats-batch URL list is unrecoverable. Report triage: any *_flag or speed_factor>1.8.

**Before the first overnight batch on the new order — two side effects, neither a bug:**
(a) `download` amortises nothing, so hoisting it means a 100-video queue downloads in full before
the first transcribe — ~100 GB in hour 0. `--scout` removes this for a TRIAGE pass (audio only), not
for a dubbing batch. Watch for ENOSPC; the compensation is that network
failures surface immediately instead of smeared across the night. **Measured 2026-07-20: 81 GB free
on D: (of 3.8 TB).** That is less than one full large-queue run, so queue size is bounded by disk,
not by patience — and the already-deleted `work-exp/` baselines suggest a space cleanup has happened
once already. Decide what in `work-exp/` is a consumable and what is an archive BEFORE the next
3am cleanup makes that call for you.
(b) `_title_of` is a networked `yt-dlp --print title` with a 30 s timeout for pre-change workdirs.
Those calls used to be spread across the batch; in the finish sweep they queue back-to-back — an
offline resume of 12 videos can sit in up to 6 minutes of timeouts in one block at the very end.

**Carried into the next ordinary batch — not gates, just things to look at when they pass by:**
- listen to the repaired unit in the finished MKV (repair changed a TTS unit boundary, so `atempo`
  on that unit changed too);
- `--repair-asr auto`'s recall (5/12) and the `RyvXxApfHkk#11` 246-vs-35.9 ch/s discrepancy are
  both unreconciled — DECISIONS 2026-07-20, provenance section. Treat the fixture as a signal.
**Scout is exercised, not theoretical — the 2026-07-20 "never run on real media" caveat is
closed.** Multiple real queues have been fetched, transcribed, graded and published. `-f
bestaudio` has not failed on a real source; the info.json rename lands (no workdir pays the 30 s
networked title lookup); grades read as reasonable against real material. Still unconfirmed on
real media, because nothing has needed it yet: **one promotion end to end** — `transcribe` must
fast-skip while `download` re-runs.

**MEASURED 2026-07-21** — four runs, same 6-video queue (2:53:44, 1683 sentences), one change at
a time. Full table in CHANGELOG. Route C now costs, per pass over this queue:
download 162 s · transcribe 723 s wall / 718 s work (RTF 0.087) · summarize wave **192 s**.
Baselines preserved under `work-exp/wave-*-2026-07-21/`; a re-run of that queue overwrites the
live artifacts, so copy the six `scout.json` before repeating it.

---

**Items are NAMED, not numbered (2026-07-22).** The numbers were re-cut with every roadmap and
the references in code never moved with them, so by this week "PLAN item 1" meant the F5 speedup
in `exp_nfe_sweep.py`, the source-anomaly pass in `runreport.py`, proper nouns in DECISIONS, and
transcribe here — four different things, one label. Every such reference in code and tests now
names its TOPIC (the queue-page merge, the source-anomaly pass, the video summary), which cannot
rot when this list is re-ordered. Do not reintroduce numbering; CHANGELOG and DECISIONS entries
that carry the old numbers are historical records and stay as written.

---

## Batch 2026-07-25 — 24 videos, route B (analysed; SEVEN FIXED same day, three residues open)

**Status: the seven items below are IMPLEMENTED — full record in CHANGELOG 2026-07-25.** They are
kept here in full because each one's EVIDENCE is the measurement, and the next batch is how the
fixes get judged. What to check on the next route-B run, in order:
1. `needs_triage` count (was 23/24 → 16/24 on the same artifacts). If it is back near N/N, the
   actionable set has drifted again — look at what is padding it before adding another detector.
2. The `- pronounce:` line per video. It ranged 9..248 invented readings here; a video near 200 is
   telling you which tokens the dictionary still lacks. Feed the top of its audit back into `WORDS`
   (proper nouns / closed class only) or into a rule.
3. Whether Step 1b (`--repair-asr auto`) actually fires, and whether the ×1.8+ unit count drops from
   17. That is the one fix whose effect is unproven — nothing was re-run to verify it.

**Three residues stay OPEN and are NOT in the fixed set:**
- **Transcription rules for open-class words.** `execute → эксекют` (18 hits), `adventures →
  адвентурс`, `fields → фиелдс`, `open → опен`, `waters → вейтерс`, and `buy → буи` (pre-existing,
  spotted while measuring). By the WORDS contract these are the fallback's job, not the dictionary's,
  and a rule touching `ex-`/`ie`/`-ute` is ambiguous in English ("exit" wants экс, "execute" wants
  эгз) — so this needs a rules cycle WITH an ear check, not another dictionary line. ~55-rule
  ceiling applies.
- **`neg_loss` fired 19 times and every case inspected was correct** — the negation was carried
  lexically ("Hell no" → "Чёрта с два", "no matter what" → "вне зависимости от", "are not equally
  spaced anymore" → "перестают быть"). It was deliberately NOT demoted with the others: DECISIONS
  2026-07-19 carves it out by name ("an inverted negation is the most dangerous silent loss there
  is, and one false positive per batch is a fair price"). 19 per batch is not one per batch — that
  is a decision to revisit in DECISIONS with this number in hand, and it is the user's call.
- **Sentence splitting loses 166 endings** (the last item below, untouched).

Evidence: `queue.txt` + the 24 `work/<id>/` dirs from that night (all 24 muxed, no crash, no real
translate failure). 7.26 h of source in 3.27 h of pipeline work, RTF 0.451, per-video RTF band
0.38-0.50 (the one outlier, `Tu2cCEMwvHI` 0.78, is a 631 s download — network, not the pipeline).
Stage shares of the summed wall: synthesize 47.6% · transcribe 21.3% · download 9.8% ·
verify 8.3% · mux 7.9% · separate 4.9%. Compression is mild almost everywhere: 78.1% of 4321
units sit at cf ≤ 1.05, only 60 units above 1.4. **Nothing below is a speed item** — at RTF 0.45
a 24-video night finishes in three hours; what fails is knowing WHICH videos to open and what a
listener actually hears.

### Report — the batch wall time is unlabelled and unreadable (operator report 2026-07-25)
The three surfaces that print batch totals all print raw seconds with no unit conversion and no
statement of what the number IS: `scripts/run_report.py` (`totals: wall 11778.0s`),
`scripts/scout_report.py` header (`24 видео · wall 11778.0s`) and `overdub/cli.py`'s batch sweep
(`total wall 11778.0s`). Two defects, one line each: (a) 11778 s means nothing to a human reading
a morning report — it is 3 h 16 min; (b) the label "wall" is actively wrong for what it holds. It
is the SUM of per-video stage walls, not the elapsed time of the batch: this night ran ~21:53 →
03:07 (~5.2 h) because the route-B Sonnet translate wave sits between transcribe and synthesize
and no stage timer covers it. Fix the formatting in the shared layer (`queueview.batch_totals`)
so all three surfaces move together, and name the number honestly ("суммарная работа пайплайна",
not "wall"). `totals_of`'s existing rule stands and is the reason this is a LABEL fix, not a new
grand total: do not add a sum of work to a wall clock and call it "итого".

### «Самое интересное» is empty for 18 of 24 rows (operator report 2026-07-25)
The scan table's highlight column renders `—` for every dubbed-but-never-scouted video
(`scout_report._views`, the `highlight` key), because it reads only `scout.json`, which route B
never writes — 6 of these 24 had it from an earlier scout pass, 18 did not. The content EXISTS:
every one of the 24 has a `summary.md` whose second paragraph is exactly that field («Самое
интересное — французское исследование 2022 года (около 3:50)…»). This is the same gap
`_one_liner_from_summary` already closed for the «о чём» column on 2026-07-22 — the symmetric
half was never done. Two parts: (a) derive the highlight from `summary.md`'s second paragraph in
the renderer; (b) the summarizer prompt asks for "(a) worth watching (b) the most interesting
thing" as free prose, so 2 of 24 answered in ONE paragraph and ~6 opened paragraph 2 with the
watch-verdict instead — pin the shape in the prompt (paragraph 2 leads with the highlight). The
prompt is SHARED with `overdub-scout`; change both or the routes diverge.

### `english_echo` fired 28 times and was wrong 28 times
Every one is Sonnet correctly keeping Latin that must stay: CLI invocations (`task-master init`,
`npm run dev`, `/update-doc initialize`), filenames (`contact-session-1.md`), and set phrases
(`free-to-play`, `gold edition`, `executable code actions`). They are counted as translate
FAILURES and land in `flags_actionable`, which is why `1L509JK8p1I` reports 15 actionable flags of
which 11 are this. Either whitelist the shape (a token that is a command/path/identifier, not
prose) or drop `english_echo` out of the actionable set. Note what the audit shows about the
consequence: these units DID reach TTS and were transliterated («таск-мастер парс-пи-ар-ди
скриптс/пи-ар-ди.ти-экс-ти»), i.e. the pipeline handled them; only the report lied.

### `needs_triage` marked 23 of 24 — the metric is dead a second time
Same failure the `entity_loss` demotion fixed in `runreport.py` (its own comment: "11 of 12 …
carries the same information as marking none"). Today's actionable pool is padded by the 28
false `english_echo` plus `rate_implausible` (54) and `dup_adjacent` (35) — and both of those
detectors read the EN SOURCE (`completeness.py` says so), so they describe a whisper defect a
listener cannot fix by opening the dub. Measured alternative on this batch: counting only
dub-side evidence (a `verify_flag`, an `assemble_flag`, or cf ≥ 1.8) gives **9 of 24**. Keep the
source-side counts printed as advisory; stop letting them decide whether a human opens a video.

### The worst units are broken SLOTS, not long Russian
17 units at cf ≥ 1.8, up to **12.5×** (`iWRmtPdFbGw#10`: slot 0.46 s for 5.24 s of speech;
`aVwxzDHniEw#198` 2.32 s for 11.34 s; `8zJlKmgMT44#130-133` — four source duplicates sharing one
5.74 s slot). At ×12 the unit is unconditionally garbage and it ships silently: `assemble_flag`
is None on all 17. This is a pre-synthesis check, not a translate problem — a slot implausibly
short for its text should be flagged and merged/dropped before the TTS spends time on it. Note
the arithmetic that makes this cheap: with 78% of units at cf ≤ 1.05, "no tempo cap" is barely
exercised, so a hard bar at the top costs almost nothing.

### `floor_ratio ≥ 0.085` never fired — the signal is the RUN LENGTH
Batch max was 0.070, so `--repair-asr` triggered on nothing (repair windows 0 across 24) — while
`aVwxzDHniEw` has `floor_longest_run` **82** with a visible end-of-video collapse ("а затем почти
всё это «джастиали» сделано мной") and `8zJlKmgMT44` has 45. Both are also the videos with the
worst cf. The `config.py` comment already admits the ratio is "knowingly unreliable" for
borderline detection; on this batch `floor_longest_run ≥ 40` separates exactly those two and
nothing else. Recalibrate off the accumulated series as that comment asks — but recalibrate the
CHAIN, not the ratio.

### Transliteration is the largest defect in the batch and nothing measures it
`pronounce_audit.json` (present for all 24) records **1587 fallback transliterations** + 466
correct letter-by-letter ones, across 653 distinct Latin tokens — and none of it reaches
`run.json`, the digest, the HTML or triage. The fallback is literal, not phonetic, so the
listener hears `readme → ар-и-эй-ди-эм-и` (×11), `heroes → херос` (×50), `builder → буилдер`,
`execute → эксекют`, `facebook → фасебук`, `fields → фиелдс`, `euro → эуро`,
`adventures → адвентурс`. The top 40 tokens cover ~700 of the 1587 occurrences, so a hand-written
dictionary of ~50 entries is the highest-value hour available in the project right now. Two
sub-findings worth keeping: `of` (×23), `to` (×13), `the` (×11), `for` (×9) went through the
transliterator at all, which means whole English fragments reached TTS; and the audit should
surface a count in `run.json` so the next batch cannot hide this again.

### Sentence splitting loses 166 endings (lower priority, but it is OURS)
Of 388 source anomalies the Sonnet pass reported (9.0% of 4321 sentences), 166 are `truncated`
and they cluster in live Q&A material where whisper emits no terminal punctuation
(`2qrzI8YCVgI`, `Tu2cCEMwvHI`: "cut off mid-thought; continues into id 212", consecutively).
The rebuild from word timestamps is our step, so these are our splits, not source damage —
distinct from the 143 `garbled` / 60 `dup_neighbour`, which really are whisper's.

---

### Transcribe speed — CLOSED 2026-07-24 (measured record in CHANGELOG + DECISIONS)
Transcribe is still the bottleneck (~907 s per pass over the 6-video queue, 79% of a scout pass,
RTF 0.087 on large-v3 / fp16 / beam 5), but no cheap lever moves it. **All four candidate levers
measured, none adopted:** beam 5→1 and int8_float16 rejected (int8 is 24% SLOWER, beam trades a
worse error class — fp16 large-v3 on Ada is at the decode ceiling); distil-large-v3 rejected by
decision (validation costs an ear cycle, its likely failure — degraded timestamps — is invisible
to the probe); cross-video threading real but shallow (N=2 ~1.15× and unstable, N=3 a net loss)
and too costly to adopt (parallelising the stage breaks resume, `_guard`, and the just-built
`detail.transcribe` accounting). Full record: CHANGELOG 2026-07-22 (beam) + 2026-07-24 (int8,
threading); rationale DECISIONS 2026-07-24. **Reopen only** on different hardware (a second GPU for
real parallelism, or a non-Ada / CPU host where int8 pays off) or distil cleared by ear — not
another probe on this host. `word_timestamps=True` stays load-bearing (do not touch — sentence
resegmentation, timing sync and `--repair-asr` are all built on it). Summarize is likewise closed
(at its 4.5× parallel ceiling, CHANGELOG 2026-07-21). One undiagnosed loose end: the `Tu2cCEMwvHI`
116.7 s download outlier (6-13 s for the rest of that queue).

### The condition_on_previous claim — RESOLVED 2026-07-24 (claim SURVIVES, both halves)
Measured with `asr_probe.py --variant nocond`, two axes added (loop: 0.02s stamps · dup sentence
pairs · max ch/s; punct: terminator density · longest terminator-free gap in seconds), corpus
`4szRHy_CT7s` + fixture six, 4 repeats mirrored. **The falsification criterion did NOT fire:** on
`4szRHy_CT7s` the loop rows are DISJOINT with cond=True higher (0.02s stamps 70-119 vs 0, max ch/s
293.8 vs 24.2), so the 2026-07-19 n=1 attribution is now confirmed at 7 videos × 4. Loop half
("cond=True → collapse") holds 7/7 on floor stamps — precisely: it is the ALIGNMENT-COLLAPSE
signature the note measured, NOT necessarily textual repetition (`dup_pairs` is mostly 0), and it
is stochastic (a single cond=True draw can come back clean — 2YCaBqP ch/s spanned 31-300). Punct
half ("cond=False → terminator-free blocks") is clear on the source (longest gap 35.8 s vs 16 s,
term density 5.08 vs 5.7) and directional-but-weak on healthy videos (gaps mostly overlap). The
beam counter-evidence is resolved as BOTH factors mattering, not cond being inoperative.
**Consequences, all UPHELD — no code change:** `_guard`'s cond=True→cond=False retry is confirmed
directly (cond=True drives floor to 8-12% on 4szRHy/RyvXxApfHkk/W4Ua6X, cond=False to 0%); the
per-source hatch is justified; the batched-inference demotion (b) keeps its argument (cond is
operative), on the narrower basis that the punct cost bites on PROBLEM sources, not universally.
Side note, NOT reopened: cond=True is itself the collapse source and 1.60× slower than cond=False —
that does not reopen transcribe speed, because cond=False is rejected on punctuation (now measured),
not on speed. Cells `work-exp/asr-probe-cond/`; rationale DECISIONS 2026-07-24.

### S2 artifact route
**Decide how S2's artifacts reach the disk — the current answer is workable but not settled.**
   Sub-agents are blocked from the Write tool ("Subagents should return findings as text, not
   write report files"). Until 2026-07-21 the prompt told them so and told them how to write the
   files anyway; a safety classifier stopped one of six agents over exactly that, correctly, and
   the framing is gone. What remains is a plain instruction to write two pipeline artifacts with
   PowerShell, plus a rule to hand the content back rather than hunt for another route if that is
   refused. Two open threads:
   (a) **The fully compliant shape is "sub-agent returns, caller writes"**, and run 6's recovery
   ran it end to end: the respawned agent returned the summary as text and the caller wrote both
   files. Its cost is the reason it is not already the default — the caller has to GENERATE the
   content it writes, ~3-4k chars per video, and the measured cost of orchestrator generation is
   ~8.5 s per 1000 chars, so six videos is roughly 200 s added back to a 200-600 s wave. Worth
   measuring properly rather than assuming; the numbers to compare against are in
   `work-exp/wave-run{4,5}-2026-07-21/`.
   (b) **Structured return via a schema is the other candidate and has a known failure mode** —
   long string fields abort the run after data is already on disk
   (`~/.claude/knowledge/claude-code/agent-orchestration.md`), and `paragraph` runs to 1500
   chars. Do not reach for it without re-reading that note.
   Until this is decided, expect an occasional classifier stop on a video; treat it as a respawn,
   not as a reason to reinstate any instruction about what is blocked.

### Timing accounting
**SHIPPED 2026-07-22 — the mechanism is complete; what remains is one measurement on real
media.** `timings.json` carries a `detail.<stage>` entry beside every stage wall clock for the
three heavy stages, and `run.json` no longer bills exclusively off the wall:

- `detail.transcribe` — `work_sec` (load and warmup excluded), `asr_passes`.
- `detail.synthesize` — `work_sec` (worker spawn and model excluded), `n_units`, **`n_rendered`**,
  `n_synth_calls`. `n_rendered` closes the gotcha DECISIONS 2026-07-19 recorded: a resumed run
  re-renders a fraction of the units and nothing in the file said which fraction, so the only way
  to spot a poisoned number was comparing segment wav mtimes against `timings.json`.
- `detail.translate` — `work_sec` (preflight excluded), `n_sentences`, **`n_api`**,
  `first_call_sec`. Ollama loads Gemma INSIDE the first `/api/chat` call, so that load cannot be
  excluded; `first_call_sec` is recorded separately rather than pretended away, and `n_api` is
  translate's resume counter.
- `run.json.timings` gains `overhead_s` (per stage: wall − work), `total_overhead_s`,
  `total_work_s`, **`rtf_work`**, `work_coverage`, `work_complete`. `rtf` is unchanged and still
  bills the whole wall — it is what the run cost. The digest prints the pair only when it exists
  and marks a partial figure `RTF~`.

**The correction that matters, and it reverses this item's own claim.** This item used to say
every recorded speed number was suspect "including `nfe` 48→16's 2.16×". **That is wrong about
that number.** `scripts/exp_nfe_sweep.py` times each cell around `engine.synthesize` alone and
records the worker spawn separately as `startup_s`; it never billed a model load to a video, so
the 2.16× needs no re-check. What IS wall-clock contaminated is anything derived from
`timings.json` stage walls before this change — the ~72 s/video fixed cost, the Silero-vs-F5
whole-pipeline RTF pair (0.14-0.17 vs 0.70-0.92), and every `breakdown_pct`. Re-derive those
from `rtf_work` on the next pass rather than quoting them.

**`separate` now reports detail (2026-07-24):** `detail.separate.work_sec` is the ffmpeg extract
— the one part that scales with audio length — and the demucs subprocess bills as OVERHEAD
(`demucs_sec` recorded beside it): htdemucs load and inference are inseparable in the CLI
subprocess and DECISIONS 2026-07-19 measured the demucs wall's slope against length at R²=0.000
(load-dominated). So `overhead[separate] = wall − extract` lands the ~13.2 s demucs load where it
belongs, and `rtf_work` no longer counts it as work. **Still open, a measurement not code:**
`download`, `verify`, `assemble` and `mux` report no `detail`, so `work_complete` stays False on a
real run and `total_work_s` is an UPPER bound; add their detail the same way when a real batch
makes the timing calls worth it.

### Repair-window hotwords
**Feed the repair window `hotwords` / `initial_prompt`.** Fixes the one confirmed regression from
   the 2026-07-20 ear check (rationale + why this does NOT reopen the repetition loop: DECISIONS
   2026-07-20). Available in faster-whisper 1.2.1, verified. Word-list sources cheapest first: the
   video's own out-of-window sentences, then `pronounce_audit.json`. Measure on the golden fixture —
   the regression is a reproducible test case, which is what makes this cheap.
   **Last on purpose:** `--repair-asr` shipped with 5/12 recall and a proper-noun regression, so
   the open question is whether the feature earns more investment at all, not whether its window
   could be prompted better. Polishing it ranks below every item that serves a route in daily use.

### Parallel F5 workers — GATE PASSED 2026-07-24, build DEFERRED
**The one F5 speed lever absent from the ledger** (nfe, stage-major, fp16, `torch.compile`,
   cross-unit batching, TF32, cudnn, SDPA, VRAM parking, ref clip and demucs are all in the
   2026-07-19 DECISIONS ledger): running several worker PROCESSES concurrently. Rationale: F5
   synthesizes one short unit at a time, small tensors, so the GPU is plausibly launch-bound.
   **The occupancy gate is PASSED.** `nvidia-smi dmon` at nfe=16 over 40 real units
   (`exp_nfe_sweep.py --nfe 16`, dmon 1 s cadence): **median SM 5%, mean 26.6%, and 60% of the
   active window sits below 10% occupancy** — GPU saturated only 15% of the time. F5 is confirmed
   launch-bound (synth wall 66 s of a 148 s render), so the lever is REAL — the "90%+ → no lever"
   exit did not fire. Contrast: cross-video threading found whisper ~28% idle and returned 1.15×;
   F5 leaves twice the idle, so the ceiling is plausibly higher.
   **But the build is deferred, and the gate result is why the decision is informed, not why it is
   automatic.** Three things the occupancy number does NOT promise: (1) the 60% idle includes the
   verify round-trip (whisper-small, which F5 workers cannot fill), the one-off 66 s worker spawn,
   and IPC/file overhead — only the F5-synth slice is fillable; (2) Windows has no MPS, so N
   processes get WDDM time-slicing, and threading already showed N=3 DEGRADES (N=2 is the likely
   optimum); (3) VRAM is tight — two F5 workers (~2×1.3 GB) + whisper-small + desktop 5.7 GB ≈ 9+ GB
   of 12, an OOM risk. Building the 2-worker measurement harness (concurrent processes, unit split,
   mirrored serial-vs-parallel wall) is real code, and F5 is the DUB route (B) — not daily; scout
   does not synthesize. **Reopen when route B synthesis is a measured bottleneck**; the gate says
   it will be worth measuring then, not that it is worth building now. Occupancy raw:
   `work-exp/f5-occupancy/` + `scratchpad/dmon_f5.txt`. Budget ~0.8 GB/worker + ~0.5 GB CUDA
   context each.

### Shorter reference clip
**Bigger than the workers item and already measured, but it moves the voice.**
   DEFERRED in the 2026-07-19 ledger and still unexercised. F5 denoises `ref + gen` and throws the
   ref part away (`utils_infer.py:508`); the reference is 9.164 s against a ~7 s mean unit, so over
   half of every unit's compute is discarded. Worth ~158 s/batch after nfe=16 — larger than the
   parallel-workers item is likely to be, and it needs no occupancy measurement to justify. The
   cost is not compute but
   quality: shortening the reference changes speaker conditioning, i.e. the narrator's voice, so it
   needs an ear session. The ledger bundles it with the rights-clear narrator replacement, which
   owes that same session — do them together or the ear cost is paid twice.

Backlog (second tier) — **throughput / weaker hardware, unlocked by the Silero v5 audition
(DECISIONS 2026-07-19):** Silero v5 synthesizes 12-19× faster than F5 on CPU alone (synth 11-14 s
vs 128-250 s; whole-pipeline RTF 0.14-0.17 vs 0.70-0.92), at quality the user accepts as a
deliberate trade. Two directions follow:
  - **Run on weaker hardware.** With TTS on CPU and the GPU idle during synthesis, the remaining
    GPU load is whisper-large (transcribe) + whisper-small (verify). A low-VRAM or GPU-less host
    becomes plausible — and the Arc B390 path (currently Deferred) gets a realistic TTS story,
    since Silero-on-CPU sidesteps the unproven F5-on-XPU spike entirely.
  - **Raise batch throughput.** Synthesis is no longer the bottleneck on the Silero path; verify
    and separate now dominate. Re-time the batch before optimizing anything — the old assumption
    that synth dominates is only true for F5.
  Blocked on the three ear defects first (all in DECISIONS 2026-07-19): post-processing chain
  (denoise / compression / EQ) for the cheap-microphone timbre; intonation variation (v5_5 is
  reported to support it, unexplored); and the span-vs-slot timing drift — the last one is a
  pipeline fix, not an engine one, and would also tighten any future non-targeting engine.
  **Start from [`docs/russian-tts-guide.md`](../docs/russian-tts-guide.md)** (user-supplied,
  July 2026) — it addresses two of those three directly and contradicts one thing we ship:
  - **Monotone is mostly an INPUT problem, not a settings problem.** The guide puts ~70% of
    prosody quality on what is fed in, and names flat ASR+MT punctuation as the main cause of
    monotony — which is exactly our input shape. Cheapest lever we have not pulled.
  - **Silero DOES take SSML** (`<speak> <p> <s> <prosody> <break>` — no emphasis/emotion tags).
    `<p>`/`<s>` wrapping alone gives pauses and contour reset. Our adapter sends `text=` only.
  - **`sample_rate` 24000 is called out as audibly "plastic"; 48000 is the recommendation.** We
    already run Silero at 48000 (`overdub.toml`) — but F5 is engine-fixed at 24000, worth an ear
    check against this claim.
  - Also relevant to defects we already logged: per-chunk silence trimming + crossfade at joins
    (our "seams"), synthesizing by PARAGRAPH rather than per sentence (our unit grouping already
    moves this way), and a versioned stress dictionary (`terms.tsv`) for domain terms — the class
    `pronounce_audit.json` already surfaces but nothing consumes.
  - Its ordering advice matches ours by accident: punctuation + number normalization first,
    round-trip ASR as QA (shipped), SSML/LLM markup last.

Backlog (second tier): any-language source → Russian (was a roadmap item, shelved 2026-07-19 until
the EN queue runs dry — biggest effort in the list and it breaks the EN→RU hard constraint; whisper
large-v3 is already multilingual: drop the hardcoded `language="en"` and detect; the translator is
prompt-driven, so source language is a prompt variable, not a model choice; quality degradation on
rare languages ACCEPTED — coverage, not parity; touches `cfg.source_lang` semantics, the transcribe
call, both translate routes' prompts, the `en.srt` label, and the Latin-punctuation-shaped
resegmentation (`TERMINATORS`, `_ABBREV`) needs review for languages that punctuate differently);
`--repair id,id --seed N` (point re-synth + remux; grain = the GROUP after
units); per-SERIES terminology glossary (`terms.tsv` per playlist fed into every translate prompt
and checked after — drift measured across the 12-video course, e.g. ИИ-грамотность vs владение ИИ;
per-video isolation makes it invisible to every stage, only a batch-level check sees it);
name-safety pass (out-of-dict Latin names self-agree through verify UNFLAGGED — Bungie→бунджи —
promote `pronounce_audit.json` to a pre-batch operator gate + a per-run known-names check on
src_en for ASR mis-spellings like CLAWD→Claude); enumeration-head detector (in a run of ≥3
adjacent sentences matching `^(and )?X to …` the captured head must be unique — measured 1 fire /
1101 sentences, the true positive, 0 FP, ~15 LOC); Ollama circuit-breaker (abort translate after
~3 consecutive api_error instead of burning 4×timeout per sentence overnight; note failed records
are not retried on resume); normalize polish pass (range+unit "3.5-4.5 GHz" voices the unit as
"гхз"; decade suffixes "90х" → "девяностох"; "10-20%" keeps a literal dash); reuse the scout audio on promotion instead of
re-fetching it inside the merged MKV (~5% waste, accepted 2026-07-20 — but answer the provenance
question first: a promoted run OVERWRITES `source.wav` with a differently-decoded file, ba[ext=m4a]
vs the scout's opus, while `sentences.json` was read off the old one and `--repair-asr` clips
windows from the new one; same master and same timeline, so believed benign, never checked);
`--no-playlist` on both yt-dlp fetches (`stages/download.py` `_fetch_video` + `_fetch_audio`, one
flag each + test: a queue line carrying `&list=` passes the id regex, then yt-dlp FOLLOWS the
playlist into the fixed `-o source.*` path — dozens of videos fetched over one workdir, verified
2026-07-24; today the only guard is a check in both skills, i.e. instruction, not code);
`libopus` for the dub
track (one-flag quality upgrade over aac); singing/music detection → keep original (no robot
singing); loudnorm/EQ on the dub; `--subs-only` fast path; cross-video stage pipelining (translate
GPU ∥ synth/verify) if nights get tight;
fix the out/ export name collision (identical `<title> [<id>].mkv` across models overwrites — namespace
exports per run/model or per work_root); RU analogue for the "four Ds" mnemonic
(Д/Ф/К/Д does not spell "4D" — prompt unpacking or a RU mnemonic, translation-quality class; was
item-0i); whisper anti-repetition decoder params — REJECTED 2026-07-19 on a
60-run sweep (DECISIONS/CHANGELOG), retry ONLY with a content comparison against a reference
transcript (the word-count axis cannot tell "removed a duplicate" from "ate real speech"; probe
script: `scratchpad/floor_variance.py`, extend it rather than starting over). — tail (lowest
priority, keep for later): translation
completeness check (EN↔RU content-word ratio / back-translation on outliers) — evidence exists:
Gemma dropped 3 of 4 adverbs in `DmgujoZ1mmk` id1, unflagged (INBOX 2026-07-18); babble duration
heuristic (expected-vs-actual unit duration → flag garbled synth the ASR round-trip misses) — output
is good now, ADD IT before any narrator-voice or TTS-engine change.

Deferred — NOT near-term (revisit when a need surfaces):
**improving the GRADE's quality.** Closed as a roadmap item 2026-07-20 evening: across several
real queues the grades read as reasonable against the material, which is the bar this pass was
meant to clear. What is deferred is making them BETTER, and the honest position is that nobody
has defined what better means here — there is no reference set, no disagreement log, and no
measurement, so any prompt change would be evaluated by vibe. Before touching the prompt, decide
what a wrong grade even looks like. The cheap instrument already exists if a queue ever comes
back looking wrong: the profile's four "калибровочные примеры" are videos its owner will
certainly watch — scout them and they should come back `high`. That test separates "the queue was
weak" from "the grader is drifting", and it is the thing the 0/1/9 run lacked. Run it as a
diagnostic when suspicion arises, not as routine work.
Also deferred: promoting `n_src` from advisory into
`flags_actionable` — **blocked on measuring the source-anomaly detector's fire rate and precision on
a real Sonnet batch first.** It has zero measured precision today, and `entity_loss` firing on 11 of
12 videos is the standing precedent for what an unmeasured detector does to a triage list;
in-pipeline Anthropic API translate flag
(approved in principle, DECISIONS 2026-07-18; build ONLY if the manual sub-agent seam becomes the
bottleneck — it is not one today, and the seam is where the translate, summary and scout sub-agents
all hang, so automating it away has a cost beyond the code); gender-matched
narrator (median-F0 → M/F reference; blocked on a female PD reference — search the ESpeech
community first: HF Space Den4ikAI/ESpeech-TTS discussions + the author's channels; fallback
re-scan LibriVox female readers — xenium5 rejected on mic, chekhov01 on timbre);
multi-speaker violation detector (ECAPA vs dominant-voice centroid → report flag; full diarization
stays out of scope); UTMOS/MOS verification (high cost, low effect until batch stats prove the
duration heuristic insufficient); unit sim threshold re-tune (base 0.9 — revisit only if production
flags misbehave); Arc B390 path (whisper.cpp/llama.cpp SYCL, Silero-on-CPU or an unproven
F5/Gemma-on-XPU spike); streamed mixing in mux (trigger: multi-hour sources — the numpy mix holds
a ~2-3 GB transient even after chunked RMS/peak); rights-clear narrator reference (HARD gate:
before ANY publication of dubs — today's demo-clip narrator is personal-use only, and re-check the
ESpeech Apache provenance caveat: weights possibly derived from a CC-BY-NC base).

## Open questions
- **"Keep length" ↔ slow speech.** The SYSTEM prompt asks the LLM to keep RU CLOSE IN LENGTH to the
  EN so it fits the same slot; every sentence is then fitted to its slot (atempo compress if long,
  F5 slot-fill stretch if short). Measured Gemma vs Qwen (508 segs): Gemma ~2% shorter (raw
  audio/slot 0.981 vs 0.997), stretched on 46% of segments vs 39%, mean tts_speed 0.977 vs 0.989,
  leftover silence 1.2% vs 0.8% — its tightness pushes marginally toward the slow-speech end. Lever:
  RELAX the keep-length pressure for fuller RU (less stretch, more compression) — a trade, not free.
  `f5_speed_floor` caps max stretch at the cost of inter-phrase gaps.
- Silero stress on names/homographs — a `+`-stress dictionary pass? (fallback engine only, low stakes)
- ~~Similarity metric/threshold~~ RESOLVED: char-level SequenceMatcher(autojunk=False); unit-level 0.9.
- ~~RTF end-to-end~~ RESOLVED (2026-07-16): translate is the bottleneck. Gemma adds ~16% there.

## Closed phases (details in CHANGELOG)
Phase 0 skeleton ✅ · Phase 1 MVP turn-key URL→MKV ✅ · Phase 3 TTS → F5/ESpeech ✅ · Dead-air ✅ ·
Batch queue + stop switch ✅ · Proper nouns ✅ · Segmentation cluster + whisper-context ROOT fix ✅ ·
**Item 0 whisper-context ear-validated ✅ (2026-07-18)** · **Gemma-3-12B migration ✅ (2026-07-18,
A/B-driven; Qwen removed)** · **Sonnet A/B + verdict: semi-auto = primary route ✅ (2026-07-18)** ·
**Observability: run.json + timings.json + run_report.py digest + morning-triage HTML ✅ (2026-07-19)** ·
**Item 0 — AI-Fluency batch: 8 ASR defects repaired, 2 detectors shipped, 12 MKVs re-shipped ✅
(2026-07-19; sub-item index 0a-0j in CHANGELOG)** · **`no_repeat_ngram_size` sweep → REJECTED ✅
(2026-07-19)** · **F5 `nfe` 48→16 measured + ear-checked + adopted, 2.16× on synthesis ✅
(2026-07-19; fp16/compile/batching found already-on, unavailable and a mirage respectively)** ·
**Stage-major batch execution ✅ (2026-07-19; byte-identity verified 39/39 wavs, one worker spawn
amortised per extra video — roadmap item 1 "speed up F5" CLOSED, lever ledger in DECISIONS)** ·
**`--repair-asr` shipped ⚠️ (2026-07-20; code done and fixture-measured, but recall is 5/12 and it
REGRESSED a proper noun on real audio — DECISIONS 2026-07-20. Closed as a deliverable, NOT as a
solved problem)** · **Video summary `summary.md` ✅ (2026-07-20)** · **Source-anomaly reporting at
the translate seam ✅ (2026-07-20)** · **Scout mode `--scout` ✅ (2026-07-20; audio-only fetch, two
download gates, scout cards in both report surfaces — 44 new tests; the "never run on real media"
caveat is CLOSED 2026-07-20 evening: multiple real queues fetched, graded and published)** ·
**Scout report + per-video timing instrumentation ✅ (2026-07-20 evening; two kinds of timing kept
apart, filesystem-stamped summarize marker, 49 tests)** · **One queue page ✅ (2026-07-21; roadmap
item 2 closed by MERGING the renderers: `triage_html.py` retired into `scout_report.py`, shared
data layer in `runreport.py`, cp/adv semantics unified across all surfaces, promoted-but-untranslated
videos now visible as «в работе» cards; 405→431 tests)** · **Timing accounting completed +
roadmap de-numbered ✅ (2026-07-22; `detail` entries for synthesize/translate, `rtf_work` and
per-stage `overhead_s` in run.json, one stale claim in the item itself corrected; 34 stale
"PLAN item N" references in code and tests renamed to topics; 434→445 tests)** · **Queue-page
previews and «о чём» for dubbed-without-scout rows ✅ (2026-07-22; the full download now takes a
thumbnail, the preview normalizer moved into `overdub/workdir.py` so it no longer belongs to the
summarizer step, and the scan cell falls back to summary.md's first sentence)** · **Transcribe-speed
axis closed ✅ (2026-07-24; four levers measured, none adopted — int8 rejected 24% slower, threading
measured N=2 ~1.15×/N=3 net loss and closed, distil rejected by decision, beam already rejected;
fp16 large-v3 on one GPU at its practical ceiling. `asr_probe.py --threads N` driver added +
min→mean drift fix; DECISIONS 2026-07-24)** · **`condition_on_previous` claim tested and SURVIVES ✅
(2026-07-24; two probe axes added — loop + punctuation — corpus 4szRHy_CT7s + fixture six, 4 repeats;
falsification criterion did not fire, cond=True→collapse confirmed 7/7, cond=False→terminator-free
blocks clear on the source; `_guard` / hatch / batched demotion all upheld, no code change; the
2026-07-19 n=1 attribution now n=7×4; DECISIONS 2026-07-24)**.
The `--repair-asr` entry above is the only one still carrying an unsolved problem; the pre-batch
checks at the top of this file apply to the next DUBBING batch, not to a scout pass.

Stack pins, host findings and setup: STACK.md (findings ledger; API examples now live in the code it
points to) + SETUP.md. Translation: Gemma-3-12B (Ollama),
`gemma3:12b`, local in-pipeline default by A/B 2026-07-18 (Qwen3-14B removed); PRIMARY route =
Sonnet semi-automatic (DECISIONS 2026-07-18, runbook README "Running"). TTS: ESpeech-TTS-1_RL-V2 (F5-TTS,
.venv-f5tts) — production by ear 2026-07-16; narrator = ESpeech demo reference (rights caveat in
README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
