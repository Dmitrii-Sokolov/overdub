"""Unit tests for assemble's DISPLAY-ONLY subtitle cue split (_split_cue) — pure, no audio.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_assemble_cues.py   (or via pytest)
Contract: a cue split changes PRESENTATION only — text is never lost, the outer [a, b] is
preserved bit-exactly (sentence onsets stay synced), sub-cues are monotone and
non-overlapping, and no sub-MIN_CUE_SEC flash-frame is ever manufactured. Splits land at
CLAUSE SEAMS only: no em-dash (RU zero-copula) and no bare word gaps (would break mid-clause),
so a cue with no interior seam is left whole rather than broken at an invented boundary.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.stages.assemble import (  # noqa: E402
    MAX_CUE_CHARS, MAX_CUE_SEC, MIN_CUE_SEC, _split_cue,
)

_LONG = ("Это довольно длинное предложение, которое содержит несколько частей, "
         "разделённых запятыми, и оно точно не помещается в один короткий титр, "
         "потому что читается как стена текста.")


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_text_is_never_lost() -> None:
    cues = _split_cue(0.0, 20.0, _LONG)
    assert len(cues) > 1, cues
    assert _flat(" ".join(t for _, _, t in cues)) == _flat(_LONG)


def test_outer_endpoints_are_exact() -> None:
    a, b = 12.345, 31.5
    cues = _split_cue(a, b, _LONG)
    assert cues[0][0] == a, cues[0]
    assert cues[-1][1] == b, cues[-1]


def test_monotone_non_overlapping() -> None:
    cues = _split_cue(0.0, 20.0, _LONG)
    assert all(x < y for x, y, _ in cues), cues
    assert all(cues[i][1] == cues[i + 1][0] for i in range(len(cues) - 1)), cues


def test_caps_respected_when_splittable() -> None:
    for a, b, text in ((0.0, 20.0, _LONG), (5.0, 40.0, _LONG + " " + _LONG)):
        for x, y, t in _split_cue(a, b, text):
            assert y - x <= MAX_CUE_SEC + 1e-9, (x, y, t)
            assert len(t) <= MAX_CUE_CHARS, (len(t), t)


def test_single_long_token_survives() -> None:
    tok = "я" * 240                                   # no seam, no gap: unsplittable
    cues = _split_cue(0.0, 20.0, tok)
    assert cues == [(0.0, 20.0, tok)], cues


def test_short_cue_is_identity() -> None:
    cues = _split_cue(1.0, 4.0, "Короткая реплика.")  # under both caps
    assert cues == [(1.0, 4.0, "Короткая реплика.")], cues


def test_never_manufactures_a_flash_frame() -> None:
    # text-dense but SHORT span: any split would make a sub-MIN_CUE_SEC cue -> keep whole
    cues = _split_cue(0.0, 1.5, _LONG)
    assert cues == [(0.0, 1.5, _LONG)], cues
    for x, y, _ in _split_cue(0.0, 20.0, _LONG):      # and never on a splittable one
        assert y - x >= MIN_CUE_SEC - 1e-9, (x, y)


def test_no_stranded_leading_punctuation() -> None:
    for _, _, t in _split_cue(0.0, 20.0, _LONG):
        assert t[:1] not in {",", ";", ":", ".", "!", "?"}, t


def test_em_dash_is_not_a_seam() -> None:
    # "X — это Y": the em-dash is a RU zero-copula, NOT a line end. A split must never strand
    # it at a cue TAIL (it did under the old dash-inclusive seam class — 19 corpus cues).
    text = ("Владение искусственным интеллектом — это не просто знание технических "
            "нюансов работы с большими языковыми моделями, это гораздо шире")
    cues = _split_cue(0.0, 11.0, text)
    assert len(cues) > 1, cues
    assert all(not t.rstrip().endswith("—") for _, _, t in cues), cues


def test_seamless_long_clause_stays_whole() -> None:
    # over the duration cap but with no interior clause punctuation: a word-gap split would
    # land mid-clause ("AI | fluency"), so the cue is left whole — presentation never invents
    # a linguistic boundary the sentence does not have.
    text = "это довольно длинное предложение без единого знака препинания внутри вообще"
    assert len(text) < MAX_CUE_CHARS                  # only the 12 s > 6 s cap can trigger
    cues = _split_cue(0.0, 12.0, text)
    assert cues == [(0.0, 12.0, text)], cues


def test_lopsided_lone_seam_is_left_whole() -> None:
    # The only seam is a short leading clause ("Итак."): splitting there flashes, and there is
    # NO other seam. Deliberate Finding-1/Finding-3 reconciliation — rather than break the long
    # tail at a word gap to hit the cap, we leave the cue whole (no invented mid-clause break).
    text = "Итак. " + " ".join(["слово"] * 22)         # 132 chars, one lopsided seam
    cues = _split_cue(0.0, 9.4, text)
    assert cues == [(0.0, 9.4, text.strip())], cues


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all cue tests passed")
