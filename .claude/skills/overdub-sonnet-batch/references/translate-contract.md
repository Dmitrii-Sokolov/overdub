# Translate-seam contract (route B)

Everything a Sonnet sub-agent needs to translate one video, plus the exact schemas of the three
artifacts involved. The division of labour is the whole point:

| Who | Produces | Owns |
|---|---|---|
| transcribe stage | `sentences.json` | id, source text, timings |
| **Sonnet sub-agent** | `translation.draft.json` | **`text_ru` + `src`** (the two judgement parts) |
| `scripts/build_translation.py` | `translation.json` + `pronounce_audit.json` | src_en/timings copy, `text_tts`, gate, contiguity, src vocab clamp + coverage count |

## Input — `work/<id>/sentences.json`

A JSON list, `id` contiguous from 0. The sub-agent reads this.

```json
[ { "id": 0, "text": "So today we're looking at the RTX 4080.", "start": 1.28, "end": 3.90 }, ... ]
```

The unit of translation is the sentence (`text`). Translate in `id` order.

## Draft schema — `work/<id>/translation.draft.json` (the sub-agent writes THIS, and only this)

A JSON list, one entry per sentence, covering **every** id in `sentences.json`:

```json
[ {"id": 0,  "text_ru": "Итак, сегодня мы смотрим на RTX 4080.", "src": "ok"},
  {"id": 19, "text_ru": "Описание выходит за рамки различия.",
   "src": "truncated",
   "src_note": "ends mid-thought; id 20 reads as its continuation"} ]
```

`src` is REQUIRED on every record; `src_note` is required whenever `src` is not `"ok"` and is
ignored otherwise. Nothing else. No `text_tts`, no `src_en`, no `start`/`end`, no `status`. Those
are filled deterministically by the helper. One `text_ru` = one natural spoken-Russian line.

## Translation rules (paste verbatim into the sub-agent prompt)

> These mirror the `SYSTEM` prompt of the local Gemma route so both routes translate identically.
> **Source of truth is `SYSTEM` in `overdub/stages/translate.py`** — if that changes, sync here.

1. Translate each English sentence into **natural, spoken Russian** for a single-narrator
   voice-over dub.
2. This is **dubbing**: the Russian must sound natural said aloud and stay **close in length** to
   the English so it fits the same on-screen time slot. Do not pad, do not over-compress.
3. Keep terminology, names and pronouns **consistent** across sentences (that is why you translate
   in id order with a rolling memory of the earlier sentences and your Russian for them).
4. Preserve meaning, tone and register. Write common acronyms the way they are normally written
   in Russian.
5. Keep every proper **name of a game, brand, platform or company in LATIN script**, capitalised
   the standard way, even when the English is lowercase (`runescape` → `RuneScape`, `minecraft` →
   `Minecraft`). **Never respell such a name in Cyrillic** — pronunciation is handled by a later
   step. Personal names may be written the usual Russian way.
6. Keep **numbers as digits** (`4080`, `50%`, `24/7`). Do **NOT** spell numbers out in words —
   that is handled later by the normalizer.
7. Each `text_ru` is a **single line** — no quotes, no English, no labels, no notes, no
   explanations, no `[RU]` prefix.
8. If a source sentence is **garbled, self-contradictory, truncated mid-thought, duplicative of
   its neighbour, or contradicts what earlier sentences established** — **translate it AS-IS and
   REPORT it.** Do not smooth it into plausible Russian, do not guess the intended wording, do
   not merge it with a neighbour. Set that record's `src` to the matching kind and add a
   one-line **English** `src_note` saying what looks wrong. A translator that repairs the source
   silently destroys the only signal that the source was damaged. Also watch runs of parallel or
   enumerated clauses: an item that repeats another item's head, or that contradicts the rolling
   context, is `enum_repeat` / `context_contradiction` even when each sentence reads fine alone.
   Every record gets a `src` — `"ok"` when the English is sound.

## Source anomalies — REPORT, never repair

Rationale: a good translator silently launders source damage. DECISIONS 2026-07-19 —
`RyvXxApfHkk` id11's ASR garbage was repaired into plausible Russian by Sonnet on the first
pass and vanished from everything downstream. The better the translator, the more reliably it
hides source damage. A reading pass helps only when it is asked to REPORT rather than smooth;
that is a prompt requirement, not a property of the model.

