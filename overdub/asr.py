"""Shared faster-whisper helpers: Windows cuDNN DLL discovery + model loading.

Used by the transcribe (large-v3) and verify (whisper-small) stages. CTranslate2
does not bundle or auto-locate cuDNN/cuBLAS, and Python 3.8+ ignores PATH for DLL
loading — so on Windows we must register the pip nvidia wheels' bin dirs explicitly
(the STACK.md gotcha). Verified working on the RTX 4080 Mobile.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def add_cuda_dll_dirs() -> None:
    if os.name != "nt":
        return
    try:
        import nvidia  # namespace package from nvidia-cudnn-cu12 / nvidia-cublas-cu12
    except ImportError:
        return
    for root in nvidia.__path__:
        for pkg in ("cudnn", "cublas"):
            bindir = Path(root) / pkg / "bin"
            if bindir.is_dir():
                os.add_dll_directory(str(bindir))


def _warm(model) -> None:
    """One throwaway decode, so the first REAL video does not pay for kernel autotuning.

    Constructing a WhisperModel does not touch the GPU compute path: cuDNN/cuBLAS pick and tune
    their kernels on the first actual encode, so that cost lands inside whichever video happens
    to be first in a sweep. It is invisible in the stage wall clock (it looks like a slow video)
    and it makes the first row of every batch incomparable to the rest — which is exactly what a
    before/after optimization measurement must not have.

    Shaped like the real call on purpose — same beam size, same word_timestamps — because those
    are what select the kernels being tuned; a cheaper warmup would tune the wrong ones. VAD is
    off so the decoder cannot skip the buffer entirely and warm nothing.

    NEVER RAISES. A model that loaded is usable whether or not it got warmed; failing the run
    over an optimization aid would trade a real capability for a measurement.
    """
    try:
        import numpy as np

        # 1 s of near-silent noise at whisper's 16 kHz. Digital silence is a weaker warmup —
        # the decoder can short-circuit on an all-zero buffer and tune nothing.
        rng = np.random.default_rng(0)                      # fixed seed: warmup must not be a
        audio = (rng.standard_normal(16_000) * 1e-3).astype("float32")   # source of run variance
        segments, _info = model.transcribe(audio, language="en", beam_size=5,
                                           word_timestamps=True, vad_filter=False)
        for _ in segments:                                  # the generator is lazy — draining it
            pass                                            # is what actually runs the decode
    except Exception as e:                                  # noqa: BLE001 — cosmetic by contract
        print(f"[warn] whisper warmup failed ({e}) — the first video of this sweep absorbs "
              f"kernel autotuning and will look slower than it is", file=sys.stderr)


def load_whisper(model: str, device: str = "cuda", compute_type: str = "float16"):
    """Load a faster-whisper WhisperModel with the Windows DLL dirs registered first, warmed.

    Warming HERE rather than in the transcribe stage is deliberate: the session caches one model
    per (name, device, compute_type) and hands it to transcribe, verify and the synthesize reseed
    loop alike, so this is the one place that runs exactly once per load and no caller has to
    know the concept exists."""
    add_cuda_dll_dirs()
    from faster_whisper import WhisperModel

    t0 = time.perf_counter()
    m = WhisperModel(model, device=device, compute_type=compute_type)
    load_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    _warm(m)
    print(f"[asr ] {model} loaded in {load_s:.1f}s, warmed in {time.perf_counter() - t0:.1f}s",
          file=sys.stderr)
    return m


def roundtrip_similarity(model, wav_path, ref_norm: str, language: str) -> tuple[float, str, str]:
    """ASR round-trip: transcribe `wav_path`, normalize the hypothesis with the SAME
    normalizer as the reference, return (char-level ratio, raw hyp, normalized hyp).

    The single source of truth for the round-trip — verify and the synthesize reseed
    loop MUST both call this, or their similarity scores drift apart (the normalize.py
    "same transform on both sides" precedent). An empty normalized hypothesis scores 0.0.
    Transcription errors propagate — callers own the flag taxonomy.
    """
    from difflib import SequenceMatcher

    from .normalize import normalize_for_compare

    parts, _info = model.transcribe(
        str(wav_path), language=language, beam_size=5,
        vad_filter=False, condition_on_previous_text=False,
    )
    hyp = " ".join(p.text.strip() for p in parts).strip()
    hyp_n = normalize_for_compare(hyp)
    if not hyp_n:
        return 0.0, hyp, hyp_n
    return SequenceMatcher(None, ref_norm, hyp_n, autojunk=False).ratio(), hyp, hyp_n
