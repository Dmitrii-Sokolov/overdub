"""TTS text normalization: digits / units / acronyms / Latin / symbols -> spoken Russian.

Pure, deterministic, no I/O, no LLM. Two public functions:

  normalize_for_tts(text)      -> TTS-ready Russian (engine-neutral). Output alphabet is
                                  Cyrillic-only (no digits, no Latin letters) => the
                                  function is IDEMPOTENT.
  normalize_for_compare(text)  -> the single "same normalizer on both sides" transform the
                                  verify stage applies to BOTH text_tts and the ASR hypothesis.

Latin / proper-noun resolution lives in pronounce.py (phrases -> words -> plural ->
case-gated acronyms -> letter names -> rule transliteration), wired in as passes 0a/1b
and the pass-6 resolver below.

Why idempotency matters (the verify coupling): the translate stage stores
`text_tts = normalize_for_tts(text_ru)`. The verify stage compares
`normalize_for_compare(text_tts)` against `normalize_for_compare(whisper_hypothesis)`.
Because normalize_for_tts leaves no digits/Latin, re-applying it inside
normalize_for_compare is a no-op on text_tts — so both sides pass through identical
code and a correct dub can never be false-flagged on a number it spelled out itself.

SAFETY-CRITICAL: because verify normalizes BOTH sides with this same code, a magnitude bug
here (a number voiced with the wrong value) is INVISIBLE to the verify round-trip — it
self-agrees and passes unflagged. Number handling must therefore be tested directly, not
only through the round-trip. See tests/test_normalize.py. Pronunciation expansions
(pronounce.py) self-agree in verify exactly like number expansions — gated only by the
direct goldens in tests/test_pronounce.py.

Known PoC loss (documented, accepted): num2words yields nominative case, so numbers in
oblique contexts ("в 2021 году", "2 карты") are occasionally voiced in the wrong
grammatical form. This is SELF-CONSISTENT for verify (both sides share the expansion) and
audibly-rough-but-not-silent. The feminine 1/2 fixup below blunts the most frequent case.
"""

from __future__ import annotations

import re

from . import pronounce

