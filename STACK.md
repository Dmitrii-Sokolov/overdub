# STACK.md — overdub verified stack (Windows 11 + RTX 4080 Mobile, 12 GB)

Local-only YouTube→Russian dubbing. One heavy GPU model at a time; explicit unload between stages.
Every fact below is tagged by confidence from the adversarial verification pass. **Load-bearing empirical
unknowns are called out explicitly — do not treat them as settled.**

Pipeline: `yt-dlp → faster-whisper large-v3 → Qwen3-14B (Ollama) → Chatterbox Multilingual → whisper-small verify → ffmpeg (MKV)`

---

## Stage 0 — Media I/O (yt-dlp + ffmpeg)

**Install**
```powershell
python -m pip install -U yt-dlp        # latest 2026.07.04, pure-Python
winget install Gyan.FFmpeg             # ffmpeg + ffprobe on PATH (both required)
# Verify, do not auto-install:
ffmpeg -version ; ffprobe -version ; yt-dlp --version
```

**Verified API — download, extract, tempo-fit, assemble, mux**
```python
import math, subprocess

# 1. Download (video stream kept intact for final mux, no re-encode)
subprocess.run(["yt-dlp", "-f", "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b",
                "--merge-output-format", "mkv", "-o", "work/source.%(ext)s", URL], check=True)

# 1b. 16 kHz mono WAV for whisper + reference extraction
subprocess.run(["ffmpeg","-y","-i","work/source.mkv","-vn","-ac","1","-ar","16000",
                "-c:a","pcm_s16le","work/source.wav"], check=True)

# 2. atempo chain for arbitrary factor (uncapped), each instance <= 2.0 (smooth blend)
def atempo_chain(f: float) -> str:
    if f <= 0: raise ValueError("factor must be > 0")
    base = 2.0 if f > 1 else 0.5
    n = max(1, math.ceil(math.log(f) / math.log(base)))   # keep each instance in [0.5, 2.0]
    each = f ** (1.0 / n)                                   # product of n copies == f exactly
    return ",".join(f"atempo={each:.6f}" for _ in range(n))

# 4. Assemble dub track: place each segment WAV at absolute start ms
def build_dub_track(segments, out, total_ms):   # segments = [(path, start_ms), ...] non-overlapping
    inputs, fil = [], []
    for i,(p,_) in enumerate(segments): inputs += ["-i", p]
    for i,(_,st) in enumerate(segments):
        fil.append(f"[{i}:a]aresample=48000,adelay={int(st)}:all=1[a{i}]")   # ms; :all=1 mandatory
    mix = "".join(f"[a{i}]" for i in range(len(segments)))
    fc = ";".join(fil) + f";{mix}amix=inputs={len(segments)}:normalize=0:dropout_transition=0," \
         f"apad,atrim=end={total_ms/1000.0}[out]"          # normalize=0 mandatory or track goes near-silent
    subprocess.run(["ffmpeg","-y",*inputs,"-filter_complex",fc,"-map","[out]",
                    "-ac","1","-ar","48000","-c:a","pcm_s16le",out], check=True)

# 3. Final MKV mux: copy video, orig+RU audio, EN+RU SRT, RU default
subprocess.run(["ffmpeg","-y","-i","work/source.mkv","-i","work/dub_ru.wav",
                "-i","work/en.srt","-i","work/ru.srt",
                "-map","0:v:0","-map","0:a:0","-map","1:a:0","-map","2:0","-map","3:0",
                "-c:v","copy","-c:a:0","copy","-c:a:1","aac","-b:a:1","192k","-c:s","srt",
                "-metadata:s:a:0","language=eng","-metadata:s:a:1","language=rus",
                "-metadata:s:s:0","language=eng","-metadata:s:s:1","language=rus",
                "-disposition:a:0","0","-disposition:a:1","default",       # clear orig default first
                "-disposition:s:0","0","-disposition:s:1","default",
                "work/output.mkv"], check=True)
```

**VRAM:** zero. Stream-copy mux + CPU DSP only; runs in seconds for multi-hour video.

