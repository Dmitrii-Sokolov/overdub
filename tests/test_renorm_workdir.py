"""tools/renorm_workdir.py keeps what the copy needs to be dubbed like its source.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_renorm_workdir.py   (or via pytest)
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location("renorm_workdir", ROOT / "tools" / "renorm_workdir.py")
renorm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(renorm)


def test_speakers_survive_the_copy() -> None:
    with tempfile.TemporaryDirectory() as d:
        src, dst = Path(d) / "src", Path(d) / "dst"
        src.mkdir()
        diar = {"speakers": 2, "speakers_info": [], "segments": [], "meta": {}}
        (src / "diar.json").write_text(json.dumps(diar), encoding="utf-8")
        (src / "translation.json").write_text(json.dumps(
            [{"id": 0, "speaker": 1, "text_ru": "Привет.", "text_tts": "привет"}]),
            encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            assert renorm.main([str(src), str(dst)]) == 0
        assert json.loads((dst / "diar.json").read_text(encoding="utf-8")) == diar
        assert json.loads((dst / "translation.json").read_text(encoding="utf-8"))[0]["speaker"] == 1


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all renorm_workdir tests passed")
