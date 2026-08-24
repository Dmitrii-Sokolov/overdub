# Narrator's grammatical gender → the translate prompt

## Goal + AC

Russian marks gender on 1st-person PAST verbs, English does not, and the transcript carries no
name — so every first-person past clause is a silent coin flip today. A cheap F0 pass gives the
translator a `feminine|masculine|unknown` field (user, 2026-07-25).
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] Median F0 over voiced frames of `source.wav` (one cheap pass, no model; single-speaker is
  already assumed), written beside the transcript.
- [ ] Thread into BOTH routes: the route-B sub-agent prompt and `SYSTEM` in
  `stages/translate.py`.
- [ ] An operator override belongs next to it (per-channel data).

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. Getting it wrong is
audible immediately and costs only a re-synth of the affected units — which is also why it never
blocks a batch.

## Findings

Measured on `aVwxzDHniEw` (Freya Holmér): the sub-agent used impersonal constructions where they
read naturally and defaulted to masculine in 7 places (ids 178/181/190-192/195-196). Not a
translator defect — the information was not in its input.

**Three rules keep it honest:** F0 measures VOCAL TYPE, not a person's gender, so the field is
about the grammatical gender of self-reference; a middle band (~155-185 Hz) resolves to
`unknown`, never to a guess; `unknown` means "prefer impersonal constructions", which is a real
instruction, not a default to masculine.

**Deferred sibling — gender-matched narrator voice.** No longer blocked on sourcing a voice
(2026-07-27): the female voices ship with the model (kseniya = backup, xenia, baya), so matching
is `tts_voice` per video. What is left is a design question and an ear pass: whether the
narrator's voice should follow the speaker's median F0 at all, and whether kseniya holds up over
a full video. Shares the F0 pass with the main task — measure once, use twice.
