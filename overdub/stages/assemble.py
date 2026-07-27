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


def effective_lowpass(hz: int | None, sr: int | None) -> int | None:
    """The cutoff actually applied to the dub track, or None when the filter is a no-op.

    Skipped unless the cutoff sits comfortably below Nyquist: the hiss it targets is a
    48 kHz Silero artifact living above 12 kHz, while on a 24 kHz track (the opt-in F5
    engine) an 11 kHz biquad would ride the band edge and recolour the voice for nothing.
    run() and done() both call THIS, so the gate can never disagree with what was written."""
    return hz if hz and sr and hz < sr * 0.4 else None


def _apply_lowpass(path, sr: int, hz: int) -> None:
    """One ffmpeg pass over the whole finished track, in place (path is still the .tmp).

    Deliberately NOT folded into the per-unit atempo call: that call only runs for units
    with factor > 1.0, so a per-unit filter would leave every un-sped unit unfiltered and
    put an audible tembre step at those seams. atempo is pitch-preserving, so filtering
    after it is spectrally equivalent to filtering before."""
    dst = path.with_suffix(path.suffix + ".lp")
    # explicit -f wav for the SAME reason soundfile calls need format="WAV" here: both ends are
    # atomic temp paths (…/dub_ru.wav.tmp[.lp]) whose extension names no container.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "wav", "-i", str(path),
         "-filter:a", f"lowpass=f={hz}", "-ar", str(sr), "-ac", "1",
         "-c:a", "pcm_s16le", "-f", "wav", str(dst)],
        check=True,
    )
    os.replace(dst, path)


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


def _write_srt(path, rows, *, split: bool = True) -> None:
    """rows: iterable of (start, end, text). Long cues are broken up for DISPLAY only (see
    _split_cue). end is floored to start+0.05 — a zero/negative cue is silently dropped by
    most players.

    split=False for rows that were ALREADY split by the caller. _split_cue divides a span by
    CHARACTER share, which is only meaningful while the span is speech: applied to a ru row
    whose end was stretched over slot silence it walks the tail fragment out into the hole
    (measured: a fragment opening 10.6 s after its own audio stopped). _ru_cue_rows therefore
    splits first and stretches after, and must not be split a second time here."""
    out: list[str] = []
    i = 0
    for a0, b0, text0 in rows:
        for a, b, text in (_split_cue(a0, b0, text0) if split else [(a0, b0, text0)]):
            i += 1
            b = max(b, a + 0.05)
            out += [str(i), f"{_ts(a)} --> {_ts(b)}", (text or "…").strip(), ""]
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(out), encoding="utf-8")
    os.replace(tmp, path)


def _tempo_for(nat: int, slot: int | None, cfg) -> tuple[float, float, float]:
    """(req, factor, stretch) for one unit, in SAMPLES. Pure — the tempo decision, testable.

    `req` is the COMPRESSION demand and stays floored at 1.0 even when the unit under-fills:
    every triage surface already reads it (and `combined`), and underfill has its own metric in
    `fill_median`. `factor` is what ffmpeg is actually given — above 1.0 it compresses, below it
    stretches. `stretch` is 1.0 unless the unit was slowed.

    Stretching is bounded by cfg.atempo_floor rather than allowed to reach the slot at any cost:
    the median hole needs ~1.37x, which is well past what stays natural, so this is the TRIM
    beside a slot-sized translation, not the fix. cfg.atempo_floor = 1.0 restores the
    speed-up-only behaviour that shipped before 2026-07-25."""
    if slot is not None and nat > slot:
        req = nat / slot                                   # TRUE required factor — uncapped
        return req, min(req, 100.0), 1.0                   # only the ffmpeg arg is clamped
    want = slot * cfg.slot_fill_target if slot is not None else None
    if want and nat and nat < want:
        stretch = max(nat / want, cfg.atempo_floor)
        return 1.0, stretch, stretch
    return 1.0, 1.0, 1.0


def _write_ru_srt(path, plans, segs, sr) -> None:
    """ru.srt end to end: rows from ACTUAL placement, split over the spoken span, written
    without a second split.

    One function rather than two calls at the call site, because `split=False` there is a
    correctness requirement that looks like a formatting option — re-splitting these rows
    reintroduces the exact defect _ru_cue_rows is ordered to avoid, and a mutation test
    confirmed nothing else would catch it being flipped back."""
    _write_srt(path, _ru_cue_rows(plans, segs, sr), split=False)


