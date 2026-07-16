"""Assemble stage (Phase 1): place each segment at its start ts, atempo-fit, pad → dub_ru.wav.

Each RU clip is anchored at its own absolute start (round(start*sr)) and truncated to its slot
[start_i, start_{i+1}) — the sentence span PLUS the following inter-sentence gap as pause
headroom. Anchoring at the absolute start means consuming the gap only delays the start of
silence, never the next sentence (independently anchored), so it strictly beats a [start, end]
slot: free pause is spent before any pitch-warp ("no tempo cap" is not "no effort"). Clips are
placed into a pre-allocated int16 buffer; disjoint slots make the blit lossless with zero
cumulative drift. atempo is UNCAPPED (ffmpeg's single-filter 0.5–100 range covers any realistic
factor, pitch preserved); extreme factors are logged in report.json, never clamped.

Also emits en.srt (src_en) and ru.srt (raw text_ru, NOT text_tts) on the source timeline.
Per-segment speed factor is merged into report.json (co-owned with verify via overdub.report).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import numpy as np
import soundfile as sf

from .. import report
from ..pipeline import Context

_BROKEN = 1.8   # speed factor at/above which a segment is a "candidate broken" in the report


def _ts(t: float) -> str:
    ms = max(0, round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _write_srt(path, rows) -> None:
    """rows: iterable of (start, end, text). end is floored to start+0.05 — a zero/negative
    cue is silently dropped by most players."""
    out: list[str] = []
    for i, (a, b, text) in enumerate(rows, 1):
        b = max(b, a + 0.05)
        out += [str(i), f"{_ts(a)} --> {_ts(b)}", (text or "…").strip(), ""]
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(out), encoding="utf-8")
    os.replace(tmp, path)


class AssembleStage:
    name = "assemble"

    def done(self, ctx: Context) -> bool:
        return ctx.work.dub_audio.exists()

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH — required for atempo. "
                               "Install ffmpeg; overdub does not auto-install.")
        segs = json.loads(ctx.work.translation.read_text(encoding="utf-8"))
        if not ctx.work.seg_manifest.exists():
            raise RuntimeError("segments/manifest.json missing — run synthesize before assemble")
        doc = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
        man = {e["id"]: e for e in doc["segments"]}
        sr = doc["sample_rate"]
        if sr != cfg.tts_sample_rate:                      # sr drift → whole-track desync if wrong
            print(f"       [warn] manifest sr {sr} != cfg {cfg.tts_sample_rate}; using manifest sr",
                  file=sys.stderr)
        ids = [s["id"] for s in segs]
        if ids != list(range(len(segs))) or set(ids) != set(man):
            raise RuntimeError("assemble id mismatch (never-drop invariant)")

        # plan pass (no audio): absolute offsets, slots computed from ROUNDED offsets so
        # consecutive slots tile with no ±1-sample seam, and speed factors.
        n = len(segs)
        plans: list[dict] = []
        for i, s in enumerate(segs):
            sid = s["id"]
            offset = round(s["start"] * sr)
            nat = man[sid]["samples"]
            aflag: str | None = None
            slot = (round(segs[i + 1]["start"] * sr) - offset) if i < n - 1 else None
            if slot is not None and slot <= 0:             # non-monotone: contract violation
                slot, aflag = None, "bad_slot"
            if slot is not None and nat > slot:
                req = nat / slot                           # TRUE required factor — logged uncapped
                factor = min(req, 100.0)                   # only the ffmpeg atempo arg is clamped (single-filter max)
                if req > 100.0:
                    aflag = aflag or "extreme_tempo"
            else:
                req = factor = 1.0                         # fits, or last segment: place raw + pad
            plans.append({"s": s, "sid": sid, "offset": offset, "slot": slot,
                          "factor": factor, "req": req, "nat": nat, "aflag": aflag})

        if not plans:                                      # speech-free source (music-only / wrong URL)
            raise RuntimeError("0 segments — no speech detected in source (music-only or wrong URL?)")
        last = plans[-1]
        total = max(1, last["offset"] + man[last["sid"]]["samples"])
        buf = np.zeros(total, dtype="int16")
        rep = report.load(ctx.work.report)                 # preserve any verify fields
        tmp_dir = ctx.work.segments_dir / "_atempo"
        tmp_dir.mkdir(exist_ok=True)
        n_sped = n_over = 0
        max_f = 1.0
        for p in plans:
            sid, offset, slot, factor, req, aflag = (
                p["sid"], p["offset"], p["slot"], p["factor"], p["req"], p["aflag"])
            wav = ctx.work.seg_wav(sid)
            placed = 0
            try:
                if not wav.exists():
                    raise FileNotFoundError(wav)
                if factor > 1.0:
                    dst = tmp_dir / f"{sid:05d}.wav"
                    subprocess.run(
                        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                         "-filter:a", f"atempo={factor:.6f}", "-ar", str(sr),
                         "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
                        check=True,
                    )
                    clip, _ = sf.read(str(dst), dtype="int16")
                    n_sped += 1
                    max_f = max(max_f, req)                 # summary tracks the TRUE demand, uncapped
                    if req >= _BROKEN:
                        n_over += 1
                else:
                    clip, _ = sf.read(str(wav), dtype="int16")
                if clip.ndim > 1:
                    clip = clip[:, 0]
                cap = slot if slot is not None else len(clip)
                m = max(0, min(len(clip), cap, total - offset))
                buf[offset:offset + m] = clip[:m]
                placed = m
            except Exception as e:
                aflag = aflag or "assemble_error"
                print(f"       [flag] id{sid}: {aflag} {e}", file=sys.stderr)
            if placed == 0 and (p["s"].get("text_tts") or "").strip():   # expected audio, none placed
                aflag = aflag or "missing_audio"           # e.g. synth_error / torn wav on an --only assemble path
            if aflag or req >= _BROKEN:
                print(f"       [flag] id{sid}: factor={req:.2f} {aflag or ''}".rstrip(),
                      file=sys.stderr)
            report.upsert(
                rep, sid, status=p["s"]["status"], translate_flag=p["s"].get("flag"),
                speed_factor=round(req, 4),                # logged UNCAPPED (honors the contract)
                slot_sec=(round(slot / sr, 3) if slot is not None else None),
                raw_sec=round(p["nat"] / sr, 3), placed_sec=round(placed / sr, 3),
                assemble_flag=aflag,
            )

        dub_tmp = ctx.work.dub_audio.with_suffix(".wav.tmp")
        sf.write(str(dub_tmp), buf, sr, format="WAV", subtype="PCM_16")  # explicit: .tmp defeats inference
        _write_srt(ctx.work.en_srt, [(s["start"], s["end"], s["src_en"]) for s in segs])
        _write_srt(ctx.work.ru_srt, [(s["start"], s["end"], s["text_ru"]) for s in segs])
        report.prune(rep, {s["id"] for s in segs})         # drop phantom records from a shrunk re-tune
        rep["assemble"] = {"sample_rate": sr, "duration_sec": round(total / sr, 3),
                           "n_sped": n_sped, "max_speed_factor": round(max_f, 4), "n_over_1_8": n_over}
        report.save(ctx.work.report, rep)
        os.replace(dub_tmp, ctx.work.dub_audio)            # done-gate flips LAST
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print(f"       dub_ru.wav {total / sr:.1f}s ({n_sped} sped, max ×{max_f:.2f}, {n_over} over 1.8×)")
