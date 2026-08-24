# Any-language source → Russian

## Goal + AC

Any source language dubs to Russian. Shelved 2026-07-19 until the EN queue runs dry — biggest
effort in the backlog and it breaks the EN→RU hard constraint (CLAUDE.md). Quality degradation
on rare languages ACCEPTED — coverage, not parity.
AC: not frozen — task shelved; imported from PLAN.md (2026-08-24).

## Plan

- [ ] whisper large-v3 is already multilingual: drop the hardcoded `language="en"` and detect;
  the translator is prompt-driven, so source language is a prompt variable.
- [ ] Touches: `cfg.source_lang`, the transcribe call, both routes' prompts, the `en.srt` label,
  and the Latin-punctuation-shaped resegmentation `TERMINATORS`/`_ABBREV`.

## State

Shelved. Imported from PLAN.md at the 2026-08-24 agent-docs migration.

## Findings

Two of the touch-points are now MEASURED rather than suspected, on the Russian side at least:
route E went EN-or-RU on 2026-08-14 and `resegment` needed nothing — dotted abbreviations appear
once in 1832 sentences and Russian sentence length matches English, so `TERMINATORS`/`_ABBREV`
are not the obstacle this task assumed for RU. Says nothing about a language that does not end
sentences with `.!?`.

Related open bug: `--repair-asr` forces `language=ctx.cfg.source_lang` on every re-read window
(INBOX 2026-08-14 entry) — three call sites read `cfg.source_lang` for three different reasons
and only two of them mean it.
