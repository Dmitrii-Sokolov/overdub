"""F5-TTS (ESpeech RL-V2) engine — drives a persistent worker in .venv-f5tts.

The F5 stack is dependency-incompatible with the pipeline venv (torch 2.8 vs 2.11,
numpy downgrade, torchcodec ABI — see DECISIONS 2026-07-16), so synthesis runs in a
child process spawned from `.venv-f5tts` speaking line-JSON over stdio (see
f5_worker.py for the protocol). One worker per engine instance (~30 s startup,
0.8 GiB VRAM), closed via close().

Failure policy: transport failures (timeout / EOF / id mismatch / broken pipe) kill
and respawn the worker and resend the request once. EVERY consecutive failure —
transport, respawn handshake, or an ok:false synthesis reply (a sticky CUDA context
dies per-request while the process stays alive) — counts toward _MAX_CRASHES, after
which TtsFatalError escapes the per-segment catch and fails the stage loudly: a dead
engine must not grind out hundreds of synth_error flags overnight. The counter
resets on any successful synthesis.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from .base import TtsEngineError, TtsFatalError

_STARTUP_TIMEOUT_S = 240.0   # measured load ~30 s; first ever run may also fetch the Vocos
                             # vocoder from the HF hub (prefetch step in SETUP.md)
_REQUEST_TIMEOUT_S = 120.0   # worst sentence ~15 s audio at RTF 0.39 ≈ 6 s; ~20× thermal margin
_MAX_CRASHES = 3


class _WorkerCrash(Exception):
    """Internal: transport-level worker failure (timeout, EOF, protocol corruption)."""


def plan_speed(gen_bytes: int, ref_sec: float, ref_bytes: int, base_speed: float,
               floor: float, ceil: float,
               target_sec: float | None, max_sec: float | None) -> float:
    """Slot-fill policy: pick the native F5 speed for one render unit.

    F5's duration canvas is deterministic: out_sec ≈ ref_sec * gen_bytes / ref_bytes / speed
    (utils_infer's canvas line; raw pre-accent bytes on BOTH sides so the stress-mark byte
    inflation cancels to first order). Three branches against the unit's SOURCE SPAN
    (target_sec) and its slot cap (max_sec) — the span, not the slot, is the fill target so
    real inter-sentence pauses stay pauses:
      underfill  (nominal < span)          → stretch down to floor*base_speed
      fits slot  (span ≤ nominal ≤ slot)   → base_speed (free gap absorbs the spill, as today)
      overflows  (nominal > slot)          → compress up to ceil*base_speed; atempo tops up
    floor/ceil are MULTIPLIERS of base_speed so a recalibrated narrator pace (DECISIONS
    speed-calibration) shifts the whole window with it. Pure — unit-tested without GPU.
    """
    nominal = ref_sec * gen_bytes / ref_bytes / base_speed
    if target_sec is None or nominal <= 0:
        return base_speed
    if nominal < target_sec:
        return max(nominal * base_speed / target_sec, floor * base_speed)
    if max_sec is not None and nominal > max_sec:
        return min(nominal * base_speed / max_sec, ceil * base_speed)
    return base_speed


class F5Engine:
    sample_rate = 24000          # vocos-mel-24khz — asserted against the worker handshake
    supports_seed = True
    supports_target = True

    def __init__(self, python: Path, ckpt: Path, vocab: Path, ref_audio: Path,
                 ref_text: Path, nfe: int, speed: float, default_seed: int,
                 speed_floor: float = 1.0, speed_ceil: float = 1.0) -> None:
        for p in (python, ckpt, vocab, ref_audio, ref_text):
            if not Path(p).exists():
                raise RuntimeError(
                    f"F5 asset missing: {p} — fetch it at setup (see SETUP.md); "
                    "overdub does not auto-download")
        self._argv = [
            str(Path(python).resolve()),
            str(Path(__file__).with_name("f5_worker.py")),
            "--ckpt", str(Path(ckpt).resolve()),
            "--vocab", str(Path(vocab).resolve()),
            "--ref-audio", str(Path(ref_audio).resolve()),
            "--ref-text", str(Path(ref_text).resolve()),
            "--nfe", str(int(nfe)),
        ]
        self._speed = float(speed)
        self._floor = float(speed_floor)
        self._ceil = float(speed_ceil)
        self._ref_sec: float | None = None       # from the ready handshake (slot-fill inputs)
        self._ref_bytes: int | None = None
        self._default_seed = int(default_seed)
        self._proc: subprocess.Popen | None = None
        self._q: queue.Queue | None = None
        self._crashes = 0
        self._rid = 0
        self._respawn()              # eager: a worker that can't start fails the stage NOW,
                                     # in one loud error — never as N per-segment flags

    # --- process management -----------------------------------------------------
    def _respawn(self) -> None:
        self._kill()
        try:
            self._proc = subprocess.Popen(
                self._argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
                encoding="utf-8", errors="replace",
                env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            )
        except OSError as e:
            raise RuntimeError(f"cannot spawn f5 worker ({self._argv[0]}): {e}") from e
        q: queue.Queue = queue.Queue()

        def _pump(proc=self._proc, q=q):
            try:
                for line in proc.stdout:
                    q.put(line)
            finally:
                q.put(None)                                # EOF sentinel, even on reader error

        threading.Thread(target=_pump, daemon=True).start()
        self._q = q
        try:
            msg = self._read(_STARTUP_TIMEOUT_S)
        except _WorkerCrash as e:
            self._kill()
            self._count_crash(f"worker failed to start (see stderr above): {e}")
            raise TtsEngineError(f"f5 worker failed to start: {e}") from e
        if msg.get("event") != "ready":
            self._kill()
            self._count_crash(f"unexpected handshake: {msg}")
            raise TtsEngineError(f"f5 worker bad handshake: {msg}")
        if msg.get("sample_rate") != self.sample_rate:     # vocoder drift would silently
            self._kill()                                   # rescale assemble's timing math
            raise TtsFatalError(
                f"f5 worker sample_rate {msg.get('sample_rate')} != {self.sample_rate}")
        self._ref_sec = float(msg.get("ref_sec") or 0) or None
        self._ref_bytes = int(msg.get("ref_bytes") or 0) or None
        if (self._ref_sec is None or self._ref_bytes is None) and (
                self._floor != 1.0 or self._ceil != 1.0):
            print(f"       [warn] f5 worker sent no usable ref stats "
                  f"(ref_sec={msg.get('ref_sec')}, ref_bytes={msg.get('ref_bytes')}) — "
                  "slot-fill DISABLED, all units render at base speed", file=sys.stderr)

    def _count_crash(self, why: str) -> None:
        self._crashes += 1
        if self._crashes >= _MAX_CRASHES:
            raise TtsFatalError(
                f"f5 worker failed {self._crashes}× consecutively — engine/driver is down: {why}")

    def _read(self, timeout: float) -> dict:
        """Next protocol line as a dict. Skips non-JSON noise (a native fd-1 write that
        slipped past the worker's dup2). Raises _WorkerCrash on timeout or EOF."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _WorkerCrash(f"no response within {timeout:.0f}s")
            try:
                line = self._q.get(timeout=remaining)
            except queue.Empty:
                raise _WorkerCrash(f"no response within {timeout:.0f}s") from None
            if line is None:
                raise _WorkerCrash("worker died (stdout EOF)")
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict):
                return msg

    def _kill(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None

    # --- TtsEngine API ------------------------------------------------------------
    def synthesize(self, text: str, out_path: Path, *, seed: int | None = None,
                   target_sec: float | None = None, max_sec: float | None = None) -> float:
        speed = self._speed
        if target_sec is not None and self._ref_sec and self._ref_bytes:
            speed = plan_speed(len(text.encode("utf-8")), self._ref_sec, self._ref_bytes,
                               self._speed, self._floor, self._ceil, target_sec, max_sec)
        self._rid += 1
        req = {"id": self._rid, "text": text, "out": str(Path(out_path).resolve()),
               "seed": self._default_seed if seed is None else int(seed),
               "speed": round(speed, 4)}
        line = json.dumps(req, ensure_ascii=False) + "\n"
        for retry in (False, True):
            if self._proc is None or self._proc.poll() is not None:
                self._respawn()                            # may raise TtsEngineError/TtsFatalError
            try:
                self._proc.stdin.write(line)
                self._proc.stdin.flush()
                msg = self._read(_REQUEST_TIMEOUT_S)
                if msg.get("id") != req["id"]:
                    raise _WorkerCrash(f"protocol id mismatch ({msg.get('id')} != {req['id']})")
            except (OSError, _WorkerCrash) as e:
                self._kill()
                self._count_crash(str(e))                  # TtsFatalError at the cap
                if retry:
                    raise TtsEngineError(f"f5 worker crashed twice on one request: {e}") from e
                continue                                   # respawn + resend once
            if not msg.get("ok"):
                # worker alive, request failed. A sticky CUDA context (device-side assert,
                # illegal memory access) fails EVERY request while the process survives —
                # so per-request failures count toward the same cap as transport crashes.
                self._count_crash(f"synth error: {msg.get('error')}")
                raise TtsEngineError(f"f5 synth failed: {msg.get('error')}")
            self._crashes = 0
            # prefer the worker-reported EFFECTIVE speed: F5 forces local_speed=0.3 for
            # texts under 10 UTF-8 bytes, where echoing the request would record fiction
            return float(msg.get("speed_eff", req["speed"]))

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.stdin.close()                       # EOF ends the worker's stdin loop
            self._proc.wait(timeout=10)
        except Exception:
            self._kill()
        self._proc = None
