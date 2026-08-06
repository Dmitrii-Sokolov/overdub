"""Unit tests for the Parakeet ASR path — 2026-08-06.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_parakeet.py   (or via pytest)
No GPU, no NeMo, no media, no network. `scripts/parakeet_worker.py` imports nothing heavier than
the stdlib at module level (torch, soundfile, silero and nemo are all imported inside functions),
so its pure logic is testable from `.venv-asr` — which is the point: the decision-making code must
not be reachable only from the venv that needs a 5 GB install.

The failure classes this pins:

  * THE HOLE DETECTOR MEASURES THE WRONG GRAIN. It was first written to score whole VAD segments
    and found nothing at all: at min_silence 2000 ms a 12-minute video is often ONE segment, which
    is never entirely empty, so the 41 s hole in dwvBOwDjT64 stayed invisible while the code looked
    like it worked. It has to score GAPS INSIDE a segment.
  * A SEAM TRIM EATS THE END OF A SPEECH BLOCK. With VAD on, consecutive decode windows can belong
    to different blocks with dead air between them. The overlap trim is only valid where windows
    genuinely overlap; applied blindly it silently drops the last 7.5 s of every block.
  * PARAKEET INHERITS WHISPER'S PROVENANCE KEY. Its key must not carry a beam or a cond it does not
    have, and must move when the VAD gate moves — a gated video ships an EMPTY transcript, which is
    as different an artefact as a transcript gets.
  * THE ALIGNMENT GUARD LOOKS ALIVE ON AN ENGINE IT CANNOT WORK ON. floor_run_ratio keys on words
    pinned to the 0.02 s floor; Parakeet stamps on an 80 ms grid, so it is structurally 0.0 and the
    guard can never fire. The stage must not pretend otherwise.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import parakeet_worker as pw                                       # noqa: E402
from overdub.asr import asr_key, asr_key_core                      # noqa: E402
from overdub.config import Config                                  # noqa: E402
from overdub.pipeline import Context                               # noqa: E402
from overdub.stages.transcribe import TranscribeStage              # noqa: E402
from overdub.workdir import WorkDir                                # noqa: E402

URL = "https://youtu.be/xxxxxxxxxxx"


def _w(start: float, end: float, text: str = "x") -> dict:
    return {"text": text, "start": start, "end": end, "seg_end": False}


# --- 1. the hole detector -------------------------------------------------------------

def test_a_gap_inside_a_speech_segment_is_a_hole() -> None:
    # One segment of continuous speech, words at both ends, nothing in the middle: the VAD says
    # someone was talking there and the decoder returned nothing.
    spans = pw.uncovered_spans([(0.0, 51.0)], [_w(0.0, 1.0), _w(50.0, 51.0)])
    assert spans == [(1.0, 50.0)], spans


def test_an_untranscribed_segment_tail_is_a_hole_too() -> None:
    # The tail is where Parakeet actually fails: it stops early and the rest of the window comes
    # back empty (7 videos, 186 words, measured 2026-08-06 before the VAD gate moved the seams).
    spans = pw.uncovered_spans([(0.0, 60.0)], [_w(0.0, 1.0)])
    assert spans == [(1.0, 60.0)], spans


def test_a_short_gap_is_not_a_hole() -> None:
    # Ordinary breathing room. HOLE_MIN_SEC is what separates "a pause" from "missing speech".
    assert pw.uncovered_spans([(0.0, 30.0)], [_w(0.0, 1.0), _w(3.0, 30.0)]) == []


def test_a_whole_empty_segment_is_a_hole() -> None:
    spans = pw.uncovered_spans([(0.0, 10.0), (20.0, 40.0)], [_w(0.0, 9.0)])
    assert spans == [(20.0, 40.0)], spans


def test_holes_are_measured_per_segment_not_across_them() -> None:
    # The silence BETWEEN two segments is not a hole — the VAD already ruled it non-speech, and
    # flagging it would send every inter-segment pause back for a pointless second decode.
    spans = pw.uncovered_spans([(0.0, 10.0), (300.0, 310.0)],
                               [_w(0.0, 10.0), _w(300.0, 310.0)])
    assert spans == [], spans


def test_adjacent_holes_merge_into_one_reread() -> None:
    # Two empty stretches split by a single stray word cost two decodes if taken literally.
    spans = pw.uncovered_spans([(0.0, 40.0)], [_w(0.0, 0.5), _w(20.0, 20.3), _w(39.5, 40.0)])
    assert len(spans) == 1 and spans[0][0] < 20.0 < spans[0][1], spans


def test_no_segments_means_no_holes() -> None:
    # VAD gated the file: an empty transcript is the ANSWER there, not a defect to repair.
    assert pw.uncovered_spans([], []) == []
    assert pw.uncovered_spans([], [_w(0.0, 1.0)]) == []


# --- 2. stitching windows -------------------------------------------------------------

def test_the_seam_trim_applies_only_where_windows_overlap() -> None:
    # Two windows from DIFFERENT speech blocks: 0-100 and 300-400, no overlap. Trimming here would
    # delete every word in the last CHUNK_OVERLAP_SEC/2 of the first block.
    a = [_w(95.0, 99.0, "keep-me")]
    b = [_w(300.0, 301.0, "next")]
    out = pw._stitch([(0.0, 100.0, a), (300.0, 400.0, b)])
    assert [w["text"] for w in out] == ["keep-me", "next"], out


def test_overlapping_windows_are_cut_at_the_middle_of_the_overlap() -> None:
    # 0-600 and 585-1185 overlap by 15 s; the cut lands at 592.5, so each word survives once.
    early = [_w(590.0, 591.0, "early"), _w(596.0, 597.0, "late-from-first")]
    later = [_w(590.0, 591.0, "early-dup"), _w(596.0, 597.0, "late-from-second")]
    out = pw._stitch([(0.0, 600.0, early), (585.0, 1185.0, later)])
    assert [w["text"] for w in out] == ["early", "late-from-second"], out


# --- 3. provenance --------------------------------------------------------------------

def test_parakeet_key_names_the_engine_and_the_gate() -> None:
    cfg = Config(asr_engine="parakeet")
    assert asr_key(cfg) == "parakeet-tdt-0.6b-v3|vad=True", asr_key(cfg)
    assert asr_key(Config(asr_engine="parakeet", parakeet_vad=False)) != asr_key(cfg)


def test_parakeet_key_ignores_whisper_only_knobs() -> None:
    # Beam and context feedback do not exist for a greedy TDT decoder. Carrying them would claim a
    # difference between two transcripts that are byte-identical.
    base = asr_key(Config(asr_engine="parakeet"))
    for field, value in (("whisper_beam_size", 1), ("whisper_condition_on_previous", False),
                         ("whisper_compute_type", "int8_float16"), ("whisper_model", "small")):
        cfg = Config(asr_engine="parakeet")
        setattr(cfg, field, value)
        assert asr_key(cfg) == base, field


def test_parakeet_and_whisper_keys_can_never_collide() -> None:
    # The whole point of the stamp: two workdirs decoded by different engines must not read as one.
    assert asr_key(Config(asr_engine="parakeet")) != asr_key(Config(asr_engine="whisper"))


def test_parakeet_key_core_is_the_whole_key() -> None:
    # asr_key_core exists to drop the cond hatch, which parakeet has no equivalent of — so nothing
    # may be dropped, or a repair would accept a window from the other engine.
    key = asr_key(Config(asr_engine="parakeet"))
    assert asr_key_core(key) == key


def test_repair_style_cond_argument_is_accepted_and_ignored() -> None:
    # repair.py passes cond="mixed" positionally without knowing which engine wrote the file.
    key = asr_key(Config(asr_engine="parakeet"))
    assert asr_key(Config(asr_engine="parakeet"), cond="mixed") == key


# --- 4. the stage ---------------------------------------------------------------------

class _FakeWorker:
    """Stands in for the .venv-parakeet subprocess: returns canned words, counts the calls."""

    def __init__(self, words, meta=None) -> None:
        self.words = words
        self.meta = meta or {"holes": [], "hole_words_recovered": 0, "vad_blocks": 1,
                             "vad_speech_sec": 12.0}
        self.calls = 0

    def transcribe(self, wav):
        self.calls += 1
        return self.words, self.meta


class _FakeSession:
    def __init__(self, worker) -> None:
        self._worker = worker

    def parakeet(self, cfg):
        return self._worker

    def whisper(self, cfg, model, *, role):        # must never be reached on this path
        raise AssertionError("the parakeet path must not load whisper")


def _ctx(tmp: Path, worker) -> Context:
    cfg = Config(asr_engine="parakeet")
    cfg.work_root = tmp
    work = WorkDir(root=tmp / "vid")
    work.root.mkdir(parents=True, exist_ok=True)
    ctx = Context(url=URL, cfg=cfg, work=work)
    ctx.session = _FakeSession(worker)
    return ctx


def test_the_stage_writes_both_artifacts_and_never_touches_whisper() -> None:
    # Sentences long enough to clear MIN_SENT_CHARS — the resegmenter merges ultra-short ones into
    # a neighbour, so a two-word fixture would test _merge_short instead of this path.
    first = "The first sentence is long enough to stand alone."
    second = "And the second one also clears the merge threshold."
    words = ([{"text": t, "start": 0.0 + i * 0.4, "end": 0.3 + i * 0.4, "seg_end": False}
              for i, t in enumerate(first.split())]
             + [{"text": t, "start": 30.0 + i * 0.4, "end": 30.3 + i * 0.4, "seg_end": False}
                for i, t in enumerate(second.split())])
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), _FakeWorker(words))
        TranscribeStage().run(ctx)
        assert json.loads(ctx.work.words.read_text(encoding="utf-8")) == words
        sents = json.loads(ctx.work.sentences.read_text(encoding="utf-8"))
        assert [s["text"] for s in sents] == [first, second], sents
        assert [s["id"] for s in sents] == [0, 1]


def test_an_empty_transcript_is_written_not_raised() -> None:
    # The VAD gate returning nothing is the CORRECT answer for a silent video, and the pipeline
    # already treats an empty transcript as "ships without a dub" (DECISIONS 2026-08-06).
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), _FakeWorker([], {"holes": [], "hole_words_recovered": 0,
                                             "vad_blocks": 0, "vad_speech_sec": 0.0}))
        TranscribeStage().run(ctx)
        assert json.loads(ctx.work.sentences.read_text(encoding="utf-8")) == []
        assert json.loads(ctx.work.words.read_text(encoding="utf-8")) == []


def test_the_stage_stamps_the_parakeet_key_and_the_hole_count() -> None:
    meta = {"holes": [[10.0, 20.0], [30.0, 41.0]], "hole_words_recovered": 42,
            "vad_blocks": 2, "vad_speech_sec": 100.0}
    words = [{"text": "One.", "start": 0.0, "end": 0.4, "seg_end": True}]
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), _FakeWorker(words, meta))
        TranscribeStage().run(ctx)
        detail = json.loads((ctx.work.root / "timings.json").read_text(
            encoding="utf-8"))["detail"]["transcribe"]
        assert detail["asr_key"] == "parakeet-tdt-0.6b-v3|vad=True", detail
        assert detail["asr_repair_windows"] == 2, detail
        assert detail["hole_words_recovered"] == 42, detail


def test_the_stage_stamps_where_the_unrecovered_speech_is() -> None:
    """The worker knows the spans and its meta dies with the process — this stamp is the only
    record. Without it the report can say a video needs an ear but not where to put it, and the
    spans cannot be rebuilt later: they are defined against VAD segments that never hit the disk.
    """
    meta = {"holes": [[10.0, 20.0], [30.0, 41.0]], "hole_words_recovered": 42,
            "holes_unrecovered": [[30.0, 41.0]], "hole_sec_unrecovered": 11.0,
            "vad_blocks": 2, "vad_speech_sec": 100.0}
    words = [{"text": "One.", "start": 0.0, "end": 0.4, "seg_end": True}]
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), _FakeWorker(words, meta))
        TranscribeStage().run(ctx)
        detail = json.loads((ctx.work.root / "timings.json").read_text(
            encoding="utf-8"))["detail"]["transcribe"]
        assert detail["hole_spans_unrecovered"] == [[30.0, 41.0]], detail
        # The count stays beside them: it is what needs_triage reads, and a run predating the
        # spans still has to be tellable from one that was checked and came back clean.
        assert detail["holes_unrecovered"] == 1, detail


def test_the_stage_collapses_a_repetition_loop() -> None:
    # _dehallucinate is NOT whisper-only: Parakeet produced "That's the seven three" fifteen times
    # over a silent file (2026-08-06). Same defect shape, different engine.
    words = [{"text": "seven", "start": float(i), "end": float(i) + 0.5, "seg_end": False}
             for i in range(6)]
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), _FakeWorker(words))
        TranscribeStage().run(ctx)
        kept = json.loads(ctx.work.words.read_text(encoding="utf-8"))
        assert len(kept) == 1, kept


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all parakeet tests passed")
