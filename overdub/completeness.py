"""Cheap deterministic completeness check: flags likely translation losses per sentence.

Pure, deterministic, no LLM, no VRAM, no I/O. Public API:

    check(src_en: str, text_ru: str, cfg) -> dict

returning {"length_ratio", "missing_numbers", "negation_lost", "missing_entities", "flags"}
where flags is a subset of ["num_loss", "neg_loss", "entity_loss", "length_short"].

The check is a pure src_en <-> text_ru TEXT comparison. It compares RAW strings (light
casefold only) and NEVER pipes them through normalize.py: normalize_for_tts spells digits
into Russian words ("100" -> "сто") and transliterates Latin to Cyrillic ("Minecraft" ->
"майнкрафт"), which would DESTROY exactly the two signals the number/entity detectors depend
on (an exact digit substring, and a kept-Latin run). The only normalize.py reuse is the
number-speller normalize._n2w, used solely as a false-positive SUPPRESSOR (see below).

All four flags are NON-BLOCKING triage hints written to report.json. Each is precise-but-not-
perfect; every detector has a documented false-positive source and the whole check is
designed to prefer a MISS over a false alarm (the weak length signal most of all). None of
these flags ever halts the pipeline or changes flow — they exist for a human triaging the run.

DETECTORS
---------
length_short  (signal A, WEAK) — len(text_ru)/len(src_en) below cfg.completeness_len_ratio_min
    AND len(src_en) >= _MIN_SRC_LEN chars. Russian and English land at near-parity char length
    (median ratio ~0.95 on real data — RU drops articles/auxiliaries), so normal dubbing
    compression is NOT loss. The min-length guard removes the noisy short-fragment tail; below
    that the threshold (0.45) sits under the natural RU-compression floor (~0.46), so it fires
    only on a genuinely dropped clause / empty / truncated output. Validated 0/427 false
    positives on both the Gemma and the near-clean Sonnet 427-sentence samples.
    FALSE POSITIVE: a legitimately condensed sentence just above the floor; kept rare by the
    conservative threshold. This signal is coarse and intentionally redundant with the precise
    B-signals below — it only catches the catastrophic drop that carries no number/neg/entity.

num_loss  (signal B) — a digit run present in src_en but absent from text_ru. Leans on the
    translation rule "keep numbers as DIGITS": a number in src_en stays the same digits in
    text_ru, so detection is exact digit-substring matching. CLEAN on the Sonnet path (0 fires
    on 427). NOISY on the Gemma path, which spells numbers out against the rule ("100%" -> "сто
    процентов"); the normalize._n2w nominative-spelling suppressor blunts most of that, but RU
    oblique case ("140" -> "ста сорока", nominative is "сто сорок") still slips through.
    FALSE POSITIVE: a number the translator legitimately spelled/reformatted (Gemma path only).

neg_loss  (signal B) — an EN negation marker present in src_en with NO RU negation marker in
    text_ru. Negation inverts meaning: the single most dangerous SILENT loss. RU markers are
    matched as word-INITIAL PREFIXES (не*, ни*) — bound-prefix negatives (непросто, невозможно,
    нельзя, нечего) glue the negation to the stem and are missed by whole-word matching. Over-
    matching non-negation не-/ни- words (неделя, нейрон) only SUPPRESSES the flag -> a miss,
    the safe direction. Known multiword names ("No Man's Sky") and pleonastic idioms ("more
    often than not", "no doubt") are stripped before the scan.
    FALSE POSITIVE: legitimate double-negative collapse; lexical/implicit RU negation with no
    не/ни/без token ("not playing" -> "в одиночку"). Irreducible without a lexicon; triage-only.

entity_loss  (signal B) — a Latin proper NAME present in src_en but absent (case-insensitively)
    from text_ru. Leans on the rule "keep game/brand/platform/company NAMES in LATIN script":
    such a name stays Latin in text_ru and substring-matches; a dropped or Cyrillicized one does
    not. Candidates are Titlecase Latin tokens (first letter upper, NOT all-caps) of base length
    >= 2, minus a stoplist (function words, pronouns incl. 'i', weekday/month names) and the
    sentence-initial token. ALL-CAPS acronyms are excluded on purpose: the prompt allows them to
    be Russianized (AI -> ИИ), so including them is near-pure noise.
    FALSE POSITIVE (dominant, irreducible): personal names, which the naming rule PERMITS to be
    Russified (Jimmy -> Джимми, Bruce Lee -> Брюс Ли). Also translated quoted work titles. No
    cheap person-vs-brand discriminator exists; this flag is triage-only, as designed.
"""

from __future__ import annotations

import re

from . import normalize, pronounce

# Min src_en length (chars) for the length_short signal. Companion guard to
# completeness_len_ratio_min, NOT a second tunable — it removes the noisy short-fragment tail
# (where nothing CAN be dropped) so the conservative ratio threshold stays zero-false-positive.
# Stable for every guard length in 30..100 on the real data.
_MIN_SRC_LEN = 30

# --- number detector ----------------------------------------------------------
_DIGITS_RE = re.compile(r"\d+")


