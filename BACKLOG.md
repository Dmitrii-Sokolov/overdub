# Backlog

One line per task, phrased as an outcome. Detail lives in `tasks/`, created when the task is
picked up. Written by `/triage`; an executor may only tick its own line on completion.
Tasks are NAMED by slug, never numbered — the numbering was re-cut with every roadmap while code
references stayed put, so "item 1" meant four different things by 2026-07-22 (DECISIONS 07-22).
Line order inside a section is the priority order; the next measurement is allowed to overturn it.
Admission rule: an item must change the TOOL (CLAUDE.md) — repairing one video is never an item.

## Open — ordered by value (re-cut 2026-07-27; there is no blocker)

- [ ] The first video reaches its post-translate tail while the next still translates: mux profiled and taken, a clean end-to-end figure, acceptance re-phrased → tasks/pipeline-batch-latency.md
- [ ] Proper nouns survive ASR into all three surfaces (dub, EN subs, RU subs) via a name list at the source pass → tasks/asr-name-list.md
- [ ] Promotion into route B confirmed once on real media (transcribe fast-skips, download re-runs) → tasks/promotion-to-dub.md
- [ ] The translation is sized to its slot (target chars = slot ÷ voice rate); the runaway gate re-anchored → tasks/slot-fit.md
- [ ] The dub stops reading flat: translator punctuation quality + `<p>`/`<s>` SSML → tasks/input-prosody.md
- [ ] Out-of-dict pronunciation comes from CMUdict phonemes, not spelling → tasks/cmudict-transliteration.md
- [ ] Stress audit of the dictionary (gated on the CMUdict task) → tasks/stress-audit.md
- [ ] Voice post-processing: compression/EQ on the dub, judged by ear → tasks/voice-postprocessing.md
- [ ] The batch is re-timed on Silero (after slot-fit) → tasks/retime-batch-silero.md

## Also open — independent, not ordered against Open

