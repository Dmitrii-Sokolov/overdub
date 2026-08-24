# Stress audit of the dictionary

## Goal + AC

The stress dictionary content pass: mark stresses where Silero's own guess is wrong, using
`stress_index`/`apply_stress`; English stress wins on disagreement (user call). **Gated on
tasks/cmudict-transliteration.md** — of the top 60 invented tokens only 10 disagree with
Silero's own stress and half of those would mark an already-broken transliteration
(`execute → +эксекют`), so accenting first entrenches the defect.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] Land tasks/cmudict-transliteration.md first.
- [ ] Ear pass over the candidates — 34 of 60 automatic stresses were already correct, where a
  mark is pure noise in the data.

## State

Not started; blocked on the CMUdict task. Imported from PLAN.md at the 2026-08-24 agent-docs
migration. The mechanism shipped 2026-07-25 (marks honoured, verify strips them, CMUdict
in-repo); this is the content pass.
