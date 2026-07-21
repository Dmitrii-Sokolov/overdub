"""Unit tests for translate._heal_torn_tail — the torn-jsonl newline guard on resume.

Run: .venv-asr/Scripts/python.exe tests/test_translate_partial.py   (or via pytest)
Filesystem only — no GPU, no Ollama, no media. Guards the APPEND side of the
translation.jsonl resume trail: the reader already skips a torn last line from a
crash mid-write, but without the guard the first record appended on resume would
concatenate onto the fragment — one merged garbage line that swallows both records.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.stages.translate import _heal_torn_tail  # noqa: E402

# Torn tail ends MID-UTF-8-SEQUENCE (\xd0 is the first byte of a Cyrillic pair) — the
# realistic crash shape, and the reason the guard must work in binary mode.
TORN = b'{"id": 1, "src_en": "one", "text_ru": "\xd0\xbe\xd0'
CLEAN = b'{"id": 0}\n{"id": 1}\n'


def test_torn_file_healed_once() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "translation.jsonl"
        p.write_bytes(TORN)
        assert _heal_torn_tail(p) is True
        assert p.read_bytes() == TORN + b"\n"   # exactly one \n, fragment bytes untouched


def test_second_call_is_a_noop() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "translation.jsonl"
        p.write_bytes(TORN)
        assert _heal_torn_tail(p) is True
        healed = p.read_bytes()
        assert _heal_torn_tail(p) is False      # idempotent — newlines must not stack
        assert p.read_bytes() == healed


def test_empty_file_untouched() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "translation.jsonl"
        p.write_bytes(b"")
        assert _heal_torn_tail(p) is False
        assert p.read_bytes() == b""


def test_missing_file_not_created() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "translation.jsonl"
        assert _heal_torn_tail(p) is False
        assert not p.exists()                   # exists() is the resume signal — never fake it


def test_clean_file_untouched() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "translation.jsonl"
        p.write_bytes(CLEAN)
        assert _heal_torn_tail(p) is False
        assert p.read_bytes() == CLEAN


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all translate partial-trail tests passed")
