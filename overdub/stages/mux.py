"""Mux stage: build the RU audio track per cfg.dub_mix, then ffmpeg assembles the MKV.

Modes (dead-air design, DECISIONS 2026-07-16):
  replace — RU track = the dub alone (Phase-1 behavior, plus loudness alignment);
  duck    — original audio under the dub, ducked −15 dB during unit SPANS (not just placed
            audio: cap-clamped underfill must not let full-level EN pop through mid-span)
            via an explicit sample-exact gain envelope — deterministic depth, no compressor
            pumping, intervals merged when gaps < 1 s so the original doesn't "breathe";
  bed     — Demucs no-vocals bed (separate stage) at −6 dB under the dub.

All modes align the dub's RMS to the original speech loudness (one static gain, ±6 dB cap)
so an A/B between modes compares MECHANISMS, not loudness. Units whose wav is empty
(empty_tts / synth_error) are NOT ducked — the original EN plays there at full level as the
honest fallback. The mix is built in numpy at 48 kHz stereo and encoded by the same ffmpeg
invocation that muxes; video is stream-copied, never re-encoded. done() self-heals: a
dub_mix flip or a resynthesis (synth_key stamp) re-runs mux automatically.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import numpy as np
import soundfile as sf

from .. import report
from ..pipeline import Context
from ..workdir import replace_retry
from .synthesize import units_of

_MIX_SR = 48000
_DUCK_GAIN = 10 ** (-15 / 20)     # −15 dB under RU speech (VO standard)
_BED_GAIN = 10 ** (-6 / 20)       # bed sits −6 dB under the dub
_ATTACK_S = 0.05                  # duck edge ramps
_RELEASE_S = 0.30
_MERGE_GAP_S = 1.0                # merge duck intervals closer than this (no phrase-rate pumping)
_GAIN_CAP_DB = 6.0                # dub loudness alignment is capped to ±6 dB


def _extract(src, dst, *, sr=_MIX_SR, ch=2) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
                    "-vn", "-ac", str(ch), "-ar", str(sr), "-c:a", "pcm_s16le", str(dst)],
                   check=True)


_CHUNK = 10_000_000


def _sqsum(x: np.ndarray) -> float:
    """Chunked float64 sum of squares — no full-array float64 copy (a 39-min stereo track
    is ~200M samples; whole-array astype would transiently cost ~1.6 GB per call)."""
    flat = x.reshape(-1)
    acc = 0.0
    for i in range(0, flat.size, _CHUNK):
        c = flat[i:i + _CHUNK].astype("float64")
        acc += float(np.dot(c, c))
    return acc


def _nonzero(x: np.ndarray) -> int:
    flat = x.reshape(-1)
    return sum(int(np.count_nonzero(flat[i:i + _CHUNK])) for i in range(0, flat.size, _CHUNK))


def _dub_gain(orig: np.ndarray, dub: np.ndarray, spans: list[tuple[int, int]]) -> float:
    """Static gain aligning dub loudness to the original's speech loudness (±6 dB cap)."""
    sq = 0.0
    cnt = 0
    for a, b in (spans or [(0, len(orig))]):
        c = orig[a:b]
        sq += _sqsum(c)
        cnt += c.size
    r_orig = (sq / cnt) ** 0.5 if cnt else 0.0
    nz = _nonzero(dub)                                     # zeros add nothing to the sq-sum
    r_dub = (_sqsum(dub) / nz) ** 0.5 if nz else 0.0
    if r_orig <= 0 or r_dub <= 0:
        return 1.0
    cap = 10 ** (_GAIN_CAP_DB / 20)
    return float(np.clip(r_orig / r_dub, 1 / cap, cap))


def _duck_envelope(n: int, spans: list[tuple[int, int]]) -> np.ndarray:
    """Sample-exact gain envelope: 1.0 outside spans, _DUCK_GAIN inside, linear ramps."""
    env = np.ones(n, dtype="float32")
    if not spans:
        return env
    merged: list[list[int]] = []
    for a, b in sorted(spans):
        if merged and a - merged[-1][1] < int(_MERGE_GAP_S * _MIX_SR):
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    atk, rel = int(_ATTACK_S * _MIX_SR), int(_RELEASE_S * _MIX_SR)
    down = np.linspace(1.0, _DUCK_GAIN, atk, dtype="float32")
    up = np.linspace(_DUCK_GAIN, 1.0, rel, dtype="float32")
    for a, b in merged:
        a0, b1 = max(0, a - atk), min(n, b + rel)
        env[max(0, a):min(n, b)] = np.minimum(env[max(0, a):min(n, b)], _DUCK_GAIN)
        seg = env[a0:max(0, a)]
        seg[:] = np.minimum(seg, down[-len(seg):] if len(seg) else seg)
        seg = env[min(n, b):b1]
        seg[:] = np.minimum(seg, up[:len(seg)])
    return env


