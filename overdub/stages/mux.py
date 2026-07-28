"""Mux stage: build the RU audio track per cfg.dub_mix, then ffmpeg assembles the MKV.

Modes (dead-air design, DECISIONS 2026-07-16):
  replace — RU track = the dub alone (Phase-1 behavior, plus loudness alignment);
  duck    — original audio under the dub, ducked −15 dB during unit SPANS (not just placed
            audio: cap-clamped underfill must not let full-level EN pop through mid-span)
            via an explicit sample-exact gain envelope — deterministic depth, no compressor
            pumping, intervals merged when gaps < 1 s so the original doesn't "breathe";
  bed     — Demucs no-vocals bed (separate stage) at ORIGINAL level under the dub
            (ear 2026-07-17: attenuating the bed is worse; production default).

All modes align the dub's RMS to the original speech loudness (one static gain, ±6 dB cap)
so an A/B between modes compares MECHANISMS, not loudness. Units whose wav is empty
(empty_tts / synth_error) are NOT ducked — the original EN plays there at full level as the
honest fallback. The mix is built in numpy at 48 kHz stereo and encoded by the same ffmpeg
invocation that muxes; video is stream-copied, never re-encoded. done() self-heals: a
dub_mix flip, a resynthesis (synth_key stamp) or a track that has APPEARED since the last
mux all re-run mux automatically.

DEGRADED OUTPUT (2026-07-28). Only `source.mkv` is required. The dub and the two subtitle
tracks are OPTIONAL: whatever is on disk is muxed, whatever is missing is omitted END TO END
(input, -map, codec, metadata, disposition), and the omission is printed as a [warn] and
recorded in the report's `tracks` stamp. Rationale: a video whose translate or synthesize
never produced anything used to yield NO artifact at all — the run died on `mux input
missing` after the video was already downloaded and transcribed. The missing-artifact case
DEGRADES; an INCONSISTENT one (a dub with no manifest, an unknown dub_mix, bed mode with no
bed) still raises — losing a track is a reportable outcome, shipping a wrong one is not.
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
_BED_GAIN = 1.0                   # bed at original level (ear 2026-07-17: no attenuation)
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


def mux_args(video, *, dub=None, subs=(), out, dub_mix: str) -> list[str]:
    """The complete ffmpeg argv for the final MKV, given only the tracks that EXIST.

    `dub` is the mixed RU wav or None; `subs` is an ordered sequence of (lang, path) whose
    lang is the 3-letter code stamped on the stream. Every optional track is added or omitted
    in ONE place — input, -map, codec, metadata and disposition together — which is the whole
    reason this is a function and not four `if`s scattered through run(): a -map that outlives
    its -i names an input that does not exist, and ffmpeg reports that as a stream-specifier
    error at the end of an hour-long run, not as a missing dub.

    Input indices are assigned as inputs are appended, so the subtitle inputs shift down by
    one when there is no dub. Pure — no filesystem, no ffmpeg; the caller decides what exists.

    Disposition is emitted ONLY alongside a dub. `-disposition:a:0 0` exists to un-default the
    ORIGINAL so a player picks the RU track; with no RU track it would ship an MKV whose sole
    audio stream is marked non-default, which some players then refuse to auto-select.
    """
    inputs = ["-i", str(video)]
    maps = ["-map", "0:v:0", "-map", "0:a:0"]
    codecs = ["-c:v", "copy", "-c:a:0", "copy"]
    meta = ["-metadata:s:a:0", "language=eng", "-metadata:s:a:0", "title=Original"]
    disp: list[str] = []
    idx = 1
    if dub is not None:
        inputs += ["-i", str(dub)]
        maps += ["-map", f"{idx}:a:0"]
        codecs += ["-c:a:1", "aac", "-b:a:1", "192k"]
        meta += ["-metadata:s:a:1", "language=rus",
                 "-metadata:s:a:1", f"title=Russian dub ({dub_mix})"]
        disp += ["-disposition:a:0", "0", "-disposition:a:1", "default"]
        idx += 1
    sub_meta: list[str] = []
    for k, (lang, path) in enumerate(subs):
        inputs += ["-i", str(path)]
        maps += ["-map", f"{idx}:0"]
        sub_meta += [f"-metadata:s:s:{k}", f"language={lang}"]
        idx += 1
    if subs:
        codecs += ["-c:s", "srt"]
    return (["ffmpeg", "-y", "-loglevel", "error"] + inputs + maps + codecs + meta + sub_meta
            + disp + ["-f", "matroska", str(out)])


def tracks_on_disk(work) -> dict[str, bool]:
    """Which optional tracks a mux run right now WOULD carry. The stamp's vocabulary."""
    return {"dub": work.dub_audio.exists(),
            "en_srt": work.en_srt.exists(),
            "ru_srt": work.ru_srt.exists()}


