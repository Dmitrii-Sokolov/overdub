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

## General
- [chore] yt-dlp is 90+ days old (warning on run) — `pip install -U yt-dlp`
