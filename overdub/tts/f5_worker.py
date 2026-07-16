"""F5-TTS (ESpeech) worker — runs inside .venv-f5tts, serves synthesis over stdio.

Spawned as a SCRIPT by overdub.tts.f5.F5Engine, never imported: the F5 stack
(torch 2.8) is dependency-incompatible with the pipeline venv (torch 2.11), so it
lives in its own process with its own venv. Imports only .venv-f5tts deps + stdlib —
no `overdub` imports.

Protocol (one JSON object per line, UTF-8):
  child -> parent  {"event":"ready","sample_rate":24000}          after load-once init
  parent -> child  {"id":N,"text":...,"out":...,"seed":I,"speed":F}
  child -> parent  {"id":N,"ok":true,"sr":24000,"frames":M} | {"id":N,"ok":false,"error":...}
Worker exits on stdin EOF. A per-request exception answers ok:false and the worker
lives on; only a catastrophic failure (CUDA context death) kills the process.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# LOAD-BEARING — must run BEFORE the heavy imports below: save the real stdout for the
# protocol, then point fd 1 at stderr so any library print / tqdm / native fd-1 write
# (f5_tts and transformers both print banners) cannot corrupt the JSONL protocol stream.
_PROTO = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
os.dup2(2, 1)
sys.stdout = sys.stderr
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from ruaccent import RUAccent  # noqa: E402
from f5_tts.infer.utils_infer import (  # noqa: E402
    infer_process, load_model, load_vocoder, preprocess_ref_audio_text,
)
from f5_tts.model import DiT  # noqa: E402

MODEL_CFG = dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4)
CROSS_FADE = 0.15
SAMPLE_RATE = 24000                    # vocos-mel-24khz — a fact of the checkpoint, not a knob
_CYR = re.compile("[а-яА-ЯёЁ]")


class _SessionShim:
    """ruaccent 1.5.8.3 omits the token_type_ids input its accent/omograph ONNX exports
    declare — supply zeros (single-segment BERT semantics). Same shim as the bake-off
    scripts; drop when ruaccent fixes the export upstream."""

    def __init__(self, session):
        self._s = session
        self._need_tt = any(i.name == "token_type_ids" for i in session.get_inputs())

    def run(self, out, feed):
        if self._need_tt and "token_type_ids" not in feed:
            feed = {**feed, "token_type_ids": np.zeros_like(feed["input_ids"])}
        return self._s.run(out, feed)

    def __getattr__(self, name):
        return getattr(self._s, name)


def _send(msg: dict) -> None:
    _PROTO.write(json.dumps(msg, ensure_ascii=False) + "\n")
    _PROTO.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--vocab", required=True)
    ap.add_argument("--ref-audio", required=True)
    ap.add_argument("--ref-text", required=True, help="path to the exact ref transcript")
    ap.add_argument("--nfe", type=int, default=48)
    args = ap.parse_args()

    accent = RUAccent()
    accent.load(omograph_model_size="turbo3.1", use_dictionary=True)
    accent.accent_model.session = _SessionShim(accent.accent_model.session)
    if hasattr(accent, "omograph_model") and hasattr(accent.omograph_model, "session"):
        accent.omograph_model.session = _SessionShim(accent.omograph_model.session)

    def accentize(text: str) -> str:
        return accent.process_all(text) if _CYR.search(text) else text

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_model(DiT, MODEL_CFG, args.ckpt, vocab_file=args.vocab)
    vocoder = load_vocoder()               # NOTE: fetches Vocos from the HF cache on first ever run
    model.to(device)
    vocoder.to(device)

    ref_text_raw = open(args.ref_text, encoding="utf-8").read().strip()
    ref_audio_proc, ref_text_final = preprocess_ref_audio_text(args.ref_audio, accentize(ref_text_raw))

    _send({"event": "ready", "sample_rate": SAMPLE_RATE})

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            rid = req.get("id")
            try:
                torch.manual_seed(int(req["seed"]))
                wave, sr, _ = infer_process(
                    ref_audio_proc, ref_text_final, accentize(req["text"]), model, vocoder,
                    nfe_step=args.nfe, cross_fade_duration=CROSS_FADE, speed=float(req["speed"]),
                )
                # explicit format="WAV": out is usually an atomic .wav.tmp path soundfile
                # cannot infer a container from
                sf.write(req["out"], wave, sr, format="WAV", subtype="PCM_16")
                _send({"id": rid, "ok": True, "sr": int(sr), "frames": int(len(wave))})
            except Exception as e:         # per-request failure never kills the worker
                _send({"id": rid, "ok": False, "error": f"{type(e).__name__}: {e}"})
    except KeyboardInterrupt:              # shared console Ctrl+C: exit quietly, parent handles it
        pass


if __name__ == "__main__":
    main()
