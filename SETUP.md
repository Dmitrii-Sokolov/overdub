# SETUP.md — Windows 11 + RTX 4080 Mobile (12 GB) runtime for overdub

## Strategy: pipeline venv + F5 worker venv + Ollama as a separate OS process

1. **`.venv-asr`** — the pipeline venv: faster-whisper (STT + verify), Silero (fallback TTS via
   torch.hub), the `overdub` package itself. torch cu128 line.
2. **`.venv-f5tts`** — the F5/ESpeech TTS venv (torch 2.8 cu128). The production engine runs
   here as a worker subprocess (`overdub/tts/f5_worker.py`) driven over stdio — f5-tts is
   dependency-incompatible with `.venv-asr` (torch 2.11 vs 2.8, numpy downgrade, torchcodec ABI,
   ~110 extra packages; measured via pip dry-run, see DECISIONS 2026-07-16). Never merge them.
3. **Ollama** — standalone Windows app/service, its own bundled CUDA; NOT a pip package, never in a
   venv. Treat as a black-box localhost service.

## F5/ESpeech TTS venv + assets (production engine)

```powershell
py -3.12 -m venv .venv-f5tts ; .venv-f5tts\Scripts\Activate.ps1
pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
pip install f5-tts ruaccent soundfile huggingface_hub

# ESpeech RL-V2 checkpoint + vocab (~2.7 GB) -> models/espeech-rlv2/
hf download ESpeech/ESpeech-TTS-1_RL-V2 --local-dir models\espeech-rlv2

# Narrator reference: HF Space Den4ikAI/ESpeech-TTS, file ref/example.mp3 -> convert to wav +
# write the exact transcript next to it (rights caveat — personal use only, NOT committed;
# see README "Voices, cloning and the law"):
#   models/refs/ref_espeech_demo.wav + models/refs/ref_espeech_demo.txt

# Vocos vocoder prefetch (load_vocoder() pulls charactr/vocos-mel-24khz from the HF hub on
# first use — on a clean machine do it NOW, not inside the worker's startup timeout):
python -c "from f5_tts.infer.utils_infer import load_vocoder; load_vocoder()"
# RUAccent models (turbo3.1 + dictionary) auto-download on first load the same way.
```

The pipeline needs only `f5_python = ".venv-f5tts/Scripts/python.exe"` (config default) — the
worker is spawned per synthesize run, loads the model once (~30 s), and is closed at stage end.
Run the pipeline itself with `python -X utf8 -m overdub ...` — the worker's stderr is UTF-8 and
a cp1251 parent console would mojibake the overnight log lines morning triage reads.

> Verified on host: Silero loads and synthesizes fine on torch 2.11 (cu128). The one catch is that
> torchaudio 2.11 routes `torchaudio.save` through TorchCodec — so the SileroEngine writes wavs with
> `soundfile` instead. `.venv-tts` has been retired.

## Python
Use **Python 3.12** on Windows (mid-2026 sweet spot — torch, faster-whisper, ctranslate2, chatterbox all
ship 3.12 wheels; 3.13 audio/TTS wheel coverage is still spotty). `py -3.12 -m venv ...`.

## Install order (pin torch FIRST so a transitive dep can't swap your CUDA build)

```powershell
py -3.12 -m venv .venv-asr ; .venv-asr\Scripts\Activate.ps1
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128   # torch/torchaudio ONLY on this index
pip install faster-whisper                                                        # pulls ctranslate2>=4.5 (cuDNN 9 / CUDA 12)
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*                             # DLLs; see discovery caveat below
pip install -e .                                                                  # overdub package + deps (yt-dlp, openai, soundfile, omegaconf)
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
# Silero model auto-downloads on first synthesis (~38 MB, torch.hub cache)
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
- **Stage 3** Silero runs on **CPU** (~0 VRAM) + whisper-small (~1 GB) → trivially SAFE. The only real GPU contention is Stage 1 ↔ Stage 2.

## Laptop thermals (overnight batches)
Sustained load will thermal-throttle the 4080 Mobile (shows as rising RTF, not errors). Set a lower power
limit (`nvidia-smi -pl` or MSI Afterburner), insert cooldown pauses, keep the batch runner resumable per project spec.
