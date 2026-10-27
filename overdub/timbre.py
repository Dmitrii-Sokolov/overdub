"""Two numbers per voice: median F0 (how high) and formant spacing ΔF (how big the vocal tract
sounds — the axis the palette's formant variants move).

They are the timbre the voice assignment matches source speakers to dub voices on, and F0 alone
also decides the voice pool and the grammatical gender the translator is told. One function runs
on both sides of that match — a speaker's spans of source.wav and a palette voice's rendered
audio — so the two sides are measured the same way by construction.

Pure numpy, any sample rate, deterministic. A long speaker is subsampled to MAX_FRAMES evenly
spaced frames, which bounds the cost of a 4-hour video without biasing it.

ΔF is the least-squares fit of F1..F4 to an idealised uniform tube, Fi = (2i-1)/2 · ΔF — the
standard vocal-tract-length proxy. The formants come from LPC on the spectrum cut at a ceiling,
which needs no resampling. The ceiling follows the voice's own pool (Praat's convention, 5000 Hz
male / 5500 Hz female): one fixed ceiling pushed a raised female F4 out of range and read a
+12% shift as +3%. ΔF values are therefore comparable WITHIN a pool only — which is the only
comparison the voice assignment makes.

Accuracy, measured 2026-10-27 by reading the same audio at ×0.88 / ×1.12 its sample rate (an
exact scaling of every frequency): F0 within 1%, ΔF within 1-5% (male) and 2-3% (female). The
palette's rubberband formant variants measure at about half their nominal shift on this scale,
so a variant's ΔF must be measured, never taken from its name.
"""

from __future__ import annotations

import numpy as np

F0_MIN = 60.0
F0_MAX = 400.0
FRAME_SEC = 3.0 / F0_MIN      # three periods of the lowest F0, the pitch-tracking minimum
HOP_SEC = 0.01
MAX_FRAMES = 4000
VOICING_MIN = 0.5           # normalized autocorrelation peak a frame needs to count as voiced
LPC_FRAME_SEC = 0.025
LPC_CEIL_HZ = {"male": 5000.0, "female": 5500.0}
LPC_ORDER = 12
N_FORMANTS = 4

F0_OVERLAP_HZ = (150.0, 200.0)      # male and female F0 overlap here; outside it F0 decides, inside
                                    # it ΔF does. A man at 176 Hz (ear-confirmed, 2026-10-27) put a
                                    # pure F0 split in the wrong pool; his ΔF, 922 Hz, did not.
POOL_SPLIT_DF_HZ = 1075.0           # inside the overlap: ΔF below → male pool, at or above →
                                    # female. Midway between the highest male (1037) and the lowest
                                    # female (1085) measured 2026-10-27 — 12 men, 1 real woman and
                                    # the 3 female palette voices; re-check on more women.
GENDER_DF_HZ = (1040.0, 1110.0)     # inside the overlap the translator's grammatical gender is
                                    # "unknown" (prefer impersonal constructions) unless ΔF clears
                                    # this band — the pool must pick a side, the grammar need not


def _frame_starts(spans: list[tuple[float, float]], sr: int, n: int) -> np.ndarray:
    flen, hop = int(FRAME_SEC * sr), int(HOP_SEC * sr)
    starts = [np.arange(int(a * sr), min(int(b * sr), n) - flen, hop) for a, b in spans]
    starts = np.concatenate(starts) if starts else np.zeros(0, dtype=int)
    if len(starts) > MAX_FRAMES:
        starts = starts[np.linspace(0, len(starts) - 1, MAX_FRAMES).astype(int)]
    return starts.astype(int)


def _acorr(x: np.ndarray, nfft: int) -> np.ndarray:
    return np.fft.irfft(np.abs(np.fft.rfft(x, nfft)) ** 2, nfft)[..., :x.shape[-1]]


