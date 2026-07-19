# PLAN

## → Roadmap (reprioritized 2026-07-18; item 0 ear-check + Gemma migration → CHANGELOG)
Sample workdirs: `work/` (Silero baselines, read-only); `work-exp/context-earcheck/x7DfiXqSEdM/`
(item-0 ear-check, Qwen translate — PASSED); `work-exp/stats-batch/` (Qwen, 8/23 — batch STOPPED to
switch models); `work-exp/gemma-ab/` (Gemma, the same 8 — the A/B set). A/B report artifact
published (Qwen vs Gemma, 508 sentences). Report triage: any *_flag or speed_factor>1.8.

0. ~~**Close out the AI-Fluency batch.**~~ **CLOSED 2026-07-19 — details in CHANGELOG.** Final
   scope was 8 defects across 6 of 12 videos (PLAN had recorded 2). All repaired via
   isolated-window re-ASR, 6 videos re-translated, all 12 MKVs rebuilt; both ASR detectors now
   fire zero times across the batch and the 2 remaining triage flags are documented false
   positives. Two detectors shipped (`rate_implausible`, containment) plus the `_RU_NEG_RE` fix.
   **What did NOT get closed, deliberately:** cross-video terminology drift (measured, INBOX,
   judged not worth re-translating the other 6 videos for) and the `entity_loss` acronym+s bug
   (0h below — advisory-only, costs noise not correctness).
   Kept below for the reasoning, which the roadmap items above still lean on.

   **REPAIRED 2026-07-19 via isolated-window re-ASR (method + caveats in DECISIONS).** 7 defect
   regions across 6 videos merged back to the single sentence each window actually contains;
   originals at `work/<id>/_pre-repair-sentences.json`. Both ASR detectors now fire ZERO times
   across the 12 queue videos (`rate_implausible` max 246 → 39.36 ch/s; `dup_adjacent` 3 → 0).
   Repaired: `ytEN_iAk09c` 7/8 · `W4Ua6XFfX9w` four-Ds recap + 29/30/31 · `RyvXxApfHkk` 10/11 ·
   `2YCaBqP8muw` 16/17/18 + 43/44 · `DmgujoZ1mmk` 31/32 · `W5cga7xipRI` 23/24.
   REMAINING for these 6: translate (Sonnet seam) → synthesize → verify → assemble → separate →
   mux, then a fresh digest. Until that finishes, `out/` still holds the OLD dubs.

   **RE-TRANSCRIBE RESULT (2026-07-19) — the premise of 0a was WRONG.** All four videos were
   re-transcribed with `--force --only transcribe`. PLAN assumed whisper non-determinism would
   shake the defects loose ("the guard may now handle it; re-run and check"). It fixed **1 of 4**:
   `W4Ua6XFfX9w`'s four-Ds recap came back correct as a single sentence. The other three reproduce
   the SAME defect on the same audio — this is not decoder noise, it is a stable response to those
   passages. `RyvXxApfHkk` came back partly worse (a new 0.28 s collapsed segment), and the new
   `ytEN_iAk09c` gained a garbled line with CJK+Cyrillic characters. **Re-running transcribe is
   not a repair strategy for this class.**
   Workdirs were RESTORED from `_bak-20260719/` so they stay consistent with `out/`; the new
   transcripts are preserved beside them in `_retranscribe-20260719/` (not wired into anything).
   Deciding what to actually repair is the open question — surgical `sentences.json` edits are the
   only deterministic option identified.

   **STATUS after the 0c/0d pass (2026-07-19, multi-agent):**
   - ✅ `dup_adjacent` detector shipped in `completeness.py` + wired through verify/runreport,
     ACTIONABLE. Fires exactly once in 1028 adjacent pairs, and that fire is the ytEN_iAk09c
     ground truth. Catches the verbatim-ECHO class ONLY — see DECISIONS for the documented misses.
   - ✅ `_RU_NEG_RE` fixed (bound бес-/без- prefix), then CORRECTED: the first cut suppressed
     positive-polarity stems (безопасн-) and went blind to real inversions. See DECISIONS.
   - ✅ `rate_implausible` detector shipped (chars/sec > 40 on the EN source span). 7 fires /
     1100 sentences, 7 true positives, 0 false — the best-grounded detector in the module.
   - ✅ 0g fixed: `--force --only verify assemble` across all 12 cleared the 6 phantom
     `translate:refusal`; the digest now matches `translation.json`.
   - ❌ 0a, 0b, 0e, 0f repairs: NOT done. Re-transcribe rejected as the method (see above).
   - 🆕 two more videos carry real defects (0e, 0f below), and TWO MORE were found by the rate
     detector in videos previously reported `[clean]` (0j below).

   **0j. `DmgujoZ1mmk#32` and `W5cga7xipRI#23` — collapsed spans in videos reported clean.**
   Found only after the rate detector existed: 93 chars in 0.88 s and 66 chars in 0.94 s. Both
   videos reported `[clean]` through every earlier audit, including 0d. Impact is a timing
   artifact rather than wrong text — the dub sentence is crammed into a fraction of its slot —
   so severity is lower than 0a/0e, but they were INVISIBLE, which is the point. Batch triage is
   now 4 of 12, up from 2, and all four are real.
   **Detection scorecard on the shipped transcripts — 4 of 6 known defects are now visible:**
   0a ✅ (dup + rate) · 0f ✅ (dup + rate) · 0j ✅ (rate, ×2) · 0b ❌ · 0e ❌.

   **0e. `RyvXxApfHkk` ids 10-11 — garbled + repeated ASR, reported `[clean]`.** id10 "Large
   language models, or LLMs, like the LLM, are used to analyze and categorize data." (self-
   referential nonsense); id11 repeats "used to analyze and categorize data" and mangles
   "Anthropic's Claude models" into "anthropics, quads models". **The masking mechanism is the
   finding worth keeping:** Sonnet partially REPAIRED id11 into plausible Russian ("...как модели
   Claude от Anthropic..."), hiding the source damage from every downstream detector. A translator
   good enough to fix ASR damage is a translator good enough to hide it. This is POST-re-transcribe
   (`sentences.json` 12:56) — the older INBOX note about CJK garbage at id12 is a different,
   now-gone defect.

   **0f. `2YCaBqP8muw` ids 16-17 — whisper repetition loop, video in TRIAGE for an unrelated
   reason.** id17 re-speaks 87 chars of id16 verbatim AND repeats "break complex tasks into steps"
   twice inside itself; the six-item tip list is dubbed twice, 207 RU chars into a 4.5 s slot.
   `similarity 0.9982`, `completeness_flags=[]` — invisible. Ratio 0.6569, BELOW the 0.80
   threshold, so `dup_adjacent` does not catch it either.

   **0a. `ytEN_iAk09c` — duplicated sentence pair (ids 7, 8).** Same whisper repetition class that
   was fixed in `4szRHy_CT7s`; this video was simply never re-transcribed. The dub says the same
   thing twice. Detected early in the session and then dropped on the floor — no re-run was ever
   made. FIX: `--force --only transcribe` (the guard may now handle it; whisper is non-deterministic
   so re-run and check), then re-translate that video with a Sonnet sub-agent (`sentences.json` ids
   shift → the draft goes stale), `scripts/build_translation.py work\ytEN_iAk09c`, then
   `--force --only synthesize verify assemble separate mux`. Back up the workdir artifacts first —
   the same `_bak` discipline used for the other two.

   **0b. `W4Ua6XFfX9w` — garbled four-Ds recap, ids 45-48.** The source enumerates the four
   competencies but whisper duplicated a word: id46 "Description to control AI", id47
   "**Delegation** to communicate clearly with AI" — id47 should be Description. The translator
   sub-agent reported this at translate time; it was acknowledged and never acted on. Not a
   near-duplicate (the dup scan misses it — the two lines differ), so it needs the same re-transcribe
   treatment and then a manual read of ids 45-48 to confirm the recap reads correctly.

   **0c. The blind spot this exposes, which matters more than the two videos.** Neither defect is
   surfaced by the triage that was just rebuilt: `ytEN_iAk09c` reports `triage: no`, and
   `W4Ua6XFfX9w` reports `yes` only because of a `neg_loss` the user already diagnosed as FALSE
   ("полезное от бесполезного" — the negation lives in the bound prefix `бес-`, which
   `_RU_NEG_RE` cannot match because it scans for `без` with a `з`). So 2 of 12 videos carry real
   defects and the report points at neither.
   **There is no duplicate-sentence detector anywhere in the pipeline.** The whole session used an
   ad-hoc script; it found real defects in 2 of 12 videos, a better hit rate than `entity_loss`,
   which is a shipped detector. It belongs in `completeness.py` as an ACTIONABLE flag. The method,
   recorded here because the scratchpad it lived in is temporary — for each adjacent pair in
   `sentences.json`, when the first is longer than 25 chars and
   `difflib.SequenceMatcher(None, a, b).ratio() > 0.80`, flag both ids. Cheap, pure, no model.
   Note it must run on `sentences.json` (source EN), not on the translation: it is an ASR defect.

   **0d. Re-audit the original morning report line by line.** ✅ DONE 2026-07-19, from artifacts.
   Result: triage flags 2 of 12 videos and is wrong about both — it misses all four real defects
   and the one video it correctly puts in TRIAGE got there via a FALSE `neg_loss`. Beyond 0e/0f
   above, it surfaced three structural findings, kept here because nothing else records them:

   **0g. `report.json` is structurally stale against `translation.json` across all 12 videos, and
   a normal re-run can never fix it.** Flags in `translation.json` changed at 14:44 (the refusal-
   regex rebuild) while every `report.json` is 10:52-13:04. `verify.done()`/`assemble.done()` gate
   on `synth_key`/`units_key`, which depend on TEXT, not flags — text did not change (verified:
   0 stale units across all 12, manifests complete). So the digest still prints **6 phantom
   `translate:refusal`** that DECISIONS 2026-07-19 declared "6 → 0", and will print them forever.
   `run_report.py --rebuild` does not help (it rebuilds `run.json`; offenders come from
   `report.json`). Only `--force --only verify assemble` clears it. This is the `synth_key`
   silent-staleness class reappearing on the FLAGS field instead of the audio — the invariant has
   no equivalent on flags.

   **0h. `entity_loss` detector bug: acronym+s bypasses the ALL-CAPS exclusion.**
   `completeness.py` filters with `base[0].isupper() and not base.isupper()`; for "LLMs" the
   lowercase plural `s` makes `base.isupper()` False, so the acronym passes as a Titlecase name —
   exactly what the docstring promises to exclude. 13 of 34 `entity_loss` fires in the batch
   (38%): LLMs ×9, GPUs+TPUs, Ds ×4. One-line fix (strip a trailing `s`, or require a lowercase
   letter in `base[1:-1]`). Advisory-only, so it costs noise, not correctness.

   **0i. The "four Ds" mnemonic is destroyed in translation** (`W4Ua6XFfX9w`, `ytEN_iAk09c`,
   `JpGtOfSgR-c`). RU keeps "четыре D"/"4D" and pronounce voices it as "четыре ди", while the RU
   competency names are делегирование / формулировка / критическая оценка / добросовестность —
   Д, Ф, К, Д. The listener hears a mnemonic that does not work. Translation-quality class, not
   ASR: needs a RU-analogue mnemonic or an explicit unpacking in the prompt.

1. **Video summary from the full transcript — "is this worth watching at all?"** A separate Sonnet
   sub-agent reads the COMPLETE original transcript (`sentences.json` — it already exists after
   transcribe, no new stage input) and writes a **Russian** summary of **~200 words**. Purpose is
   triage-before-viewing, not a synopsis: it must answer (a) is the video worth watching, and
   (b) what is the most interesting thing in it / what to look for. Runs at the same seam as the
   translate sub-agents, so it costs one extra agent per video and no GPU. Open: where the artifact
   lands (`work/<id>/summary.md`?), whether it belongs in the batch digest and the triage HTML,
   and whether it should run before translate so a "not worth it" verdict can skip the expensive
   stages entirely — that last one is the real payoff at batch scale.

2. **Any-language source → Russian.** Today the pipeline is EN→RU by contract (CLAUDE.md hard
   constraint: no language detection, no multi-language handling). Extend it to accept effectively
   any source language, WITHOUT swapping models: whisper large-v3 is already multilingual (drop the
   hardcoded `language="en"`, detect instead), and the translator is prompt-driven so the source
   language is a prompt variable, not a model choice. Quality degradation on rare languages is
   ACCEPTED by design — the point is coverage, not parity. Touches: `cfg.source_lang` semantics,
   the transcribe call, both translate routes' prompts, and the `en.srt` label. Note the knock-on:
   sentence resegmentation (`TERMINATORS`, `_ABBREV`) is Latin-punctuation-shaped and will need
   review for languages that punctuate differently.

3. **Sonnet semi-automatic translate — live-run the primary route.** Verdict recorded
   2026-07-18 (DECISIONS): quality noticeably better, much faster, replaces the heaviest stage;
   both routes stay — Gemma = local in-pipeline default, Sonnet (subscription, cloud) = PRIMARY,
   in semi-automatic mode (sub-agents at the translate seam). Runbook: README "Running" route B.
   Open: harden the recipe on the first real batch beyond the spike (e.g. the remaining 15/23
   stats-batch videos). The in-pipeline Anthropic API flag stays approved but deferred — build
   only if the manual seam becomes the bottleneck.

4. ~~**Whisper anti-repetition decoder params.**~~ **REJECTED 2026-07-19** on a 60-run sweep — no
   consistent direction (helped the severe source, made the borderline one worse on every axis,
   damaged a healthy control at n=4). See DECISIONS. Do NOT retry as-is: the measurement's third
   axis (word count vs baseline) cannot distinguish "removed a duplicate" from "ate real speech",
   so any rerun needs a CONTENT comparison against a reference transcript first. What remains open
   from this line of work is not the knob but the guard's threshold — see below.
   Original writeup kept for the design of a future attempt:
   The transcribe
   guard (shipped 2026-07-19) catches a collapsed alignment AFTER the fact; these params attack
   what CAUSES it. `no_repeat_ngram_size` and `repetition_penalty` sit at library defaults (0 and
   1 — off), so the repetition loop that feeds whisper's temperature fallback is unopposed, and
   that fallback is why the same audio yields a different transcript per run (measured: a "clean"
   video spanned 0.00–7.46% over 5 runs). This is the only lever that could NARROW the spread
   instead of catching its tail — which would also let the guard's PROVISIONAL 0.085 threshold
   become a real constant.
   Do NOT adopt blind: too small an `n` silently eats legitimate repetition ("very, very",
   refrains, list items with a shared opener) — the forbidden silent-loss class.
   Measurement design (agreed, deferred): `4szRHy_CT7s` (severe) + a healthy control, `n` in
   0/4/5/6, 3 repeat runs per combination (~24 runs, ~25-30 min), scored on THREE axes —
   floor_run_ratio, duplicate adjacent sentences, and TOTAL WORD COUNT vs the n=0 baseline.
   The third axis is the load-bearing one: fewer duplicates is the win, fewer words is the
   regression, and a single metric cannot tell them apart. Probe script kept at
   `scratchpad/floor_variance.py` (read-only, transcribes from work/<id>/source.wav, writes
   nothing back) — extend it with the `n` sweep rather than starting over.

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

5. **Speed up F5.** The Silero audition put a number on what the primary engine costs: 128-250 s
   of synthesis per ~5-minute video against Silero's 11-14 s. F5 quality stays preferred, so the
   question is how much of that gap is recoverable. Unexplored levers: `f5_nfe` (48 → 32 is noted
   in overdub.toml as ~30% faster with an un-ear-checked quality delta — ear-check it), batching
   across units instead of one worker call per unit, keeping the worker process warm across
   videos in a batch, and half-precision / compile options in the F5 worker. Measure per lever,
   ear-check anything that touches quality — the id101 precedent says metrics alone cannot sign
   this off.

Backlog (second tier): `--repair id,id --seed N` (point re-synth + remux; grain = the GROUP after
units); per-run terminology glossary; singing/music detection → keep original (no robot singing);
loudnorm/EQ on the dub; `--subs-only` fast path; cross-video stage pipelining (translate GPU ∥
synth/verify) if nights get tight;
fix the out/ export name collision (identical `<title> [<id>].mkv` across models overwrites — namespace
exports per run/model or per work_root). — tail (lowest priority, keep for later): translation
completeness check (EN↔RU content-word ratio / back-translation on outliers) — no current evidence
the model drops words on short sentences, but cheap insurance if it ever does; babble duration
heuristic (expected-vs-actual unit duration → flag garbled synth the ASR round-trip misses) — output
is good now, ADD IT before any narrator-voice or TTS-engine change.

Deferred — NOT near-term (revisit when a need surfaces): gender-matched
narrator (median-F0 → M/F reference; blocked on a female PD reference);
multi-speaker violation detector (ECAPA vs dominant-voice centroid → report flag; full diarization
stays out of scope); UTMOS/MOS verification (high cost, low effect until batch stats prove the
duration heuristic insufficient); unit sim threshold re-tune (base 0.9 — revisit only if production
flags misbehave); Arc B390 path (whisper.cpp/llama.cpp SYCL, Silero-on-CPU or an unproven
F5/Gemma-on-XPU spike).

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
**Observability: run.json + timings.json + run_report.py digest + morning-triage HTML ✅ (2026-07-19)**.

Stack pins, verified APIs and setup: STACK.md + SETUP.md. Translation: Gemma-3-12B (Ollama),
`gemma3:12b`, local in-pipeline default by A/B 2026-07-18 (Qwen3-14B removed); PRIMARY route =
Sonnet semi-automatic (DECISIONS 2026-07-18, runbook README "Running"). TTS: ESpeech-TTS-1_RL-V2 (F5-TTS,
.venv-f5tts) — production by ear 2026-07-16; narrator = ESpeech demo reference (rights caveat in
README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
