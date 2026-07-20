# PLAN

## → Roadmap (re-cut 2026-07-20 — scout mode shipped; timing accounting leads now)
Sample workdirs: `work/` (13 dirs — Silero baselines + the AI-Fluency batch, read-only).
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
- **scout mode has never touched YouTube — the first real `--scout` pass IS its measurement.** All
  current evidence is synthetic (tests, injected stages). Watch on the first run: bytes and wall per
  video vs a full fetch; whether `-f bestaudio` ever fails on a real source (no `/best` fallback by
  design — that video FAILs out of the pass); that the info.json rename actually lands, or every
  scouted workdir pays a 30 s networked title lookup at report time; and one promotion end to end —
  `transcribe` must fast-skip while `download` re-runs.

**Two scout findings from 2026-07-20 that are not items yet — check them on the next pass:**
- **Calibrate the grade before trusting a queue-wide shape.** The profile carries four videos its
  owner will certainly watch (its "калибровочные примеры" line). Scout them and read the grades:
  under the NEW contract they should come back `high` on substance/currency/delivery. If they do
  not, the prompt is drifting and no amount of queue-reading will show it — this is the only
  cheap test that separates "the queue was weak" from "the grader is wrong", and it is what the
  0/1/9 run lacked.
- **Two yt-dlp binaries are installed and the pipeline picks the older one.** `2026.03.17` on
  PATH (used, because running `.venv-asr\Scripts\python.exe` does NOT activate the venv) and
  `2026.07.04` inside `.venv-asr` (unused). Not implicated in any failure — both fetched the two
  "broken" videos on demand — but the download stage's version is currently unpredictable and is
  not the one that was installed for it.

1. **The summarize wave is the scout bottleneck — 5×, not the tie it was assumed to be.**
   Measured 2026-07-20 on a 10-video queue: download 34 s, transcribe 4.6 min (both sums),
   summarize **25.1 min** (wall clock of the wave). Two consequences, and the second is the
   bigger one:
   (a) **Pipelining transcribe → summarize buys ~15%, not a third.** The ceiling is
   `min(transcribe, summarize)` = 4.6 min of 30. Still worth doing — the dependency is strictly
   per video (`sentences.json` → its sub-agent), so it is a barrier-free pipeline — but it
   breaks the skill's three-step shape: S1 must finish before S2 starts today, and the pipeline
   needs the Python run and the sub-agent wave alive at once. Cheapest form: cut the queue into
   batches of 3-4 and interleave, rather than a true streaming orchestrator.
   (b) **Attack the wave itself first.** 25 min for one wave of sub-agents, each reading a
   transcript and writing five short fields, is the actual cost. Levers, cheapest first: wave
   width (how many concurrent agents), and input size (a 500-sentence transcript is fed whole —
   nothing has tested whether a truncated or chunked input changes the grade).
   **The measurement now exists — collect the baseline before touching either lever.** Each
   sub-agent touches `work/<id>/scout.started` and `summarize_sec` is the mtime delta
   (DECISIONS 2026-07-20 evening). Note the plan above was wrong about the mechanism: having the
   ORCHESTRATOR stamp each spawn does not work, because agents queue behind the concurrency cap
   and spawn time then measures the queue. Nothing on disk carries the field yet — every
   `summarize_sec` is `null` until a wave runs under the new prompt, so the first pass IS the
   baseline and there is nothing to compare against before it.

2. **Batch/video timing accounting — transcribe DONE, the other stages are not.** `timings.json`
   now carries `detail.transcribe.work_sec` (load and warmup excluded) alongside the stage wall
   clock, and `scout.json` surfaces both. Remaining:
   (a) **`synthesize` and `translate` have no `detail` entry**, so the same distortion still
   applies to them — and synthesize is the expensive one on the dubbing route.
   (b) **`run.json` / RTF still bill per video off the wall clock.** `runreport` computes
   `total_wall` and the percentage breakdown from `stages` alone, so every RTF number remains
   incomparable across batch positions and across `--video-major`.
   (c) **Blocks trusting any recorded speed number, including `nfe` 48→16's "2.16×"**; those
   were measured under the old accounting and must be re-checked before reuse.

3. **Feed the repair window `hotwords` / `initial_prompt`.** Fixes the one confirmed regression from
   the 2026-07-20 ear check (rationale + why this does NOT reopen the repetition loop: DECISIONS
   2026-07-20). Available in faster-whisper 1.2.1, verified. Word-list sources cheapest first: the
   video's own out-of-window sentences, then `pronounce_audit.json`. Measure on the golden fixture —
   the regression is a reproducible test case, which is what makes this cheap.

