# Phoneme transliteration from CMUdict

## Goal + AC

The out-of-dictionary `pronounce` fallback transliterates from PHONEMES (ARPAbet→Cyrillic,
`data/cmudict.dict`) instead of guessing from spelling, so ordinary English words stop needing
the translator's dual-form markup. Blocks tasks/stress-audit.md.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup. Needs an ear check
either way.

## Plan

- [ ] ARPAbet→Cyrillic table: ~39 phonemes against ~55 letter rules — smaller AND more accurate.
- [ ] Keep the letter rules as the out-of-dictionary fallback (brands and neologisms: `mcp`,
  `anthropic`, `vercel`, `shadcn`, `tmux` are absent from CMUdict).
- [ ] Ear check on the measured offender classes below.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. Partly DEFUSED
2026-08-11 by the dual-form markup (DECISIONS 08-11): the translator now supplies the reading,
so the fallback saw 2 tokens on `L0nBN6ME7VQ` instead of 90 — the task is no longer about the
DUB being wrong, it is about how much the translator has to mark, i.e. the seam's cost. Fixing
it makes the markup optional for ordinary words.

## Findings

The letter rules guess from spelling what the dictionary knows phonetically: `buy → буи` vs
`B AY1`, `fields → фиелдс` vs `F IY1 L D Z`, `update → упдейт` vs `AH0 P D EY1 T`, `execute →
эксекют` vs `EH1 K S AH0 K Y UW2 T`. Coverage over the corpus's invented tokens: 79% of types,
77% of occurrences; the absent tail is brands and neologisms, so the letter rules STAY as the
fallback.

**The 2026-07-28 translation-layer audit measured the same class from the other end and named
its frequency peak: `alignment → алигнмент`, 91 occurrences.** `data/cmudict.dict` has it
(`AH0 L AY1 N M AH0 N T`) and 6 of the audit's other 7 examples — `deceptive`, `language`,
`research`, `reduce`, `hero`, `models` — each giving roughly the pronunciation the audit asked
for; only `OpenAI` sits in the brand tail. So the dictionary route already reaches the top
offender, and the audit's own proposal (a hand-built 50-100 entry transliteration list) is the
same fix at more maintenance for less coverage. This also closes the open-class residue the
~55-rule ceiling made awkward: `execute → эксекют` (18 hits), `adventures → адвентурс`,
`fields → фиелдс`, `open → опен`, `waters → вейтерс`, `buy → буи`. A rule on `ex-`/`ie`/`-ute`
is ambiguous in English ("exit" wants экс, "execute" wants эгз) — hence the dictionary, not
another rule.

**Confirmed from a third angle 2026-08-11.** Four more spelling failures off `L0nBN6ME7VQ`:
`button → буттон`, `changes → чанджс`, `breaking → брикинг`, and `alchemy → алчеми` where the
`ch` is /k/ — the last being the clean argument that no rule over letters can reach this class.
Compounds are the sharper case: `AlchemySerializeField` came out as one glued
«алчемисериалайзфиелд».

**Do not reach for espeak-ng for this** (proposed 2026-08-11, the worse option):
`data/cmudict.dict` is already in-repo and covers the measured class, while espeak would be a
third external binary against the two the stack rule allows, and it answers only the
brand/neologism tail the letter rules already own.
