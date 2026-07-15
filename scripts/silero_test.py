"""Silero v4 Russian TTS — engine comparison test (replaces Chatterbox).

Native Russian, fixed speakers (no cloning), tiny + fast, built-in stress/yo.
Loaded from torch.hub (downloads ~60 MB model once, cached in ~/.cache/torch/hub).
Runs on CPU by design — keeps VRAM free; Silero is real-time on CPU.

Run:  .venv-tts\\Scripts\\python.exe scripts\\silero_test.py
"""

import time

import torch
import torchaudio as ta

TEXT = (
    "Это тест синтеза русской речи движком Силеро. "
    "Голос нативно русский, без клонирования и без иностранного акцента. "
    "Мы сравниваем разборчивость и естественность с предыдущим движком. "
    "Числа и сокращения мы заранее разворачиваем в слова. "
    "Ударения расставляются автоматически встроенным акцентуатором. "
    "На этом короткий проверочный отрывок заканчивается."
)

SPEAKERS = ["kseniya", "xenia"]   # kseniya (f), xenia (f) — the two remaining v4_ru voices
SR = 48000

device = torch.device("cpu")   # tiny model; CPU keeps the GPU free
print("loading silero v4_ru from torch.hub ...")
model, _ = torch.hub.load(
    repo_or_dir="snakers4/silero-models",
    model="silero_tts", language="ru", speaker="v4_ru",
)
model.to(device)
print("loaded")

for sp in SPEAKERS:
    t0 = time.perf_counter()
    audio = model.apply_tts(text=TEXT, speaker=sp, sample_rate=SR, put_accent=True, put_yo=True)
    out = f"out_silero_{sp}.wav"
    ta.save(out, audio.unsqueeze(0), SR)
    print(f"{out}  gen {time.perf_counter()-t0:.1f}s  audio {len(audio)/SR:.1f}s")

print("done — listen to out_silero_*.wav")
