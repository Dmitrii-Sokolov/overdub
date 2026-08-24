# STACK.md — overdub host-findings ledger (Windows 11 + RTX 4080 Mobile, 12 GB)

Local-only YouTube→Russian dubbing. **This file is NOT a cookbook and NOT an install guide.** The
runnable code is the source of truth for HOW to call each library (pointers per stage below), and
SETUP.md owns install. This ledger holds only what is true ONLY on this host, or ONLY after being
measured / debugged here: VRAM budgets, host-specific findings, and non-obvious gotchas in the
external tools that cost real effort to discover and would be re-derived from scratch without a note.
If a fact is derivable by reading the code, it does not belong here.

Pipeline: `yt-dlp → Parakeet-TDT 0.6b v3 → Claude Sonnet (translate seam) → Silero v5_5_ru → whisper-small verify → htdemucs bed → ffmpeg (MKV)`

- **Install:** SETUP.md · **Rationale + history:** `DECISIONS.md` · **Config defaults:** `overdub/config.py`

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
- **The default YouTube player client serves 403 on URLs it just listed.** Measured 2026-08-14 on
  yt-dlp 2026.07.04: the default chain lands on `android_vr`, which lists format 251 and then 403s
  it; `ios`/`mweb` want a GVS PO token, `web`/`web_safari` return storyboards only. The stage pins
  `--extractor-args youtube:player_client=web_embedded` (`_CLIENT_ARGV`, `stages/download.py`). Two
  traps around it: `default,web_embedded` is NOT a fallback and fails MORE videos than either alone
  (multiple clients pool and re-rank their formats, and yt-dlp does not retry a second client after
  a 403 — the poisoned URL just wins the ranking again); and the `tv` client's "this video is drm
  protected" is a session-wide yt-dlp experiment (issue #12563), not a fact about your video.

---

## Stage 1a — ASR: Parakeet-TDT 0.6b v3 (the transcriber since 2026-08-06)

**Code:** worker `scripts/parakeet_worker.py` (runs in `.venv-parakeet`; VAD gate, chunking,
uncovered-speech re-read, `--serve` line protocol) · bridge `overdub/parakeet.py` ·
`TranscribeStage._run_parakeet`. Selected by `asr_engine` in `overdub/config.py`.

**VRAM: ~8.8 GB at 10-minute chunks** (host-measured 2026-08-06 over 47.9 h). The chunk size is the
only thing bounding that, and **the ceiling does not raise an error**: at 20-minute chunks every
long video pinned exactly 10 813 MB of 12 282 and WDDM began spilling into system RAM — 100% GPU
utilisation at roughly a twentieth of the throughput, a 271-minute video still running after 24
minutes. A silent 20× slowdown, not an OOM.

**Gotchas:**
- **`torch.cuda.empty_cache()` between chunks kills the batch.** NeMo's TDT greedy decoder replays a
  CUDA graph, and a graph holds the raw addresses of the buffers captured into it; handing those
  blocks back to the allocator makes the next replay read freed memory. Symptom is
  `CUDA error: an illegal memory access`, and the first failure poisons the context so every later
  video fails identically — 17/17 in 8 s, all with the same message, one real cause.
- **NeMo makes fd 1 unusable when it is a pipe.** The first `print` after `from_pretrained` dies with
  `OSError: [Errno 22] Invalid argument`. The worker's `--serve` mode duplicates the descriptor
  BEFORE loading the model and points fd 1 at stderr, so the protocol stream cannot be corrupted by
  anything the model stack writes.
- **No VAD of any kind.** faster-whisper runs Silero internally (`vad_filter=True`); NeMo does not,
  and Parakeet invents words on non-speech (110, 32 and 6 words on three silent videos, 2026-08-06).
  The gate is the worker's job and is not optional.
- **It drops real speech at window boundaries** — 20 spans over 146 videos, largest 41 s. Not
  deafness: a re-read of the same samples in a different window returns the text, with MORE words
  than whisper had there. Hence the worker's coverage check.
- **Timestamps land on an 80 ms grid** (10 ms features × 8 subsampling), against whisper's ~20 ms.
  Anything keyed on sub-80 ms word durations is meaningless here — `floor_run_ratio` measured 0.0 on
  all 145 videos, which is why the alignment guard is not wired into this path.
- **Language is auto-detected and cannot be forced.** Measured 0.0 non-Latin output across 145
  videos, so the risk did not materialise on this corpus — but there is no `language="en"` to set.
- **`nemo_toolkit[asr]` pins numpy below the pipeline's** (2.5.1 → 2.4.6) and resolves 137 packages.
  This is the whole reason for the third venv. Windows-clean otherwise: only `sox`,
  `kaldi-python-io` and `wget` arrive as sdists and all three are pure Python; `pynini` belongs to
  `nemo_text_processing` and is not pulled by the `[asr]` extra.

---

## Stage 1b — ASR: faster-whisper large-v3 (fallback) + small (verify)

