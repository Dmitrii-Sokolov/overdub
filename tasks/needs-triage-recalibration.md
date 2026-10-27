# Recalibrate `needs_triage`

## Goal + AC

`needs_triage` (`overdub/runreport.py`) answers "does a human have to OPEN this video" again —
it fires on defects a listener can find and act on, not on correct translations or videos with
nothing to listen to. AC: not frozen — fix at pickup.

## Plan

- [x] `num_loss` joins `_ADVISORY_COMPLETENESS` (measured precision 0/25, see Findings).
- [ ] A `no_transcript` degraded run leaves the triage flag and gets its own row in the digest
  and the queue page — "no speech" is not "listen to this".
- [ ] Site `holes_unrecovered` by ear: listen to ~10 unrecovered spans across videos, decide
  whether it needs a minimum span length or stays as is.
- [ ] Re-score the corpus after each step and record the before/after rate in DECISIONS.

## State

Step 1 shipped 2026-10-27 (DECISIONS 2026-10-27): `num_loss` advisory, corpus re-scores
106 → 48 of 198. Next: the `no_transcript` row, then the holes listen.

## Findings

**Measured 2026-10-27** over the 198 `run.json` in `work/` with mtime on or after 2026-09-01
(mtime is a proxy for "written by the current pipeline", 189.3 h of video): `needs_triage` true
on **106 (54%)**. The driver is `num_loss`, the only completeness flag still actionable: 382
units out of 124840 segments, on 79 videos.

`num_loss` sample, 25 random flagged units: **0 real losses.** Every one is the translator doing
the right thing — a number rendered as a Russian word (`1,000 → тысячу`, `10,000 year →
десятитысячелетнюю`, `3D → трёхмерный` ×10), an ASR garble corrected (`04 Mini → o4-mini`,
`Claude 35 Sonic → Claude 3.5 Sonnet`, `18, 24, flop → 10^24 флопс`, `Opus 30 → Opus 3`) or an
idiom (`AI 101 → азы ИИ`). One arguable case: `Hamachi 4 Quattro → Omarchy Quattro`. The same
shape as `entity_loss` at 11 of 12 (DECISIONS 2026-08-01).

Re-scored with `num_loss` advisory: **48 of 198 (24%)** — `holes_unrecovered` 32, degraded 9
(all nine `no_transcript`), other actionable flags 7. Dropping `no_transcript` too leaves ~39
(~20%), dominated by holes.

**`holes_unrecovered` is not rare.** The comment at its use in `runreport.py` calls it "RARE by
construction" off the 2026-08-06 measurement; on this corpus it fires on 32 of 198 videos
(median 1 span per video, max 108). Its precision has never been measured — music or singing
the VAD hears as speech would land here too. Do not demote it blind: it is the one flag that
names a stretch of the MKV with no dub under it.

The INBOX entry of 2026-08-04 (@9fingergames batch: 18 of 26 flagged, 16 of them empty
transcripts, 2 of 10 among videos with speech) is the first sighting of the `no_transcript`
half.
