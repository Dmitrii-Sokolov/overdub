# Input prosody — punctuation and SSML

## Goal + AC

The dub stops reading flat: the translator's punctuation quality and `<p>`/`<s>`/`<prosody>`
markup give Silero pauses and a contour reset. The cheapest unpulled lever on the list, and the
one that answers "the dub is fine but it reads flat". AC: not frozen — task imported from
PLAN.md (2026-08-24), fix AC at pickup; judged by ear, like everything in this half of the list.

## Plan

- [ ] Punctuation quality first — `docs/russian-tts-guide.md` attributes ~70% of prosody quality
  to the INPUT and names flat ASR+MT punctuation as the main cause of monotony, exactly our input
  shape. This is not a markup question at all — it is what the translator writes.
- [ ] `<p>`/`<s>` (and possibly `<prosody>`): Silero accepts SSML
  (`<speak> <p> <s> <prosody> <break>`) while the adapter sends plain `text=`; `<p>`/`<s>` alone
  give pauses and a contour reset.
- [ ] Prove markup does not trip the Latin-deletion contract: `text_tts` is Cyrillic-by-contract
  because Silero DELETES Latin script.
- [ ] Strip tags on the verify comparison side exactly as stress marks already are (verify
  compares against `text_tts`).

## State

Not started. Promoted from PLAN Backlog 2026-07-27; imported from PLAN.md at the 2026-08-24
agent-docs migration.

## Findings

**`<break>` is NOT part of this task — it was built, measured and REJECTED by ear (DECISIONS
2026-07-25), and it stays in the code at `silero_ssml_breaks = False`.** Recorded here because
the mechanism is still wired and reads as available: it was the right mechanism on the wrong
problem, the holes being made by ASSEMBLY rather than by swallowed pauses. The forensics that
killed it are the comment at that config key (`overdub/config.py`, the ONLY copy); do not
re-derive them here. It comes back onto the list only if units with genuinely long INTERNAL
pauses start appearing — the condition it was the right mechanism for and never met.
