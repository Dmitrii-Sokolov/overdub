"""Narrator audition: render 3 test phrases through ESpeech for each candidate reference.

Candidates: models/refs/<name>.wav + .txt (LibriVox public-domain cuts + the demo ref).
Output: bakeoff/narrators/<name>/<key>.wav
Run: .venv-f5tts/Scripts/python.exe scripts/bakeoff3_narrators.py
Progress prints are intentional (CLI test script).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from ruaccent import RUAccent
from f5_tts.infer.utils_infer import infer_process, load_model, load_vocoder, preprocess_ref_audio_text
from f5_tts.model import DiT

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REFS = ["lv_tovarisch", "lv_chulsky", "lv_xenium5", "lv_chekhov01", "lv_chekhov04", "ref_espeech_demo"]
import sys  # noqa: E402
REFS = sys.argv[1:] or DEFAULT_REFS
KEYS = ["ref_day1", "id038_medium", "id171_numbers"]
MODEL_CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
SEED = 42
_CYR = re.compile("[а-яА-ЯёЁ]")

accent = RUAccent()
accent.load(omograph_model_size="turbo3.1", use_dictionary=True)


class _SessionShim:
    """ruaccent 1.5.8.3 omits token_type_ids the current accent ONNX declares — feed zeros."""

    def __init__(self, session):
        self._s = session
        self._need_tt = any(i.name == "token_type_ids" for i in session.get_inputs())

    def run(self, out, feed):
        if self._need_tt and "token_type_ids" not in feed:
            feed = {**feed, "token_type_ids": np.zeros_like(feed["input_ids"])}
        return self._s.run(out, feed)

    def __getattr__(self, name):
        return getattr(self._s, name)


accent.accent_model.session = _SessionShim(accent.accent_model.session)
if hasattr(accent, "omograph_model") and hasattr(accent.omograph_model, "session"):
    accent.omograph_model.session = _SessionShim(accent.omograph_model.session)

device = "cuda" if torch.cuda.is_available() else "cpu"
model = load_model(DiT, MODEL_CFG, str(ROOT / "models/espeech-rlv2/espeech_tts_rlv2.pt"),
                   vocab_file=str(ROOT / "models/espeech-rlv2/vocab.txt"))
vocoder = load_vocoder()
model.to(device)
vocoder.to(device)

items = {i["key"]: i["text"] for i in json.loads((ROOT / "bakeoff/texts.json").read_text(encoding="utf-8"))["items"]}

for ref in REFS:
    ref_wav = ROOT / "models/refs" / f"{ref}.wav"
    ref_txt = (ROOT / "models/refs" / f"{ref}.txt").read_text(encoding="utf-8").strip()
    ra, rt = preprocess_ref_audio_text(str(ref_wav), accent.process_all(ref_txt) if _CYR.search(ref_txt) else ref_txt)
    out_dir = ROOT / "bakeoff/narrators" / ref
    out_dir.mkdir(parents=True, exist_ok=True)
    for key in KEYS:
        t0 = time.perf_counter()
        torch.manual_seed(SEED)
        wave, sr, _ = infer_process(ra, rt, accent.process_all(items[key]), model, vocoder,
                                    nfe_step=48, cross_fade_duration=0.15, speed=1.0)
        sf.write(str(out_dir / f"{key}.wav"), wave, sr, format="WAV", subtype="PCM_16")
        print(f"{ref}/{key}  {time.perf_counter() - t0:.1f}s")

print("done")