`"ok"` is a POSITIVE CLAIM: you read this English sentence and it is not damaged. Omitting the
field is not the same as `"ok"` — it is reported as "not scanned".

| `src` | fires when | the 0-case it exists for |
|---|---|---|
| `ok` | you read this English sentence and it is not damaged | — (positive claim) |
| `garbled` | unintelligible or self-contradictory as written | `RyvXxApfHkk` id11 |
| `truncated` | cut mid-thought; the thought continues in a neighbour | `W4Ua6XFfX9w` 19/20 |
| `dup_neighbour` | says what an adjacent sentence already said | echoes below the 0.80 `dup_adjacent` bar |
| `enum_repeat` | an item in a run of parallel/enumerated clauses repeats another item's head | 0b duplicated head |
| `context_contradiction` | contradicts what earlier sentences established | the bogus id46 line |

- `dup_neighbour` is set on **every** id involved, matching `completeness.duplicate_adjacent`'s
  both-pair-members convention that `repair.seed_ids_from_detectors` relies on.
- `garbled` covers self-contradictory-*as-written*; `context_contradiction` covers contradicting
  the *rolling context*.
- `src_note` is **English** (it sits beside the `src_en` it describes) and one line. Anything
  over 200 chars is visibly truncated by the helper.

Worked example (`W4Ua6XFfX9w`): id 19 `"Description goes beyond distinction."` /
id 20 `"just writing prompts."` — a hallucinated `distinction` for `just` split one sentence in
two. Each half sits at ~26 ch/s against the 40 bound and the halves are not similar to each
other, so `rate_implausible` and `dup_adjacent` are blind BY CONSTRUCTION. Only reading the
text finds it. Mark id 19 `truncated` ("ends mid-thought; id 20 reads as its continuation").

## Output schema — `work/<id>/translation.json` (the helper builds THIS; agents never write it)

```json
[ { "id": 0, "start": 1.28, "end": 3.90,
    "src_en": "So today we're looking at the RTX 4080.",
    "text_ru": "Итак, сегодня мы смотрим на RTX 4080.",
    "text_tts": "Итак, сегодня мы смотрим на эр-ти-экс четыре тысячи восемьдесят.",
    "status": "ok", "attempts": 1 }, ... ]
```

- `src_en`, `start`, `end` — copied from `sentences.json` (join on id). The resume/congruence key.
- `text_tts` — `overdub.normalize.normalize_for_tts(text_ru)`, the **same** function verify uses.
  Never hand-written.
- `status` — `"ok"`, or `"failed"` with an extra `"flag"` field when `_is_bad` rejects the line.
- `attempts` — always `1` on this route (no reseed loop; Sonnet translated once).

The helper also writes `work/<id>/pronounce_audit.json` (audit-only, read by nobody — same as
the local route): what the pronounce chain invented for Latin tokens, for operator triage of
the out-of-dict-name silent-loss class.

## Gate — why a line comes back `status:"failed"`

`scripts/build_translation.py` runs each `text_ru` through
`overdub.stages.translate._is_bad(text_ru, src_en, cfg)` — the same gate as the Gemma path.
Reasons (`flag` value), so you know what to fix in the draft:

| flag | meaning | fix |
|---|---|---|
| `empty` | blank `text_ru` | the sentence has no translation — add one |
| `no_cyrillic` | no Russian even after normalization (pure punctuation/garbage) | translate it for real |
| `english_echo` | too many all-lowercase Latin runs (untranslated English left in) | actually translate; only game/brand NAMES stay Latin |
| `runaway` | `text_ru` > 3× the source length | over-translation/rambling — tighten it |
| `refusal` | contains an "I cannot / как модель / не могу перевести" phrase | remove the meta-text, give the translation |

Flagged lines are **not blocking** — they are recorded and the pipeline runs on (audibly broken
segments are acceptable losses; silent ones are not). Re-run just the affected sub-agent and the
helper if you want to clear a flag.

The helper's `src` handling is deliberately **non-blocking**: a missing `src`, an unknown kind,
or an anomaly with no note each produce a `[warn]` and are reported (unknown kinds bucket as
`unknown`; a record with no `src` counts as unscanned and shows as `-` rather than `0` in the
digest). It never exits non-zero on them. A report must never gate a dub — a hard failure here
would leave `translation.json` unwritten, and a resume would then silently run the local Gemma
path for that video.