**Code:** transcribe `overdub/stages/transcribe.py` (`transcribe_words` — the shared body used by
both the stage and `--repair-asr`, so they cannot drift in beam/VAD/word_timestamps;
`TranscribeStage._guard` = the automatic cond retry) · verify `overdub/stages/verify.py` · model load
+ caching `overdub/asr.py` (`load_whisper`, `asr_key`) and `overdub/pipeline.py` (session reuse).
Both ASR roles are configured in `overdub/config.py`. Reached by `asr_engine = "whisper"`; the
verify round-trip uses whisper-small regardless of that setting.

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
  cells `work-exp/asr-probe-int8/`.
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

## Stage 2 — Translation (at the seam, not in-process)

Translation happens at the translate seam: sub-agents write `work/<id>/translation.json` and the
pipeline resumes from it (`scripts/build_translation.py` owns the contract; runbook in README
"Running", route B). **No model runs on this host for it, so there is nothing to record here** — no
VRAM budget, no loader gotcha, no local service to keep alive. The prompt rules and the artifact
schema live in `.claude/skills/overdub-sonnet-batch/references/translate-contract.md`; the gate that
validates a draft is `overdub/stages/translate._is_bad`.

---

## Stage 3 — TTS: Silero v5_5_ru + whisper-small verify

**Code:** Silero `overdub/tts/silero.py` · synthesize stage + reseed-retry
`overdub/stages/synthesize.py`. Engine history and the audition that picked it: DECISIONS.

**Silero — THE engine (fixed voice, CPU, no reference clip):**
- Adapter default **v5_5_ru** (audition 2026-07-19: audibly better, and synthesis stopped being a
  throughput factor); **v4_ru** kept only to reproduce pre-2026-07-19 runs. v5 REJECTS Latin script —
  safe because `text_tts` is Cyrillic-only by the normalize contract (0 Latin chars measured across
  the 12-video batch, no filter needed).
- Voices (same five in v4/v5): **eugene = primary, kseniya = backup**; xenia slightly unpleasant;
  aidar/baya off-standard accent, avoid. No cloning — every video gets the same chosen narrator voice.
  Speaking rate is a VOICE fact and the duration model keys on it (`overdub.tts.voice_rate`).
- **VRAM effectively zero** (runs on CPU; ~0.1–0.5 GB even on GPU) → whisper-small verify (~1 GB) has
  the whole Stage-3 budget. Measured RTF ~0.02–0.3 on CPU — TTS is no longer a throughput factor.
- **Deterministic** (no seed) → good for a reproducible verify gate, BUT a failed segment can't be
  reseeded, only flagged. **No `supports_target`** — fitting speech to its slot is the pipeline's job
  (`atempo_floor` at assembly + the open `tasks/slot-fit.md`).
- Takes SSML (`<speak> <p> <s> <prosody> <break>`) while the adapter sends plain `text=` — an open
  BACKLOG item (`tasks/input-prosody.md`), not a settled decision. **Except `<break>`, which is NOT open:
  `silero.build_ssml` is built and wired (`supports_breaks`, gaps from `synthesize.build_units`)
  but ships OFF — `silero_ssml_breaks = False`, rejected by ear 2026-07-25 as the right mechanism
  on the wrong problem.** Read that config comment before re-proposing pause markup; the engine
  constructor's own `breaks=True` default is not what ships, `build_engine` passes the config key.
  Per-call text bounded ~1000 chars.
  Normalization (GPU→джи-пи-ю, x2→в два раза) still mandatory before synth. Runs at 48000 (24000 is
  audibly "plastic"). Guide: `docs/russian-tts-guide.md`.

---

## Stage 4 — Separation: htdemucs (the `bed` mix)

**Code:** `overdub/stages/separate.py`, driven as a `.venv-demucs` CLI subprocess. ~3 GB VRAM,
standalone between assemble and mux.

**The wall here is HOST RAM, not VRAM, and it scales with DURATION.** htdemucs allocates its output
tensor for all FOUR stems over the whole track even under `--two-stems` — `duration × 44100 × 2ch ×
4src × 4B` = 1.41 MB per second of source, plus the input tensor and the copies around it. Measured
2026-08-11: a 7.90 h source asked for **37.4 GiB in one allocation** and died on a 63.7 GB host,
while 6.95 h went through. Hence `separate_chunk_sec = 3600`, which caps that term at ~5.1 GB
regardless of length — the point is that the ceiling stops being a function of duration.
`separate_overlap_sec = 5.0` is extracted on both sides of every cut and blended back as a weighted
average, never a shortening crossfade: two independently separated chunks disagree slightly at a
hard seam and butt-joining them clicks, but the bed must stay sample-aligned with the picture.

---

## Cross-stage VRAM discipline (single 12 GB GPU)

**Code:** `overdub/pipeline.py` (session load + `unload` — MUST drop refs before `empty_cache()`, else
it is a no-op). Order: whisper-large → unload → whisper-small (~1 GB) for verify; **Stage 3 adds no
VRAM at all** (Silero is CPU), so a pass never holds two heavy models at once and the 12 GB budget is
never tight. `separate` (htdemucs, ~3 GB) runs standalone between assemble and mux.

---

**Sources (verification trail):** faster-whisper SYSTRAN #1257/#1230/#1086 + transcribe.py; ffmpeg
libavfilter `af_amix.c`/`af_atempo.c`; snakers4/silero-models.
