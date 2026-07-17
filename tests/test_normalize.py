"""Unit tests for overdub.normalize — no live LLM, pure functions.

Run: .venv-asr/Scripts/python.exe tests/test_normalize.py   (or via pytest if installed)
Invariants: EN->RU snapshots, idempotency, Cyrillic-only output, verify-coupling no-op.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.normalize import normalize_for_compare, normalize_for_tts  # noqa: E402

_ASCII_ALNUM = re.compile(r"[0-9A-Za-z]")

SNAPSHOTS = {
    "GPU": "джи-пи-ю",
    "AI": "эй-ай",
    "API": "эй-пи-ай",
    "x2": "в два раза",
    "2x": "в два раза",
    "24/7": "круглосуточно",
    "50%": "пятьдесят процентов",
    "12 GB": "двенадцать гигабайт",
    "500 ms": "пятьсот миллисекунд",
    "2 ms": "две миллисекунды",          # feminine unit fixup: два -> две
    "RTX 4080": "эр-ти-икс четыре тысячи восемьдесят",
    "2021": "две тысячи двадцать один",
    "$5": "пять долларов",
    "1 доллар": "один доллар",
    # NxM must NOT read as a multiplier ("в 1080 раз"): 0b splits AFTER pass 1, so the
    # multiplier's own digit guards reject the glued shape (Latin goldens live in
    # test_pronounce.py — this row pins the normalize-level pass ordering)
    "1920x1080": "одна тысяча девятьсот двадцать экс одна тысяча восемьдесят",
}

IDEMPOTENT_INPUTS = [
    "The RTX 4080 has 12 GB of VRAM and is 2x faster, up to 50%.",
    "Модель qwen3:14b занимает 9 GB видеопамяти.",
    "Это обычное русское предложение без цифр.",
    "GPU, CPU и 24/7 нагрузка при 90°C.",
    "",
    "Цена $100 или €90 за 3.5 часа.",
    "Бюджет $1,999, объём 10 000 записей, до 1,000,000 строк.",
    "Разгон 3.5-4.5 GHz, рост 10-20% и ось х при 90° севернее.",
]


def test_snapshots():
    for src, expected in SNAPSHOTS.items():
        got = normalize_for_tts(src)
        assert got == expected, f"{src!r} -> {got!r}, expected {expected!r}"


def test_no_ascii_alnum_in_output():
    for src in list(SNAPSHOTS) + IDEMPOTENT_INPUTS:
        got = normalize_for_tts(src)
        assert not _ASCII_ALNUM.search(got), f"{src!r} left ascii alnum: {got!r}"


def test_idempotent():
    for src in IDEMPOTENT_INPUTS + list(SNAPSHOTS):
        once = normalize_for_tts(src)
        twice = normalize_for_tts(once)
        assert once == twice, f"not idempotent: {src!r}\n once={once!r}\n twice={twice!r}"


def test_verify_coupling_is_noop():
    # text_tts = normalize_for_tts(text_ru); the verify no-op guarantee is that re-normalizing
    # text_tts changes nothing, so both sides of the comparison pass through identical code.
    for text_ru in ["У RTX 4080 12 ГБ видеопамяти.", "Это в 2 раза быстрее.", "Обычный текст."]:
        text_tts = normalize_for_tts(text_ru)
        assert normalize_for_tts(text_tts) == text_tts
        assert normalize_for_compare(text_tts) == normalize_for_compare(text_tts)


def test_compare_strips_case_punct_yo():
    a = normalize_for_compare("Ёлка, ёж!")
    b = normalize_for_compare("елка еж")
    assert a == b, f"{a!r} != {b!r}"


def test_plural_agreement():
    assert normalize_for_tts("1 GB") == "один гигабайт"
    assert normalize_for_tts("3 GB") == "три гигабайта"
    assert normalize_for_tts("5 GB") == "пять гигабайт"


def test_thousands_separators_keep_magnitude():
    # verify is BLIND to magnitude bugs (both sides share the normalizer) -> test directly
    assert normalize_for_tts("$1,999") == "одна тысяча девятьсот девяносто девять долларов"
    assert normalize_for_tts("10 000") == "десять тысяч"
    assert normalize_for_tts("1,000,000") == "один миллион"
    assert normalize_for_tts("стоит $2 999.") == "стоит две тысячи девятьсот девяносто девять долларов."
    # a grouped number must NOT be misread as a decimal (no "целых")
    assert "целых" not in normalize_for_tts("$1,999")
    # a real decimal comma survives the grouping collapse
    assert normalize_for_tts("ускорение 3,5 раза") == "ускорение три целых пять раза"


def test_decimal_range_not_shredded():
    assert normalize_for_tts("10-20") == "от десять до двадцать"
    assert normalize_for_tts("3.5-4.5") == "от три целых пять до четыре целых пять"
    # the old bug produced "три.от пять до четыре.пять" — guard against regression
    assert "." not in normalize_for_tts("3.5-4.5")


def test_cyrillic_not_mangled():
    # Cyrillic 'х' is not a multiplier; the digit is still spelled, the 'х' is preserved
    assert normalize_for_tts("по оси х 5") == "по оси х пять"
    # Celsius letter must not eat the leading letter of the next Russian word
    assert normalize_for_tts("было 90° севернее") == "было девяносто градусов севернее"
    assert normalize_for_tts("при 90°C воды") == "при девяносто градусов цельсия воды"


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
