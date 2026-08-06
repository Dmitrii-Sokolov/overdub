# SETUP.md — Windows 11 + RTX 4080 Mobile (12 GB) runtime for overdub

## Strategy: pipeline venv + parakeet venv + demucs venv

1. **`.venv-asr`** — the pipeline venv: **Silero — THE TTS engine since 2026-07-25** (via
   torch.hub, no asset to fetch and no separate venv), faster-whisper (the verify round-trip, and
   the fallback transcriber at `asr_engine = "whisper"`), the `overdub` package itself. torch cu128
   line.
2. **`.venv-parakeet`** — the STT venv since 2026-08-06, when Parakeet-TDT 0.6b v3 became the
   default transcriber. The `transcribe` stage drives it as a subprocess worker
   (`overdub/parakeet.py` ↔ `scripts/parakeet_worker.py --serve`), one live process per stage
   sweep. Isolation is not tidiness: `nemo_toolkit[asr]` resolves 137 packages and pins numpy
   BELOW the pipeline's (2.5.1 → 2.4.6), so installing it into `.venv-asr` would gamble
   faster-whisper, ctranslate2 and Silero on an ASR dependency tree.
3. **`.venv-demucs`** — the Demucs separation venv. The `separate` stage calls it as a CLI
   subprocess to build the no-vocals bed for `dub_mix = "bed"` (the production default). Isolation
   is deliberate: demucs's torch pins must not gamble the pipeline stack.

## Parakeet venv (the default transcriber)

Verified on host 2026-08-06: Python 3.12, torch 2.11 cu128, nemo-toolkit 2.7.3. Nothing needs a
compiler — of the resolved packages only `sox`, `kaldi-python-io` and `wget` arrive as sdists and
all three are pure Python. `pynini`, the one genuinely Windows-hostile NeMo dependency, belongs to
`nemo_text_processing` and is NOT pulled by the `[asr]` extra.

```powershell
py -3.12 -m venv .venv-parakeet
.venv-parakeet\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
.venv-parakeet\Scripts\python.exe -m pip install "nemo_toolkit[asr]" silero-vad
# ~2.5 GB of weights auto-download on first use (HF cache); the venv itself is ~7 GB
.venv-parakeet\Scripts\python.exe -c "import nemo.collections.asr; print('ok')"
```

`silero-vad` is NOT optional. NeMo has no VAD, and without the gate the model invents words on
non-speech — three silent videos in the 165-video corpus came back with 110, 32 and 6 invented
words (2026-08-06). The worker refuses to be quiet about a missing VAD, but it does not stop.

To go back to whisper: `asr_engine = "whisper"` in `overdub.toml`. Nothing else changes — the
verify round-trip runs on whisper either way, so `.venv-asr` keeps faster-whisper regardless.

## Demucs venv (bed mix — the default `dub_mix`)

Verified combo on host: Python 3.12, torch 2.11 cu128, demucs 4.1.0.

```powershell
py -3.12 -m venv .venv-demucs ; .venv-demucs\Scripts\Activate.ps1
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install demucs
# htdemucs weights auto-download on first run (torch.hub cache); ~3 GB VRAM per separation
```

The pipeline needs only `demucs_python = ".venv-demucs/Scripts/python.exe"` (config default).
`dub_mix = "replace"` or `"duck"` skips the separate stage entirely — no venv needed then.

> Verified on host: Silero loads and synthesizes fine on torch 2.11 (cu128). The one catch is that
> torchaudio 2.11 routes `torchaudio.save` through TorchCodec — so the SileroEngine writes wavs with
> `soundfile` instead. `.venv-tts` has been retired, and `.venv-f5tts` (8.7 GB) was deleted
> 2026-08-03 with the F5 engine it served. The layout was two venvs until 2026-08-06 and is
> **three** since Parakeet became the transcriber; a document saying "two" predates that.

