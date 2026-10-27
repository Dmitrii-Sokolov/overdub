# `--repair-asr` reads the transcript's language and treats an empty transcript as nothing to do

## Goal + AC

`--repair-asr` re-reads a window in the language of the TRANSCRIPT, never `cfg.source_lang`, and
a video with an empty transcript is a no-op row, not a failure. Both matter only on
`asr_engine = "whisper"` (the mode refuses on Parakeet). AC: not frozen — fix at pickup.

## Plan

- [ ] Take the language from the transcript (`build_clean.detect_lang` already does it from
  `sentences.json`, per video) or have it handed in explicitly.
- [ ] An empty `sentences.json` prints the same kind of row as `no defect windows` and does not
  move the step's exit code.

## State

Not started. Routed from INBOX at triage 2026-10-27 (two entries, same mode).

## Findings

**Language.** `repair.py` passes `language=ctx.cfg.source_lang` (`"en"` by hard constraint) to
every window it re-reads. Harmless while every route was EN→RU; route E became EN-or-RU on
2026-08-14, so a Russian queue on whisper would decode Russian audio as English and splice it in
under an accept gate that compares two equally wrong readings. Not observed in the wild. The
`overdub-clean` skill (E2) says "do not run whisper repair over a Russian queue" — prose is the
weaker half of the fix. Three call sites read `cfg.source_lang` for three different reasons and
only two of them mean it; `--transcribe-file` solved the same problem with `language=None`.

**Empty transcript.** `repair.load_sentences` raises per video on an empty transcript and drags
the step's exit code to 1 — 16 of 26 on 2026-08-04 (music-only trailers). The cause is
deterministic, so the summary's advice "re-run the same command to retry failed videos" is wrong
by construction, and the exit code is unusable as a gate on any queue containing a trailer.
