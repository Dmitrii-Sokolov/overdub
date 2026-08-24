# Slot fit — size the translation to the slot

## Goal + AC

The translation is sized to its slot (target chars = slot ÷ the voice's rate, `tts.target_chars`)
so the residual slot silence and the audible floor-pinned stretches go away. **The fit is
TWO-SIDED** (re-framed 2026-07-25, user call) — see Findings for why the original "Silero
under-fills, translate longer" framing did not survive the corpus.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup.

## Plan

- [ ] Compute the per-sentence target in a shared helper that `translate.py` and
  `scripts/build_translation.py` both call; enforce/report it in the latter, or route-B
  compliance is unverifiable. (Route B's prompt is a STATIC template in
  `.claude/workflows/translate-batch.js` — it can carry a rule change without a model in the
  loop, but the per-sentence target has to travel with the data.)
- [ ] Re-anchor the `runaway` gate: `_is_bad` caps `text_ru` at
  `translate_max_len_ratio=3.0 × len(src_en)`, so for any source slower than ~6.3 en ch/s the
  CORRECT length is flagged, costing up to 4 reseeds and in the limit shipping `src_en`, i.e.
  English into the dub. Anchor on the target, not on the source length.
- [ ] Re-derive the inventory of the length rule's hand-synced copies before touching any of
  them (see Findings — the list was wrong in both directions until 2026-08-03).

## State

Not started under this file. Imported from PLAN.md at the 2026-08-24 agent-docs migration.
Two thirds already shipped 2026-07-25 (ru.srt follows the dub; `atempo_floor` = 0.75 cut slot
silence 283 → 84 s on `8zJlKmgMT44` in assembly alone). Ranked below the top three because the
ear passed the shipped config twice (2026-07-26/27) without it. What is left is the polish that
removes the 84 s residue and the audible stretch on the 42-of-69 units pinned at the floor.

## Findings

**Two-sided fit.** On 3 of the 5 videos in `work-silero-v5` Silero **over**-runs its slots
(raw/slot medians 1.023, 1.145, 1.017; 16/30, 19/31, 21/37 units under atempo), on 2 it
under-fills (0.791, 0.816), and 0.73 was one video's SOURCE pace, not an engine property. What is
missing is a duration model in either direction. The engine side is a usable constant because
Silero's rate is stable (CV 5.5%), but it is **per VOICE, not per engine**: eugene runs ~1.4×
baya; the shipped per-voice rates live in `overdub/tts/__init__.py` `_VOICE_RATE` (with their
provenance) — the knob keys on `tts_voice`.

**Sized from the TEXT side 2026-07-28** (translation-layer audit, 9 files): median 18-22 ch/s
against the slot, p90 25-31, 631 of 988 segments over 20 ch/s in the worst file — and ru/en
length ratio **0.97**, so the pressure is the SOURCE speaker's pace, not RU expansion (same
conclusion the 0.73 reached from the audio side). Two cautions: the audit's "comfortable Russian
TTS is 14-16 ch/s" is not our number and sits against a measured eugene rate of 19.85 ru ch/s;
and at that rate a 22 ch/s slot needs cf ≈ 1.11, inside the 1.22 the shipped-config batches
already reached and the ear already passed twice. The figures SIZE this task; they do not reopen
it as a defect.

**Obstacles, status as of 2026-08-24:** (i) ~~`atempo` <1 does not exist~~ BUILT
(`assemble._tempo_for`); (ii) the `runaway` gate fights the target (see Plan); (iii) the length
rule lives in FOUR hand-synced copies — the inventory is worth re-deriving before touching any
of them; it was wrong in both directions until 2026-08-03:

| where | what it is |
|---|---|
| `translate.py` `SYSTEM` | the stated source of truth — and NOT imported by anything: `build_translation.py` imports `_is_bad` from this module, never `SYSTEM`, so nothing enforces the other three against it |
| `skills/overdub-sonnet-batch/references/translate-contract.md` rule 2 | what the route-B sub-agent reads off disk |
| **`.claude/workflows/translate-batch.js`** | the route-B prompt itself — **the copy that decides the output**, and the one the old inventory missed |
| `CLAUDE.md` (Design rules) | prose — states WHY the prompt must carry the rule, not the rule's text |

~~`README.md`~~ — removed 2026-08-21: it had drifted to the pre-08-11 wording (the inverse of the
shipped dual-form rule) while the old inventory listed it as a synced copy. README now points at
`translate-contract.md` instead of restating anything. Do not re-add a fifth copy by summarising
the rules there again.

(iv) ~~the resume key ignores timings, so after `--repair-asr` a translation sized for a slot
that no longer exists is silently kept~~ GONE with route A: the resume key is now
`translation.json` existing (`stages/translate.py` `done()`), and `invalidate_downstream` deletes
that file plus `translation.jsonl` and `translation.draft.json` on every repair.

**"Keep length" is being replaced, not tuned** (was PLAN "Open questions"). The SYSTEM prompt
asks the LLM to keep RU close in length to the EN; this task replaces that with an explicit
target character count, and the engine-side slot-fill stretch — the other half of the old
trade — no longer exists. The measured translator-tightness comparison from that era (508 segs)
is evidence about a knob that is going away. Do not tune the old prompt; land this task.

**Current valid reading of `8zJlKmgMT44`** (shipped grouping 1.2/20/600, measured 2026-07-25 —
was PLAN "Numbers to re-measure" (A)): fill median 0.7104, slot silence 283.1 s of a 1058.8 s dub
(`in_span_silence` reads 241.8 s on the same run and understates by 41 s — it excludes the
inter-unit gap). Quote these; every earlier pair on this video was measured at grouping
0.4/12/300 and is history, not a comparison arm. **Retired, do not re-quote: "17 units at
cf ≥ 1.8, up to ×12.5"** — recomputed over all of `work/` 2026-07-25: 7 units of 3575, worst
2.63 (12 SENTENCE rows — the two counts were being mixed, and the ×12.5 was one sentence's
pre-repair `speed_factor`).
