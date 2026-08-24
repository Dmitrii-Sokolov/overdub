# host_guard decides on the wrong instrument — move it to the SM clock

## Goal + AC

`scripts/host_guard.py` gates on the SM CLOCK (idle-clocked is idle whatever the percentage),
keeps memory as the second signal, and demotes `utilization.gpu` to something printed rather
than decided on. The measurement and the diagnosis: DECISIONS 2026-08-07 (`utilization.gpu` is
not a load signal). AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] Gate on clock; keep the memory bar; print (not decide on) utilization.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration.

## Findings

Today it gates on `utilization.gpu` (bar 40) and memory (bar 2500 MiB), and `utilization.gpu`
measures the fraction of sample windows containing any kernel at all, not load — desktop
compositing keeps it in the tens of percent on a card sitting at its idle clock. It printed
`35% util, 815 MiB, 57 C, 210 MHz — idle` and that ONE line misled in both directions at once:
the verdict said idle, the percentage said busy, and only the 210 MHz was true. Measured the
same session (2026-08-07): **210 MHz / 13.5 W at rest vs 2445 MHz / 45 W under load** — an order
of magnitude, against a utilisation figure that cannot separate the two.

**Do NOT just lower `BUSY_UTIL_PCT`**: that keeps the wrong instrument and would start refusing
to run on a normally composited desktop, which is the hardware this project targets.
