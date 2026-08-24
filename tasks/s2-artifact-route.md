# S2 artifact route — workable but not settled

## Goal + AC

Decide how summarizer sub-agents deliver their two artifacts, given the harness blocks their
`Write` tool on `*summary*.md` paths. Until decided, an occasional classifier stop is a respawn,
not a reason to reinstate any instruction about what is blocked.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] Option (a): "sub-agent returns, caller writes" — fully compliant; run 6's recovery ran it
  end to end. Cost: the caller GENERATES ~3-4k chars per video at ~8.5 s/1000 chars, so six
  videos add ~200 s to a 200-600 s wave. Worth measuring against
  `work-exp/wave-run{4,5}-2026-07-21/` rather than assuming.
- [ ] Option (b): structured return via a schema — known failure mode: long string fields abort
  the run after data is on disk (`~/.claude/knowledge/claude-code/agent-orchestration.md`) and
  `paragraph` runs to 1500 chars. Do not reach for it without re-reading that note.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. First sample outside
route C (2026-07-28): route B's four summarizers wrote `summary.md` via the PowerShell path 4/4
with no refusal and no end-run — weak evidence that stating the mechanism is enough and the
~200 s/6 videos in (a) may never have to be paid. Four agents is a sample, not a rate. Related
INBOX entry (2026-08-01: one refusal in 19 — "fix the write path, not the wording") routes here
at triage. Note route B dropped its summarizer 2026-08-20 (DECISIONS), so the surface is route C
plus the shared prompt in `scout-summarize.js`.
