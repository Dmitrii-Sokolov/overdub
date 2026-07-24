"""F5 `nfe_step` sweep harness — renders REAL production units at several nfe values and
emits a BLIND A/B listening page per candidate. Built for the F5 speedup (lever ledger:
DECISIONS 2026-07-19).

MEASURES PER CELL, NOT OFF A STAGE WALL CLOCK. `wall_s` is taken around `engine.synthesize`
alone and `startup_s` — the worker spawn — is recorded separately and excluded. That is why the
`nfe` 48→16 = 2.16x figure survives the 2026-07-21 timing-accounting review: it never billed a
model load to a video in the first place. Stage-level numbers measured off `timings.json`
BEFORE the per-stage `detail` entries existed do not have that property.

Run with the .venv-asr python from the repo root (it spawns the .venv-f5tts worker itself):

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\exp_nfe_sweep.py --dry-run
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\exp_nfe_sweep.py
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\exp_nfe_sweep.py --pages-only

Read-only w.r.t. the pipeline: it imports overdub but mutates no config and writes nothing
under `work/` — every byte lands in `--out` (default `work-exp/nfe-sweep/`, gitignored).
Progress prints are intentional (CLI experiment script, same as exp_clone_synth.py).

WHY THIS SHAPE
--------------
F5 is deterministic for a fixed (text, seed, speed, nfe): the worker calls
torch.manual_seed per request. Re-rendering one cell therefore adds NO information, so
coverage comes from MORE TEXTS, never from repeats. The only repeat in this harness is the
`--recheck` pass, which exists to falsify that determinism claim (and to measure thermal
drift), not to average anything.

nfe is a worker SPAWN argument (`--nfe`), so the loop is outer=nfe / inner=unit: one worker
per nfe value, ~30 s startup each, and never two F5 workers alive at once (12 GB budget;
whisper-small stays co-resident, which is the CLAUDE.md-blessed exception).

SAMPLE SELECTION (disjoint strata, rarest-first assignment; see `_STRATA`)
Real units from `work/*/segments/manifest.json`, rendered at their real target_sec/max_sec
so `plan_speed` reproduces the exact speed production used. A sweep on synthetic sentences
at speed=1.0 would measure a regime we never ship.

METRIC SEMANTICS — what each possible movement could mean, and whether the metric can tell
the good cause from the bad one. (The `no_repeat_ngram_size` sweep was rejected partly
because its third axis, word count, could not separate "removed a duplicate" from "ate real
speech". Every axis below is stated against that bar.)

  wall_s ...... The treatment effect itself, not a quality signal. DOWN is the intended
                result and cannot be bad on its own. Down MORE than the nfe ratio predicts
                is suspicious (truncated canvas) — only readable jointly with duration_s.
                UP means thermal throttling or a respawn; `--recheck` is what disambiguates.

  duration_s .. The one axis with a ZERO expectation. F5's duration canvas is
                ref_sec * gen_bytes / ref_bytes / speed — it does not depend on nfe. So any
                movement is a BUG signal, not a quality signal, and its direction is
                unambiguous: shrink + sim drop = truncation (ate speech); shrink + sim flat
                = trailing-silence trim; any change at all = something other than nfe moved
                (speed drift, chunking fired, ref clip changed). This is the axis the ngram
                sweep lacked: expected movement is zero, so movement is self-interpreting.

  sim ......... Round-trip ASR similarity (the pipeline's own asr.roundtrip_similarity +
                normalize.normalize_for_compare, whisper-small). A CATASTROPHE TRIPWIRE, not
                a ranking. Three separate reasons it cannot deliver the verdict:
                (a) Ceiling. Measured over 527 production units: min 0.924, p50 0.995, zero
                    below the 0.9 gate, zero reseed retries ever fired. There is almost no
                    dynamic range left to lose in the good region.
                (b) Direction is not meaning. A flatter, more robotic, over-smoothed reading
                    is EASIER for ASR to transcribe. sim going UP is fully compatible with
                    the audio getting worse. It must never be read as "better".
                (c) Small moves are noise. 0.995 -> 0.985 on a different waveform is inside
                    whisper's own beam-search arbitrariness; it cannot separate "slightly
                    worse diction" from "whisper picked a different homophone this time".
                Actionable only at the extreme: below `similarity_threshold` (0.9), or a
                drop > `_SIM_ALARM` vs control. Those get reported LOUD. A sweep where sim
                does not move is the EXPECTED outcome and proves nothing — the ear decides.

  hyp ......... The raw ASR hypothesis string, stored per cell. Not scored. This is the
                lesson from the ngram sweep made concrete: a suspicious number must be
                inspectable as text, so "what actually changed in the words" is a diff, not
                an inference from a count.

  peak_dbfs ... RECORDED BUT NEVER ALARMED ON, and the reason matters. Measured over 120
                production wavs: 108 peak at exactly 1.0 and 109 above 0.99 — F5/vocos output
                is peak-normalized by construction. The axis is PINNED, so it cannot detect
                clipping (everything looks clipped) and a "peak >= -0.1 dBFS" tripwire would
                fire on ~90% of cells and bury the real alarms. Kept in the CSV only because
                a value that stopped being ~0 dBFS would itself be news.
                Useful side effect: with both variants normalized to full scale there is no
                systematic loudness cue, so the blind A/B cannot be won on level alone.

  rms_dbfs .... The level axis that DOES carry signal, but only as a same-text delta against
                control (peak being pinned makes rms a crude dynamic-range proxy). Same text,
                same duration, same speed => the two variants should land within ~1 dB. A
                drop past `_RMS_ALARM` means the output went quiet or degenerate, which is
                the failure ASR is blindest to: whisper will happily hallucinate plausible
                text over near-silence and score a high sim. BINARY tripwire, not a gradient
                — sub-dB moves are meaningless and must not be ranked on. Absolute rms is NOT
                comparable across different units and is never alarmed on.

  wav_sha256 .. Expected movement ZERO across a repeat of the same cell. Non-zero falsifies
                the determinism premise that licenses "no repeat cells", which would
                invalidate the whole design. Cheapest high-value check here.

  DELIBERATELY NOT RECORDED: hypothesis word count (the exact axis that sank the ngram
  sweep — superseded by storing `hyp` verbatim plus the zero-expectation duration axis); any
  UTMOS/MOS proxy (Deferred in PLAN; a learned score with no validated relationship to this
  artifact class would get laundered into the verdict the ear is supposed to give).
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import html
import json
import math
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub.asr import load_whisper, roundtrip_similarity          # noqa: E402
from overdub.config import Config                                   # noqa: E402
from overdub.normalize import normalize_for_compare                 # noqa: E402
from overdub.tts.base import TtsFatalError                          # noqa: E402
from overdub.tts.f5 import F5Engine                                 # noqa: E402
from overdub.workdir import replace_retry                           # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

_LATIN = re.compile(r"[A-Za-z]")
_DIGIT = re.compile(r"[0-9]")


def _latin_density(r: dict) -> float:
    """Share of Latin+digit characters in the SOURCE Russian translation.

    The `translit` stratum ranks on this rather than on text length: density is what drives the
    hand-normalized respelling that F5 never saw in training (the «калл оф дутй» class), and it
    is anti-correlated with length, so ranking by length selects against the property.
    Measured on the corpus: pool mean 0.056, max 0.409.
    """
    ru = r.get("text_ru") or ""
    if not ru:
        return 0.0
    hits = len(_LATIN.findall(ru)) + len(_DIGIT.findall(ru))
    return hits / len(ru)

# Cost model from the on-disk baseline probe (12 workdirs, 6 direct fixed-cost measurements):
#   unit_s ~= _DIT_S_PER_CANVAS_S * (nfe/48) * (_REF_SEC + duration) + _ASR_S
# Used ONLY for the pre-flight ETA print; nothing downstream depends on it.
_REF_SEC = 9.164             # recovered by inverting plan_speed over 326 unclamped units
_DIT_S_PER_CANVAS_S = 0.2176
_ASR_S = 0.295               # whisper-small round-trip, from verify ~ 1 + units (R^2 0.899)
_STARTUP_S = 34.8            # worker spawn + whisper load, median of 6 clean measurements

_SIM_ALARM = 0.05            # sim drop vs control that gets reported LOUD
_DUR_ALARM = 0.01            # fractional duration drift vs control that gets reported LOUD
_RMS_ALARM = 3.0             # dB rms move vs control. Same text/duration/speed should land
                             # within ~1 dB; 3 dB is "the output went quiet or degenerate".
                             # NOTE there is deliberately no peak/clipping alarm — see the
                             # peak_dbfs entry in the module docstring (the axis is pinned at
                             # full scale by F5's own normalization, measured 108/120).
_LISTEN_SALT = "overdub-nfe-sweep-2026-07"

# Disjoint strata, assigned RAREST-FIRST so the diagnostic classes are never crowded out by
# the bulk. Each entry: (name, predicate, quota, ranking key -- lower sorts first).
# Rationale per stratum is in the module docstring's selection section and in README of the
# emitted index.html.
_STRATA: list[tuple] = [
    # 10 units in the whole corpus sit under 0.95. These are the ones closest to the 0.9
    # gate today, so they are where a degradation first becomes OBSERVABLE rather than
    # merely audible.
    ("lowsim", lambda r: r["sim"] is not None and r["sim"] < 0.96, 5,
     lambda r: r["sim"]),
    # The bakeoff transliteration class ("калл оф дутй"): text_ru carried Latin or digits, so
    # text_tts is a hand-normalized Cyrillic respelling the model has never seen in training.
    # 77/527 units. Historically the first thing to break on any TTS change.
    # RANK BY DENSITY, NOT LENGTH. Ranking by -len picked the six LONGEST texts of the pool,
    # where a Latin run is one speck in 250 Cyrillic chars: measured mean density 0.022 against
    # the pool's 0.056, and the corpus's most extreme unit (W4Ua6XFfX9w_00000, 41% Latin) was
    # not selected at all. Length and density are anti-correlated, so the old key actively
    # selected AGAINST the very property this stratum exists to cover.
    ("translit", lambda r: r["lat"] or r["dig"], 6,
     lambda r: (-_latin_density(r), r["key"])),
    # Native compression at/near f5_speed_ceil. Highest-risk regime by prior evidence: native
    # speed >=~1.3 already DROPS words mid-word (DECISIONS 2026-07-16). Fewer denoise steps
    # under compression is the single most plausible way nfe reduction breaks something.
    ("compressed", lambda r: (r["speed"] or 0) >= 1.09, 6,
     lambda r: (-(r["speed"] or 0), r["key"])),
    # The opposite extreme: pinned at f5_speed_floor (0.75), canvas stretched, acoustic
    # evidence per frame thinnest.
    ("stretched", lambda r: (r["speed"] or 1) <= 0.755, 5,
     lambda r: ((r["speed"] or 1), r["key"])),
    # Shortest units (7.2% of corpus). The ref canvas dominates the trajectory here, and F5
    # forces local_speed=0.3 under 10 UTF-8 bytes -- a different regime, not a smaller one.
    ("short", lambda r: (r["dur"] or 0) < 3.0, 6,
     lambda r: ((r["dur"] or 0), r["key"])),
    # Longest units: most tokens per trajectory, nearest the internal-chunking boundary and
    # the model's trained <=30 s regime.
    ("long", lambda r: (r["dur"] or 0) >= 10.0, 6,
     lambda r: (-(r["dur"] or 0), r["key"])),
    # The bulk (293/527). Without this the sweep would measure only the tails and miss the
    # regime that actually ships.
    ("medium", lambda r: True, 6,
     lambda r: (abs((r["dur"] or 0) - 6.5), r["key"])),
]


# --- corpus -----------------------------------------------------------------------------
def load_corpus(work_root: Path) -> list[dict]:
    """Every rendered unit across every workdir, joined to its translation record.

    A workdir with no manifest (never synthesized) or an unreadable translation.json is
    SKIPPED with a note -- this is a read-only probe over whatever happens to be on disk,
    not a gate.
    """
    rows: list[dict] = []
    for manifest in sorted(Path(work_root).glob("*/segments/manifest.json")):
        wd = manifest.parents[1]
        try:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            segs = json.loads((wd / "translation.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"  [skip] {wd.name}: {e}")
            continue
        by_id = {s["id"]: s for s in segs}
        for u in doc.get("units", []):
            text = (u.get("text_tts") or "").strip()
            if not text or u.get("flag"):
                continue                                   # empty slots / synth_error carry no signal
            ids = u["ids"]
            if any(i not in by_id for i in ids):
                continue                                   # manifest predates the translation
            ru = " ".join((by_id[i].get("text_ru") or "") for i in ids)
            rows.append({
                "key": f"{wd.name}_{ids[0]:05d}",
                "vid": wd.name, "ids": ids, "text": text,
                "text_ru": ru, "src_en": " ".join((by_id[i].get("src_en") or "") for i in ids),
                "dur": u.get("duration"), "target_sec": u.get("target_sec"),
                "max_sec": u.get("max_sec"), "speed": u.get("speed"),
                "sim": u.get("synth_sim"),
                "lat": bool(_LATIN.search(ru)), "dig": bool(_DIGIT.search(ru)),
            })
    return rows


def select_sample(rows: list[dict]) -> list[dict]:
    """Deterministic stratified pick. Disjoint: a unit lands in the FIRST stratum (in
    _STRATA order, rarest/most-diagnostic first) whose predicate it satisfies, so the bulk
    never crowds out the diagnostic classes. Within a stratum, units are ordered by that
    stratum's ranking key and taken round-robin across videos, so no single video can
    dominate a stratum (12 videos, 5-6 slots each)."""
    taken: set[str] = set()
    out: list[dict] = []
    for name, pred, quota, rank in _STRATA:
        pool = sorted([r for r in rows if r["key"] not in taken and pred(r)], key=rank)
        # round-robin by video: walk the ranked pool repeatedly, taking at most one per
        # video per lap, until the quota is met or the pool is exhausted
        picked: list[dict] = []
        lap_seen: set[str] = set()
        remaining = list(pool)
        while remaining and len(picked) < quota:
            nxt = [r for r in remaining if r["vid"] not in lap_seen]
            if not nxt:                                    # every video used this lap
                lap_seen.clear()
                continue
            r = nxt[0]
            picked.append(r)
            lap_seen.add(r["vid"])
            remaining.remove(r)
        for r in picked:
            taken.add(r["key"])
            tags = [n for n, p, _q, _k in _STRATA if p(r) and n != "medium"]
            out.append({**r, "stratum": name, "tags": tags or ["medium"]})
    return out


# --- rendering --------------------------------------------------------------------------
def _wav_stats(path: Path) -> dict:
    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    n = int(data.size)
    peak = float(np.max(np.abs(data))) if n else 0.0
    rms = float(np.sqrt(np.mean(np.square(data, dtype=np.float64)))) if n else 0.0
    # None (not -inf) for digital silence: json.dumps would emit `-Infinity`, which is not
    # valid JSON for anything downstream that is stricter than Python's own loader
    dbfs = lambda v: (round(20 * math.log10(v), 2) if v > 0 else None)             # noqa: E731
    return {"samples": n, "sample_rate": int(sr), "duration_s": round(n / sr, 3) if sr else 0.0,
            "peak_dbfs": dbfs(peak), "rms_dbfs": dbfs(rms),
            "wav_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _cell_done(wav: Path, meta: Path) -> bool:
    """A cell is resumable-complete only if BOTH artifacts exist and agree on length --
    a crash between the wav flip and the metric write must re-render, not resume half."""
    if not (wav.exists() and meta.exists()):
        return False
    try:
        m = json.loads(meta.read_text(encoding="utf-8"))
        return m.get("samples") == sf.info(str(wav)).frames and m.get("error") is None
    except Exception:
        return False


def _write_json(path: Path, doc: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    replace_retry(tmp, path)


# One-shot guard: the regime check runs on the first cell that carries a manifest speed, then
# stays quiet (every later cell still records its own drift, and the rollup still reports it).
_preflight = {"pending": True}


def render_grid(sample: list[dict], nfes: list[int], out: Path, cfg: Config,
                verifier, *, tag: str = "") -> None:
    """One F5 worker per nfe (outer loop), every unit through it (inner loop). Never two
    workers alive: the engine is closed before the next nfe spawns."""
    for nfe in nfes:
        cell_dir = out / f"nfe{nfe}"
        cell_dir.mkdir(parents=True, exist_ok=True)
        todo = [r for r in sample
                if not _cell_done(cell_dir / f"{r['key']}.wav", cell_dir / f"{r['key']}.json")]
        if not todo:
            print(f"  nfe={nfe}{tag}: all {len(sample)} cells present — skipped")
            continue
        print(f"  nfe={nfe}{tag}: {len(todo)}/{len(sample)} cells to render "
              f"(spawning worker, ~30 s) ...")
        t_spawn = time.perf_counter()
        engine = F5Engine(
            python=cfg.f5_python, ckpt=cfg.f5_ckpt, vocab=cfg.f5_vocab,
            ref_audio=cfg.f5_ref_audio, ref_text=cfg.f5_ref_text,
            nfe=nfe, speed=cfg.f5_speed, default_seed=cfg.tts_seed,
            speed_floor=cfg.f5_speed_floor, speed_ceil=cfg.f5_speed_ceil)
        startup_s = round(time.perf_counter() - t_spawn, 2)
        print(f"    worker up in {startup_s:.1f}s")
        try:
            for n, r in enumerate(todo, 1):
                wav = cell_dir / f"{r['key']}.wav"
                meta = cell_dir / f"{r['key']}.json"
                tmp = wav.with_suffix(".wav.tmp")
                # t_wall is LOAD-BEARING and unrecoverable after the fact: nfe blocks run
                # sequentially, so block order is fully confounded with elapsed time (and the
                # GPU's thermal state — DECISIONS records RTF 0.39 cold vs ~0.60 hot). With a
                # per-cell timestamp the confound becomes ESTIMABLE post-hoc by regressing
                # wall_s on the nfe term plus elapsed; without it, it is simply unknown.
                rec = {"key": r["key"], "nfe": nfe, "stratum": r["stratum"],
                       "session": SESSION, "startup_s": startup_s, "error": None,
                       "t_wall": round(time.time(), 3)}
                try:
                    t0 = time.perf_counter()
                    speed_eff = engine.synthesize(
                        r["text"], tmp, seed=cfg.tts_seed,
                        target_sec=r["target_sec"], max_sec=r["max_sec"])
                    rec["wall_s"] = round(time.perf_counter() - t0, 3)
                    replace_retry(tmp, wav)
                except TtsFatalError:
                    raise                                  # engine/driver is down — abort LOUD
                except Exception as e:
                    print(f"    [flag] {r['key']}: synth_error {e}", file=sys.stderr)
                    tmp.unlink(missing_ok=True)
                    wav.unlink(missing_ok=True)
                    _write_json(meta, {**rec, "error": f"synth: {e}"})
                    continue
                try:
                    rec.update(_wav_stats(wav))
                except Exception as e:                     # unreadable wav (AV lock, torn write)
                    print(f"    [flag] {r['key']}: unreadable wav {e}", file=sys.stderr)
                    _write_json(meta, {**rec, "error": f"wav: {e}"})
                    continue                               # one bad cell must not kill the sweep
                rec["speed_eff"] = round(float(speed_eff), 4)
                # plan_speed is nfe-independent, so this MUST equal what production recorded.
                # Drift means the ref clip or the slot inputs moved -> the comparison is not
                # against the shipped regime any more. Recorded, never silently swallowed.
                rec["speed_manifest"] = r["speed"]
                rec["speed_drift"] = (round(rec["speed_eff"] - r["speed"], 4)
                                      if r["speed"] is not None else None)
                # PRE-FLIGHT: fail on the FIRST cell, not in the rollup 10 minutes later.
                # plan_speed is nfe-independent, so a drift here means the ref clip or the slot
                # inputs moved and every cell after this one would be measured against a regime
                # that was never shipped. 30 s wasted instead of a whole sweep.
                if _preflight["pending"] and rec["speed_drift"] is not None:
                    _preflight["pending"] = False
                    if abs(rec["speed_drift"]) > 1e-3:
                        raise SystemExit(
                            f"[ABORT] {r['key']}: speed_eff {rec['speed_eff']} != manifest "
                            f"{r['speed']} (drift {rec['speed_drift']}). plan_speed is "
                            f"nfe-independent, so the ref clip / slot inputs have moved since "
                            f"production — this sweep would not be measuring the shipped "
                            f"regime. Check cfg.f5_ref_audio / f5_ref_text against the run that "
                            f"produced work/*/segments/manifest.json.")
                ref_norm = normalize_for_compare(r["text"])
                try:
                    sim, hyp, _hn = roundtrip_similarity(verifier, wav, ref_norm, cfg.target_lang)
                    rec["sim"], rec["hyp"] = round(sim, 4), hyp
                except Exception as e:                     # round-trip broke, audio didn't
                    print(f"    [warn] {r['key']}: round-trip failed ({e})", file=sys.stderr)
                    rec["sim"], rec["hyp"] = None, None
                _write_json(meta, rec)
                print(f"    [{n:>3}/{len(todo)}] {r['key']:<22} {rec['wall_s']:6.2f}s  "
                      f"out {rec['duration_s']:5.2f}s  sim {rec['sim']}")
        finally:
            engine.close()


# --- rollup -----------------------------------------------------------------------------
def rollup(sample: list[dict], nfes: list[int], out: Path, control: int) -> dict:
    cells: dict[tuple[str, int], dict] = {}
    for nfe in nfes:
        for r in sample:
            meta = out / f"nfe{nfe}" / f"{r['key']}.json"
            if meta.exists():
                try:
                    cells[(r["key"], nfe)] = json.loads(meta.read_text(encoding="utf-8"))
                except ValueError:
                    pass

    rows: list[dict] = []
    alarms: list[str] = []
    for r in sample:
        base = cells.get((r["key"], control))
        for nfe in nfes:
            c = cells.get((r["key"], nfe))
            if c is None:
                continue
            row = {"key": r["key"], "vid": r["vid"], "stratum": r["stratum"],
                   "tags": "+".join(r["tags"]), "nfe": nfe,
                   "chars": len(r["text"]), "bytes": len(r["text"].encode("utf-8")),
                   "speed": c.get("speed_eff"), "speed_drift": c.get("speed_drift"),
                   "wall_s": c.get("wall_s"), "duration_s": c.get("duration_s"),
                   "samples": c.get("samples"), "sim": c.get("sim"),
                   "peak_dbfs": c.get("peak_dbfs"), "rms_dbfs": c.get("rms_dbfs"),
                   "session": c.get("session"), "error": c.get("error")}
            if base and nfe != control and not c.get("error") and not base.get("error"):
                if c.get("sim") is not None and base.get("sim") is not None:
                    row["d_sim"] = round(c["sim"] - base["sim"], 4)
                    if c["sim"] < 0.9:
                        alarms.append(f"nfe{nfe} {r['key']}: sim {c['sim']:.3f} below the 0.9 gate")
                    elif row["d_sim"] <= -_SIM_ALARM:
                        alarms.append(f"nfe{nfe} {r['key']}: sim {base['sim']:.3f} -> "
                                      f"{c['sim']:.3f} (drop {-row['d_sim']:.3f})")
                if base.get("duration_s"):
                    dd = (c["duration_s"] - base["duration_s"]) / base["duration_s"]
                    row["d_dur_pct"] = round(100 * dd, 3)
                    if abs(dd) > _DUR_ALARM:
                        alarms.append(f"nfe{nfe} {r['key']}: duration moved {100 * dd:+.2f}% "
                                      f"— nfe must NOT change the canvas; investigate")
                if base.get("wall_s"):
                    row["speedup_x"] = round(base["wall_s"] / c["wall_s"], 3) if c.get("wall_s") else None
                # rms is only meaningful as a same-text delta (peak is pinned at full scale by
                # F5's normalization, so absolute level says nothing) — see the docstring
                if c.get("rms_dbfs") is None:              # digital silence (dbfs() -> None)
                    alarms.append(f"nfe{nfe} {r['key']}: SILENT output (rms is zero)")
                elif base.get("rms_dbfs") is not None:
                    row["d_rms_db"] = round(c["rms_dbfs"] - base["rms_dbfs"], 2)
                    if abs(row["d_rms_db"]) > _RMS_ALARM:
                        alarms.append(f"nfe{nfe} {r['key']}: rms moved {row['d_rms_db']:+.1f} dB "
                                      f"— output may be quiet/degenerate (ASR is blind to this)")
            if c.get("speed_drift") not in (None, 0) and abs(c["speed_drift"]) > 1e-3:
                alarms.append(f"nfe{nfe} {r['key']}: speed {c['speed_manifest']} -> "
                              f"{c['speed_eff']} vs the shipped manifest — regime drift")
            rows.append(row)

    per_nfe: list[dict] = []
    for nfe in nfes:
        rs = [x for x in rows if x["nfe"] == nfe and not x["error"]]
        walls = [x["wall_s"] for x in rs if x["wall_s"]]
        sims = [x["sim"] for x in rs if x["sim"] is not None]
        base_walls = [x["wall_s"] for x in rows
                      if x["nfe"] == control and not x["error"] and x["wall_s"]]
        per_nfe.append({
            "nfe": nfe, "n_cells": len(rs),
            "wall_total_s": round(sum(walls), 2),
            "wall_mean_s": round(sum(walls) / len(walls), 3) if walls else None,
            "speedup_vs_control": (round(sum(base_walls) / sum(walls), 3)
                                   if walls and base_walls else None),
            "sim_mean": round(sum(sims) / len(sims), 4) if sims else None,
            "sim_min": min(sims) if sims else None,
            "n_below_gate": sum(1 for s in sims if s < 0.9),
        })

    doc = {"control_nfe": control, "nfes": nfes, "n_units": len(sample),
           "session": SESSION, "per_nfe": per_nfe, "alarms": alarms, "cells": rows}
    _write_json(out / "results.json", doc)
    cols = ["key", "vid", "stratum", "tags", "nfe", "chars", "bytes", "speed", "speed_drift",
            "wall_s", "duration_s", "samples", "sim", "d_sim", "d_dur_pct", "speedup_x",
            "peak_dbfs", "rms_dbfs", "d_rms_db", "session", "error"]
    tmp = (out / "results.csv").with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    replace_retry(tmp, out / "results.csv")
    return doc


def recheck(sample: list[dict], out: Path, cfg: Config, verifier, control: int, n: int,
            nfes: list[int]) -> None:
    """Re-render the first `n` control cells into recheck/ at the END of the run.

    NOT a repeat for averaging (F5 is deterministic — that would add nothing). Two jobs:
      1. FALSIFY the determinism premise. Identical bytes are expected; a mismatch means
         "one render per cell is sufficient" is false and the sweep design is invalid.
      2. Measure thermal drift. The control runs first and the low-nfe cells run last, so a
         hot GPU would understate the speedup. This puts a number on that.
    """
    # STRATIFIED, not sample[:n]: the sample is ordered by _STRATA, so sample[:6] was
    # lowsim x5 + translit x1 — determinism got checked on one class and never on the long
    # units, which sit nearest the internal-chunking boundary where a nondeterministic path
    # would most plausibly live.
    sub = listen_subset(sample, n)
    rc = out / "recheck"
    # Check BOTH schedule paths. nfe in {5,6,7,10,12,16} takes get_epss_timesteps' tuned table,
    # every other value falls through to naive linspace — different code, and the low-nfe path
    # is exactly the one the probes recommend adopting. Verifying determinism only on the
    # control would leave the recommended setting's premise untested.
    epss = next((x for x in nfes if x in (5, 6, 7, 10, 12, 16)), None)
    checks = [control] + ([epss] if epss is not None else [])
    render_grid(sub, checks, rc, cfg, verifier, tag=" (recheck)")
    same = diff = 0
    per_nfe: dict[int, list[float]] = {}
    for nfe in checks:
        for r in sub:
            a = out / f"nfe{nfe}" / f"{r['key']}.json"
            b = rc / f"nfe{nfe}" / f"{r['key']}.json"
            if not (a.exists() and b.exists()):
                continue
            ja, jb = (json.loads(p.read_text(encoding="utf-8")) for p in (a, b))
            if ja.get("wav_sha256") and ja["wav_sha256"] == jb.get("wav_sha256"):
                same += 1
            else:
                diff += 1
                print(f"  [ALARM] {r['key']} nfe={nfe}: recheck bytes DIFFER — F5 is not "
                      f"deterministic for a fixed (text, seed, speed, nfe); the no-repeat "
                      f"design is invalid", file=sys.stderr)
            if ja.get("wall_s") and jb.get("wall_s"):
                per_nfe.setdefault(nfe, []).append(jb["wall_s"] / ja["wall_s"])
    ratios = {k: round(sum(v) / len(v), 3) for k, v in per_nfe.items() if v}
    md = ratios.get(control)
    print(f"  recheck: {same} identical, {diff} differing (nfe {checks}); "
          f"wall-time ratio hot/cold = {ratios} (>1 means the GPU slowed down over the run)")
    _write_json(out / "recheck.json",
                {"control_nfe": control, "checked_nfe": checks, "n": len(sub),
                 "identical": same, "differing": diff, "thermal_wall_ratio": md,
                 "thermal_wall_ratio_by_nfe": ratios, "session": SESSION})


# --- blind A/B listening page -----------------------------------------------------------
_PAGE_CSS = """
:root { color-scheme: dark; }
body { font-family: system-ui, sans-serif; margin: 0 auto; padding: 2rem 1.5rem 6rem;
       max-width: 62rem; background: #14161a; color: #e8e8e8; }
h1 { font-size: 1.25rem; margin: 0 0 .3rem; }
.note { font-size: .82rem; color: #9aa; line-height: 1.5; max-width: 52rem; margin: .6rem 0 1.6rem; }
.note b { color: #cde; }
.row { border: 1px solid #2a2f36; border-radius: 8px; padding: .9rem 1rem; margin: 0 0 .9rem;
       background: #181b20; }
.row.done { border-color: #2f4a3a; background: #171d1a; }
.meta { font-size: .72rem; color: #7f8a95; margin-bottom: .45rem;
        display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; }
.tag { background: #222a33; color: #9fb3c8; border-radius: 4px; padding: .1rem .4rem; }
.text { font-size: .9rem; color: #d5d9de; margin-bottom: .75rem; line-height: 1.45; }
.ctl { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; }
button { font: inherit; font-size: .85rem; padding: .42rem .85rem; border-radius: 6px;
         border: 1px solid #39414b; background: #232830; color: #e8e8e8; cursor: pointer; }
button:hover { background: #2c333c; }
button.play { min-width: 5.2rem; font-variant-numeric: tabular-nums; }
button.play.on { background: #2b4a63; border-color: #3d6a8c; }
.vote { margin-left: auto; display: flex; gap: .4rem; }
.vote button.sel { background: #2f5d43; border-color: #47845f; color: #fff; }
.vote button.tie.sel { background: #5a4a26; border-color: #8a7238; }
.bar { position: fixed; left: 0; right: 0; bottom: 0; background: #10131700; backdrop-filter: blur(6px);
       border-top: 1px solid #2a2f36; padding: .6rem 1.5rem; display: flex; gap: .7rem;
       align-items: center; font-size: .82rem; background: #101317ee; }
.bar .grow { flex: 1; color: #9aa; }
textarea { width: 100%; height: 7rem; margin-top: .8rem; background: #0f1215; color: #cfd6dd;
           border: 1px solid #2a2f36; border-radius: 6px; padding: .6rem; font-family: ui-monospace,
           Consolas, monospace; font-size: .75rem; }
.reveal { margin-top: 1.4rem; padding: 1rem; border: 1px dashed #4a3f2a; border-radius: 8px;
          background: #1b1710; font-size: .85rem; }
.hidden { display: none; }
.score { font-size: 1rem; line-height: 1.7; }
"""

_PAGE_JS = r"""
const $ = (s, r) => (r || document).querySelector(s);
// Variant identity and file paths are base64'd in the payload and the <audio> src is wired
// from JS, so a glance at view-source does not spell out "nfe12". This is a don't-trip-over-
// the-answer guard, NOT security: the paths are trivially recoverable, and the authoritative
// mapping lives in key_<pair>.json on purpose.
const dec = s => decodeURIComponent(escape(atob(s)));
const STORE = "nfe-ab:" + DATA.pair;
let votes = {};
try { votes = JSON.parse(localStorage.getItem(STORE) || "{}"); } catch (e) { votes = {}; }
let cur = null, curSide = null;

function save() { try { localStorage.setItem(STORE, JSON.stringify(votes)); } catch (e) {} }

function stopAll() {
  document.querySelectorAll("audio").forEach(a => { a.pause(); a.currentTime = 0; });
  document.querySelectorAll("button.play").forEach(b => b.classList.remove("on"));
  curSide = null;
}

function play(i, side) {
  const wasSame = (cur === i && curSide === side);
  stopAll();
  if (wasSame) return;
  const a = $("#a-" + i + "-" + side);
  a.play();
  $("#b-" + i + "-" + side).classList.add("on");
  cur = i; curSide = side;
}

function vote(i, v) {
  votes[DATA.rows[i].row_key] = v;
  save(); paint();
}

function paint() {
  DATA.rows.forEach((r, i) => {
    const v = votes[r.row_key];
    const row = $("#row-" + i);
    row.classList.toggle("done", !!v);
    ["A", "B", "tie"].forEach(k => {
      $("#v-" + i + "-" + k).classList.toggle("sel", v === k);
    });
  });
  const n = DATA.rows.filter(r => votes[r.row_key]).length;
  $("#progress").textContent = n + " / " + DATA.rows.length + " judged";
  $("#dl").disabled = n === 0;
}

function wire() {
  DATA.rows.forEach((r, i) => {
    $("#a-" + i + "-A").src = dec(r.sa);
    $("#a-" + i + "-B").src = dec(r.sb);
  });
}

function results() {
  return {
    pair: DATA.pair, control_nfe: DATA.control, candidate_nfe: DATA.candidate,
    generated: DATA.generated, judged_at: new Date().toISOString(),
    revealed_at: window.__revealed || null,
    votes: DATA.rows.map(r => ({ row_key: r.row_key, key: r.key, stratum: r.stratum,
                                 choice: votes[r.row_key] || null }))
  };
}

function download() {
  const blob = new Blob([JSON.stringify(results(), null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "verdict_" + DATA.pair + ".json";
  a.click();
}

function reveal() {
  if (!confirm("Reveal which side was which?\n\nDo this only AFTER judging every row you "
             + "intend to judge — the reveal timestamp is written into the exported verdict.")) return;
  window.__revealed = new Date().toISOString();
  let ctl = 0, cand = 0, tie = 0, unjudged = 0;
  DATA.rows.forEach((r, i) => {
    const v = votes[r.row_key];
    const va = dec(r.av), vb = dec(r.bv);
    const winner = v === "tie" ? "tie" : (v === "A" ? va : (v === "B" ? vb : null));
    if (!v) unjudged++; else if (v === "tie") tie++;
    else if (winner === "control") ctl++; else cand++;
    $("#key-" + i).textContent = "A = nfe" + (va === "control" ? DATA.control : DATA.candidate)
      + " · B = nfe" + (vb === "control" ? DATA.control : DATA.candidate)
      + (v ? "  →  you chose " + (v === "tie" ? "cannot tell" : "nfe" +
        (winner === "control" ? DATA.control : DATA.candidate)) : "  →  not judged");
    $("#key-" + i).classList.remove("hidden");
  });
  $("#score").innerHTML =
      "<b>nfe" + DATA.control + " (control) preferred:</b> " + ctl + "<br>"
    + "<b>nfe" + DATA.candidate + " (candidate) preferred:</b> " + cand + "<br>"
    + "<b>cannot tell:</b> " + tie + "<br>"
    + (unjudged ? "<b>not judged:</b> " + unjudged + "<br>" : "")
    + "<br>Decision rule: <i>cannot tell</i> ADOPTS nfe" + DATA.candidate
    + " — it is the faster setting and indistinguishable is a pass. Only a consistent, "
    + "repeatable preference for nfe" + DATA.control + " justifies keeping the slower one.";
  $("#revealBox").classList.remove("hidden");
}

document.addEventListener("keydown", e => {
  if (e.target.tagName === "TEXTAREA" || cur === null) return;
  if (e.key === "a") { play(cur, "A"); e.preventDefault(); }
  if (e.key === "b") { play(cur, "B"); e.preventDefault(); }
  if (e.key === "q") vote(cur, "A");
  if (e.key === "w") vote(cur, "tie");
  if (e.key === "e") vote(cur, "B");
});
wire();
paint();
"""


def _row_key(pair: str, key: str) -> str:
    return hashlib.sha1(f"{_LISTEN_SALT}|{pair}|{key}".encode("utf-8")).hexdigest()[:12]


def _side_flip(pair: str, key: str) -> bool:
    """Deterministic, reproducible coin flip for which variant sits on side A."""
    h = hashlib.sha1(f"{_LISTEN_SALT}|side|{pair}|{key}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 2 == 1


# Listening quotas are RISK-WEIGHTED, not uniform. Flat round-robin gave the two classes
# carrying an actual failure hypothesis (compressed: fewer denoise steps under native
# compression; translit: out-of-training respellings) the same 2 rows as `medium`, which has no
# hypothesis at all — and a regression cannot be detected on 2 rows at any outcome. Quotas are
# capped by what each stratum holds; the remainder is filled round-robin.
_LISTEN_QUOTA = {"compressed": 4, "translit": 4, "lowsim": 2,
                 "stretched": 2, "short": 2, "long": 1, "medium": 1}


def listen_subset(sample: list[dict], n: int, offset: int = 0) -> list[dict]:
    """Deterministic listening subset, risk-weighted across strata (_LISTEN_QUOTA).

    `offset` rotates the window per PAIR so the three pages are not the same 16 texts: with a
    single shared set the listener has the material memorised by the third page, and page 3
    stops being a blind test of anything. Metrics run on the full sample; ears run on this.
    """
    order = [s[0] for s in _STRATA]
    buckets = {}
    for name in order:
        rows = [r for r in sample if r["stratum"] == name]
        if rows and offset:
            k = offset % len(rows)
            rows = rows[k:] + rows[:k]                 # rotate, never drop
        buckets[name] = rows
    out: list[dict] = []
    for name in order:                                 # quota pass first
        take = min(_LISTEN_QUOTA.get(name, 0), len(buckets[name]), max(0, n - len(out)))
        for _ in range(take):
            out.append(buckets[name].pop(0))
    while len(out) < n and any(buckets.values()):      # round-robin fill for the remainder
        for name in order:
            if buckets[name] and len(out) < n:
                out.append(buckets[name].pop(0))
    return out


def emit_page(out: Path, sample: list[dict], control: int, candidate: int, n: int,
              offset: int = 0) -> Path:
    pair = f"nfe{control}_vs_nfe{candidate}"
    subset = listen_subset(sample, n, offset=offset)
    rows, key_rows = [], []
    for r in subset:
        flip = _side_flip(pair, r["key"])
        a_var, b_var = ("candidate", "control") if flip else ("control", "candidate")
        a_nfe = candidate if a_var == "candidate" else control
        b_nfe = candidate if b_var == "candidate" else control
        rk = _row_key(pair, r["key"])
        b64 = lambda s: base64.b64encode(str(s).encode("utf-8")).decode("ascii")   # noqa: E731
        rows.append({"row_key": rk, "key": r["key"], "stratum": r["stratum"],
                     "tags": r["tags"], "text": r["text"],
                     "av": b64(a_var), "bv": b64(b_var),
                     "sa": b64(f"nfe{a_nfe}/{r['key']}.wav"),
                     "sb": b64(f"nfe{b_nfe}/{r['key']}.wav")})
        key_rows.append({"row_key": rk, "key": r["key"], "stratum": r["stratum"],
                         "A": f"nfe{a_nfe}", "B": f"nfe{b_nfe}"})

    generated = time.strftime("%Y-%m-%d %H:%M")
    data = {"pair": pair, "control": control, "candidate": candidate,
            "generated": generated, "rows": rows}

    body = []
    for i, r in enumerate(rows):
        body.append(f"""
<div class="row" id="row-{i}">
  <div class="meta"><span class="tag">{html.escape(r['stratum'])}</span>
    <span>{html.escape('+'.join(r['tags']))}</span><span>#{i + 1}</span></div>
  <div class="text">{html.escape(r['text'])}</div>
  <audio id="a-{i}-A" preload="auto"></audio>
  <audio id="a-{i}-B" preload="auto"></audio>
  <div class="ctl">
    <button class="play" id="b-{i}-A" onclick="play({i},'A')">&#9654; A</button>
    <button class="play" id="b-{i}-B" onclick="play({i},'B')">&#9654; B</button>
    <button onclick="stopAll()">&#9632;</button>
    <span class="vote">
      <button id="v-{i}-A" onclick="vote({i},'A')">A better</button>
      <button id="v-{i}-tie" class="tie" onclick="vote({i},'tie')">cannot tell</button>
      <button id="v-{i}-B" onclick="vote({i},'B')">B better</button>
    </span>
  </div>
  <div class="meta hidden" id="key-{i}"></div>
</div>""")

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>overdub — blind A/B: nfe {control} vs {candidate}</title>
<style>{_PAGE_CSS}</style>
</head>
<body>
<h1>Слепой A/B — F5 nfe {control} против nfe {candidate}</h1>
<p class="note">
  {len(rows)} реальных юнита из production-прогонов, отрисованных с их настоящими
  target_sec/max_sec — то есть с той же самой скоростью, с какой они уходили в дубляж.
  В каждой строке две версии одного текста, <b>порядок A/B рандомизирован построчно</b>:
  по колонке ничего не выучить. Плеер намеренно без таймлайна — длительность трека выдала бы
  вариант.<br>
  <b>«Cannot tell» — полноценный ответ, а не отказ.</b> Правило решения задано заранее:
  неразличимо ⇒ принимаем nfe {candidate} (он быстрее). Чтобы оставить nfe {control},
  нужно устойчивое, повторяющееся предпочтение — не одна строка.<br>
  Слушать в наушниках. Клавиши: <b>a</b>/<b>b</b> — проиграть сторону, <b>q</b>/<b>w</b>/<b>e</b> —
  голос A / cannot tell / B. Ответы сохраняются в localStorage, страницу можно закрыть.
  Ключ соответствия лежит отдельно в <code>key_{pair}.json</code> — не открывайте его до конца.
  Сгенерировано {generated}.
</p>
{''.join(body)}

<div class="reveal">
  <button onclick="reveal()">Раскрыть ключ и посчитать результат</button>
  <span class="note" style="margin:0 0 0 .6rem">время раскрытия пишется в экспортируемый вердикт</span>
  <div id="revealBox" class="hidden"><div class="score" id="score"></div></div>
</div>

<div class="bar">
  <span id="progress">0 / 0</span>
  <span class="grow"></span>
  <button id="dl" onclick="download()">Скачать вердикт (JSON)</button>
</div>

<script>
const DATA = {payload};
{_PAGE_JS}
</script>
</body>
</html>
"""
    page_path = out / f"listen_{pair}.html"
    tmp = page_path.with_suffix(".html.tmp")
    tmp.write_text(page, encoding="utf-8")
    replace_retry(tmp, page_path)
    _write_json(out / f"key_{pair}.json",
                {"pair": pair, "control_nfe": control, "candidate_nfe": candidate,
                 "salt": _LISTEN_SALT, "generated": generated, "rows": key_rows})
    return page_path


def emit_index(out: Path, pages: list[Path], sample: list[dict], nfes: list[int],
               control: int) -> None:
    counts: dict[str, int] = {}
    for r in sample:
        counts[r["stratum"]] = counts.get(r["stratum"], 0) + 1
    li = "\n".join(f'<li><a href="{html.escape(p.name)}">{html.escape(p.name)}</a></li>'
                   for p in pages)
    strata = "\n".join(f"<li><b>{html.escape(k)}</b> — {v} units</li>" for k, v in counts.items())
    page = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>overdub — nfe sweep</title>
<style>{_PAGE_CSS}</style></head><body>
<h1>F5 nfe sweep — {len(sample)} units × nfe {', '.join(str(n) for n in nfes)}</h1>
<p class="note">Control = nfe {control}. Метрики (<code>results.csv</code>,
<code>results.json</code>) — это <b>предохранитель от катастрофы, а не вердикт</b>:
synth_sim по 527 production-юнитам имеет медиану 0.995 и минимум 0.924, шкалы для «лучше»
там просто нет, и рост sim совместимо с ухудшением звука. Решает ухо.</p>
<h2 style="font-size:1rem;color:#9aa">Слепые A/B страницы</h2><ul>{li}</ul>
<h2 style="font-size:1rem;color:#9aa">Страты выборки</h2><ul>{strata}</ul>
</body></html>
"""
    tmp = (out / "index.html").with_suffix(".html.tmp")
    tmp.write_text(page, encoding="utf-8")
    replace_retry(tmp, out / "index.html")


# --- driver -----------------------------------------------------------------------------
SESSION = time.strftime("%Y%m%dT%H%M%S")


def _eta(sample: list[dict], nfes: list[int]) -> float:
    total = _STARTUP_S * len(nfes)
    for nfe in nfes:
        for r in sample:
            canvas = _REF_SEC + (r["dur"] or 0)
            total += _DIT_S_PER_CANVAS_S * (nfe / 48.0) * canvas + _ASR_S
    return total


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="exp_nfe_sweep",
        description="F5 nfe sweep over real production units + blind A/B listening pages.")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"))
    p.add_argument("--out", type=Path, default=Path("work-exp/nfe-sweep"))
    p.add_argument("--nfe", default="48,32,16,12",
                   help="nfe grid; the FIRST value is the control (default 48,32,16,12 — 16 and "
                        "12 are the authors' EPSS-tuned step counts, 32 is not)")
    p.add_argument("--listen-n", type=int, default=16,
                   help="rows per blind A/B page (default 16; metrics still cover the full sample)")
    p.add_argument("--recheck-n", type=int, default=6,
                   help="control cells re-rendered at the end to falsify determinism and measure "
                        "thermal drift (0 disables)")
    p.add_argument("--reselect", action="store_true",
                   help="re-run sample selection even if sample.json exists (ORPHANS existing cells)")
    p.add_argument("--dry-run", action="store_true",
                   help="select the sample, print the plan and the ETA, touch no GPU")
    p.add_argument("--pages-only", action="store_true",
                   help="regenerate the listening pages + rollup from existing cells, no GPU")
    args = p.parse_args(argv)

    nfes = [int(x) for x in str(args.nfe).replace(" ", "").split(",") if x]
    if not nfes:
        p.error("--nfe needs at least one value")
    control = nfes[0]

    # Config.load returns DEFAULTS for a missing path. Silent fallback would render with the
    # default ref clip and default speeds while the report claims the shipped regime — the exact
    # silent-failure class CLAUDE.md forbids. A measurement run must fail loud instead.
    if not Path(args.config).exists():
        p.error(f"config not found: {args.config} — run from the repo root, or pass --config. "
                f"Rendering against defaults would silently measure a regime we do not ship.")
    cfg = Config.load(args.config)
    out = Path(args.out).resolve()
    work_root = Path(cfg.work_root).resolve()
    if out == work_root or work_root in out.parents:
        p.error(f"--out {out} is inside work_root {work_root} — this harness never writes "
                f"into the pipeline's workdirs")
    out.mkdir(parents=True, exist_ok=True)

    sample_path = out / "sample.json"
    if sample_path.exists() and not args.reselect:
        sample = json.loads(sample_path.read_text(encoding="utf-8"))["units"]
        print(f"sample: {len(sample)} units reused from {sample_path}")
    else:
        rows = load_corpus(work_root)
        if not rows:
            p.error(f"no rendered units found under {work_root}/*/segments/manifest.json")
        sample = select_sample(rows)
        _write_json(sample_path, {"generated": SESSION, "corpus_units": len(rows),
                                  "n": len(sample), "units": sample})
        print(f"sample: {len(sample)} units selected from {len(rows)} corpus units "
              f"-> {sample_path}")
    by_stratum: dict[str, int] = {}
    for r in sample:
        by_stratum[r["stratum"]] = by_stratum.get(r["stratum"], 0) + 1
    print("  strata: " + ", ".join(f"{k}={v}" for k, v in by_stratum.items()))
    print(f"  videos: {len(set(r['vid'] for r in sample))}, "
          f"duration {min(r['dur'] for r in sample):.1f}-{max(r['dur'] for r in sample):.1f}s, "
          f"speed {min(r['speed'] for r in sample):.3f}-{max(r['speed'] for r in sample):.3f}")

    eta = _eta(sample, nfes)
    print(f"  grid: {len(sample)} units × nfe {nfes} = {len(sample) * len(nfes)} cells, "
          f"predicted ~{eta / 60:.1f} min (+{args.recheck_n} recheck cells)")

    if args.dry_run:
        print("dry run — nothing rendered")
        return 0

    if not args.pages_only:
        print("loading whisper-small (verifier, stays resident across the whole sweep) ...")
        verifier = load_whisper(cfg.verify_model, cfg.whisper_device,
                                cfg.compute_type_for("verify"))
        t0 = time.perf_counter()
        try:
            render_grid(sample, nfes, out, cfg, verifier)
            if args.recheck_n:
                recheck(sample, out, cfg, verifier, control, args.recheck_n, nfes)
        finally:
            del verifier
            try:
                import gc

                import torch
                gc.collect()
                torch.cuda.empty_cache()
            except Exception:
                pass
        print(f"render wall {time.perf_counter() - t0:.0f}s")

    doc = rollup(sample, nfes, out, control)
    print("\n── per nfe " + "─" * 40)
    print(" | ".join(("nfe", "cells", "wall_s", "mean_s", "speedup", "sim_mean", "sim_min", "<0.9")))
    for r in doc["per_nfe"]:
        print(" | ".join(str(x) for x in (
            r["nfe"], r["n_cells"], r["wall_total_s"], r["wall_mean_s"],
            r["speedup_vs_control"], r["sim_mean"], r["sim_min"], r["n_below_gate"])))
    if doc["alarms"]:
        print(f"\n{len(doc['alarms'])} ALARM(s) — these are the only metric movements that mean "
              f"something on their own:")
        for a in doc["alarms"]:
            print("  ! " + a)
    else:
        print("\nno alarms. NOTE: that is the EXPECTED outcome and is NOT a pass — the guard "
              "metrics are saturated in this regime (see the module docstring). Judge by ear.")

    # offset rotates each pair's window so the three pages are not the same 16 texts
    pages = [emit_page(out, sample, control, c, args.listen_n, offset=i)
             for i, c in enumerate(x for x in nfes if x != control)]
    emit_index(out, pages, sample, nfes, control)
    print("\nblind A/B pages (open in a browser, judge BEFORE reading any key_*.json):")
    for pp in pages:
        print(f"  {pp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
