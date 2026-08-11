"""[[written|spoken]] markup: one draft line, two artifacts pulled in opposite directions.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_dual_form.py   (or via pytest)

WHY. Subtitles and synthesis want different text and used to be served one string, so improving
either damaged the other: leaving Latin in handed the token to the pronounce chain's
spelling-based fallback, which invents a reading ("буттон" for button); spelling the reading into
text_ru made the SUBTITLES read like a caption of someone talking. (Silero's deletion of Latin is
real but never fires — normalize_for_tts is Cyrillic-only by contract, so the engine never sees
it.) The markup ends the trade-off, and these tests pin the two properties that make it safe —
the sides never leak into each other, and text_tts is still DERIVED rather than authored.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_translation  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.normalize import normalize_for_tts, spoken_form, written_form  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

LINE = "Итак, сегодня мы смотрим на [[RTX 4080|эр-ти-экс четыре тысячи восемьдесят]]."


def test_the_two_sides_are_pulled_apart() -> None:
    assert written_form(LINE) == "Итак, сегодня мы смотрим на RTX 4080."
    assert spoken_form(LINE) == "Итак, сегодня мы смотрим на эр-ти-экс четыре тысячи восемьдесят."


def test_neither_side_leaks_the_other() -> None:
    # The failure that matters: a subtitle reading out a pronunciation, or the dub voicing the
    # spelling it was given a reading for. Both are silent — nothing downstream compares them.
    assert "эр-ти-экс" not in written_form(LINE)
    assert "RTX" not in spoken_form(LINE)
    assert "[[" not in written_form(LINE) and "]]" not in written_form(LINE)
    assert "[[" not in spoken_form(LINE) and "]]" not in spoken_form(LINE)


def test_several_spans_in_one_line_stay_separate() -> None:
    # Non-greedy matching, or the first [[ pairs with the LAST ]] and everything between two
    # names collapses into one span — losing a whole clause with no error.
    s = "В [[Unity|Юнити]] есть [[GetComponent|гет-компонент]], а в [[Blender|Блендере]] нет."
    assert written_form(s) == "В Unity есть GetComponent, а в Blender нет."
    assert spoken_form(s) == "В Юнити есть гет-компонент, а в Блендере нет."


def test_unmarked_prose_is_untouched_on_both_sides() -> None:
    plain = "Сегодня мы разберём метод тепла и геодезические расстояния."
    assert written_form(plain) == plain
    assert spoken_form(plain) == plain


def test_malformed_markup_is_left_alone_not_guessed() -> None:
    # Visible beats silent: literal brackets in a subtitle get noticed and fixed; a repair
    # guesses which half was meant and nobody ever learns it guessed.
    # NB "[[[[x|y]]" is NOT in this list: it contains a well-formed [[x|y]] behind two stray
    # brackets, and resolving that span is right. Only a span with no pipe, no terminator, no
    # opener, or a pipe too many is left as written.
    for bad in ("[[Unity]]", "[[Unity|", "Unity|Юнити]]", "[[a|b|c]]"):
        assert written_form(bad) == bad, bad
        assert spoken_form(bad) == bad, bad
    # A well-formed but EMPTY span is not malformed — it collapses, on both sides, to nothing.
    assert written_form("до [[|]]после") == "до после"


def test_the_spoken_side_still_goes_through_the_normalizer() -> None:
    # The markup gives the normalizer better input; it does not replace it. An unmarked number
    # must still be voiced, or a translator's omission becomes digits read aloud.
    out = normalize_for_tts(spoken_form("Осталось 5 минут."))
    assert "5" not in out and "пять" in out


def test_a_marked_reading_survives_the_normalizer_unchanged() -> None:
    # The point of marking: the translator's reading is what gets said, not the fallback's.
    out = normalize_for_tts(spoken_form(LINE))
    assert "эр-ти-экс" in out
    assert not any(c.isascii() and c.isalnum() for c in out), out


def _audit_tokens(draft_line: str) -> dict:
    """Run the real build() on a one-sentence draft; return pronounce_audit.json's tokens."""
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(root=Path(d))
        work.sentences.write_text(
            json.dumps([{"id": 0, "text": "Odin is nice.", "start": 0.0, "end": 2.0}]),
            encoding="utf-8")
        dp = Path(d) / "draft.json"
        dp.write_text(json.dumps([{"id": 0, "text_ru": draft_line, "src": "ok"}],
                                 ensure_ascii=False), encoding="utf-8")
        build_translation.build(work, dp, Config())
        return json.loads(work.pronounce_audit.read_text(encoding="utf-8"))["tokens"]


def test_the_audit_reads_the_spoken_side_not_the_subtitle() -> None:
    """pronounce_audit is the ONLY detector for the out-of-dict-name silent-loss class, and it
    reads a record's text_ru — which is now the WRITTEN side, full of legitimate Latin that never
    reaches the pronounce chain. Auditing that field turns the detector into noise: measured on
    L0nBN6ME7VQ it reported 75 invented readings where 2 were real, i.e. every marked name
    counted as a guess while the actual guesses were buried. Marked spans must be invisible here.
    """
    assert _audit_tokens("Это [[Odin|Один]] и [[Unity|Юнити]].") == {}


def test_an_unmarked_name_still_shows_up_in_the_audit() -> None:
    # The other half: the detector must keep firing on what the translator did NOT mark, or the
    # fix above would have bought silence rather than signal.
    tokens = _audit_tokens("Это Odin и [[Unity|Юнити]].")
    assert "odin" in tokens and "unity" not in tokens


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all dual-form tests passed")
