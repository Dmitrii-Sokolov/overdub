"""Unit tests for the dead-air layers: build_units (grouping) + plan_speed (slot-fill).

Run: .venv-asr/Scripts/python.exe tests/test_units_speed.py   (or via pytest)
Pure functions — no GPU, no worker.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.config import Config  # noqa: E402
from overdub.stages.synthesize import (  # noqa: E402
    _GROUP_MAX_CHARS, _GROUP_MAX_SPAN, build_units, unit_sim_threshold, units_of)
from overdub.tts.f5 import plan_speed  # noqa: E402


def seg(i, start, end, text="Нормальное предложение для теста."):
    return {"id": i, "start": start, "end": end, "text_tts": text}


# ---- build_units -------------------------------------------------------------
def test_adjacent_sentences_group() -> None:
    units = build_units([seg(0, 0.0, 2.0), seg(1, 2.2, 4.0), seg(2, 4.1, 6.0)], 0.4)
    assert [u["ids"] for u in units] == [[0, 1, 2]], units
    assert units[0]["start"] == 0.0 and units[0]["end"] == 6.0


def test_large_gap_breaks_chain() -> None:
    units = build_units([seg(0, 0.0, 2.0), seg(1, 3.0, 5.0)], 0.4)   # gap 1.0 > 0.4
    assert [u["ids"] for u in units] == [[0], [1]], units


def test_empty_text_is_singleton_chain_breaker() -> None:
    units = build_units([seg(0, 0.0, 2.0), seg(1, 2.1, 4.0, text=""), seg(2, 4.1, 6.0)], 0.4)
    assert [u["ids"] for u in units] == [[0], [1], [2]], units
    assert units[1]["text"] == ""


def test_span_cap_respected() -> None:
    segs = [seg(i, i * 5.0, i * 5.0 + 4.9) for i in range(5)]        # gaps 0.1, spans add up
    units = build_units(segs, 0.4)
    for u in units:
        assert u["end"] - u["start"] <= _GROUP_MAX_SPAN + 1e-9, u


def test_char_cap_respected() -> None:
    long_text = "х" * 140
    units = build_units([seg(0, 0.0, 1.0, long_text), seg(1, 1.1, 2.0, long_text),
                         seg(2, 2.1, 3.0, long_text)], 0.4)
    for u in units:
        assert len(u["text"]) <= _GROUP_MAX_CHARS, len(u["text"])


def test_ids_cover_exactly() -> None:
    segs = [seg(i, i * 2.0, i * 2.0 + 1.5) for i in range(7)]
    units = build_units(segs, 0.4)
    assert sorted(i for u in units for i in u["ids"]) == list(range(7))


def test_gap_zero_disables_grouping() -> None:
    # gap_max=0.0 must disable grouping even for exact-zero gaps (clamped word timings
    # can produce them), or the documented "0.0 disables" contract silently lies
    units = build_units([seg(0, 0.0, 2.0), seg(1, 2.0, 4.0)], 0.0)
    assert [u["ids"] for u in units] == [[0], [1]], units


def test_units_of_legacy_segments() -> None:
    doc = {"segments": [{"id": 0, "text_tts": "а", "samples": 10},
                        {"id": 1, "text_tts": "б", "samples": 20}]}
    units = units_of(doc)
    assert [u["ids"] for u in units] == [[0], [1]]
    assert units[0]["samples"] == 10


# ---- plan_speed ----------------------------------------------------------------
REF = dict(ref_sec=10.0, ref_bytes=200, base_speed=1.0, floor=0.75, ceil=1.6)


def _speed(gen_bytes, target, mx):
    return plan_speed(gen_bytes, REF["ref_sec"], REF["ref_bytes"], REF["base_speed"],
                      REF["floor"], REF["ceil"], target, mx)


def test_underfill_stretches_to_span() -> None:
    # nominal = 10*100/200 = 5.0 s; span 6.0 → speed 5/6 ≈ 0.833 (above floor)
    assert abs(_speed(100, 6.0, 8.0) - 5.0 / 6.0) < 1e-9


def test_stretch_capped_at_floor() -> None:
    # nominal 5.0 s; span 10.0 → uncapped 0.5 < floor 0.75 → floor
    assert _speed(100, 10.0, 12.0) == 0.75


def test_fits_slot_neutral() -> None:
    # nominal 5.0 s; span 4.0, slot 6.0 → spill absorbed by gap → base speed
    assert _speed(100, 4.0, 6.0) == 1.0


def test_overflow_compresses_to_slot() -> None:
    # nominal 5.0 s; span 3.0, slot 4.0 → speed 5/4 = 1.25 (below ceil)
    assert abs(_speed(100, 3.0, 4.0) - 1.25) < 1e-9


def test_compression_capped_at_ceil() -> None:
    # nominal 10.0 s; slot 4.0 → uncapped 2.5 > ceil 1.6 → ceil (atempo tops up)
    assert _speed(200, 3.0, 4.0) == 1.6


def test_no_target_means_base_speed() -> None:
    assert _speed(100, None, None) == 1.0


def test_last_unit_no_slot_still_stretches() -> None:
    # nominal 5.0 s; span 6.0, no slot (last unit) → stretch to span
    assert abs(_speed(100, 6.0, None) - 5.0 / 6.0) < 1e-9


def test_base_speed_scales_window() -> None:
    # narrator recalibrated to 1.2: caps move with it (multipliers)
    s = plan_speed(100, 10.0, 200, 1.2, 0.75, 1.6, 10.0, None)
    # nominal at base = 5/1.2 ≈ 4.17 s < 10 → stretch: 100*10/200 * 1.2 / 10 = 0.6 < 0.9 floor → 0.9
    assert abs(s - 0.75 * 1.2) < 1e-9


# ---- unit_sim_threshold ----------------------------------------------------------
def test_sim_threshold_stricter_for_compressed_units() -> None:
    cfg = Config()                                                   # f5_speed=1.0, 0.8/0.9
    assert unit_sim_threshold(cfg, None) == cfg.similarity_threshold           # silero/legacy
    assert unit_sim_threshold(cfg, cfg.f5_speed) == cfg.similarity_threshold   # neutral
    assert unit_sim_threshold(cfg, cfg.f5_speed * 0.8) == cfg.similarity_threshold  # stretched
    assert unit_sim_threshold(cfg, cfg.f5_speed * 1.05) == cfg.similarity_threshold_compressed


def test_sim_threshold_never_relaxes() -> None:
    # a compressed gate below the base threshold must not weaken the base gate
    cfg = Config()
    cfg.similarity_threshold = 0.95
    cfg.similarity_threshold_compressed = 0.9
    assert unit_sim_threshold(cfg, cfg.f5_speed * 1.05) == 0.95


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all unit/speed tests passed")
