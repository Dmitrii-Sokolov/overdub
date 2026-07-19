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
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = WorkDir(root=tmp)
        work.sentences.write_text(json.dumps(sentences, ensure_ascii=False), encoding="utf-8")
        dp = tmp / "draft.json"
        dp.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        total, n_fail = build_translation.build(work, dp, Config())
        return json.loads(work.translation.read_text(encoding="utf-8")), total, n_fail


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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all build_translation tests passed")
