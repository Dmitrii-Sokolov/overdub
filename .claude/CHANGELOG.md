# CHANGELOG

## 2026-07-19 — Item 0 closed: 8 ASR defects repaired, 2 new detectors, batch re-shipped
- **The batch carried 8 defects across 6 of 12 videos, not the 2 PLAN recorded**, and triage
  pointed at none of them. All 8 are now repaired and all 12 MKVs rebuilt.
- NEW `completeness.implausible_rate(texts, durations)` → flag `rate_implausible`: chars/sec above
  40 on the EN source span, the signature of a whisper alignment collapse. Threshold sits on a
  PHYSICAL bound (speech tops out at 25-30 ch/s; corpus median 16.75, p99 34.26) rather than on
  corpus separation. **7 fires / 1100 sentences, 7 true positives, 0 false** — best precision in
  the module, and it found real defects in two videos every text-based signal called `[clean]`.
- NEW containment signal inside `duplicate_adjacent` (`lcs / len(shorter) > 0.85`, OR-ed with the
  existing ratio): catches the whisper RESTART class, where a re-spoken line is swallowed by its
  neighbour and the symmetric ratio is dragged down by the new tail. Ratio alone found 1 of the
  corpus's 3 repetition defects; with containment, 3 of 3.
- FIXED `_RU_NEG_RE` twice. First cut widened it to a bare `бе[зс][а-я]*`, which made
  positive-polarity stems (безопасн-, бесплатн-) count as surviving negation and went blind to
  real inversions ("not safe" → "безопасно"); a test had even been added pinning that miss as
  acceptable. Shipped form subtracts `_NEG_POSITIVE_STEMS` — re-measured identical on the corpus
  (2 fires, target FP `W4Ua6XFfX9w#32` still removed, zero new FPs) while closing the hole.
- Repair method: **isolated-window re-ASR, not full-file re-transcription.** Re-running whole
  files fixed 1 defect of 4 and created new ones; re-transcribing just the defect window (no
  prior context for the loop to feed on) returned a clean reading for 7 of 7, identical under
  `condition_on_previous_text` True and False — that agreement was the acceptance criterion.
  Originals at `work/<id>/_pre-repair*-sentences.json`; `words.json` deliberately untouched.
