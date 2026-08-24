# Feed `src != ok` from translation.json into repair seeds

## Goal + AC

`repair.seed_ids_from_detectors` also reads the translator's `src` verdicts, catching the one
defect class NO detector sees by construction: a clause repeated INSIDE one sentence.
User-selected as the next step 2026-07-25. AC: not frozen — task imported from PLAN.md
(2026-08-24), fix AC at pickup.

## Plan

- [ ] Add `src != ok` as an ADDITIONAL seed source when `translation.json` already exists.
- [ ] Respect the ordering constraint below — it shapes the whole design.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. Note the mode this
feeds (`--repair-asr`) is whisper-only since 2026-08-06, so the seed only matters on the
fallback engine until the Parakeet-determinism question resolves (INBOX carries it).

## Findings

Measured on `8zJlKmgMT44` (audible repeats at 3:22 and 9:53): `#44` repeats "and the subtle ways
that they can affect our behavior" at a normal 18 ch/s, `#105` repeats "we had to move stuff
around…" plus a stump in a 1.50 s slot. `dup_adjacent` compares NEIGHBOURS, `rate_implausible`
needs a timing anomaly — both blind. Only the translator's reading pass caught them
(`src=garbled`), and that signal is printed and dies.

**Constraint:** seeds are read BEFORE translation (`auto --batch` on a fresh transcript is the
normal case), so src-seeds can only ever be an ADDITIONAL source when `translation.json` already
exists.
