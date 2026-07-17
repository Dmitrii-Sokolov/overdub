"""Unit tests for overdub.pronounce — direct goldens for every expansion class.

Run: .venv-asr/Scripts/python.exe tests/test_pronounce.py   (or via pytest if installed)

DIRECT-TEST RULE: every PHRASES/WORDS entry and every fallback rule is tested here
directly; the verify round-trip can NOT catch them — both sides share this code, so a
wrong expansion self-agrees and passes unflagged.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.normalize import normalize_for_compare, normalize_for_tts  # noqa: E402
from overdub.pronounce import (  # noqa: E402
    _ACRONYMS, _LETTER_NAMES, PHRASES, WORDS, transliterate_en)

_ASCII_ALNUM = re.compile(r"[0-9A-Za-z]")
_VALUE_RE = re.compile(r"^[а-яё \-]+$")
_VOWELS = re.compile(r"[аеёиоуыэюя]")

# through normalize_for_tts, exact match
GOLDEN = {
    # id150 ear case + apostrophe variants (phrase pass)
    "No Man's Sky": "ноу мэнс скай",
    "no man's sky": "ноу мэнс скай",
    "No Man’s Sky": "ноу мэнс скай",
    "No Man's Sky's": "ноу мэнс скай",   # possessive tail consumed — no stranded apostrophe
    "Marvel Rivals": "марвел райвалс",
    "Dark Souls": "дарк соулс",
    "Super Smash Bros": "супер смэш брос",
    # corpus games / platforms
    "Minecraft": "майнкрафт", "Valheim": "валхейм",
    "Xbox": "иксбокс", "Xbox Live": "иксбокс лайв", "Xbox One": "иксбокс уан",
    "YouTube": "ютуб", "Halo": "хейло", "Halo 3": "хейло три",
    "Call of Duty": "кол оф дьюти",
    "PvP": "пи-ви-пи", "PVP": "пи-ви-пи", "PvE": "пи-ви-и",
    "MOBA": "моба",
    "Claude": "клод", "Clawed Code": "клод код",
    "Reddit": "реддит", "Discord": "дискорд", "Twitch": "твитч",
    "Fortnite": "фортнайт", "Titanfall": "титанфолл",
    "Deep Rock Galactic": "дип рок галактик", "Destiny": "дестини",
    "It Takes Two": "ит тейкс ту", "Overcooked": "оверкукт",
    "Space Marine": "спейс марин", "Bumble": "бамбл", "Slack": "слэк", "Steam": "стим",
    "Skyrim": "скайрим", "Fallout": "фоллаут", "Cyberpunk": "киберпанк",
    "Elden Ring": "элден ринг",
    "Warcraft": "варкрафт", "World of Warcraft": "ворлд оф варкрафт",
    "Half-Life": "халф-лайф", "Counter-Strike": "каунтер-страйк",
    # tech
    "Windows": "виндовс", "Windows 11": "виндовс одиннадцать",
    "Google": "гугл", "GitHub": "гитхаб", "Python": "пайтон", "Linux": "линукс",
    "NVIDIA": "энвидиа", "Intel": "интел", "Unity": "юнити", "Unreal": "анриал",
    "Microsoft": "майкрософт", "Apple": "эппл", "Netflix": "нетфликс", "iPhone": "айфон",
    # fillers / composed tokens
    "uh": "э-э", "um": "эм",
    "PS5": "пи-эс пять", "qwen3": "квен три", "F5-TTS": "эф пять-ти-ти-эс",
    "r/gamerpals": "ар/гамерпалс",
    # arch tokens are PHRASES entries — the pass-1 multiplier must never see them
    "x86": "икс восемьдесят шесть", "x64": "икс шестьдесят четыре",
    "такие как Minecraft, Valheim, uh, No Man's Sky":
        "такие как майнкрафт, валхейм, э-э, ноу мэнс скай",
}

# acronym case-gate: It/Ok must never match IT/OK; trailing-s plurals resolve through
# the singular (RU acronym reading is number-neutral); unknown all-caps plural stems are
# letter-spelled — never the rule fallback (NPCs -> нпкс was the id150 class reborn)
CASE_GUARDS = {
    "It": "ит", "it": "ит", "IT": "ай-ти",
    "Ok": "ок", "OK": "окей",
    "GPU": "джи-пи-ю", "GPUs": "джи-пи-ю", "APIs": "эй-пи-ай",
    "LLMs": "эл-эл-эм", "CPUs": "си-пи-ю",
    "NPCs": "эн-пи-си", "RPGs": "ар-пи-джи",
}

# via transliterate_en directly — snapshots against silent rule drift
FALLBACK_PINNED = {
    "clawed": "клод", "streams": "стримс", "deep": "дип", "takes": "тейкс",
    "sky": "скай", "destiny": "дестини", "space": "спейс", "fortnite": "фортнайт",
    "valheim": "валхейм", "overcooked": "оверкукт", "experience": "экспериенс",
    "gamerpals": "гамерпалс", "somewhat": "сомеуат", "galactic": "галактик",
    "rock": "рок", "counter": "каунтер", "strike": "страйк", "call": "кол",
    "half": "халф", "life": "лайф", "elden": "элден", "ring": "ринг",
    "world": "ворлд", "of": "оф", "twitch": "твитч", "google": "гугл",
    "claude": "клод", "stalker": "сталкер", "bros": "брос", "smash": "смаш",
    "quake": "квейк", "night": "найт", "know": "ноу", "the": "те",
    "DeathLoop": "дитлуп",
    # one pin per otherwise-unexercised rule — a rule with no pin is silent-drift material
    "nation": "нейшн",       # a(?=tion) + tion
    "eight": "ейт",          # eigh
    "wrap": "рап",           # ^wr
    "hype": "хайп",          # y-magic-e
    "road": "роуд",          # oa
    "down": "даун",          # mid-word ow
    "rain": "рейн",          # ai
    "day": "дей",            # ay
    "they": "тей",           # ey
    "new": "нью",            # ew(?!h)
    "boy": "бой",            # oy
    "coin": "койн",          # oi
    "movie": "мови",         # ie$
    "chat": "чат",           # ch
    "phone": "фоун",         # ph
    "started": "стартед",    # (?<=[td])ed$
    "spaces": "спейсес",     # (?<=[csxz])es$
    "crypto": "крипто",      # mid-word y
    "gaming": "гейминг",     # magic-e -ing tail (established loan, not а)
    "gamer": "геймер",       # magic-e -er tail
    "league": "лиг",         # gue$ — no stray final vowel (was лигуе)
    "unique": "уник",        # que$
    # documented-miss tier: recognizable-but-wrong, each the reason a dict entry exists
    "code": "коуд",          # dict-pinned to код: magic-e gives оу
    "two": "тво",            # dict-pinned to ту: w is not silent in the rules
    "youtube": "йаутюб",     # dict-pinned to ютуб: ou -> ау mid-word
    "marine": "марайн",      # dict-pinned to марин: magic-e fires on borrowed French
    "duty": "дути",          # dict-pinned to дьюти: no soft-consonant rule
    "windows": "виндоус",    # dict-pinned to виндовс: ow(?=s$) -> оу
    "github": "джитуб",      # dict-pinned to гитхаб: g(?=i) palatalizes, th eats the seam
    "minecraft": "минекрафт",  # dict-pinned to майнкрафт: mine-e is not word-final
}

# every Latin token that occurs in the four corpus translation.json files (text_ru)
CORPUS_TOKENS = [
    "PvP", "Xbox", "Claude", "Halo", "YouTube", "Call", "Clawed", "Code", "Discord",
    "Duty", "Live", "Man's", "No", "of", "PvE", "Reddit", "Sky", "Titanfall", "Bumble",
    "Deep", "Destiny", "experience", "Fortnite", "Galactic", "gamerpals", "It", "live",
    "Marine", "Marvel", "Minecraft", "MOBA", "Overcooked", "PS", "pvp", "r", "Rivals",
    "Rock", "somewhat", "Space", "streams", "Takes", "Twitch", "Two", "uh", "Valheim",
    "H", "I", "Slack",
]

EDGE_TOKENS = ["Man's", "F5-TTS", "qwen3", "PS5", "DeathLoop", "STALKER", "r"]

# NON-corpus adversarial tokens: acronym plurals and vowel-less leaks that once bypassed
# every guard (NPCs -> нпкс, brb -> брб) — _resolve must letter-spell all of these
ADVERSARIAL_TOKENS = ["LLMs", "PCs", "TVs", "SSDs", "NPCs", "RPGs", "brb", "hmm", "tbh", "mp3"]


def test_golden():
    for src, expected in GOLDEN.items():
        got = normalize_for_tts(src)
        assert got == expected, f"{src!r} -> {got!r}, expected {expected!r}"


def test_case_guards():
    for src, expected in CASE_GUARDS.items():
        got = normalize_for_tts(src)
        assert got == expected, f"{src!r} -> {got!r}, expected {expected!r}"


def test_fallback_pinned():
    for src, expected in FALLBACK_PINNED.items():
        got = transliterate_en(src)
        assert got == expected, f"{src!r} -> {got!r}, expected {expected!r}"


def test_data_invariants():
    for table in (PHRASES, WORDS, _ACRONYMS, _LETTER_NAMES):
        for k, v in table.items():
            assert v and _VALUE_RE.fullmatch(v), f"bad value {k!r} -> {v!r}"
    for k in PHRASES:
        assert k == k.lower() and "," not in k and "  " not in k, f"bad phrase key {k!r}"
    for k in WORDS:
        assert k == k.lower(), f"WORDS key not lowercase: {k!r}"
    shadowed = set(WORDS) & {k.lower() for k in _ACRONYMS}
    assert not shadowed, f"WORDS must not shadow the acronym case-gate: {shadowed}"


def test_corpus_tokens_pronounceable():
    # structural anti-скй: over the corpus inventory AND adversarial non-corpus leaks,
    # no output word >= 2 chars may be vowel-less (2-char clusters like мп count too)
    for tok in CORPUS_TOKENS + ADVERSARIAL_TOKENS:
        out = normalize_for_tts(tok)
        for w in re.findall(r"[а-яё]+", out.lower()):
            assert len(w) < 2 or _VOWELS.search(w), f"{tok!r} -> {out!r}: vowel-less {w!r}"


def test_no_ascii_and_idempotent():
    for src in list(GOLDEN) + list(CASE_GUARDS) + CORPUS_TOKENS + EDGE_TOKENS + ADVERSARIAL_TOKENS:
        once = normalize_for_tts(src)
        assert not _ASCII_ALNUM.search(once), f"{src!r} left ascii alnum: {once!r}"
        assert normalize_for_tts(once) == once, f"not idempotent: {src!r} -> {once!r}"


def test_compare_convergence():
    # why verify keeps working when whisper emits the Latin brand verbatim:
    # both sides converge through the same dictionary/rules
    assert (normalize_for_compare("Xbox Live или PS5")
            == normalize_for_compare("иксбокс лайв или пи-эс пять"))
    assert normalize_for_compare("No Man's Sky") == normalize_for_compare("ноу мэнс скай")


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