- 6 videos re-translated through the Sonnet seam. Two defects were found by translator agents
  READING the source, not by any detector — a hallucinated word splitting one sentence in two
  (`W4Ua6XFfX9w` 19/20, both halves at a plausible ~26 ch/s and not similar to each other) and
  self-referential garble. Also fixed `chain-of-thought` → «цепочка рассуждений`, which the
  normalizer had been voicing as "чейн-оф-таугхт".
- Also fixed 0g: `report.json` was structurally stale against `translation.json` across all 12
  (verify/assemble gate on text-derived keys, so flag-only changes never invalidated them),
  leaving 6 phantom `translate:refusal` in the digest that DECISIONS had declared cleared.
- **Result: both ASR detectors fire ZERO times across the batch** (`rate_implausible` max 246 →
  39.36 ch/s; `dup_adjacent` 3 → 0). Digest: 2 of 12 need triage, and both are documented false
  positives — a lexical negation with no не/ни/без token, and an accepted `few-shot prompting`
  Latin run. Full suite (11 files) green.
- Sub-item index (the 0a-0j labels INBOX/DECISIONS still reference; the detail lived in PLAN item 0,
  removed on close): 0a `ytEN_iAk09c` 7/8 duplicated pair · 0b `W4Ua6XFfX9w` four-Ds recap garble ·
  0c the no-duplicate-detector blind spot (→ `dup_adjacent`) · 0d morning-report re-audit (triage
  was wrong about both videos it named) · 0e `RyvXxApfHkk` 10/11 garbled ASR masked by Sonnet's
  repair · 0f `2YCaBqP8muw` 16/17 repetition loop · 0g `report.json` flag-staleness (cleared via
  `--force --only verify assemble`) · 0h `entity_loss` acronym+s bug (left open → PLAN backlog) ·
  0i four-Ds mnemonic destroyed in RU (left open → PLAN backlog) · 0j collapsed spans in videos
  reported `[clean]` (found by the rate detector).

## 2026-07-19 — `no_repeat_ngram_size` measured and REJECTED; guard threshold downgraded
- 60-run sweep (3 videos × n in 0/4/5/6 × 5 repeats, read-only probe, no workdir writes): the knob
  is NOT adopted. Severe source improved (floor 11.07% → 8.2%, dups 2 → 0 at n=6), borderline got
  worse on every axis (floor 6.13% → 13.51%, dups 0 → 2, words +11.5% — more words WITH more
  duplicates = the loop changed shape, not stopped), healthy control degraded at n=4
  (0.13% → 4.44%). No code change; PLAN item 3 struck through with the reason.
- The sweep's third axis is recorded as MISDESIGNED: "word count drops ⇒ real speech eaten" cannot
  distinguish that from "a duplicate was correctly removed", which is exactly the case it had to
  judge. A future attempt needs a content comparison against a reference transcript.
- `cfg.transcribe_floor_run_max` comment corrected: the n=0 cells form a second independent sample
  and put the MID video at 15.82% — above the severe video's entire range, and 2× its own maximum
  from the earlier session. The 1.8 pp "separating gap" does not exist; the populations overlap.
  0.085 is kept only because the severe case has never fallen below it. Catastrophe insurance
  holds; borderline detection is knowingly unreliable.

## 2026-07-19 — Triage that means something: `refusal` narrowed, advisory flags demoted
- FIXED `translate._REFUSAL`: `как (?:ии|модель|языковая)` matched ordinary "как ИИ" = "how AI",
  so all 6 refusal flags in the 12-video batch were false. Now requires the first-person clause a
  real refusal carries (`как ИИ, я …`). Validated 0 false positives / 0 misses over 8 benign + 8
  genuine refusals. All 12 translations rebuilt: refusal 6 → 0.
- NEW `_ADVISORY_COMPLETENESS = {entity_loss, length_short}` in runreport: these are counted and
  printed but no longer decide `needs_triage`. Both are documented false-positive-prone by
  completeness.py itself (personal-name Russification; the deliberately coarse length signal).
  `num_loss` / `neg_loss` stay actionable — an inverted negation is the worst silent loss.
- `run.json` gains `flags_actionable` + `flags_advisory` (`flags_total` unchanged);
  `completeness` gains `n_actionable` + `n_advisory`. Digest block shows
  `completeness N (+M advisory)`; batch table splits `cp` / `adv`.
- EFFECT on the AI-Fluency batch, same run data: **11 of 12 videos needing triage → 2**, and both
  survivors are real (a `neg_loss`; an `english_echo` that would feed Latin script to the TTS).
- Full suite (11 files) green.

## 2026-07-19 — Silero release is a config knob; v5_5_ru becomes the fallback default
- NEW `cfg.silero_model` (default `"v5_5_ru"`, was a hardcoded `MODEL_ID = "v4_ru"` in the
  adapter): the torch.hub release id. v4 was the bake-off entrant BY MISTAKE — already superseded
  at the time — so every pre-2026-07-19 Silero verdict describes an outdated model. v4 stays
  selectable to reproduce old runs.
- `synth_key` now includes the release id (`silero|<model>|<voice>|sr=…`). Load-bearing: without
  it v5 silently reuses v4 wavs under the same voice name, the exact silent-staleness class the
  key's INVARIANT exists to prevent. Legacy manifests re-render once, which is correct.
- `SileroEngine(model_id=…)` + docstring: both releases expose the same five speakers; v5 is
  Cyrillic-only, which is safe only because `text_tts` is Cyrillic by contract (measured: 0 Latin
  characters across all 12 batch videos) — noted with the condition under which a filter is needed.
- AUDITION (5 videos × 5 voices, same translations as the F5 run): synth 11-14 s vs F5's
  128-250 s (12-19× faster, CPU-only, GPU idle); pipeline RTF 0.14-0.17 vs 0.70-0.92; mean
  round-trip similarity 0.979-0.992 vs 0.985-0.991; 0 verify flags, 0 segments over ×1.8.
  Ear: eugene + kseniya best, xenia good-but-slightly-unpleasant, aidar/baya off-standard accent.
  Three ear-only defects (hiss/no ring, no expressiveness, dub lags picture) → DECISIONS + PLAN.
- Production default unchanged: `tts_engine = "f5"`. Full suite (11 files) green.

## 2026-07-19 — Transcribe guard: auto-retry on a collapsed word alignment + `asr` rollup
- NEW `transcribe.floor_run_ratio(flat) -> (ratio, longest_run)`: share of words sitting on the
  `MIN_WORD_DUR` floor IN A CHAIN (start == previous end), the signature of a whisper alignment
  collapse. Only chained hits count — whisper stamps on a 20 ms grid, so an isolated short word
  is ordinary output, not evidence.
- NEW `TranscribeStage._guard`: when the ratio exceeds `cfg.transcribe_floor_run_max` it re-runs
  ASR ONCE with `condition_on_previous_text=False` (the model stays loaded — no reload cost) and
  keeps the retry only if it at least HALVES the ratio; otherwise it keeps the original and says
  loudly that the timings are still suspect. Never silent either way.
- NEW `cfg.transcribe_floor_run_max = 0.085` (0.0 disables), marked PROVISIONAL with its sample.
- `run.json` gains an `asr` block (`n_words`, `floor_ratio`, `floor_longest_run`), recomputed from
  the already-persisted `words.json` — no new artifact, no schema break, and the SAME function the
  guard gates on, so report and guard cannot drift. Reported every run, not only when the guard
  fires: the threshold can only be calibrated from a distribution.
- `scripts/run_report.py`: `floor` column in the batch table, `- asr:` line per video block, and a
  new `--rebuild` flag (recompute run.json from artifacts) so older runs gain new rollup fields.
  Import of `floor_run_ratio` is function-local — a module-level one cycles
  `pipeline → runreport → stages.transcribe → pipeline`.
- NEW `tests/test_transcribe_guard.py` (12 tests: detector shape + every `_guard` branch on a stub
  ASR). Full suite 11 files green.
- FIXED in the AI-Fluency batch: `4szRHy_CT7s` (repetition loop → 2 duplicate sentence pairs, one
  slot at 294 char/s) re-transcribed with the flag off — 170 floor-stamped words → 0, max density
  294 → 24 char/s, atempo ×8.79 → ×1.03, no overlong terminator-free blocks came back.
  `RyvXxApfHkk` likewise re-run: max ×1.81 → ×1.57, 63.6 → 35.9 char/s.
- MEASURED (5 repeat runs × 3 videos): whisper's temperature fallback samples, so the metric scores
  the RUN, not the video — a "clean" control video hit 7.46% on one run of five. See DECISIONS.

## 2026-07-19 — Morning-triage HTML: flagged units with inline audio (closes PLAN item 1)
- NEW `scripts/triage_html.py [work/<id> ...] [--queue FILE] [--out PATH] [--link]`: renders one
  self-contained HTML page for a batch — a triage table (which videos need a listen) + per FLAGGED
  render unit its reason badges, EN/RU text, the ASR similarity + what whisper HEARD back vs the
  EXPECTED `text_tts` (the verify-triage payload), and an `<audio>` player for the unit's raw
  `segments/<lead>.wav`. Audio is base64-EMBEDDED by default (every player works under file://, page
  is portable); `--link` references wavs by relative path (tiny page, must stay next to work/).
  Read-only, best-effort, no model/GPU/network; a missing wav degrades to a note, a missing run.json
  to a skipped video. Videos needing triage sort first.
- NEW `runreport.flagged_units(report, translation)` (pure, tested): UNIT-level triage rows (deduped
  by `group_id`) — reasons unioned across a unit's members (verify/speed/assemble from the leader,
  completeness/translate from any member), leader id (= the wav key), similarity + hypothesis, joined
  EN/RU/tts text, span, speed. +3 tests; full suite (10 files) green. HTML validated well-formed in
  both audio modes on a synthetic workdir (embed base64 + link relative + ASR expected/heard block).
- README morning-triage bullets + skill Step 4 now point at the HTML page alongside the text digest.
  Closes PLAN item 1 (observability) in full.

## 2026-07-19 — Observability: per-run run.json + timings.json + digest + skill Step 4 (PLAN item 1)
- NEW `overdub/runreport.py` (pure stdlib, no model/GPU/network; one best-effort ffprobe): rolls
  up the ALREADY-PERSISTED artifacts into `work/<id>/run.json` — timings + RTF + stage breakdown,
  flag counts by type (translate/verify/completeness), speed distribution (median/p95/max of
  `combined_factor`, count ≥ 1.8), completeness aggregates, retry/repair, flags_total +
  needs_triage. Unit-level fields deduped by `group_id` (report records fan out per sentence) so
  speed/verify by_type count UNITS not member sentences.
- NEW `work/<id>/timings.json`: `run_pipeline` now persists each stage's wall-clock as it runs
  (`record_stage_timing`, atomic upsert) — a resumed/`--only` run rewrites only the stages it
  actually ran; skipped stages keep their last real timing. Never raises into the runner.
- CLI: `_run_one` refreshes run.json after the pipeline (one-line RTF/flags/triage headline);
  `_run_batch` prints a BATCH SWEEP (total wall, aggregate throughput, which video_ids need
  triage) after the existing summary. Both best-effort — a missing/None run.json never crashes.
- NEW `scripts/run_report.py [work\<id> ...] [--queue FILE]`: deterministic ENGLISH digest
  (per-video block + batch table + totals) built from run.json (or rebuilt on the fly). This is
  the DATA the overdub-sonnet-batch skill reads to write its Russian triage narrative.
- Skill: new **Step 4 — Human-readable report** (runs the digest, agent narrates in Russian);
  front-matter description now notes the route ends with a human-readable report.
- 21 tests (`tests/test_runreport.py`), no regression (completeness suite green, all 10 test
  files pass, imports resolve, no import cycle — runreport is stdlib-only). run.json validated on
  a synthetic workdir + the digest smoke. PLAN item 1 now down to its last open sub-part: the
  morning-triage HTML.
- Post-build adversarial review (ultracode, 4 lenses + verify): 9 confirmed minor/nit findings,
  all applied — verify by_type gained an `unknown` catch-all (silent-loss symmetry with translate);
  speed emits null (not a fabricated 1.0) when verify ran but assemble did not; `n_over_1_8` trusts
  assemble's raw-float rollup over the rounded recompute; a reset workdir clears its stale run.json;
  torn timings.json now warns before rebuilding; +6 regression-guard tests.

## 2026-07-19 — Route-B skill audit round 2: 5 gaps closed (SKILL.md only)
- Re-audit vs code after the round-1 hardening: commands/contract/flag table/stage order all
  hold; helper contract tests green. 5 residual gaps, all in SKILL.md orchestration prose:
  (1) `$ids` snippet now fails loud when a queue line doesn't match the id regex — an
  unmatched URL (e.g. `/live/`) is still processed by the pipeline via the `video_id()`
  hash fallback but was invisible to every gate → silent Gemma substitution at step 3;
  (2) `$ids` deduped with `-Unique` (CLI dedupes by video_id; two spellings of one video =
  two sub-agents racing on one draft file); (3) step-2 resume filter `$todo` — skip videos
  with a helper-validated translation.json, mtime clause re-queues drafts stale from a
  re-transcribe; (4) step-3 synth preflight now lists exact paths (config.py defaults incl.
  the not-in-repo ref clip) instead of "models/ exists"; (5) step-2 parallelism capped at
  waves of ~6 sub-agents. All three snippets verified live on a sandbox (dedupe/throw/
  single-URL scalar/todo filter/preflight)

## 2026-07-19 — Completeness A+B: deterministic verify-side loss flags (ultracode)
- NEW `overdub/completeness.py` — 4 non-blocking per-sentence detectors (num_loss/neg_loss/
  entity_loss/length_short) written to `report.json` at verify; rollup `rep["completeness"]`.
  Pure, no LLM/VRAM. 21 tests, no regression. Built via an 8-agent ultracode workflow
  (understand → build → adversarial verify → synthesize).
- Validation (x7DfiXqSEdM, 854 checks): num_loss+length_short = silent precise insurance (0 FP on
  clean data, fire only on a real number/clause drop); entity_loss ~100% FP structurally (naming
  rule permits Russifying personal names); neg_loss guards meaning inversion. User: keep all four
  as-is, triage-only, non-blocking. DECISIONS 2026-07-19
- PLAN: observability / run-report added as item 1 (persist stage timings, per-run rollup, flag
  counts by type, speed distribution, completeness aggregates, batch sweep) — completeness is its
  first data source

## 2026-07-19 — Route-B hardening: skill audit closed 8 defects (skill + helper)
- Skill audit (minimal-context-agent lens) vs code: commands/contract/flag table all held;
  8 gaps fixed. SKILL.md: ids from queue.txt (regex, never a `work/` listing — stale/baseline
  workdirs would be re-translated and their translation.json overwritten), gate before step 2
  (every sentences.json exists), MANDATORY gate before step 3 (every translation.json exists —
  a missing one silently falls back to Gemma with Ollama up, or fails with a misleading
  "start the daemon"), explicit `model: "sonnet"` for sub-agents (else session model silently
  substitutes), incremental draft writes for 300+ sentences, synth-prereq preflight before the
  overnight resume
- build_translation.py: writes pronounce_audit.json (parity with the local route — route B was
  silently losing the only detector for the out-of-dict Latin-name silent-loss class,
  DECISIONS 2026-07-17 item F); rejects non-string text_ru (JSON null coerced to "None" passed
  every _is_bad gate and would be voiced as «нон»). Both verified live on a synthetic workdir
- translate-contract.md: helper's outputs now include pronounce_audit.json
- A/B/C/D on x7DfiXqSEdM (427 sentences): gemma-base vs gemma-impr (completeness+lookahead+few-shot+
  anti-repeat bundle) vs sonnet-v1 (general-purpose) vs sonnet-iso (isolated agent). User read-through:
  Gemma bundle = parity but clumsier → dropped (×10 more >1.5× slots, no completeness win); Sonnet iso
  ≈ v1, no quality gain → dropped; Sonnet >> Gemma, confirmed primary. DECISIONS 2026-07-19
- Kept + committed: `.claude/skills/overdub-sonnet-batch/` (fixed route-B order: transcribe → Sonnet
  sub-agent writes `{id,text_ru}` draft → resume) + `scripts/build_translation.py` (helper fills the
  contract: src_en/timings, `text_tts` via normalize_for_tts, `_is_bad` gate, id-contiguity)
- Discarded: branch `gemma-completeness-ab` (translate.py prompt bundle) and the isolated
  `overdub-translator` agent type — neither earned its keep

## 2026-07-18 — Silero v5 recorded as the good no-sample TTS option
- User verdict: quality slightly below F5/ESpeech, but no narrator reference clip needed —
  zero voice-sample setup and zero rights questions. Documented in README (pipeline, stack
  table, Voices), STACK Stage 3, CLAUDE.md. Adapter still loads v4_ru → INBOX chore to bump
  (`v5_5_ru`; v5 rejects Latin script — needs an out-of-alphabet filter). DECISIONS 2026-07-18

## 2026-07-18 — Sonnet verdict: semi-automatic cloud translate is the primary route
- User read-through verdict on the A/B: Sonnet noticeably better and much faster; both routes
  declared good — Gemma = good quality, local, slow (in-pipeline default); Sonnet = subscription,
  better quality, cloud, replaces the heaviest stage. PRIMARY route = Sonnet in semi-automatic
  mode (sub-agent workflow at the translate seam). In-pipeline Anthropic API flag stays approved
  but deferred. DECISIONS 2026-07-18
- Runbook added to README ("Running"): route A — turn-key local batch (Gemma); route B —
  transcribe-only batch → Sonnet sub-agents write translation.json under the translate contract
  (text_tts via normalize_for_tts in Python, _is_bad gates) → plain rerun resumes from
  synthesize. CLAUDE.md hard-constraint note updated to match

## 2026-07-18 — fix: synthesize.done() congruence gate (stale-wav skip closed)
- done() now compares the manifest's own units against the CURRENT translation.json text_tts
  (same join as verify's reference); mismatch or uncovered ids → stage re-runs and re-renders
  exactly the changed units via the existing reusable() path. Closes the INBOX 2026-07-17 bug:
  `--force --only translate` + plain rerun silently skipped synthesize over stale wavs (bit the
  renorm A/B). Grouping changes stay WARN-only (no surprise regroup); unreadable translation
  keeps legacy behavior. New tests/test_synthesize_done.py (8 cases); all 7 suites green

## 2026-07-18 — Docs audit: README/STACK/SETUP caught up with the code
- README pipeline/stack/status still described the Silero era (contradicting its own "Voices"
  section); STACK's header pipeline line still said Chatterbox and Stage 3 had no section for
  the actual production engine. Both now document F5/ESpeech production + Silero fallback,
  the separate stage + bed mix, and Gemma/F5 VRAM figures
- SETUP: added the missing `.venv-demucs` section — separate.py's error message said "create
  .venv-demucs per SETUP.md" but SETUP never covered it (verified combo from the live venv:
  py 3.12, torch 2.11 cu128, demucs 4.1.0)
- INBOX: purged resolved (struck-through) entries; deleted the 3 superseded session conspectus
  from .claude-tasks/ (each declared superseded by the next; the 2026-07-18 handoff kept).
  Audit also confirmed: all 6 test suites green, no TODO/stub code in the package

## 2026-07-18 — Sonnet cloud-translate A/B spike (sub-agents, not yet in pipeline)
- Ran Claude Sonnet on the SAME 8 videos / 508 sentences / segmentation as the Gemma A/B, via 8
  parallel Sonnet sub-agents (one per video, same prompt rules) — a research spike, NOT the pipeline
  path. Reused Gemma's sentences.json so only the translator varied; built translation.json through
  the same normalize/_is_bad; published a Gemma-vs-Sonnet artifact
- Findings: Sonnet holds length near 1:1 (median 1.00 vs Gemma 1.06 — best dubbing-fit of the three
  models), more natural, and corrects ASR errors both local models translated literally (CLAWD→
  Claude, entropic→Anthropic, «дообучение» for fine-tuning). Flag counts (Sonnet 7 vs Gemma 4) are
  noise — all the «как ИИ/модель» refusal-regex false positive (INBOX); real flags 0/0
- Speed: ~3× faster than Gemma without parallelism (988s cumulative vs 2691s), order-of-magnitude
  faster in parallel (~4 min wall for 8 agents vs ~45 min). Cost: ~$3 per hour of source video (cloud)
- No adoption decision yet — awaiting the user's read-through; if adopted, the in-pipeline opt-in
  Anthropic path still has to be built. completeness-check + babble heuristic returned to the backlog
  tail (triggers: model errors on short sentences / a narrator-voice or TTS-engine change)

## 2026-07-18 — Gemma-3-12B replaces Qwen3-14B (translation model swap)
- 8-video A/B on identical `sentences.json` (the Qwen stats batch's finished 8; only the translator
  varied — bed + downstream byte-identical). 508 sentences: Gemma tighter (len ratio median 1.062
  vs 1.086), fewer flags (4 vs 6), ≈ verify sim. User read ~100 phrases — all better on Gemma;
  Qwen's defects (эффективное×2 for effectively/efficiently, "fluent" left Latin, "Интеллектуальная
  грамотность" for AI fluency) absent. DECISIONS 2026-07-18
- Cost: ~16% slower translate (5.30 vs 4.58 s/sentence), ≈ +8–10% end-to-end. Accepted for the quality
- Code: translate stage folds SYSTEM into the user turn + sends no "think" key (Gemma 3 has no
  thinking mode and rejects a system role). The A/B's two config flags AND the Qwen branch removed
  (Qwen not kept even as an option); `ollama_model` default qwen3:14b → gemma3:12b. Live smoke green
- Built via an ultracode workflow (7 agents) that kept the Qwen wire-request byte-identical during
  the A/B, then collapsed to the single Gemma path. Reference docs updated (Qwen findings in STACK
  retained as history)

## 2026-07-18 — Whisper-context fix ear-validated: roadmap item 0 CLOSED
- Full --force pass on a fresh workdir with `whisper_condition_on_previous=True` (x7DfiXqSEdM,
  work-exp/context-earcheck). Objective: 427 sentences (matched the predicted 314→427), 0 verify
  flags, max speed 1.288, 0 units >1.8. User ear verdict: all found problems gone, no sudden
  pauses, "sounds better than ever"
- One accepted roughness: speech slightly slow (inter-word gaps a touch large) = the slot-fill
  stretch (f5_speed_floor). Compressing instead would open inter-phrase gaps (worse). Root lever is
  the "keep length" prompt pressure (PLAN Open questions), not a post-hoc squeeze. NB the ear-check
  dub used Qwen — the segmentation verdict is translator-independent

## 2026-07-17 — Whisper punctuation context: segmentation root fix (config flag)
- Ear check of the segfix run found the "period mid-sentence" defect frequent (181/314
  sentences open mid-thought). Layered trace: the full stop is Qwen's, but the BREAK is
  `_split_overlong`'s, forced by whisper returning 60-206 s terminator-free blocks under
  `condition_on_previous_text=False`. Qwen is 1:1 and only inherits the break
- Single-variable experiment (flipped ONLY the whisper flag, re-ran ASR): max terminator-free
  range 206→27 s, 314→427 real sentences, both ear cases whole in one sentence. Proves the
  root is whisper punctuation, not Qwen
- Hallucination risk (why the flag was off) measured on the music video: longest repeat run =
  3 ordinary words, zero loops — safe. Shipped as Config `whisper_condition_on_previous`
  (default True, not hardcoded — a looping source can flip it off without code)
- The segmentation cluster (9ca7751) is now second-order (with context on, `_split_overlong`
  rarely fires) but kept as the fallback splitter. Priority lesson in DECISIONS: test the root
  before polishing the symptom
- NOT yet re-run to MKV with the flag on — a full --force pass (~46 min) is the ear-check

## 2026-07-17 — Segmentation cluster: the "pause" that wasn't (transcribe/translate/assemble)
- Root cause (measured on stored words.json, not guessed): `_split_overlong` branch 1 treated
  whisper `seg_end` as a speaker pause, but 73% of seg_ends carry a 0.000 s gap (VAD/window
  artifact). Both ear-reported splits (id149/150 "survival | exploration", id188/189
  "met through | Xbox Live") were cut at gap 0.000, chosen purely by time-midpoint proximity
  ('survival' beat 'games' by 0.030 s). NOT the MAX_SEC cap — the emitted spans were recursion
  leaves with _too_long=False
- Fix: MIN_PAUSE_SEC=0.20 gate on branch 1 + `_ok_cut` veto applied to all three branches
  (filter in 1/2, sort-preference in 3 so it always cuts); `_CONJ`→`_CUT_BEFORE` drops
  ambiguous subordinators (that/which/who/as/if…) that severed verb-object pairs; item E
  ('.'+seg_end before a lowercase word is a boundary, 11/11 genuine on corpus)
- Item F (translate prompt): proper NAMES of games/brands stay Latin with canonical casing
  (runescape→RuneScape) so pronounce.py owns them; `_is_bad` echo gate keys on `islower()`
  and accepts a names-only line whose normalize_for_tts yields Cyrillic (retired id150 false
  english_echo). Item G (assemble): display-only cue split at clause punctuation, ≤6 s/84 ch,
  flash-guarded — sentences.json/ids/timings untouched
- Items C (tolerance band) and D (Capital-after-lowercase run-on) REJECTED on corpus evidence:
  C breaks F5's 12 s unit cap and lets merges rebuild long sentences; D ~5% precision (cuts
  inside "Call of|Duty"). The ear reported A/B/F/G, not C/D
- Process: ultracode workflow, 31 agents; Measure phase first (empirical, disproved my own
  "it's the 15 s cap" diagnosis); 10 review findings all confirmed and fixed (incl. a critical:
  clause branch cutting before "that"). Fix/Smoke re-run after a mid-flight 529. Smoke: 6 test
  suites green, corpus A/B invariants hold, both ear bugs at defensible boundaries, corpus
  SHA-identical (untouched). NOT yet ear-validated post --force re-transcribe

## 2026-07-17 — Proper nouns (roadmap 1, code): pronunciation chain replaces naive translit
- New `overdub/pronounce.py`: PHRASES (multiword names, raw-text pass before numerics) →
  WORDS (~50 established RU spellings: ютуб, иксбокс, хейло, майнкрафт…) → plural tails →
  case-gated acronyms (It/Ok no longer misread; GPUs via singular) → letter names →
  ~74-rule left-to-right practical transcription (sky→скай; the vowel-less скй class is
  structurally excluded — rule output without a vowel letter-spells instead)
- normalize.py passes 0a (phrases) + 1b (PS5→пи-эс пять seam split; after pass 1 so
  1920x1080 is not "в раз") + rewritten pass 6; purity/idempotency/Cyrillic-only intact,
  verify inherits identical resolution via normalize_for_compare
- "Per-run cache" reinterpreted (DECISIONS): audit-only `pronounce_audit.json` from
  translate — dictionary-seeding material, never a resolution input
- `tools/renorm_workdir.py` SRC DST: A/B copy with re-derived text_tts, no LLM re-run,
  SRC untouched; downstream self-heals, only changed units re-render
- Process: ultracode workflow, 43 agents / ~2.9M tok: corpus mine (55 tokens, 60 goldens)
  → 2 designs → judge → impl → 4-lens review (16 findings, all confirmed incl. 2 majors:
  hardlinked wavs could corrupt read-only corpus; acronym-plural bypass) → fixes → smoke:
  4 suites green, 710-sentence sweep 0 violations, 72/710 text_tts improved
- Ear verdict (user, same day, A/B on renormed f5-control — 31 units re-rendered, verify
  0 flags): pronunciation CORRECT on all five target ids — item CLOSED. The A/B also
  surfaced upstream findings (transcribe mid-phrase splits, Qwen self-transliteration,
  long subtitle cues) — reclassified to their own stages, INBOX 2026-07-17
- Found live by the A/B: renorm tool bug — copied complete:true manifest made synthesize
  skip over stale wavs (done() never compares text_tts); fixed same day, tool now writes
  complete:false

## 2026-07-17 — Batch queue + stop switch (roadmap 2-3): overnight runs are turn-key
- `--batch FILE`: one URL per line, `#` comments/blank lines skipped, BOM-safe (utf-8-sig),
  dedupe by video id first-wins; sequential turn-key runs. A failed video prints the full
  traceback and the batch CONTINUES; summary rows [ok/FAIL/stop/not run] + counts; exit codes
  0 ok / 1 any fail / 2 usage / 3 stop-halt. `--force`/`--only` pass through per video
