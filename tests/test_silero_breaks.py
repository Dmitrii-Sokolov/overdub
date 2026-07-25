"""Unit tests for SSML break restoration (silero.build_ssml) — pure, no model, no audio.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_silero_breaks.py   (or via pytest)
Contract: a grouped unit gets its ORIGINAL inter-sentence pauses back as <break>, and the
builder DECLINES (returns None → plain-text synthesis) whenever it cannot prove where a pause
belongs. Declining matters more than emitting: `text` is what verify compares against, so a
misplaced pause is silent damage, while falling back to plain text only loses the improvement.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.stages.synthesize import build_units  # noqa: E402
from overdub.tts.silero import MAX_BREAK_MS, MIN_BREAK_MS, build_ssml  # noqa: E402


def seg(i: int, a: float, b: float, text: str) -> dict:
    return {"id": i, "start": a, "end": b, "text_tts": text}


def test_singleton_unit_gets_no_markup() -> None:
    assert build_ssml("Одно предложение.", []) is None
    assert build_ssml("Одно предложение.", None) is None


def test_pause_is_restored_at_its_measured_length() -> None:
    out = build_ssml("Первое. Второе.", [0.8])
    assert out == '<speak>Первое. <break time="800ms"/> Второе.</speak>', out


def test_short_gap_emits_no_break() -> None:
    # Below the floor a break reads as no pause at all — emit nothing rather than markup noise.
    out = build_ssml("Первое. Второе.", [MIN_BREAK_MS / 1000 - 0.01])
    assert "<break" not in out and "Первое." in out and "Второе." in out


def test_long_gap_is_capped() -> None:
    out = build_ssml("Первое. Второе.", [9.0])
    assert f'time="{MAX_BREAK_MS}ms"' in out, out


def test_declines_when_split_disagrees_with_members() -> None:
    # Two members but the joined text has no interior terminator: the split yields one part,
    # so there is no defensible place for the pause.
    assert build_ssml("Первое и второе", [0.5]) is None


def test_escapes_markup_characters() -> None:
    out = build_ssml("Цена < трёх. Больше & лучше.", [0.4])
    assert "&lt;" in out and "&amp;" in out and "<speak>" in out


def test_gaps_match_what_grouping_swallowed() -> None:
    # The end-to-end invariant: build_units records one gap per join, and build_ssml accepts
    # exactly that shape — the two sides cannot drift apart silently.
    segs = [seg(0, 0.0, 2.0, "Первое."), seg(1, 2.5, 4.0, "Второе."),
            seg(2, 4.3, 6.0, "Третье.")]
    unit = build_units(segs, gap_max=1.2)[0]
    assert unit["ids"] == [0, 1, 2]
    assert unit["gaps"] == [0.5, 0.3]
    out = build_ssml(unit["text"], unit["gaps"])
    assert out.count("<break") == 2 and '"500ms"' in out and '"300ms"' in out, out


def test_ungrouped_sentences_carry_empty_gaps() -> None:
    segs = [seg(0, 0.0, 2.0, "Первое."), seg(1, 9.0, 11.0, "Второе.")]
    units = build_units(segs, gap_max=1.2)
    assert [u["gaps"] for u in units] == [[], []]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all silero break tests passed")
