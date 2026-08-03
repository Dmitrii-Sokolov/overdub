"""Is this host quiet enough to measure on? Call it FIRST, before any timed work.

Written after a grouping A/B produced verify times of 347 s and 597 s against a 45 s baseline
and a whole conclusion was drawn from them ("grouping makes synthesis slower"). Every
number was an artifact: a game was holding the GPU at 98% and 86 C. The probe methodology was
otherwise sound — mirrored order, repeated blocks — but a mirrored pair only cancels drift that
is SLOW compared to the run. A process that owns the card for the whole session is not drift,
it is a different machine, and no amount of counterbalancing detects it.

So this is deliberately a PRE-flight check, not a post-hoc correction: the cheapest moment to
learn the host is busy is before spending an hour measuring it.

Two signals, sampled a few times because the desktop compositor spikes utilisation on its own:
  - memory in use: the reliable one. A quiet host sat at 1.3 GB, the busy one at 8.6 GB
  - utilisation: median, not a single reading (the quiet host still showed 27% in one sample)
Clock throttling is REPORTED but never blocks — a laptop under a power cap is normal here and
would make this refuse to run on the very hardware the project targets.

CLI: `python scripts/host_guard.py` prints the state and exits 1 when busy, so a shell can use
it as a gate: `python scripts/host_guard.py && python scripts/asr_probe.py --variant beam1`
"""

from __future__ import annotations

import argparse
import shutil
import statistics
import subprocess
import sys
import time

# A quiet host measured 1347 MiB / 27% util; the busy one 8634 MiB / 98%. The memory bar sits
# well above idle desktop use and well below any real model load; the util bar is high enough
# that compositor spikes do not trip it.
BUSY_MEM_MIB = 2500
BUSY_UTIL_PCT = 40

_QUERY = "utilization.gpu,memory.used,memory.total,temperature.gpu,clocks.sm"


def parse_row(line: str) -> dict | None:
    """One `--format=csv,noheader,nounits` row → ints. None if the row is not parseable.

    Pure, so the thresholds are testable without a GPU."""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 5:
        return None
    try:
        util, used, total, temp, sm = (int(float(p)) for p in parts[:5])
    except ValueError:
        return None                                    # "[N/A]" on some driver/VM combinations
    return {"util": util, "mem_used": used, "mem_total": total, "temp": temp, "sm_clock": sm}


def sample(n: int = 3, interval: float = 0.4) -> list[dict]:
    """n readings of the first GPU. Empty list when nvidia-smi is absent or unusable."""
    if shutil.which("nvidia-smi") is None:
        return []
    rows = []
    for i in range(n):
        if i:
            time.sleep(interval)
        try:
            out = subprocess.run(
                ["nvidia-smi", f"--query-gpu={_QUERY}", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10, check=True).stdout
        except Exception:                              # noqa: BLE001 — a guard must never be
            return []                                  # the thing that breaks the measurement
        first = next((ln for ln in out.splitlines() if ln.strip()), "")
        row = parse_row(first)
        if row:
            rows.append(row)
    return rows


def verdict(rows: list[dict]) -> dict:
    """Fold samples into {busy, reason, ...}. No samples = unknown, never busy: a host we
    cannot inspect must not block work, only forfeit the guarantee."""
    if not rows:
        return {"busy": False, "known": False, "reason": "nvidia-smi unavailable"}
    util = int(statistics.median(r["util"] for r in rows))       # median: kills desktop spikes
    mem = max(r["mem_used"] for r in rows)                        # max: catches a fluctuating load
    reasons = []
    if mem >= BUSY_MEM_MIB:
        reasons.append(f"{mem} MiB in use (bar {BUSY_MEM_MIB})")
    if util >= BUSY_UTIL_PCT:
        reasons.append(f"{util}% utilisation (bar {BUSY_UTIL_PCT})")
    return {"busy": bool(reasons), "known": True, "reason": "; ".join(reasons),
            "util": util, "mem_used": mem, "mem_total": rows[-1]["mem_total"],
            "temp": max(r["temp"] for r in rows), "sm_clock": rows[-1]["sm_clock"]}


def describe(v: dict) -> str:
    if not v["known"]:
        return f"[host] GPU state unknown ({v['reason']}) — timings are UNGUARDED"
    head = (f"[host] GPU {v['util']}% util, {v['mem_used']}/{v['mem_total']} MiB, "
            f"{v['temp']} C, {v['sm_clock']} MHz")
    return f"{head} — BUSY: {v['reason']}" if v["busy"] else f"{head} — idle"


def require_idle(*, allow_busy: bool = False, quiet: bool = False) -> dict:
    """Print the state; raise SystemExit when the card is busy and the caller did not opt in."""
    v = verdict(sample())
    if not quiet:
        print(describe(v), file=sys.stderr)
    if v["busy"] and not allow_busy:
        raise SystemExit(
            "refusing to measure on a busy GPU — close whatever is using it, or pass "
            "--allow-busy-gpu to measure anyway (the numbers will not be comparable to any "
            "run made on an idle card)")
    return v


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="host_guard", description=__doc__.splitlines()[0])
    p.add_argument("--allow-busy-gpu", action="store_true",
                   help="report and exit 0 even when the card is busy")
    args = p.parse_args(argv)
    v = verdict(sample())
    print(describe(v))
    return 1 if (v["busy"] and not args.allow_busy_gpu) else 0


if __name__ == "__main__":
    sys.exit(main())
