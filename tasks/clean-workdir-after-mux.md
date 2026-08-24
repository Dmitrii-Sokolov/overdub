# Clean work/<id>/ after a successful mux

## Goal + AC

Hygiene, NOT a queue-size lever: after a successful mux, delete BINARIES only (`source.mkv`,
`source.wav`, `source_bed.wav`, `dub_ru.wav`, `segments/`); json/md are pennies. Transcript,
translation and summary survive; the cost is re-synthesis of everything downstream. `out/` holds
a second hardlink so the result survives on its own.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] **Blocker inside it:** mux's input must move `source.mkv` → `output.mkv`, or a re-mux
  needs a re-download.
- [ ] Keep `mux.gained_tracks` UPGRADE-ONLY semantics intact — its docstring depends on this
  cleanup existing (a vanished track must not trigger a re-mux that strips it).

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. Related detector work
(silent-dub gate before mux) lives in INBOX (2026-08-04 entry, `work/_silent-dub-2026-08-04/`
fixture) — triage may merge it here or keep it separate.
