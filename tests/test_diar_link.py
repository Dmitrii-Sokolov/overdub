"""Unit tests for windowed diarization and identity linking in the worker — 2026-10-27.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_diar_link.py   (or via pytest)
No GPU, no NeMo: the pure halves of scripts/parakeet_worker.py, with synthetic embeddings.

The failure classes this pins:

  * ONE VOICE, SEVERAL LABELS. Over hours the diarizer opens a new label for a voice it already
    has (48 of 89 calibration videos over-counted); the same voice in two windows is two labels by
    construction. Labels with one voice must join — across windows and within one.
  * TWO VOICES JOINED. Linking must stop at the threshold, or a panel collapses into one voice.
  * A SAMPLE FROM ONE END. Drift is over time, so a label's embedding chunks must span its whole
    speech, not its first minutes.
  * A SLIVER WINDOW. The last window must not be a few seconds the diarizer cannot work with.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))

import parakeet_worker as pw                                       # noqa: E402


def _voice(seed: int, n: int = 6, spread: float = 0.15) -> np.ndarray:
    rng = np.random.default_rng(seed)
    centre = rng.normal(size=192)
    v = centre + spread * np.linalg.norm(centre) / np.sqrt(192) * rng.normal(size=(n, 192))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def test_windows_are_equal_and_cover_the_file() -> None:
    assert pw.diar_windows(600.0) == [(0.0, 600.0)]
    w = pw.diar_windows(1201.0)                          # not 1200 s + a 1 s sliver
    assert len(w) == 2 and w[0][0] == 0.0 and w[-1][1] == 1201.0
    assert abs((w[0][1] - w[0][0]) - (w[1][1] - w[1][0])) < 1e-6
    assert all(b - a <= pw.DIAR_WINDOW_SEC for a, b in pw.diar_windows(3 * 3600.0 + 5))


def test_one_voice_under_three_labels_becomes_one_group() -> None:
    a = _voice(1)
    mapping, merges = pw.link_labels({"w0:speaker_0": a[:3], "w1:speaker_1": a[3:],
                                      "w2:speaker_0": a[1:4]})
    assert len(set(mapping.values())) == 1, (mapping, merges)


def test_two_voices_stay_two() -> None:
    mapping, merges = pw.link_labels({"w0:speaker_0": _voice(1), "w0:speaker_1": _voice(2),
                                      "w1:speaker_0": _voice(2), "w1:speaker_1": _voice(1)})
    assert len(set(mapping.values())) == 2, (mapping, merges)
    assert mapping["w0:speaker_0"] == mapping["w1:speaker_1"]
    assert mapping["w0:speaker_1"] == mapping["w1:speaker_0"]


def test_a_label_without_an_embedding_is_its_own_group() -> None:
    mapping, _ = pw.link_labels({"w0:speaker_0": _voice(1)})
    assert mapping == {"w0:speaker_0": "w0:speaker_0"}


def test_chunks_span_the_whole_speech() -> None:
    spans = [(t, t + 10.0) for t in range(0, 3600, 60)]  # 10 s every minute for an hour
    chunks = pw.link_chunks(spans)
    assert len(chunks) == pw.LINK_MAX_CHUNKS
    assert chunks[0][0] < 60 and chunks[-1][1] > 3500, chunks
    assert all(abs((b - a) - pw.LINK_CHUNK_SEC) < 1e-9 for a, b in chunks)


def test_a_short_label_offers_its_longest_run_or_nothing() -> None:
    assert pw.link_chunks([(0.0, 0.5), (5.0, 6.8)]) == [(5.0, 6.8)]
    assert pw.link_chunks([(0.0, 0.4), (5.0, 5.6)]) == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all diar-link tests passed")
