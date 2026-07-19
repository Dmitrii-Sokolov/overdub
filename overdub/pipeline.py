"""Stage runner: sequential per video, resumable, skip-if-artifact-exists.

Every stage is artifact-driven — `done(ctx)` checks whether its output already
exists so a re-run resumes instead of redoing work. Stages can be run in
isolation via the CLI `--only` flag.
"""

from __future__ import annotations

import gc
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from . import runreport
from .config import Config
from .workdir import WorkDir

STOP_NAME = "STOP"


class StopRequested(Exception):
    """STOP file seen at a checkpoint; str(exc) says where ("before stage 'x'")."""


def check_stop(work_root: Path, where: str) -> None:
    """O(1) stop-switch checkpoint: if work_root/STOP exists, consume it and raise.
    Consuming at honor time means a plain re-run resumes; the stale-file sweep at
    run start (cli.main) is the safety net for a crash between detect and unlink."""
    stop = work_root / STOP_NAME
    if not stop.exists():
        return
    try:
        stop.unlink()
    except OSError:
        print(f"[warn] could not remove {stop} — remove it manually")
    raise StopRequested(where)


class Session:
    """Loaded models shared across the videos of ONE stage sweep.

    Two invariants make it safe:

    GET-OR-CREATE AT THE USE SITE, never eagerly at stage start — synthesize must still
    spawn no F5 worker at all for a batch whose wavs are all reusable (its `if need:`
    gate).

    LIFETIME IS EXACTLY ONE STAGE SWEEP. Peak VRAM stays the MAX over models instead of
    their sum, which is what lets the local translate route hand Gemma the whole budget
    with no parking or eviction policy. For a single video a "sweep" is one video, i.e.
    exactly the per-stage teardown the stages used to do in their own finally blocks.
    """

    def __init__(self) -> None:
        self._cache: dict = {}

    def get(self, key, factory):
        if key not in self._cache:
            self._cache[key] = factory()
        return self._cache[key]

    def whisper(self, cfg: Config, model: str):
        """faster-whisper keyed by every knob load_whisper takes. transcribe asks for
        cfg.whisper_model; verify AND synthesize's reseed verifier both ask for
        cfg.verify_model — inside one stage those two share one instance. Safe to share:
        no concurrency (the sweep is strictly sequential), CTranslate2 is stateless, and
        roundtrip_similarity drains its lazy generator before returning (asr.py)."""
        from .asr import load_whisper

        return self.get(("whisper", model, cfg.whisper_device, cfg.whisper_compute_type),
                        lambda: load_whisper(model, cfg.whisper_device, cfg.whisper_compute_type))

    def tts_engine(self, cfg: Config):
        from .tts import build_engine

        return self.get(_tts_key(cfg), lambda: build_engine(cfg))

    def clear(self) -> None:
        """Release everything. Never raises: a teardown failure PRINTS and must not mask
        an exception already unwinding through the caller."""
        if not self._cache:      # nothing was loaded (download, assemble, mux, an all-skip
            return               # resume): don't drag torch into a run that never used it
        for key, obj in list(self._cache.items()):
            self._cache.pop(key, None)
            close = getattr(obj, "close", None)         # whisper models have none — the
            if close is not None:                       # ref-drop + gc below is their release
                try:
                    close()
                except Exception as e:
                    print(f"[warn] session: closing {key[0]} failed ({e}) — continuing",
                          file=sys.stderr)
        gc.collect()
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:
            pass


def _tts_key(cfg: Config):
    """TTS engine cache key. synth_key is the project's canonical "what changes rendered
    audio" fingerprint and carries an explicit INVARIANT (tts/__init__.py) that every new
    audio-affecting knob enters it — reusing it means this key can never silently fall
    behind. It is deliberately WIDER than worker identity (seed/speed/floor/ceil are
    per-REQUEST arguments, not worker argv), and that costs nothing: cfg is loaded once
    per process, so the key is constant across a batch. f5_python is appended because
    synth_key does NOT cover it and a different venv is a different worker process;
    resolved so two spellings of one interpreter share an entry. Recomputed per video on
    purpose (~1 ms): it hashes the ref-audio BYTES, the only thing that would notice a
    narrator reference rewritten on disk mid-batch."""
    from .tts import synth_key

    if cfg.tts_engine != "f5":
        return ("tts", synth_key(cfg))
    return ("tts", synth_key(cfg), str(Path(cfg.f5_python).resolve()))


@dataclass
class Context:
    url: str
    cfg: Config
    work: WorkDir
    session: Session = field(default_factory=Session)


class Stage(Protocol):
    name: str

    def done(self, ctx: Context) -> bool: ...

    def run(self, ctx: Context) -> None: ...


def run_pipeline(
    ctx: Context,
    stages: list[Stage],
    *,
    force: bool = False,
    only: set[str] | None = None,
    owns_session: bool = True,
) -> None:
    for st in stages:
        # before the only/done filters: a stop halts at the next stage boundary even
        # through a run of [skip] lines (predictability beats racing to finish)
        check_stop(ctx.cfg.work_root, f"before stage '{st.name}'")
        if only is not None and st.name not in only:
            continue
        if not force and st.done(ctx):
            print(f"[skip] {st.name}  (artifact exists)")
            continue
        print(f"[run ] {st.name}")
        t0 = time.perf_counter()
        try:
            st.run(ctx)
            elapsed = time.perf_counter() - t0
            print(f"[ok  ] {st.name}  {elapsed:.1f}s")
            # persist this stage's wall-clock (only stages that ACTUALLY ran — the [skip] and
            # --only-excluded branches above continue before here, so a resumed/partial run keeps
            # every other stage's last real timing). Best-effort: never raises into the runner.
            runreport.record_stage_timing(ctx.work, st.name, elapsed)
        finally:
            # UNCONDITIONAL: teardown used to live in each stage's own `finally`, so it ran on
            # the raising path too. A stage that raises can leave a LIVE F5 worker — the
            # ok:false branch (f5.py) does NOT kill the process, and the pump thread pins the
            # Popen, so nothing collects it: the orphan holds ~0.8 GiB until this process dies.
            # Same for a loaded Gemma after a translate failure. Timing stays INSIDE the try so
            # only stages that actually completed are recorded.
            if owns_session:
                # a model's lifetime is ONE stage sweep. An owning caller runs one video per
                # sweep, so clearing here reproduces the old per-stage teardown exactly; the
                # stage-major driver passes owns_session=False and clears after ITS sweep.
                ctx.session.clear()
