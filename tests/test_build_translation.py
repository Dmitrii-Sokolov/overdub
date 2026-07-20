"""Unit tests for scripts/build_translation.py — the route-B translate-contract assembler.

Run: .venv-asr/Scripts/python.exe tests/test_build_translation.py   (or via pytest)
Filesystem only. Guards the contract the Sonnet sub-agent's {id,text_ru} draft is held to:
src_en/timings copied from sentences.json, text_tts derived by normalize_for_tts, _is_bad
gate, id-contiguity — so a malformed draft fails LOUD (exit) instead of reaching synthesize.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import build_translation  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402


def _build(sentences: list[dict], draft: list[dict]):
    """Write sentences + draft into a tmp workdir, run build(), return (records, total, n_fail)."""
    out, total, n_fail, _, _ = _build_full(sentences, draft)
    return out, total, n_fail


def _build_full(sentences: list[dict], draft: list[dict]):
    """As _build, but also returns the source-anomaly counts + rows (PLAN item 1):
    (records, total, n_fail, n_anom, n_scanned, anom_rows) — flattened to 5 + rows."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = WorkDir(root=tmp)
        work.sentences.write_text(json.dumps(sentences, ensure_ascii=False), encoding="utf-8")
        dp = tmp / "draft.json"
        dp.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        total, n_fail, n_anom, n_scanned, rows = build_translation.build(work, dp, Config())
        recs = json.loads(work.translation.read_text(encoding="utf-8"))
        return recs, total, n_fail, (n_anom, n_scanned), rows


def _sent(i, text, start=None, end=None):
    return {"id": i, "text": text, "start": i * 2.0 if start is None else start,
            "end": i * 2.0 + 1.5 if end is None else end}


def _exits(sentences, draft) -> bool:
    try:
        _build(sentences, draft)
        return False
    except SystemExit:
        return True


def test_happy_path_contract() -> None:
    out, total, n_fail = _build(
        [_sent(0, "Hello there."), _sent(1, "How are you?")],
        [{"id": 0, "text_ru": "Привет."}, {"id": 1, "text_ru": "Как дела?"}],
    )
    assert (total, n_fail) == (2, 0)
    r = out[0]
    assert set(r) >= {"id", "start", "end", "src_en", "text_ru", "text_tts", "status", "attempts"}
    assert r["status"] == "ok" and r["attempts"] == 1
    assert [o["id"] for o in out] == [0, 1]


def test_src_en_and_timings_copied_from_sentences() -> None:
    # the sub-agent supplies ONLY text_ru; src_en/start/end must come from sentences.json
    out, _, _ = _build(
        [_sent(0, "The quick brown fox.", start=3.25, end=5.5)],
        [{"id": 0, "text_ru": "Быстрая лиса."}],
    )
    assert out[0]["src_en"] == "The quick brown fox."
    assert out[0]["start"] == 3.25 and out[0]["end"] == 5.5


def test_text_tts_normalized_not_llm_spelled() -> None:
    # text_tts must be the Python normalizer's output, digits/Latin expanded — never text_ru verbatim
    out, _, _ = _build(
        [_sent(0, "The RTX 4080 is fast.")],
        [{"id": 0, "text_ru": "RTX 4080 быстрая."}],
    )
    tts = out[0]["text_tts"]
    assert tts != out[0]["text_ru"]
    assert "4080" not in tts and "RTX" not in tts   # expanded to Russian words


def test_english_echo_flagged_not_hidden() -> None:
    out, total, n_fail = _build(
        [_sent(0, "Привет."), _sent(1, "This was left untranslated.")],
        [{"id": 0, "text_ru": "Привет."}, {"id": 1, "text_ru": "this was left untranslated"}],
    )
    assert (total, n_fail) == (2, 1)
    assert out[0]["status"] == "ok"
    assert out[1]["status"] == "failed" and out[1]["flag"] == "english_echo"


def test_missing_id_exits() -> None:
    # draft misses id 1 → LOUD exit, never a partial translation.json
    assert _exits(
        [_sent(0, "a"), _sent(1, "b")],
        [{"id": 0, "text_ru": "а"}],
    )


def test_extra_id_exits() -> None:
    # draft has an id not present in sentences.json → LOUD exit
    assert _exits(
        [_sent(0, "a")],
        [{"id": 0, "text_ru": "а"}, {"id": 5, "text_ru": "лишний"}],
    )


def test_empty_text_ru_flagged() -> None:
    out, _, n_fail = _build(
        [_sent(0, "Something.")],
        [{"id": 0, "text_ru": ""}],
    )
    assert n_fail == 1
    assert out[0]["status"] == "failed" and out[0]["flag"] == "empty"


def test_non_string_text_ru_exits() -> None:
    # a JSON null must be rejected LOUD — str() coercion would voice it literally
    # ("None" -> "нон") and it passes every _is_bad gate
    assert _exits(
        [_sent(0, "a")],
        [{"id": 0, "text_ru": None}],
    )