- Stop switch: `work_root/STOP` checked before EVERY stage boundary (hence also between
  videos), consumed at honor time; stale file swept at startup (unremovable → loud abort).
  Halt prints where it stopped; a plain re-run resumes (artifact-driven skip)
- Export: final MKV hardlinked (copy fallback) into `output_dir` (new key, default `out/`)
  as `"<title> [<video id>].mkv"` — atomic .tmp flip, mtime-based refresh on re-mux,
  stale-export cleanup; `work/<id>/output.mkv` never moves. Title persisted at download
  (`--write-info-json`) with a one-shot metadata-only backfill for pre-change workdirs;
  offline → loud id-only fallback. `safe_filename()` in workdir.py (Windows reserved names,
  forbidden chars, 120-char cap, Cyrillic preserved)
- Process: ultracode workflow, 34 agents / ~2.0M tok: 2 design biases → judge spec → impl →
  4-lens adversarial review (13 findings → 11 confirmed by 2-skeptic verify, all fixed) →
  smoke 52/52 (stubbed batch/stop/export/sanitizer, no network). Not yet run on real videos

## 2026-07-17 — Dead-air CLOSED by ear: ceil→atempo fix + bed@0dB is the production mix
- Final ear verdict (user): L3 bed on a music-heavy source works perfectly; the 17:02
  mid-word cutoff is fixed acceptably; remaining artifacts roughly mirror the source's own
  unusual intonations/stutters — the dead-air problem group is closed
