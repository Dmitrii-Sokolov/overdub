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
