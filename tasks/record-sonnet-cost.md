# Record per-video sub-agent token cost

## Goal + AC

Some route artifact (digest, `run.json`, or a batch-level record) carries the Sonnet sub-agent
token cost per video, so the price stops living only in chat messages. **An observability gap,
NOT a ceiling** (re-framed 2026-08-06). AC: not frozen — task imported from PLAN.md
(2026-08-24), fix AC at pickup.

## Plan

- [ ] Persist the `Workflow` task-notification `usage` block (`subagent_tokens`) somewhere —
  same gap and likely same fix as tasks/persist-batch-capacity.md.
- [ ] Key the persisted figure per 1000 sentences, not per video — transcript length is the
  variable the per-video means hide (see Findings).

## State

Not started; nothing is gated on it. Imported from PLAN.md at the 2026-08-24 agent-docs
migration. Two measured datapoints exist in INBOX (2026-08-04: ≈63k/agent on a mostly-empty
queue vs ≈334k/agent on a long-transcript queue — 5.3× apart); triage routes them here.

## Findings

The old "the scarce resource now that disk is not" framing is **retracted**. The user's operating
estimate (2026-08-06) is ~1% of the weekly limit per 2-5 h of translated audio, i.e. tens of
hours run without approaching a limit — an ESTIMATE with a named source, not a measurement, and
it does not become one by being quoted again. Route B spends sub-agents per video (translator;
the summarizer was dropped 2026-08-20), route C one, route E one per CHUNK. The only route that
ever had a recorded figure (route D, ~200k per video, 2026-07-30) was deleted with the route on
2026-08-03, so that number describes nothing that still exists.
