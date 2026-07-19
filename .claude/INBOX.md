# INBOX

Tags: `[bug] [feature] [chore] [?]` — one line per entry, processed weekly.

## Deferred from transcribe review (2026-07-15)
- [chore] transcribe: calibrate MAX_SEC/MAX_CHARS against Silero eugene comfortable input length during QA
- [feature] transcribe: preserve whisper sub-word spacing ("decision -making") — store leading-space bit, join continuation tokens without a space (cosmetic EN-subtitle fidelity, no dub impact)
- [feature] transcribe: '.'+seg_end pause should be a boundary even before a lowercase next word (id44 "tool. it's") — cap-gate currently eats it
- [feature] transcribe: tolerance band — don't overlong-split sentences within ~10% of MAX_SEC (id16 was 15.3s)
- [bug] transcribe: _ABBREV collides with common words ("no"/"us"/"am") — latent (0 hits here); gate abbrev on an internal dot / capital in the source token (U.S. vs the word "us")
- [feature] transcribe: run-on recovery — soft boundary on Capital-after-lowercase-without-terminator (id47 "framework Whichever", whisper dropped the period)
- [feature] transcribe: words=None segment → regex-split seg.text into pseudo-words with proportional timings (latent; would break the atempo budget if it ever fired on a long segment)
- [chore] persist a sentences.json contract validator as a repo test/util (currently only in session scratchpad)

