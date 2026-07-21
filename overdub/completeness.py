"""Cheap deterministic completeness check: flags likely translation losses per sentence.

Pure, deterministic, no LLM, no VRAM, no I/O. Public API:

    check(src_en: str, text_ru: str, cfg) -> dict           # per sentence PAIR
    duplicate_adjacent(texts: list[str]) -> dict[int, int]  # per DOCUMENT (EN source)
    implausible_rate(texts, durations) -> dict[int, float]  # per DOCUMENT (EN source + timing)

check() returns {"length_ratio", "missing_numbers", "negation_lost", "missing_entities",
"flags"} where flags is a subset of ["num_loss", "neg_loss", "entity_loss", "length_short"].
The two DOCUMENT-level detectors contribute the fifth and sixth flags, "dup_adjacent" and
"rate_implausible", which the caller appends (verify.py) — check() sees one sentence pair at a
time and can reach neither a neighbour nor a timestamp. Both of those inspect the EN SOURCE:
they catch ASR defects, not translation ones.

The check is a pure src_en <-> text_ru TEXT comparison. It compares RAW strings (light
casefold only) and NEVER pipes them through normalize.py: normalize_for_tts spells digits
into Russian words ("100" -> "сто") and transliterates Latin to Cyrillic ("Minecraft" ->
"майнкрафт"), which would DESTROY exactly the two signals the number/entity detectors depend
on (an exact digit substring, and a kept-Latin run). The only normalize.py reuse is the
number-speller normalize._n2w, used solely as a false-positive SUPPRESSOR (see below).

All five flags are NON-BLOCKING triage hints written to report.json. Each is precise-but-not-
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
    matched as word-INITIAL PREFIXES (не*, ни*, без*, бес*) — bound-prefix negatives (непросто,
    невозможно, нельзя, нечего, бесполезно, безопасно) glue the negation to the stem and are
    missed by whole-word matching. The без/бес pair is ONE marker under Russian voicing
    assimilation (без+полезный -> бесполезный): matching only the voiced з, or only the
    standalone preposition, made the з/с alternation decide the flag — the W4Ua6XFfX9w#32 false
    positive ("полезное от бесполезного"). Over-matching не-/ни- words (неделя, нейрон) only
    SUPPRESSES the flag -> a miss, the module's usual safe direction. бе[зс]- is the EXCEPTION:
    _NEG_POSITIVE_STEMS subtracts the stems that are privative by etymology but POSITIVE by
    polarity (безопасный, бесплатный, бесед-), because suppressing on those blinds the detector
    to the inversion it exists for. See the comment on _NEG_POSITIVE_STEMS for why this one
    detector inverts the module's prefer-miss default.
    Known multiword names ("No Man's Sky") and pleonastic idioms ("more
    often than not", "no doubt") are stripped before the scan.
    FALSE POSITIVE: legitimate double-negative collapse; lexical/implicit RU negation with no
    не/ни/без token ("not playing" -> "в одиночку"); and, by the deliberate trade above, a
    correct translation into a positive-polarity бе[зс]- word ("not dangerous" -> "безопасно").
    Irreducible without a lexicon; triage-only.

entity_loss  (signal B) — a Latin proper NAME present in src_en but absent (case-insensitively)
    from text_ru. Leans on the rule "keep game/brand/platform/company NAMES in LATIN script":
    such a name stays Latin in text_ru and substring-matches; a dropped or Cyrillicized one does
    not. Candidates are Titlecase Latin tokens (first letter upper, NOT all-caps) of base length
    >= 2, minus a stoplist (function words, pronouns incl. 'i', weekday/month names) and the
    sentence-initial token. ALL-CAPS acronyms are excluded on purpose — including their PLURAL
    form (LLMs/GPUs/APIs: ALL-CAPS stem + trailing lowercase s, which reads as Titlecase to the
    shape check): the prompt allows both to be Russianized (AI -> ИИ, LLMs -> нейросети), so
    including them is near-pure noise.
    FALSE POSITIVE (dominant, irreducible): personal names, which the naming rule PERMITS to be
    Russified (Jimmy -> Джимми, Bruce Lee -> Брюс Ли). Also translated quoted work titles. No
    cheap person-vs-brand discriminator exists; this flag is triage-only, as designed.

dup_adjacent  (signal C, CROSS-SENTENCE — the only detector that is not a src_en<->text_ru
    comparison) — two ADJACENT source sentences that are near-identical (ratio >
    _DUP_RATIO_MIN) OR where one is largely contained in the other (containment >
    _DUP_CONTAINMENT_MIN), with the first at least _DUP_MIN_LEN chars. An ASR defect, not a
    translation one: whisper's repetition loop emits a line twice, or re-speaks part of it and
    continues, and the dub then says it twice. It therefore runs on the EN SOURCE, never on
    text_ru, and is computed by duplicate_adjacent() over the whole document rather than by
    check(). Two signals because they catch disjoint shapes: ratio alone found 1 of this
    corpus's 3 repetition defects, containment finds all 3.
    Measured on the 13-video / 1101-sentence batch: 3 fires in 1028 eligible pairs, all true
    positives (ytEN_iAk09c 7/8 byte-identical, the second spanning 0.32 s; x7DfiXqSEdM 298/299
    and 2YCaBqP8muw 16/17, both restarts).
    FALSE POSITIVE (dominant): single-token substitution across a shared frame — enumerations
    ("Number one, be specific…" / "Number two, be specific…" = 0.89), before/after and free/paid
    contrasts (0.92-0.93), CPU/GPU swaps (0.98). At 0.80 a pair may differ in ~12% of its
    characters, so near-identity is NOT required to fire. The dangerous shape is a polarity flip
    in an otherwise identical frame ("You should use this…" / "You should not use this…" =
    0.96): a triager who acts on the flag by deleting one member INVERTS the meaning — read both
    members before touching either. Measured zero times in the 1028-pair batch (explainer prose,
    where such pairs are rare), so this is genre exposure rather than an observed defect; a
    conversational or instructional corpus would fire far more often.
    Deliberate verbatim repetition for effect ("It is not enough. It is not enough.") is the
    other, rarer FP mode.
    KNOWN MISS, documented so a clean flag is not over-read. Two classes stay invisible:
    (1) NON-ADJACENT repetition loops — the scan is strictly pairwise, so a loop that skips a
    sentence is unreachable by construction, not by threshold. A duration/words-per-second
    check would catch those independently of any text comparison (INBOX).
    (2) SEMANTIC garbles that repeat no span, e.g. the W4Ua6XFfX9w four-Ds recap, where a head
    token is duplicated across an enumeration (ratio 0.5882, containment 0.44) — a different
    defect needing a different detector. A clean dup_adjacent does NOT mean "no repetition
    defects in this transcript". Class (1) is now covered by rate_implausible below, which sees
    collapsed alignments without comparing text at all.

rate_implausible  (signal D, per sentence, EN source + TIMING — the only detector that does not
    read text_ru at all) — a source sentence whose chars/second exceeds _RATE_MAX_CPS, i.e. one
    that cannot physically have been spoken in its own span. The signature of a whisper
    alignment collapse: the decoder stamps a hallucinated or repeated line onto a fraction of a
    second. Computed by implausible_rate() over the document; needs `start`/`end`, which the
    translate seam already carries.
    Measured on the 13-video / 1100-sentence corpus: 7 fires, 7 TRUE positives, 0 false — the
    highest precision of any detector here, and it found defects in two videos every text-based
    signal reported clean (DmgujoZ1mmk#32 at 106 ch/s, W5cga7xipRI#23 at 70 ch/s).
    FALSE POSITIVE: a genuinely clipped span on an otherwise sound sentence — whisper occasionally
    under-stamps the last word of a segment. None observed at 40 ch/s, but the failure mode is
    a timing artifact rather than a text one, so a fire means "check the SPAN", not "the text is
    wrong". The two can be distinguished by reading the sentence: garbled text plus a short span
    is a collapse; sound text plus a short span is a stamping error.
    KNOWN MISS: a repetition loop stamped across a PLAUSIBLE span is invisible here — that is
    the class dup_adjacent covers. The two detectors are complementary by construction; neither
    subsumes the other.
"""

