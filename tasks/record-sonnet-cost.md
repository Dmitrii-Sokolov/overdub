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
migration; the two INBOX datapoints were routed into Findings at triage 2026-10-27.

## Findings

The old "the scarce resource now that disk is not" framing is **retracted**. The user's operating
estimate (2026-08-06) is ~1% of the weekly limit per 2-5 h of translated audio, i.e. tens of
hours run without approaching a limit — an ESTIMATE with a named source, not a measurement, and
it does not become one by being quoted again. Route B spends one sub-agent per video (the
translator), route E one per CHUNK. The only route that
ever had a recorded figure (the digest route, ~200k per video) was deleted with the route,
so that number describes nothing that still exists.

**Two measured datapoints, both 2026-08-04, both from the era when route B still spawned a
summarizer per video** (two agents per video — the per-video means do not carry over to today's
one-agent route). @9fingergames: 3,254,362 tokens over 52 agents / 26 videos (≈63k per agent),
but 16 of 26 transcripts were empty and their agents trivial. 5-video WL batch: 4,344,370 over 13
agents (≈334k per agent, ≈869k per video), all five at 1221-2829 sentences; ~1.1M of it bought
nothing — the two stalled videos were paid twice and delivered no `translation.json`. Transcript
LENGTH is the variable both means hide. Neither is comparable to the ~5.6k/video orchestrator-side
projection — different grain, different pocket.
