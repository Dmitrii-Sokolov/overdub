# Name list at ASR — the proper-noun class

## Goal + AC

Proper nouns survive transcription: a name list biases the SOURCE ASR pass so that "Claude" does
not ship as "Cloud" in EN subs, RU subs and the dub at once. First in the value order because it
is the only known defect that survives into a finished MKV and cannot be reached from any later
stage. AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] Decide where the names come from (video title + channel are free and on disk; a per-queue
  list is an operator step) — open sub-question before any code.
- [ ] Look at NeMo's own context biasing first (a `biasing_cfg` rides on every `Hypothesis`) —
  unmeasured on this corpus; `initial_prompt` / `hotwords` are faster-whisper arguments and do
  not exist on Parakeet.
- [ ] Adopt only off a measurement on the six fixture videos (`docs/repair-fixture.md`), never
  because it reads well — biasing an ASR toward a word list also changes decoding elsewhere in
  the transcript, which is what `scripts/asr_probe.py` measures (whisper side).

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. The engine changed
under this item on 2026-08-06 and the defect did not — the fix is still a name list, not an
engine choice; the mechanism to build it on changed (NeMo biasing, not hotwords).

## Findings

The SOURCE pass is `stages/transcribe.transcribe_words`; `asr.py` calls the same API for the
verify round-trip, and a name list must NOT reach that one — a judge handed the answer stops
being one, and the similarity score would rise on exactly the words it is there to check. The
verify round-trip still runs on whisper after the engine switch, so this warning holds unchanged.

Measured 2026-07-26: `vLIDHi-1PVU` ("Designing Claude Code") came back with **16 × "Cloud" and
0 × "Claude"** at large-v3/fp16/beam 5 — so DECISIONS 2026-07-20's proper-noun class is not a
beam-1-only artifact. Fixing it at the translate seam is possible but partial and expensive: it
needs a `src` flag on every normalised record, it makes 27 of 28 `entity_loss` offenders false,
and it cannot reach `en.srt` at all (not re-timed by design — the rule and its reason are in
`assemble._ru_cue_rows`'s docstring, beside the RU path that IS re-timed — one MKV shipped with
15 × "Cloud" in EN subs against 35 × "Claude" in RU). A name list closes all three surfaces at
once.

**Conditions, non-negotiable:** it changes source text, so it goes into `asr_key`; adoption is
by fixture measurement only. Rationale: DECISIONS 2026-07-26.

**Parakeet (2026-08-06):** produced 6 × `Cloud` against 30 × `Claude` in `2YCaBqP8muw`, where
whisper had 0 — but in `RyvXxApfHkk` it was the only source of the three (whisper, the human
transcript, itself) to write `Claude` correctly all four times. Neither engine owns this class.