from __future__ import annotations

import difflib
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
# RU markers: не/ни/без/бес as word-INITIAL PREFIXES — catches непросто/нельзя/никогда and
# the bound бес-/без- of бесполезный. без/бес is one marker split by voicing assimilation, so
# both spellings are matched symmetrically with не/ни; standalone "без" still matches ([а-я]*
# takes zero chars). Text is casefolded + ё->е before this runs, which is what makes the [а-я]
# class (no ё) correct — do not reorder those two steps.
#
# _NEG_POSITIVE_STEMS is the ONE place this detector deliberately breaks the "over-match is the
# safe direction" rule that governs the rest of the module, and it must not be deleted as
# redundant. Those stems are etymologically privative but semantically POSITIVE (безопасный =
# safe, бесплатный = free), so counting them as surviving negation makes the detector blind to
# exactly the inversion it exists to catch: "it is not safe" -> "это безопасно" reads as a kept
# negation and passes silently. Prefer-miss is the module default, but DECISIONS 2026-07-19
# carves neg_loss out of it by name — "an inverted negation is the most dangerous silent loss
# there is, and one false positive per batch is a fair price for never missing one" — so here a
# FALSE POSITIVE ("it is not dangerous" -> "это безопасно") is the correct trade.
# Measured on the 13-video / 1101-sentence batch: zero effect either way (0 negated-safety
# constructions), so this closes a LATENT hole and costs nothing observed.
_NEG_POSITIVE_STEMS = "опасн|платн|условн|обидн|конечн|ед"   # безопасн-, бесплатн-, ..., бесед-
_RU_NEG_RE = re.compile(
    r"(?<![а-я])(?:не|ни)[а-я]*"
    rf"|(?<![а-я])бе[зс](?!{_NEG_POSITIVE_STEMS})[а-я]*"
)


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
        if len(base) >= 3 and base.endswith("s") and base[:-1].isupper():  # plural acronym: LLMs
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


