"""
Chatterbox Multilingual — day-1 Russian A/B ear test (cross-lingual voice clone).

THE LOAD-BEARING GATE. The overdub value proposition is that an English speaker's
voice can carry natural Russian. Resemble AI's own docs warn that a
language-mismatched reference inherits its accent by default, and cfg_weight=0.0
only MINIMIZES (never eliminates) that bleed (github issue #360: even a native RU
reference drifts to an English accent + broken stress after ~5 generations).
So day 1 is an A/B listening test, not a smoke check.

WHAT IT DOES
  Synthesizes the same ~2 min of Russian across a matrix of:
    reference clip : English (required) and, if reference_ru.wav exists, Russian
    cfg_weight     : 0.0 (min accent bleed) and 0.5 (default)
  Writes one wav per config (out_<ref>_cfg<val>.wav) and prints load time,
  generation time, audio duration and RTF per config. Then: LISTEN and compare.

DECISION RULE
  If EN-ref Russian is not natural/intelligible enough to pass a whisper-small
  round-trip at acceptable similarity, Chatterbox EN-ref cloning is NOT viable:
  fall back to a fixed RU reference (loses same-voice dubbing) or another engine
  (Silero / XTTS) behind the TTS adapter. See .claude/DECISIONS.md.

INSTALL  (isolated venv — chatterbox hard-pins torch==2.6.0 / transformers==5.2.0)
  py -3.12 -m venv .venv-tts
  .venv-tts\\Scripts\\Activate.ps1
  pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
  pip install chatterbox-tts        # git must be on PATH (resemble-perth builds from a git URL)
  # First run downloads model weights from HuggingFace (needs network; cached under HF_HOME).

REFERENCE CLIPS  (10s+ mono, clean speech, no music)
  Make one from any source with ffmpeg, e.g.:
    ffmpeg -i source.mkv -ss 00:01:00 -t 12 -vn -ac 1 -ar 24000 reference_en.wav

RUN
  python scripts/day1_smoke_test.py                                 # EN ref only, default paths
  python scripts/day1_smoke_test.py reference_en.wav reference_ru.wav
"""

import os
import re
import sys
import time

import torch
import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

CFG_WEIGHTS = (0.0, 0.5)   # 0.0 minimizes reference-accent bleed; 0.5 is the default

# ~2 minutes of Russian at a normal speaking rate. Chatterbox degrades / hallucinates on long
# inputs (~a few hundred chars per call), and overdub synthesizes per-sentence anyway — so we
# split into sentences and generate each independently, exactly like the real pipeline will.
RU_TEXT = """
Это тестовый прогон синтеза русской речи для проекта локального дубляжа.
Мы проверяем, насколько естественно звучит голос, склонированный с англоязычной записи.
Модель получает короткий образец речи диктора и должна воспроизвести его тембр по-русски.
Главный вопрос простой: слышен ли в результате иностранный акцент.
По документации акцент исходного языка может частично проникать в готовую озвучку.
Параметр cfg weight, выставленный в ноль, лишь уменьшает это влияние, но не убирает его полностью.
Поэтому день первый посвящён именно слуховой проверке качества.
Если русская речь звучит чисто и разборчиво, мы продолжаем строить конвейер.
Если акцент слишком заметен, придётся использовать русский образец или другой движок синтеза.
Пайплайн в любом случае проверяет каждый сегмент обратным распознаванием речи.
Это защитная сетка на случай, когда синтез уходит в сторону или начинает выдумывать слова.
Сейчас мы измеряем время загрузки модели и скорость генерации звука.
Показатель реального времени говорит, успеваем ли мы синтезировать быстрее, чем идёт запись.
Для ночного пакетного режима на ноутбуке это критически важная величина.
Числа, единицы измерения и латинские сокращения мы заранее разворачиваем в русские слова.
Нейронный синтез плохо справляется с сырыми цифрами и иностранными буквами.
На этом вводный текст для проверки заканчивается, переходим к анализу результата.
"""


def split_sentences(text):
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def synth(model, sentences, ref, cfg):
    chunks = []
    t0 = time.perf_counter()
    for s in sentences:
        # VERIFIED signature: generate(text, language_id, audio_prompt_path=..., exaggeration,
        #   cfg_weight, temperature, ...). Signature verified live via inspect.signature.
        wav = model.generate(
            s,
            language_id="ru",
            audio_prompt_path=ref,
            exaggeration=0.5,
            cfg_weight=cfg,
            temperature=0.8,
        )
        chunks.append(wav)
    gen_s = time.perf_counter() - t0
    return torch.cat(chunks, dim=-1), gen_s   # generate() returns (1, N); cat on sample axis


def main():
    en_ref = sys.argv[1] if len(sys.argv) > 1 else "reference_en.wav"
    ru_ref = sys.argv[2] if len(sys.argv) > 2 else "reference_ru.wav"
    refs = [("en", en_ref)]
    if os.path.exists(ru_ref):
        refs.append(("ru", ru_ref))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device = {device}")
    if device == "cpu":
        print("WARNING: CUDA unavailable — this will be unusably slow. Check the torch cu124 install.")
    for tag, p in refs:
        if not os.path.exists(p):
            print(f"ERROR: {tag} reference clip not found: {p}")
            sys.exit(1)

    t0 = time.perf_counter()
    # chatterbox-tts 0.1.7 from_pretrained takes only (device) — no t3_model arg (verified live).
    model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    load_s = time.perf_counter() - t0
    sr = model.sr
    print(f"model load: {load_s:.1f}s  sr={sr}")

    sentences = split_sentences(RU_TEXT)
    print(f"{len(sentences)} sentences × {len(refs)} ref(s) × {len(CFG_WEIGHTS)} cfg_weight(s)\n")

    print(f"{'config':<26}{'gen_s':>8}{'audio_s':>9}{'RTF':>8}")
    print("-" * 51)
    for tag, ref in refs:
        for cfg in CFG_WEIGHTS:
            full, gen_s = synth(model, sentences, ref, cfg)
            audio_s = full.shape[-1] / sr
            rtf = gen_s / audio_s if audio_s else float("nan")
            out = f"out_{tag}_cfg{cfg:.1f}.wav"
            ta.save(out, full, sr)
            print(f"{out:<26}{gen_s:>8.1f}{audio_s:>9.1f}{rtf:>8.3f}")

    print("\n*** NOW LISTEN: compare EN-ref vs RU-ref for residual English accent. ***")
    print("    EN-ref RU must be natural enough to survive a whisper-small round-trip,")
    print("    or Chatterbox EN-ref cloning is not viable (see .claude/DECISIONS.md).")


if __name__ == "__main__":
    main()