- [ ] Dual-form seam cost measured on the first real batch; pre-set rule: too expensive → roll back → tasks/dual-form-seam-cost.md
- [ ] The chunked-translate threshold re-sited on characters, not sentences → tasks/chunk-threshold-on-chars.md
- [ ] Next-batch watchlist worked through once (repair recall, download outlier, needs_triage rate, gap column, translate-batch unexercised paths) → tasks/next-batch-watchlist.md
- [ ] Transcribe's 35× wall variance explained; transcribe figures quotable again → tasks/transcribe-wall-variance.md
- [ ] host_guard gates on the SM clock instead of utilization.gpu → tasks/host-guard-sm-clock.md
- [ ] Batch capacity persisted to work/capacity.jsonl with a config fingerprint → tasks/persist-batch-capacity.md
- [ ] Per-video sub-agent token cost recorded, keyed per 1000 sentences → tasks/record-sonnet-cost.md
- [ ] Translator `src != ok` verdicts feed `--repair-asr` seeds (additional source only) → tasks/src-seed-repair.md
- [ ] The sentence rebuild stops cutting unpunctuated sentences in half (166 of 388 truncated are ours) → tasks/rebuild-truncated-endings.md
- [ ] work/<id>/ binaries cleaned after a successful mux; mux input moves to output.mkv first → tasks/clean-workdir-after-mux.md
- [ ] work-exp/ classified consumable vs archive, before the next disk cleanup decides → tasks/work-exp-archive-policy.md
- [ ] effort:'low' A/B for route-B translators — shorter turn chain vs Russian quality, ear-judged (numbers: DECISIONS 2026-08-20) → tasks/translator-effort-low.md
- [ ] Decided whether the detector-driven repair half needs a home on Parakeet (completeness-seeded re-reads; that class's rate on Parakeet unmeasured; DECISIONS 2026-08-06) → tasks/parakeet-repair-home.md
- [ ] The floor CHAIN recalibrated off the accumulated series (`_guard` still gates on the "knowingly unreliable" ratio — config.py's own comment asks; `floor_longest_run ≥ 40` separates the real collapses) → tasks/floor-chain-recalibration.md
- [ ] download/verify/assemble/mux report timing `detail`, so `work_complete` can go True on a real run → tasks/stage-timing-detail.md
- [ ] Repair-window hotwords/initial_prompt — decide whether `--repair-asr` earns more investment at all (word lists cheapest first; measure on the golden fixture; DECISIONS 2026-07-20) → tasks/repair-window-hotwords.md

## Backlog — lower value

- [ ] Throughput on weaker hardware: low-VRAM / GPU-less host, Arc B390 path (whisper.cpp SYCL) — after the Silero re-time → tasks/weaker-hardware.md
- [ ] Per-chunk silence trimming + crossfade at joins (the "seams") → tasks/seam-crossfade.md
- [ ] A versioned stress dictionary (`terms.tsv`) for domain terms — the class `pronounce_audit.json` surfaces and nothing consumes → tasks/terms-tsv.md
- [ ] `MIN_SENT_CHARS` re-validated on Silero (calibrated on retired F5; synth sub-15-char units alone vs merged and listen — before any further merge tuning, every other merge knob is calibrated against this one) → tasks/min-sent-chars-silero.md
- [ ] The translator knows the narrator's grammatical gender (median-F0 pass → prompt field) → tasks/narrator-gender-f0.md
- [ ] URL/domain branch in the normalizer ("клод точка эй-ай"; the dot must not survive into TTS) → tasks/translation-audit-remainders.md
- [ ] File-scoped terminology glossary carried across segments ("alignment" rendered 3 ways in one file) → tasks/translation-audit-remainders.md
- [ ] `english_echo` stops writing `failed` on deliberately preserved terms → tasks/translation-audit-remainders.md
- [ ] Per-SERIES terminology glossary (`terms.tsv` per playlist into every translate prompt, checked after; drift measured across the 12-video course) → tasks/series-glossary.md
- [ ] Name-safety pass: `pronounce_audit.json` as a pre-batch operator gate + per-run known-names check on `src_en` (Bungie → бунджи self-agrees through verify unflagged; CLAWD→Claude) → tasks/name-safety-pass.md
- [ ] `--no-playlist` on both yt-dlp fetches (a `&list=` URL follows the playlist into one workdir, verified 2026-07-24; the only guard today is queue-contract §1 instruction, not code) → tasks/no-playlist-flag.md
- [ ] Enumeration-head detector (unique head in a run of ≥3 `^(and )?X to …` sentences; 1 fire / 1101 sentences, the true positive, 0 FP, ~15 LOC) → tasks/enumeration-head-detector.md
- [ ] `--repair id,id --seed N`: point re-synth + remux at the GROUP grain → tasks/point-resynth.md
- [ ] Normalize polish: range+unit ("3.5-4.5 GHz" voices the unit as "гхз"), "90х" → "девяностох", "10-20%" keeps a literal dash → tasks/normalize-polish.md
- [ ] Audio-only fetch reused on promotion instead of re-fetching — but first answer WHY a re-fetch changed the transcript (2057→2055 words, DECISIONS 2026-08-06; the two downloads were never compared for format or bytes) → tasks/reuse-audio-on-promotion.md
- [ ] Dub-track polish: `libopus` instead of aac; loudnorm/EQ; singing/music detection → keep original; `--subs-only` fast path → tasks/dub-track-polish.md
- [ ] out/ export name collision fixed (identical `<title> [<id>].mkv` across models overwrites) → tasks/out-name-collision.md
- [ ] Cross-video stage pipelining (translate ∥ synth/verify) if nights get tight → tasks/cross-video-pipelining.md
- [ ] RU analogue for the "four Ds" mnemonic class (Д/Ф/К/Д does not spell "4D" — prompt unpacking or a RU mnemonic) → tasks/ru-mnemonics.md
- [ ] Any-language source → Russian (shelved until the EN queue runs dry; breaks the EN→RU hard constraint) → tasks/any-language-source.md
- [ ] Translation completeness tail: EN↔RU content-word ratio / back-translation on outliers (failure class: DECISIONS 2026-07-18 — the class carries to any route, the measured rate died with the local translator) → tasks/translation-completeness-tail.md
- [ ] Babble duration heuristic (expected-vs-actual unit duration flags garbled synth the ASR round-trip misses) — add BEFORE any narrator-voice or engine change → tasks/babble-heuristic.md

## Deferred — not near-term

- [ ] `n_src` promoted into `flags_actionable` — blocked on measuring its fire rate and precision on a real Sonnet batch first (`entity_loss` at 11 of 12 is the precedent) → tasks/nsrc-promotion.md
- [ ] In-pipeline Anthropic API translate flag — build ONLY if the manual sub-agent seam becomes the bottleneck (approved in principle, DECISIONS 2026-07-18) → tasks/api-translate-flag.md
- [ ] Gender-matched narrator voice (kseniya/xenia/baya per video) — design question + ear pass; shares the F0 pass → tasks/narrator-gender-f0.md
- [ ] Multi-speaker violation detector (ECAPA vs dominant-voice centroid → report flag; full diarization stays out of scope) → tasks/multi-speaker-detector.md
- [ ] UTMOS/MOS verification — only if batch stats prove the duration heuristic insufficient → tasks/utmos-verification.md
- [ ] Unit sim threshold re-tune (base 0.9) — only if production flags misbehave → tasks/sim-threshold-retune.md
- [ ] Streamed mixing in mux — trigger: multi-hour sources (the numpy mix holds a ~2-3 GB transient even after chunked RMS/peak) → tasks/streamed-mixing.md
- [ ] Pre-synthesis bar on the compression factor — reopen only on a batch that actually produces units over the 1.8 bar → tasks/presynthesis-cf-bar.md
