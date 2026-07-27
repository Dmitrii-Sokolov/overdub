# STACK.md — overdub host-findings ledger (Windows 11 + RTX 4080 Mobile, 12 GB)

Local-only YouTube→Russian dubbing. **This file is NOT a cookbook and NOT an install guide.** The
runnable code is the source of truth for HOW to call each library (pointers per stage below), and
SETUP.md owns install. This ledger holds only what is true ONLY on this host, or ONLY after being
measured / debugged here: VRAM budgets, host-specific findings, and non-obvious gotchas in the
external tools that cost real effort to discover and would be re-derived from scratch without a note.
If a fact is derivable by reading the code, it does not belong here.

Pipeline: `yt-dlp → faster-whisper large-v3 → Gemma-3-12B (Ollama) → Silero v5_5_ru → whisper-small verify → htdemucs bed → ffmpeg (MKV)`

- **Install:** SETUP.md · **Rationale + history:** `.claude/DECISIONS.md` · **Config defaults:** `overdub/config.py`

---

## Stage 0 — Media I/O (yt-dlp + ffmpeg)

**Code:** download `overdub/stages/download.py` (`_tool_exe` resolves yt-dlp/ffmpeg venv-Scripts-first
then PATH; `_extract_wav` = 16 kHz mono for whisper) · dub track `overdub/stages/assemble.py`
(the atempo chain + adelay/amix layering) · mux `overdub/stages/mux.py` (`_extract`, final MKV).
**VRAM: zero** — CPU DSP + stream-copy mux, runs in seconds for multi-hour video (video stream is
never re-encoded).

**Gotchas (verified against ffmpeg source — these are the ones that silently corrupt output):**
- **atempo** is valid `[0.5, 100.0]` per instance, but >2.0 SKIPS samples instead of blending. Use an
  equal-split chain — `n = ceil(log_base(f))` copies of `f**(1/n)` both stay ≤ base and multiply to
  exactly `f`. A wrong split does NOT silently desync — ffmpeg hard-errors or degrades quality,
  duration stays exact. Real risk is only a wrapper that clamps instead of erroring.
- **amix `normalize=0` is REQUIRED.** The default `normalize=1` applies 1/N scaling → a many-segment
  dub goes near-silent. With `normalize=0` non-overlapping segments sum at unity gain, losslessly.
  `dropout_transition` has no effect when `normalize=0`.
- **adelay** value is MILLISECONDS and `:all=1` is mandatory (else only channel 1 is delayed). Delays
  are from t=0 and independent → no cumulative drift. amix does NOT resample — force every input
  through `aresample=48000` first.
- **MKV not MP4** for SRT subs (`-c:s srt`); MP4 only takes `mov_text`.
- **Disposition/metadata:** clear `-disposition:a:0 0` BEFORE `-disposition:a:1 default` (the source
  default flag is copied otherwise). Specifier is `-metadata:s:a:1` (leading `s` = stream-level).
  `default` is a player hint — mpv/VLC/Plex usually honor it but may override by language preference.
- yt-dlp needs BOTH `ffmpeg.exe` AND `ffprobe.exe` on PATH.

---

## Stage 1 — ASR: faster-whisper large-v3 (main) + small (verify)

**Code:** transcribe `overdub/stages/transcribe.py` (`transcribe_words` — the shared body used by
both the stage and `--repair-asr`, so they cannot drift in beam/VAD/word_timestamps;
`TranscribeStage._guard` = the automatic cond retry) · verify `overdub/stages/verify.py` · model load
+ caching `overdub/asr.py` (`load_whisper`, `asr_key`) and `overdub/pipeline.py` (session reuse).
Both ASR roles are configured in `overdub/config.py`.

**VRAM:** large-v3 fp16 ~4.5 GB standard / ~6 GB batched (host-measured ~3.1 GB resident); small
verify fp16 ~0.5 GB. Well under 12 GB for sequential use. **"never OOMs" is FALSE** — faster-whisper
#1257: `BatchedInferencePipeline` at batch_size=80 hit 19 GB; VRAM scales with batch/beam/audio-length,
so keep batching conservative. No official RTF/VRAM benchmark on the 4080 Mobile (the ~6 GB is a
3070 Ti run) — measure on host.

