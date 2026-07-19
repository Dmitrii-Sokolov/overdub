# STACK.md — overdub verified stack (Windows 11 + RTX 4080 Mobile, 12 GB)

Local-only YouTube→Russian dubbing. One heavy GPU model at a time; explicit unload between stages.
Every fact below is tagged by confidence from the adversarial verification pass. **Load-bearing empirical
unknowns are called out explicitly — do not treat them as settled.**

Pipeline: `yt-dlp → faster-whisper large-v3 → Gemma-3-12B (Ollama) → ESpeech/F5-TTS (worker) → whisper-small verify → htdemucs bed → ffmpeg (MKV)`

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

## Stage 2 — Translation: Gemma-3-12B via Ollama (OpenAI-compatible)

> As of 2026-07-18 the default is **Gemma-3-12B** (no thinking mode, no system role — the system prompt is folded into the user turn, no `think` key sent). The Qwen3-14B findings below are retained as history.

**Install**
```powershell
# Ollama is a SEPARATE OS process with its own bundled CUDA — NOT a pip package, NOT in the venv.
ollama pull gemma3:12b            # default = Q4_K_M, ~8.1 GB (this host: digest f4031aab637d)
# reproducible batches: pin by digest (gemma3:12b@sha256:…) — no bare gemma3:12b-q4_K_M tag exists
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
    model="gemma3:12b",
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

**HOST FINDING (2026-07-15, overrides the sketch above): use native `/api/chat` with `think: false`, NOT `/v1` + `/no_think`.** Measured on the RTX 4080M: over the OpenAI `/v1` endpoint, an in-prompt `/no_think` is ignored on many samples, qwen3's reasoning goes to a separate `reasoning` field, and `num_predict` truncates it (`finish_reason=length`) BEFORE any answer — leaving `message.content` **EMPTY**. `extra_body={"think": false}` and `chat_template_kwargs.enable_thinking=false` on `/v1` did NOT help. The native `POST /api/chat` body `{"think": false, "stream": false, "options": {...}}` reliably disables thinking: ~5 s/sentence vs ~16 s, clean `message.content`. The translate stage uses this; it dropped the `openai` dep (stdlib urllib only). Keep the `<think>` regex strip as a defensive fallback anyway.

**Gotchas (verified):**
- **`/no_think` does NOT "reliably" suppress thinking** — silently ignored on several tags/quants/endpoints (mostly qwen3-vl and some 0.12.x/0.17.x builds). BUT non-VL `qwen3:14b` DOES carry the correct toggle template, so native `think=false` works there (see HOST FINDING — the `/v1` path leaves content empty). Verify the installed template carries the toggle; keep the defensive strip as fallback.
- **`seed` is NOT ignored on `/v1`** — Ollama source forwards `seed` and `temperature` into the same Options map as native `/api/chat`. Caveat: seed ≠ bit-exact determinism — pin `num_ctx`, expect "reproducible-ish". Don't assume determinism for the verification gate.
- **`keep_alive` via OpenAI `extra_body` is flaky** — prefer server-side `OLLAMA_KEEP_ALIVE`.
- Verify the daemon is serving before the run: `curl http://localhost:11434/api/tags`.

**Sources:** ollama.com/library/qwen3:14b, docs.ollama.com/api/openai-compatibility, ollama.com/blog/thinking, github.com/ollama/ollama (openai.go, issues #12917/#11032/#14798/#5321), huggingface.co/Qwen/Qwen3-14B/config.json

---

## Stage 3 — TTS: ESpeech/F5 (production) + Silero v5_5_ru (fallback) + whisper-small verify

> Engine history: the day-1 ear test **rejected Chatterbox** (unusable Russian
> even without cloning); Silero v4_ru carried Phase 1; bake-off #2 (2026-07-16,
> ear) made **ESpeech-TTS-1_RL-V2 (F5-TTS) the production engine**. See
> DECISIONS.md + bakeoff/tts-research-2026-07.md.

### Production: ESpeech-TTS-1_RL-V2 (F5-TTS) — worker in `.venv-f5tts`

- **Install / assets:** SETUP.md ("F5/ESpeech TTS venv + assets") — checkpoint
  ~2.7 GB + narrator reference clip (wav + exact transcript; config
  `f5_ref_audio` / `f5_ref_text`; rights caveat in README "Voices").
- **Adapter:** `overdub/tts/f5.py` spawns `overdub/tts/f5_worker.py` with the
  venv's python; line-JSON over stdio, reader-thread timeouts, id echo,
  respawn-once, 3-strike `TtsFatalError`. Startup ~30 s; warm synth ~×1.1 of
  audio duration; RTF 0.39 cold / ~0.60 thermally loaded; ~0.7–0.8 GiB VRAM.
- **Output:** 24 kHz mono (vocos-mel-24khz — a checkpoint fact, not a knob);
  RUAccent (turbo3.1) puts stresses in-worker.
- **Seed-capable:** reseed-retry lives in the synthesize stage (keep-best by
  round-trip similarity, seeds base+1..+N).
