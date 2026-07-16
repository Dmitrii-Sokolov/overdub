"""Voice-cloning experiment: synthesize a whole video's translation.json with ESpeech
(F5-TTS) conditioned on an arbitrary reference clip, writing segments/ + manifest.json
in the exact synthesize-stage format so verify/assemble/mux run on it unchanged.

Run (dedicated venv):
  .venv-f5tts/Scripts/python.exe scripts/exp_clone_synth.py <ref_name> <workdir>
e.g.
  .venv-f5tts/Scripts/python.exe scripts/exp_clone_synth.py ref_en_speaker work-exp/enclone/4szRHy_CT7s

Reference clip models/refs/<ref_name>.wav + exact transcript models/refs/<ref_name>.txt.
RUAccent is applied to Cyrillic text only (an EN reference transcript passes through raw).
Progress prints are intentional (CLI experiment script).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from ruaccent import RUAccent
from f5_tts.infer.utils_infer import infer_process, load_model, load_vocoder, preprocess_ref_audio_text
from f5_tts.model import DiT

ROOT = Path(__file__).resolve().parents[1]
MODEL_CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
CKPT = ROOT / "models/espeech-rlv2/espeech_tts_rlv2.pt"
VOCAB = ROOT / "models/espeech-rlv2/vocab.txt"
SEED = 42
NFE_STEP = 48
_CYR = re.compile("[а-яА-ЯёЁ]")

ref_name, workdir = sys.argv[1], Path(sys.argv[2])
speed = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0   # >1 shrinks F5's duration canvas
ref_audio = ROOT / "models/refs" / f"{ref_name}.wav"
ref_text = (ROOT / "models/refs" / f"{ref_name}.txt").read_text(encoding="utf-8").strip()

print("loading RUAccent (turbo3.1) ...")
accent = RUAccent()
accent.load(omograph_model_size="turbo3.1", use_dictionary=True)


class _SessionShim:
    """Same shim as bakeoff2_f5.py: ruaccent 1.5.8.3 omits token_type_ids the current
    accent ONNX export declares — supply zeros (single-segment BERT semantics)."""

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


def accentize(text: str) -> str:
    return accent.process_all(text) if _CYR.search(text) else text


device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"loading ESpeech RL-V2 on {device} ...")
model = load_model(DiT, MODEL_CFG, str(CKPT), vocab_file=str(VOCAB))
vocoder = load_vocoder()
model.to(device)
vocoder.to(device)

ref_audio_proc, ref_text_final = preprocess_ref_audio_text(str(ref_audio), accentize(ref_text))

segs = json.loads((workdir / "translation.json").read_text(encoding="utf-8"))
seg_dir = workdir / "segments"
seg_dir.mkdir(parents=True, exist_ok=True)

out: list[dict] = []
n_flag = 0
sr_out = 24000
t_all = time.perf_counter()
for s in segs:
    sid = s["id"]
    wav = seg_dir / f"{sid:05d}.wav"
    text = (s.get("text_tts") or "").strip()
    flag: str | None = None
    if not text:
        sf.write(str(wav), np.zeros(0, dtype="float32"), sr_out)
        flag = "empty_tts"
    else:
        try:
            torch.manual_seed(SEED)
            wave, sr_out, _ = infer_process(
                ref_audio_proc, ref_text_final, accentize(text), model, vocoder,
                nfe_step=NFE_STEP, cross_fade_duration=0.15, speed=speed,
            )
            tmp = wav.with_suffix(".wav.tmp")
            sf.write(str(tmp), wave, sr_out, format="WAV", subtype="PCM_16")
            os.replace(tmp, wav)
        except Exception as e:
            print(f"[flag] id{sid}: synth_error {e}", file=sys.stderr)
            sf.write(str(wav), np.zeros(0, dtype="float32"), sr_out)
            flag = "synth_error"
    info = sf.info(str(wav))
    if flag:
        n_flag += 1
    out.append({
        "id": sid, "path": f"segments/{sid:05d}.wav",
        "samples": info.frames, "duration": round(info.frames / sr_out, 3),
        "sample_rate": info.samplerate if info.frames else sr_out,
        "start": s["start"], "end": s["end"],
        "text_tts": s.get("text_tts"), "flag": flag,
    })
    print(f"id{sid:03d}  {info.frames / sr_out:6.1f}s  {'FLAG ' + flag if flag else 'ok'}")

doc = {
    "sample_rate": sr_out, "engine": "f5-espeech-exp", "voice": ref_name,
    "count": len(out), "n_flagged": n_flag, "segments": out,
}
manifest = seg_dir / "manifest.json"                      # canonical: WorkDir.seg_manifest
tmp = manifest.with_suffix(".json.tmp")
tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
os.replace(tmp, manifest)
print(f"{len(out)} segments in {time.perf_counter() - t_all:.0f}s ({n_flag} flagged) -> {manifest}")
