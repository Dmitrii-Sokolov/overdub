"""Host resources the scheduler reads: which cores are the fast ones, and how much RAM is free.

Both answers are best-effort and degrade to None — a host this module cannot read is run exactly
as before, never refused.

WHY P-CORES. On a hybrid CPU (i9-13900HX: 8 hyper-threaded P-cores, 16 E-cores) Windows decides
per process where a single-threaded child lands, and for ffmpeg it guesses wrong often enough to
matter: one 3-min AAC encode took 5.9 s pinned to a P-core and 11.4 s on an E-core (2026-10-29),
and an unpinned encode came out anywhere between the two. Pinning removes the lottery. Silero,
in contrast, already lands on P-cores by itself (6.25 s unpinned vs 6.41 s pinned, same day), so
only the children this pipeline spawns are pinned, never the pipeline process.
"""

from __future__ import annotations

import ctypes
import os
import sys
from typing import Callable


def performance_mask() -> "int | None":
    """Affinity mask of the logical processors in the HIGHEST efficiency class (processor group 0).

    None off Windows, on a CPU whose cores are all one class (nothing to prefer), or when the API
    cannot be read. Walks SYSTEM_CPU_SET_INFORMATION records by their own Size field, so a newer
    Windows that appends fields to the record does not misalign the parse.
    """
    if sys.platform != "win32":
        return None
    try:
        k32 = ctypes.windll.kernel32
        need = ctypes.c_ulong(0)
        k32.GetSystemCpuSetInformation(None, 0, ctypes.byref(need), None, 0)
        buf = (ctypes.c_ubyte * need.value)()
        if not k32.GetSystemCpuSetInformation(buf, need, ctypes.byref(need), None, 0):
            return None
        raw = bytes(buf)
        classes: dict[int, int] = {}                  # logical index -> efficiency class
        off = 0
        while off + 16 <= len(raw):
            size = int.from_bytes(raw[off:off + 4], "little")
            if size <= 0:
                break
            # Type 0 = CpuSetInformation; the CpuSet member starts at byte 8:
            # Id(4) Group(2) LogicalProcessorIndex(1) CoreIndex(1) LLC(1) Numa(1) EfficiencyClass(1)
            if int.from_bytes(raw[off + 4:off + 8], "little") == 0:
                group = int.from_bytes(raw[off + 12:off + 14], "little")
                if group == 0:
                    classes[raw[off + 14]] = raw[off + 18]
            off += size
        if not classes or len(set(classes.values())) < 2:
            return None
        top = max(classes.values())
        return sum(1 << lp for lp, c in classes.items() if c == top and lp < 64)
    except Exception:                                 # noqa: BLE001 — degrade, never refuse
        return None


def pin(proc, mask: "int | None") -> bool:
    """Restrict a started subprocess.Popen to `mask`. False (and the process untouched) when the
    mask is None or the call fails. The child has already run for the few microseconds between
    Popen returning and this call, which costs nothing measurable on a minutes-long encode."""
    if mask is None or sys.platform != "win32":
        return False
    try:
        k32 = ctypes.windll.kernel32
        k32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        return bool(k32.SetProcessAffinityMask(ctypes.c_void_p(int(proc._handle)), mask))
    except Exception:                                 # noqa: BLE001
        return False


class _MemStatus(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def available_ram() -> "int | None":
    """Physical RAM available right now, in bytes; None when it cannot be read."""
    try:
        if sys.platform == "win32":
            st = _MemStatus()
            st.dwLength = ctypes.sizeof(_MemStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return int(st.ullAvailPhys)
            return None
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except Exception:                                 # noqa: BLE001
        return None


_RAM_HEADROOM = 4 * 2**30          # left free for everything the admitted jobs do not account for


def ram_admission() -> "Callable[[list[int], int], bool]":
    """Read free RAM once and return the rule that admits concurrent jobs under it.

    The rule, `admits(held, need)`, answers "may a job needing `need` bytes start beside the
    running jobs, whose needs are `held` (one entry per running job)?":

    - nothing running: yes, always, so a job too large for the budget still runs, alone;
    - free RAM unreadable: no, so the caller runs one job at a time — how it ran before it had a
      concurrent path at all;
    - otherwise: while the running needs plus this one fit the RAM free at the reading, minus a
      headroom.

    The budget is fixed at the reading rather than re-read per admission, because a job that has
    started but not yet allocated would make a live reading look free.
    """
    free = available_ram()
    budget = None if free is None else max(0, free - _RAM_HEADROOM)
    if budget is None:
        print("[warn] free RAM cannot be read — concurrent jobs run one at a time",
              file=sys.stderr)

    def admits(held: "list[int]", need: int) -> bool:
        if not held:
            return True
        return budget is not None and sum(held) + need <= budget

    return admits