**Gotchas:**
- **Windows DLL-not-found** (`cudnn_ops64_9.dll` / `cublas64_12.dll`): the pip nvidia wheels drop
  DLLs under `site-packages/nvidia/*/bin`, which is NOT on PATH, and Python 3.8+ ignores PATH for DLL
  loading. Fix with `os.add_dll_directory(...)` before import (SETUP.md) or the Purfview standalone
  bundle. Single most common setup failure. [general form: `~/.claude/knowledge/python/windows-ml-gotchas.md`]
- **CUDA 12 + cuDNN 9 required** (ctranslate2 ≥4.5). Wrong cuDNN major = hard load failure. Legacy:
  cuDNN 8 → pin `ctranslate2==4.4.0`; CUDA 11 → `3.24.0`.
- **`condition_on_previous_text=True` is what SHIPS** (`cfg.whisper_condition_on_previous`), and the
  "False cuts loops" folk wisdom is backwards here. True is required for PUNCTUATION — without it
  whisper returned 60–206 s terminator-free blocks the resegmenter bisected mid-phrase (the "period
  mid-sentence" class, DECISIONS 2026-07-17). True CAN feed an alignment-collapse loop (2026-07-24
  confirmed cond=True is the collapse SOURCE, not a guard — 7/7 on floor stamps), but the pipeline
  does not pay for that by defaulting the flag off: `_guard` measures the share of words stamped onto
  the `MIN_WORD_DUR` floor (`floor_run_ratio`, the collapse signature) and re-runs ONCE at cond=False,
  keeping the retry only if it at least HALVES the ratio; deterministic-collapse sources get a
  per-source `cond=False` hatch in `overdub.toml` (e.g. 4szRHy_CT7s). The value that ACTUALLY decoded,
  not the intent, is stamped into `asr_key`. Do NOT hardcode `False` as a blanket loop guard.
- **`int8_float16` is SLOWER here — 0.81× (−24%) on large-v3, rejected 2026-07-24.** Ada's fp16
  tensor cores are already the fast path; `int8_float16` only adds a per-layer quantize/dequantize
  cost for no compute win. This is NOT the silent CTranslate2 fp16 fallback (that reads ~1.0× with
  near-identical text — here int8 executes AND the text differs, the answer is just negative). int8
  pays off on CPU, pre-Ada GPUs, or when VRAM is the bound — none hold here (~3.1 GB in a 12 GB
  budget). **Both ASR roles ship `float16`; do not "optimize" either to int8.** Record: DECISIONS +
  CHANGELOG 2026-07-24, cells `work-exp/asr-probe-int8/`.
- **verify compute_type is a SEPARATE config key** (`verify_compute_type`, deliberately NOT inherited
  from `whisper_compute_type`): the round-trip verifier is the pipeline's measuring instrument — it
  decides which units are flagged — so it must not move with the transcriber under test. Today both
  resolve to float16.
- **`Word` has exactly `.start/.end/.word/.probability`**, and `seg.words` is None unless
  `word_timestamps=True`. Pin the faster-whisper version. Word timestamps can be non-monotonic at
  segment joins — clamp/sort before cutting audio (flatten does). `word_timestamps=True` is
  load-bearing (sentence resegmentation, timing sync and `--repair-asr` all build on it).
- **Silence/music hallucination** (repeated "Thank you.", credits): `vad_filter=True` is the primary
  defence, critical for YouTube intros/outros. (On cond the shipped answer is True + `_guard`, not a
  blanket False — see above.)
- **Always pin `language=`** ("en" main, "ru" verify) — never auto-detect. The lazy generator must be
  iterated or nothing transcribes and no error is raised.
- **`num_workers=N`** is a construction-time knob = ctranslate2 `inter_threads`; the pipeline is
  strictly sequential and never passes it (exposed on `load_whisper` for the sweep harness only, not a
  Config key — DECISIONS 2026-07-22). **`BatchedInferencePipeline` silently overrides you** (1.2.1):
  it hardcodes `condition_on_previous_text=False`, forces `max_speech_duration_s=chunk_length`,
  `hallucination_silence_threshold=None`, `max_initial_timestamp=0.0`; `word_timestamps` survives.
  Since cond=True is what buys punctuation, batching is not a drop-in speed lever here.

---

## Stage 2 — Translation: Gemma-3-12B via Ollama

**Code:** `overdub/stages/translate.py` (`_chat` = native `/api/chat` call over stdlib urllib,
`_unload` = keep_alive:0). Default since 2026-07-18: **Gemma-3-12B**, no thinking mode, no system role
(the system prompt is folded into the user turn). Qwen3-14B history retained in DECISIONS.

