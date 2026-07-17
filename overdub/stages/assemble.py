"""Assemble stage: place each render unit at its start ts, atempo-fit, pad → dub_ru.wav.

Iterates manifest UNITS (one wav per unit; legacy per-sentence manifests adapt as singleton
units). Each unit is anchored at its own absolute start (round(start*sr)) and truncated to
its slot [start_i, start_{i+1}) — span plus the following inter-unit gap as pause headroom.
atempo is UNCAPPED and applied strictly after verification. With slot-fill native speed
upstream, atempo is a rare top-up; triage flags the COMBINED compression (native × atempo),
or the report would go blind exactly when native compression does the work.

Clip edges get ~10 ms micro-fades: a hard step was inaudible against digital silence, but
audible as a tick once the mix modes (duck/bed) put real audio under the dub.

Report records fan out per SENTENCE id (group_id + the unit's speed fields duplicated).
done(): dub exists AND the report's assemble synth_key stamp matches the manifest — a
resynthesis auto-invalidates the dub (self-healing re-assemble), never silently ships
pre-resynthesis audio.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
import soundfile as sf

from .. import report
from ..pipeline import Context
from ..tts import engine_sample_rate
from ..workdir import replace_retry
from .synthesize import units_of

_BROKEN = 1.8   # combined compression factor at/above which a unit is "candidate broken"
_FADE_SEC = 0.010

MAX_CUE_SEC = 6.0       # display-only cue caps: a sentence-granularity cue reads as a text
MAX_CUE_CHARS = 84      # wall (47/315 ru cues ran >12 s). ~2 lines x 42 chars, ~14 cps
MIN_CUE_SEC = 1.2       # never manufacture a flash-frame: a seam whose split would make one is
                        # skipped, and the cue is left whole once every seam is exhausted
# split AFTER clause punctuation only — NOT the em-dash ("X — это Y" is a RU zero-copula, not a
# line end) and NOT bare word gaps (a gap split lands mid-clause, e.g. "AI | fluency"): a cue
# with no interior clause seam is left whole rather than broken at an invented boundary.
_CUE_SEAM = re.compile(r"(?<=[,;:.!?…])\s")


def _fade(clip: np.ndarray, sr: int) -> np.ndarray:
    """~10 ms linear fade-in/out in place (int16-safe via float multiply)."""
    n = min(int(sr * _FADE_SEC), len(clip) // 2)
    if n <= 0:
        return clip
    ramp = np.linspace(0.0, 1.0, n, dtype="float32")
    clip = clip.astype("float32")
    clip[:n] *= ramp
    clip[-n:] *= ramp[::-1]
    return clip.astype("int16")


def _ts(t: float) -> str:
    ms = max(0, round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _cue_seams(text: str) -> list[int]:
    """Interior clause-seam split indices, ordered nearest the char midpoint first. The
    0 < i < len-1 filter guarantees a non-empty side after .strip() on both halves, so
    _split_cue needs no empty-side guard."""
    mid = len(text) / 2.0
    idx = [m.start() for m in _CUE_SEAM.finditer(text) if 0 < m.start() < len(text) - 1]
    return sorted(idx, key=lambda i: abs(i - mid))


def _split_cue(a: float, b: float, text: str) -> list[tuple[float, float, str]]:
    """DISPLAY-ONLY recursive cue split (same shape as transcribe._split_overlong).
    sentences.json / translation.json ids, text and timings are untouched — this decides
    only how ONE sentence's span is PRESENTED. Sub-cue timings are proportional to char
    count and the outer [a, b] is preserved exactly, so cue onsets stay sentence-synced.
    Seams are tried nearest-midpoint first; one whose split would flash (< MIN_CUE_SEC) is
    skipped, and the cue is left whole once every seam is exhausted (no seam is the same as
    all-flash — there is no readable way to break it, so we don't)."""
    text = (text or "").strip()
    if (b - a) <= MAX_CUE_SEC and len(text) <= MAX_CUE_CHARS:
        return [(a, b, text)]
    for i in _cue_seams(text):
        left, right = text[:i].strip(), text[i:].strip()
        m = a + (b - a) * len(left) / (len(left) + len(right))
        if m - a < MIN_CUE_SEC or b - m < MIN_CUE_SEC:   # would flash: try the next seam
            continue
        return _split_cue(a, m, left) + _split_cue(m, b, right)
    return [(a, b, text)]                                 # no usable clause seam: leave whole


def _write_srt(path, rows) -> None:
    """rows: iterable of (start, end, text). Long cues are broken up for DISPLAY only (see
    _split_cue). end is floored to start+0.05 — a zero/negative cue is silently dropped by
    most players."""
    out: list[str] = []
    i = 0
    for a0, b0, text0 in rows:
        for a, b, text in _split_cue(a0, b0, text0):
            i += 1
            b = max(b, a + 0.05)
            out += [str(i), f"{_ts(a)} --> {_ts(b)}", (text or "…").strip(), ""]
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(out), encoding="utf-8")
    os.replace(tmp, path)


