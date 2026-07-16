"""Cut clean 8-11 s reference windows from LibriVox fragments (public domain).

For each models/refs/lv/<name>_raw.wav: whisper-large segments -> first run of
consecutive segments (inter-gap < 0.6 s) totalling 8-11 s -> cut wav + save transcript.
Run: .venv-asr/Scripts/python.exe scripts/lv_pick_refs.py <name> [<name> ...]
Progress prints are intentional (CLI utility).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overdub.asr import load_whisper  # noqa: E402

args = sys.argv[1:]
PREFIX = "lv"                                   # source subdir + output name prefix
GAP = 0.6                                       # max inter-segment pause inside a window, s
while args and args[0] in ("--prefix", "--gap"):
    if args[0] == "--prefix":
        PREFIX = args[1]
    else:
        GAP = float(args[1])
    args = args[2:]
SRC = Path(__file__).resolve().parents[1] / "models/refs" / PREFIX
OUT = Path(__file__).resolve().parents[1] / "models/refs"

model = load_whisper("large-v3")
for name in args:
    raw = SRC / f"{name}_raw.wav"
    segs = list(model.transcribe(str(raw), language="ru", word_timestamps=False)[0])
    window: list = []
    best: list = []                     # longest ≤11 s window seen — fallback if none reaches 8 s
    for s in segs:
        if window and s.start - window[-1].end > GAP:
            window = []
        window.append(s)
        while window and window[-1].end - window[0].start > 11.0:
            window.pop(0)
        if not window:
            continue
        dur = window[-1].end - window[0].start
        if not best or dur > best[-1].end - best[0].start:
            best = list(window)
        if 8.0 <= dur <= 11.0:
            break
    window = best
    if not window:
        print(f"{name}: NO clean window found")
        continue
    t0, t1 = window[0].start, window[-1].end
    text = " ".join(s.text.strip() for s in window)
    wav_out = OUT / f"{PREFIX}_{name}.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{t0:.2f}", "-to", f"{t1:.2f}",
         "-i", str(raw), str(wav_out)],
        check=True,
    )
    (OUT / f"{PREFIX}_{name}.txt").write_text(text + "\n", encoding="utf-8")
    print(f"{name}: {t1 - t0:.1f}s  [{t0:.1f}-{t1:.1f}]  {text[:90]}")
