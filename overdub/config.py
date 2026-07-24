"""Pipeline configuration. Flat TOML (overdub.toml) overrides the defaults below."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    # work dir
    work_root: Path = Path("work")
    # export — title-named final MKVs: "<title> [<video id>].mkv" (hardlink/copy of output.mkv)
    output_dir: Path = Path("out")

    # language (fixed EN->RU for v1)
    source_lang: str = "en"
    target_lang: str = "ru"

    # STT — faster-whisper
    whisper_model: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    whisper_beam_size: int = 5                   # decode beam for the TRANSCRIBE role (the stage
                                                 # AND --repair-asr, which share transcribe_words
                                                 # on purpose). Candidate speed lever for the
                                                 # "Transcribe speed" roadmap item: 907 s per pass
                                                 # over the 6-video queue is 79% of a scout pass.
                                                 # NOT a free dial — beam width is what buys the
                                                 # transcript its second opinion on ambiguous
                                                 # audio, and this repo has already watched a
                                                 # narrower-context decode turn "Claude" into
                                                 # "Cloud" on clean, clearly enunciated speech
                                                 # (DECISIONS 2026-07-20). Move it only on
                                                 # evidence from scripts/asr_probe.py, never
                                                 # on a single run: whisper's temperature fallback
                                                 # SAMPLES, so the same audio at the same settings
                                                 # comes back different (see the 5-vs-6-run story
                                                 # under transcribe_floor_run_max below).
                                                 # Changing it changes SOURCE TEXT → it is part of
                                                 # asr_key (overdub/asr.py) and a changed key
                                                 # trips the transcribe provenance guard.
    whisper_condition_on_previous: bool = True   # feed prior text as context so whisper
                                                 # PUNCTUATES properly. False left 60-206 s
                                                 # terminator-free blocks that the resegmenter
                                                 # bisected mid-phrase (the "period mid-sentence"
                                                 # class, DECISIONS 2026-07-17). Measured safe:
                                                 # no repetition-loop on the music video. Flip
                                                 # to False only if a source makes whisper loop.
                                                 # Recorded in asr_key (as what ACTUALLY decoded,
                                                 # so the transcribe guard's own retry shows as
                                                 # cond=False) but NEVER refused on: it is a
                                                 # per-source hatch under a global config and the
                                                 # pipeline sets it itself — see asr.asr_key_core
    transcribe_floor_run_max: float = 0.085      # share of words landing on the MIN_WORD_DUR
                                                 # floor above which THIS RUN's transcript is
                                                 # treated as alignment-collapsed and re-run with
                                                 # context feedback OFF (transcribe.py guard).
                                                 # 0.0 disables.
                                                 #
                                                 # PROVISIONAL, and weaker than a threshold should
                                                 # be. Whisper's temperature fallback samples, so
                                                 # the SAME audio varies run to run and this scores
                                                 # the RUN, not the video. First 5-run sample
                                                 # (2026-07-19) looked separable — severe
                                                 # 9.33-11.38%, mid 3.82-7.52%, clean 0.00-7.46% —
                                                 # but a second independent sample the same day put
                                                 # the MID video at 15.82%, above the severe one's
                                                 # entire range. The populations OVERLAP; there is
                                                 # no clean gap to sit in. 0.085 is kept because
                                                 # the severe case has never once fallen below it
                                                 # (catastrophe insurance holds), while borderline
                                                 # detection is knowingly unreliable. Recalibrate
                                                 # from the asr.floor_ratio series run_report now
                                                 # accumulates — not from another hand-run probe.

    # --- --repair-asr: isolated-window re-ASR (DECISIONS 2026-07-19) ---
    # Neither key enters synth_key: they change SOURCE TEXT, which is upstream of synthesis
    # and already covered by the downstream delete set. Do not "fix" that.
    repair_window_min_sec: float = 8.0    # A collapsed sentence has a BOGUS span (measured:
                                          # 66 chars in 0.94 s; 0.28 s on RyvXxApfHkk#11), so
                                          # clipping its own span yields no usable audio. The
                                          # window is widened outward by whole SENTENCES until
                                          # its audio span reaches this length. 8-18 s is the
                                          # band all 7 manual repairs worked in — a reported
                                          # range, not a calibrated threshold. Do not cite it
                                          # as measured.
                                          # WHAT MOVING IT COSTS (measured 2026-07-20, ear-checked
                                          # — DECISIONS): every second of widening pulls MORE
                                          # unflagged neighbours into the replaced range, and the
                                          # window's reading overwrites them. That cut both ways
                                          # in one run: it corrected a sentence the human got
                                          # wrong (DmgujoZ1mmk), and it is the mechanism by which
                                          # a clean neighbour CAN be degraded. So: RAISING it
                                          # buys the clip more audio to decode and widens the
                                          # blast radius; LOWERING it below ~8 s starves the clip
                                          # of the context that makes the re-ASR trustworthy at
                                          # all. Not a free dial in either direction — that is
                                          # the whole reason it is a key and not a constant.
                                          # There is NO matching max key: `repair_window_max_sec`
                                          # existed until 2026-07-20, when it was measured to be
                                          # inert — see repair.widen's docstring. A window that
                                          # reaches min_sec by swallowing one long neighbour, or
                                          # a merged window, has no upper bound, and that is
                                          # correct: reaching min_sec is what makes the clip
                                          # transcribable. The actual span is always printed.

    # translation — Gemma-3-12B via Ollama native /api/chat (see stages/translate.py)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:12b"
    num_ctx: int = 4096
    context_window: int = 4          # previous OK sentence pairs fed as rolling context
    ollama_timeout_s: float = 120.0
    translate_temperature: float = 0.2
    translate_top_p: float = 0.9
    translate_seed: int = 42
    translate_max_retries: int = 3
    translate_max_tokens: int = 512  # ramble/echo guard
    translate_max_len_ratio: float = 3.0   # runaway guard: text_ru chars vs source
    latin_ratio_max: float = 0.30    # english-echo detector (Latin fraction of alpha chars)
    translate_context_char_cap: int = 2400  # drop oldest ctx pairs beyond this (KV knife-edge)
    translate_unload: bool = True    # POST keep_alive:0 after the stage to free VRAM

    # TTS — engine selection + seed policy
    tts_engine: str = "f5"           # "f5" (production, Phase-3 ear check 2026-07-16) | "silero" (fallback)
    tts_voice: str = "eugene"        # silero-only
    silero_model: str = "v5_5_ru"    # silero-only release id via torch.hub. v4_ru (~38 MB) was
                                     # the 2026-07-15 bake-off entrant BY MISTAKE — v5_5_ru
                                     # (~139 MB) was already current and is audibly better; v4 is
                                     # superseded, keep it only to reproduce old runs. Same five
                                     # speakers either way (aidar, baya, kseniya, eugene, xenia);
                                     # best by ear = kseniya, eugene. v5 is Cyrillic-only — safe
                                     # because text_tts is Cyrillic by contract (see tts/silero.py).
                                     # Audio-affecting → it is part of synth_key.
    tts_sample_rate: int = 48000     # silero-only (F5 sr is engine-owned: 24000)
    tts_seed: int = 42               # base seed (seed-capable engines); retries use seed+attempt
    tts_max_retries: int = 3         # reseed attempts after the first try (seed-capable engines)

    # TTS — F5/ESpeech (worker process in .venv-f5tts; see overdub/tts/f5.py)
    f5_python: Path = Path(".venv-f5tts/Scripts/python.exe")
    f5_ckpt: Path = Path("models/espeech-rlv2/espeech_tts_rlv2.pt")
    f5_vocab: Path = Path("models/espeech-rlv2/vocab.txt")
    f5_ref_audio: Path = Path("models/refs/ref_espeech_demo.wav")
    f5_ref_text: Path = Path("models/refs/ref_espeech_demo.txt")
    f5_nfe: int = 16                 # denoising steps. 16, not 48 (2026-07-19, ear-checked on a
                                     # full video): cost is EXACTLY linear in nfe (Euler, one DiT
                                     # forward per step), and 16 is one of the step counts F5's
                                     # get_epss_timesteps has a TUNED schedule for (5,6,7,10,12,16)
                                     # — 48 and 32 both fall through to a naive linspace, so the
                                     # once-planned 48→32 was the one step down that buys no help
                                     # from the library. Measured 2.16× per unit over 40 real units
                                     # × 4 step counts; 12 adds only 6% more and leaves the tuned
                                     # grid's edge. Metrics could NOT sign this off (round-trip sim
                                     # is saturated: corpus median 0.995, zero units under the 0.9
                                     # gate) — the ear did. Audio-affecting → part of synth_key.
    f5_speed: float = 1.0            # base narrator pace (narrator calibration, DECISIONS)
    f5_speed_floor: float = 0.75     # max stretch: min per-unit speed as a MULTIPLIER of
                                     # f5_speed (slot-fill; 1.0 disables stretching)
    f5_speed_ceil: float = 1.1       # max native compression multiplier before atempo tops
                                     # up. Ear 2026-07-16: native ≥~1.3 DROPS words mid-word
                                     # (atempo never does) — keep ≲1.15; 1.0 disables

    # dead-air / mix (see DECISIONS 2026-07-16 dead-air entry + 2026-07-17 ear verdict)
    group_gap_max: float = 0.4       # join adjacent sentences into one render unit when the
                                     # inter-sentence gap ≤ this (s); 0.0 disables grouping
    dub_mix: str = "bed"             # "replace" | "duck" | "bed" (no-vocals stem at original
                                     # level under the dub — production default by ear)
    demucs_python: Path = Path(".venv-demucs/Scripts/python.exe")  # bed mode only

    # verification — whisper-small round-trip
    verify_model: str = "small"
    verify_compute_type: str = "float16"   # DELIBERATELY NOT inherited from whisper_compute_type.
                                           # The round-trip verifier is the pipeline's MEASURING
                                           # INSTRUMENT: it decides which units are flagged and
                                           # which pass similarity_threshold. An instrument that
                                           # moves with the thing it measures cannot detect a
                                           # regression in it — flipping the transcriber to
                                           # int8_float16 would shift every similarity score and
                                           # the flag counts with it, and a transcribe-speed
                                           # experiment would read its own measurement error as a
                                           # result. Set this only to move the verifier ON PURPOSE.
                                           # Today's value equals whisper_compute_type, so an
                                           # unchanged overdub.toml resolves both roles identically
                                           # and the session cache keys are what they were before
                                           # the split.
    similarity_threshold: float = 0.9      # unit-level gate (0.8 → 0.9, 2026-07-17: units are
                                           # long joined strings that dilute local defects —
                                           # the 17:02 word-drop scored 0.836 and passed 0.8)
    similarity_threshold_compressed: float = 0.9   # stricter gate for natively compressed
                                                   # units (word-drop risk; unit_sim_threshold)

    # completeness — cheap deterministic loss check (stages/verify.py + completeness.py),
    # non-blocking triage only. len(text_ru)/len(src_en) below this AND len(src_en) >= 30 chars
    # -> length_short. 0.45 sits under the natural RU-compression floor (~0.46): validated
    # 0/427 false positives on both the Gemma and near-clean Sonnet samples; 0.50 would false-
    # flag a legit condensed sentence. Weak signal, redundant with the precise num/neg/entity
    # detectors — kept conservative to prefer a miss over a false alarm.
    completeness_len_ratio_min: float = 0.45

    def compute_type_for(self, role: str) -> str:
        """Resolved CTranslate2 compute type for an ASR ROLE, not for a model name.

        Roles, not names, because verify_model is a config key: someone pointing it at large-v3
        must not silently inherit the transcriber's experimental compute type. Raises on an
        unknown role — the role set is a closed 2-element enum with 4 call sites, so a typo is a
        programming error, not a runtime scenario.
        """
        if role == "transcribe":
            return self.whisper_compute_type
        if role == "verify":
            return self.verify_compute_type
        raise ValueError(f"unknown ASR role: {role!r}")

    @classmethod
    def load(cls, path: Path | None) -> "Config":
        cfg = cls()
        if path is None or not Path(path).exists():
            return cfg
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        for key, value in data.items():
            if not hasattr(cfg, key):
                print(f"[config] unknown key ignored: {key}")
                continue
            current = getattr(cfg, key)
            setattr(cfg, key, Path(value) if isinstance(current, Path) else value)
        return cfg