# --- adjacent-duplicate detector (cross-sentence, EN source) ------------------
# Ratio above which an adjacent pair is a duplicate. NOT a tuned knob: on the 13-video /
# 1101-sentence batch EVERY threshold in 0.70..0.95 yields the same single fire (ytEN_iAk09c
# 7/8, ratio 1.0000). The true positive sits in a 0.30-wide empty band above the loudest
# benign pair (0.6977). A Config field would imply a tuning problem that does not exist.
_DUP_RATIO_MIN = 0.80
# Min length (chars) of the FIRST member for a pair to be eligible — a repeated short
# interjection ("Yeah." / "Yeah.") is speech, not a defect. INERT on the current batch (the
# fire set is identical at every guard length 0..40): kept as a cheap structural guard for
# more conversational corpora, NOT as a validated constant. Do not cite it as measured.
_DUP_MIN_LEN = 25
# Containment = longest common SUBSTRING / len(shorter member). The second signal, and the one
# that earns its keep: the symmetric ratio above only sees the verbatim ECHO class, which is 1 of
# the 3 repetition defects in this corpus. A whisper RESTART re-speaks part of the previous line
# and then continues, so the shared span is large but the ratio is dragged down by the new tail —
# ratio calls x7DfiXqSEdM 298/299 a 0.6977 and 2YCaBqP8muw 16/17 a 0.6569, both real defects,
# both below any usable ratio threshold. Containment scores those 0.9677 and 0.9167.
#
# 0.85 is a HYPOTHESIS, not a measured constant — say so out loud, because _DUP_RATIO_MIN's
# comment above earns the opposite claim and the two must not be read the same way. It rests on
# 3 true positives (1.0000 / 0.9677 / 0.9167) against a loudest benign pair at 0.7188, so the
# empty band is 0.20 wide but the positive sample is tiny. Re-validate when the corpus grows; a
# benign long quotation restated verbatim inside a longer sentence is the FP shape to watch for.
_DUP_CONTAINMENT_MIN = 0.85


def _containment(a: str, b: str) -> float:
    """Longest common substring length / length of the SHORTER input (0.0 when either is empty).

    Asymmetric-by-design companion to SequenceMatcher.ratio(): it answers "is one of these
    largely contained in the other" rather than "are these the same size and shape", which is
    exactly the difference between a whisper restart and two distinct sentences.
    """
    if not a or not b:
        return 0.0
    match = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(
        0, len(a), 0, len(b))
    return match.size / min(len(a), len(b))


