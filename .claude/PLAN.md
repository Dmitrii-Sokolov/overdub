# PLAN

## → Roadmap (re-cut 2026-07-20 — the three items that led this list shipped; scout mode leads now)
Sample workdirs: `work/` (13 dirs — Silero baselines + the AI-Fluency batch, read-only).
**Corrected 2026-07-20 — the rest of this line was stale:** `work-exp/context-earcheck/`,
`work-exp/stats-batch/` and `work-exp/gemma-ab/` NO LONGER EXIST on disk (`work-exp/` holds only
`nfe-sweep/` and `nfe16/`). The Qwen-vs-Gemma A/B set and the 8/23 stats-batch workdirs are gone;
the published A/B report artifact (508 sentences) is the only surviving record of that comparison,
and the stats-batch URL list is unrecoverable. Report triage: any *_flag or speed_factor>1.8.

**Before the first overnight batch on the new order — two side effects, neither a bug:**
(a) `download` amortises nothing, so hoisting it means a 100-video queue downloads in full before
the first transcribe — ~100 GB in hour 0. Watch for ENOSPC; the compensation is that network
failures surface immediately instead of smeared across the night. **Measured 2026-07-20: 81 GB free
on D: (of 3.8 TB).** That is less than one full large-queue run, so queue size is bounded by disk,
not by patience — and the already-deleted `work-exp/` baselines suggest a space cleanup has happened
once already. Decide what in `work-exp/` is a consumable and what is an archive BEFORE the next
3am cleanup makes that call for you.
(b) `_title_of` is a networked `yt-dlp --print title` with a 30 s timeout for pre-change workdirs.
Those calls used to be spread across the batch; in the finish sweep they queue back-to-back — an
offline resume of 12 videos can sit in up to 6 minutes of timeouts in one block at the very end.

**→ DO THIS BEFORE THE NEXT BATCH (opened 2026-07-20).** Items 1-3 below are implemented but
**uncommitted and not ear-checked**. Three checks stand between the change set and trusting it:

  a. **`--only synthesize` fast-skip on an existing workdir.** Item 1 widened the `translation.json`
     record with `src`/`src_note`. `synthesize._write_manifest` fingerprints `(ids, text_tts,
     samples)` field-selectively, so extra keys SHOULD be inert — static reading only, never
     executed. If that is wrong, the next batch silently re-renders hours of audio. One cheap run
     settles it. **Do this first; it is the only check that can waste a whole night.**
  b. **Listen to a repaired window.** DECISIONS 2026-07-20: window re-ASR is a trade, not a free
     improvement, and it regressed `Claude` → `Cloud` on real audio with both readings agreeing. A
     repaired window now deserves the same listen a flagged one gets. Nothing automated can replace
     this.
  c. **Re-run the spec-blind contract tests knowingly.** `tests/test_repair_contract.py` exists and
     passes, but the agent that wrote it died before reporting, so it is unknown whether it found
     failures or quietly relaxed its assertions to go green. Read the file once against DECISIONS
     before counting it as independent evidence. Until then it is a test file, not a verification.

Also unreconciled (DECISIONS 2026-07-20, provenance section): this repo records
`RyvXxApfHkk#11` at 246 ch/s while the preserved backup measures 35.9, and "7 repairs" against 12
on-disk diff blocks. Someone's number is wrong; the recall figure below inherits that uncertainty.

1. **Scout mode — summary only, nothing else.** `download → transcribe → summary`, full stop: no
   translate, no synth, no verify, no assemble, no mux. The point is deciding whether a video is
   worth watching AT ALL before spending anything on dubbing it — the honest form of the skip-gate
   the summary item deliberately did NOT build, with the human as the decider instead of the model.
   Pairs with a batch-level scout page: N videos, each with its ~200-word summary and verdict, one
   screen. **Half of this is already done** (CHANGELOG 2026-07-20): `summary.md` exists and a
   summary-only workdir already surfaces it in the text digest, so `runreport.read_summary` needs no
   change. What is missing is the MODE and the page — `scripts/triage_html.py` skips a workdir with
   no `run.json` by design, so scout summaries never reach the HTML. Open:
   (a) **does scout need the full video download?** If it pulls the whole MKV the saving is GPU
   only — network and disk are untouched, which at 100 videos is most of the cost. An audio-only
   fetch (`yt-dlp -f bestaudio`) is where the real economy is, but then promoting a scouted video
   to a full dub must not re-download from scratch — the artifact-reuse story is the actual design
   work here, not the flag; (b) whether scout is a `--only` composition or its own mode; (c) how a
   promoted video skips re-transcribe (it should — `sentences.json` already exists).

2. **Batch/video timing accounting — amortised model loads are misattributed.** Since stage-major
   batch execution shipped (CHANGELOG 2026-07-19) one F5 worker spawn is amortised across the whole
   batch, but `timings.json` / `run.json` still bill wall time per video. So the FIRST video of a
   batch absorbs the entire model-load cost and reads slow, every later one reads fast, and per-video
   RTF is not comparable across batch positions. `--video-major` has the opposite profile (a load per
   video), so the two modes' numbers are not comparable to each other either. Fix: record setup /
   model-load time as its own line, separate from processing time, so per-video RTF is honest in both
   modes and the batch total reports amortised setup once instead of smearing it.
   **Blind spot this opens:** every speed verdict measured so far rests on this accounting — the
   `nfe` 48→16 "2.16× on synthesis" number included. Re-check whether any recorded measurement was
   distorted by which position in the batch it was measured at, before trusting it in a future
   comparison.

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
"гхз"; decade suffixes "90х" → "девяностох"; "10-20%" keeps a literal dash); `libopus` for the dub
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

Deferred — NOT near-term (revisit when a need surfaces): in-pipeline Anthropic API translate flag
(approved in principle, DECISIONS 2026-07-18; build ONLY if the manual sub-agent seam becomes the
bottleneck — it is not one today, and the seam is where items 1 and 3 both hang their sub-agents,
so automating it away has a cost beyond the code); gender-matched
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
the translate seam ✅ (2026-07-20)**. All three await the pre-batch checks at the top of this file.

Stack pins, verified APIs and setup: STACK.md + SETUP.md. Translation: Gemma-3-12B (Ollama),
`gemma3:12b`, local in-pipeline default by A/B 2026-07-18 (Qwen3-14B removed); PRIMARY route =
Sonnet semi-automatic (DECISIONS 2026-07-18, runbook README "Running"). TTS: ESpeech-TTS-1_RL-V2 (F5-TTS,
.venv-f5tts) — production by ear 2026-07-16; narrator = ESpeech demo reference (rights caveat in
README). Silero v4/v5 = fallback; Chatterbox rejected day-1.
