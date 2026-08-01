# INBOX

Tags: `[bug] [feature] [chore] [?]` — one line per entry, processed weekly.

<!-- processed 2026-07-19: 54 entries → PLAN (roadmap 3/6, backlog, deferred) / already in DECISIONS / deleted -->
<!-- processed 2026-07-20: 6 entries → PLAN roadmap 4 (the two renderer-divergence bugs merged into
     one item; they were one root cause) + PLAN roadmap 5 (repair destroys the anomaly worklist) +
     PLAN deferred (measure n_src precision first) / fixed in place (repair_window_min_sec docs) /
     DECISIONS 2026-07-20 (exit 0 on all-rejected) -->
<!-- processed 2026-07-22: both queue-page entries BUILT the same day (CHANGELOG 2026-07-22) —
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
     as a decision the user owes DECISIONS); 4 were already recorded in CHANGELOG 2026-07-25 the
     same day and needed no slot (Silero 8.1×, Step 1b dry-run — since APPLIED to both videos, the
     silero-breaks verify gap, git LF on cmudict — FIXED IN PLACE via .gitattributes); 3 deleted as
     dead with the transcribe axis (beam-probe cell naming, asr_probe git-HEAD mode, asr_key
     back-fill — a documented limitation, not a bug). Two number-groups that were being quoted
     interchangeably are now fenced in PLAN under "Numbers to re-measure". -->

- [bug] `scout_report.py` embeds audio for ADVISORY units too, not just hard flags — the 19-video batch of 2026-08-01 produced a 2012 MB `work/scout-report.html` (1186 units embedded against 74 hard flags) that no browser opens. The page is the only surface for actually LISTENING to a flagged unit, so at this size that capability is gone, silently: the script exits 0 and prints a normal-looking line. Needs an embed threshold keyed on the hard flags. The advisory bulk was almost entirely `entity_loss` (1179 flagged sentences vs 1186 units embedded), and that detector was DELETED the same day (DECISIONS 2026-08-01) — so a fresh batch will not reproduce the 2 GB page. This entry stays open anyway, for two reasons: the threshold is still wrong (the remaining advisory detectors — `dup_adjacent`, `rate_implausible`, `neg_loss`, `length_short` — accounted for ~171 units on this batch and nothing stops that growing), and every workdir transcribed before 2026-08-01 still carries `entity_loss` flags, so re-running the page over old `work/` dirs still blows up. Do not close this by re-running the script on a new batch and observing a small file: that measures the deletion, not the threshold.
- [bug] `.claude/workflows/translate-batch.js` instructs sub-agents to write `summary.md` via a PowerShell shell call to route around a harness-level block on subagent `Write` to `*summary*.md` paths. A safety classifier refused exactly one of 19 summarizer agents on 2026-08-01 (`CytZvXYLojA`, no summary written) — so the bypass is in the prompt permanently while the refusal is nondeterministic, i.e. it will keep dropping a random video per batch. Fix the write path, not the wording. Same prompt is shared with `scout-summarize.js` (route C) — check both.
- [bug] `slot_silence_sec` and `fill_median` READ AS DUB DEFECTS but are dominated by the SOURCE speaker's pacing — they will keep raising false alarms until the report separates the two. Both are measured against the SLOT (`[start_i, start_{i+1})` = the unit's span PLUS the following inter-unit gap), so every pause the original speaker left is counted as dub silence. `in_span_silence_sec` is not a fix either: its span is the UNIT's, and a unit groups several sentences, so inter-sentence pauses still land inside it. Measured at the only grain that isolates the dub — sum of per-SENTENCE spans vs sum of per-UNIT `placed_sec`, deduped by `group_id` — on the 19-video batch of 2026-08-01: source speech 1348.8m, dub voiced 1397.1m, summed real hole 7.5m (0.6%). **15 of 19 videos voice MORE time than the source was speaking, i.e. zero hole.** `slot_silence` reported 87.8m, overstating the real hole by 11.7×. Ranking by it is wrong too: `_xbGK_5wlfs` looked 3rd-worst at 9.1m and has NO hole at all. Suggested fix: report the sentence-grain figure as the headline and demote slot_silence to a source-pacing stat, or drop it. Scratch measurement scripts existed only in the session scratchpad — re-derive from `report.json` (`segments[].placed_sec`, `group_id`) + `translation.json` spans.
- [?] `s30pjYV8aBM` (Terra Nil) is the ONE video on the 2026-08-01 batch with a real under-fill: 44.5m of source speech against 38.1m voiced = 14.4% hole (6.4m). Next worst is `9j3I3owY8a8` at 1.6%, then nothing above 0.2%. The hole is DIFFUSE, not a few broken units — the worst half of its 225 units hold 93% of it, and a typical offender is a 2-sentence unit with a ~17s span and ~10s of speech. Worth one listen to decide whether 14% reads as natural pacing (the bed plays under it) or as dead air; if it is audible, this is the only evidence so far that "Slot fit" (PLAN) has a real target. Do NOT generalise it to the batch — that was the mistake the entry above documents.
- [chore] Long `--batch` runs must redirect stdout to a file (`> work/x.log 2>&1`), never `Tee-Object`: demucs progress bars flood the background-task stream and two step-3 runs on 2026-08-01 were killed mid-`separate` (after 95 min and after 2.5 min) until the redirect was used, after which the identical command exited 0. Demucs itself was cleared by direct re-run (exit 0 on the video both kills landed on) — the pipeline was not at fault. Worth a line in the route-B skill's step 3.
