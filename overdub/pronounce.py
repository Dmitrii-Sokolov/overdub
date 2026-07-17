"""Latin / proper-noun pronunciation: phrase dict + word dict + rule transliteration.

Pure, deterministic, no I/O — module-level data only, compiled at import. normalize.py
wires this in as pass 0a (phrases), pass 0b (letter<->digit seams) and the pass-6 token
resolver; normalize_for_compare calls normalize_for_tts, so the verify stage and the
synthesize reseed loop inherit IDENTICAL resolution on both sides automatically.

Resolution chain (first hit wins): PHRASES -> WORDS -> plural tail -> _ACRONYMS
(case-gated, trailing-S plurals resolve through the singular) -> letter names (single /
unknown all-caps / all-caps plural stems) -> transliterate_en (rules; vowel-less rule
output is letter-spelled instead — the net that keeps the скй class out).

SAFETY-CRITICAL: verify normalizes both sides with this same data, so a wrong dictionary
expansion self-agrees and passes unflagged (corpus proof: broken-translit sims sat at
0.93-0.97, only id189 ever flagged); every PHRASES/WORDS entry and every fallback rule is
gated ONLY by the direct goldens in tests/test_pronounce.py — the round-trip cannot catch
them.

Accepted irregularity: the rule fallback targets *pronounceable and recognizable*, not
correct — минекрафт/тво/йаутюб-class misses are dictionary work. The vowel-less cluster
(sky -> скй, the id150 ear class) IS structurally excluded: acronym plurals (GPUs/LLMs)
resolve through the singular, unknown all-caps plural stems (NPCs) are letter-spelled,
and any rule output without a Cyrillic vowel (brb/hmm) is letter-spelled instead
(tested, incl. adversarial non-corpus tokens). Ceiling ~55 rules; anything needing
context beyond "position + neighbor" goes to the dict.
"""

from __future__ import annotations

import re

# --- multiword names, replaced on RAW text (pass 0a) ---------------------------
# Policy: a phrase earns a slot ONLY when word-by-word resolution (WORDS + rules) cannot
# produce the target. Composable titles (call of duty, xbox live, it takes two, deep rock
# galactic, half-life, counter-strike, world of warcraft, ...) are pinned by goldens
# instead. Keys: lowercase, single-spaced, "'" for apostrophes (digits allowed — pass 0a
# runs before every numeric pass).
PHRASES = {
    "no man's sky": "ноу мэнс скай",        # id150 ear case; composition impossible (no->но, mans->манс)
    "marvel rivals": "марвел райвалс",      # rivals not rule-reachable (ривалс)
    "dark souls": "дарк соулс",             # souls not rule-reachable (саулс)
    "super smash bros": "супер смэш брос",  # corpus id19; смэш not rule-reachable (смаш)
    # arch tokens: pass 1 would misread the glued x-digit shape as a multiplier ("в 86 раз")
    "x86": "икс восемьдесят шесть",
    "x64": "икс шестьдесят четыре",
}

# a possessive tail after the phrase is consumed and DROPPED ("No Man's Sky's" must not
# strand an apostrophe in text_tts); the trailing boundary also rejects 'x-suffix shapes
_PHRASE_RE = re.compile(
    "(?<![A-Za-z0-9])(?:" + "|".join(
        re.escape(k).replace("'", "['’]")
        for k in sorted(PHRASES, key=len, reverse=True)       # longest-match-first
    ) + ")(?:['’]s)?(?!['’]?[A-Za-z0-9])",
    re.IGNORECASE,
)


def _phrase_sub(m: re.Match) -> str:
    key = m.group(0).lower().replace("’", "'")
    if key not in PHRASES and key.endswith("'s"):
        key = key[:-2]                                        # consumed possessive tail
    return PHRASES[key]


def replace_phrases(text: str) -> str:
    return _PHRASE_RE.sub(_phrase_sub, text)


