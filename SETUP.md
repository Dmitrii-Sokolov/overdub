# SETUP.md — Windows 11 + RTX 4080 Mobile (12 GB) runtime for overdub

## Strategy: TWO Python venvs + Ollama as a separate OS process

Chatterbox hard-pins `torch==2.6.0` and `transformers==5.2.0`. faster-whisper wants current
`ctranslate2>=4.5` and coexists best with a current torch (cu128). Those pins fight. Rather than
solve a fragile shared resolution, split by the natural stage boundary the pipeline already enforces:

1. **`.venv-asr`** — faster-whisper large-v3 + whisper-small (STT stages). Current torch cu128 line.
2. **`.venv-tts`** — Chatterbox Multilingual (TTS stage). Pinned torch 2.6.0 cu124.
3. **Ollama** — installed as a standalone Windows app/service. Its own bundled CUDA; NOT a pip package, never in a venv. Treat as a black-box localhost service.

> faster-whisper + torch CAN share ONE venv (both target cuDNN 9 / CUDA 12) — the "must split for
> whisper" story is overstated; the only Windows friction is DLL discovery (below). **The actual
> forcing reason to keep TTS separate is Chatterbox's transformers==5.2.0 pin.** ASR could join the
> orchestrator env; TTS stays isolated regardless.

## Python
Use **Python 3.12** on Windows (mid-2026 sweet spot — torch, faster-whisper, ctranslate2, chatterbox all
ship 3.12 wheels; 3.13 audio/TTS wheel coverage is still spotty). `py -3.12 -m venv ...`.

## Install order (pin torch FIRST in each venv so a transitive dep can't swap your CUDA build)

### .venv-asr (STT)
```powershell
py -3.12 -m venv .venv-asr ; .venv-asr\Scripts\Activate.ps1
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128   # torch/torchaudio ONLY on this index
pip install faster-whisper                                                        # pulls ctranslate2>=4.5 (cuDNN 9 / CUDA 12)
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*                             # DLLs; see discovery caveat below
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

### .venv-tts (TTS)
```powershell
py -3.12 -m venv .venv-tts ; .venv-tts\Scripts\Activate.ps1
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124   # HARD pin for chatterbox
pip install chatterbox-tts        # git must be on PATH (resemble-perth from git URL)
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```

### External binaries (verify, don't auto-install — project rule)
```powershell
winget install Gyan.FFmpeg              # ffmpeg + ffprobe on PATH
python -m pip install -U yt-dlp
# Ollama: install from ollama.com, then:
ollama pull qwen3:14b
setx OLLAMA_KEEP_ALIVE -1               # keep model resident across a long batch
ffmpeg -version ; ffprobe -version ; yt-dlp --version ; curl http://localhost:11434/api/tags
```

## `--index-url` scoping (critical)
Apply the PyTorch index-url **only to the `torch torchaudio` line**. If you apply it to installs of
faster-whisper / chatterbox, PyPI-only deps fail to resolve. Dedicated torch line, then everything else from PyPI.

## Windows cuDNN DLL discovery (the real coexistence trap, not a version conflict)
CTranslate2 does NOT bundle cuDNN and does NOT auto-locate it; Python 3.8+ ignores PATH for DLL loading.
Symptom: `Could not locate cudnn_ops64_9.dll`. Fixes (pick one):
- `os.add_dll_directory(r"...\site-packages\nvidia\cudnn\bin")` **before** importing faster_whisper, or
- add that dir to PATH, or
- drop in the Purfview whisper-standalone-win DLL bundle.
This is a discovery gap, NOT a reason to add more venvs.

## VRAM discipline on 12 GB (usable ~10.5–11 GB — WDDM + display reserve ~1–2 GB)
One heavy model at a time:
- **Stage 1** whisper large-v3 fp16 ~4.5–6 GB → SAFE. `del model; gc.collect(); torch.cuda.empty_cache()` before next stage (empty_cache is a no-op while a ref is alive — drop refs FIRST).
- **Stage 2** Qwen3-14B Q4_K_M 9.3 GB + KV → **tightest stage. Pin `num_ctx` ≤ ~8K (use 4K per-segment).** Windows CUDA sysmem fallback is ON by default → overflow = silent 5–30× slowdown, not OOM. Consider disabling sysmem fallback and running the display on the iGPU. `keep_alive:0` at stage end, then VERIFY free VRAM (nvidia-smi / `ollama ps`) before Stage 3.
- **Stage 3** Chatterbox 0.5B (~4–6 GB) + whisper-small (~1–2 GB) co-resident → SAFE.

## Laptop thermals (overnight batches)
Sustained load will thermal-throttle the 4080 Mobile (shows as rising RTF, not errors). Set a lower power
limit (`nvidia-smi -pl` or MSI Afterburner), insert cooldown pauses, keep the batch runner resumable per project spec.
