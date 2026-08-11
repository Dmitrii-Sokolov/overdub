"""Pipeline configuration. Flat TOML (overdub.toml) overrides the defaults below."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    # work dir
    work_root: Path = Path("work")
    download_concurrency: int = 3    # videos fetched at once in the batch PREFETCH (1 = off, the
                                     # pre-2026-08-06 behaviour). download is the only stage that
                                     # holds no GPU and is bound by the network, and on the
                                     # 2026-08-06 baseline it was 13.3% of machine time — 323.8 s
                                     # of strictly serial fetching whose longest single video was
                                     # 82 s, i.e. most of it was the queue and not the transfer.
                                     # Kept LOW on purpose: stage-major already delivers a queue to
                                     # YouTube as one burst, and 2026-07-20 lost two videos of a
                                     # 12-video batch to transient 403 / "unavailable" that both
                                     # succeeded on a plain re-run. Widening this makes the burst
                                     # burstier, so the knob buys wall-clock with a rate-limit risk
                                     # that has never been measured above 3.
    # export — title-named final MKVs: "<title> [<video id>].mkv" (hardlink/copy of output.mkv)
    output_dir: Path = Path("out")

    # language (fixed EN->RU for v1)
    source_lang: str = "en"
    target_lang: str = "ru"

    # STT — engine selection
    asr_engine: str = "parakeet"     # "parakeet" | "whisper". Parakeet-TDT 0.6b v3 runs in
                                     # .venv-parakeet as a subprocess worker (overdub/parakeet.py),
                                     # whisper large-v3 in-process via faster-whisper.
                                     # Measured 2026-08-06 over 47.9 h / 165 videos: RTF 0.0034 vs
                                     # 0.087 (~25x), and transcribe is 30.5% of pipeline wall clock
                                     # across 375 recorded runs, so the batch gets ~1.4x overall.
                                     # Text quality is a WASH on the fixture (1.56% vs 1.6% WER
                                     # once measurement artefacts are removed) — the reason to
                                     # switch is that whisper's repetition loops disappear: in the
                                     # 8 hand-repaired fixture windows whisper scores 23.3% WER and
                                     # Parakeet 4.2%. What it costs is proper nouns (6 Claude ->
                                     # Cloud in one fixture video) and a hard dependency on the VAD
                                     # gate, without which it invents words on non-speech.
                                     # Changing this changes SOURCE TEXT -> it is part of asr_key.
    parakeet_python: Path = Path(".venv-parakeet/Scripts/python.exe")
    parakeet_vad: bool = True        # NEVER ship this off. Without the gate three silent videos in
                                     # the 165-video corpus came back with 110, 32 and 6 invented
                                     # words (2026-08-06); with it, zero, and no healthy video was
                                     # gated. It also removed all 7 tail truncations and cut
                                     # uncovered speech from 1246 words to 816. The flag exists to
                                     # REPRODUCE that measurement, not to trade quality for speed.

    # STT — faster-whisper (asr_engine = "whisper"; also the verify round-trip either way)
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

    # translation — the gate applied to a draft written at the seam (stages/translate.py::_is_bad,
    # imported by scripts/build_translation.py). No model runs in-process.
    translate_max_len_ratio: float = 3.0   # runaway guard: text_ru chars vs source
    latin_ratio_max: float = 0.30    # english-echo detector (Latin fraction of alpha chars)

    # TTS — engine selection + seed policy
    tts_engine: str = "silero"       # THE engine since 2026-07-25 (user decision, DECISIONS):
                                     # speed + hardware cost, quality difference accepted as a
                                     # trade.
    tts_voice: str = "eugene"        # silero-only
    silero_model: str = "v5_5_ru"    # silero-only release id via torch.hub. v4_ru (~38 MB) was
                                     # the 2026-07-15 bake-off entrant BY MISTAKE — v5_5_ru
                                     # (~139 MB) was already current and is audibly better; v4 is
                                     # superseded, keep it only to reproduce old runs. Same five
                                     # speakers either way (aidar, baya, kseniya, eugene, xenia);
                                     # best by ear = kseniya, eugene. v5 is Cyrillic-only — safe
                                     # because text_tts is Cyrillic by contract (see tts/silero.py).
                                     # Audio-affecting → it is part of synth_key.
    tts_sample_rate: int = 48000     # silero-only
    silero_ssml_breaks: bool = False  # silero v5 only: put the ORIGINAL inter-sentence pauses
                                     # back inside a grouped unit as SSML <break>. OFF by ear
                                     # (2026-07-25): indistinguishable from no markup, because
                                     # it fixes the wrong thing. The holes in the dub are NOT
                                     # swallowed inter-sentence pauses — forensics on the 5:15
                                     # hole found the source speech continuous (largest word
                                     # gap 0.95 s) and the hole made by assembly: unit [61,62]
                                     # got a 15.76 s slot, spoke for 10.66 s, and the leftover
                                     # 5.10 s is digital silence. <break> put back 0.44 s of
                                     # that, i.e. 8%, while ADDING pauses where the speaker had
                                     # none. The real lever is translation length + atempo<1.
                                     # Kept, not deleted: correct mechanism, wrong problem. This
                                     # is the ONLY copy of these forensics — PLAN "Input prosody"
                                     # and docs/russian-tts-guide.md both point here instead of
                                     # restating them, so do not trim it away.
                                     # Audio-affecting → part of synth_key.
    tts_seed: int = 42               # base seed (seed-capable engines); retries use seed+attempt
    tts_max_retries: int = 3         # reseed attempts after the first try (seed-capable engines)

    # dead-air / mix (see DECISIONS 2026-07-16 dead-air entry + 2026-07-17 ear verdict)
    group_gap_max: float = 1.2       # join adjacent sentences into one render unit when the
                                     # inter-sentence gap ≤ this (s); 0.0 disables grouping.
                                     # 0.4/12/300 → 1.2/20/600 by ear on 8zJlKmgMT44
                                     # (2026-07-25): 1.32 → 2.57 sentences per unit, ~7 → ~14 s
                                     # of speech per contour. The 4.19/unit arm was also better
                                     # than baseline but barely different from this one, and it
                                     # doubles the sync cost (p90 swallowed silence 2.62 s vs
                                     # 1.28), so the middle arm wins. Costs nothing in time:
                                     # synth 22.8/28.2/25.3 s and verify 45.8/58.2/56.3 s across
                                     # the three arms are inside the run-to-run noise (two
                                     # identical baseline verify passes read 84.3 and 45.8).
    group_span_max: float = 20.0     # unit source-span cap (s) and joined-text cap. Both were
    group_chars_max: int = 600       # constants shaped for the RETIRED F5 engine ("~10 s ref + gen
                                     # inside F5's trained ≤30 s regime"), re-cut by ear to
                                     # 1.2/20/600 and never re-derived for Silero (DECISIONS
                                     # 2026-07-25, "Silero becomes the ONLY engine"). They —
                                     # not group_gap_max — are what actually binds grouping:
                                     # measured over 37 videos / 5401 sentences, raising gap
                                     # 0.4→1.2 alone moves 1.40→1.57 sentences per unit because
                                     # the refusals just migrate to span (1822→2997). Knobs, not
                                     # constants, so a grouping A/B is a toml away. Grouping is
                                     # WARN-only on change, like group_gap_max — regrouping
                                     # needs --force (see synthesize.done).
    atempo_floor: float = 0.75       # SLOWEST atempo applied to an under-filled unit (1.0 = off,
                                     # i.e. speed-up only, which is what shipped before
                                     # 2026-07-25). Silero has no supports_target, so nothing
                                     # stretches speech to its slot and the hole is left as
                                     # digital silence: measured fill median 0.71 on
                                     # 8zJlKmgMT44, 283 s of a 1058 s dub.
                                     # 0.75 is an EAR verdict on a tempo ladder (one phrase at
                                     # 1.0/0.8/0.65/0.5 back to back, three units, 2026-07-25):
                                     # degradation starts at 0.65, so the default sits half a
                                     # step above it rather than on the edge — other voices and
                                     # material will eat some of that margin. Effect measured on
                                     # 8zJlKmgMT44: slot silence 283→84 s (−70%), and 42 of 69
                                     # units are pinned here (56 would be at 0.85, 29 at 0.70).
                                     # Applies AFTER verify like every other atempo, so a
                                     # stretched unit is still verified on raw audio.
    slot_fill_target: float = 1.0    # fraction of the slot the dub aims to fill: what the
                                     # translator is asked to write toward AND what atempo
                                     # stretches toward. <1.0 deliberately leaves air between
                                     # units; 1.0 fills the slot and lets the inter-unit gap be
                                     # the only pause. Ear knob — the arithmetic is indifferent.
    dub_mix: str = "bed"             # "replace" | "duck" | "bed" (no-vocals stem at original
                                     # level under the dub — production default by ear)
    dub_lowpass_hz: int = 11000      # low-pass the FINISHED dub track (0 = off; ear check
                                     # 2026-07-25). Silero's vocoder lays a broadband hiss
                                     # across 8-20 kHz that tracks the speech instead of
                                     # sitting under it, so no denoiser (afftdn/arnndn) can
                                     # reach it — cutting the top does, at no intelligibility
                                     # cost. NOT audio-affecting in the synth sense: it lands
                                     # after verify, so it stays OUT of synth_key and never
                                     # forces a resynthesis. Auto-skipped when the cutoff is
                                     # not comfortably below Nyquist — a 24 kHz track has
                                     # nothing up there to cut (see assemble.effective_lowpass).
    demucs_python: Path = Path(".venv-demucs/Scripts/python.exe")  # bed mode only
    separate_chunk_sec: int = 3600   # 0 = never chunk. htdemucs allocates its OUTPUT tensor for
                                     # all FOUR stems over the whole track even under
                                     # --two-stems, i.e. duration * 44100 * 2ch * 4src * 4B =
                                     # 1.41 MB per second of source, plus the input tensor and
                                     # the copies around it. Measured 2026-08-11: 7.90 h asked
                                     # for 37.4 GiB in one allocation and died on a 63.7 GB
                                     # host; 6.95 h went through. An hour caps that term at
                                     # 5.1 GB no matter how long the video is, which is the
                                     # point — the ceiling stops being a function of duration.
    separate_overlap_sec: float = 5.0  # extracted on BOTH sides of every cut and blended back.
                                     # Two independently separated chunks do not agree exactly
                                     # at a hard seam, so butt-joining them clicks. The blend is
                                     # a weighted average, never a shortening crossfade: the bed
                                     # has to stay sample-aligned with the picture.

    # verification — whisper-small round-trip
    verify_roundtrip: bool = False  # OFF since 2026-08-06 (DECISIONS). Measured over 123 videos /
                                    # 5852 units: 24 flags = 0.41%, and reading all 24 by hand,
                                    # TWO were real dub defects (an unspoken sentence, a held
                                    # vowel). The rest were the metric failing on 1-3 word units
                                    # and the Latin-spelling class, which pronounce owns. ~0.94 h
                                    # of GPU per 123-video batch for that.
                                    # WHAT THIS TURNS OFF is the only detector that HEARS the
                                    # output; everything else in the pipeline judges text. So the
                                    # 0.41% is a statement that Silero is healthy TODAY, not that
                                    # the check is worthless — turn it back on to re-measure after
                                    # any engine, voice or normalization change, and read
                                    # `verify.roundtrip` in run.json before quoting a flag count.
                                    # NOT the stale-wav net: synthesize re-renders a unit whose
                                    # joined text_tts changed, so a re-translation still forces
                                    # resynthesis with this off (stages/synthesize.py, done()).
                                    # The completeness text check is UNAFFECTED and still runs —
                                    # it costs no GPU and lives in the same stage by accident of
                                    # placement, not by dependency.
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
    # -> length_short. 0.45 sits under the natural RU-compression floor (~0.46): validated 0/854
    # false positives across two 427-sentence samples of different translation quality (DECISIONS
    # 2026-07-19, the completeness A+B entry); 0.50 would false-flag a legit
    # condensed sentence. Weak signal, redundant with the precise num/neg/entity detectors —
    # kept conservative to prefer a miss over a false alarm.
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