**Gotchas (verified against ffmpeg source):**
- **atempo:** `[0.5, 100.0]` per instance, but >2.0 *skips samples* instead of blending. The equal-split chain is CONFIRMED correct — `n=ceil(log_base(f))` copies of `f**(1/n)` both stays ≤ base and multiplies to exactly `f`. A wrong split does NOT silently desync — ffmpeg hard-errors on out-of-range or degrades quality; duration stays exact. Real risk is only a wrapper that clamps instead of erroring.
- **amix:** `normalize=0` is CONFIRMED required — the default (`normalize=1`) applies 1/N scaling and makes a many-segment dub near-silent. With `normalize=0` each input passes at unity gain; non-overlapping segments sum losslessly. `dropout_transition` has no effect when `normalize=0`.
- **adelay:** value is MILLISECONDS; `:all=1` mandatory or only channel 1 is delayed. Delays are from t=0 and independent → no cumulative drift. amix does NOT resample — force every input to one rate via `aresample=48000` first.
- **MKV not MP4** for SRT (`-c:s srt`); MP4 only takes `mov_text`.
- **Disposition/metadata:** CONFIRMED pattern. Clear `-disposition:a:0 0` before `-disposition:a:1 default` (source default flag is copied otherwise). Metadata specifier is `-metadata:s:a:1` (leading `s` = stream-level). `default` is a player hint; mpv/VLC/Plex usually honor it but may override by language preference.
- yt-dlp needs **both** ffmpeg.exe AND ffprobe.exe on PATH.

**Sources:** ffmpeg atempo/adelay/amix docs + libavfilter source (af_amix.c, af_atempo.c), ffmpeg.org/ffmpeg.html, github.com/yt-dlp/yt-dlp/releases

---

## Stage 1 — ASR: faster-whisper large-v3 (main) + small (verify)

**Install**
```powershell
pip install faster-whisper            # latest 1.2.1 (2025-10-31); pulls ctranslate2>=4.5, av, onnxruntime
# GPU DLLs (see SETUP.md for the Windows PATH/os.add_dll_directory caveat):
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*
```

**Verified API**
```python
from faster_whisper import WhisperModel

# Stage 1 — main transcription (large-v3, fp16), EN forced, VAD on
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, info = model.transcribe(
    "work/source.wav", language="en", beam_size=5,
    word_timestamps=True,                 # populates seg.words: .start .end .word .probability
    vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
    condition_on_previous_text=False,     # cuts repetition/hallucination loops
)
# segments is a LAZY GENERATOR — nothing runs until iterated:
words = [(w.start, w.end, w.word, w.probability) for seg in segments for w in seg.words]

# Stage 3 verify — whisper-small (int8), RU forced
verifier = WhisperModel("small", device="cuda", compute_type="int8")
vseg, _ = verifier.transcribe("segment_ru.wav", language="ru", word_timestamps=False)
hyp = "".join(s.text for s in vseg)       # then normalize(hyp) vs normalize(ref_ru) similarity
```

**VRAM (Part A/C CONFIRMED via official benchmark, Part B corrected):**
- large-v3 fp16 ~4.5 GB standard / ~6 GB batched; int8 ~3 GB. small int8 ~1 GB. Well under 12 GB for sequential use.
- **CORRECTION — "never OOMs" is FALSE.** faster-whisper #1257: BatchedInferencePipeline at batch_size=80 hit 19 GB. VRAM scales with batch_size/beam_size/audio length. Safe only at modest settings; keep batching conservative on 12 GB.
- No official RTF/VRAM benchmark on RTX 4080 Mobile — the ~6 GB figure comes from an RTX 3070 Ti official run. RTF ~8–15× realtime is blog-level, LOW-MED confidence — **measure on the host.**

**Gotchas (verified):**
- **`Word` dataclass has exactly `.start/.end/.word/.probability`** and `seg.words` is `None` unless `word_timestamps=True` — CONFIRMED against current source. Pin your faster-whisper version.
- **Windows DLL-not-found** (`cudnn_ops64_9.dll` / `cublas64_12.dll`): the pip nvidia wheels drop DLLs under `site-packages/nvidia/*/bin` which is NOT auto-added to PATH, and Python 3.8+ ignores PATH for DLL loading. Fix with `os.add_dll_directory(...)` before import, or use the Purfview whisper-standalone-win bundle. Single most common setup failure.
- **CUDA 12 + cuDNN 9 required** (ctranslate2 ≥4.5) — CONFIRMED. Wrong cuDNN major = hard load failure. Legacy: cuDNN 8 → pin `ctranslate2==4.4.0`; CUDA 11 → `3.24.0`.
- **Silence/music hallucination** (repeated "Thank you.", credits): keep `vad_filter=True` + `condition_on_previous_text=False`. Critical for YouTube intros/outros.
- **Always pin `language=`** ("en" main, "ru" verify) — never auto-detect.
- Lazy generator: iterate it or nothing transcribes and no error is raised. Word timestamps can be non-monotonic at segment joins — clamp/sort before cutting audio.

