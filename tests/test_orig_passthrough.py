"""Unit tests for original-audio passthrough — the bed→original swap over uncovered speech.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_orig_passthrough.py   (or via pytest)
Pure: numpy arrays and tiny JSON artifacts, no ffmpeg, no media, no GPU.

Two invariants carry the feature and both are asserted directly:
  * the mask never covers a sample the DUB occupies — swapping there would play the English
    original underneath Russian speech, which is worse than the failure being fixed;
  * a sample OUTSIDE the mask is not written, not read and not scaled — "the rest of the mix is
    byte-identical to a build without this feature" is the acceptance criterion, so it is a test
    rather than a hope.
Plus the two absence contracts: None spans (unknown) are not an empty mask by accident, and a
mux stamped before the feature existed re-muxes exactly once, and only when it has spans.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import runreport                                        # noqa: E402
from overdub.config import Config                                    # noqa: E402
from overdub.pipeline import Context                                 # noqa: E402
from overdub.stages.mux import (MuxStage, _MIX_SR, _PASS_MIN_S,      # noqa: E402
                                passthrough_mask, swap_in_original)
from overdub.workdir import WorkDir                                  # noqa: E402

SR = _MIX_SR


# --- passthrough_mask ---------------------------------------------------------
def test_a_hole_with_no_dub_near_it_becomes_one_interval() -> None:
    assert passthrough_mask([(10.0, 20.0)], [], 60 * SR) == [(10 * SR, 20 * SR)]


def test_the_mask_never_covers_dub_audio() -> None:
    # a unit placed INSIDE the hole (its slot runs to the next unit's start, so it may spill
    # there) splits the mask in two rather than playing English under Russian
    mask = passthrough_mask([(10.0, 20.0)], [(12 * SR, 14 * SR)], 60 * SR)
    assert mask == [(10 * SR, 12 * SR), (14 * SR, 20 * SR)]
    for a, b in mask:
        assert b <= 12 * SR or a >= 14 * SR


def test_a_dub_covering_the_whole_hole_leaves_no_mask() -> None:
    assert passthrough_mask([(10.0, 20.0)], [(0, 30 * SR)], 60 * SR) == []


def test_overlapping_dub_intervals_trim_from_both_ends() -> None:
    mask = passthrough_mask([(10.0, 20.0)], [(5 * SR, 11 * SR), (19 * SR, 25 * SR)], 60 * SR)
    assert mask == [(11 * SR, 19 * SR)]


def test_slivers_are_dropped() -> None:
    # what is left between two units cannot carry a word; it would contribute a transient per
    # edge and nothing else
    tiny = _PASS_MIN_S / 2
    assert passthrough_mask([(10.0, 10.0 + tiny)], [], 60 * SR) == []
    assert passthrough_mask([(10.0, 10.0 + _PASS_MIN_S)], [], 60 * SR) == [
        (10 * SR, round((10.0 + _PASS_MIN_S) * SR))]


def test_the_mask_is_clipped_to_the_track() -> None:
    # the bed/original can be shorter than the transcript's last timestamp
    assert passthrough_mask([(10.0, 90.0)], [], 12 * SR) == [(10 * SR, 12 * SR)]


def test_unknown_spans_are_an_empty_mask_not_a_crash() -> None:
    assert passthrough_mask(None, [(0, SR)], 60 * SR) == []
    assert passthrough_mask([], None, 60 * SR) == []


def test_several_holes_come_back_in_order() -> None:
    assert passthrough_mask([(30.0, 40.0), (10.0, 20.0)], [], 60 * SR) == [
        (10 * SR, 20 * SR), (30 * SR, 40 * SR)]


# --- swap_in_original ---------------------------------------------------------
def _stereo(value: float, n: int) -> np.ndarray:
    return np.full((n, 2), value, dtype="float32")


def test_everything_outside_the_mask_is_untouched() -> None:
    base = _stereo(0.5, 10 * SR)
    before = base.copy()
    a, b = 3 * SR, 5 * SR
    swap_in_original(base, [(a, _stereo(-0.25, b - a))])
    assert np.array_equal(base[:a], before[:a])
    assert np.array_equal(base[b:], before[b:])


def test_the_middle_of_the_mask_is_the_original() -> None:
    base = _stereo(0.5, 10 * SR)
    a, b = 3 * SR, 5 * SR
    swap_in_original(base, [(a, _stereo(-0.25, b - a))])
    mid = (a + b) // 2
    assert abs(float(base[mid, 0]) - (-0.25)) < 1e-6


def test_the_edges_cross_fade_rather_than_cut() -> None:
    base = _stereo(1.0, 10 * SR)
    a, b = 3 * SR, 5 * SR
    swap_in_original(base, [(a, _stereo(0.0, b - a))])
    # first sample of the mask is still the bed, and the ramp is monotone into it: a hard cut
    # between two sources of different level and spectrum is an audible click
    assert abs(float(base[a, 0]) - 1.0) < 1e-6
    assert abs(float(base[b - 1, 0]) - 1.0) < 1e-3
    ramp = base[a:a + 1000, 0]
    assert np.all(np.diff(ramp) <= 1e-7)


def test_a_mask_shorter_than_two_fades_still_swaps() -> None:
    n = int(0.02 * SR)                                    # shorter than one 30 ms fade
    base = _stereo(1.0, SR)
    swapped = swap_in_original(base, [(100, _stereo(0.0, n))])
    assert abs(swapped - n / SR) < 1e-9
    assert float(base[100 + n // 2, 0]) < 1.0             # the original did reach the middle


def test_a_patch_running_past_the_track_is_truncated_not_a_crash() -> None:
    base = _stereo(1.0, SR)
    swapped = swap_in_original(base, [(SR - 1000, _stereo(0.0, 5000))])
    assert abs(swapped - 1000 / SR) < 1e-9


def test_swapped_seconds_are_the_sum_of_the_patches() -> None:
    base = _stereo(1.0, 10 * SR)
    swapped = swap_in_original(base, [(SR, _stereo(0.0, 2 * SR)),
                                      (5 * SR, _stereo(0.0, SR))])
    assert abs(swapped - 3.0) < 1e-9


# --- unrecovered_spans: absence is UNKNOWN ------------------------------------
def _work(td: str, detail=None) -> WorkDir:
    work = WorkDir.for_url("https://youtu.be/aaaaaaaaaaa", Path(td))
    if detail is not None:
        (work.root / "timings.json").write_text(
            json.dumps({"detail": {"transcribe": detail}}), encoding="utf-8")
    return work


def test_no_stamp_reads_as_unknown_not_as_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        assert runreport.unrecovered_spans(_work(td)) is None
        assert runreport.unrecovered_spans(_work(td, {"holes_unrecovered": 2})) is None


def test_an_empty_stamp_reads_as_checked_and_clean() -> None:
    with tempfile.TemporaryDirectory() as td:
        work = _work(td, {"holes_unrecovered": 0, "hole_spans_unrecovered": []})
        assert runreport.unrecovered_spans(work) == []


def test_spans_come_back_as_float_pairs() -> None:
    with tempfile.TemporaryDirectory() as td:
        work = _work(td, {"hole_spans_unrecovered": [[803.8, 818.7], [895, 900]]})
        assert runreport.unrecovered_spans(work) == [(803.8, 818.7), (895.0, 900.0)]


def test_a_torn_entry_drops_and_the_rest_stand() -> None:
    with tempfile.TemporaryDirectory() as td:
        work = _work(td, {"hole_spans_unrecovered": [[1.0, 2.0], [3.0], "nope", [5.0, 6.0]]})
        assert runreport.unrecovered_spans(work) == [(1.0, 2.0), (5.0, 6.0)]


# --- done(): a container muxed before the feature must not read as current -----
def _ctx(td: str, *, mix="bed", stamp=None, spans=None) -> Context:
    work = WorkDir.for_url("https://youtu.be/aaaaaaaaaaa", Path(td))
    for p in (work.dub_audio, work.en_srt):
        p.write_bytes(b"x")
        os.utime(p, (1000, 1000))
    work.output.write_bytes(b"x")                      # newer than every dep, or the make-style
    os.utime(work.output, (2000, 2000))                # mtime gate answers before this one
    work.report.write_text(json.dumps({"mux": stamp or {}}), encoding="utf-8")
    if spans is not None:
        (work.root / "timings.json").write_text(
            json.dumps({"detail": {"transcribe": {"hole_spans_unrecovered": spans}}}),
            encoding="utf-8")
    cfg = Config()
    cfg.dub_mix = mix
    return Context(url="u", cfg=cfg, work=work)


_LEGACY = {"dub_mix": "bed", "tracks": {"dub": True, "en_srt": True, "ru_srt": False}}


def test_a_legacy_mux_with_uncovered_speech_remuxes() -> None:
    with tempfile.TemporaryDirectory() as td:
        assert MuxStage().done(_ctx(td, stamp=_LEGACY, spans=[[10.0, 20.0]])) is False


def test_a_legacy_mux_without_uncovered_speech_is_left_alone() -> None:
    # the ~140 workdirs on disk must not each re-encode a multi-GB container for an identical file
    with tempfile.TemporaryDirectory() as td:
        assert MuxStage().done(_ctx(td, stamp=_LEGACY, spans=[])) is True
    with tempfile.TemporaryDirectory() as td:
        assert MuxStage().done(_ctx(td, stamp=_LEGACY)) is True


def test_a_stamped_zero_never_churns() -> None:
    with tempfile.TemporaryDirectory() as td:
        stamp = dict(_LEGACY, orig_passthrough_sec=0.0)
        assert MuxStage().done(_ctx(td, stamp=stamp, spans=[[10.0, 20.0]])) is True


def test_the_gate_is_bed_only() -> None:
    # duck already plays the original at full level across a hole; replace excludes it by contract
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td, mix="duck", stamp=dict(_LEGACY, dub_mix="duck"), spans=[[10.0, 20.0]])
        assert MuxStage().done(ctx) is True


# --- the stamp reaches run.json ------------------------------------------------
def test_run_json_carries_the_passthrough() -> None:
    with tempfile.TemporaryDirectory() as td:
        work = WorkDir.for_url("https://youtu.be/aaaaaaaaaaa", Path(td))
        work.report.write_text(json.dumps({
            "segments": [],
            "mux": {"dub_mix": "bed", "orig_passthrough_sec": 30.1,
                    "orig_passthrough_spans": 3}}), encoding="utf-8")
        run = runreport.build_run_report(work, Config())
        assert run["mux"]["orig_passthrough_sec"] == 30.1
        assert run["mux"]["orig_passthrough_spans"] == 3


def test_a_pre_feature_run_json_reads_unknown_not_zero() -> None:
    with tempfile.TemporaryDirectory() as td:
        work = WorkDir.for_url("https://youtu.be/aaaaaaaaaaa", Path(td))
        work.report.write_text(json.dumps({"segments": [], "mux": {"dub_mix": "bed"}}),
                               encoding="utf-8")
        run = runreport.build_run_report(work, Config())
        assert run["mux"]["orig_passthrough_sec"] is None


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all original-audio passthrough tests passed")