def _f0(frames: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """(f0 per frame, voiced mask). The frame's autocorrelation is divided by its window's (the
    Boersma correction): without it the window decays the true peak at one period below the
    half-period one, and a low voice reads an octave HIGH. Among the remaining peaks the shortest
    lag within 90% of the best wins, which guards the opposite, octave-low error."""
    n = frames.shape[1]
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    win = np.hanning(n)
    x = frames - frames.mean(axis=1, keepdims=True)
    r = _acorr(x * win, nfft)
    rw = _acorr(win, nfft)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(r[:, :1] > 0, (r / r[:, :1]) / (rw / rw[0]), 0.0)
    lo, hi = int(sr / F0_MAX), min(int(sr / F0_MIN), n // 2)     # beyond n/2 rw is too small
    seg = r[:, lo:hi]
    peak = seg.max(axis=1)
    lag = lo + np.argmax(seg >= 0.9 * peak[:, None], axis=1)
    return sr / lag, peak >= VOICING_MIN


def _levinson(r: np.ndarray, order: int) -> np.ndarray:
    a = np.zeros(order + 1)
    a[0] = 1.0
    err = r[0]
    for i in range(1, order + 1):
        k = -(r[i] + np.dot(a[1:i], r[i - 1:0:-1])) / err
        a[1:i] = a[1:i] + k * a[i - 1:0:-1]
        a[i] = k
        err *= 1.0 - k * k
        if err <= 0:
            break
    return a


def _formant_spacing(frame: np.ndarray, sr: int, ceil: float) -> "float | None":
    m = int(LPC_FRAME_SEC * sr)
    frame = frame[(len(frame) - m) // 2:][:m]                  # formants want ~25 ms, not 3 periods
    x = np.append(frame[0], frame[1:] - 0.97 * frame[:-1]) * np.hamming(len(frame))
    nfft = 1 << int(np.ceil(np.log2(len(x))) + 1)
    spec = np.abs(np.fft.rfft(x, nfft)) ** 2
    k = int(ceil / (sr / nfft)) + 1                 # bins up to the ceiling → a signal at 2·ceil
    r = np.fft.irfft(spec[:k], 2 * (k - 1))[:LPC_ORDER + 1]
    if r[0] <= 0:
        return None
    roots = np.roots(_levinson(r, LPC_ORDER))
    roots = roots[np.imag(roots) > 0]
    fs = 2 * ceil
    freq = np.angle(roots) * fs / (2 * np.pi)
    bw = -fs / np.pi * np.log(np.abs(roots))
    f = np.sort(freq[(freq > 90) & (freq < ceil - 200) & (bw < 400)])[:N_FORMANTS]
    if len(f) < N_FORMANTS:
        return None
    w = (2 * np.arange(1, N_FORMANTS + 1) - 1) / 2.0
    return float(np.dot(f, w) / np.dot(w, w))


def timbre(audio: np.ndarray, sr: int, spans: list[tuple[float, float]]) -> dict:
    """{"f0_hz", "delta_f_hz", "voiced_frames"} over the voiced frames inside `spans` (seconds).
    Both values are None when no frame is voiced — silence must not read as a voice."""
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    starts = _frame_starts(spans, sr, len(audio))
    if not len(starts):
        return {"f0_hz": None, "delta_f_hz": None, "voiced_frames": 0}
    flen = int(FRAME_SEC * sr)
    # only the sampled frames are cast: a 4-hour source as float64 would be ~1.8 GB
    frames = audio[starts[:, None] + np.arange(flen)[None, :]].astype(np.float64)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    loud = rms >= 0.1 * np.percentile(rms, 90)
    f0, voiced = _f0(frames, sr)
    keep = loud & voiced
    if not keep.any():
        return {"f0_hz": None, "delta_f_hz": None, "voiced_frames": 0}
    f0_hz = round(float(np.median(f0[keep])), 1)
    # the ceiling needs a pool before ΔF exists: F0 alone picks it, at the overlap's midpoint
    ceil = LPC_CEIL_HZ["female" if f0_hz >= sum(F0_OVERLAP_HZ) / 2 else "male"]
    dfs = [d for d in (_formant_spacing(fr, sr, ceil) for fr in frames[keep]) if d is not None]
    return {"f0_hz": f0_hz,
            "delta_f_hz": round(float(np.median(dfs)), 1) if dfs else None,
            "voiced_frames": int(keep.sum())}


def pool_of(f0_hz: "float | None", delta_f_hz: "float | None" = None) -> "str | None":
    """Voice pool: never "unknown" — every speaker needs a voice. Inside the F0 overlap ΔF
    decides; with no ΔF there, the overlap's midpoint does."""
    if f0_hz is None:
        return None
    lo, hi = F0_OVERLAP_HZ
    if f0_hz < lo:
        return "male"
    if f0_hz > hi:
        return "female"
    if delta_f_hz is None:
        return "female" if f0_hz >= (lo + hi) / 2 else "male"
    return "female" if delta_f_hz >= POOL_SPLIT_DF_HZ else "male"


def grammatical_gender(f0_hz: "float | None", delta_f_hz: "float | None" = None) -> str:
    if f0_hz is None:
        return "unknown"
    lo, hi = F0_OVERLAP_HZ
    if f0_hz < lo:
        return "masculine"
    if f0_hz > hi:
        return "feminine"
    if delta_f_hz is None:
        return "unknown"
    if delta_f_hz < GENDER_DF_HZ[0]:
        return "masculine"
    if delta_f_hz > GENDER_DF_HZ[1]:
        return "feminine"
    return "unknown"
