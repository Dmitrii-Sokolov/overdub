"""Unit tests for overdub.timbre (F0 and formant spacing) — 2026-10-27.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_timbre.py   (or via pytest)
No media: a synthetic vowel — an impulse train at a known F0 through resonators at known formants.

The failure classes this pins:

  * A LOW VOICE READS AN OCTAVE HIGH. Without dividing out the window's own autocorrelation, the
    true peak at one period decays below the half-period one; eugene at x-low pitch (76 Hz)
    measured 156 Hz on the first version.
  * A FIXED FORMANT CEILING MISREADS A RAISED FEMALE VOICE. F4 leaves the analysis band and a +12%
    shift read as +3%; the ceiling follows the pool.
  * SILENCE READS AS A VOICE. No voiced frame must mean no value, not a default.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from overdub.timbre import grammatical_gender, pool_of, timbre   # noqa: E402

SR = 16000


def _vowel(f0: float, formants: list[float], sec: float = 2.0) -> np.ndarray:
    n = int(sec * SR)
    x = np.zeros(n)
    x[(np.arange(0, sec, 1.0 / f0) * SR).astype(int)] = 1.0
    for f in formants:                                   # two-pole resonator, 80 Hz bandwidth
        r = np.exp(-np.pi * 80.0 / SR)
        a1, a2 = 2 * r * np.cos(2 * np.pi * f / SR), -r * r
        y = np.zeros(n)
        for i in range(n):
            y[i] = x[i] + a1 * (y[i - 1] if i else 0.0) + a2 * (y[i - 2] if i > 1 else 0.0)
        x = y / np.abs(y).max()
    return x.astype(np.float32)


TUBE = [500.0, 1500.0, 2500.0, 3500.0]                   # an ideal uniform tube: ΔF = 1000 Hz


def test_f0_of_a_low_voice_is_not_doubled() -> None:
    t = timbre(_vowel(76.0, TUBE), SR, [(0.0, 2.0)])
    assert abs(t["f0_hz"] - 76.0) < 3.0, t


def test_f0_of_a_high_voice() -> None:
    t = timbre(_vowel(250.0, [f * 1.15 for f in TUBE]), SR, [(0.0, 2.0)])
    assert abs(t["f0_hz"] - 250.0) < 8.0, t


def test_formant_spacing_of_an_ideal_tube() -> None:
    t = timbre(_vowel(110.0, TUBE), SR, [(0.0, 2.0)])
    assert abs(t["delta_f_hz"] - 1000.0) < 50.0, t


def test_formant_spacing_follows_a_scaled_tract() -> None:
    small = timbre(_vowel(110.0, TUBE), SR, [(0.0, 2.0)])["delta_f_hz"]
    big = timbre(_vowel(110.0, [f * 1.12 for f in TUBE]), SR, [(0.0, 2.0)])["delta_f_hz"]
    assert 1.07 < big / small < 1.17, (small, big)


def test_only_the_spans_are_measured() -> None:
    audio = np.concatenate([_vowel(100.0, TUBE, 1.0), _vowel(220.0, TUBE, 1.0)])
    assert abs(timbre(audio, SR, [(1.0, 2.0)])["f0_hz"] - 220.0) < 8.0


def test_silence_has_no_timbre() -> None:
    t = timbre(np.zeros(SR * 2, dtype=np.int16), SR, [(0.0, 2.0)])
    assert t == {"f0_hz": None, "delta_f_hz": None, "voiced_frames": 0}, t


def test_outside_the_overlap_f0_decides() -> None:
    assert (pool_of(120.0, 1300.0), pool_of(230.0, 900.0), pool_of(None)) == ("male", "female", None)
    assert (grammatical_gender(120.0, 1300.0), grammatical_gender(230.0, 900.0)) == (
        "masculine", "feminine")


def test_inside_the_overlap_formant_spacing_decides() -> None:
    # 9GtcbnmldcY speaker 0: a man at 176 Hz with ΔF 922 — a pure F0 split called him female
    assert pool_of(176.0, 922.0) == "male"
    assert grammatical_gender(176.0, 922.0) == "masculine"
    assert pool_of(176.0, 1169.0) == "female"
    assert grammatical_gender(176.0, 1169.0) == "feminine"


def test_an_ambiguous_formant_spacing_picks_a_pool_but_not_a_grammar() -> None:
    assert pool_of(176.0, 1080.0) == "female"
    assert grammatical_gender(176.0, 1080.0) == "unknown"
    assert grammatical_gender(176.0, None) == "unknown"
    assert pool_of(176.0, None) == "female" and pool_of(170.0, None) == "male"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all timbre tests passed")
