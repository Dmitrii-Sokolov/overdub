"""Bake-off #2: render bakeoff/texts.json through an F5-TTS Russian checkpoint.

Run (dedicated venv):
  .venv-f5tts/Scripts/python.exe scripts/bakeoff2_f5.py espeech
  .venv-f5tts/Scripts/python.exe scripts/bakeoff2_f5.py misha

Invocation pattern follows the ESpeech author's HF Space app.py:
RUAccent turbo3.1 pre-pass, nfe_step=48, fixed seed, ref clip <= 12 s.
Progress prints are intentional (CLI test script, same as bakeoff2_silero.py).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import soundfile as sf
import torch
from ruaccent import RUAccent
from f5_tts.infer.utils_infer import infer_process, load_model, load_vocoder, preprocess_ref_audio_text
from f5_tts.model import DiT

ROOT = Path(__file__).resolve().parents[1]
BAKEOFF = ROOT / "bakeoff"
MODELS = ROOT / "models"

ENGINES = {
    "espeech": {
        "ckpt": MODELS / "espeech-rlv2" / "espeech_tts_rlv2.pt",
        "vocab": MODELS / "espeech-rlv2" / "vocab.txt",
        "out": "f5_espeech_rlv2",
    },
    "misha": {
        "ckpt": MODELS / "misha-f5-ru" / "model_last_inference.safetensors",
        "vocab": MODELS / "misha-f5-ru" / "vocab.txt",
        "out": "f5_misha_v2",
    },
}

MODEL_CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
REF_AUDIO = MODELS / "espeech-rlv2" / "example.mp3"
REF_TEXT = (MODELS / "espeech-rlv2" / "example_ref.txt").read_text(encoding="utf-8").strip()
SEED = 42
NFE_STEP = 48

which = sys.argv[1] if len(sys.argv) > 1 else "espeech"
eng = ENGINES[which]

print("loading RUAccent (turbo3.1) ...")
accent = RUAccent()
accent.load(omograph_model_size="turbo3.1", use_dictionary=True)


class _SessionShim:
    """ruaccent 1.5.8.3 feeds only input_ids+attention_mask, but the current
    accent ONNX export also declares token_type_ids — supply zeros (single-segment
    BERT semantics). Contained here; site-packages stays untouched."""

    def __init__(self, session):
        self._s = session
        self._need_tt = any(i.name == "token_type_ids" for i in session.get_inputs())

    def run(self, out, feed):
        if self._need_tt and "token_type_ids" not in feed:
            import numpy as np

            feed = {**feed, "token_type_ids": np.zeros_like(feed["input_ids"])}
        return self._s.run(out, feed)

    def __getattr__(self, name):
        return getattr(self._s, name)


accent.accent_model.session = _SessionShim(accent.accent_model.session)
if hasattr(accent, "omograph_model") and hasattr(accent.omograph_model, "session"):
    accent.omograph_model.session = _SessionShim(accent.omograph_model.session)

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"loading {which} on {device} ...")
model = load_model(DiT, MODEL_CFG, str(eng["ckpt"]), vocab_file=str(eng["vocab"]))
vocoder = load_vocoder()
model.to(device)
vocoder.to(device)

ref_audio_proc, ref_text_final = preprocess_ref_audio_text(str(REF_AUDIO), accent.process_all(REF_TEXT))

items = json.loads((BAKEOFF / "texts.json").read_text(encoding="utf-8"))["items"]
out_dir = BAKEOFF / eng["out"]
out_dir.mkdir(parents=True, exist_ok=True)

for it in items:
    t0 = time.perf_counter()
    torch.manual_seed(SEED)
    text = accent.process_all(it["text"])
    wave, sr, _ = infer_process(
        ref_audio_proc, ref_text_final, text, model, vocoder,
        nfe_step=NFE_STEP, cross_fade_duration=0.15, speed=1.0,
    )
    out = out_dir / f"{it['key']}.wav"
    sf.write(str(out), wave, sr, format="WAV", subtype="PCM_16")
    print(f"{out.relative_to(ROOT)}  {time.perf_counter() - t0:.1f}s  audio {len(wave) / sr:.1f}s")

print("done")
