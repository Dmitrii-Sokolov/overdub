"""Unit tests for ru.srt cue PLACEMENT (_ru_cue_rows) — pure, no audio, no ffmpeg.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_assemble_srt.py   (or via pytest)

Contract: ru cues follow the DUB, not the source timeline. Grouping swallows the pauses inside
a unit, so a source-timed cue drifts from the voice that speaks it (p90 1.28 s at the shipped
1.2/20/600 grouping). Each cue therefore opens where the audio actually landed — the unit's
offset plus the sentence's character share of the unit's PLACED duration, shared over text_tts
because that is the string the engine voiced — and runs to the next cue's onset, so an
under-filled unit's silence stays readable instead of being cut off.

Separate from test_assemble_cues.py on purpose: that file owns _split_cue's PRESENTATION
contract (how one span is broken up), this one owns where the span comes from.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.stages.assemble import _ru_cue_rows, _write_ru_srt  # noqa: E402

SR = 1000                                          # 1 ms per sample: offsets read as seconds


def _seg(i: int, start: float, end: float, ru: str, tts: str | None = None) -> dict:
    return {"id": i, "start": start, "end": end, "text_ru": ru,
            "text_tts": ru if tts is None else tts}


def _plan(ids: list[int], start: float, end: float, offset: float, placed: float) -> dict:
    """A plan row as assemble.run builds it, reduced to the keys _ru_cue_rows reads."""
    return {"u": {"ids": ids, "start": start, "end": end, "text_tts": "spoken"},
            "offset": round(offset * SR), "placed": round(placed * SR)}


def test_cue_follows_the_audio_not_the_source_span() -> None:
    # source span 10..20 s, but the unit only speaks for 4 s
    segs = [_seg(0, 10.0, 20.0, "Привет.")]
    rows = _ru_cue_rows([_plan([0], 10.0, 20.0, 10.0, 4.0)], segs, SR)
    assert len(rows) == 1, rows
    a, b, text = rows[0]
    assert (round(a, 6), round(b, 6)) == (10.0, 14.0), rows
    assert text == "Привет."


def test_share_is_taken_over_text_tts_not_text_ru() -> None:
    # equal text_ru lengths, 1:3 text_tts lengths -> the split lands at 25%, not 50%
    segs = [_seg(0, 0.0, 5.0, "AAAAA", tts="а"),
            _seg(1, 5.0, 10.0, "BBBBB", tts="ббб")]
    rows = _ru_cue_rows([_plan([0, 1], 0.0, 10.0, 0.0, 8.0)], segs, SR)
    assert len(rows) == 2, rows
    assert round(rows[0][1], 6) == 2.0, rows      # 8 s * 1/4
    assert round(rows[1][0], 6) == 2.0, rows
    assert round(rows[1][1], 6) == 8.0, rows


def test_cue_end_runs_to_the_next_onset() -> None:
    # unit 0 speaks 2 s of a 10 s slot: the cue must linger over the hole, not cut at 2 s
    segs = [_seg(0, 0.0, 10.0, "Первое."), _seg(1, 10.0, 13.0, "Второе.")]
    rows = _ru_cue_rows([_plan([0], 0.0, 10.0, 0.0, 2.0),
                         _plan([1], 10.0, 13.0, 10.0, 3.0)], segs, SR)
    assert round(rows[0][1], 6) == 10.0, rows
    assert round(rows[1][0], 6) == 10.0, rows
    assert round(rows[1][1], 6) == 13.0, rows     # last cue ends with its audio


def test_silent_unit_falls_back_to_source_timings() -> None:
    segs = [_seg(0, 4.0, 9.0, "Ничего не синтезировалось.")]
    rows = _ru_cue_rows([_plan([0], 4.0, 9.0, 4.0, 0.0)], segs, SR)
    assert rows == [(4.0, 9.0, "Ничего не синтезировалось.")], rows


def test_onsets_stay_monotone_when_a_fallback_row_reaches_back() -> None:
    # a placed unit at 20 s followed by a SILENT unit whose source timing opens at 5 s
    segs = [_seg(0, 20.0, 24.0, "Озвучено."), _seg(1, 5.0, 8.0, "Молчит.")]
    rows = _ru_cue_rows([_plan([0], 20.0, 24.0, 20.0, 4.0),
                         _plan([1], 5.0, 8.0, 5.0, 0.0)], segs, SR)
    assert all(rows[i][0] <= rows[i + 1][0] for i in range(len(rows) - 1)), rows
    assert all(b >= a for a, b, _ in rows), rows


def test_no_cue_is_ever_dropped() -> None:
    segs = [_seg(0, 0.0, 3.0, "Раз."), _seg(1, 3.0, 6.0, "Два."),
            _seg(2, 6.0, 9.0, "Три."), _seg(3, 9.0, 12.0, "Четыре.")]
    rows = _ru_cue_rows([_plan([0, 1], 0.0, 6.0, 0.0, 5.0),
                         _plan([2], 6.0, 9.0, 6.0, 0.0),        # silent
                         _plan([3], 9.0, 12.0, 9.0, 2.0)], segs, SR)
    assert len(rows) == len(segs), rows
    assert [t for _, _, t in rows] == [s["text_ru"] for s in segs], rows


def test_empty_text_tts_inside_a_spoken_unit_still_takes_a_slice() -> None:
    # an empty text_tts takes its width from text_ru, so the sentence still owns a slice and
    # the ones after it in the same unit do not inherit its time and read early
    segs = [_seg(0, 0.0, 4.0, "…", tts=""), _seg(1, 4.0, 8.0, "Реплика.", tts="Реплика.")]
    rows = _ru_cue_rows([_plan([0, 1], 0.0, 8.0, 0.0, 6.0)], segs, SR)
    assert len(rows) == 2, rows
    assert rows[0][0] == 0.0, rows
    assert rows[1][0] > rows[0][0], rows


def test_a_unit_with_no_text_at_all_does_not_divide_by_zero() -> None:
    # what the width floor actually buys: with every width 0 the char share divides by the
    # summed width, and an assemble crash here would take down a finished dub at the last step
    segs = [_seg(0, 0.0, 4.0, "   ", tts="  ")]
    rows = _ru_cue_rows([_plan([0], 0.0, 4.0, 0.0, 3.0)], segs, SR)
    assert len(rows) == 1, rows
    assert rows[0][0] == 0.0 and rows[0][1] >= rows[0][0], rows


def test_last_cue_does_not_run_past_its_audio() -> None:
    segs = [_seg(0, 0.0, 2.0, "Одно."), _seg(1, 2.0, 30.0, "Последнее.")]
    rows = _ru_cue_rows([_plan([0], 0.0, 2.0, 0.0, 2.0),
                         _plan([1], 2.0, 30.0, 2.0, 3.0)], segs, SR)
    assert round(rows[-1][1], 6) == 5.0, rows     # 2.0 + 3.0, not the 30 s source end


# a long line with a clause seam: _split_cue breaks it because it exceeds MAX_CUE_CHARS (84)
_LONG_RU = ("Сначала мы разберём, как именно устроен этот механизм внутри, "
            "а затем посмотрим, что он даёт на практике и чего стоит.")


def test_split_happens_over_the_SPOKEN_span_not_the_stretched_one() -> None:
    # THE regression this ordering exists to prevent (found by adversarial review of the first
    # landing, reproduced on real work dirs): stretch-then-split divides slot SILENCE by
    # character share, so the tail fragment opens deep inside the hole — measured 10.6 s past
    # its own audio, worse than the drift the placement fixes. Every fragment must OPEN inside
    # the audio; only the last one's END may hang over the silence.
    segs = [_seg(0, 0.0, 40.0, _LONG_RU), _seg(1, 40.0, 44.0, "Дальше.")]
    plans = [_plan([0], 0.0, 40.0, 0.0, 3.0),      # speaks 3 s, then a 37 s hole
             _plan([1], 40.0, 44.0, 40.0, 4.0)]
    rows = _ru_cue_rows(plans, segs, SR)
    unit0 = [r for r in rows if r[0] < 40.0]
    assert len(unit0) > 1, rows                    # the line really did split
    for a, _, _ in unit0:
        assert a <= 3.0 + 1e-9, (a, rows)          # every onset inside the spoken 3 s
    assert round(unit0[-1][1], 6) == 40.0, rows    # only the tail END reaches the next onset


def test_a_stretched_cue_is_not_split_again_downstream() -> None:
    # _ru_cue_rows returns FINAL rows. If a caller re-split them, the stretched tail would be
    # divided by char share all over again — the same defect.
    segs = [_seg(0, 0.0, 40.0, _LONG_RU)]
    rows = _ru_cue_rows([_plan([0], 0.0, 40.0, 0.0, 3.0)], segs, SR)
    joined = " ".join(t for _, _, t in rows)
    assert " ".join(joined.split()) == " ".join(_LONG_RU.split()), rows


def test_written_ru_srt_has_exactly_the_rows_it_was_given() -> None:
    # _write_ru_srt owns the "do not split twice" requirement so a call site cannot forget it.
    # A second split would turn the stretched tail into more cues than there are rows.
    segs = [_seg(0, 0.0, 40.0, _LONG_RU), _seg(1, 40.0, 44.0, "Дальше.")]
    plans = [_plan([0], 0.0, 40.0, 0.0, 3.0), _plan([1], 40.0, 44.0, 40.0, 4.0)]
    rows = _ru_cue_rows(plans, segs, SR)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "ru.srt"
        _write_ru_srt(path, plans, segs, SR)
        blocks = [b for b in path.read_text(encoding="utf-8").split("\n\n") if b.strip()]
    assert len(blocks) == len(rows), (len(blocks), len(rows))


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all assemble srt placement tests passed")
