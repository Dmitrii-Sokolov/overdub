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