def _ru_cue_rows(plans, segs, sr) -> list[tuple[float, float, str]]:
    """ru.srt rows follow the DUB, not the source timeline.

    Grouping makes a unit's audio continuous — the inter-sentence pauses inside a group are
    swallowed — while a source-timed cue still carries them, so the two drift apart: p90
    divergence 1.28 s at the shipped 1.2/20/600 grouping against 0.30 s before it. The onset
    therefore comes from where the audio ACTUALLY landed (the unit's offset plus the
    sentence's character share of the unit's placed duration) and the end runs to the NEXT
    cue's onset: reading time is why a cue exists, and the silence after an under-filled unit
    belongs to the text that was just spoken.

    The share is taken over text_tts — the string the engine actually voiced — so a sentence
    carrying "x2" ("в два раза") is timed by what was said, not by what is displayed.

    A unit that placed no audio (empty_tts, missing_audio, assemble_error) falls back to its
    sentences' ORIGINAL timings: a silent unit has no placement to speak of, and never-drop
    outranks accuracy here. en.srt is deliberately NOT re-timed — it transcribes the original
    English track, which the MKV still carries unmodified, so moving it would desync it from
    its own audio to match a dub it does not belong to.

    SPLIT ORDER IS LOAD-BEARING: the long-cue split runs HERE, over the span the unit actually
    SPEAKS, and the stretch to the next onset happens after it. Splitting a stretched row
    instead divides slot silence by character share and walks the tail fragment out into the
    hole — measured at up to 10.6 s past its own audio, worse than the drift this function
    exists to remove. So the rows returned are final: _write_srt is called with split=False."""
    rows: list[tuple[float, float, str]] = []
    for p in plans:
        ids = p["u"]["ids"]
        dur = p.get("placed", 0) / sr
        if dur <= 0:
            for i in ids:
                rows += _split_cue(segs[i]["start"], segs[i]["end"], segs[i]["text_ru"])
            continue
        at = p["offset"] / sr
        # min width 1: an empty text_tts inside a spoken unit must still take a slice, or the
        # sentences after it in the same unit would inherit its time and read early.
        widths = [max(len((segs[i].get("text_tts") or segs[i].get("text_ru") or "").strip()), 1)
                  for i in ids]
        total_w = sum(widths)
        for sid, w in zip(ids, widths):
            b = at + dur * w / total_w
            rows += _split_cue(at, b, segs[sid]["text_ru"])
            at = b
    # Stretch each cue to the next one's onset, then keep onsets monotone: a fallback row
    # carries SOURCE timings and can otherwise open before the placed row preceding it.
    # _write_srt floors b to a + 0.05, so even a fully squeezed row still displays.
    out: list[tuple[float, float, str]] = []
    prev = 0.0
    for k, (a, b, text) in enumerate(rows):
        if k + 1 < len(rows):
            b = max(b, rows[k + 1][0])
        a = max(a, prev)
        out.append((a, max(b, a), text))
        prev = a
    return out


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
            # lowpass joins the gate because it is the one audio knob that lands HERE, not in
            # synth: without it a cutoff change would leave the old dub in place under a
            # matching synth_key. Absent from a legacy stamp reads as None, which equals the
            # effective cutoff on every 24 kHz (F5) run — those do not churn.
            # atempo_floor / slot_fill_target join for exactly the reason lowpass_hz did: they
            # change the finished track while leaving synth_key untouched, so without them here
            # a floor change would leave the OLD dub in place and read as "applied". A legacy
            # stamp has neither key — absent reads as None, which differs from any float, so
            # such a workdir re-assembles once. That is correct: it was built speed-up-only.
            if (stamp.get("synth_key") != man.get("synth_key")
                    or stamp.get("units_key") != man.get("units_key")
                    or stamp.get("atempo_floor") != ctx.cfg.atempo_floor
                    or stamp.get("slot_fill_target") != ctx.cfg.slot_fill_target
                    or stamp.get("lowpass_hz") != effective_lowpass(
                        ctx.cfg.dub_lowpass_hz, man.get("sample_rate"))):
                print("       [info] assemble: manifest synth/units/fit/lowpass key changed — "
                      "re-assembling", file=sys.stderr)
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
            req, factor, stretch = _tempo_for(nat, slot, cfg)
            if req > 100.0:
                aflag = aflag or "extreme_tempo"
            native_rel = (u.get("speed") or base_speed) / base_speed   # >1 = native compression
            plans.append({"u": u, "lead": u["ids"][0], "offset": offset, "slot": slot,
                          "factor": factor, "req": req, "nat": nat, "aflag": aflag,
                          "stretch": stretch,
                          "combined": max(1.0, native_rel) * req})

        if not plans:
            raise RuntimeError("0 units — no speech detected in source (music-only or wrong URL?)")
        last = plans[-1]
        total = max(1, last["offset"] + last["nat"])
        buf = np.zeros(total, dtype="int16")
        rep = report.load(ctx.work.report)                 # preserve any verify fields
        tmp_dir = ctx.work.segments_dir / "_atempo"
        tmp_dir.mkdir(exist_ok=True)
        n_sped = n_over = n_stretched = 0
        max_f = 1.0
        min_f = 1.0
        in_span_silence = 0.0
        slot_silence = 0.0
        for p in plans:
            u, lead, offset, slot, factor, req, aflag = (
                p["u"], p["lead"], p["offset"], p["slot"], p["factor"], p["req"], p["aflag"])
            wav = ctx.work.seg_wav(lead)
            placed = 0
            try:
                if not wav.exists():
                    raise FileNotFoundError(wav)
                if factor != 1.0:                          # >1 compresses, <1 stretches
                    dst = tmp_dir / f"{lead:05d}.wav"
                    subprocess.run(
                        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                         "-filter:a", f"atempo={factor:.6f}", "-ar", str(sr),
                         "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
                        check=True,
                    )
                    clip, _ = sf.read(str(dst), dtype="int16")
                    if factor > 1.0:
                        n_sped += 1
                        max_f = max(max_f, req)
                    else:
                        n_stretched += 1
                        min_f = min(min_f, factor)
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
            p["placed"] = placed                           # ru.srt cues are placed from this
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
                if slot is not None:
                    # against the SLOT, not the span: the span excludes the inter-unit gap the
                    # dub is free to speak into, so in_span_silence understates the hole a
                    # listener actually hears (241.8 s reported vs 283 s of real slot hole on
                    # the blocker video).
                    slot_silence += max(0.0, (slot - placed) / sr)
            for sid in u["ids"]:
                report.upsert(
                    rep, sid, status=segs[sid]["status"], translate_flag=segs[sid].get("flag"),
                    group_id=lead,
                    speed_factor=round(req, 4),            # atempo demand, logged UNCAPPED
                    combined_factor=round(p["combined"], 4),
                    slot_sec=(round(slot / sr, 3) if slot is not None else None),
                    raw_sec=round(p["nat"] / sr, 3), placed_sec=round(placed / sr, 3),
                    stretch_factor=round(p["stretch"], 4),   # <1 = slowed to fill; 1.0 = untouched
                    assemble_flag=aflag,
                )

        # The last unit has no slot (nothing follows it to bound one), so it cannot report a
        # fill — None rather than a silently short sample when nothing qualifies.
        fills = [p["nat"] / p["slot"] for p in plans if p["slot"]]
        fill_median = round(float(np.median(fills)), 4) if fills else None

        dub_tmp = ctx.work.dub_audio.with_suffix(".wav.tmp")
        sf.write(str(dub_tmp), buf, sr, format="WAV", subtype="PCM_16")
        lowpass = effective_lowpass(cfg.dub_lowpass_hz, sr)
        if lowpass:
            _apply_lowpass(dub_tmp, sr, lowpass)
        _write_srt(ctx.work.en_srt, [(s["start"], s["end"], s["src_en"]) for s in segs])
        _write_ru_srt(ctx.work.ru_srt, plans, segs, sr)
        report.prune(rep, {s["id"] for s in segs})
        rep["assemble"] = {
            "sample_rate": sr, "duration_sec": round(total / sr, 3),
            "synth_key": doc.get("synth_key"), "units_key": doc.get("units_key"),
            "n_sped": n_sped, "max_speed_factor": round(max_f, 4),
            "n_over_1_8_combined": n_over,
            "n_stretched": n_stretched,
            "min_stretch_factor": round(min_f, 4),
            "atempo_floor": cfg.atempo_floor,
            "slot_fill_target": cfg.slot_fill_target,
            "in_span_silence_sec": round(in_span_silence, 1),
            # Fill is raw/slot BEFORE atempo and is deliberately NOT floored at 1.0 the way
            # speed_factor is: that floor is why the whole speed block reads "clean" (median
            # 1.0, p95 1.0) on a video that is 23% hole — it can only ever report compression.
            # One number that moves in both directions is the point, now that underfill is
            # known to be the SOURCE speaker's pace rather than an engine property: the same
            # corpus has videos sitting at 1.02-1.15.
            "fill_median": fill_median,
            "slot_silence_sec": round(slot_silence, 1),
            "lowpass_hz": lowpass,
        }
        # artifact flips BEFORE the stamp: a crash between them leaves new-dub + old-stamp,
        # which done() treats as mismatch and harmlessly re-assembles. Stamp-first would
        # let a failed replace serve the OLD dub under a matching stamp — silent staleness.
        replace_retry(dub_tmp, ctx.work.dub_audio)
        report.save(ctx.work.report, rep)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if lowpass:
            print(f"       lowpass {lowpass} Hz applied to dub_ru.wav")
        fill_txt = f"{fill_median:.2f}" if fill_median is not None else "n/a"
        stretch_txt = f", {n_stretched} stretched, min ×{min_f:.2f}" if n_stretched else ""
        print(f"       dub_ru.wav {total / sr:.1f}s ({n_sped} sped, max ×{max_f:.2f}"
              f"{stretch_txt}, {n_over} over 1.8× combined, fill med {fill_txt}, "
              f"slot silence {slot_silence:.0f}s, in-span silence {in_span_silence:.0f}s)")