class AssembleStage:
    name = "assemble"

    def done(self, ctx: Context) -> bool:
        if not ctx.work.dub_audio.exists():
            return False
        try:
            rep = json.loads(ctx.work.report.read_text(encoding="utf-8"))
            stamp = rep.get("assemble") or {}
            man = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
            # absent stamp counts as mismatch — a legacy report re-assembles ONCE and gains
            # the stamp; units_key catches same-synth_key (--force) resynthesis
            if (stamp.get("synth_key") != man.get("synth_key")
                    or stamp.get("units_key") != man.get("units_key")):
                print("       [info] assemble: manifest synth/units key changed — re-assembling",
                      file=sys.stderr)
                return False
        except Exception:
            pass                                           # torn report → keep the old gate
        return True

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH — required for atempo. "
                               "Install ffmpeg; overdub does not auto-install.")
        segs = json.loads(ctx.work.translation.read_text(encoding="utf-8"))
        if not ctx.work.seg_manifest.exists():
            raise RuntimeError("segments/manifest.json missing — run synthesize before assemble")
        doc = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
        units = units_of(doc)
        base_speed = doc.get("base_speed") or 1.0
        sr = doc["sample_rate"]
        if sr != engine_sample_rate(cfg):                  # sr drift → whole-track desync if wrong
            print(f"       [warn] manifest sr {sr} != engine sr {engine_sample_rate(cfg)}; "
                  "using manifest sr", file=sys.stderr)
        ids = [s["id"] for s in segs]
        if ids != list(range(len(segs))) or sorted(i for u in units for i in u["ids"]) != ids:
            raise RuntimeError("assemble id mismatch (never-drop invariant)")

        # plan pass (no audio): absolute offsets, slots from ROUNDED offsets, speed factors
        n = len(units)
        plans: list[dict] = []
        for i, u in enumerate(units):
            offset = round(u["start"] * sr)
            nat = u["samples"]
            aflag: str | None = None
            slot = (round(units[i + 1]["start"] * sr) - offset) if i < n - 1 else None
            if slot is not None and slot <= 0:             # non-monotone: contract violation
                slot, aflag = None, "bad_slot"
            if slot is not None and nat > slot:
                req = nat / slot                           # TRUE required factor — logged uncapped
                factor = min(req, 100.0)                   # only the ffmpeg arg is clamped
                if req > 100.0:
                    aflag = aflag or "extreme_tempo"
            else:
                req = factor = 1.0
            native_rel = (u.get("speed") or base_speed) / base_speed   # >1 = native compression
            plans.append({"u": u, "lead": u["ids"][0], "offset": offset, "slot": slot,
                          "factor": factor, "req": req, "nat": nat, "aflag": aflag,
                          "combined": max(1.0, native_rel) * req})

        if not plans:
            raise RuntimeError("0 units — no speech detected in source (music-only or wrong URL?)")
        last = plans[-1]
        total = max(1, last["offset"] + last["nat"])
        buf = np.zeros(total, dtype="int16")
        rep = report.load(ctx.work.report)                 # preserve any verify fields
        tmp_dir = ctx.work.segments_dir / "_atempo"
        tmp_dir.mkdir(exist_ok=True)
        n_sped = n_over = 0
        max_f = 1.0
        in_span_silence = 0.0
        for p in plans:
            u, lead, offset, slot, factor, req, aflag = (
                p["u"], p["lead"], p["offset"], p["slot"], p["factor"], p["req"], p["aflag"])
            wav = ctx.work.seg_wav(lead)
            placed = 0
            try:
                if not wav.exists():
                    raise FileNotFoundError(wav)
                if factor > 1.0:
                    dst = tmp_dir / f"{lead:05d}.wav"
                    subprocess.run(
                        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                         "-filter:a", f"atempo={factor:.6f}", "-ar", str(sr),
                         "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
                        check=True,
                    )
                    clip, _ = sf.read(str(dst), dtype="int16")
                    n_sped += 1
                    max_f = max(max_f, req)
                else:
                    clip, _ = sf.read(str(wav), dtype="int16")
                if clip.ndim > 1:
                    clip = clip[:, 0]
                cap = slot if slot is not None else len(clip)
                m = max(0, min(len(clip), cap, total - offset))
                if m:
                    buf[offset:offset + m] = _fade(clip[:m], sr)
                placed = m
            except Exception as e:
                aflag = aflag or "assemble_error"
                print(f"       [flag] u{lead}: {aflag} {e}", file=sys.stderr)
            if placed == 0 and u.get("text_tts"):
                aflag = aflag or "missing_audio"
            if p["combined"] >= _BROKEN:
                n_over += 1
            if aflag or p["combined"] >= _BROKEN:
                print(f"       [flag] u{lead}: combined×{p['combined']:.2f} "
                      f"(atempo {req:.2f}) {aflag or ''}".rstrip(), file=sys.stderr)
            span_sec = u["end"] - u["start"]
            if u.get("text_tts"):
                in_span_silence += max(0.0, span_sec - placed / sr)
            for sid in u["ids"]:
                report.upsert(
                    rep, sid, status=segs[sid]["status"], translate_flag=segs[sid].get("flag"),
                    group_id=lead,
                    speed_factor=round(req, 4),            # atempo demand, logged UNCAPPED
                    combined_factor=round(p["combined"], 4),
                    slot_sec=(round(slot / sr, 3) if slot is not None else None),
                    raw_sec=round(p["nat"] / sr, 3), placed_sec=round(placed / sr, 3),
                    assemble_flag=aflag,
                )

        dub_tmp = ctx.work.dub_audio.with_suffix(".wav.tmp")
        sf.write(str(dub_tmp), buf, sr, format="WAV", subtype="PCM_16")
        _write_srt(ctx.work.en_srt, [(s["start"], s["end"], s["src_en"]) for s in segs])
        _write_srt(ctx.work.ru_srt, [(s["start"], s["end"], s["text_ru"]) for s in segs])
        report.prune(rep, {s["id"] for s in segs})
        rep["assemble"] = {
            "sample_rate": sr, "duration_sec": round(total / sr, 3),
            "synth_key": doc.get("synth_key"), "units_key": doc.get("units_key"),
            "n_sped": n_sped, "max_speed_factor": round(max_f, 4),
            "n_over_1_8_combined": n_over,
            "in_span_silence_sec": round(in_span_silence, 1),
        }
        # artifact flips BEFORE the stamp: a crash between them leaves new-dub + old-stamp,
        # which done() treats as mismatch and harmlessly re-assembles. Stamp-first would
        # let a failed replace serve the OLD dub under a matching stamp — silent staleness.
        replace_retry(dub_tmp, ctx.work.dub_audio)
        report.save(ctx.work.report, rep)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"       dub_ru.wav {total / sr:.1f}s ({n_sped} sped, max ×{max_f:.2f}, "
              f"{n_over} over 1.8× combined, in-span silence {in_span_silence:.0f}s)")
