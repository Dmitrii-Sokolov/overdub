"""Bridge to the Parakeet ASR worker running in `.venv-parakeet`.

WHY A SUBPROCESS AND NOT AN IMPORT. NeMo pulls 137 packages and pins numpy below the pipeline's
(2.5.1 -> 2.4.6 as resolved 2026-08-06). Installing it into `.venv-asr` would gamble the whole
stack — faster-whisper, ctranslate2, torch, silero — on an experiment's dependency tree. The repo
already answers this exact question once, for demucs: a second venv, driven as a CLI subprocess
(`cfg.demucs_python`, stages/separate.py). This is the same answer for the same reason.

ONE PROCESS PER STAGE SWEEP, not per video. The worker loads the model in 10-30 s; the pipeline is
stage-major, so a process per video would pay that 165 times on a 165-video batch. `Session` owns
the handle and drops it in `clear()`, which is the same lifetime a WhisperModel gets.

The worker speaks one JSON object per line on stdout and puts every human-readable line on stderr,
so parsing here needs no filtering of NeMo's startup banner.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "scripts" / "parakeet_worker.py"


class ParakeetWorker:
    """A live `parakeet_worker.py --serve` process. Not thread-safe; the sweep is sequential."""

    def __init__(self, python: Path, *, attn: str = "local", vad: bool = True) -> None:
        exe = Path(python)
        if not exe.exists():
            raise RuntimeError(
                f"Parakeet ASR is selected but its interpreter is missing: {exe}. Create the venv "
                f"(see SETUP.md) or set asr_engine = \"whisper\" in overdub.toml. This pipeline "
                f"never auto-installs.")
        argv = [str(exe), "-X", "utf8", str(WORKER), "--serve", "--attn", attn]
        if not vad:
            argv.append("--no-vad")
        env = dict(os.environ, PYTHONUTF8="1")     # the worker prints transcript text on stdout
        self._p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=None, text=True, encoding="utf-8", env=env)
        hello = self._readline()
        if not hello.get("ready"):
            raise RuntimeError(f"parakeet worker did not come up: {hello}")

    def _readline(self) -> dict:
        line = self._p.stdout.readline()
        if not line:
            code = self._p.poll()
            raise RuntimeError(f"parakeet worker died (exit {code}) — its stderr is above")
        return json.loads(line)

    def transcribe(self, wav: Path) -> tuple[list[dict], dict]:
        """(words, meta) for one wav. Raises on a worker-side failure — the stage decides."""
        self._p.stdin.write(json.dumps({"wav": str(wav)}) + "\n")
        self._p.stdin.flush()
        reply = self._readline()
        if "error" in reply:
            raise RuntimeError(f"parakeet worker: {reply['error']}")
        return reply["words"], reply["meta"]

    def close(self) -> None:
        """Never raises: teardown must not mask an exception already unwinding (Session.clear)."""
        try:
            if self._p.poll() is None:
                self._p.stdin.close()
                self._p.wait(timeout=30)
        except Exception as e:                                  # noqa: BLE001
            print(f"[warn] parakeet worker teardown: {e}", file=sys.stderr)
            try:
                self._p.kill()
            except Exception:                                   # noqa: BLE001
                pass
