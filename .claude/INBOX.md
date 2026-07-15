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

## General
- [chore] yt-dlp is 90+ days old (warning on run) — `pip install -U yt-dlp`
- [?] translate design forks to settle before coding: prompt format, rolling-context-window mechanics, normalization pass (numbers/units/Latin → Cyrillic words), stripping Qwen `<think>` output
