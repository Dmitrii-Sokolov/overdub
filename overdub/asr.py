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


VERIFY_BEAM_SIZE = 5     # beam for the round-trip verifier. A CONSTANT, not a config key, and not
                         # cfg.whisper_beam_size: verify is what decides whether a TTS unit is
                         # flagged, so it must hold still while a transcribe-speed experiment moves
                         # the transcriber. Verify is also ~0.3 s/unit — it is not on the critical
                         # path that lever is trying to shorten. Kept as a name so the two places
                         # that use it (roundtrip_similarity, the verify-role warmup) cannot drift.


def _warm(model, beam_size: int) -> None:
    """One throwaway decode, so the first REAL video does not pay for kernel autotuning.

    Constructing a WhisperModel does not touch the GPU compute path: cuDNN/cuBLAS pick and tune
    their kernels on the first actual encode, so that cost lands inside whichever video happens
    to be first in a sweep. It is invisible in the stage wall clock (it looks like a slow video)
    and it makes the first row of every batch incomparable to the rest — which is exactly what a
    before/after optimization measurement must not have.

    Shaped like the real call on purpose — same beam size, same word_timestamps — because those
    are what select the kernels being tuned; a cheaper warmup would tune the wrong ones. VAD is
    off so the decoder cannot skip the buffer entirely and warm nothing.

    `beam_size` is threaded in rather than hardcoded for exactly that reason: the beam is one of
    the things that SELECTS the kernels being tuned, so warming at 5 for a run that decodes at 1
    tunes the wrong ones — and the mis-tune lands entirely on the first video of the sweep, i.e.
    on exactly the number an optimization measurement is trying to read.

    NEVER RAISES. A model that loaded is usable whether or not it got warmed; failing the run
    over an optimization aid would trade a real capability for a measurement.
    """
    try:
        import numpy as np

        # 1 s of near-silent noise at whisper's 16 kHz. Digital silence is a weaker warmup —
        # the decoder can short-circuit on an all-zero buffer and tune nothing.
        rng = np.random.default_rng(0)                      # fixed seed: warmup must not be a
        audio = (rng.standard_normal(16_000) * 1e-3).astype("float32")   # source of run variance
        segments, _info = model.transcribe(audio, language="en", beam_size=beam_size,
                                           word_timestamps=True, vad_filter=False)
        for _ in segments:                                  # the generator is lazy — draining it
            pass                                            # is what actually runs the decode
    except Exception as e:                                  # noqa: BLE001 — cosmetic by contract
        print(f"[warn] whisper warmup failed ({e}) — the first video of this sweep absorbs "
              f"kernel autotuning and will look slower than it is", file=sys.stderr)


def load_whisper(model: str, device: str = "cuda", compute_type: str = "float16",
                 *, beam_size: int = 5, num_workers: int = 1):
    """Load a faster-whisper WhisperModel with the Windows DLL dirs registered first, warmed.

    Warming HERE rather than in the transcribe stage is deliberate: the session caches one model
    per (name, device, compute_type, beam) and hands it to transcribe, verify and the synthesize
    reseed loop alike, so this is the one place that runs exactly once per load and no caller has
    to know the concept exists.

    `num_workers` is a CONSTRUCTION argument (ctranslate2 inter_threads) and exists here only so
    scripts/asr_probe.py can measure the cross-video-threading ceiling through the one loader
    that registers the CUDA DLL dirs and warms the model. The pipeline never passes it: a stage
    sweep is strictly sequential (pipeline.run_pipeline), so >1 worker would buy nothing. It is
    deliberately NOT a Config key and deliberately NOT in the session cache key — see
    Session.whisper."""
    add_cuda_dll_dirs()
    from faster_whisper import WhisperModel

    t0 = time.perf_counter()
    m = WhisperModel(model, device=device, compute_type=compute_type, num_workers=num_workers)
    load_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    _warm(m, beam_size)
    print(f"[asr ] {model} ({compute_type}, beam {beam_size}) loaded in {load_s:.1f}s, "
          f"warmed in {time.perf_counter() - t0:.1f}s", file=sys.stderr)
    return m


_COND_MARK = "|cond="


def asr_key(cfg, *, cond: "bool | str | None" = None) -> str:
    """Fingerprint of the decode config that PRODUCED a transcript, stamped into timings.json.

    Four elements, all of which change source text: model, resolved transcribe compute type, beam
    and condition_on_previous. `cond` defaults to the config's value and is overridden by the
    caller that knows what ACTUALLY decoded — TranscribeStage.run passes the outcome of _guard
    (which re-runs with the flag off and keeps the retry when it halves the floor ratio), repair
    passes "mixed". Stamping the INTENT instead was a defect, not a simplification: the guard is a
    per-run reaction to the audio, so two workdirs could carry one identical key over materially
    different transcripts — the exact confusion the key exists to prevent, and directly corrosive
    to the sweep it exists to protect.

    There was ZERO on-disk provenance for any of these before this key (report.json records only
    verify_model; run.json records nothing), so two runs at different beam sizes were
    indistinguishable after the fact. A string, not a hash: a mismatch message that names the two
    configs is actionable; one that names two hex digests is not.

    A mismatch is REFUSED on asr_key_core(), not on this whole string — see there.
    """
    if cond is None:
        cond = bool(cfg.whisper_condition_on_previous)
    return (f"{cfg.whisper_model}|{cfg.compute_type_for('transcribe')}"
            f"|beam={cfg.whisper_beam_size}{_COND_MARK}{cond}")


def asr_key_core(key: str) -> str:
    """The part of an asr_key that a provenance mismatch may REFUSE on: model, compute type, beam.

    cond is recorded but never refused, and it is the only one of the four that earns the
    exception on two counts. It is documented as a PER-SOURCE escape hatch (overdub.toml's
    4szRHy_CT7s NOTE, DECISIONS 2026-07-17) while asr_key is computed from a single global config
    — so using the hatch and restoring the toml left that workdir raising on every later run,
    with the printed remedy ("delete sentences.json") destroying the transcript the hatch existed
    to produce. And it is the only one the PIPELINE can change by itself at runtime (_guard), so
    a stamp of what actually decoded legitimately disagrees with a perfectly correct config.

    The other three are global config facts that scripts/asr_probe.py moves and that the
    operator must not be able to land as a no-op — warning on those is the whole point of the
    stamp, and it is untouched here.
    """
    return key.split(_COND_MARK)[0]


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
        str(wav_path), language=language, beam_size=VERIFY_BEAM_SIZE,
        vad_filter=False, condition_on_previous_text=False,
    )
    hyp = " ".join(p.text.strip() for p in parts).strip()
    hyp_n = normalize_for_compare(hyp)
    if not hyp_n:
        return 0.0, hyp, hyp_n
    return SequenceMatcher(None, ref_norm, hyp_n, autojunk=False).ratio(), hyp, hyp_n
