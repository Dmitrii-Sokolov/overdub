# Session 2026-07-18 — Gemma migration + item-0 ear-check close

## TL;DR
Two threads closed:
1. **Item 0 (whisper-context segmentation fix) ear-validated and CLOSED.** Full `--force` pass on a
   fresh workdir (x7DfiXqSEdM, `whisper_condition_on_previous=True`). Objective clean: 427 sentences
   (= the predicted 314→427), 0 verify flags, max speed 1.288. User ear verdict: all found problems
   gone, no sudden pauses, "better than ever". One accepted roughness: slightly slow speech
   (slot-fill stretch). NB the ear-check dub used **Qwen** — the segmentation verdict is
   translator-independent.
2. **Gemma-3-12B replaced Qwen3-14B as the translator** — A/B-driven; Qwen removed entirely.

## What happened, in order
- Reviewed docs → PLAN item 0 was the blocker. Ran the item-0 ear-check (~53 min, F5+bed, Qwen).
- Launched a 23-video stats batch (`work-exp/stats-batch`, Qwen). User stopped it at **8/23** having
  decided the real open problem is TRANSLATION quality ("Qwen местами сыпется").
- Implemented Gemma-3-12B support via an **ultracode workflow** (7 agents): built as two config
  flags (`ollama_system_role`/`ollama_send_think`) that kept the Qwen wire-request byte-identical,
  for a clean A/B. Live smoke green (proper nouns Latin, clean RU).
- Ran Gemma on the SAME 8 videos (`work-exp/gemma-ab`), seeded with the Qwen `sentences.json` so
  only the translator varied. Full-dub A/B.
- Analysis (508 sentences): Gemma tighter (len 1.062 vs 1.086), fewer flags (4 vs 6), ~16% slower
  (5.30 vs 4.58 s/sentence). User read ~100 phrases — all better on Gemma. Published an A/B artifact.
- User decision: adopt Gemma, drop Qwen entirely (not even an option). Collapsed the code to a
  single Gemma path — removed the two flags, the Qwen branch, `/no_think`, `SYSTEM_FOLDED`, `_THINK`.
  Updated all docs. Committed.

## State of the tree
- **Code**: `overdub/config.py`, `overdub/stages/translate.py`, `overdub.toml` → Gemma default
  (`gemma3:12b`), Qwen machinery gone. `py_compile` + live default-path smoke green.
- **Docs**: `CLAUDE.md`, `README.md`, `SETUP.md`, `STACK.md` → model refs updated (Qwen tuning
  findings in STACK kept as history under a date note). 4-file artifacts updated. This conspectus.
- **Artifacts on disk** (gitignored): `work-exp/context-earcheck` (item-0 dub, Qwen),
  `work-exp/stats-batch` (8 Qwen dubs), `work-exp/gemma-ab` (8 Gemma dubs + the A/B). `out/` holds
  the Gemma exports (they overwrote the Qwen ones — name collision, see INBOX).

## Open threads (→ PLAN)
1. **Translation completeness check** — the new top verify blind spot (round-trip is blind to a
   dropped word; Gemma's tightness sometimes drops one, e.g. Dmgujo id1).
2. **Finish the stats batch on Gemma** (15/23 unrun), incl. the Karpathy 3.5 h / Jensen 1.7 h stress
   tests — watch for whisper repetition loops (context=True risk).
3. **Babble duration heuristic** (existing). RyvXxApfHkk id12 = a real whisper CJK-garble both models
   "translated" — a corpus case for it.

## Loose ends
- STACK.md historical Qwen figures (9.3 GB, `/no_think`) left as history under a 2026-07-18 note.
- `work-exp/gemma-ab/gemma.toml` still sets the removed flags → harmless "unknown key ignored".
- "Keep length" prompt ↔ slow-speech trade documented in PLAN Open questions (lever: relax the
  keep-length pressure for fuller RU → less stretch, more compression).