# --- single-word dictionary ----------------------------------------------------
# Keys lowercase single words, values lowercase Cyrillic. No key may shadow an _ACRONYMS
# case-gate (no it/id/os/ai/pc/tv/ok/io). Leaked open-class English (somewhat, experience,
# gamerpals, ...) is NOT dictionary material — the rule fallback owns the unbounded tail.
# Soft cap ~150 entries; growth beyond that means the fallback needs fixing, not the dict.
# Entries marked (=) also match the rules — insurance pins against silent rule drift.
WORDS = {
    # corpus games / platforms (established RU usage)
    "youtube": "ютуб", "xbox": "иксбокс", "halo": "хейло", "minecraft": "майнкрафт",
    "valheim": "валхейм",    # (=)
    "fortnite": "фортнайт",  # (=)
    "titanfall": "титанфолл", "destiny": "дестини",  # destiny (=)
    "overcooked": "оверкукт",  # (=)
    "runescape": "рунескейп",   # camelCase "RuneScape" rules to рюнскейп (magic-e on Rune);
                                # the translate prompt now mandates exactly that casing
    "skyrim": "скайрим", "fallout": "фоллаут", "cyberpunk": "киберпанк",
    "warcraft": "варкрафт",  # (=)
    "steam": "стим",    # (=)
    "twitch": "твитч",  # (=)
    "discord": "дискорд",  # (=)
    "reddit": "реддит",    # (=)
    "bumble": "бамбл", "slack": "слэк", "netflix": "нетфликс",  # netflix (=)
    # title parts / high-frequency leaks
    "live": "лайв",  # (=)
    "sky": "скай",   # (=)
    "duty": "дьюти", "code": "код", "space": "спейс",  # space (=)
    "marine": "марин", "two": "ту", "one": "уан",
    "stream": "стрим",  # (=)
    "moba": "моба", "pvp": "пи-ви-пи", "pve": "пи-ви-и",
    "uh": "э-э", "um": "эм",           # EN hesitation -> RU filler, keeps slot timing
    # tech
    "claude": "клод",  # (=)
    "windows": "виндовс", "google": "гугл",  # google (=)
    "github": "гитхаб",                # rules give джитуб (g before i palatalizes)
    "python": "пайтон", "linux": "линукс",  # linux (=)
    "nvidia": "энвидиа",               # spoken form; dict-first beats 6-cap letter-spelling
    "intel": "интел",  # (=)
    "unity": "юнити", "unreal": "анриал", "microsoft": "майкрософт",
    "apple": "эппл", "iphone": "айфон",
    "qwen": "квен",      # (=)
}

# --- acronyms / letter names (moved from normalize.py; the old plural keys GPUS/APIS
# are gone — _resolve strips a trailing S and reads the singular, for ALL acronyms) ------
_ACRONYMS = {
    "GPU": "джи-пи-ю", "CPU": "си-пи-ю", "RTX": "эр-ти-икс",
    "GTX": "джи-ти-икс", "VRAM": "ви-рам", "RAM": "рам", "ROM": "ром", "SSD": "эс-эс-ди",
    "HDD": "эйч-ди-ди", "USB": "ю-эс-би", "AI": "эй-ай", "API": "эй-пи-ай",
    "LLM": "эл-эл-эм", "ML": "эм-эл", "OS": "оу-эс", "PC": "пи-си", "TV": "ти-ви",
    "URL": "ю-ар-эл", "HTTP": "эйч-ти-ти-пи", "HTTPS": "эйч-ти-ти-пи-эс", "HTML": "эйч-ти-эм-эл",
    "CSS": "си-эс-эс", "SQL": "эс-кью-эл", "JSON": "джейсон", "PDF": "пи-ди-эф",
    "ID": "ай-ди", "IO": "ай-о", "OK": "окей", "FAQ": "эф-эй-кью", "CEO": "си-и-о", "IT": "ай-ти",
}
_LETTER_NAMES = {
    "A": "эй", "B": "би", "C": "си", "D": "ди", "E": "и", "F": "эф", "G": "джи", "H": "эйч",
    "I": "ай", "J": "джей", "K": "кей", "L": "эл", "M": "эм", "N": "эн", "O": "оу", "P": "пи",
    "Q": "кью", "R": "ар", "S": "эс", "T": "ти", "U": "ю", "V": "ви", "W": "дабл-ю",
    "X": "экс", "Y": "уай", "Z": "зет",
}

# pass-6 token shape (possessives stay ONE token: Man's) and the letter<->digit seam
# splitter (PS5 / qwen3 / 4K); normalize.py imports both — the import direction is
# strictly normalize -> pronounce
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
ALNUM_BOUNDARY = re.compile(r"(?<=[0-9])(?=[A-Za-z])|(?<=[A-Za-z])(?=[0-9])")

