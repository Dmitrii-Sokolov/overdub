"""Unit tests for the duration model and the tempo decision — pure, no audio, no ffmpeg.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_slot_fit.py   (or via pytest)

Contract. Silero has no supports_target, so fitting speech to its slot is the pipeline's job:
`target_chars` says how much russian the configured VOICE can say inside a slot, and `_tempo_for`
decides what assembly does with what it actually got. Two rules the numbers rest on: the rate is
per VOICE (eugene runs 35% faster than baya), and it takes two parameters, because Silero pays a
fixed ~163 ms per unit that does not scale with text — a single chars/sec constant under-predicts
every short unit.

An UNKNOWN voice must disable the model, never borrow another voice's rate: a wrong rate silently
mis-sizes every translation in the run, which is worse than not sizing them at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.config import Config  # noqa: E402
from overdub.stages.assemble import _tempo_for  # noqa: E402
from overdub.tts import target_chars, voice_rate  # noqa: E402


def _cfg(**kw) -> Config:
    cfg = Config()
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def test_rate_is_known_for_the_shipped_voice() -> None:
    cps, fixed = voice_rate(_cfg(tts_engine="silero", tts_voice="eugene"))
    assert 18.0 < cps < 21.0, cps                  # measured 19.85 over 247 units
    assert 0.0 < fixed < 0.5, fixed


def test_unknown_voice_disables_the_model_instead_of_guessing() -> None:
    assert voice_rate(_cfg(tts_engine="silero", tts_voice="no_such_voice")) is None
    assert target_chars(10.0, _cfg(tts_engine="silero", tts_voice="no_such_voice")) is None


def test_unknown_engine_has_no_rate() -> None:
    # the duration model is keyed on a MEASURED voice; anything else must return None rather
    # than borrow another engine's rate — a wrong rate mis-sizes every translation silently.
    assert voice_rate(_cfg(tts_engine="other")) is None
    assert target_chars(10.0, _cfg(tts_engine="other")) is None


def test_target_subtracts_the_fixed_per_unit_overhead() -> None:
    cfg = _cfg(tts_engine="silero", tts_voice="eugene")
    cps, fixed = voice_rate(cfg)
    assert target_chars(10.0, cfg) == round((10.0 - fixed) * cps)
    # the overhead must actually bite: a 1-param model would give strictly more
    assert target_chars(10.0, cfg) < round(10.0 * cps)


def test_target_scales_with_the_slot_and_never_goes_negative() -> None:
    cfg = _cfg(tts_engine="silero", tts_voice="eugene")
    assert target_chars(20.0, cfg) > target_chars(10.0, cfg) > target_chars(2.0, cfg)
    assert target_chars(0.05, cfg) == 0            # slot shorter than the overhead
    assert target_chars(None, cfg) is None


def test_voices_differ_enough_that_one_constant_would_not_do() -> None:
    slow = target_chars(10.0, _cfg(tts_engine="silero", tts_voice="baya"))
    fast = target_chars(10.0, _cfg(tts_engine="silero", tts_voice="eugene"))
    assert fast > slow * 1.2, (fast, slow)         # measured 19.85 vs 14.41 ch/s


def test_overlong_unit_is_compressed_and_reported_uncapped() -> None:
    req, factor, stretch = _tempo_for(nat=2000, slot=1000, cfg=_cfg())
    assert req == 2.0 and factor == 2.0 and stretch == 1.0


def test_absurd_compression_is_clamped_for_ffmpeg_but_not_for_the_report() -> None:
    req, factor, stretch = _tempo_for(nat=1_000_000, slot=1000, cfg=_cfg())
    assert req == 1000.0, req                      # the triage number stays true
    assert factor == 100.0, factor                 # only the filter argument is clamped


def test_underfilled_unit_is_stretched_toward_its_slot() -> None:
    req, factor, stretch = _tempo_for(nat=900, slot=1000, cfg=_cfg(atempo_floor=0.5))
    assert req == 1.0, req                         # compression demand stays floored
    assert abs(factor - 0.9) < 1e-9, factor
    assert factor == stretch


def test_stretch_never_passes_the_floor() -> None:
    cfg = _cfg(atempo_floor=0.85)
    _, factor, _ = _tempo_for(nat=100, slot=1000, cfg=cfg)     # would need 0.1
    assert factor == 0.85, factor


def test_floor_of_one_restores_speed_up_only_behaviour() -> None:
    req, factor, stretch = _tempo_for(nat=900, slot=1000, cfg=_cfg(atempo_floor=1.0))
    assert (req, factor, stretch) == (1.0, 1.0, 1.0)


def test_fill_target_below_one_leaves_air() -> None:
    # aiming at 90% of the slot must stretch LESS than aiming at all of it
    full = _tempo_for(nat=800, slot=1000, cfg=_cfg(atempo_floor=0.5, slot_fill_target=1.0))[1]
    airy = _tempo_for(nat=800, slot=1000, cfg=_cfg(atempo_floor=0.5, slot_fill_target=0.9))[1]
    assert full < airy < 1.0, (full, airy)


def test_last_unit_has_no_slot_and_is_left_alone() -> None:
    assert _tempo_for(nat=900, slot=None, cfg=_cfg(atempo_floor=0.5)) == (1.0, 1.0, 1.0)


def test_empty_unit_is_never_stretched() -> None:
    # a 0-sample render (empty_tts) must not be handed a 0.0 atempo factor
    assert _tempo_for(nat=0, slot=1000, cfg=_cfg(atempo_floor=0.5)) == (1.0, 1.0, 1.0)


def test_exactly_filled_unit_is_untouched() -> None:
    assert _tempo_for(nat=1000, slot=1000, cfg=_cfg(atempo_floor=0.5)) == (1.0, 1.0, 1.0)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all slot-fit tests passed")