def _missing_numbers(src_en: str, text_ru: str) -> list[str]:
    ru_cf = text_ru.casefold()
    missing: list[str] = []
    for n in dict.fromkeys(_DIGITS_RE.findall(src_en)):   # dedupe, keep order
        if n in text_ru:                                  # exact digit substring: present
            continue
        # FP-suppressor (Gemma spells numbers out against the keep-digits rule): count the
        # number PRESENT if its nominative spelling shares a token with text_ru. Over-
        # suppression only ever produces a miss (the safe direction).
        spelled = normalize._n2w(int(n))
        if any(w and w in ru_cf for w in spelled.split()):
            continue
        missing.append(n)
    return missing


# --- negation detector --------------------------------------------------------
# EN markers: whole words + the n't contraction tail (don't/isn't/can't/won't/...).
_EN_NEG_RE = re.compile(
    r"\b(?:not|never|no|none|nobody|noone|nothing|nowhere|without|cannot|neither|nor)\b"
    r"|n['’]t\b"
)
# Pleonastic EN not/no that carry no negative meaning — stripped before the scan.
_NEG_IDIOMS = (
    "more often than not", "not to mention", "not only", "no doubt", "no wonder",
    "why not", "whether or not",
)
# RU markers: не/ни as word-INITIAL PREFIXES (catches непросто/нельзя/никогда), plus без as a
# standalone preposition. Text is casefolded + ё->е before this runs.
_RU_NEG_RE = re.compile(r"(?<![а-я])(?:не|ни)[а-я]*|(?<![а-я])без(?![а-я])")


def _negation_lost(src_phrased_cf: str, text_ru: str) -> bool:
    en = src_phrased_cf
    for idiom in _NEG_IDIOMS:
        en = en.replace(idiom, " ")
    if not _EN_NEG_RE.search(en):
        return False
    ru = text_ru.casefold().replace("ё", "е")
    return not _RU_NEG_RE.search(ru)


# --- entity detector ----------------------------------------------------------
# Latin tokens whose Titlecase shape mimics a proper name but that are NOT names. Bigger is
# safer here: every added word only suppresses a fire (a miss), never creates one.
_ENTITY_STOP = {
    # pronouns (incl. the always-capitalized 'i')
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their", "mine", "yours", "hers", "ours", "theirs",
    "this", "that", "these", "those", "who", "whom", "whose", "which", "what",
    # articles / conjunctions / prepositions / frequent sentence openers
    "the", "a", "an", "and", "or", "but", "so", "if", "then", "than", "as", "at", "by",
    "for", "from", "in", "into", "of", "on", "onto", "to", "with", "without", "about",
    "after", "before", "over", "under", "up", "down", "out", "off", "through", "between",
    "not", "no", "yes", "well", "oh", "ok", "okay", "like", "just", "now", "here", "there",
    "when", "where", "why", "how", "while", "because", "though", "although", "also", "too",
    "very", "really", "actually", "maybe", "perhaps", "yeah", "yep", "nope", "hey",
    # common capitalized-at-start auxiliaries / verbs
    "is", "are", "was", "were", "be", "been", "being", "am", "do", "does", "did", "done",
    "have", "has", "had", "will", "would", "can", "could", "should", "shall", "may", "might",
    "must", "get", "got", "let", "make", "made", "go", "going", "went", "come", "came",
    "see", "say", "said", "think", "know", "want", "need", "one", "two", "some", "any",
    # weekdays + months (always capitalized in EN, translated + lowercased in RU)
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
}


def _missing_entities(src_phrased: str, text_ru: str) -> list[str]:
    ru_cf = text_ru.casefold()
    missing: list[str] = []
    seen: set[str] = set()
    for idx, m in enumerate(pronounce.TOKEN_RE.finditer(src_phrased)):
        base = re.split(r"['’]", m.group(0))[0]           # pre-apostrophe base: I'll -> I
        if len(base) < 2:
            continue
        if not (base[0].isupper() and not base.isupper()):  # Titlecase only, exclude ALL-CAPS
            continue
        low = base.casefold()
        if idx == 0:                                      # sentence-initial belt-and-suspenders
            continue
        if low in _ENTITY_STOP:
            continue
        if low in ru_cf:                                  # kept-Latin name -> substring present
            continue
        if low not in seen:
            seen.add(low)
            missing.append(base)
    return missing


# --- public API ---------------------------------------------------------------
def check(src_en: str, text_ru: str, cfg) -> dict:
    """Run all four completeness detectors on one sentence pair.

    Returns a dict with the per-sentence signals and a `flags` list (subset of
    ["num_loss", "neg_loss", "entity_loss", "length_short"], empty when clean). Deterministic,
    no I/O. See the module docstring for each detector's rule and false-positive caveat.
    """
    src_en = src_en or ""
    text_ru = text_ru or ""
    src_phrased = pronounce.replace_phrases(src_en)       # neutralize the 6 multiword names once

    length_ratio = round(len(text_ru) / max(len(src_en), 1), 3)
    missing_numbers = _missing_numbers(src_en, text_ru)
    negation_lost = _negation_lost(src_phrased.casefold(), text_ru)
    missing_entities = _missing_entities(src_phrased, text_ru)

    flags: list[str] = []
    if missing_numbers:
        flags.append("num_loss")
    if negation_lost:
        flags.append("neg_loss")
    if missing_entities:
        flags.append("entity_loss")
    if len(src_en) >= _MIN_SRC_LEN and length_ratio < cfg.completeness_len_ratio_min:
        flags.append("length_short")

    return {
        "length_ratio": length_ratio,
        "missing_numbers": missing_numbers,
        "negation_lost": negation_lost,
        "missing_entities": missing_entities,
        "flags": flags,
    }
