# Route E spends cleaner agents only where a sentence needs one

## Goal + AC

Fewer cleaner spawns per video at no measurable quality loss, decided by an A/B on one video
before the join contract changes. AC: not frozen — fix at pickup.

## Plan

- [ ] A/B one video: route only triggered sentences (stoplist hit, adjacent dup, Latin on ru)
  to agents plus a per-video glossary agent, against the shipped full fan-out.

## State

Not started. Routed from INBOX at triage 2026-10-27.

## Findings

**Measured 2026-09-04** over every `clean.json` on disk (13 videos, 10078 sentences, `src` vs
`text`): 54.5% byte-identical, 4.5% punctuation/case only, 30.7% pure deletion, 2.1% emptied,
8.1% substitution. "Precision" below means "agrees with Sonnet" — there is no human reference
for route E.

Stoplist precision is BIMODAL: um/uh 100%, ну 99%, короче 99%, собственно 100%, i mean 98%,
как бы 93%, в общем 93%, типа 92%, you know 92% — together 2505 of 4300 stoplist deletions
(58%); вот 59%, like 60%, right 41%, понимаете 41%, okay 39%, kind of 36%, да 35% are context
reads; so 8%, just 5%, actually 0%, то есть 0%, просто 2%, значит 1%, там 12% are correctly
KEPT. Adjacent-dup stutters are only 7% of non-filler deletions — false starts are not
regex-shaped. 41% of substituted tokens are a mapping repeated ≥2× inside one video
(fermulab→fermilab ×4, динамик→dynamic ×10, бачинг→batching ×9, все→всё ×21) — glossary-shaped.

42% of sentences carry NO trigger, and the agent still changed 15.2% of those (649), mostly
commas and name spellings — the miss rate of any "skip untriggered sentences" routing.

Consequences: a deterministic pre-pass on the ≥92% words cuts ZERO spawns (every id must come
back, chunks are cut by count). The spawn-cutting lever is triggered-only routing (~40% fewer
chunks) plus a glossary agent, at the price of the 649. The measurement scripts were
scratchpad-only; re-derive from `clean.json` `src`/`text`.