- Closing changes: f5_speed_ceil 1.6 → 1.1 (native F5 compression ≥~1.3 drops words; atempo
  never does — it takes the top-up), stricter gate 0.9 for compressed units (ONE shared
  unit_sim_threshold in synthesize + verify); _BED_GAIN −6 → 0 dB; dub_mix default → "bed".
  Duck-depth retest and bed-RMS census/auto-fallback cancelled by the verdict
- Control resynth (39-min): ex-defect unit [135-137] now native 1.1 + atempo ×1.20
  (combined ×1.32) with roundtrip sim 1.0 verbatim; 0 flags, 0 retries, 9 compressed units
  all ≥0.985; residual in-span silence 203.8 s accepted (speech-only source → bed ≈ replace)
- Music-video check (tJP6SKfo49c, 3.6 min, bed stem −29 dBFS RMS / active 99%): full
  turn-key on the flipped defaults incl. auto separate stage; 0 flags, atempo max ×1.18,
  in-span silence 2.9 s — L3 validated on real music
- Commits: 053b29a (fix ceil+gate), 87c31d9 (feat bed@0dB + default), 58831e3 + this (docs)

## 2026-07-16 — Dead-air elimination: slot-fill speed + render units + duck/bed mix
- Measured root cause first: 665 s silence on the 39-min F5 dub = 607 s RU-underfill (fast
  narrator ends before the EN span) + only 68 s real gaps (median 0.14 s) — not a timing bug