## Python
Use **Python 3.12** on Windows (mid-2026 sweet spot — torch, faster-whisper, ctranslate2 and
demucs all ship 3.12 wheels; 3.13 audio/TTS wheel coverage is still spotty). `py -3.12 -m venv ...`.

## Install order (pin torch FIRST so a transitive dep can't swap your CUDA build)

```powershell
py -3.12 -m venv .venv-asr ; .venv-asr\Scripts\Activate.ps1
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128   # torch/torchaudio ONLY on this index
pip install faster-whisper                                                        # pulls ctranslate2>=4.5 (cuDNN 9 / CUDA 12)
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*                             # DLLs; see discovery caveat below
pip install -e .                                                                  # overdub package + deps (yt-dlp[default,deno] — the JS runtime lands in .venv-asr\Scripts, soundfile, omegaconf)
python -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
# Silero model auto-downloads on first synthesis (~38 MB, torch.hub cache)
```

Run the pipeline itself with `python -X utf8 -m overdub ...` — a cp1251 parent console would
mojibake the overnight log lines morning triage reads.

### External binaries (verify, don't auto-install — project rule)
```powershell
winget install Gyan.FFmpeg              # ffmpeg + ffprobe on PATH
.venv-asr\Scripts\python.exe -m pip install -U "yt-dlp[default,deno]"   # the pipeline resolves yt-dlp venv-first; a PATH copy is only the fallback
ffmpeg -version ; ffprobe -version ; .venv-asr\Scripts\yt-dlp.exe --version ; .venv-asr\Scripts\deno.exe --version
```

## `--index-url` scoping (critical)
Apply the PyTorch index-url **only to the `torch torchaudio` line**. If you apply it to the
faster-whisper install, PyPI-only deps fail to resolve. Dedicated torch line, then everything else
from PyPI.

## Windows cuDNN DLL discovery (the real coexistence trap, not a version conflict)
CTranslate2 does NOT bundle cuDNN and does NOT auto-locate it; Python 3.8+ ignores PATH for DLL loading.
Symptom: `Could not locate cudnn_ops64_9.dll`. Fixes (pick one):
- `os.add_dll_directory(r"...\site-packages\nvidia\cudnn\bin")` **before** importing faster_whisper, or
- add that dir to PATH, or
- drop in the Purfview whisper-standalone-win DLL bundle.

This is a discovery gap, NOT a reason to add more venvs.

## VRAM discipline on 12 GB (usable ~10.5–11 GB — WDDM + display reserve ~1–2 GB)
- **Stage 1** Parakeet peaks at ~8.8 GB on the corpus with 10-minute chunks (2026-08-06). The chunk
  size is the ONLY thing bounding that peak, and the ceiling does not announce itself: at 20-minute
  chunks every long video pinned exactly 10 813 MB of 12 282 and the WDDM driver started spilling
  into system RAM instead of failing — 100% GPU utilisation at roughly a twentieth of the
  throughput, a 271-minute video still decoding after 24 minutes. Do NOT try to bound it with
  `torch.cuda.empty_cache()` between chunks: NeMo's TDT decoder replays a CUDA graph that holds the
  captured buffers' raw addresses, and freeing them kills the whole batch with
  `illegal memory access` (17/17 videos in 8 s).
  whisper large-v3 fp16 ~4.5–6 GB → SAFE. `del model; gc.collect(); torch.cuda.empty_cache()` before next stage (empty_cache is a no-op while a ref is alive — drop refs FIRST).
- **Stage 3** TTS costs no VRAM at all (Silero runs on CPU); whisper-small verify adds ~1 GB → SAFE.
  The `separate` stage (htdemucs, ~3 GB) runs standalone between assemble and mux.
  With TTS on the CPU there is no real GPU contention left in a single-video pass.

## Laptop thermals (overnight batches)
Sustained load will thermal-throttle the 4080 Mobile (shows as rising RTF, not errors). Set a lower power
limit (`nvidia-smi -pl` or MSI Afterburner), insert cooldown pauses, keep the batch runner resumable per project spec.