**VRAM (knife-edge — the tightest stage):** Q4_K_M weights 9.3 GB; KV cache ≈ 0.156 MB/token. 4K ctx
→ ~10 GB (fits), 8K → ~10.6 GB (fits), **32K → ~14.4 GB (OVERFLOWS).** On 12 GB with WDDM + display
reserve, usable is ~10–10.5 GB → **keep `num_ctx` ≤ ~8K (4K for per-segment).** Ollama preallocates KV
for the FULL num_ctx, so a large "safety" num_ctx is the danger, not the tiny prompts. Windows CUDA
sysmem fallback is ON by default → overflow = **silent 5–30× slowdown**, not a clean OOM; consider
disabling it so spills fail loudly. When Gemma is resident, free the other models around it
(co-residency budget: project CLAUDE.md).

**Gotchas:**
- **HOST FINDING (2026-07-15): use native `POST /api/chat` with `{"think": false}`, NOT `/v1` +
  `/no_think`.** Over `/v1`, an in-prompt `/no_think` is ignored on many samples, reasoning goes to a
  separate field, and `num_predict` truncates it BEFORE any answer → `message.content` is EMPTY.
  `extra_body={"think": false}` and `enable_thinking=false` on `/v1` did NOT help. Native `/api/chat`
  reliably disables thinking: ~5 s/sentence vs ~16 s, clean content. The stage uses this and dropped
  the `openai` dep. Keep a `<think>` regex strip as a defensive fallback anyway.
- **`seed` is NOT ignored**, but seed ≠ bit-exact determinism — pin `num_ctx`, expect
  "reproducible-ish". Do not assume determinism for the verify gate.
- **`keep_alive` via the request body is flaky** — prefer server-side `OLLAMA_KEEP_ALIVE`. Verify the
  daemon is serving before a run: `curl http://localhost:11434/api/tags`.

---

## Stage 3 — TTS: Silero v5_5_ru (THE engine since 2026-07-25) + ESpeech/F5 (opt-in) + whisper-small verify

**Code:** Silero `overdub/tts/silero.py` · synthesize stage + reseed-retry
`overdub/stages/synthesize.py` · opt-in F5 adapter `overdub/tts/f5.py` (spawns `f5_worker.py` in
`.venv-f5tts`, line-JSON over stdio, reader-thread timeouts, respawn-once, 3-strike
`TtsFatalError`). Assets: SETUP.md. Engine history
(Chatterbox rejected day-1, Silero v4 → F5 bake-off 2026-07-16): DECISIONS + `bakeoff/tts-research-2026-07.md`.

**Silero — THE engine since 2026-07-25 (fixed voice, CPU, no reference clip):**
- Adapter default **v5_5_ru** (audition 2026-07-19: audibly better, 12–19× faster synth than F5 on CPU
  alone); **v4_ru** kept only to reproduce pre-2026-07-19 runs. v5 REJECTS Latin script — safe because
  `text_tts` is Cyrillic-only by the normalize contract (0 Latin chars measured across the 12-video
  batch, no filter needed).
- Voices (same five in v4/v5): **eugene = primary, kseniya = backup**; xenia slightly unpleasant;
  aidar/baya off-standard accent, avoid. No cloning — every video gets the same chosen narrator voice.
  Speaking rate is a VOICE fact and the duration model keys on it (`overdub/tts/voice_rate`).
- **VRAM effectively zero** (runs on CPU; ~0.1–0.5 GB even on GPU) → whisper-small verify (~1 GB) has
  the whole Stage-3 budget. Measured RTF ~0.02–0.3 on CPU — TTS is no longer a throughput factor.
- **Deterministic** (no seed) → good for a reproducible verify gate, BUT a failed segment can't be
  reseeded, only flagged (the opt-in F5 path reseeds). **No `supports_target`** — fitting speech to
  its slot is the pipeline's job (`atempo_floor` at assembly + the open "Slot fit" item in PLAN).
- Takes SSML (`<speak> <p> <s> <prosody> <break>`) while the adapter sends plain `text=` — an open
  PLAN item ("Input prosody"), not a settled decision. Per-call text bounded ~1000 chars.
  Normalization (GPU→джи-пи-ю, x2→в два раза) still mandatory before synth. Runs at 48000 (24000 is
  audibly "plastic"). Guide: `docs/russian-tts-guide.md`.

