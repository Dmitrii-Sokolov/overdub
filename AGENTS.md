# overdub — agent instructions

This file holds no rules of its own. The instructions for this repository live in two files, and
both bind every agent that works here, whatever tool runs it — not only Claude:

- `CLAUDE.md` (repo root) — the project instructions. Read it first, in full.
- `overdub/CLAUDE.md` — module-local facts and constraints of the pipeline package.

The runbooks for each route live in `.claude/skills/<name>/SKILL.md`, and the fan-out scripts they
call in `.claude/workflows/`.

Nothing is copied here on purpose: a second copy of those rules would drift from the first.