def duplicate_adjacent(texts: list[str]) -> dict[int, int]:
    """Map every id in a near-duplicate ADJACENT pair to its twin's id ({} when clean).

    Cross-sentence, so it cannot live in check() — see the module docstring's dup_adjacent
    entry. `texts` is the EN SOURCE in id order; index == sentence id, which holds because
    the caller guarantees contiguous 0..n-1 ids (verify.py enforces this). Pure,
    deterministic, no I/O.

    A pair fires when the FIRST member is longer than _DUP_MIN_LEN chars AND either signal
    trips: character-level ratio > _DUP_RATIO_MIN (the verbatim ECHO) or containment >
    _DUP_CONTAINMENT_MIN (the RESTART, where one line is largely swallowed by its neighbour).
    The two are OR-ed because they target disjoint failure shapes — see each constant's comment
    for what it is worth and how well it is grounded; they are NOT equally validated.
    Both ids are mapped, each to the other. In a run of 3+ identical sentences every member is
    flagged and the interior members keep their LAST twin (id 1 of a 0/1/2 run maps to 2, not 0)
    — the flag is the signal, the twin id is a triage convenience, not a complete adjacency graph.

    autojunk=False mirrors the repo's already-settled similarity metric (PLAN "Open questions":
    char-level SequenceMatcher(autojunk=False)) and removes a length-dependent behaviour cliff
    at 200 chars, which matters here because sentences reach 238 (MAX_CHARS is 240). It changes
    NO decision on the current corpus: autojunk only suppresses the LOW-similarity range
    (measured 0.0067 vs 0.2761 on a real long pair) and leaves high-similarity pairs untouched
    (a 209/211-char near-duplicate scores 0.9810 either way), so it can neither add nor remove
    a fire at 0.80. Chosen for consistency and one less size-dependent rule, not for recall.
    """
    dup: dict[int, int] = {}
    for i in range(len(texts) - 1):
        a, b = texts[i] or "", texts[i + 1] or ""
        if len(a) <= _DUP_MIN_LEN:
            continue
        ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
        if ratio > _DUP_RATIO_MIN or _containment(a, b) > _DUP_CONTAINMENT_MIN:
            dup[i] = i + 1
            dup[i + 1] = i
    return dup


# --- implausible speech-rate detector (per sentence, EN source + timing) ------
# Chars/second above which a source sentence cannot have been SPOKEN. This is the only
# threshold in this module sited on a physical bound rather than on corpus separation, which is
# why it is the best-grounded one here: human speech tops out near 25-30 ch/s, and the corpus
# agrees (1100 sentences: median 16.75, p95 23.97, p99 34.26). 40 sits above every plausible
# utterance and an order of magnitude below the defects (70-246 ch/s).
# Measured: 7 fires in 1100 sentences, 7 true positives, 0 false positives.
_RATE_MAX_CPS = 40.0
# Ignore very short sentences: on a 3-word interjection a 0.1 s stamping error alone can push
# the rate over the bound. INERT on this corpus (every true fire is >= 53 chars) — a structural
# guard, not a measured constant.
_RATE_MIN_LEN = 20


def implausible_rate(texts: list[str], durations: list[float]) -> dict[int, float]:
    """Map each id whose source sentence is spoken impossibly fast to its chars/second.

    The one detector that reads TIMING rather than text, and the only one that can see a
    repetition loop the text comparisons structurally cannot: `duplicate_adjacent` is pairwise,
    so a loop spanning non-adjacent sentences is invisible to it, while a collapsed alignment
    always shows up here regardless of what the text says or where its twin sits. It also
    catches garbled output that repeats nothing at all (a whisper hallucination stamped onto a
    fraction of a second), which no similarity metric can reach.

    `texts` and `durations` are parallel, in id order; index == sentence id, on the same
    contiguous-ids guarantee `duplicate_adjacent` relies on. Non-positive durations are skipped
    rather than treated as infinitely fast — a missing timestamp is not evidence of a defect.
    Pure, deterministic, no I/O.
    """
    bad: dict[int, float] = {}
    for i, (text, dur) in enumerate(zip(texts, durations)):
        text = text or ""
        if len(text) < _RATE_MIN_LEN or not dur or dur <= 0:
            continue
        cps = len(text) / dur
        if cps > _RATE_MAX_CPS:
            bad[i] = round(cps, 2)
    return bad


# --- public API ---------------------------------------------------------------
def check(src_en: str, text_ru: str, cfg) -> dict:
    """Run the four PER-SENTENCE completeness detectors on one sentence pair.

    Returns a dict with the per-sentence signals and a `flags` list (subset of
    ["num_loss", "neg_loss", "entity_loss", "length_short"], empty when clean). Deterministic,
    no I/O. See the module docstring for each detector's rule and false-positive caveat. The
    fifth flag, dup_adjacent, is cross-sentence and comes from duplicate_adjacent() — it can
    never appear in this function's output.
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
