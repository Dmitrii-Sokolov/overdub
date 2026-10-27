"""Unit tests for the diarize stage and the speaker boundary in resegment — 2026-10-27.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_diarize.py   (or via pytest)
No GPU, no NeMo, no media: the diarization worker is replaced by canned segments.

The failure classes this pins:

  * TWO PEOPLE'S LINES READ AS ONE. Unpunctuated turns ("...you wanted to share" / "No we never
    agreed") used to land in one sentence, and the short-sentence merge glued a "Yes." from one
    speaker onto the other's line. A speaker change must be a hard boundary in both places.
  * A SINGLE-SPEAKER VIDEO IS TOUCHED. The corpus is single-speaker by selection; diarizing an old
    workdir must leave its transcript and translation byte-for-byte alone, or every old video
    silently loses a Sonnet translation.
  * A RE-CUT KEEPS A STALE TRANSLATION. When sentences.json changes, translation.json describes
    sentences that no longer exist — it must be preserved aside and removed, not left in place.
  * A REPAIR IS UNDONE. A --repair-asr transcript is not derivable from words.json, so a re-cut
    from the words would silently revert it.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from overdub.config import Config                                   # noqa: E402
from overdub.pipeline import Context                                # noqa: E402
from overdub.stages.diarize import (ISLAND_MAX_WORDS, DiarizeStage,  # noqa: E402
                                    assign_speakers, smooth_islands)
from overdub.stages.transcribe import W, resegment                  # noqa: E402
from overdub.workdir import WorkDir                                 # noqa: E402

URL = "https://youtu.be/xxxxxxxxxxx"

ASK = "Is that the plan you wanted to share with all of us"     # no terminator: one sentence
NO = "No we never agreed on any of that."


def _words(text: str, t0: float, step: float = 0.3) -> list[dict]:
    return [{"text": t, "start": round(t0 + i * step, 3), "end": round(t0 + i * step + 0.25, 3),
             "seg_end": False} for i, t in enumerate(text.split())]


def _seg(start: float, end: float, speaker: str) -> dict:
    return {"start": start, "end": end, "speaker": speaker}


WORDS = _words(ASK, 0.0) + _words(NO, 4.0)
TWO = [_seg(0.0, 3.6, "speaker_1"), _seg(3.9, 6.5, "speaker_0")]
ONE = [_seg(0.0, 6.5, "speaker_0")]


# --- 1. word → speaker ------------------------------------------------------------------

def test_a_word_goes_to_the_speaker_it_overlaps_most() -> None:
    words = [{"start": 1.0, "end": 2.0}]
    segs = [_seg(0.0, 1.2, "a"), _seg(1.2, 2.0, "b")]
    assert assign_speakers(words, segs) == [0]          # b: 0.8 s of the word, a: 0.2 s
    assert assign_speakers(words, [_seg(0.0, 1.8, "a"), _seg(1.8, 2.0, "b")]) == [0]


def test_a_word_in_a_gap_goes_to_the_nearest_segment() -> None:
    words = [{"start": 0.0, "end": 0.5}, {"start": 5.0, "end": 5.2}, {"start": 9.0, "end": 9.4}]
    segs = [_seg(0.0, 1.0, "a"), _seg(5.8, 9.5, "b")]
    assert assign_speakers(words, segs) == [0, 1, 1]    # 5.1 is 0.7 s from b, 4.1 s from a


def test_speakers_are_numbered_by_first_appearance_among_words() -> None:
    # the diarizer's own labels are arbitrary; the numbering must not depend on them, and a label
    # that owns no word (a false split of a few frames) must not take a number
    words = [{"start": 0.0, "end": 0.5}, {"start": 2.0, "end": 2.5}]
    segs = [_seg(0.0, 1.0, "speaker_3"), _seg(1.9, 3.0, "speaker_0"), _seg(10.0, 10.1, "speaker_2")]
    assert assign_speakers(words, segs) == [0, 1]


def test_no_segments_means_no_speakers() -> None:
    assert assign_speakers([{"start": 0.0, "end": 1.0}], []) == [None]


# --- 2. the speaker boundary in resegment -----------------------------------------------

def _flat(words: list[dict], labels) -> list[W]:
    return [W(w["text"], w["start"], w["end"], w["seg_end"], lab) for w, lab in zip(words, labels)]


def test_an_unpunctuated_turn_change_splits_the_sentence() -> None:
    plain = resegment(_flat(WORDS, [None] * len(WORDS)))
    assert len(plain) == 1, plain                       # the defect: two turns, one sentence
    labels = assign_speakers(WORDS, TWO)
    cut = resegment(_flat(WORDS, labels))
    assert [s["text"] for s in cut] == [ASK, NO], cut
    assert [s["speaker"] for s in cut] == [0, 1]


def test_a_short_reply_is_not_merged_into_the_other_speakers_line() -> None:
    words = _words("This sentence is comfortably long enough to stand alone.", 0.0) + _words("Yes.", 2.9)
    plain = resegment(_flat(words, [None] * len(words)))
    assert len(plain) == 1, plain                       # "Yes." merges into its neighbour
    labels = [0] * (len(words) - 1) + [1]
    cut = resegment(_flat(words, labels))
    assert [s["text"] for s in cut][-1] == "Yes.", cut


def test_a_single_speaker_transcript_carries_no_speaker_field() -> None:
    assert all("speaker" not in s for s in resegment(_flat(WORDS, [None] * len(WORDS))))


# --- 2b. islands -------------------------------------------------------------------------

def _speakers_after_smoothing(text: str, labels: list[int]) -> list[int]:
    flat = _flat(_words(text, 0.0), labels)
    smooth_islands(flat)
    return [w.speaker for w in flat]


def test_a_short_island_inside_an_unfinished_sentence_goes_back() -> None:
    # "...correct all the | time." — the speaker's own word under the listener's "right"
    assert _speakers_after_smoothing("they are correct all the time.", [1, 1, 1, 1, 1, 0]) == [1] * 6


def test_a_chain_of_islands_resolves_to_the_speaker_before_them() -> None:
    # "And then | Mac | minis." measured on z7cNbsr3b5s: two islands, two different labels
    assert _speakers_after_smoothing("And then Mac minis.", [1, 1, 0, 2]) == [1, 1, 1, 1]


def test_a_backchannel_after_a_finished_sentence_keeps_its_speaker() -> None:
    assert _speakers_after_smoothing("It is correct. Right. And so on.",
                                     [1, 1, 1, 0, 1, 1, 1]) == [1, 1, 1, 0, 1, 1, 1]


def test_a_real_interruption_mid_sentence_is_kept() -> None:
    labels = [1, 1, 1] + [0] * (ISLAND_MAX_WORDS + 1)
    assert _speakers_after_smoothing("so the plan was no that is not right", labels) == labels


# --- 3. the stage -----------------------------------------------------------------------

class _FakeDiarizer:
    def __init__(self, segments) -> None:
        self.segments = segments
        self.calls = 0

    def diarize(self, wav):
        self.calls += 1
        return self.segments, {"model": "fake", "n_speakers": len({s["speaker"] for s in self.segments})}


class _FakeSession:
    def __init__(self, diarizer) -> None:
        self._d = diarizer

    def diarizer(self, cfg):
        return self._d


def _ctx(tmp: Path, segments, *, translated: bool = True) -> Context:
    cfg = Config()
    cfg.work_root = tmp
    work = WorkDir(root=tmp / "vid")
    work.root.mkdir(parents=True, exist_ok=True)
    work.words.write_text(json.dumps(WORDS), encoding="utf-8")
    sf.write(str(work.source_audio), np.zeros(16000 * 7, dtype=np.int16), 16000)
    work.sentences.write_text(json.dumps(resegment(_flat(WORDS, [None] * len(WORDS))), indent=2),
                              encoding="utf-8")
    if translated:
        work.translation.write_text('[{"id": 0, "text_ru": "x"}]', encoding="utf-8")
    ctx = Context(url=URL, cfg=cfg, work=work)
    ctx.session = _FakeSession(_FakeDiarizer(segments))
    return ctx


def test_one_speaker_leaves_the_transcript_and_translation_untouched() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), ONE)
        before = (ctx.work.sentences.read_bytes(), ctx.work.translation.read_bytes())
        DiarizeStage().run(ctx)
        assert (ctx.work.sentences.read_bytes(), ctx.work.translation.read_bytes()) == before
        assert not ctx.work.pre_diarize_translation.exists()
        assert json.loads(ctx.work.diar.read_text(encoding="utf-8"))["speakers"] == 1
        assert DiarizeStage().done(ctx)


def test_two_speakers_recut_the_transcript_and_retire_the_translation() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), TWO)
        old_translation = ctx.work.translation.read_bytes()
        DiarizeStage().run(ctx)
        sents = json.loads(ctx.work.sentences.read_text(encoding="utf-8"))
        assert [s["speaker"] for s in sents] == [0, 1], sents
        assert not ctx.work.translation.exists()
        assert ctx.work.pre_diarize_translation.read_bytes() == old_translation
        assert json.loads(ctx.work.words.read_text(encoding="utf-8")) == WORDS   # never written


def test_a_speaker_owning_only_an_island_is_not_counted() -> None:
    # the z7cNbsr3b5s false split: a fourth "speaker" with one word, inside another's sentence
    segs = [_seg(0.0, 3.6, "a"), _seg(1.4, 1.6, "ghost"), _seg(3.9, 6.5, "b")]
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), segs)
        DiarizeStage().run(ctx)
        assert json.loads(ctx.work.diar.read_text(encoding="utf-8"))["speakers"] == 2
        sents = json.loads(ctx.work.sentences.read_text(encoding="utf-8"))
        assert [s["text"] for s in sents] == [ASK, NO], sents


def test_a_rerun_with_the_same_cut_keeps_the_new_translation() -> None:
    # after the re-cut, route B translates the new sentences; diarizing again (--force) yields the
    # same cut and must not throw that translation away
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), TWO)
        DiarizeStage().run(ctx)
        ctx.work.translation.write_text('[{"id": 0}, {"id": 1}]', encoding="utf-8")
        DiarizeStage().run(ctx)
        assert ctx.work.translation.read_text(encoding="utf-8") == '[{"id": 0}, {"id": 1}]'


def test_a_repaired_transcript_with_two_speakers_raises_and_stays_not_done() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), TWO)
        ctx.work.pre_repair_sentences.write_text("[]", encoding="utf-8")
        before = ctx.work.sentences.read_bytes()
        try:
            DiarizeStage().run(ctx)
        except RuntimeError as e:
            assert "repair" in str(e)
        else:
            raise AssertionError("a re-cut over a repaired transcript must raise")
        assert ctx.work.sentences.read_bytes() == before
        assert not DiarizeStage().done(ctx)


def test_no_words_skips_the_model() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), TWO, translated=False)
        ctx.work.words.write_text("[]", encoding="utf-8")
        DiarizeStage().run(ctx)
        assert ctx.session._d.calls == 0
        assert json.loads(ctx.work.diar.read_text(encoding="utf-8"))["speakers"] == 0


def test_silence_yields_no_timbre_rather_than_a_voice() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), ONE)
        DiarizeStage().run(ctx)
        info = json.loads(ctx.work.diar.read_text(encoding="utf-8"))["speakers_info"]
        assert info == [{"speaker": 0, "words": len(WORDS), "f0_hz": None, "delta_f_hz": None,
                         "voiced_frames": 0, "pool": None, "gender": "unknown"}], info


def test_diarize_off_is_done_without_an_artifact() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), TWO)
        ctx.cfg.diarize = False
        assert DiarizeStage().done(ctx)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all diarize tests passed")
