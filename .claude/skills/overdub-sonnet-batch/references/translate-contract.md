# Translate-seam contract (route B)

Everything a Sonnet sub-agent needs to translate one video, plus the exact schemas of the three
artifacts involved. The division of labour is the whole point:

| Who | Produces | Owns |
|---|---|---|
| transcribe stage | `sentences.json` | id, source text, timings |
| **Sonnet sub-agent** | `translation.draft.json` | **`text_ru` only** (the judgement part) |
| `scripts/build_translation.py` | `translation.json` + `pronounce_audit.json` | src_en/timings copy, `text_tts`, gate, contiguity |

## Input — `work/<id>/sentences.json`

A JSON list, `id` contiguous from 0. The sub-agent reads this.

```json
[ { "id": 0, "text": "So today we're looking at the RTX 4080.", "start": 1.28, "end": 3.90 }, ... ]
```

The unit of translation is the sentence (`text`). Translate in `id` order.

## Draft schema — `work/<id>/translation.draft.json` (the sub-agent writes THIS, and only this)

A JSON list, one entry per sentence, covering **every** id in `sentences.json`:

```json
[ { "id": 0, "text_ru": "Итак, сегодня мы смотрим на RTX 4080." }, ... ]
```

Nothing else. No `text_tts`, no `src_en`, no `start`/`end`, no `status`. Those are filled
deterministically by the helper. One `text_ru` = one natural spoken-Russian line.

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