class MuxStage:
    name = "mux"

    def done(self, ctx: Context) -> bool:
        if not ctx.work.output.exists():
            return False
        try:                                               # make-style freshness: a re-assembled
            for dep in (ctx.work.dub_audio, ctx.work.source_bed):   # dub or a new bed re-muxes
                if dep.exists() and dep.stat().st_mtime > ctx.work.output.stat().st_mtime:
                    print(f"       [info] mux: {dep.name} newer than output.mkv — re-muxing",
                          file=sys.stderr)
                    return False
        except OSError:
            return False
        try:
            rep = json.loads(ctx.work.report.read_text(encoding="utf-8"))
            stamp = rep.get("mux") or {}
            man = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
            if stamp.get("dub_mix") != ctx.cfg.dub_mix:
                print(f"       [info] mux: dub_mix changed ({stamp.get('dub_mix')} → "
                      f"{ctx.cfg.dub_mix}) — re-muxing", file=sys.stderr)
                return False
            if stamp.get("synth_key") and stamp["synth_key"] != man.get("synth_key"):
                print("       [info] mux: manifest synth_key changed — re-muxing", file=sys.stderr)
                return False
        except Exception:
            pass                                           # legacy/torn report → keep old gate
        return True

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH — required for mux. "
                               "Install ffmpeg; overdub does not auto-install.")
        w = ctx.work
        for p in (w.source_video, w.dub_audio, w.en_srt, w.ru_srt):
            if not p.exists():
                raise RuntimeError(f"mux input missing: {p} — run earlier stages first")
        if cfg.dub_mix not in ("replace", "duck", "bed"):
            raise ValueError(f"unknown dub_mix: {cfg.dub_mix!r}")
        if cfg.dub_mix == "bed" and not w.source_bed.exists():
            raise RuntimeError("source_bed.wav missing — run separate before mux (dub_mix=bed)")
        man = json.loads(w.seg_manifest.read_text(encoding="utf-8"))

        dub48 = w.root / "_mix_dub48.wav"
        orig48 = w.root / "_mix_orig48.wav"
        bed48 = w.root / "_mix_bed48.wav"
        mix_wav = w.root / "_mix_ru.wav"
        try:
            _extract(w.dub_audio, dub48)                   # 24k mono → 48k stereo
            dub, _ = sf.read(str(dub48), dtype="float32")
            _extract(w.source_video, orig48)               # original: gain reference (+ duck base)
            orig, _ = sf.read(str(orig48), dtype="float32")

            # duck/gain intervals = unit spans EXTENDED to the placed audio: the slot-fill
            # neutral branch deliberately spills RU past the span into the free gap, and
            # that tail must not ride over full-level EN. samples/man_sr is the pre-atempo
            # upper bound (atempo only shortens; overshoot lands in the next ducked span).
            man_sr = man.get("sample_rate") or _MIX_SR
            spans = []
            for u in units_of(man):
                if (u.get("samples") or 0) > 0:
                    end_sec = max(u["end"], u["start"] + u["samples"] / man_sr)
                    spans.append((round(u["start"] * _MIX_SR), round(end_sec * _MIX_SR)))
            gain = _dub_gain(orig, dub, spans)             # loudness ref is ALWAYS the original
            dub *= gain
            if cfg.dub_mix == "bed":
                _extract(w.source_bed, bed48)
                base = sf.read(str(bed48), dtype="float32")[0]
                del orig
            else:
                base = orig

            n = max(len(base), len(dub))                   # the dub may outlast the video
            if len(base) < n:
                base = np.vstack([base, np.zeros((n - len(base), base.shape[1]), "float32")])
            if len(dub) < n:
                dub = np.vstack([dub, np.zeros((n - len(dub), dub.shape[1]), "float32")])

            if cfg.dub_mix == "replace":
                mix = dub
            elif cfg.dub_mix == "duck":
                np.multiply(base, _duck_envelope(n, spans)[:, None], out=base)   # in place
                base += dub
                mix = base
            else:                                          # bed
                base *= _BED_GAIN
                base += dub
                mix = base
            peak = 0.0                                     # chunked: no full |mix| copy
            flat = mix.reshape(-1)
            for i in range(0, flat.size, _CHUNK):
                c = flat[i:i + _CHUNK]
                peak = max(peak, float(c.max(initial=0.0)), float(-c.min(initial=0.0)))
            if peak > 0.99:                                # summing headroom guard
                mix *= 0.99 / peak
            sf.write(str(mix_wav), mix, _MIX_SR, format="WAV", subtype="PCM_16")
            del base, dub, mix, flat

            tmp = w.output.with_suffix(".mkv.tmp")
            subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(w.source_video), "-i", str(mix_wav),
                    "-i", str(w.en_srt), "-i", str(w.ru_srt),
                    "-map", "0:v:0", "-map", "0:a:0", "-map", "1:a:0", "-map", "2:0", "-map", "3:0",
                    "-c:v", "copy", "-c:a:0", "copy", "-c:a:1", "aac", "-b:a:1", "192k",
                    "-c:s", "srt",
                    "-metadata:s:a:0", "language=eng", "-metadata:s:a:0", "title=Original",
                    "-metadata:s:a:1", "language=rus",
                    "-metadata:s:a:1", f"title=Russian dub ({cfg.dub_mix})",
                    "-metadata:s:s:0", "language=eng", "-metadata:s:s:1", "language=rus",
                    "-disposition:a:0", "0", "-disposition:a:1", "default",
                    "-f", "matroska", str(tmp),
                ],
                check=True,
            )
            # artifact flips BEFORE the stamp (assemble's "done-gate flips LAST" discipline):
            # a crash between them leaves new-mkv + old-stamp → harmless idempotent re-mux;
            # stamp-first would ship the OLD mix labeled as the new mode after a failed swap
            replace_retry(tmp, w.output)
            rep = report.load(w.report)
            rep["mux"] = {"dub_mix": cfg.dub_mix, "synth_key": man.get("synth_key"),
                          "dub_gain_db": round(20 * float(np.log10(gain)), 2)}
            report.save(w.report, rep)
        finally:
            for p in (dub48, orig48, bed48, mix_wav, w.output.with_suffix(".mkv.tmp")):
                p.unlink(missing_ok=True)
        print(f"       → {w.output.name} (dub_mix={cfg.dub_mix})")