## Deferred from translate review (2026-07-15)
- [feature] normalize: range+unit interaction — "3.5-4.5 GHz" voices the unit as "гхз" (unit loses its preceding digit after the range expands); and "от 3.5-4.5" doubles "от". Cosmetic, not magnitude
- [feature] normalize: decade suffix "90х"/"2000х" → "девяностых"/"двухтысячных" (currently "девяностох", rough); dedicated pass if worth voicing
- [feature] normalize: "10-20%" keeps a literal dash ("десять-двадцать процентов") — percent pass consumes the 20 before the range pass. Prosody-only, verify strips the hyphen
- [feature] translate: Ollama circuit-breaker — abort after ~3 consecutive api_error instead of burning 4×timeout/sentence for the whole file (batch-scale operability; note failed records aren't retried on resume)
- [bug] translate: refusal regex both directions — "как модель/ии" false-positives on legit RU; RU refusals outside the 4 phrases pass as ok. Tighten self-reference phrasing, broaden RU set
- [?] translate: _parse keeps only line 1 — silently truncates a genuine multi-line continuation (rare with think:false). Consider flagging when discarded lines look like substantive Cyrillic prose
- [bug] translate: torn last jsonl line on power-loss can concat two records; self-heals (unparseable line re-translated) but leaves junk. Prepend "\n" on first append if file doesn't end in one
- [chore] translate: global terminology drift beyond the 4-pair window (AI → "ИИ" vs "искусственный интеллект"); a per-run glossary/term-pin pass if consistency matters

## Deferred from tail review (synthesize/verify/assemble/mux, 2026-07-15)
- [chore] download.py: no `shutil.which` preflight for yt-dlp/ffmpeg (raw WinError 2, no tool name) — mirror the assemble/mux guard; pre-existing, out of the tail diff's scope
- [?] mux: RU dub is the DEFAULT audio track — revisit if the original should stay default; also `libopus` dub is a one-flag quality upgrade over aac (this host has libopus) once local-only portability isn't the constraint
- [feature] assemble: a zero-segment (speech-free) source now raises a clear RuntimeError — if turn-key-on-no-speech is ever wanted, emit an empty dub + subs and let mux still produce an MKV
- [feature] ru.srt cue offsets track the SOURCE `[start,end]`, not the (possibly gap-spilled) dub; sub-onset is synced, offset drifts slightly on long clips — dub-tracking timestamps if it reads wrong
- [chore] verify VRAM: whisper-small loads standalone (Silero is CPU) — the DECISIONS "whisper-small co-resident with TTS" note applied to a reseeding loop that no longer exists; harmless, but the co-residency exception is now moot

## Dead-air review deferrals (2026-07-16)
- [chore] --repair id,id contract: after units the atomic re-render grain is the GROUP — update the backlog item's wording when it lands
- [?] translate keep-length prompt now interacts with L1 stretch: relaxing the length pressure could attack underfill at the root (fuller RU, less stretching) — experiment post-ear-verdict
- [?] mux duck/bed on multi-hour videos: numpy mix holds ~2-3 GB transient even after chunked RMS/peak — streamed mixing if hours-long sources become real

## Ear-check findings (2026-07-16, F5 control run)
- [bug] translate: «причина» ×3 подряд (ids 134-137, ~17:00) — no repetition-avoidance in the rolling context; consider a variation hint in the prompt or the per-run glossary pass
- [?] verify: id101 sim=1.0 but ear-bad (ultra-short garble ASR normalizes away) — real-content proof of the round-trip blind spot; duration heuristic (expected vs actual) is the cheap detector

## F5 engine integration backlog (2026-07-16; narrator + engine decisions → DECISIONS)
- [?] nfe=32 vs 48: RTF 0.27 vs 0.39 — ear-check the quality delta; now doubly relevant: sustained-load synth RTF measured 0.60 vs cold 0.39 (thermal), nfe=32 would claw back ~30%
- [chore] f5: worker keep-alive across videos for batch mode — startup ~30 s × N videos/night adds up (Phase 2 batching decision)
- [chore] before ANY publication of dubs: replace narrator with a rights-clear reference + re-check ESpeech Apache provenance caveat (weights possibly derived from CC-BY-NC base)
- [chore] female PD narrator reference for gender-matching: search the ESpeech community first — HF Space Den4ikAI/ESpeech-TTS discussions + the author's channels/forums (where example.mp3 lives) for shared female refs; fallback: re-scan LibriVox female readers with decent mics (xenium5 rejected: mic; chekhov01: timbre)

## Ideas backlog (2026-07-16 session brainstorm; top-3 first — duplicated in PLAN roadmap/backlog)
- [feature] babble detector in verify: expected-vs-actual duration heuristic + optional local MOS (UTMOS) — ASR round-trip PROVEN blind to babble (sim 0.93 on garbage audio)
- [feature] per-segment NATIVE F5 speed from slot budget, atempo only on the residual — ×1.6 verified at ≤0.022 sim cost; part of F5Engine integration
- [feature] morning triage HTML for batch runs: flagged segments (+2 s context) with audio players + one-command reseed — listen to 1–2% instead of 100%
- [feature] sentence grouping for prosody: adjacent sentences with gap <0.4 s → one synth call (also mitigates the id43 ultra-short class)
- [feature] --repair id,id --seed N: point re-synthesis + remux without a full rerun
- [feature] per-run terminology glossary: pin the first translation of recurring terms (AI → один вариант на весь ролик)
- [feature] singing/music detection (whisper no-speech prob) → keep original audio, don't dub songs
- [chore] loudnorm/EQ pass on the dub track at assemble
- [feature] --subs-only fast path: skip the TTS tail, emit MKV with original audio + both subtitle tracks
- [?] cross-video stage pipelining (translate on GPU ∥ synth/verify of the previous video) — only if overnight batches get time-bound

## 2026-07-17 session
- [?] diagnostic: per-unit measured trailing silence in the placed dub (L1 fill honesty — complements the predicted-vs-actual duration heuristic; born from the "measure, don't predict" discussion)

## Ear findings on the pronounce A/B (2026-07-17, user; pronunciation itself PASSED)
- [?] translate/F5: within-word micro-pause at speed=1.0 (id187 "просто · людьми", no punctuation between) — F5 prosody artifact on a single generation, not slot-fill (speed=1.0) and not the em-dash; verify blind to it (sim 0.99). Reseed would likely fix; low priority, single occurrence noted
- [?] translate: «катфиш-мов» — anglicism calqued instead of translated ("total catfish move"); generic Qwen quality, glossary/prompt class
- [bug] translate/pronounce: OUT-OF-DICT game/company names now hit the pronounce rule fallback and self-agree through verify UNFLAGGED (Bungie→бунджи, Bethesda→бетесда, Terraria→террариа) — silent-loss class, invisible to the 3-video corpus. Only detector: promote pronounce_audit.json to a pre-batch operator gate (fallback-via entries are the candidate WORDS additions)
- [?] transcribe: _ok_cut vetoes only the 16-word _STOP set, so ~9 corpus cuts still end on a bare verb/pronoun ("you have"/"i think") — accepted (dangling verb ≫ fake-pause cut); widening _STOP is a large unmeasured change, revisit only if the ear flags it. _STOP also still lacks through/from/about (bug B's dangling preposition, now moot since branch 1 is gap-gated)

## 2026-07-18 session (docs audit + verdicts)
- [chore] tts: SileroEngine hardcodes v4_ru; v5 (`v5_5_ru`) validated as the no-sample option
  (DECISIONS 2026-07-18) — bump the hub id when next touching the fallback; v5 rejects Latin
  script, so add an out-of-alphabet char filter in the adapter (bakeoff #317 crash class)

## 2026-07-19 session (repair round)
- [?] **terminology drifts ACROSS videos of one course, and nothing measures it** (decided
  2026-07-19: not worth fixing for this batch — the drift already shipped). Measured over the
  12-video AI-Fluency batch: "AI fluency" → ИИ-грамотность ×12 in three videos vs «владение ИИ»
  ×2 in `QbLf2zb3oPc`; Discernment → «критическая оценка» ×13 vs «проницательность» ×1;
  Description split «формулировка» (`Y0KidGr9Z2Y`) vs «описание» (`JpGtOfSgR-c`, `DmgujoZ1mmk`).
  The existing backlog item calls this a per-RUN glossary; the real scope is per-SERIES. Cheap
  version: a `terms.tsv` per playlist, passed into every translate prompt and checked after.
  Note the structural reason it is invisible — each video is translated in isolation, so no stage
  ever sees two videos at once; only a batch-level check can catch it

## 2026-07-19 session (repair round)
- [feature] **make the translate seam report anomalies, not just translate** — CONFIRMED as the
  only detector for semantic garbles with no timing anomaly and no repeated span (DECISIONS
  2026-07-19: `W4Ua6XFfX9w` 19/20, a hallucinated word splitting one sentence). Add to the
  sub-agent prompt: "if a source sentence looks garbled, self-contradictory, truncated, or
  duplicative of its neighbour, translate it as-is AND report the id". Near-zero token cost, and
  it turns a stage we already run into a detection pass. Do NOT let it silently smooth the text —
  that is exactly how PLAN 0e stayed hidden
- [?] the same reading pass surfaced ASR mis-spellings of known names (`CLAWD` → Claude,
  `anthropics` → Anthropic) that `pronounce_audit.json` never gated on. A per-run known-names
  list checked against src_en would catch this class deterministically, before translate
- [feature] **automate the isolated-window repair** — the manual loop proved out on 7 defects
  (DECISIONS 2026-07-19): `rate_implausible`/`dup_adjacent` already localise the defect, so the
  pipeline could re-ASR just that window with `condition_on_previous_text=False`, accept the
  reading only if it is identical under both settings, merge the run, renumber. That is a
  `--repair-asr id,id` stage and it reuses the existing detectors as the trigger
- [?] the stability check (same reading under cond=True and cond=False) is doing real work as an
  accept/reject gate — worth keeping as the acceptance criterion in any automation, and possibly
  worth back-porting into the existing transcribe guard, which currently accepts a retry on a
  floor-ratio HALVING rather than on agreement
- [chore] `words.json` is not updated by a sentences.json repair — harmless today (only
  `asr.floor_ratio` reads it, and it SHOULD keep showing the original collapse), but any future
  consumer of words.json must know it can disagree with sentences.json after a repair

## 2026-07-19 session (item 0c/0d, multi-agent pass)
- [feature] completeness: **containment beats ratio for repetition defects — the single highest-value
  follow-up from this pass.** `dup_adjacent`'s symmetric `SequenceMatcher.ratio() > 0.80` catches only
  the verbatim echo (1 of the batch's 3 repetition defects). Longest-common-substring containment
  (`lcs / len(shorter)`) separates cleanly over all 13 videos: 1.0000 ytEN 7/8 (real), 0.9677
  x7DfiXqSEdM 298/299 (real, currently a documented miss), 0.9167 2YCaBqP8muw 16/17 (real, PLAN 0f),
  then 0.7188 for a benign rephrase. A 0.85 cutoff catches all three with zero FP in a 0.20-wide empty
  band. Caveat the scan itself raised: 3 true positives is a thin basis — treat 0.85 as a hypothesis,
  not a measured constant, same distinction the `_DUP_MIN_LEN` comment already draws. Also softens the
  docstring's "unreachable at any usable threshold", which is true only for the symmetric metric
- [feature] transcribe/verify: **near-zero-duration detector — catches the echo class with no text
  comparison and no threshold tuning.** ytEN_iAk09c id8 packs 56 chars into 0.32 s (25 words/s);
  `words.json` shows 8 consecutive words each 0.02 s wide — the canonical fingerprint of a decoder
  repetition loop. A words-per-second bound (>8 wps, or chars/s z-score) is orthogonal to string
  similarity and would also catch NON-adjacent loops, which `dup_adjacent` structurally cannot see
- [feature] completeness: enumeration-head detector for the PLAN 0b class — in a run of ≥3 adjacent
  sentences matching `^(?:and\s+)?([A-Za-z]+)\s+to\s+\w+`, the captured head must be unique. Measured
  on the real batch: exactly one flag across 13 videos / 1101 sentences, and it is the true positive
  (`W4Ua6XFfX9w` ids 45/47, duplicated head "delegation"). Zero FPs. ~15 LOC, no model
- [?] translate seam: ask the translator sub-agent to flag enumerations whose items repeat or
  contradict an earlier definition in its rolling context — ~0 extra tokens, and it is the only
  proposed detector that catches BOTH the duplicated head at id47 AND the bogus "Description to
  control AI" at id46 that no string metric can see
- [bug] a good translator MASKS ASR damage (PLAN 0e): Sonnet repaired garbled source into plausible
  Russian, hiding it from every downstream detector. Argues for detecting on `src_en` BEFORE
  translate, not after — the earlier the seam, the less repair has happened

## 2026-07-18 session (Gemma migration + item-0 close)
- [?] verify: translation COMPLETENESS unmeasured — the ASR round-trip proves TTS↔text_ru, not
  text_ru↔EN. Gemma's tightness drops a word unflagged (Dmgujo id1: 3 of 4 adverbs). Now the top
  verify gap → PLAN roadmap 1 (EN/RU content-word ratio or back-translation spot-check)
- [bug] transcribe: RyvXxApfHkk id12 — whisper emitted garbage with CJK chars + U+FFFD ("Theisk
  models… 酸petto"); both Qwen and Gemma dutifully "translated" it and verify passed it (round-trip
  blind to confident garbage). Real corpus case for the babble/duration heuristic (roadmap 3)
- [chore] mux/export: out/ name collision — Qwen and Gemma runs export identical "<title> [<id>].mkv"
  and silently overwrite each other; authoritative per-model MKVs live in the work dirs. Namespace
  exports per work_root/model (backlog)
- [chore] work-exp/gemma-ab/gemma.toml still sets the removed ollama_system_role/ollama_send_think
  keys → harmless "[config] unknown key ignored" on rerun; drop them if that dir is reused
