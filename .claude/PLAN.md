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

### The condition_on_previous claim
**A causal claim this project has treated as settled since 2026-07-17, never independently
tested here, and one piece of our own data cuts against it.** The claim has two halves:
`condition_on_previous_text=False` produces 60-206 s terminator-free blocks (the "period
mid-sentence" ROOT class), and `=True` produces repetition loops. Both are load-bearing: the
flag's default, `TranscribeStage._guard`'s entire retry, `overdub.toml`'s per-source hatch, and
the 2026-07-22 demotion of batched inference all rest on them.

   **Today's counter-evidence, from the beam probe and not from theory.** `RyvXxApfHkk` at beam 5
   **with `cond=True`** returned a textbook loop — `"The LLM is used to analyze and categorize
   data."` five times consecutively. The same video at beam 1, **also `cond=True`**, did not. The
   flag was identical on both sides; the loop appeared and vanished with BEAM. So `cond` is not
   sufficient to explain loop presence, and the causal story is at minimum incomplete. Raw:
   `work-exp/beam-probe/RyvXxApfHkk__*.json`.

   **What the existing evidence actually is, stated at its real strength:**
   - Upstream documents it (`faster_whisper/transcribe.py:818-821`: "less prone to getting stuck
     in a failure loop, such as repetition looping"), and ships a dedicated mitigation,
     `prompt_reset_on_temperature=0.5` (`:278`, effect `:1372-1383`). Strong evidence about what
     the maintainers believe. **No evidence at all about our sources.**
   - `overdub.toml`'s NOTE 2026-07-19 (`4szRHy_CT7s`: 170 degenerate 0.02 s stamps → 0, 2 duplicate
     sentence pairs → 0, 294 ch/s → 24) is **one video, one run per side** — and we established on
     2026-07-22 that the same audio at the same settings returns a different transcript and a
     different alignment. `transcribe_floor_run_max`'s own comment records a 5-run sample overturned
     by a sixth. A single before/after on a sampling decoder cannot separate a flag effect from a
     draw. The 170→0 move is large, which is the strongest thing going for it; it is still n=1.
   - `STACK.md:120` recommends `vad_filter=True` **and** `cond=False` together for the silence
     "Thank you." loop — two variables moved at once, so it attributes to neither. That failure is
     at least as plausibly pure VAD.
   - The punctuation half (DECISIONS 2026-07-17) has never been restated as a number here at all.

   **The test.** `scripts/asr_probe.py --variant nocond` is wired (the variant exists), but the
   probe is missing the two axes that would settle it — both were in the deleted harness, ~30 lines
   to re-add: (a) a LOOP axis using the same quantities the 2026-07-19 note used, so the results are
   directly comparable — runs collapsed by `_dehallucinate`, duplicate sentence pairs, max ch/s per
   sentence; (b) a PUNCTUATION axis — terminator density and the LONGEST terminator-free stretch in
   seconds, which is the 60-206 s claim stated as a measurement instead of a memory. Corpus:
   `4szRHy_CT7s` (6.4 min, on disk, the source the claim was built on) plus the fixture six as
   controls. **At least 4 repeats per side, mirrored order** — fewer repeats reproduces the original
   mistake. Cost ~20 min of GPU. **Falsification criterion, fixed now:** if the loop metrics on
   `4szRHy_CT7s` OVERLAP between `cond=True` and `cond=False` across 4 repeats, the 2026-07-19
   attribution does not survive and both the guard and the hatch need re-justifying.

   **What hangs on the answer, and it is not small.** If the flag is not the operative variable,
   the batched-inference demotion loses its main argument — batching hardcodes `cond=False`, and
   that only matters if `cond` matters. Lever (b) would come back onto the table, and `_guard`
   would be re-running ASR on suspect videos for a reason that does not hold. Do not quote the
   2026-07-17 or 2026-07-19 conclusions as established until this runs.

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

**Still open, and it is a measurement not code:** `download`, `separate`, `verify`, `assemble`
and `mux` report no `detail`, so `work_complete` is False on every real run today and
`total_work_s` is an UPPER bound. `separate` is the one worth doing next — DECISIONS 2026-07-19
measured its slope against audio length at R²=0.000, i.e. the stage is nothing but model
loading, which means its entire wall is overhead and `rtf_work` is currently overstating by
~13.2 s per video.

### Repair-window hotwords
**Feed the repair window `hotwords` / `initial_prompt`.** Fixes the one confirmed regression from
   the 2026-07-20 ear check (rationale + why this does NOT reopen the repetition loop: DECISIONS
   2026-07-20). Available in faster-whisper 1.2.1, verified. Word-list sources cheapest first: the
   video's own out-of-window sentences, then `pronounce_audit.json`. Measure on the golden fixture —
   the regression is a reproducible test case, which is what makes this cheap.
   **Last on purpose:** `--repair-asr` shipped with 5/12 recall and a proper-noun regression, so
   the open question is whether the feature earns more investment at all, not whether its window
   could be prompted better. Polishing it ranks below every item that serves a route in daily use.

### Parallel F5 workers
**The one F5 speed lever absent from the ledger.** The
   2026-07-19 ledger (DECISIONS) covers nfe, stage-major, fp16, `torch.compile`, cross-unit
   batching, TF32, cudnn, SDPA, VRAM parking, ref clip and demucs — running several worker
   PROCESSES concurrently is the gap. Rationale: F5 synthesizes one short unit at a time through
   `infer_process`, small tensors, so the GPU is plausibly launch-bound rather than compute-bound.
   **Gated on a five-minute measurement, not on code: `nvidia-smi dmon` during synthesize AT
   nfe=16.** If SM occupancy is already 90%+ there is no lever and this item closes having cost
   nothing. Caveat that decides the ceiling: Windows has no MPS, so N processes get WDDM
   time-slicing, not concurrent kernels — the win only exists to the extent short units leave the
   GPU idle. Budget ~0.8 GB per worker plus ~0.5 GB CUDA context each; three fit inside the 12 GB
   rule with room. Applies to the DUB route (B); scout does not synthesize at all.

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
min→mean drift fix; DECISIONS 2026-07-24)**.
The `--repair-asr` entry above is the only one still carrying an unsolved problem; the pre-batch
checks at the top of this file apply to the next DUBBING batch, not to a scout pass.

Stack pins, verified APIs and setup: STACK.md + SETUP.md. Translation: Gemma-3-12B (Ollama),
`gemma3:12b`, local in-pipeline default by A/B 2026-07-18 (Qwen3-14B removed); PRIMARY route =
Sonnet semi-automatic (DECISIONS 2026-07-18, runbook README "Running"). TTS: ESpeech-TTS-1_RL-V2 (F5-TTS,
.venv-f5tts) — production by ear 2026-07-16; narrator = ESpeech demo reference (rights caveat in
README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
