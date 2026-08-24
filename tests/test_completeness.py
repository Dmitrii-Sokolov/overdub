"""Unit tests for overdub/completeness.py — the cheap deterministic loss detectors.

Run: .venv-asr/Scripts/python.exe tests/test_completeness.py   (or via pytest)
Pure, no I/O, no GPU. Guards each detector's fire/no-fire contract plus its documented
false-positive guards (RU bound-prefix negation incl. the без/бес voicing pair, double-negative,
sentence-initial entity, personal-name Russification, spelled-out numbers), and the "clean
sentence -> no flags" invariant that keeps 400+ good sentences unflagged.

duplicate_adjacent (the one CROSS-SENTENCE detector) is tested separately from check(): its
regression case is the real ytEN_iAk09c 7/8 echo, and the near-miss cases that must stay silent
are a real rhetorical-parallelism pair (passes the length guard, rejected by the threshold), a
short identical pair (rejected by the length guard alone) and a non-adjacent repeat.
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
    # a translator spelling digits against the keep-digits rule; _n2w must absorb it.
    r = _check("It costs 100 dollars.", "Это стоит сто долларов.")
    assert r["missing_numbers"] == []
    assert "num_loss" not in r["flags"]


def test_a_spelled_number_in_any_case_or_derivative_is_not_a_loss() -> None:
    # The whole-token suppressor only matched the NOMINATIVE, which is the one form Russian prose
    # rarely uses — 5 of 7 fires on the 2026-07-25 batch were the number spelled correctly in an
    # oblique case or folded into a derivative. Stem matching (2026-07-25) covers those.
    for en, ru in (
        ("If any of these 10 felt targeted.", "Если какой-то из этих десяти пунктов попал."),
        ("I'm just going to click the 5.", "Просто нажму на пятёрку."),
        ("The Oregon Trail of 50 years ago.", "Oregon Trail пятидесятилетней давности."),
        ("It has 8 cores.", "У него восьми ядер."),
    ):
        r = _check(en, ru)
        assert r["missing_numbers"] == [], (en, ru, r["missing_numbers"])
        assert "num_loss" not in r["flags"]


def test_stem_suppression_still_misses_a_root_vowel_change() -> None:
    # KNOWN residue, asserted so it is a documented limit rather than a surprise: два→дву-,
    # три→тре-, сто→ста change the root itself, so a 3-char prefix cannot match ("два" vs
    # "двумерном"). Left alone deliberately — num_loss fired 7 times in 4321 sentences and the
    # stem fix took the bulk of that; a hand-written root table for three numerals costs more
    # than the noise it removes. Revisit only if a batch shows this class actually recurring.
    assert _check("the derivative in 2D.", "производную в двумерном.")["missing_numbers"] == ["2"]
    # The opposite residue, and the price of a 3-char stem: "сто" is a prefix of ordinary words
    # ("стоит", "стало"), so a dropped 100 can be suppressed by unrelated prose. A MISS, which is
    # the direction this module documents as safe — unlike a false alarm, it costs no attention.
    assert _check("It costs 100 dollars.", "Дорого стоит.")["missing_numbers"] == []


def test_a_genuinely_dropped_number_still_fires_after_the_stem_change() -> None:
    # The loosened suppressor must not blind the detector: no numeral stem in the RU at all.
    r = _check("The RTX 4080 runs at 60 fps.", "Видеокарта работает плавно.")
    assert "60" in r["missing_numbers"] and "num_loss" in r["flags"]
    r = _check("We shipped 7 features this month.", "Мы выпустили новые функции за месяц.")
    assert "7" in r["missing_numbers"]


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


def test_negation_bes_bound_prefix_not_flagged() -> None:
    # бес- (voiceless) is the SAME bound prefix as не-; the з/с alternation of без/бес is pure
    # voicing assimilation and must not decide the flag. Regression on W4Ua6XFfX9w#32.
    r = _check("Separate what's useful from what's not.", "Отделять полезное от бесполезного.")
    assert r["negation_lost"] is False
    assert "neg_loss" not in r["flags"]


def test_negation_bez_positive_stem_is_an_accepted_false_positive() -> None:
    # "безопасно" is privative by etymology but POSITIVE by polarity, so it is NOT accepted as
    # surviving negation. Cost: this correct translation is flagged. Benefit: the test below.
    # DECISIONS 2026-07-19 prices this explicitly — one FP per batch beats one missed inversion.
    r = _check("It's not dangerous.", "Это безопасно.")
    assert r["negation_lost"] is True


def test_negation_inverted_into_positive_stem_is_caught() -> None:
    # The case the FP above buys: the translation INVERTS the meaning ("not safe" -> "safe").
    # If a future change makes this pass silently, the detector has lost its whole purpose.
    r = _check("This setup is not safe.", "Эта конфигурация безопасна.")
    assert r["negation_lost"] is True
    assert "neg_loss" in r["flags"]


def test_negation_bez_standalone_preposition_not_flagged() -> None:
    # [а-я]* takes zero chars, so the bare preposition still matches after the widening.
    r = _check("I did it without help.", "Я сделал это без помощи.")
    assert r["negation_lost"] is False


def test_negation_dropped_before_bes_lookalike_is_caught() -> None:
    # "беседа" merely STARTS like бес-; it carries no negation, and here the translation really
    # did drop one ("don't like" -> "нравится"). An earlier revision pinned this as an accepted
    # miss on prefer-miss grounds — wrong for this detector, whose entire job is the inversion.
    r = _check("I don't like this conversation.", "Мне нравится эта беседа.")
    assert r["negation_lost"] is True
    assert "neg_loss" in r["flags"]


# --- entities: DELETED 2026-08-01 ---------------------------------------------
# The entity_loss detector is gone (DECISIONS 2026-08-01). This test pins the removal so a
# reintroduction has to be deliberate: a dropped Latin name must produce NO flag now.
def test_dropped_latin_name_no_longer_flags() -> None:
    r = _check("I switched from Minecraft to Fortnite.", "Я перешёл на другую игру.")
    assert r["flags"] == []
    assert "missing_entities" not in r


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


# --- adjacent duplicates (cross-sentence, EN source) --------------------------
_DUP_LINE = "Description addresses how we communicate with AI systems."


def test_dup_adjacent_exact_echo_flags_both() -> None:
    # The real defect shape: ytEN_iAk09c ids 7/8 are byte-identical (ratio 1.0000).
    d = completeness.duplicate_adjacent([
        "Intro line that is comfortably long.",
        _DUP_LINE,
        _DUP_LINE,
        "Then the talk moves on to something else entirely.",
    ])
    assert d == {1: 2, 2: 1}


def test_dup_adjacent_clean_document_no_fire() -> None:
    # Real consecutive sentences from W4Ua6XFfX9w — distinct content, must stay silent.
    assert completeness.duplicate_adjacent([
        "Delegation to decide when and how to use AI.",
        "Discernment to evaluate AI outputs.",
        "And diligence to use AI responsibly.",
    ]) == {}


def test_dup_adjacent_short_first_member_guarded() -> None:
    # Pair is IDENTICAL, so only the length guard can suppress it (len 14 <= 25).
    assert completeness.duplicate_adjacent(["Yeah, exactly.", "Yeah, exactly."]) == {}


def test_dup_adjacent_short_frame_parallelism_not_flagged() -> None:
    # Real pair ytEN_iAk09c 47/48: ratio 0.5106 with len(a)=27 > 25, so it PASSES the length
    # guard and is rejected by the threshold alone — a true negative control, not a guard artifact.
    # NOTE the narrow name: this covers parallelism with a SHORT frame and differing content.
    # Long-frame parallelism does fire — see the test below, which pins that boundary.
    assert completeness.duplicate_adjacent([
        "Be effective and efficient.",
        "Be ethical and safe.",
    ]) == {}


def test_dup_adjacent_long_frame_substitution_does_fire() -> None:
    # The detector's real boundary, pinned so nobody reads the test above as "parallelism is
    # safe". A one-word swap in a long shared frame scores ~0.96 and FIRES. This is the
    # documented dominant false positive, and the pair is semantically OPPOSITE — the case where
    # a triager deleting one member would invert the meaning.
    d = completeness.duplicate_adjacent([
        "You should use this approach for short prompts.",
        "You should not use this approach for short prompts.",
    ])
    assert d == {0: 1, 1: 0}


def test_dup_adjacent_restart_caught_by_containment() -> None:
    # Real x7DfiXqSEdM 298/299. ratio 0.6977 — BELOW _DUP_RATIO_MIN, so only containment
    # (0.9677) can catch it. This is the regression guard for the restart class: if someone
    # drops the containment signal, this test is what fails.
    d = completeness.duplicate_adjacent([
        "I acknowledge that this none of these methods are easy.",
        "None of these methods are easy.",
    ])
    assert d == {0: 1, 1: 0}


def test_dup_adjacent_loop_swallowing_previous_line() -> None:
    # Real 2YCaBqP8muw 16/17: the tip list is re-spoken inside the next sentence.
    # ratio 0.6569, containment 0.9167.
    d = completeness.duplicate_adjacent([
        "They are give Claude context, show examples of what good looks like, "
        "specify output constraints,",
        "break complex tasks into steps, give Claude context, show examples of what good "
        "looks like, specify output constraints, break complex tasks into steps, ask Claude "
        "to think first,",
    ])
    assert d == {0: 1, 1: 0}


def test_dup_adjacent_benign_shared_opener_below_containment() -> None:
    # Real x7DfiXqSEdM 143/144 — the loudest benign containment in the corpus (0.7188), a
    # genuine rephrase. Pins the lower edge of the empty band that _DUP_CONTAINMENT_MIN sits in.
    assert completeness.duplicate_adjacent([
        "But as soon as you start, as soon as you're actually playing the game, most of the "
        "time, and at least for me, I start to enjoy it.",
        "I immediately start to have fun.",
    ]) == {}


# --- implausible speech rate (per sentence, EN source + timing) ---------------
def test_rate_implausible_collapsed_alignment_flagged() -> None:
    # Real ytEN_iAk09c id8: 57 chars stamped onto 0.32 s = 178 ch/s. Physically unspeakable.
    r = completeness.implausible_rate([_DUP_LINE], [0.32])
    assert set(r) == {0}
    assert r[0] > 100


def test_rate_implausible_normal_speech_not_flagged() -> None:
    # Corpus median is 16.75 ch/s and p99 is 34.26 — ordinary narration must stay silent.
    assert completeness.implausible_rate([_DUP_LINE], [3.90]) == {}
    # Real x7DfiXqSEdM 29, the fastest BENIGN sentence in the corpus (39.4 ch/s).
    assert completeness.implausible_rate(["We were setting our long -term goals."], [0.94]) == {}


def test_rate_implausible_short_sentence_guarded() -> None:
    # Below _RATE_MIN_LEN a stamping error alone clears the bound — must not fire.
    assert completeness.implausible_rate(["Yeah, okay."], [0.05]) == {}


def test_rate_implausible_missing_timing_is_not_evidence() -> None:
    # A zero/absent span means "unknown", never "infinitely fast".
    assert completeness.implausible_rate([_DUP_LINE, _DUP_LINE], [0.0, -1.0]) == {}


def test_rate_implausible_catches_what_dup_adjacent_cannot() -> None:
    # The complementarity claim in the docstring, pinned: a collapsed garble that repeats
    # NOTHING is invisible to the text detectors and visible here.
    garbled = "The LLM is used to analyze and categorize data, like the LLM, or LLM."
    assert completeness.duplicate_adjacent(["A perfectly ordinary preceding sentence.", garbled]) == {}
    assert set(completeness.implausible_rate(["A perfectly ordinary preceding sentence.", garbled],
                                             [3.0, 0.28])) == {1}


def test_containment_helper_contract() -> None:
    assert completeness._containment("", "anything") == 0.0
    assert completeness._containment("abc", "") == 0.0
    assert completeness._containment("hello world", "hello world") == 1.0
    # Fully swallowed shorter member -> 1.0 regardless of the longer one's tail.
    assert completeness._containment("the quick brown fox", "the quick brown fox jumps") == 1.0


def test_dup_adjacent_non_adjacent_repeat_not_flagged() -> None:
    # A callback later in the video is legitimate; only ADJACENT pairs are a whisper echo.
    assert completeness.duplicate_adjacent([
        "This is the thesis of the whole video.",
        "Some intervening explanation here.",
        "This is the thesis of the whole video.",
    ]) == {}


def test_dup_adjacent_run_of_three() -> None:
    # Documented semantics: every member is flagged, interior members keep their LAST twin.
    d = completeness.duplicate_adjacent([_DUP_LINE, _DUP_LINE, _DUP_LINE])
    assert set(d) == {0, 1, 2}
    assert d[1] == 2


def test_dup_adjacent_edge_inputs() -> None:
    assert completeness.duplicate_adjacent([]) == {}
    assert completeness.duplicate_adjacent(["Only one sentence in the document."]) == {}


# --- clean invariant ----------------------------------------------------------
def test_clean_sentence_no_flags() -> None:
    r = _check("Social gaming used to be a staple of my life.",
               "Совместные игры раньше были неотъемлемой частью моей жизни.")
    assert r["flags"] == []
    assert r["missing_numbers"] == []
    assert r["negation_lost"] is False


def test_all_signals_at_once() -> None:
    # a sentence dropping a number, a negation, and most of its length. The dropped names
    # (Skyrim, Steam) no longer contribute a flag — entity_loss was deleted 2026-08-01.
    r = _check("You should not buy 3 copies of Skyrim on Steam today okay.", "Купи.")
    assert set(r["flags"]) == {"num_loss", "neg_loss", "length_short"}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all completeness tests passed")