# --- rule fallback: ordered left-to-right practical-transcription scanner ------
# At each cursor position the FIRST matching rule wins and the cursor advances by the
# match length; lookarounds see the ORIGINAL ASCII word; "^" matches only at part start
# (re.match(word, i) semantics). Guards: "V+" needs a vowel [aeiouy] before the cursor,
# "V-" needs none of [aeiou] before it ("red"/"the" are not inflected forms).
_CME = "[bcdfgklmnpstvz]"        # consonants that keep magic-e vowels long
_CONS = "[bcdfghjklmnpqrstvwxz]"
_ETAIL = "(e|es|ed|er|ers|ing)$"  # magic-e tails incl. derived forms: gamer, gaming
_RULES: list[tuple[re.Pattern[str], str, str | None]] = [
    (re.compile(p), out, guard) for p, out, guard in [
        # multigraphs / silent starts / no-stray-vowel endings
        ("a(?=tion)", "ей", None),                            # nation -> нейшн, not нашн
        ("tion", "шн", None), ("eigh", "ей", None), ("igh", "ай", None), ("tch", "тч", None),
        ("^kn", "н", None), ("^wr", "р", None),
        ("gue$", "г", "V+"), ("que$", "к", "V+"),             # league -> лиг, unique -> уник
        # magic-e long vowels: takes -> тейкс, fortnite -> фортнайт, gamer -> геймер
        (f"a(?={_CME}{_ETAIL})", "ей", None), (f"i(?={_CME}{_ETAIL})", "ай", None),
        (f"o(?={_CME}{_ETAIL})", "оу", None), (f"u(?={_CME}{_ETAIL})", "ю", None),
        (f"y(?={_CME}{_ETAIL})", "ай", None),
        (f"all(?=$|{_CONS})", "ол", None),                    # call -> кол (gallery unaffected)
        # vowel digraphs
        ("ee", "и", None), ("ea", "и", None), ("oo", "у", None), ("oa", "оу", None),
        ("ou", "ау", None), ("ow(?=s?$)", "оу", None), ("ow", "ау", None),
        ("ai", "ей", None), ("ay", "ей", None), ("ei", "ей", None), ("ey", "ей", None),
        ("ew(?!h)", "ью", None),                              # new -> нью; somewhat stays off ью
        ("oy", "ой", None), ("oi", "ой", None), ("au", "о", None), ("aw", "о", None),
        ("ie$", "и", None),           # word-final only (movie/cookie); experience keeps и+е
        # consonant digraphs
        ("sh", "ш", None), ("ch", "ч", None), ("ck", "к", None), ("ph", "ф", None),
        ("th", "т", None), ("wh", "у", None), ("qu", "кв", None),
        # inflection tails
        ("(?<=[pkfsx])ed$", "т", "V+"), ("(?<=[td])ed$", "ед", "V+"), ("ed$", "д", "V+"),
        ("(?<=[csxz])es$", "ес", "V+"), ("es$", "с", "V+"),
        (f"(?<={_CONS})e$", "", "V+"),                        # silent final e: google -> гугл
        # context singles
        ("c(?=[eiy])", "с", None), ("c", "к", None),
        ("g(?=[eiy])", "дж", None), ("g", "г", None),
        ("y(?=[aeiou])", "й", None),
        ("y$", "ай", "V-"),                                   # the anti-скй rule: sky -> скай
        ("y$", "и", None), ("y", "и", None),
        ("^e", "э", None),
        # base map (totality: every remaining ASCII letter has a Cyrillic output)
        ("a", "а", None), ("b", "б", None), ("d", "д", None), ("e", "е", None),
        ("f", "ф", None), ("h", "х", None), ("i", "и", None), ("j", "дж", None),
        ("k", "к", None), ("l", "л", None), ("m", "м", None), ("n", "н", None),
        ("o", "о", None), ("p", "п", None), ("q", "к", None), ("r", "р", None),
        ("s", "с", None), ("t", "т", None), ("u", "у", None), ("v", "в", None),
        ("w", "в", None), ("x", "кс", None), ("z", "з", None),
    ]
]
_HAS_VY = re.compile(r"[aeiouy]")
_HAS_V = re.compile(r"[aeiou]")
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _scan(word: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(word):
        for pat, rep, guard in _RULES:
            m = pat.match(word, i)
            if m is None:
                continue
            if guard == "V+" and not _HAS_VY.search(word, 0, i):
                continue
            if guard == "V-" and _HAS_V.search(word, 0, i):
                continue
            out.append(rep)
            i = m.end()
            break
        # no else: the base map is total over a-z, the inner for always breaks
    return "".join(out)


def transliterate_en(word: str) -> str:
    """Rule fallback: practical EN->RU transcription of one token. camelCase parts are
    transliterated separately (each with its own word-final context) and joined with no
    separator (DeathLoop -> дитлуп); apostrophes are dropped (Man's -> манс)."""
    word = word.replace("'", "").replace("’", "")
    return "".join(_scan(p.lower()) for p in _CAMEL.sub(" ", word).split(" ") if p)


_CYR_VOWEL = re.compile(r"[аеёиоуыэюя]")


def _resolve(tok: str) -> tuple[str, str]:
    """(via, spoken) for one pass-6 token; precedence is the module contract."""
    low = tok.lower()
    if low in WORDS:                                          # also catches NVIDIA/MOBA/PVP
        return "word", WORDS[low]
    if low.endswith("s") and low[:-1] in WORDS:               # plural tail: iphones -> айфонс
        return "word", WORDS[low[:-1]] + "с"
    up = tok.upper().replace("'", "").replace("’", "")        # IT'S -> ITS for letter branches
    # plural-caps shape (GPUs/NPCs); stem >= 2 letters so "As"/"Is" stay ordinary words
    plural_caps = len(tok) > 2 and tok[:-1].isupper() and tok[-1] in "sS"
    if tok.isupper() or plural_caps:                          # case-gated: It/Ok never match
        if up in _ACRONYMS:                                   # exact first: HTTPS is not HTTP+s
            return "acronym", _ACRONYMS[up]
        if up.endswith("S") and up[:-1] in _ACRONYMS:         # GPUs/LLMs: RU acronym reading
            return "acronym", _ACRONYMS[up[:-1]]              # is number-neutral, no plural mark
    if len(up) == 1:                                          # single letter, ANY case: r -> ар
        return "letters", _LETTER_NAMES[up]
    if tok.isupper() and len(up) <= 6:                        # unknown all-caps run -> letter names
        return "letters", "-".join(_LETTER_NAMES[c] for c in up)
    if plural_caps and len(up) - 1 <= 6:                      # NPCs -> эн-пи-си (stem, number-neutral)
        return "letters", "-".join(_LETTER_NAMES[c] for c in up[:-1])
    spoken = transliterate_en(tok)                            # incl. all-caps > 6: STALKER
    if not _CYR_VOWEL.search(spoken):                         # vowel-less cluster (brb -> брб):
        return "letters", "-".join(_LETTER_NAMES[c] for c in up)  # the скй ear class must not ship
    return "fallback", spoken


def resolve_token(tok: str) -> str:
    return _resolve(tok)[1]


def audit_events(text: str) -> list[tuple[str, str, str]]:
    """(token_lower, via, spoken) for every token the pipeline had to INVENT — via in
    ("letters", "fallback") only; dictionary/acronym hits are by-design noise. AUDIT-ONLY
    (translate writes pronounce_audit.json from this, nothing ever reads it back):
    congruence with normalize's numeric passes is not required."""
    t = ALNUM_BOUNDARY.sub(" ", replace_phrases(text))
    events: list[tuple[str, str, str]] = []
    for m in TOKEN_RE.finditer(t):
        via, spoken = _resolve(m.group(0))
        if via in ("letters", "fallback"):
            events.append((m.group(0).lower(), via, spoken))
    return events


def audit_summary(video_id: str, records: list[dict]) -> dict:
    """Aggregate audit_events over translation records into the pronounce_audit.json shape:
    fallback entries first, then letters, alphabetical within each. Pure dict-building —
    the single source of the shape for both the translate stage and tools/renorm_workdir."""
    tokens: dict[str, dict] = {}
    for r in records:
        for low, via, spoken in audit_events(r["text_ru"]):
            e = tokens.setdefault(low, {"count": 0, "via": via, "out": spoken, "ids": []})
            e["count"] += 1
            if r["id"] not in e["ids"]:
                e["ids"].append(r["id"])
    return {"video_id": video_id,
            "tokens": dict(sorted(tokens.items(),
                                  key=lambda kv: (kv[1]["via"] != "fallback", kv[0])))}
