"""Quick experiment: Chatterbox Russian WITHOUT a reference clip (built-in voice).

Isolates the cause of bad quality: audio_prompt_path is optional (defaults to None),
so with no reference the engine uses its own built-in voice — no cross-lingual accent
bleed, no dependence on the (blindly-extracted) reference clip. If Russian is clean
here, the problem was the reference / cross-lingual cloning; if it's still bad, the
engine's Russian itself is weak and we switch engines.

Run:  .venv-tts\\Scripts\\python.exe scripts\\no_ref_test.py
"""

import time

import torch
import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

TEXT = [
    "Это тест синтеза русской речи без образца голоса.",
    "Движок использует собственный встроенный голос по умолчанию.",
    "Мы проверяем, насколько чисто звучит русский сам по себе.",
    "Если без образца речь разборчива и без акцента, значит проблема была в референсе.",
    "Числа и сокращения мы заранее разворачиваем в слова.",
    "На этом короткий проверочный отрывок заканчивается.",
]

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"device = {device}")
model = ChatterboxMultilingualTTS.from_pretrained(device=device)
sr = model.sr
print(f"loaded, sr={sr}")

for cfg in (0.3, 0.5):
    chunks = []
    t0 = time.perf_counter()
    for s in TEXT:
        wav = model.generate(
            s, language_id="ru", audio_prompt_path=None,   # no reference -> built-in voice
            exaggeration=0.5, cfg_weight=cfg, temperature=0.8,
        )
        chunks.append(wav)
    full = torch.cat(chunks, dim=-1)
    out = f"out_noref_cfg{cfg:.1f}.wav"
    ta.save(out, full, sr)
    print(f"{out}  gen {time.perf_counter()-t0:.1f}s  audio {full.shape[-1]/sr:.1f}s")

print("done — listen to out_noref_cfg*.wav")