- L1 slot-fill: per-unit native F5 speed from the span budget (plan_speed, pure, 16 tests);
  stretch floor 0.75 fixed by a pre-registered bench rule (canvas formula err ≤1.5% incl.
  group-shaped texts, sims stable to 0.7); compress ceil 1.6 before atempo. Caps are
  multipliers of the narrator base pace and enter synth_key
- L2 render units: sentences grouped at synthesis (gap ≤0.4 s, span ≤12 s, ≤300 chars) —
  natural prosody, ultra-shorts dissolve; manifest v3 "units" + units_key fingerprint;
  per-sentence report records with group_id; verify refs CURRENT translation
- L3 dub_mix: replace | duck (sample-exact −15 dB envelope over spans extended to placed
  audio, merged <1 s) | bed (htdemucs no-vocals −6 dB, new separate stage in .venv-demucs,
  45 s for a 39-min video); all modes RMS-align dub loudness to the original (+4.0 dB here)
- Self-healing done() chain: synth/units key stamps in verify/assemble, dub_mix/mtime deps
  in mux — flipping dub_mix re-runs exactly mux (the 3-output A/B costs seconds per mode);
  artifact-flips-before-stamp discipline everywhere (review catch: stamp-first + failed
  replace = silently served stale audio)
- Process: design panel (3+3, 651k tok) → impl → 4-lens adversarial review (25 agents,
  1.51M tok): 20 findings, 1 refuted, all fixed. Control result: in-span silence 204 s
  (−66%), 0 flags, 0 atempo, unit sim mean 0.9939, synth 996 s (was 1409 — fewer calls);
  three outputs produced for the ear verdict, dub_mix default flip pending it

