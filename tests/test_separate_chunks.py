"""Chunked separation: the cut plan, and the stitch that has to be sample-exact.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_separate_chunks.py   (or via pytest)

WHY. htdemucs allocates its output tensor for all four stems across the WHOLE track even under
--two-stems, so peak memory is a linear function of duration (~1.41 MB per source second).
Measured 2026-08-11: a 7.90 h video asked for 37.4 GiB in one allocation and died on a 63.7 GB
host. Chunking caps that term; these tests cover the two ways chunking can quietly go wrong.

The load-bearing one is LENGTH. The bed is laid under a dub whose timeline came from the
transcript, so a bed even a few thousand frames short or long slides the music against the
picture for the rest of the video — and nothing downstream measures it. That is why the stitch
blends by weighted average over material extracted as OVERLAP rather than crossfading two
butt-joined pieces: a crossfade shortens by its own length, once per cut.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overdub.stages.separate import SR, _plan_chunks, _stitch_bed  # noqa: E402


def _signal(n: int) -> np.ndarray:
    """Deterministic stereo material — a sweep plus a ramp, so any splice shows as a jump."""
    t = np.arange(n, dtype=np.float32) / SR
    left = 0.4 * np.sin(2 * np.pi * 220.0 * t) + 0.3 * (t / max(t[-1], 1e-9))
    right = 0.4 * np.sin(2 * np.pi * 330.0 * t) - 0.3 * (t / max(t[-1], 1e-9))
    return np.stack([left, right], axis=1).astype(np.float32)


def _fake_stems(tmp: Path, sig: np.ndarray, plan: list[tuple[float, float]]) -> list:
    """A PERFECT separator: every chunk's stem is exactly its slice of the original.

    That is the point of the fixture — with a perfect separator the stitch has no excuse, so any
    deviation in the result is the blend's own doing and not the model's.
    """
    stems = []
    for i, (a, b) in enumerate(plan):
        p = tmp / f"stem_{i:03d}.wav"
        sf.write(p, sig[int(round(a * SR)):int(round(b * SR))], SR, subtype="PCM_16")
        stems.append((p, a))
    return stems


def test_cores_tile_the_track_exactly() -> None:
    # The overlap is extra material, never a moved boundary: the cores must still sum to the
    # track. If they did not, the bed would be longer or shorter than the video.
    for duration in (10000.0, 3600.0, 3600.5, 7200.0, 12345.6):
        plan = _plan_chunks(duration, 3600, 5.0)
        cores = sum(min((i + 1) * 3600, duration) - i * 3600 for i in range(len(plan)))
        assert abs(cores - duration) < 1e-6, duration


def test_windows_carry_overlap_and_clamp_at_both_ends() -> None:
    plan = _plan_chunks(10000.0, 3600, 5.0)
    assert len(plan) == 3
    assert plan[0][0] == 0.0                               # never seeks before the file
    assert plan[-1][1] == 10000.0                          # never reads past it
    assert plan[1] == (3595.0, 7205.0)                     # overlap on BOTH sides of the cut
    for (a, b), (c, _) in zip(plan, plan[1:]):
        assert c < b, "windows must overlap or there is nothing to blend"
        assert a < c


def test_no_chunking_below_the_threshold() -> None:
    assert len(_plan_chunks(3599.0, 3600, 5.0)) == 1


def test_stitch_preserves_length_exactly() -> None:
    # The sync property. Off-by-anything here is silent and permanent.
    dur = 12.0
    sig = _signal(int(dur * SR))
    plan = _plan_chunks(dur, 5, 1.0)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        out = tmp / "bed.wav"
        _stitch_bed(_fake_stems(tmp, sig, plan), out, dur, 1.0)
        got, rate = sf.read(out, always_2d=True)
    assert rate == SR
    assert len(got) == int(round(dur * SR)) == len(sig)


def test_stitch_reconstructs_a_perfectly_separated_track() -> None:
    # Weighted average of two identical estimates is that estimate — so a perfect separator must
    # come back through the blend unchanged. Catches a wrong ramp direction, a doubled overlap
    # and an equal-power law (which would bulge ~3 dB at every seam), none of which a
    # length check can see.
    dur = 12.0
    sig = _signal(int(dur * SR))
    plan = _plan_chunks(dur, 5, 1.0)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        out = tmp / "bed.wav"
        _stitch_bed(_fake_stems(tmp, sig, plan), out, dur, 1.0)
        got, _ = sf.read(out, always_2d=True, dtype="float32")
    assert np.max(np.abs(got - sig)) < 2e-4                # PCM_16 quantisation is ~3e-5


def test_stitch_leaves_no_step_at_the_seams() -> None:
    # A click is a discontinuity, not an amplitude error, so measure it as one: the largest
    # sample-to-sample jump in the stitched bed must not exceed the source's own.
    dur = 12.0
    sig = _signal(int(dur * SR))
    plan = _plan_chunks(dur, 5, 1.0)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        out = tmp / "bed.wav"
        _stitch_bed(_fake_stems(tmp, sig, plan), out, dur, 1.0)
        got, _ = sf.read(out, always_2d=True, dtype="float32")
    assert np.max(np.abs(np.diff(got, axis=0))) <= np.max(np.abs(np.diff(sig, axis=0))) + 2e-4


def test_a_short_last_stem_still_yields_a_full_length_bed() -> None:
    # The pad exists for exactly this and nothing in the tidy fixtures above reaches it
    # (mutation-checked 2026-08-11: deleting the pad broke no test until this one). If demucs
    # ever returns a stem a few frames shy, the bed must still be the length of the video —
    # trailing silence is a defect you cannot hear, a short bed slides the music against the
    # picture from that point on.
    dur = 12.0
    sig = _signal(int(dur * SR))
    plan = _plan_chunks(dur, 5, 1.0)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        stems = _fake_stems(tmp, sig, plan)
        last, start = stems[-1]
        clipped, _ = sf.read(last, always_2d=True, dtype="float32")
        sf.write(last, clipped[:-2000], SR, subtype="PCM_16")     # demucs came up short
        out = tmp / "bed.wav"
        _stitch_bed(stems, out, dur, 1.0)
        got, _ = sf.read(out, always_2d=True)
    assert len(got) == int(round(dur * SR))


def _marked_stems(tmp: Path, sig: np.ndarray, plan: list[tuple[float, float]],
                  step: float = 0.05) -> list:
    """Stems that DISAGREE in the overlap: chunk k carries a DC offset of k*step.

    The perfect-separator fixture above cannot see a blend's direction or its width, because
    a*w + b*(1-w) collapses to a when a == b — mutation-checked 2026-08-11, a reversed ramp and
    a halved blend zone both survived it. Two real separations of the same seconds differ
    slightly, so giving each chunk a constant signature restores what that fixture cancels: the
    output's offset now traces the ramp itself.
    """
    stems = []
    for i, (a, b) in enumerate(plan):
        p = tmp / f"marked_{i:03d}.wav"
        sf.write(p, sig[int(round(a * SR)):int(round(b * SR))] + i * step, SR, subtype="PCM_16")
        stems.append((p, a))
    return stems


def _marker(tmp: Path, dur: float, chunk: int, overlap: float) -> np.ndarray:
    sig = _signal(int(dur * SR))
    plan = _plan_chunks(dur, chunk, overlap)
    out = tmp / "bed.wav"
    _stitch_bed(_marked_stems(tmp, sig, plan), out, dur, overlap)
    got, _ = sf.read(out, always_2d=True, dtype="float32")
    return (got - sig).mean(axis=1)                        # the per-chunk signature, isolated


def test_blend_runs_from_the_earlier_chunk_to_the_later_one() -> None:
    # Direction. A reversed ramp still reconstructs an identical-stem fixture perfectly, and
    # still produces a bed that jumps to the NEXT chunk's content before the cut and back after.
    with tempfile.TemporaryDirectory() as d:
        m = _marker(Path(d), 12.0, 5, 1.0)
    assert abs(m[int(2.0 * SR)] - 0.00) < 3e-3             # solo chunk 0
    assert abs(m[int(7.5 * SR)] - 0.05) < 3e-3             # solo chunk 1
    assert abs(m[int(11.5 * SR)] - 0.10) < 3e-3            # solo chunk 2
    # The zone itself, at its two ends — this is what "direction" means and the only assertion
    # here that sees it. A per-sample monotonicity check does NOT: a reversed ramp slides back
    # by 5.7e-7 per sample, under any tolerance loose enough to allow PCM_16 quantisation.
    assert m[int(4.05 * SR)] < 0.010, "the blend must OPEN on the earlier chunk"
    assert m[int(5.95 * SR)] > 0.040, "and CLOSE on the later one"
    coarse = m[::SR // 2]                                  # half-second steps
    assert np.all(np.diff(coarse) > -1e-3), "the blend must never run backwards"


def test_blend_zone_spans_the_overlap_on_both_sides() -> None:
    # Width. The zone is 2*overlap by construction — one overlap before the cut and one after.
    # Halving it is inaudible in a fixture where the chunks agree, and audible where they do not.
    with tempfile.TemporaryDirectory() as d:
        m = _marker(Path(d), 12.0, 5, 1.0)
    lo = int(np.argmax(m > 0.0125))                        # 25% and 75% of the first step
    hi = int(np.argmax(m > 0.0375))
    assert abs((hi - lo) - 0.5 * 2 * 1.0 * SR) < 0.05 * SR


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all separate chunking tests passed")
