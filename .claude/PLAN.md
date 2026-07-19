# PLAN

## → Roadmap (reprioritized 2026-07-18; item 0 ear-check + Gemma migration → CHANGELOG)
Sample workdirs: `work/` (Silero baselines, read-only); `work-exp/context-earcheck/x7DfiXqSEdM/`
(item-0 ear-check, Qwen translate — PASSED); `work-exp/stats-batch/` (Qwen, 8/23 — batch STOPPED to
switch models); `work-exp/gemma-ab/` (Gemma, the same 8 — the A/B set). A/B report artifact
published (Qwen vs Gemma, 508 sentences). Report triage: any *_flag or speed_factor>1.8.

0. **Close out the AI-Fluency batch: two REAL defects still shipped, and the triage cannot see
   them.** Found 2026-07-19 by re-auditing at the end of the session, after the batch had been
   declared done twice. Both are in `out/` right now.

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

   **0d. Re-audit the original morning report line by line.** Two items were lost between finding
   and fixing, so the reconstruction-from-memory used all session is not trustworthy. Walk the
   first `run_report.py --queue queue.txt` output (the 11-of-12 version, reproduced from
   `work/<id>/report.json` if needed) against current state and confirm every listed offender is
   either fixed, reclassified with a written reason, or still open here.

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