## Phase 3 — TTS engine upgrade ✅ (closed 2026-07-16)
- [x] Research sweep + adversarial verify of the July-2026 local RU TTS landscape →
      bakeoff/tts-research-2026-07.md (~20 engines; only Silero/ESpeech/Misha speak Russian)
- [x] Bake-off #2: ESpeech-TTS-1_RL-V2 unambiguous winner by ear; RU-voice cloning works,
      EN-cloning dropped by goal (DECISIONS 2026-07-16)
- [x] F5Engine behind the adapter — worker in .venv-f5tts, synth_key resume guard, manifest v2
- [x] Reseed-retry in synthesize (keep-best), proven on id43
- [x] Ultra-short merge in transcribe, unit-tested
- [x] Narrator: ESpeech demo reference (rights caveat; PD fallbacks in DECISIONS)
- [x] Control run 39-min vs Silero baseline: flags 0 vs 1, sim 0.9943 vs 0.986, 0 retries;
      RTF gate missed (×0.65 vs ≤0.5, thermal) — x5 budget still cleared ~3.8×
- [x] User ear check passed (id101 ultra-short noted bad → feeds roadmap item 1); default
      tts_engine flipped to "f5", Silero stays the fallback

## 2026-07-16 — F5Engine integrated: worker adapter, reseed-retry, ultra-short merge, control run
- ESpeech (F5-TTS) is now a first-class engine behind the adapter: overdub/tts/f5.py drives a
  persistent worker (overdub/tts/f5_worker.py) in .venv-f5tts over JSONL stdio — venv merge was
  killed by measured evidence (torch 2.11 vs 2.8, numpy downgrade, ~110 packages, torchcodec ABI).
  fd-level stdout isolation, reader-thread timeouts, id-echo, respawn-once + 3-strike TtsFatalError
  (ok:false counts too — sticky CUDA context). Startup ~30 s, warm synth ~×1.1 audio, 0.7 GiB VRAM
