# INBOX

Tags: `[bug] [feature] [chore] [?]` — one line per entry, processed weekly.

<!-- processed 2026-07-19: 54 entries → PLAN (roadmap 3/6, backlog, deferred) / already in DECISIONS / deleted -->

- `[bug]` triage_html.py reports `completeness.n_flagged` where run_report.py reports `n_actionable` + `n_advisory` — same batch, two different numbers
- `[bug]` the two batch tables have diverged: run_report.py vs triage_html.py column counts no longer match (13 after the item-1 src column)
- `[?]` a repair erases the `src_note` that motivated it — `_pre-repair-sentences.json` preserves original TEXT only, not the anomaly report attached to it
- `[?]` before promoting `n_src` from advisory into `flags_actionable`, measure the detector's fire rate and precision on a real Sonnet batch — it has zero measured precision today, and `entity_loss` (fired on 11 of 12 videos) is the cautionary precedent
- `[chore]` `repair_window_min_sec` has the doc-vs-behaviour gap that let `repair_window_max_sec` survive as a dead key: config.py calls 8-18 s "a reported range, not a calibrated threshold" while overdub.toml presents it as a tunable knob with no stated effect
- `[?]` `--repair-asr` exits 0 when EVERY window was rejected — deliberate (a rejection is a decided outcome), but a `repair && resume` wrapper would then dub an unimproved transcript silently. The one place the no-silent-failures rule is bent; decide consciously
