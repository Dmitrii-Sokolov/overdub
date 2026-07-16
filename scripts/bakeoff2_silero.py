"""Bake-off #2 baseline: render bakeoff/texts.json through the current engine (Silero v4_ru).

Run:  .venv-asr/Scripts/python.exe scripts/bakeoff2_silero.py
Outputs: bakeoff/silero_<voice>/<key>.wav — A/B-listen against candidate engines.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.tts.silero import SileroEngine  # noqa: E402

ROOT = Path(__file__).resolve().parents[1] / "bakeoff"
VOICES = ["eugene", "xenia"]  # primary + backup, both as baseline

items = json.loads((ROOT / "texts.json").read_text(encoding="utf-8"))["items"]

for voice in VOICES:
    out_dir = ROOT / f"silero_{voice}"
    out_dir.mkdir(parents=True, exist_ok=True)
    engine = SileroEngine(voice=voice)
    for it in items:
        t0 = time.perf_counter()
        out = out_dir / f"{it['key']}.wav"
        engine.synthesize(it["text"], out)
        print(f"{out.relative_to(ROOT.parent)}  {time.perf_counter() - t0:.1f}s")

print("done")