- Reseed-retry in SYNTHESIZE (manifest single-writer; verify stays the pure judge): in-stage
  whisper-small round-trip via shared asr.roundtrip_similarity, seeds base+1..+3, keep-best.
  Proven on id43: 4 attempts, best kept, honestly flagged when still low
- synth_key resume guard: engine|ref-content-hash|ckpt|nfe|speed|seed gates ALL wav reuse (engine
  switch / ref swap / knob change → full resynth, loud [info]); manifest v2 with complete-marker,
  downgraded before wavs mutate, flushed every 25 fresh segments (overnight interrupt-resume)
- Ultra-short sentence merge in transcribe (chars<15 → merge into neighbor, gap ≤0.6 s, chain
  absorption ≤1.5 s) + 8 unit tests — kills the id43 class at the source for fresh videos
- Process: design panel (3 biases + 3 lens judges, 610k tok) → implementation → adversarial review
  (4 lenses, per-finding refutation, 1.25M tok): 16 findings, 0 refuted, ALL fixed — incl. 5 major
  (poisoned-CUDA grind cap, sf.info wav/manifest divergence, stale complete:true during resynth,
  ckpt identity missing from synth_key, first-round-trip failure destroying good audio). Judges
  also caught two factual errors by all designers (id43 is in the SAMPLE video; baseline's only
  flag id189 is engine-independent) → control gates made absolute, not baseline-relative
- Control run (39-min x7DfiXqSEdM, frozen transcript/translation, baseline untouched): F5 beats
  Silero on every quality metric — flags 0 vs 1 (id189 proper-noun: F5 0.95 unflagged vs Silero
  0.661), sim mean 0.9943 vs 0.986, min 0.837 vs 0.661, atempo ×1.014/max 1.87 vs ×1.018/max 2.08,
  0 retries. RTF gate missed: synth+verify ×0.65 vs ≤0.5 target (thermal-loaded vs cold 0.39);
  full pipeline ~×1.33 realtime, x5 budget cleared ~3.8×. Default engine flip awaits the user ear
  check (Phase 3 stays open on that one item)

## 2026-07-16 — TTS bake-off #2: ESpeech adopted, narrator selected, cloning explored
- RTF gate PASSED: 39-min real video end-to-end ×0.75 realtime (translate = 80% of wall-clock),
  x5 budget cleared 6.7×. Real-content triage surfaced the proper-noun transliteration defect
  ("но ман'с скй", english_echo false flag) → queued as work item 2 in PLAN
- Multi-agent engine research (~20 engines, adversarial verify, ~940k tokens) →
  bakeoff/tts-research-2026-07.md; only Silero/ESpeech/Misha credibly speak Russian. Bake-off #2
  by ear (bakeoff/listen.html, 8 phrases × 5 engines incl. Silero v5): **ESpeech-TTS-1_RL-V2 wins**
  — .venv-f5tts + ESpeech/Misha checkpoints installed, RTF 0.39 @ 0.8 GiB VRAM measured on host