4. **Reconcile the two report renderers.** `triage_html.py` prints `completeness.n_flagged` where
   `run_report.py` prints `n_actionable` + `n_advisory`, and the batch tables have diverged to 10 vs
   13 columns — same batch, two different numbers, in the two surfaces a morning operator compares.
   One root cause, one fix. Note `_batch_table`'s cell classes are index-based, so column changes
   there mis-colour silently (the `src` column bit exactly this; now `len(cells)-1`). Scout added a
   third divergence to fold in: both surfaces now special-case a run.json-less workdir, separately.

5. **A repair destroys the worklist that motivated it.** `--repair-asr` deletes `translation.json`,
   which is where the source-anomaly report lives — and the anomaly report is exactly the input
   for explicit-id repairs, since the detectors are blind to that class. It also renumbers ids, so
   any remaining ids from that report are stale. Repairing the first window from a report therefore
   destroys the rest of the list. The renumbering is already warned about; the report loss is not.
   Cheapest fix is probably preserving the report alongside `_pre-repair-sentences.json`.

6. **Integrate pytest — there is no way to run the suite with one command.** `pytest` is installed
   in NO venv (`find_spec('pytest')` → False in all three), there is no `conftest.py` and no
   `[tool.pytest.ini_options]`; every `tests/test_*.py` is a self-driving script with a `__main__`
   footer, run one file at a time. Surfaced 2026-07-20 when the scout work had to loop over the
   files by hand to get a suite-wide result. Consequences today: no single green/red signal before
   a commit, no aggregate count, a file that dies on import reports as one failed file rather than
   N failed tests, and any agent told to "run the tests" invents its own loop — or claims a pytest
   result line it never produced. Add pytest to `.venv-asr` + a `[tool.pytest.ini_options]` block
   in `pyproject.toml`. **Migrate the existing footers rather than rewriting the tests:** they are
   already plain asserts in `test_*` functions, so collection mostly works as is — keep the
   `__main__` footers so a single file stays directly runnable, and check what the injected-stage
   fixtures in `test_batch_order.py` / `test_scout.py` need. Non-goal: coverage, CI, parametrizing.

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
a promoted video's summary is invisible on the triage page between the full download and translate
(`source.mkv` present + no `run.json` → `skipped` — printed, but not carded; it was invisible before
scout mode too, so this is a gap scout made worth closing, not one it opened); `libopus` for the dub
track (one-flag quality upgrade over aac); singing/music detection → keep original (no robot
singing); loudnorm/EQ on the dub; `--subs-only` fast path; cross-video stage pipelining (translate
GPU ∥ synth/verify) if nights get tight;
fix the out/ export name collision (identical `<title> [<id>].mkv` across models overwrites — namespace
exports per run/model or per work_root); `entity_loss` acronym+s bug ("LLMs" bypasses the ALL-CAPS
exclusion — one-line fix, advisory noise only; was item-0h); RU analogue for the "four Ds" mnemonic
(Д/Ф/К/Д does not spell "4D" — prompt unpacking or a RU mnemonic, translation-quality class; was
item-0i); quick code fixes: torn-jsonl newline guard on first append, `download.py` shutil.which
preflight for yt-dlp/ffmpeg (raw WinError 2 today), drop the removed config keys from
`work-exp/gemma-ab/gemma.toml`; whisper anti-repetition decoder params — REJECTED 2026-07-19 on a
60-run sweep (DECISIONS/CHANGELOG), retry ONLY with a content comparison against a reference
transcript (the word-count axis cannot tell "removed a duplicate" from "ate real speech"; probe
script: `scratchpad/floor_variance.py`, extend it rather than starting over). — tail (lowest
priority, keep for later): translation
completeness check (EN↔RU content-word ratio / back-translation on outliers) — evidence exists:
Gemma dropped 3 of 4 adverbs in `DmgujoZ1mmk` id1, unflagged (INBOX 2026-07-18); babble duration
heuristic (expected-vs-actual unit duration → flag garbled synth the ASR round-trip misses) — output
is good now, ADD IT before any narrator-voice or TTS-engine change.

Deferred — NOT near-term (revisit when a need surfaces): promoting `n_src` from advisory into
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
download gates, scout cards in both report surfaces — 44 new tests, but NEVER run on real media)**.
All four await the pre-batch checks at the top of this file.

Stack pins, verified APIs and setup: STACK.md + SETUP.md. Translation: Gemma-3-12B (Ollama),
`gemma3:12b`, local in-pipeline default by A/B 2026-07-18 (Qwen3-14B removed); PRIMARY route =
Sonnet semi-automatic (DECISIONS 2026-07-18, runbook README "Running"). TTS: ESpeech-TTS-1_RL-V2 (F5-TTS,
.venv-f5tts) — production by ear 2026-07-16; narrator = ESpeech demo reference (rights caveat in
README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