def test_pronounce_audit_written() -> None:
    # parity with TranslateStage.run: route B must keep the audit-only triage artifact
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = WorkDir(root=tmp)
        work.sentences.write_text(
            json.dumps([_sent(0, "It runs at 60 fps.")]), encoding="utf-8")
        dp = tmp / "draft.json"
        dp.write_text(json.dumps([{"id": 0, "text_ru": "Она выдаёт 60 fps."}],
                                 ensure_ascii=False), encoding="utf-8")
        build_translation.build(work, dp, Config())
        audit = json.loads(work.pronounce_audit.read_text(encoding="utf-8"))
        assert audit["video_id"] == work.root.name
        assert "fps" in audit["tokens"]


# --- source anomalies (PLAN item 1) ------------------------------------------
# The whole point of `src`: a good translator LAUNDERS source damage, so the draft must carry a
# positive "ok" claim per record and every src defect must degrade to a [warn] — never an exit.
# A hard failure here would leave translation.json unwritten and hand the video to the silent
# local-Gemma path at resume, i.e. a report gating a dub.
def test_src_ok_copied_without_note() -> None:
    out, _, _, (n_anom, n_scanned), rows = _build_full(
        [_sent(0, "Hello there."), _sent(1, "How are you?")],
        [{"id": 0, "text_ru": "Привет.", "src": "ok"},
         {"id": 1, "text_ru": "Как дела?", "src": "ok"}],
    )
    assert (n_anom, n_scanned) == (0, 2) and rows == []
    assert all(r["src"] == "ok" for r in out)
    assert all("src_note" not in r for r in out)      # note is meaningless on an ok record


def test_src_anomaly_and_note_preserved() -> None:
    out, _, _, (n_anom, n_scanned), rows = _build_full(
        [_sent(0, "Description goes beyond distinction.")],
        [{"id": 0, "text_ru": "Описание выходит за рамки различия.", "src": "truncated",
          "src_note": "ends mid-thought; id 1 reads as its continuation"}],
    )
    assert (n_anom, n_scanned) == (1, 1)
    assert out[0]["src"] == "truncated"
    assert out[0]["src_note"] == "ends mid-thought; id 1 reads as its continuation"
    # the seam row carries the EN source so the operator can act at step 2, not after synthesis
    assert rows[0][0] == 0 and rows[0][1] == "truncated"
    assert rows[0][3] == "Description goes beyond distinction."


def test_missing_src_is_unscanned_never_fatal() -> None:
    # An UNSCANNED record: no src key at all. Must not raise, must not exit, and must leave the
    # key off translation.json so `scanned` stays derivable — "not scanned" != "clean".
    out, total, _, (n_anom, n_scanned), _ = _build_full(
        [_sent(0, "a"), _sent(1, "b")],
        [{"id": 0, "text_ru": "а", "src": "ok"}, {"id": 1, "text_ru": "б"}],
    )
    assert (total, n_scanned, n_anom) == (2, 1, 0)     # short by exactly one
    assert out[0]["src"] == "ok" and "src" not in out[1]


def test_unknown_src_clamped_raw_value_preserved() -> None:
    # Clamp, never drop: an unknown kind must not vanish AND must not fail the build.
    out, _, _, (n_anom, _), _ = _build_full(
        [_sent(0, "a")],
        [{"id": 0, "text_ru": "а", "src": "weird", "src_note": "смотри сам"}],
    )
    assert n_anom == 1
    assert out[0]["src"] == "unknown"
    assert out[0]["src_note"].startswith("[raw src='weird']")


def test_anomaly_without_note_still_written() -> None:
    out, _, _, (n_anom, _), _ = _build_full(
        [_sent(0, "a")],
        [{"id": 0, "text_ru": "а", "src": "garbled"}],
    )
    assert n_anom == 1
    assert out[0]["src"] == "garbled" and out[0]["src_note"] == ""


def test_non_string_src_note_dropped() -> None:
    out, _, _, (n_anom, n_scanned), _ = _build_full(
        [_sent(0, "a")],
        [{"id": 0, "text_ru": "а", "src": "garbled", "src_note": 42}],
    )
    assert (n_anom, n_scanned) == (1, 1)
    assert out[0]["src"] == "garbled" and out[0]["src_note"] == ""


def test_long_src_note_truncated_visibly() -> None:
    out, _, _, _, _ = _build_full(
        [_sent(0, "a")],
        [{"id": 0, "text_ru": "а", "src": "garbled", "src_note": "x" * 300}],
    )
    assert out[0]["src_note"].endswith(" …[truncated]")   # visible, never a silent drop
    assert len(out[0]["src_note"]) < 300


def test_id_problem_still_exits_despite_src_leniency() -> None:
    # Regression guard: loosening the src handling must NOT loosen the id/text_ru exits. A wrong
    # id set produces a wrong DUB; a mislabeled report row only produces a wrong report.
    assert _exits([_sent(0, "a"), _sent(1, "b")],
                  [{"id": 0, "text_ru": "а", "src": "ok"}])
    assert _exits([_sent(0, "a")], [{"id": 0, "text_ru": None, "src": "ok"}])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all build_translation tests passed")
