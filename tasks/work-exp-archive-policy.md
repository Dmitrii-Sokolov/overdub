# work-exp/ — decide what is a consumable and what is an archive

## Goal + AC

Every directory under `work-exp/` is classified as consumable (may be deleted/overwritten) or
archive (protected), BEFORE the next disk cleanup makes that call by accident. AC: a written
policy (this file or `overdub/CLAUDE.md`) plus whatever copying/renaming it implies, executed.

## Plan

- [ ] Inventory what survives today (2026-08-24 state: only the 2026-07-2x cells and the
  `parakeet/fixture/` re-fetch remain).
- [ ] Classify; protect the route-C baselines.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration.

## Findings

**`work-exp/` is not an archive and has already lost data once.** `context-earcheck/`,
`stats-batch/` and the translator A/B cells NO LONGER EXIST: those workdirs are gone, the
published A/B report artifact (508 sentences) is the only surviving record of that comparison,
and the stats-batch URL list is unrecoverable.

The route-C baselines under `work-exp/wave-*-2026-07-21/` are live — **a re-run of that 6-video
queue overwrites the artifacts, so copy the six `scout.json` before repeating it.**

The six repair-fixture `source.wav` were also lost from `work/` by a disk cleanup and re-fetched
into `work-exp/parakeet/fixture/` (`docs/repair-fixture.md` carries the details) — the precedent
this task exists to stop repeating.