# --- number spelling (num2words with a stdlib hand-rolled fallback) ------------
_ONES_M = ["ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_ONES_F = ["ноль", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
_TEENS = ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать",
          "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
_TENS = ["", "", "двадцать", "тридцать", "сорок", "пятьдесят",
         "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
_HUNDREDS = ["", "сто", "двести", "триста", "четыреста", "пятьсот",
             "шестьсот", "семьсот", "восемьсот", "девятьсот"]


def _plural(n: int, one: str, few: str, many: str) -> str:
    """Russian count agreement: 1 -> one, 2-4 -> few, else many (11-14 -> many)."""
    n = abs(n) % 100
    if 11 <= n <= 14:
        return many
    d = n % 10
    if d == 1:
        return one
    if 2 <= d <= 4:
        return few
    return many


def _below_1000(n: int, feminine: bool = False) -> str:
    ones = _ONES_F if feminine else _ONES_M
    parts: list[str] = []
    h, rem = divmod(n, 100)
    if h:
        parts.append(_HUNDREDS[h])
    t, o = divmod(rem, 10)
    if t == 1:
        parts.append(_TEENS[o])
    else:
        if t:
            parts.append(_TENS[t])
        if o:
            parts.append(ones[o])
    return " ".join(parts)


def _hand_int(n: int) -> str:
    """Stdlib fallback speller (0..999_999_999), used only if num2words is unavailable."""
    if n == 0:
        return "ноль"
    neg, n = n < 0, abs(n)
    out: list[str] = []
    million, rem = divmod(n, 1_000_000)
    thousand, unit = divmod(rem, 1000)
    if million:
        out += [_below_1000(million), _plural(million, "миллион", "миллиона", "миллионов")]
    if thousand:
        out += [_below_1000(thousand, feminine=True), _plural(thousand, "тысяча", "тысячи", "тысяч")]
    if unit:
        out.append(_below_1000(unit))
    res = " ".join(p for p in out if p)
    return ("минус " + res) if neg else res


def _n2w(n: int) -> str:
    try:
        from num2words import num2words
        return num2words(int(n), lang="ru")
    except Exception:
        return _hand_int(int(n))


def _feminize(words: str) -> str:
    """один/два -> одна/две at the tail, for a following feminine unit (2 секунды -> две секунды)."""
    words = re.sub(r"один$", "одна", words)
    words = re.sub(r"два$", "две", words)
    return words


def _spell_decimal(s: str) -> str:
    intp, _, frac = s.replace(",", ".").partition(".")
    words = _n2w(int(intp) if intp else 0) + " целых"
    if frac:
        words += " " + _n2w(int(frac))
    return words


def _spell_num(s: str) -> str:
    """Spell a numeric literal string, integer or decimal."""
    return _spell_decimal(s) if ("." in s or "," in s) else _n2w(int(s))


def _bare_num(m: re.Match) -> str:
    return _spell_num(m.group(0))


# --- units: token -> (feminine, one, few, many) genitive-count forms ----------
_UNITS = {
    "gb": (False, "гигабайт", "гигабайта", "гигабайт"), "гб": (False, "гигабайт", "гигабайта", "гигабайт"),
    "mb": (False, "мегабайт", "мегабайта", "мегабайт"), "мб": (False, "мегабайт", "мегабайта", "мегабайт"),
    "tb": (False, "терабайт", "терабайта", "терабайт"), "тб": (False, "терабайт", "терабайта", "терабайт"),
    "kb": (False, "килобайт", "килобайта", "килобайт"), "кб": (False, "килобайт", "килобайта", "килобайт"),
    "ghz": (False, "гигагерц", "гигагерца", "гигагерц"), "ггц": (False, "гигагерц", "гигагерца", "гигагерц"),
    "mhz": (False, "мегагерц", "мегагерца", "мегагерц"), "мгц": (False, "мегагерц", "мегагерца", "мегагерц"),
    "ms": (True, "миллисекунда", "миллисекунды", "миллисекунд"), "мс": (True, "миллисекунда", "миллисекунды", "миллисекунд"),
    "kg": (False, "килограмм", "килограмма", "килограммов"), "кг": (False, "килограмм", "килограмма", "килограммов"),
    "km": (False, "километр", "километра", "километров"), "км": (False, "километр", "километра", "километров"),
    "w": (False, "ватт", "ватта", "ватт"), "вт": (False, "ватт", "ватта", "ватт"),
    "fps": (False, "кадр в секунду", "кадра в секунду", "кадров в секунду"),
}
_UNIT_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s?(" + "|".join(sorted(_UNITS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _num_unit(m: re.Match) -> str:
    num_str, unit = m.group(1), m.group(2).lower()
    fem, one, few, many = _UNITS[unit]
    if re.fullmatch(r"\d+", num_str):
        n = int(num_str)
        w = _n2w(n)
        if fem:
            w = _feminize(w)
        return f"{w} {_plural(n, one, few, many)}"
    return f"{_spell_decimal(num_str)} {few}"      # decimal -> genitive singular-ish


# separators used for grouped thousands: NBSP, narrow-NBSP, thin space, regular space
_GROUP_SEP = re.compile(r"(?<=\d)[    ](?=\d{3}(?!\d))")
_GROUP_COMMA = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")


# --- dual-form markup ---------------------------------------------------------
# A translator writes ONE string carrying both forms of anything that is written differently
# from how it is said: [[RTX 4080|эр-ти-экс четыре тысячи восемьдесят]]. The two readers below
# collapse it in opposite directions, and that is the whole mechanism — subtitles keep the
# WRITTEN form, synthesis gets the SPOKEN one.
#
# It exists because the two consumers genuinely want different text and the pipeline used to
# have only one source for both. Spelling the reading into text_ru made the subtitles unreadable;
# leaving Latin in handed the token to the pronounce chain's SPELLING-based fallback, which
# invents a reading — 756 of them over 261 distinct tokens on one video of the 2026-08-10 batch
# ("буттон" for button), a wrongness verify cannot hear. Silero's outright deletion of Latin is
# real (measured 2026-08-11) but never fires: normalize_for_tts is Cyrillic-only by contract, so
# the engine never sees a Latin character. The translator has the sentence and the rolling
# terminology; a letter table has neither.
#
# Non-greedy on both sides so two spans in one sentence do not merge into one. A `|`-less or
# unterminated `[[` is left ALONE rather than repaired: it then shows up as literal brackets in
# a subtitle, which is visible and cheap, where a guess would be silent.
_DUAL = re.compile(r"\[\[([^\[\]|]*)\|([^\[\]|]*)\]\]")


def written_form(text: str) -> str:
    """Subtitle side: keep what it LOOKS like, drop the reading."""
    return _DUAL.sub(lambda m: m.group(1), text)


def spoken_form(text: str) -> str:
    """Synthesis side: keep what it SOUNDS like, drop the spelling.

    Feed the result to normalize_for_tts as usual — it stays the net for everything the
    translator did not mark, so an unmarked number is still voiced rather than read as digits.
    """
    return _DUAL.sub(lambda m: m.group(2), text)


# --- ordered passes -----------------------------------------------------------
def normalize_for_tts(text: str) -> str:
    """Expand digits/units/acronyms/Latin/symbols to spoken Russian words.
    Punctuation- and case-preserving (TTS prosody). Output has no [0-9A-Za-z] => idempotent.
    """
    t = text

    # 0a. multiword names on RAW text: phrase keys may contain digits/apostrophes/hyphens,
    #     so this MUST precede every numeric pass; outputs are Cyrillic => inert downstream
    t = pronounce.replace_phrases(t)

    # 0. collapse grouped thousands so MAGNITUDE survives (BEFORE any number pass):
    #    "10 000"/"1 000 000" (space-grouped) and "1,999"/"1,000,000" (English comma-grouped).
    #    Guard (?!\d) restricts to exactly-3-digit groups so a decimal comma ("3,5") is left alone.
    t = _GROUP_SEP.sub("", t)
    t = _GROUP_COMMA.sub("", t)

    # 1. symbolic / shorthand (must run before bare-number spelling consumes the digits).
    #    Multiplier classes are Latin-only (x/X/×): Cyrillic 'х' collides with real words
    #    ("по оси х", "в 90х годах") — never treat it as a multiplier.
    t = re.sub(r"\b24\s?/\s?7\b", "круглосуточно", t)
    t = re.sub(r"(?<![A-Za-zА-Яа-я0-9])[xX×]\s?(\d+)(?![A-Za-zА-Яа-я])",
               lambda m: f"в {_n2w(int(m.group(1)))} {_plural(int(m.group(1)), 'раз', 'раза', 'раз')}", t)
    t = re.sub(r"(?<![A-Za-zА-Яа-я])(\d+)\s?[xX×](?![A-Za-zА-Яа-я0-9])",
               lambda m: f"в {_n2w(int(m.group(1)))} {_plural(int(m.group(1)), 'раз', 'раза', 'раз')}", t)
    t = re.sub(r"(\d+[.,]\d+)\s?%", lambda m: f"{_spell_decimal(m.group(1))} процента", t)
    t = re.sub(r"(\d+)\s?%", lambda m: f"{_n2w(int(m.group(1)))} {_plural(int(m.group(1)), 'процент', 'процента', 'процентов')}", t)
    t = re.sub(r"\$\s?(\d+[.,]\d+)", lambda m: f"{_spell_decimal(m.group(1))} доллара", t)
    t = re.sub(r"\$\s?(\d+)", lambda m: f"{_n2w(int(m.group(1)))} {_plural(int(m.group(1)), 'доллар', 'доллара', 'долларов')}", t)
    t = re.sub(r"(\d+)\s?\$", lambda m: f"{_n2w(int(m.group(1)))} {_plural(int(m.group(1)), 'доллар', 'доллара', 'долларов')}", t)
    t = re.sub(r"€\s?(\d+)", lambda m: f"{_n2w(int(m.group(1)))} евро", t)
    t = re.sub(r"(\d+)\s?€", lambda m: f"{_n2w(int(m.group(1)))} евро", t)
    # Celsius: the letter must not be glued to a following word ("90° севернее" must NOT eat 'с')
    t = re.sub(r"(\d+)\s?°\s?[CСcс](?![A-Za-zА-Яа-яЁё])",
               lambda m: f"{_n2w(int(m.group(1)))} {_plural(int(m.group(1)), 'градус', 'градуса', 'градусов')} цельсия", t)
    t = re.sub(r"(\d+)\s?°",
               lambda m: f"{_n2w(int(m.group(1)))} {_plural(int(m.group(1)), 'градус', 'градуса', 'градусов')}", t)

    # 1b. split letter<->digit seams so PS5 / mp3 / 4K resolve as letters + number.
    #     AFTER pass 1 on purpose: glued NxM (1920x1080, 8x8) must stay glued there so the
    #     multiplier's own digit guards reject it — splitting first would assert "в N раз"
    #     semantics on resolutions/grids. Units unaffected: _UNIT_RE tolerates the space.
    t = pronounce.ALNUM_BOUNDARY.sub(" ", t)

    # 2. numeric range (decimal-aware, boundary-guarded): "10-20" / "3.5-4.5" -> "от … до …"
    t = re.sub(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s?[-–—]\s?(\d+(?:[.,]\d+)?)(?![\d.,])",
               lambda m: f"от {_spell_num(m.group(1))} до {_spell_num(m.group(2))}", t)

    # 3. number + unit (before bare numbers)
    t = _UNIT_RE.sub(_num_unit, t)

    # 4. bare numbers (integers + decimals)
    t = re.sub(r"\d+(?:[.,]\d+)?", _bare_num, t)

    # 5. standalone operator symbols
    t = re.sub(r"(?<=\s)\+(?=\s)", "плюс", t)
    t = re.sub(r"(?<=\s)=(?=\s)", "равно", t)
    t = t.replace("&", " и ")

    # 6. Latin resolution (never leave Latin — neural TTS can't voice it); phrases were
    #    handled in 0a, the token shape keeps possessives whole ("Man's" reaches the
    #    resolver as ONE token — no stranded apostrophe)
    t = pronounce.TOKEN_RE.sub(lambda m: pronounce.resolve_token(m.group(0)), t)

    # 7. collapse whitespace (keep punctuation for prosody)
    t = re.sub(r"[ \t]+", " ", t).strip()
    return t


def normalize_for_compare(text: str) -> str:
    """The single canonicalizer the verify stage applies to BOTH sides before similarity:
    full TTS normalization, then casefold, ё->е, strip punctuation, collapse whitespace."""
    t = normalize_for_tts(text).casefold().replace("ё", "е")
    # Stress marks are DELETED, not blanked. Silero takes "+" before the stressed vowel and
    # dictionary values carry it (pronounce.WORDS), but the punctuation pass below turns every
    # non-word char into a SPACE — "р+еддит" would become two tokens and the round-trip would
    # score a correct reading as a defect. Must precede that pass.
    t = t.replace("+", "")
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t
