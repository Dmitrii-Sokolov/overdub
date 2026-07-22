# INBOX

Tags: `[bug] [feature] [chore] [?]` — one line per entry, processed weekly.

<!-- processed 2026-07-19: 54 entries → PLAN (roadmap 3/6, backlog, deferred) / already in DECISIONS / deleted -->
<!-- processed 2026-07-20: 6 entries → PLAN roadmap 4 (the two renderer-divergence bugs merged into
     one item; they were one root cause) + PLAN roadmap 5 (repair destroys the anomaly worklist) +
     PLAN deferred (measure n_src precision first) / fixed in place (repair_window_min_sec docs) /
     DECISIONS 2026-07-20 (exit 0 on all-rejected) -->

## 2026-07-22
- [feature] queue page: thumb for dubbed-without-scout videos — full download saves no thumb.jpg; teach the dub download to write one (yt-dlp flag + rescale) or backfill via build_scout._ensure_thumb
- [feature] queue page: «о чём» for dubbed-without-scout rows — derive a one-liner from summary.md first sentence? (page is network-free by contract, data exists on disk)
