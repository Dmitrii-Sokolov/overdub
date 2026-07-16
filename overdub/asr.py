"""Shared faster-whisper helpers: Windows cuDNN DLL discovery + model loading.

Used by the transcribe (large-v3) and verify (whisper-small) stages. CTranslate2
does not bundle or auto-locate cuDNN/cuBLAS, and Python 3.8+ ignores PATH for DLL
loading — so on Windows we must register the pip nvidia wheels' bin dirs explicitly
(the STACK.md gotcha). Verified working on the RTX 4080 Mobile.
"""

from __future__ import annotations

import os
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


def load_whisper(model: str, device: str = "cuda", compute_type: str = "float16"):
    """Load a faster-whisper WhisperModel with the Windows DLL dirs registered first."""
    add_cuda_dll_dirs()
    from faster_whisper import WhisperModel

    return WhisperModel(model, device=device, compute_type=compute_type)


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
