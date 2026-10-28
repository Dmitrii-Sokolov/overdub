"""Unit tests for the dialogue dash at a speaker change (assemble.turn_marked) — pure.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_turn_marks.py   (or via pytest)

Contract: a sentence whose speaker differs from the previous sentence's opens its subtitle with
"— " in ru.srt and "- " in en.srt. A record without `speaker` never marks, so a single-speaker
video's subtitles are unchanged; the artifacts on disk keep their text.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.stages.assemble import _ru_cue_rows, source_timed_rows, turn_marked  # noqa: E402

SR = 1000


def _rec(i: int, spk, en: str, ru: str) -> dict:
    r = {"id": i, "start": i * 2.0, "end": i * 2.0 + 1.5, "src_en": en, "text": en,
         "text_ru": ru, "text_tts": ru}
    if spk is not None:
        r["speaker"] = spk
    return r


DIALOG = [_rec(0, 0, "Hi.", "Привет."), _rec(1, 0, "How are you?", "Как дела?"),
          _rec(2, 1, "Fine.", "Хорошо."), _rec(3, 0, "Good.", "Отлично.")]


def test_a_speaker_change_opens_with_a_dash_on_both_sides() -> None:
    assert [r["text_ru"] for r in turn_marked(DIALOG, "text_ru")] == \
        ["Привет.", "Как дела?", "— Хорошо.", "— Отлично."]
    assert [r["src_en"] for r in turn_marked(DIALOG, "src_en")] == \
        ["Hi.", "How are you?", "- Fine.", "- Good."]


def test_a_single_speaker_video_is_unchanged() -> None:
    recs = [_rec(i, None, "Line.", "Строка.") for i in range(3)]
    assert turn_marked(recs, "text_ru") == recs


def test_the_records_on_disk_are_not_touched() -> None:
    before = [dict(r) for r in DIALOG]
    turn_marked(DIALOG, "text_ru")
    assert DIALOG == before


def test_an_empty_line_takes_no_dash() -> None:
    recs = [_rec(0, 0, "Hi.", "Привет."), _rec(1, 1, "", "")]
    assert turn_marked(recs, "text_ru")[1]["text_ru"] == ""


def test_the_dub_timed_ru_cue_carries_the_dash() -> None:
    plans = [{"u": {"ids": [0, 1, 2, 3]}, "offset": 0, "placed": 8 * SR}]
    rows = _ru_cue_rows(plans, turn_marked(DIALOG, "text_ru"), SR)
    assert [t for _, _, t in rows] == ["Привет.", "Как дела?", "— Хорошо.", "— Отлично."], rows


def test_the_degraded_track_carries_the_dash() -> None:
    rows = source_timed_rows(turn_marked(DIALOG, "text"), "text")
    assert [t for _, _, t in rows] == ["Hi.", "How are you?", "- Fine.", "- Good."], rows


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all turn-mark tests passed")
