"""Unit tests for overdub.voices (palette voice per speaker) and the palette config — 2026-10-27.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_voices.py   (or via pytest)
No media: speakers_info entries written by hand, the shipped palettes and VOICE_TIMBRE.

The failure classes this pins:

  * THE DOMINANT SPEAKER GRABS THE PRIMARY VOICE. Matching is by timbre, never by speech time: a
    guest whose voice is eugene's gets eugene even if the host talks more.
  * A VOICE DEPENDS ON WHO ELSE IS IN THE VIDEO. The scale is the palette's, so one speaker's
    voice does not move when another speaker's timbre does.
  * AN INSERT TAKES A PARTICIPANT'S VOICE WHILE THE PALETTE HAS FREE ONES — or, past the palette,
    a voice that is not its closest participant's.
  * AN UNMEASURED SPEAKER IS DROPPED. No voiced frames must still yield a voice.
  * AN UNMEASURED PALETTE NAME IS SKIPPED. It must fail at the start, not be matched to nobody.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from overdub.config import Config                                  # noqa: E402
from overdub.tts import VOICE_TIMBRE, palettes, parse_voice      # noqa: E402
from overdub.voices import assign_voices                          # noqa: E402

PAL = palettes(Config())


def _spk(n, f0, df, words=100, main=True, pool=None):
    return {"speaker": n, "words": words, "main": main, "f0_hz": f0, "delta_f_hz": df,
            "pool": pool or ("female" if f0 and f0 > 175 else "male")}


def test_shipped_palettes_are_all_measured_and_male_starts_at_tts_voice() -> None:
    assert PAL["male"][0] == Config().tts_voice
    assert all(v in VOICE_TIMBRE for p in PAL.values() for v in p)
    assert parse_voice("aidar+formant=0.88") == ("aidar", 0.88)
    assert parse_voice("xenia") == ("xenia", 1.0)


def test_an_unmeasured_palette_voice_fails_loudly() -> None:
    cfg = Config()
    cfg.voice_palette_female = ["xenia", "kseniya+formant=1.5"]
    try:
        palettes(cfg)
    except ValueError as e:
        assert "kseniya+formant=1.5" in str(e)
    else:
        raise AssertionError("an unmeasured voice was accepted")


def test_single_male_and_single_female_take_their_pools_first_voice() -> None:
    assert assign_voices([_spk(0, 110, 980)], PAL, VOICE_TIMBRE) == {0: "eugene"}
    assert assign_voices([_spk(0, 250, 1250)], PAL, VOICE_TIMBRE) == {0: "xenia"}


def test_timbre_wins_over_speech_time() -> None:
    # the host talks most but sounds like aidar; the guest sounds like eugene
    got = assign_voices([_spk(0, 130, 945, words=5000), _spk(1, 94, 950, words=500)],
                        PAL, VOICE_TIMBRE)
    assert got == {0: "aidar", 1: "eugene"}, got


def test_a_voice_does_not_depend_on_the_other_speaker() -> None:
    a = assign_voices([_spk(0, 96, 955), _spk(1, 140, 940)], PAL, VOICE_TIMBRE)
    b = assign_voices([_spk(0, 96, 955), _spk(1, 125, 945)], PAL, VOICE_TIMBRE)
    assert a[0] == b[0] == "eugene"


def test_two_women_and_a_man_split_by_pool() -> None:
    got = assign_voices([_spk(0, 205, 1090), _spk(1, 115, 960), _spk(2, 255, 1260)],
                        PAL, VOICE_TIMBRE)
    assert got == {0: "xenia", 1: "eugene", 2: "kseniya"}, got


def test_an_insert_takes_the_next_free_voice_not_a_participants() -> None:
    got = assign_voices([_spk(0, 95, 950), _spk(1, 128, 943), _spk(2, 96, 955, words=5, main=False)],
                        PAL, VOICE_TIMBRE)
    assert got[2] not in (got[0], got[1]) and got[2] in PAL["male"][2:4], got


def test_past_the_palette_an_insert_speaks_as_its_closest_participant() -> None:
    mains = [_spk(i, 90 + 8 * i, 940 + 10 * i, words=1000) for i in range(6)]
    insert = _spk(9, 131, 990, words=3, main=False)                # closest to main 5
    got = assign_voices(mains + [insert], PAL, VOICE_TIMBRE)
    assert len({got[i] for i in range(6)}) == 6
    assert got[9] == got[5], got


def test_a_speaker_without_timbre_still_gets_a_voice() -> None:
    got = assign_voices([_spk(0, 95, 950), {"speaker": 1, "words": 3, "main": False,
                                            "f0_hz": None, "delta_f_hz": None, "pool": None}],
                        PAL, VOICE_TIMBRE)
    assert got == {0: "eugene", 1: "aidar"}, got


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all voices tests passed")
