"""Unit tests for overdub.transcript_md: sentences → paragraphs with speakers.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_transcript_md.py   (or via pytest)
No GPU, no media, no network.

The failure classes this pins:

  * TWO PEOPLE GLUED INTO ONE PARAGRAPH. A speaker change must break even with no pause at all.
  * A SINGLE-SPEAKER TRANSCRIPT GROWS LABELS. One voice reads as prose, not as a dialogue.
  * ROUTE E CHANGES SHAPE. Records without `speaker` must paragraph exactly as before.
  * A NO-SPEECH VIDEO PRODUCES AN EMPTY DOCUMENT.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from overdub import cli                                       # noqa: E402
from overdub.transcript_md import paragraphs, render_transcript   # noqa: E402
from overdub.workdir import WorkDir                           # noqa: E402


def _s(i: int, start: float, end: float, text: str, speaker=None) -> dict:
    rec = {"id": i, "start": start, "end": end, "text": text}
    if speaker is not None:
        rec["speaker"] = speaker
    return rec


def test_a_speaker_change_breaks_without_any_pause() -> None:
    paras = paragraphs([_s(0, 0.0, 1.0, "Hello.", 0), _s(1, 1.0, 2.0, "Hi there.", 1)])
    assert [(p["speaker"], p["text"]) for p in paras] == [(0, "Hello."), (1, "Hi there.")]


def test_the_same_speaker_without_a_pause_stays_one_paragraph() -> None:
    paras = paragraphs([_s(0, 0.0, 1.0, "One.", 2), _s(1, 1.1, 2.0, "Two.", 2)])
    assert len(paras) == 1 and paras[0]["text"] == "One. Two." and paras[0]["speaker"] == 2


def test_records_without_a_speaker_keep_the_route_e_shape() -> None:
    paras = paragraphs([_s(0, 0.0, 1.0, "A."), _s(1, 5.0, 6.0, "B.")])
    assert paras == [{"start": 0.0, "text": "A."}, {"start": 5.0, "text": "B."}]


def test_speaker_zero_is_a_speaker_not_a_missing_one() -> None:
    paras = paragraphs([_s(0, 0.0, 1.0, "A.", 0)])
    assert paras[0]["speaker"] == 0


def test_labels_appear_only_when_several_people_talk() -> None:
    two = render_transcript([_s(0, 0.0, 1.0, "Hello.", 0), _s(1, 1.0, 2.0, "Hi.", 1)],
                            title="T", duration=125.0)
    assert "**Speaker 0** [0:00]" in two and "**Speaker 1** [0:01]" in two
    assert "2 speakers" in two and "2:05" in two
    one = render_transcript([_s(0, 0.0, 1.0, "Hello.", 0), _s(1, 9.0, 10.0, "Again.", 0)],
                            title="T", duration=None)
    assert "Speaker" not in one and "speakers" not in one


def test_a_long_monologue_gets_periodic_timecodes() -> None:
    sents = [_s(i, i * 100.0, i * 100.0 + 50.0, f"Line {i}.", 0) for i in range(4)]
    md = render_transcript(sents, title="T", duration=None)
    assert "**[0:00]**" in md and "**[3:20]**" in md and "**[1:40]**" not in md


def test_no_speech_says_so() -> None:
    assert "_No speech detected._" in render_transcript([], title="T", duration=60.0)


def test_description_sits_between_the_header_and_the_body() -> None:
    md = render_transcript([_s(0, 0.0, 1.0, "Hello.", 0)], title="T", duration=None,
                           description="0:00 Intro\r\n12:30 Q&A\r\nGuest: Jane\n")
    assert "## Description\n\n0:00 Intro\n12:30 Q&A\nGuest: Jane\n\n## Transcript\n" in md
    assert md.index("## Description") < md.index("Hello.")
    for blank in (None, "", "  \n"):
        assert "## Description" not in render_transcript([_s(0, 0.0, 1.0, "Hi.", 0)], title="T",
                                                         duration=None, description=blank)


def test_finalize_writes_the_document_and_never_raises() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d) / "abc12345678")
        work.root.mkdir()
        ctx = type("C", (), {"work": work})()
        assert "no readable sentences.json" in cli._finalize_transcript(ctx)
        assert not work.transcript_md.exists()
        work.sentences.write_text(
            '[{"id": 0, "text": "Hi.", "start": 0.0, "end": 1.0, "speaker": 0},'
            ' {"id": 1, "text": "Yo.", "start": 1.0, "end": 2.0, "speaker": 1}]',
            encoding="utf-8")
        assert cli._finalize_transcript(ctx).startswith("transcribed")
        assert "Speaker 1" in work.transcript_md.read_text(encoding="utf-8")
        assert "## Description" not in work.transcript_md.read_text(encoding="utf-8")
        work.info_json.write_text('{"title": "T", "description": "Guest: Jane"}', encoding="utf-8")
        cli._finalize_transcript(ctx)
        assert "Guest: Jane" in work.transcript_md.read_text(encoding="utf-8")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all transcript_md tests passed")
