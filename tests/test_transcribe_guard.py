"""Unit tests for transcribe's collapsed-alignment guard (floor_run_ratio) — pure, no ASR.

Run: .venv-asr/Scripts/python.exe tests/test_transcribe_guard.py   (or via pytest)
Contract: only CHAINED floor-stamped words count (an isolated 20 ms grid word is ordinary
whisper output, not evidence), the ratio is per-word, and the longest run is reported as
context only. Thresholds are calibrated in config; these tests pin the detector's shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.stages.transcribe import (  # noqa: E402
    MIN_WORD_DUR, TranscribeStage, W, floor_run_ratio,
)


def chain(start: float, n: int) -> list[W]:
    """n words each exactly MIN_WORD_DUR long, butted end-to-start — what flatten's monotone
    clamp + floor produce when whisper returns no usable timing for a stretch."""
    out: list[W] = []
    t = start
    for i in range(n):
        out.append(W(f"w{i}", t, t + MIN_WORD_DUR, seg_end=False))
        t += MIN_WORD_DUR
    return out


def normal(start: float, n: int, dur: float = 0.30) -> list[W]:
    out: list[W] = []
    t = start
    for i in range(n):
        out.append(W(f"n{i}", t, t + dur, seg_end=False))
        t += dur
    return out


def test_clean_transcript_scores_zero() -> None:
    ratio, longest = floor_run_ratio(normal(0.0, 50))
    assert ratio == 0.0 and longest == 0


def test_empty_is_zero_not_a_crash() -> None:
    assert floor_run_ratio([]) == (0.0, 0)


def test_isolated_floor_word_is_not_evidence() -> None:
    """A single short word on the 20 ms grid is ordinary whisper output. It is only counted
    when CHAINED to the previous word's end, so a lone one must not move the ratio."""
    flat = normal(0.0, 10)
    tail = flat[-1].end
    flat.append(W("short", tail + 0.5, tail + 0.5 + MIN_WORD_DUR, seg_end=False))  # gap => unchained
    ratio, longest = floor_run_ratio(flat)
    assert ratio == 0.0 and longest == 0


def test_collapsed_chain_is_detected() -> None:
    flat = normal(0.0, 20) + chain(6.0, 20)                # normal() ends exactly at 6.0
    ratio, longest = floor_run_ratio(flat)
    assert longest == 20, longest
    assert ratio == 0.5, ratio                             # 20 chained of 40 words


def test_chain_head_counts_only_when_it_butts_the_previous_word() -> None:
    """The head of a chain is evidence only if it continues the previous word — that is what
    distinguishes flatten's monotone clamp from a genuine pause before a short word. Same
    9-word chain, started with and without a gap: 9 vs 8."""
    butted = normal(0.0, 10) + chain(3.0, 9)               # normal() ends exactly at 3.0
    gapped = normal(0.0, 10) + chain(4.0, 9)               # 1 s pause before the chain
    assert floor_run_ratio(butted)[1] == 9
    assert floor_run_ratio(gapped)[1] == 8


def test_longest_run_tracks_the_worst_chain_not_the_total() -> None:
    flat = normal(0.0, 10) + chain(3.0, 4) + normal(5.0, 10) + chain(8.0, 9)
    _ratio, longest = floor_run_ratio(flat)
    assert longest == 9, longest


def test_real_batch_shape_separates() -> None:
    """Shape guard for the calibrated threshold: a healthy transcript (sparse, short chains)
    must land far below the 6% default, a collapsed one far above."""
    healthy = normal(0.0, 200) + chain(60.0, 3)
    collapsed = normal(0.0, 100) + chain(30.0, 44)
    assert floor_run_ratio(healthy)[0] < 0.06
    assert floor_run_ratio(collapsed)[0] > 0.06


# --- _guard branching (stub ASR — no model, no workdir) -----------------------
class _Cfg:
    def __init__(self, limit: float = 0.06, condition: bool = True) -> None:
        self.transcribe_floor_run_max = limit
        self.whisper_condition_on_previous = condition


class _Ctx:
    def __init__(self, cfg: _Cfg) -> None:
        self.cfg = cfg


def _guard_with(first: list[W], retry: list[W], **cfg_kw):
    """Run TranscribeStage._guard against a stub asr(); returns (chosen, n_retries)."""
    calls = []

    def asr(condition_on_previous: bool) -> list[W]:
        calls.append(condition_on_previous)
        return retry

    chosen = TranscribeStage()._guard(_Ctx(_Cfg(**cfg_kw)), asr, first)
    return chosen, len(calls)


def test_guard_silent_on_a_healthy_transcript() -> None:
    healthy = normal(0.0, 200) + chain(60.0, 3)
    chosen, retries = _guard_with(healthy, normal(0.0, 10))
    assert chosen is healthy and retries == 0            # never re-runs ASR when under limit


def test_guard_accepts_a_retry_that_halves_the_ratio() -> None:
    collapsed = normal(0.0, 100) + chain(30.0, 44)
    clean = normal(0.0, 140)
    chosen, retries = _guard_with(collapsed, clean)
    assert chosen is clean and retries == 1


def test_guard_rejects_a_retry_that_does_not_halve() -> None:
    """The flag is on for punctuation; a marginal win does not justify dropping it, so the
    original survives and the operator is told the timings are still suspect."""
    collapsed = normal(0.0, 100) + chain(30.0, 44)
    barely_better = normal(0.0, 100) + chain(30.0, 40)
    chosen, retries = _guard_with(collapsed, barely_better)
    assert chosen is collapsed and retries == 1


def test_guard_disabled_by_zero_limit() -> None:
    collapsed = normal(0.0, 100) + chain(30.0, 44)
    chosen, retries = _guard_with(collapsed, normal(0.0, 10), limit=0.0)
    assert chosen is collapsed and retries == 0


def test_guard_skipped_when_context_feedback_already_off() -> None:
    """Nothing left to trade away — the retry would be the same run."""
    collapsed = normal(0.0, 100) + chain(30.0, 44)
    chosen, retries = _guard_with(collapsed, normal(0.0, 10), condition=False)
    assert chosen is collapsed and retries == 0


def main() -> None:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"ok  {t.__name__}")
    print(f"\n{len(tests)} passed")


if __name__ == "__main__":
    main()
