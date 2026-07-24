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

## 2026-07-22
- [chore] `work-exp/beam-probe/` cells predate `asr_probe.py`'s naming — `--variant beam1` re-measures instead of reusing the 24 existing cells
- [feature] `asr_probe.py` has no "compare against a git HEAD worktree" mode; the technique that settled the drift question lives only in a session scratchpad now
- [?] `asr_key` is never back-filled: a workdir whose transcribe never re-runs stays unstamped forever, so the warning can only ever cover post-2026-07-22 transcripts