- **Native speed / slot-fill:** the duration canvas is deterministic
  (`out ≈ ref_sec·gen_bytes/ref_bytes/speed`); `plan_speed()` stretches to the
  unit's source span (floor 0.75×base) or mildly compresses (ceil 1.1×base —
  native compression ≥~1.3 DROPS words; atempo does the top-up, ear 2026-07-17).
- **Short-text class:** gen texts <10 UTF-8 bytes force local speed 0.3 and
  garble — mitigated upstream (ultra-short merge in transcribe + unit grouping).

### Fallback: Silero (fixed voice, CPU, no reference clip)

> Slightly below F5/ESpeech on quality, but needs NO voice sample — the
> zero-setup, zero-rights-questions option (user verdict 2026-07-18). The
> adapter defaults to **v5_5_ru** (`cfg.silero_model`, audition 2026-07-19 —
> audibly better, same five voices, 12-19× faster synth than F5 on CPU alone);
> **v4_ru** is kept only to reproduce pre-2026-07-19 runs. v5 REJECTS Latin
> script — safe because text_tts is Cyrillic-only by the normalize contract
> (measured: 0 Latin chars across the 12-video batch; no filter needed).

**Install** — no pip package required; `torch.hub` fetches the model. Silero
needs only `torch` + `torchaudio` (+ `omegaconf`), so it shares the ASR venv
(`.venv-asr`); the Chatterbox-era `.venv-tts` is retired.
```powershell
pip install omegaconf            # usually already present; torch/torchaudio already installed
# model auto-downloads on first torch.hub.load (~139 MB for v5_5_ru, cached in ~/.cache/torch/hub)
```

**Verified API** (working on host)
```python
import torch, torchaudio as ta

# CPU by design — measured RTF ~0.02–0.3 on CPU; keeps the GPU free.
model, _ = torch.hub.load("snakers4/silero-models", "silero_tts",
                          language="ru", speaker="v5_5_ru", trust_repo=True)
model.to(torch.device("cpu"))

audio = model.apply_tts(                      # returns a 1-D float tensor
    text="Это тест синтеза русской речи.",
    speaker="eugene",                         # primary voice; kseniya = backup
    sample_rate=48000,                        # 8000 / 24000 / 48000 — 48k is best
    put_accent=True, put_yo=True,             # auto stress + ё
)
ta.save("seg.wav", audio.unsqueeze(0), 48000)  # apply_tts is 1-D → unsqueeze for save
```

**Voices** (same five in v4/v5): `aidar`, `baya`, `kseniya`, `xenia`, `eugene`
(v4's extra `random` speaker was removed in v5). Ear ranking (2026-07-19,
v5_5_ru): **eugene = primary**, **kseniya = backup**; xenia good but slightly
unpleasant; aidar/baya have an off-standard accent — avoid. No cloning — every
video gets the same chosen narrator voice (the same-voice premise was dropped).

**VRAM:** effectively **zero** — runs on CPU (model ~0.1–0.5 GB even on GPU).
whisper-small verify (~1 GB) has the whole Stage-3 budget to itself. **Measured
RTF ~0.02–0.3 on CPU** — TTS is no longer a throughput factor.

**Controls / gotchas:**
- **Speech rate / pauses** via SSML (`<prosody rate="...">`, `<break time="400ms"/>`), but the pipeline fits timing with `atempo` at assembly anyway — SSML rate is secondary.
- **Manual stress**: put `+` after the stressed vowel (`«зам+ок»`) to fix homographs / names; `put_accent=True` handles the common case automatically.
- **Deterministic** — no temperature/seed; same text → same audio. Good for a reproducible verify gate, BUT a failed segment can't be "reseeded" — it gets flagged, not regenerated (the F5 path reseeds; Silero failures flag directly).
- **Per-call text length** bounded (~1000 chars) — per-sentence input is fine.
- **Sibilant hiss** on some speakers (baya) — de-ess / `afftdn` post-pass if ever needed; eugene is clean.
- Normalization (GPU→джи-пи-ю, x2→в два раза) still mandatory before synthesis.

**Sources:** github.com/snakers4/silero-models, pytorch.org/hub/snakers4_silero-models_tts, models.silero.ai

---

## Cross-stage VRAM discipline (single 12 GB GPU)

```python
import gc, torch, requests

def unload(model):
    del model                    # MUST drop refs first — empty_cache() is a no-op while a ref lives
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()

def ollama_unload(model="gemma3:12b"):
    requests.post("http://localhost:11434/api/generate", json={"model": model, "keep_alive": 0})
    # then VERIFY release (ollama ps / nvidia-smi) before loading Stage-3 PyTorch models
```
Order: Stage1 whisper → `unload` → Stage2 Ollama → `ollama_unload` + verify free VRAM → Stage3 F5 worker (~0.7 GiB) + whisper-small (~1 GB). Stage 3 is light — the only real juggling is whisper-large ↔ Gemma. (Silero fallback: CPU, ~zero VRAM. The `separate` stage — htdemucs, ~3 GB — runs standalone between assemble and mux.)
