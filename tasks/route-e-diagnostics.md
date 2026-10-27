# Route E diagnostics say something on a healthy run

## Goal + AC

`build_clean.py`'s checks stop reporting noise and start showing trends: the entity detector does
not fire on corrected spellings, the ratio distribution is visible without a breach, and the
ratio floors sit where they can catch something. AC: not frozen — fix at pickup.

## Plan

- [ ] Entity detector (`_missing_tokens` over `_ENTITY_RE`): suppress a reported term when a
  SIMILAR token appears in the same id's cleaned text (difflib ratio over the pair). Site the
  threshold on the five pairs in Findings before picking a number.
- [ ] `--stats`: min/p10/median/max of the chunk ratio plus the lowest few chunks — the join
  already computes every number, `report()` discards them.
- [ ] Re-site `_RATIO_WARN_CHUNK` / `_RATIO_WARN_DOC` after 3-4 videos of different genres.
- [ ] Hand each cleaner agent its own range file (`clean/<from>-<to>.src.json`, range plus a few
  context lines) from `--plan`, instead of the complete `sentences.json`.

## State

Not started. Routed from INBOX at triage 2026-10-27 (four entries).

## Findings

**Entity detector, first real run** (`nVA0ASqbBhY`, 2690 sentences): 5 fires, **all 5 spelling
CORRECTIONS**, 0/5 precision — Chroniker→Kronecker, Kotan→cotan, Jacoby→Jacobi,
Lazenby→Lasenby, "Keane and Crane"→"Keenan Crane" (ASR had split one name into two people).

**Ratio floors are inert** against the only measurement: `nVA0ASqbBhY` came out at min 0.83 /
p10 0.86 / median 0.91 / max 0.97 over 34 chunks; the chunk floor (0.60) sits 0.23 below the
observed minimum. Candidate 0.70 — but do NOT move it on this sample: ratio tracks the FILLER
SHARE of the source, i.e. the genre (this video is a technical conversation, 165 lines emptied).
On the same run 43% of sentences came back byte-identical, 74% at similarity >= 0.90, and every
one of the 6 most-changed lines was pure filler — no paraphrasing observed. On a 20-char line,
dropping two words scores 0.4 mechanically.

**Range file.** `cleanerPrompt` points every agent at the COMPLETE `sentences.json` (16142 lines
on `nVA0ASqbBhY`; Read defaults to 2000 lines), so all 34 agents locate their range by offset.
