"""Unit tests for transcribe's ultra-short sentence merge (_merge_short) — pure, no ASR.

Run: .venv-asr/Scripts/python.exe tests/test_transcribe_merge.py   (or via pytest)
Invariants: id contiguity, monotone non-overlapping spans, MERGE_GAP_MAX respected,
_too_long never violated by a merge, fixpoint chain collapse.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.stages.transcribe import (  # noqa: E402
    MIN_SENT_CHARS, W, _merge_short, resegment,
)


def words(*groups: tuple[str, float, float, float]) -> list[W]:
    """Each group: (text, start, end, word_gap) — builds one W per space-split token,
    evenly spaced inside [start, end]."""
    flat: list[W] = []
    for text, start, end, _gap in groups:
        toks = text.split()
        step = (end - start) / len(toks)
        for i, t in enumerate(toks):
            flat.append(W(t, start + i * step, start + (i + 1) * step,
                          seg_end=(i == len(toks) - 1)))
    return flat


def spans_of(sents: list[dict]) -> list[tuple[float, float]]:
    return [(s["start"], s["end"]) for s in sents]


def test_short_merges_into_prev_within_gap() -> None:
    flat = words(("This is a normal length sentence.", 0.0, 3.0, 0),
                 ("Decisions.", 3.2, 3.8, 0))              # 10 chars < 15, gap 0.2 <= 0.6
    sents = resegment(flat)
    assert len(sents) == 1, sents
    assert sents[0]["text"].endswith("Decisions.")
    assert sents[0]["start"] == 0.0 and sents[0]["end"] == 3.8


def test_no_merge_across_long_pause() -> None:
    flat = words(("This is a normal length sentence.", 0.0, 3.0, 0),
                 ("Decisions.", 4.5, 5.1, 0))              # gap 1.5 > MERGE_GAP_MAX
    sents = resegment(flat)
    assert len(sents) == 2, sents                          # isolated short stays (reseed net)


def test_merge_prefers_smaller_gap() -> None:
    flat = words(("First normal sentence here okay.", 0.0, 3.0, 0),
                 ("Yes.", 3.5, 3.9, 0),                    # gap prev 0.5, gap next 0.1
                 ("Second normal sentence follows now.", 4.0, 7.0, 0))
    sents = resegment(flat)
    assert len(sents) == 2, sents
    assert sents[1]["text"].startswith("Yes."), sents      # merged into NEXT (smaller gap)


def test_merge_respects_too_long() -> None:
    # direct _merge_short call isolates the _too_long guard (the same behavior is also
    # reachable via resegment — the 14.8 s span is under MAX_SEC so the splitter keeps it).
    # Merged span would run 0→15.2 s (> MAX_SEC) — the merge must be rejected and the
    # short one survives alone.
    flat = words(("A fairly long sentence that lasts almost the whole cap.", 0.0, 14.8, 0),
                 ("Hi.", 14.9, 15.2, 0))
    n_long = len(flat) - 1
    merged = _merge_short(flat, [(0, n_long - 1), (n_long, n_long)])
    assert merged == [(0, n_long - 1), (n_long, n_long)], merged


def test_chain_collapses_to_fixpoint() -> None:
    flat = words(("A normal opening sentence, quite long.", 0.0, 3.0, 0),
                 ("One.", 3.1, 3.4, 0),
                 ("Two.", 3.5, 3.8, 0),
                 ("Three.", 3.9, 4.2, 0))
    sents = resegment(flat)
    assert len(sents) == 1, sents                          # whole chain folds into the opener


def test_ids_contiguous_and_monotone() -> None:
    flat = words(("First normal sentence in the set.", 0.0, 3.0, 0),
                 ("Ok.", 3.1, 3.3, 0),
                 ("Another normal sentence right after that one.", 3.4, 6.5, 0),
                 ("Final one, also of a normal length.", 7.0, 10.0, 0))
    sents = resegment(flat)
    assert [s["id"] for s in sents] == list(range(len(sents)))
    ss = spans_of(sents)
    assert all(a < b for a, b in ss)
    assert all(ss[i][1] <= ss[i + 1][0] for i in range(len(ss) - 1)), ss


def test_normal_sentences_untouched() -> None:
    flat = words(("This sentence is long enough to stand.", 0.0, 3.0, 0),
                 ("And so is this one, no merging needed.", 3.5, 6.5, 0))
    assert len(resegment(flat)) == 2


def test_merge_short_pure_spans() -> None:
    flat = words(("Normal sentence number one right here.", 0.0, 3.0, 0),
                 ("No.", 3.2, 3.4, 0))
    spans = [(0, 5), (6, 6)]                               # 6-word sentence + "No."
    merged = _merge_short(flat, spans)
    assert merged == [(0, 6)], merged
    assert MIN_SENT_CHARS > len("No."), "threshold sanity"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all merge tests passed")
