# Translation-layer audit (2026-07-28) — the three findings that had no home

## Goal + AC

Shared context for three BACKLOG lines born from the 2026-07-28 translation-layer audit
(9 `translation.json`, ~2090 segments). Semantic translation quality and ASR-repair metadata
came back clean; every finding is in the TTS normalization layer or cross-segment consistency.
AC: each sub-item below fixed or explicitly rejected.

**Provenance caveat: the audit read files named `translation__N_.json` and no video ids, so not
one of its counts is traceable to a workdir — get the id mapping before quoting any number from
it.** A `translation.json` is engine-neutral EXCEPT where a figure is measured against the slot
(there the F5-era corpus boundary applies — `overdub/CLAUDE.md`).

## Plan

- [ ] **URL / domain branch in the normalizer.** `claude.ai` → "клод.ей": the dot SURVIVES, so
  Silero reads it as a sentence end (spurious pause + falling contour mid-phrase), and `.ai`
  voices as "ей" instead of "эй-ай"; want "клод точка эй-ай". Also `anthropic.com` →
  "антропик.ком", `importai.substack.com`. `pronounce.py` carries `URL`/`HTTP`/`HTTPS` as
  acronyms and no domain rule at all, so nothing owns this shape today. Cheap and
  self-contained; the ear-audible half is the dot, not the TLD.
- [ ] **Terminology drifts INSIDE one file, not only across a series.** One file renders
  "alignment" three ways — 93× left in Latin, 23× "согласова-", 9× "выравнива-", sometimes in
  adjacent segments — and produced "фейковать выравнивание". Different grain from the per-SERIES
  glossary (BACKLOG): the fix is a file-scoped glossary carried across segments instead of
  re-derived per sentence, i.e. a route-B prompt/`build_translation` change, not a `terms.tsv`.
- [ ] **`english_echo` marks deliberately preserved terms as `failed`** — 7 segments, all on
  "alignment faking", translations correct. Not a new class: the comment above
  `translate._latin_prose_chars` records that 13 of 28 fires on the 2026-07-25 batch were the
  technical-token shape and the remaining 15 were set phrases the translator kept on purpose
  (`runreport`'s `_ADVISORY_TRANSLATE` comment scores all 28 as correct Sonnet behaviour). But
  the STATUS written into `translation.json` is still `failed`, which is what the audit read —
  decide whether the term-preservation exemption belongs in `_is_bad` beside the three that are
  there, or whether the status is simply the wrong field for an advisory.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. The audit's four
OTHER findings were routed into existing items at the time and are deliberately not duplicated
here: anglicisms → tasks/cmudict-transliteration.md; ch/s over the slot → tasks/slot-fit.md;
the inert `src` detector → tasks/src-seed-repair.md; numeral case → the accepted PoC loss in
`normalize.py`'s module docstring, whose proposed LLM fix is rejected by DECISIONS 2026-07-17
F1/F2 (an LLM-spelled `text_tts` diverges from the Python normalizer verify applies and silently
depresses similarity on correct numeric dubs — case-aware numerals are a `num2words` +
syntactic-context pass inside `normalize.py`, never an LLM field).
