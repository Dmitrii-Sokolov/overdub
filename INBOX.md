# INBOX

Tags: `[bug] [feature] [chore] [?]` — one line per entry, processed weekly.

<!-- processed 2026-07-19: 54 entries → PLAN (roadmap 3/6, backlog, deferred) / already in DECISIONS / deleted -->
<!-- processed 2026-07-20: 6 entries → PLAN roadmap 4 (the two renderer-divergence bugs merged into
     one item; they were one root cause) + PLAN roadmap 5 (repair destroys the anomaly worklist) +
     PLAN deferred (measure n_src precision first) / fixed in place (repair_window_min_sec docs) /
     DECISIONS 2026-07-20 (exit 0 on all-rejected) -->
<!-- processed 2026-07-22: both queue-page entries BUILT the same day —
     neither needed a roadmap slot: the thumb was a missing yt-dlp flag plus a glob one character
     too narrow, and the «о чём» was a fallback over prose already on disk. -->
<!-- processed 2026-07-24: the STACK.md drift entry FIXED IN PLACE, no roadmap slot — it was pure
     doc-vs-code skew in the Stage-1 skeleton. verify compute_type int8→float16 corrected (code
     ships float16 both roles since the asr role-split), an int8-is-24%-slower gotcha added, and
     the cond skeleton flipped False→True with a dedicated gotcha carrying the _guard mechanic;
     STACK is now internally consistent on both cond and int8. Code was already correct — the
     document was the only thing wrong. -->
<!-- processed 2026-07-25: 17 entries → 0. Route: 4 to PLAN (subtitle drift → item 1(c); src!=ok
     seeds, Sonnet-limit accounting, work/ cleanup → "Next after the blocker"); 4 already in PLAN
     when written and deleted as echo (voice post-processing = item 3, stress audit = item 4,
     open-class rules = item 2, 166 truncated = the rebuild item); 2 merged into existing PLAN items
     (the aVwxzDHniEw#67 broken slot is the same root as 166 truncated; neg_loss keeps its own entry
     as a decision the user owes DECISIONS); 4 were already shipped on 2026-07-25 the
     same day and needed no slot (Silero 8.1×, Step 1b dry-run — since APPLIED to both videos, the
     silero-breaks verify gap, git LF on cmudict — FIXED IN PLACE via .gitattributes); 3 deleted as
     dead with the transcribe axis (beam-probe cell naming, asr_probe git-HEAD mode, asr_key
     back-fill — a documented limitation, not a bug). Two number-groups that were being quoted
     interchangeably are now fenced in PLAN under "Numbers to re-measure". -->
<!-- processed 2026-10-27: 28 entries → 0. New BACKLOG items (8, task file each): silent-dub
     guard, needs_triage recalibration (the no-speech padding entry, opened as a task on the
     user's verdict that translations read correct; num_loss measured 0/25 the same day), drain
     deadline, repair-asr language + empty
     transcript (2 entries), video_id URL shapes, route-E diagnostics (4 entries), route-E
     triggered routing, §-citation test (the inventory entry narrowed — 3 of its 4 instances died
     with route C and PLAN.md). Findings into existing tasks (11 entries): transcribe-wall-variance
     (both Parakeet-determinism entries), chunk-threshold-on-chars (stall + 64k cap),
     record-sonnet-cost (both token datapoints), slot-fit (slot_silence overstatement + Terra
     Nil), cmudict-transliteration, pipeline-batch-latency (mux), multi-speaker-detector (panel
     anomaly rate; file created to hold it). Fixed in place: Tee-Object →
     redirect line in the route-B skill step 3. Deleted (5): scout_report embed size and the
     summary.md bypass (dead with route C / the summarizer), route-B empty-transcript gate and
     wasted no-speech agents (closed 2026-08-06), unlisted Vimeo URLs (outside YouTube→RU). -->
- [feature] 2026-10-27 Multi-speaker dubbing spec drafted with the user → tasks/multi-speaker-dubbing.md. Triage owes: a DECISIONS entry lifting the founding "single-speaker, no diarization" hard constraint (CLAUDE.md, AGENTS.md, README Constraints all state it); a BACKLOG line; `narrator-gender-f0.md` absorbed (F0 per speaker feeds both voice and translator); fate of `multi-speaker-detector.md` (its ECAPA flag is subsumed by diarization).