- Voice cloning explored on full-video runs: RU-ref WORKS (user's voice: 0.994 / 0 flags);
  EN-ref (original-speaker premise) diagnosed — F5 sizes duration by UTF-8 *byte* ratio, Latin ref
  → ×2 canvas → babble filler; two fixes verified (speed≈1.7 → 0.980), then DROPPED by project
  goal. Famous-voice refs (personal-use) failed the quality bar (noisy refs clone their noise)
- Narrator adopted: ESpeech demo reference (0.992 / 0 flags / ×1.03); rights caveat documented in
  README ("Voices, cloning and the law" section); PD fallbacks (LibriVox: tovarisch/Kazbek/Chulsky)
  recorded in DECISIONS; speed-calibration for slow narrators validated (×1.03–1.08 @ ≤0.022 sim)
- New scripts: bakeoff2_silero/bakeoff2_f5/bakeoff3_narrators (auditions), lv_pick_refs
  (PD reference cutting), exp_clone_synth (full-video F5 synth — the F5Engine prototype)
- Intermediate voice artifacts pruned; kept work-exp/espeechvoice (chosen-voice run) + the ref clip

## 2026-07-16 — Phase 1 validated (user ear-test)
- User inspected the assembled output on a real video: RU dub audio present, positioned at the
  correct timestamps, translation correct. This is the Phase-1 quality gate — the pipeline is
  proven turn-key (URL→MKV) on real content, not just mechanically on the sample. Phase 1 closed;
  next up is Phase 2 (batch mode) after broader real-content passes + full-length RTF measurement

## 2026-07-15 — Pipeline tail: synthesize + verify + assemble + mux (Phase 1 complete, turn-key)
- Filled the last 4 stub stages → the pipeline now runs URL→MKV end-to-end. Design panel
  (3-bias) + adversarial review (4-lens + per-finding verify) workflows, per the project rhythm
- synthesize: build_engine (Silero eugene) renders text_tts → segments/NNNNN.wav + manifest.json;
  atomic per-wav (tmp+os.replace), staleness-guarded resume (text_tts + flag), 0-frame honest
  empty slot, sr-drift guard, never-drop contiguity
- verify: whisper-small round-trip on RAW wavs; char-level SequenceMatcher(autojunk=False) of
  normalize_for_compare(text_tts) vs RU hypothesis @ 0.8; deterministic → flag not reseed;
  done() checks the "verify" marker key (NOT report.exists()) so an out-of-order run can't
  silently disable verification; loud guard if run before synthesize
- assemble: place each clip at absolute round(start*sr) in an int16 buffer, slot = [start,
  next.start) (gap = pause headroom), atempo uncapped (ffmpeg single-filter 0.5–100), speed
  factor logged UNCAPPED; dub_ru.wav + en.srt/ru.srt; atomic dub written last
- mux: MKV = av1 video copy + orig aac + RU dub (aac 128k, DEFAULT track) + EN/RU SRT with
  language metadata; explicit per-stream maps; atomic .mkv.tmp
- new overdub/report.py: co-owned report.json (load/upsert/save/prune, merge-by-id) so verify
  and assemble never clobber each other's fields; + workdir.seg_wav; silero.py explicit format="WAV"
- Verified on the 50-sentence sample (each stage via --only): synth 50/0-flagged, verify mean
  sim 0.988 / 0 flagged, assemble 3 sped max ×1.23, mux → 5-stream MKV (video not re-encoded).
  Review: 13 findings → 11 kept (all PLAUSIBLE/low), 2 refuted; 8 cheap fixes applied, 1 → INBOX

## 2026-07-15 — Project founded
- Repository initialized, documentation written (README, CLAUDE.md, artifact files)
- Stack and constraints fixed: see DECISIONS.md founding entry

## 2026-07-15 — Stack installed + day-1 TTS bake-off
- Installed local stack on the RTX 4080 Mobile: Ollama 0.31.2 + qwen3:14b,
  faster-whisper (.venv-asr), verified CUDA in both venvs
- Multi-agent stack-verification pass → STACK.md + SETUP.md (verified APIs, VRAM)
- Day-1 ear test on a real video: Chatterbox RU rejected (unusable even without
  cloning); Silero v4_ru adopted — voice eugene, xenia backup. Cross-lingual
  cloning dropped (same-voice premise abandoned). See DECISIONS engine bake-off.
- Experiment scripts: scripts/{day1_smoke_test,no_ref_test,silero_test}.py

## 2026-07-15 — Phase 0 skeleton
- overdub package: CLI, flat-TOML config, per-video workdir, resumable stage
  runner (skip-if-exists, --only/--force); 7 stages (download real, rest stubs)
- TTS engine adapter + SileroEngine (torch.hub v4_ru/eugene, soundfile output)
- Consolidated to one venv (.venv-asr); .venv-tts retired; `pip install -e .`
- Verified end-to-end: `overdub <url> --only download` → source.mkv + source.wav

## 2026-07-15 — Transcribe stage (Phase 1)
- faster-whisper large-v3 → word timestamps → word-level sentence resegmentation
  → sentences.json (+ words.json for re-tuning). Design + adversarial review via
  two workflows (3-approach design panel; 4-lens review + verify)
- Shared asr.py: Windows cuDNN DLL discovery + whisper loader; cuDNN verified on host
- 885 words → 50 sentences in 32s (RTF ~0.08); contract validated (ids contiguous,
  no zero-duration slots, monotone non-overlapping, no stutter/dangling artifacts)

## 2026-07-15 — Translate stage (Phase 1)
- sentences.json → Qwen3-14B (Ollama) → translation.json: per-sentence, id order,
  rolling ok-only context window; text_ru (subtitles) + text_tts (normalized for TTS).
  Design + adversarial review via two workflows (3-approach panel; 4-lens review+verify)
- New overdub/normalize.py: deterministic digits/units/acronyms/Latin/symbols → spoken
  Russian; idempotent, Cyrillic-only output; normalize_for_compare reused by verify.
  num2words (ru) added; stdlib speller fallback. 9 unit tests (magnitude/range/collision)
- Native Ollama /api/chat + think:false (not /v1 — /no_think left content empty on
  truncated reasoning); ~5s/sentence, openai dependency dropped, stage now stdlib-only
- Robustness: validate→reseed-retry→flagged EN fallback (never drop); append-only
  translation.jsonl (fsync) resume keyed on src_en; contiguity enforced; atomic write
- Verified on the 50-sentence sample: 50/50 ok, 0 flagged, RU/EN length ratios ≤1.67
  (atempo-friendly), resume confirmed (47→50 in 19s). Review fixed 3 silent magnitude
  bugs in the normalizer (grouped thousands, decimal ranges, Cyrillic х/с collisions)