**F5 / ESpeech — opt-in via `tts_engine = "f5"`, and what pre-2026-07-25 artifacts used.** Nothing
here describes a default run; it is kept because a revival should not re-derive it (PLAN "Deferred
— the F5 path"):
- Startup ~30 s; ~0.7–0.8 GiB VRAM; output 24 kHz mono (vocos-mel-24khz — a checkpoint fact, not a
  knob); RUAccent turbo3.1 puts stresses in-worker.
- **`nfe` is the speed knob and cost is EXACTLY linear in it** (Euler solver, one DiT forward/step).
  Do NOT pick arbitrary values: `get_epss_timesteps` (f5_tts `model/utils.py`) has tuned schedules
  only for n ∈ {5,6,7,10,12,16}; 48/32 fall through to a naive linspace. Default is **16** since
  2026-07-19 (2.16× faster per unit than 48).
- **Already fp16 and NOT compilable** (f5_tts self-casts for vocos on sm≥7; the vocoder stays fp32; no
  Triton in `.venv-f5tts`); cross-unit batching is a dead end too. Full lever ledger: DECISIONS
  2026-07-19 — read it before ANY further F5 speed work.
- **Over half of each call denoises audio that is thrown away**: F5 builds the canvas as `ref + gen`
  and slices the ref part off after (`utils_infer.py:508`). The reference is **9.164 s** against a
  ~7 s mean unit (~57% of the trajectory). Shortening it is a real lever, multiplicative with nfe —
  deferred WITH the narrator swap because it changes speaker conditioning.
- **Cost model (12 workdirs, at nfe=48):** `stage_s ≈ 34.8 + 2.295·units + 0.2176·audio_sec`; scale
  the nfe terms by `nfe/48`. Per-call floor = 0.295 s ASR round-trip + 2.00 s F5, and that 2.00 s IS
  the discarded ref canvas (`0.2176·9.164`). Fixed per-stage-SWEEP costs (stage-major amortises them
  to once per BATCH): transcribe 22.2 s load, synth 34.8 s spawn, separate 13.2 s (pure load,
  R²=0.000 vs length), verify 1.5 s. **These are measured OFF STAGE WALLS so they INCLUDE the loads**
  — use `run.json.timings.rtf_work` to compare one build against another; `rtf` is the honest total.
  (`scripts/exp_nfe_sweep.py` times synth alone with the spawn recorded separately, which is why its
  nfe 48→16 = 2.16× needs no re-check.) **All of it is F5-shaped and none of it transfers to the
  Silero path** — PLAN "Numbers to re-measure" (B).
- **Short-text class:** gen texts <10 UTF-8 bytes force local speed 0.3 and garble — mitigated
  upstream (ultra-short merge in transcribe). Duration canvas is deterministic; `plan_speed()`
  stretches to the unit's source span (floor 0.75×base) or mildly compresses (ceil 1.1×base — native
  ≥~1.3 DROPS words, atempo does the top-up). Seed-capable: reseed-retry keeps best by round-trip
  similarity.

---

## Cross-stage VRAM discipline (single 12 GB GPU)

**Code:** `overdub/pipeline.py` (session load + `unload` — MUST drop refs before `empty_cache()`, else
it is a no-op) + `overdub/stages/translate.py:_unload` (Ollama `keep_alive:0`, then VERIFY release via
`ollama ps` / nvidia-smi before loading Stage-3 models). Order: whisper → unload → Ollama →
unload + verify free → whisper-small (~1 GB) for verify; **on the shipped engine Stage 3 adds no
VRAM at all** (Silero is CPU), so the only real juggling is whisper-large ↔ Gemma. The 12 GB budget
is a budget, not a one-model-at-a-time rule (project CLAUDE.md): co-residency is allowed when the
arithmetic works — the one model that makes it tight is Gemma (~8–9 GB), so free the others around
it. With `tts_engine = "f5"` add the worker's ~0.7 GiB to that step. `separate` (htdemucs, ~3 GB)
runs standalone between assemble and mux.

---

**Sources (verification trail):** faster-whisper SYSTRAN #1257/#1230/#1086 + transcribe.py; ffmpeg
libavfilter `af_amix.c`/`af_atempo.c`; Ollama `openai.go` + #12917/#11032/#14798/#5321,
docs.ollama.com/api/openai-compatibility; snakers4/silero-models; f5_tts `utils_infer.py`/`model/utils.py`.