**Sources:** github.com/SYSTRAN/faster-whisper (+ transcribe.py, issues #1257/#1230/#1086), pypi.org/project/faster-whisper, pypi.org/project/ctranslate2

---

## Stage 2 — Translation: Qwen3-14B via Ollama (OpenAI-compatible)

**Install**
```powershell
# Ollama is a SEPARATE OS process with its own bundled CUDA — NOT a pip package, NOT in the venv.
ollama pull qwen3:14b            # default = Q4_K_M, 9.3 GB, 40K native ctx
ollama pull qwen3:14b-q4_K_M     # explicit pin for reproducible batches (same blob)
pip install openai               # HTTP client only; no cloud calls
setx OLLAMA_KEEP_ALIVE -1        # keep resident across a long batch (more reliable than per-request)
```

**Verified API**
```python
from openai import OpenAI
import re

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")  # api_key ignored but must be non-empty

SYSTEM = ("You are a professional dubbing translator. Translate the English line to natural spoken "
          "Russian. Keep length close to the original so it fits the same speech duration. Expand "
          "numbers, units, acronyms and Latin terms into Russian words (GPU -> джи-пи-ю, x2 -> в два раза). "
          "Output ONLY the Russian translation, no notes. /no_think")

resp = client.chat.completions.create(
    model="qwen3:14b",
    messages=[{"role":"system","content":SYSTEM},
              {"role":"user","content":"This GPU is roughly x2 faster."}],
    temperature=0.2, top_p=0.9, seed=42,
    extra_body={"options": {"num_ctx": 4096}},   # pin ctx — Ollama preallocates KV for FULL num_ctx
)
text = resp.choices[0].message.content
text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()  # defensive fallback strip
```

**VRAM (CONFIRMED knife-edge — the tightest stage):**
- Q4_K_M weights = 9.3 GB. KV cache ≈ 0.156 MB/token (40 layers, 8 KV heads, head_dim 128, fp16).
- 4K ctx → ~10 GB total → FITS. 8K → ~10.6 GB → fits. **32K → ~14.4 GB → OVERFLOWS.**
- On a 12 GB laptop, WDDM + display reserve ~1–2 GB → usable ~10–10.5 GB. **Keep `num_ctx` ≤ ~8K (ideally 4K for per-segment).** Per-segment prompts are tiny; the danger is a large "safety" num_ctx that Ollama preallocates.
- Windows CUDA sysmem fallback is ON by default → overflow = **silent 5–30× slowdown**, not a clean OOM. Consider disabling it so spills fail loudly.

**Gotchas (verified):**
- **`/no_think` does NOT "reliably" suppress thinking** — silently ignored on several tags/quants/endpoints (mostly qwen3-vl and some 0.12.x/0.17.x builds). BUT non-VL `qwen3:14b` DOES carry the correct toggle template, so `think=false` works there; on native `/api/chat` thinking is routed to a separate `message.thinking` field and does NOT pollute `message.content`. Verify the installed template carries the toggle; keep the defensive strip as fallback.
- **`seed` is NOT ignored on `/v1`** — Ollama source forwards `seed` and `temperature` into the same Options map as native `/api/chat`. Caveat: seed ≠ bit-exact determinism — pin `num_ctx`, expect "reproducible-ish". Don't assume determinism for the verification gate.
- **`keep_alive` via OpenAI `extra_body` is flaky** — prefer server-side `OLLAMA_KEEP_ALIVE`.
- Verify the daemon is serving before the run: `curl http://localhost:11434/api/tags`.

**Sources:** ollama.com/library/qwen3:14b, docs.ollama.com/api/openai-compatibility, ollama.com/blog/thinking, github.com/ollama/ollama (openai.go, issues #12917/#11032/#14798/#5321), huggingface.co/Qwen/Qwen3-14B/config.json

---

## Stage 3 — TTS: Chatterbox Multilingual (EN reference → RU) + whisper-small verify

> **HIGHEST-RISK STAGE.** Mechanics verified; RU-from-EN-reference *quality* is REFUTED-as-guaranteed and must be ear-tested day 1. See DECISIONS.md go/no-go.

**Install (ISOLATED venv — hard pins collide with the whisper/torch venv)**
```powershell
py -3.12 -m venv .venv-tts
.venv-tts\Scripts\Activate.ps1
# Install CUDA torch FIRST (chatterbox does NOT pull a CUDA build itself):
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
pip install chatterbox-tts        # latest 0.1.7 (2026-03-26); import as `chatterbox`
# git must be on PATH — resemble-perth installs from a git URL at build time.
```

**Verified API**
```python
import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

# t3_model="v3" is REQUIRED — the shipped DEFAULT is v2, not v3. Omitting it silently gives V2.
model = ChatterboxMultilingualTTS.from_pretrained(device="cuda", t3_model="v3")

# CROSS-LINGUAL: Russian text, timbre from an ENGLISH clip.
# cfg_weight=0.0 = documented lever to MINIMIZE (not eliminate) reference-accent bleed.
wav = model.generate(
    "Привет, это тест синтеза русской речи.",
    language_id="ru",                         # REQUIRED for the multilingual class
    audio_prompt_path="reference_en.wav",     # 10s+ mono clip of the EN source speaker
    exaggeration=0.5, cfg_weight=0.0, temperature=0.8,
)
ta.save("out_ru.wav", wav, model.sr)
```
Full signature (CONFIRMED): `generate(self, text, language_id, audio_prompt_path=None, exaggeration=0.5, cfg_weight=0.5, temperature=0.8, repetition_penalty=1.2, min_p=0.05, top_p=1.0)`.

**VRAM:** 0.5B model, ~4–6 GB real-world at inference. Co-resident with whisper-small (~1–2 GB) fits under 12 GB — this is the one intentional two-model stage and it's SAFE. **No verified RTF for the full V3 multilingual on 4080 Mobile** — only datapoint is the 350M Turbo at RTF ~0.5 on a desktop 4090. Extrapolated ~0.8–1.5, UNVERIFIED — measure on host.

**Gotchas (verified):**
- **REFUTED: "EN reference sounds natively Russian, no accent."** Vendor docs: mismatched reference language → output "may inherit the accent of the reference clip's language"; `cfg_weight=0.0` only "minimizes"/"reduces" bleed. Issue #360: even a native RU reference drifts to English accent + broken stress after ~5 generations. **This is the project's core unproven assumption — see DECISIONS.md.**
- **v3 not default** — pass `t3_model="v3"` explicitly (loads `t3_mtl23ls_v3.safetensors`, 2.14 GB, from `ResembleAI/chatterbox` — CONFIRMED present). `cfg_weight` gates CFG (`>0.0`); 0.0 disables guidance.
- **Hard pins** `transformers==5.2.0`, `torch/torchaudio==2.6.0` — WILL collide with faster-whisper/Qwen tooling. Isolate this venv.
- **Per-call length bounded** (~few hundred chars / ~40s before hallucination). overdub is per-segment — keep segments short, never feed paragraphs.
- **No built-in RU normalizer** — the CLAUDE.md normalization (GPU→джи-пи-ю, x2→в два раза) is mandatory before `generate()`.
- Every output carries an imperceptible **Perth watermark** (not optional in default path). First run downloads weights from HF (needs network, then cached under HF_HOME).

**Sources:** github.com/resemble-ai/chatterbox (mtl_tts.py, README tips, issue #360), pypi.org/project/chatterbox-tts, huggingface.co/ResembleAI/chatterbox, replicate.com/resemble-ai/chatterbox-multilingual

---

## Cross-stage VRAM discipline (single 12 GB GPU)

```python
import gc, torch, requests

def unload(model):
    del model                    # MUST drop refs first — empty_cache() is a no-op while a ref lives
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()

def ollama_unload(model="qwen3:14b"):
    requests.post("http://localhost:11434/api/generate", json={"model": model, "keep_alive": 0})
    # then VERIFY release (ollama ps / nvidia-smi) before loading Stage-3 PyTorch models
```
Order: Stage1 whisper → `unload` → Stage2 Ollama → `ollama_unload` + verify free VRAM → Stage3 Chatterbox+whisper-small.
