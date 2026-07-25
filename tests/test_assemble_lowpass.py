"""Unit tests for the dub-track low-pass gate (effective_lowpass) — pure, no audio, no ffmpeg.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_assemble_lowpass.py   (or via pytest)
Contract: the cutoff is applied only when it sits comfortably below Nyquist, so a 48 kHz
Silero track loses its vocoder hiss while a 24 kHz F5 track is left untouched (the filter
would ride F5's band edge and recolour the production engine for nothing). run() writes the
stamp from this function and done() re-derives it from the same one — a legacy stamp with no
lowpass_hz field reads as None and must NOT churn an F5 run, whose effective cutoff is also
None at the shipped default.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.config import Config             # noqa: E402
from overdub.stages.assemble import effective_lowpass  # noqa: E402

_SILERO_SR = 48000
_F5_SR = 24000


def test_silero_rate_applies_shipped_default() -> None:
    assert effective_lowpass(Config().dub_lowpass_hz, _SILERO_SR) == 11000


def test_f5_rate_skips_shipped_default() -> None:
    # 11 kHz vs 12 kHz Nyquist: the band edge. Skipped, so switching engines never silently
    # recolours the production track.
    assert effective_lowpass(Config().dub_lowpass_hz, _F5_SR) is None


def test_zero_disables() -> None:
    assert effective_lowpass(0, _SILERO_SR) is None


def test_missing_inputs_are_no_ops() -> None:
    # done() feeds this straight from a manifest that may predate the field.
    assert effective_lowpass(None, _SILERO_SR) is None
    assert effective_lowpass(11000, None) is None


def test_boundary_is_exclusive_at_four_tenths_rate() -> None:
    assert effective_lowpass(19199, _SILERO_SR) == 19199
    assert effective_lowpass(19200, _SILERO_SR) is None      # exactly 0.4*sr: not "comfortably"


def test_legacy_f5_stamp_does_not_churn() -> None:
    # The done() comparison, spelled out: absent field vs freshly derived cutoff.
    legacy_stamp: dict = {"synth_key": "k", "units_key": "u"}
    assert legacy_stamp.get("lowpass_hz") == effective_lowpass(Config().dub_lowpass_hz, _F5_SR)


def test_cutoff_change_invalidates_a_silero_dub() -> None:
    stamp = {"lowpass_hz": effective_lowpass(11000, _SILERO_SR)}
    assert stamp["lowpass_hz"] != effective_lowpass(9000, _SILERO_SR)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all lowpass gate tests passed")
