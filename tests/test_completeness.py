"""Unit tests for overdub/completeness.py — the cheap deterministic loss detectors.

Run: .venv-asr/Scripts/python.exe tests/test_completeness.py   (or via pytest)
Pure, no I/O, no GPU. Guards each detector's fire/no-fire contract plus its documented
false-positive guards (RU bound-prefix negation, double-negative, sentence-initial entity,
personal-name Russification, Gemma spelled-out numbers), and the "clean sentence -> no flags"
invariant that keeps 400+ good sentences unflagged.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import completeness  # noqa: E402
from overdub.config import Config  # noqa: E402

_CFG = Config()


def _check(src_en: str, text_ru: str) -> dict:
    return completeness.check(src_en, text_ru, _CFG)


# --- numbers ------------------------------------------------------------------
def test_number_preserved() -> None:
    r = _check("I have 3 cats and 12 dogs.", "У меня 3 кошки и 12 собак.")
    assert r["missing_numbers"] == []
    assert "num_loss" not in r["flags"]


def test_number_lost() -> None:
    r = _check("The RTX 4080 runs at 60 fps.", "Видеокарта работает плавно.")
    assert "4080" in r["missing_numbers"] and "60" in r["missing_numbers"]
    assert "num_loss" in r["flags"]


def test_number_spelled_out_not_flagged() -> None:
    # Gemma spells digits against the keep-digits rule; the _n2w suppressor must absorb it.
    r = _check("It costs 100 dollars.", "Это стоит сто долларов.")
    assert r["missing_numbers"] == []
    assert "num_loss" not in r["flags"]


# --- negation -----------------------------------------------------------------
def test_negation_preserved() -> None:
    r = _check("I do not like this game.", "Мне не нравится эта игра.")
    assert r["negation_lost"] is False
    assert "neg_loss" not in r["flags"]


def test_negation_lost() -> None:
    r = _check("This is not a good idea.", "Это хорошая идея.")
    assert r["negation_lost"] is True
    assert "neg_loss" in r["flags"]


def test_negation_contraction_lost() -> None:
    r = _check("I don't play anymore.", "Я всё ещё играю.")
    assert r["negation_lost"] is True


def test_negation_bound_prefix_not_flagged() -> None:
    # RU glues the negation to the stem: "непросто" IS a negation; whole-word \bне\b misses it.
    r = _check("It's not easy.", "Это непросто.")
    assert r["negation_lost"] is False
    assert "neg_loss" not in r["flags"]


def test_negation_ni_prefix_not_flagged() -> None:
    r = _check("Nobody knows.", "Никто не знает.")
    assert r["negation_lost"] is False


def test_double_negative_collapse_guard() -> None:
    # pleonastic idiom carries no negation -> must not fire even with no RU negation marker.
    r = _check("It happens more often than not.", "Это случается часто.")
    assert r["negation_lost"] is False
    assert "neg_loss" not in r["flags"]


def test_negation_word_inside_name_not_flagged() -> None:
    # "No Man's Sky" contains "No" but is a title, not a negation.
    r = _check("I love playing No Man's Sky.", "Обожаю играть в No Man's Sky.")
    assert r["negation_lost"] is False


# --- entities -----------------------------------------------------------------
def test_entity_preserved() -> None:
    r = _check("I mostly play Minecraft now.", "Сейчас в основном играю в Minecraft.")
    assert r["missing_entities"] == []
    assert "entity_loss" not in r["flags"]


def test_entity_lost() -> None:
    r = _check("I switched from Minecraft to Fortnite.", "Я перешёл на другую игру.")
    assert "Minecraft" in r["missing_entities"] and "Fortnite" in r["missing_entities"]
    assert "entity_loss" in r["flags"]


def test_entity_inflected_latin_not_flagged() -> None:
    # kept-Latin name with a Russian case suffix: substring check still matches.
    r = _check("I played a lot of Minecraft.", "Я много играл в Minecraft-е.")
    assert r["missing_entities"] == []


def test_entity_pronoun_i_not_flagged() -> None:
    # "I'll"/"I'm" are Titlecase because 'I' is always capitalized -> must be stoplisted.
    r = _check("I'll tell you what I think.", "Я скажу, что думаю.")
    assert r["missing_entities"] == []
    assert "entity_loss" not in r["flags"]


def test_entity_sentence_initial_not_flagged() -> None:
    # sentence-initial token is dropped (belt-and-suspenders), even if it looks like a name.
    r = _check("Minecraft is my favorite.", "Моя любимая игра — Minecraft.")
    assert r["missing_entities"] == []


def test_entity_acronym_russianized_not_flagged() -> None:
    # ALL-CAPS acronyms are excluded: the prompt allows AI -> ИИ.
    r = _check("This AI is impressive.", "Этот ИИ впечатляет.")
    assert r["missing_entities"] == []
    assert "entity_loss" not in r["flags"]


# --- length -------------------------------------------------------------------
def test_length_short() -> None:
    src = "You choose what to play, when to play, and how long you keep going for."
    r = _check(src, "Ты выбираешь.")
    assert r["length_ratio"] < _CFG.completeness_len_ratio_min
    assert "length_short" in r["flags"]


def test_length_short_guarded_on_short_source() -> None:
    # short src_en (< 30 chars) never fires length_short even at a tiny ratio — filler drop.
    r = _check("And then after that,", "А потом,")
    assert len("And then after that,") < 30
    assert "length_short" not in r["flags"]


def test_normal_compression_not_flagged() -> None:
    # near-parity RU/EN length is normal dubbing, not loss.
    src = "Social gaming used to be a staple of my life."
    r = _check(src, "Совместные игры раньше были неотъемлемой частью моей жизни.")
    assert "length_short" not in r["flags"]


# --- clean invariant ----------------------------------------------------------
def test_clean_sentence_no_flags() -> None:
    r = _check("Social gaming used to be a staple of my life.",
               "Совместные игры раньше были неотъемлемой частью моей жизни.")
    assert r["flags"] == []
    assert r["missing_numbers"] == [] and r["missing_entities"] == []
    assert r["negation_lost"] is False


def test_all_signals_at_once() -> None:
    # a sentence dropping a number, a negation, an entity, and most of its length.
    r = _check("You should not buy 3 copies of Skyrim on Steam today okay.", "Купи.")
    assert set(r["flags"]) == {"num_loss", "neg_loss", "entity_loss", "length_short"}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all completeness tests passed")
