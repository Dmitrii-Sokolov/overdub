"""Unit tests for transcribe's sentence boundaries + overlong split — pure, no ASR.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_transcribe_split.py  (or via pytest)
Guards the id149/id188 ear class: a whisper seg_end is NOT a speaker pause (73% carry a
0.000 s gap), so the pause branch requires real silence and no branch strands a bare
function word — and the clause branch never cuts before a determiner/object "that".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.stages.transcribe import W, _STOP, resegment  # noqa: E402


def words(*groups: tuple[str, float, float]) -> list[W]:
    """Each group: (text, start, end) — builds one W per space-split token, evenly spaced
    inside [start, end]; the group's last word carries seg_end. Real speaker pauses are
    expressed by a GAP between one group's end and the next group's start (see the two
    pause tests), never by a per-word field."""
    flat: list[W] = []
    for text, start, end in groups:
        toks = text.split()
        step = (end - start) / len(toks)
        for i, t in enumerate(toks):
            flat.append(W(t, start + i * step, start + (i + 1) * step,
                          seg_end=(i == len(toks) - 1)))
    return flat


def test_fake_pause_is_not_a_cut() -> None:
    # 18 s, no terminator -> must split. A ZERO-gap seg_end sits at the time midpoint
    # ("through"); a comma seam sits earlier. The VAD artifact must NOT win (bug B).
    flat = words(("many people i knew back then, they all played it through", 0.0, 9.0),
                 ("some kind of forum channel every single evening for hours", 9.0, 18.0))
    sents = resegment(flat)
    assert len(sents) == 2, sents
    assert sents[0]["text"].endswith("then,"), sents[0]["text"]


def test_real_pause_is_a_cut() -> None:
    # same text, but 0.4 s of real silence at the seg_end -> the pause branch may fire
    flat = words(("many people i knew back then, they all played it through", 0.0, 9.0),
                 ("some kind of forum channel every single evening for hours", 9.4, 18.4))
    sents = resegment(flat)
    assert len(sents) == 2, sents
    assert sents[0]["text"].endswith("through"), sents[0]["text"]


def test_no_cut_before_determiner_that() -> None:
    # 18 s, no terminator. The old code cut BEFORE "that" (it was in _CONJ), severing
    # "feel | that satisfaction" and handing Qwen a standalone "that ..." fragment — the
    # id150 cascade. The clause branch must now prefer the coordinating "but" and never open
    # a fragment with a bare "that".
    flat = words(("then yeah you're gonna you're gonna feel", 0.0, 9.0),
                 ("that satisfaction but if you're just looking to play something", 9.0, 18.0))
    sents = resegment(flat)
    assert len(sents) == 2, sents
    assert all(s["text"].split()[0].lower() != "that" for s in sents), sents
    assert sents[1]["text"].startswith("but"), sents[1]["text"]


def test_period_seg_end_before_lowercase_splits() -> None:      # item E, the id44 case
    flat = words(("this is not just a tool.", 0.0, 3.0),
                 ("it's a technology that can act on its own here", 3.0, 7.0))
    assert len(resegment(flat)) == 2, resegment(flat)


def test_abbrev_seg_end_is_not_a_boundary() -> None:            # E's FP guard
    flat = words(("i play a lot of games etc.", 0.0, 3.0),
                 ("and i still enjoy them quite a lot these days", 3.0, 7.0))
    assert len(resegment(flat)) == 1, resegment(flat)


def test_initial_seg_end_is_not_a_boundary() -> None:           # E's FP guard
    flat = words(("the video was made by j.", 0.0, 3.0),
                 ("smith and his team over many months of work", 3.0, 7.0))
    assert len(resegment(flat)) == 1, resegment(flat)


def test_clause_cut_never_strands_a_stop_word() -> None:
    flat = words(("we all sat down in the living room and", 0.0, 8.0),
                 ("so we started talking, then we kept playing for many hours", 8.0, 17.0))
    sents = resegment(flat)
    for s in sents[:-1]:
        last = s["text"].split()[-1].strip(",;:").lower()
        assert last not in _STOP, (last, [x["text"] for x in sents])


def test_no_cut_inside_a_hyphenated_compound() -> None:
    # whisper splits "shake-up" into "shake" + "-up"; a midpoint cut must not land between
    # them and hand Qwen a fragment opening with a bare "-up".
    flat = words(("i really do think that gamers are a lot like water when a big meta shake", 0.0, 10.0),
                 ("-up hits some game overnight the whole player base just adapts to it fast", 10.0, 20.0))
    sents = resegment(flat)
    assert all(not s["text"].startswith("-") for s in sents), sents


def test_split_invariants() -> None:
    flat = words(("no terminator anywhere in this very long run of speech at all", 0.0, 20.0),
                 ("and it just keeps going on and on without any punctuation here", 20.0, 44.0))
    sents = resegment(flat)
    assert [s["id"] for s in sents] == list(range(len(sents)))
    assert all(s["end"] - s["start"] <= 15.0 + 1e-6 for s in sents)
    assert " ".join(s["text"] for s in sents) == " ".join(w.text for w in flat)
    ss = [(s["start"], s["end"]) for s in sents]
    assert all(ss[i][1] <= ss[i + 1][0] for i in range(len(ss) - 1)), ss


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all split tests passed")