def gained_tracks(stamped, now) -> list[str]:
    """Tracks present NOW that the stamped mux did not carry — the re-mux trigger.

    UPGRADE-ONLY on purpose. A track that has VANISHED must NOT re-mux: `work/<id>/` cleanup
    deletes binaries after a successful mux (PLAN), and hardlinked baselines in `work-exp/`
    can even arrive with an OLDER mtime than the output, so a symmetric comparison would
    silently strip the RU track out of an MKV that already shipped it. Losing a track is only
    ever an explicit operator act; gaining one is the pipeline finishing its job.
    """
    stamped = stamped or {}
    return sorted(k for k, v in (now or {}).items() if v and not stamped.get(k))


class MuxStage:
    name = "mux"

    def done(self, ctx: Context) -> bool:
        if not ctx.work.output.exists():
            return False
        try:                                               # make-style freshness: a re-assembled
            for dep in (ctx.work.dub_audio, ctx.work.source_bed,    # dub, a new bed or a
                        ctx.work.en_srt, ctx.work.ru_srt):          # rewritten srt re-muxes
                if dep.exists() and dep.stat().st_mtime > ctx.work.output.stat().st_mtime:
                    print(f"       [info] mux: {dep.name} newer than output.mkv — re-muxing",
                          file=sys.stderr)
                    return False
        except OSError:
            return False
        try:
            rep = json.loads(ctx.work.report.read_text(encoding="utf-8"))
            stamp = rep.get("mux") or {}
        except Exception:
            return True                                    # legacy/torn report → keep old gate
        # BEFORE the manifest read, which is the point: a degraded workdir has no manifest, and
        # the old order (read the manifest first, let its absence fall into `except: pass`)
        # would skip every gate below it — i.e. a dub-less output.mkv would stay forever even
        # once the dub arrived. mtime covers the common case; this covers an artifact that
        # arrives with an older mtime (a hardlinked baseline).
        gained = gained_tracks(stamp.get("tracks"), tracks_on_disk(ctx.work))
        if stamp.get("tracks") is not None and gained:
            print(f"       [info] mux: {', '.join(gained)} now present — re-muxing",
                  file=sys.stderr)
            return False
        try:
            man = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
        except Exception:
            return True                                    # no manifest → nothing else to gate on
        if stamp.get("dub_mix") != ctx.cfg.dub_mix:
            print(f"       [info] mux: dub_mix changed ({stamp.get('dub_mix')} → "
                  f"{ctx.cfg.dub_mix}) — re-muxing", file=sys.stderr)
            return False
        if stamp.get("synth_key") and stamp["synth_key"] != man.get("synth_key"):
            print("       [info] mux: manifest synth_key changed — re-muxing", file=sys.stderr)
            return False
        return True

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH — required for mux. "
                               "Install ffmpeg; overdub does not auto-install.")
        w = ctx.work
        if not w.source_video.exists():
            # the ONE hard input: without a video stream there is no container to degrade into
            raise RuntimeError(f"mux input missing: {w.source_video} — run download first")
        if cfg.dub_mix not in ("replace", "duck", "bed"):
            raise ValueError(f"unknown dub_mix: {cfg.dub_mix!r}")
        tracks = tracks_on_disk(w)
        subs = [(lang, p) for lang, p in (("eng", w.en_srt), ("rus", w.ru_srt)) if p.exists()]
        missing = [name for name, present in (("dub_ru.wav", tracks["dub"]),
                                              ("en.srt", tracks["en_srt"]),
                                              ("ru.srt", tracks["ru_srt"])) if not present]
        if missing:
            print(f"       [warn] mux: DEGRADED — {', '.join(missing)} missing; the MKV ships "
                  f"without {'those tracks' if len(missing) > 1 else 'that track'}",
                  file=sys.stderr)
        if tracks["dub"]:
            if cfg.dub_mix == "bed" and not w.source_bed.exists():
                raise RuntimeError(
                    "source_bed.wav missing — run separate before mux (dub_mix=bed)")
            if not w.seg_manifest.exists():
                # INCONSISTENT, not missing: a dub exists, so the unit spans that decide the
                # duck envelope and the loudness reference must exist too. Guessing them would
                # ship a wrongly-mixed track, which is the one thing degrading may not do.
                raise RuntimeError("segments/manifest.json missing while dub_ru.wav exists — "
                                   "re-run synthesize/assemble (mux needs the unit spans)")
            man = json.loads(w.seg_manifest.read_text(encoding="utf-8"))
        else:
            man = {}

        dub48 = w.root / "_mix_dub48.wav"
        orig48 = w.root / "_mix_orig48.wav"
        bed48 = w.root / "_mix_bed48.wav"
        mix_wav = w.root / "_mix_ru.wav"
        gain = 1.0
        try:
            if tracks["dub"]:
                _extract(w.dub_audio, dub48)               # 24k mono → 48k stereo
                dub, _ = sf.read(str(dub48), dtype="float32")
                _extract(w.source_video, orig48)           # original: gain reference (+ duck base)
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
                gain = _dub_gain(orig, dub, spans)         # loudness ref is ALWAYS the original
                dub *= gain
                if cfg.dub_mix == "bed":
                    _extract(w.source_bed, bed48)
                    base = sf.read(str(bed48), dtype="float32")[0]
                    del orig
                else:
                    base = orig

                n = max(len(base), len(dub))               # the dub may outlast the video
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
                else:                                      # bed
                    base *= _BED_GAIN
                    base += dub
                    mix = base
                peak = 0.0                                 # chunked: no full |mix| copy
                flat = mix.reshape(-1)
                for i in range(0, flat.size, _CHUNK):
                    c = flat[i:i + _CHUNK]
                    peak = max(peak, float(c.max(initial=0.0)), float(-c.min(initial=0.0)))
                if peak > 0.99:                            # summing headroom guard
                    mix *= 0.99 / peak
                sf.write(str(mix_wav), mix, _MIX_SR, format="WAV", subtype="PCM_16")
                del base, dub, mix, flat

            tmp = w.output.with_suffix(".mkv.tmp")
            subprocess.run(
                mux_args(w.source_video, dub=(mix_wav if tracks["dub"] else None),
                         subs=subs, out=tmp, dub_mix=cfg.dub_mix),
                check=True,
            )
            # artifact flips BEFORE the stamp (assemble's "done-gate flips LAST" discipline):
            # a crash between them leaves new-mkv + old-stamp → harmless idempotent re-mux;
            # stamp-first would ship the OLD mix labeled as the new mode after a failed swap
            replace_retry(tmp, w.output)
            rep = report.load(w.report)
            rep["mux"] = {"dub_mix": cfg.dub_mix, "synth_key": man.get("synth_key"),
                          # what the container ACTUALLY carries. done() re-muxes on a gained
                          # track, and run.json reads it to mark a dub-less export for triage —
                          # the export name is unchanged, so this stamp is the only record
                          "tracks": tracks,
                          "dub_gain_db": (round(20 * float(np.log10(gain)), 2)
                                          if tracks["dub"] else None)}
            report.save(w.report, rep)
        finally:
            for p in (dub48, orig48, bed48, mix_wav, w.output.with_suffix(".mkv.tmp")):
                p.unlink(missing_ok=True)
        shipped = "dub_mix=" + cfg.dub_mix if tracks["dub"] else "NO DUB"
        print(f"       → {w.output.name} ({shipped}, subs: "
              f"{'+'.join(lang for lang, _ in subs) or 'none'})")
