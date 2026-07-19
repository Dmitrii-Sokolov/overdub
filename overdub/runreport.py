"""Per-run observability: aggregate ALREADY-PERSISTED artifacts into run.json + a digest.

This module never runs a model, never touches the GPU, never hits the network — it reads
report.json / translation.json / timings.json / sentences.json / source.info.json (all written
by earlier stages) and rolls them up. The ONE external call it may make is a best-effort
`ffprobe` on the source media to recover a video duration when yt-dlp left none — guarded, and
purely a fallback for the RTF denominator.

Pure stdlib on purpose (json/os/shutil/subprocess/math/pathlib): the aggregation logic is
unit-tested without importing torch/whisper/soundfile, and the module has NO dependency on
pipeline/stages/cli/config internals (config is passed in, WorkDir is duck-typed via `.root`
and its artifact-path properties) so importing it from pipeline.py cannot create a cycle.

Design discipline inherited from the rest of the pipeline: atomic writes (tmp + os.replace),
"never a silent loss" (every failure prints a [warn] and degrades to a partial/None report
rather than raising into the stage runner or the batch loop), and the report is BEST-EFFORT —
an `--only download` run that has neither report.json nor translation.json emits nothing rather
than a misleading empty rollup.

Two facts the aggregation leans on, both verified against report.py / verify.py / assemble.py:
  - report.json segment records FAN OUT per sentence id; unit-level fields (verify_flag,
    speed_factor, combined_factor, assemble_flag) are DUPLICATED across every member sentence of
    a render unit and share one group_id (= the unit leader's id). To count/aggregate UNITS
    (not sentences) we dedup by group_id, first-seen wins (segments are id-sorted, so the
    first-seen member of a group is its leader).
  - the speed distribution metric is `combined_factor` (native F5 compression × atempo top-up),
    NOT raw tts_speed — it is the real compression a listener hears and matches assemble's own
    `n_over_1_8_combined` triage bar (DECISIONS 2026-07-17: native ≥~1.3 drops words, atempo
    tops up the rest; the combined figure is the one that means "candidate broken").
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys

# Fixed vocabularies — kept explicit so a run.json always carries every key at 0 (a consumer
# can diff two runs without None-guarding), and an unknown/new flag can never silently vanish.
_TRANSLATE_FLAGS = ("empty", "no_cyrillic", "english_echo", "runaway", "refusal",
                    "api_error", "unknown")
_VERIFY_FLAGS = ("empty_ref", "missing_wav", "unreadable_wav", "empty_hyp", "low_similarity",
                 "unknown")
_BROKEN = 1.8   # combined compression factor at/above which a unit is "candidate broken"
                # (mirrors assemble._BROKEN — the same triage bar, one number to keep in sync)


# --- small pure helpers -------------------------------------------------------
def _load_json(path):
    """Read+parse a JSON artifact, tolerating missing/torn files (returns None). The caller
    decides what an absent input means — never raises, so a partial workdir still reports."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_write_json(path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _percentile(values, q):
    """Linear-interpolation percentile over a NON-EMPTY ascending list (numpy 'linear'/inclusive
    method: rank = q*(n-1)). Returns the single value for n==1. Pure — unit-tested directly."""
    n = len(values)
    if n == 1:
        return values[0]
    rank = q * (n - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return values[lo]
    return values[lo] + (values[hi] - values[lo]) * (rank - lo)


def _unit_leaders(report):
    """One record per render unit, deduped by group_id (first-seen wins → the leader, since
    segments are id-sorted). Unit-level fields are duplicated across members, so any member
    carries the right values; taking exactly one per group turns per-sentence fan-out back into
    per-unit counts. group_id falls back to id when absent (legacy per-sentence records)."""
    if not isinstance(report, dict):
        return []
    segs = report.get("segments")
    if not isinstance(segs, list):
        return []
    leaders = {}
    order = []
    for rec in segs:
        if not isinstance(rec, dict):
            continue
        gid = rec.get("group_id")
        if gid is None:
            gid = rec.get("id")
        if gid not in leaders:
            leaders[gid] = rec
            order.append(gid)
    return [leaders[g] for g in order]


def _ffprobe_duration(work):
    """Best-effort video duration via ffprobe on the source media — RTF-denominator fallback
    only. Guarded on shutil.which + file existence; any failure (no ffprobe, unreadable media,
    non-numeric output) just returns None and the caller falls through to the sentences bound."""
    if not shutil.which("ffprobe"):
        return None
    for f in (work.source_audio, work.source_video):
        try:
            if not f.exists():
                continue
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(f)],
                capture_output=True, text=True, timeout=30)
            val = float(r.stdout.strip())
            if val > 0:
                return val
        except Exception:
            continue
    return None


# --- public API ---------------------------------------------------------------
def record_stage_timing(work, stage, wall_s) -> None:
    """Upsert ONE stage's wall-clock into work/timings.json, atomically, preserving every other
    stage's entry. Called per stage by the pipeline, so an --only or resumed run rewrites only
    the stages it actually ran; skipped stages keep their last real timing. Tolerates a
    missing/torn file (rebuilds as {"stages": {}}). MUST NOT raise into the caller — a failed
    timing write is a [warn], never a broken pipeline."""
    try:
        path = work.root / "timings.json"
        doc = _load_json(path)
        if doc is None and path.exists():                   # torn/unreadable, not merely absent:
            try:                                            # rebuilding from {} would SILENTLY drop
                if path.read_text(encoding="utf-8").strip():   # prior stage walls (understating
                    print(f"[warn] {path.name} unreadable — prior stage timings discarded",
                          file=sys.stderr)                  # total_wall/RTF). Keep the loss visible.
            except OSError:
                pass
        stages = doc.get("stages") if isinstance(doc, dict) else None
        if not isinstance(stages, dict):
            stages = {}
        stages[stage] = round(float(wall_s), 3)
        _atomic_write_json(path, {"stages": stages})
    except Exception as e:                                  # noqa: BLE001 — must never propagate
        print(f"[warn] could not record timing for {stage!r}: {e}", file=sys.stderr)


def build_run_report(work, cfg):
    """Aggregate the persisted artifacts into work/run.json (atomic) and RETURN the dict.

    BEST-EFFORT: if BOTH report.json and translation.json are absent, return None and write
    nothing (an --only download run must not emit a misleading empty report). If only some
    inputs exist, fill what is available and leave the rest zero/empty/null. NEVER raises — the
    whole body is wrapped; on unexpected error it prints a [warn] and returns None so neither
    _run_one nor the batch loop can be crashed by a malformed artifact."""
    try:
        return _build_run_report(work, cfg)
    except Exception as e:                                  # noqa: BLE001 — best-effort contract
        print(f"[warn] run.json build failed for {work.root.name}: {e}", file=sys.stderr)
        return None


def _build_run_report(work, cfg):
    report = _load_json(work.report)
    translation = _load_json(work.translation)
    if report is None and translation is None:
        # Nothing to report — write nothing, AND clear any run.json from a prior full run: a
        # reset workdir (report+translation deleted to redo from scratch) must not leave a stale
        # rollup for the batch sweep / digest to serve as if it were current.
        (work.root / "run.json").unlink(missing_ok=True)
        return None

    info = _load_json(work.info_json)
    info = info if isinstance(info, dict) else None
    title = info.get("title") if info else None

    # --- timings + RTF -------------------------------------------------------
    timings_doc = _load_json(work.root / "timings.json")
    stages = timings_doc.get("stages") if isinstance(timings_doc, dict) else None
    if not isinstance(stages, dict):
        stages = {}
    stages = {k: float(v) for k, v in stages.items() if isinstance(v, (int, float))}
    total_wall = round(sum(stages.values()), 3)

    video_sec, video_sec_source = None, "none"
    d = info.get("duration") if info else None
    if isinstance(d, (int, float)) and not isinstance(d, bool) and d > 0:
        video_sec, video_sec_source = float(d), "info_json"
    if video_sec is None:
        probed = _ffprobe_duration(work)
        if probed is not None:
            video_sec, video_sec_source = probed, "ffprobe"
    if video_sec is None:
        sents = _load_json(work.sentences)
        if isinstance(sents, list) and sents:
            ends = [s.get("end") for s in sents
                    if isinstance(s, dict) and isinstance(s.get("end"), (int, float))]
            if ends:
                video_sec, video_sec_source = float(max(ends)), "sentences"

    rtf = round(total_wall / video_sec, 3) if video_sec else None
    breakdown = ({k: round(v / total_wall * 100, 1) for k, v in stages.items()}
                 if total_wall else {})

    # --- translate -----------------------------------------------------------
    tr_by_type = {k: 0 for k in _TRANSLATE_FLAGS}
    n_sentences = n_failed = 0
    if isinstance(translation, list):
        n_sentences = len(translation)
        for rec in translation:
            if not isinstance(rec, dict) or rec.get("status") == "ok":
                continue
            n_failed += 1
            flag = rec.get("flag")
            tr_by_type[flag if flag in tr_by_type else "unknown"] += 1

    # --- verify (rollup copied; by_type recomputed over UNIT leaders) --------
    vr = report.get("verify") if isinstance(report, dict) else None
    vr = vr if isinstance(vr, dict) else {}
    leaders = _unit_leaders(report)
    v_by_type = {k: 0 for k in _VERIFY_FLAGS}
    for lead in leaders:
        vf = lead.get("verify_flag")
        if vf:                                              # None/absent = a clean unit; a flag
            v_by_type[vf if vf in v_by_type else "unknown"] += 1   # outside the vocab never vanishes
    v_n_flagged = int(vr.get("n_flagged", 0) or 0)

    # --- completeness (six ints copied straight from the verify-side rollup) -
    cr = report.get("completeness") if isinstance(report, dict) else None
    cr = cr if isinstance(cr, dict) else {}
    completeness = {k: int(cr.get(k, 0) or 0) for k in
                    ("n_sentences", "n_flagged", "n_num_loss", "n_neg_loss",
                     "n_entity_loss", "n_length")}

    # --- assemble / mux (straight copies, null when the stage never ran) -----
    ar = report.get("assemble") if isinstance(report, dict) else None
    ar = ar if isinstance(ar, dict) else {}
    mr = report.get("mux") if isinstance(report, dict) else None
    mr = mr if isinstance(mr, dict) else {}

    # --- speed distribution over UNIT leaders (combined_factor) --------------
    # Only ASSEMBLED units carry a speed factor; before assemble runs none do. Skip those
    # rather than fabricating 1.0 — a fabricated 1.0 reads as "assembled, zero compression",
    # while the assemble/mux copies above stay null for an un-run stage, so speed must too.
    speed_vals = []
    for lead in leaders:
        v = lead.get("combined_factor")
        if v is None:
            v = lead.get("speed_factor")
        if v is None:
            continue
        speed_vals.append(float(v))
    if speed_vals:
        asc = sorted(speed_vals)
        median = round(_percentile(asc, 0.5), 4)
        p95 = round(_percentile(asc, 0.95), 4)
        smax = round(asc[-1], 4)
    else:
        median = p95 = smax = None
    # n_over: prefer assemble's own raw-float count. Recomputing from the 4-dp-ROUNDED
    # combined_factor could disagree by one unit at the exact 1.8 boundary (a raw 1.79997 rounds
    # to 1.8000) — same metric, so trust the one authoritative source; recompute only when the
    # assemble rollup is absent (a pre-assemble --only verify run).
    if "n_over_1_8_combined" in ar:
        n_over = int(ar.get("n_over_1_8_combined") or 0)
    else:
        n_over = sum(1 for v in speed_vals if v >= _BROKEN)

    n_assemble_flagged = sum(1 for lead in leaders if lead.get("assemble_flag"))
    flags_total = n_failed + v_n_flagged + completeness["n_flagged"] + n_assemble_flagged
    needs_triage = flags_total > 0 or n_over > 0

    run = {
        "video_id": work.root.name,
        "title": title,
        "timings": {
            "stages": stages,
            "total_wall_s": total_wall,
            "video_sec": video_sec,
            "video_sec_source": video_sec_source,
            "rtf": rtf,
            "breakdown_pct": breakdown,
        },
        "translate": {
            "n_sentences": n_sentences,
            "n_failed": n_failed,
            "by_type": tr_by_type,
        },
        "verify": {
            "n_units": int(vr.get("n_units", 0) or 0),
            "n_segments": int(vr.get("n_segments", 0) or 0),
            "n_flagged": v_n_flagged,
            "n_retried": int(vr.get("n_retried", 0) or 0),
            "n_repaired": int(vr.get("n_repaired", 0) or 0),
            "by_type": v_by_type,
        },
        "completeness": completeness,
        "speed": {
            "metric": "combined_factor",
            "median": median,
            "p95": p95,
            "max": smax,
            "n_over_1_8": n_over,
        },
        "assemble": {
            "duration_sec": ar.get("duration_sec"),
            "n_sped": int(ar.get("n_sped", 0) or 0),
            "in_span_silence_sec": ar.get("in_span_silence_sec"),
        },
        "mux": {
            "dub_mix": mr.get("dub_mix"),
            "dub_gain_db": mr.get("dub_gain_db"),
        },
        "flags_total": flags_total,
        "needs_triage": needs_triage,
    }
    _atomic_write_json(work.root / "run.json", run)
    return run


def summarize_offenders(report, translation=None, limit=40):
    """Triage rows for the HUMAN report — one per SENTENCE id with any problem: a failed/flagged
    translation, a verify flag, an assemble flag, a non-empty completeness_flags, OR a combined
    (fallback speed) factor >= 1.8. Pure, no I/O. src_en/text_ru are joined from `translation`
    by id when provided (else null). Capped at `limit`, sorted by id ascending for determinism."""
    if not isinstance(report, dict):
        return []
    segs = report.get("segments")
    if not isinstance(segs, list):
        return []
    tr_by_id = {}
    if isinstance(translation, list):
        for rec in translation:
            if isinstance(rec, dict) and "id" in rec:
                tr_by_id[rec.get("id")] = rec

    rows = []
    for rec in segs:
        if not isinstance(rec, dict):
            continue
        reasons = []
        tflag = rec.get("translate_flag")
        if rec.get("status") == "failed" or tflag:
            reasons.append(f"translate:{tflag or 'failed'}")
        vf = rec.get("verify_flag")
        if vf:
            reasons.append(f"verify:{vf}")
        af = rec.get("assemble_flag")
        if af:
            reasons.append(f"assemble:{af}")
        cflags = rec.get("completeness_flags")
        if isinstance(cflags, list):
            for cf in cflags:
                reasons.append(f"complete:{cf}")
        speed = rec.get("combined_factor")
        if speed is None:
            speed = rec.get("speed_factor")
        speed = float(speed) if isinstance(speed, (int, float)) else None
        if speed is not None and speed >= _BROKEN:
            reasons.append(f"speed:{speed:.2f}")
        if not reasons:
            continue
        sid = rec.get("id")
        tr = tr_by_id.get(sid)
        rows.append({
            "id": sid,
            "reasons": reasons,
            "speed": (round(speed, 4) if speed is not None else None),
            "src_en": (tr.get("src_en") if isinstance(tr, dict) else None),
            "text_ru": (tr.get("text_ru") if isinstance(tr, dict) else None),
        })
    rows.sort(key=lambda r: (r["id"] is None, r["id"]))
    return rows[:limit]


def flagged_units(report, translation=None, limit=500):
    """UNIT-level triage rows for the morning-triage HTML — richer than summarize_offenders (which
    is sentence-level for the text digest). One row per RENDER UNIT (deduped by group_id) that
    carries a problem: a verify flag / combined-speed >= 1.8 / assemble flag on the leader, OR a
    completeness flag or a failed/flagged translation on ANY member. Carries the leader id (→ the
    `segments/<lead>.wav` a human listens to), the member ids, the ASR similarity + hypothesis
    (the verify-triage payload — hypothesis lives on the leader record only), the joined EN/RU/tts
    text, and the unit span + speed. Pure, no I/O — the HTML script owns file reads/rendering.

    group_id is the leader's own sentence id by construction (verify/assemble set it to the unit's
    first id), so `lead` doubles as the wav key. Falls back to id for legacy per-sentence records."""
    if not isinstance(report, dict):
        return []
    segs = report.get("segments")
    if not isinstance(segs, list):
        return []

    groups: dict = {}                                       # gid -> {"lead": rec, "members": [rec]}
    order: list = []
    for rec in segs:
        if not isinstance(rec, dict):
            continue
        gid = rec.get("group_id")
        if gid is None:
            gid = rec.get("id")
        if gid not in groups:
            groups[gid] = {"lead": rec, "members": []}     # first-seen = the leader (id-sorted)
            order.append(gid)
        groups[gid]["members"].append(rec)

    tr_by_id: dict = {}
    if isinstance(translation, list):
        for r in translation:
            if isinstance(r, dict) and "id" in r:
                tr_by_id[r.get("id")] = r

    rows = []
    for gid in order:
        lead = groups[gid]["lead"]
        members = groups[gid]["members"]
        reasons: list = []
        vf = lead.get("verify_flag")
        if vf:
            reasons.append(f"verify:{vf}")
        sp = lead.get("combined_factor")
        if sp is None:
            sp = lead.get("speed_factor")
        sp = float(sp) if isinstance(sp, (int, float)) else None
        if sp is not None and sp >= _BROKEN:
            reasons.append(f"speed:{sp:.2f}")
        af = lead.get("assemble_flag")
        if af:
            reasons.append(f"assemble:{af}")
        seen: set = set()                                  # completeness then translate, deduped,
        for m in members:                                  # unioned across the unit's members
            cf = m.get("completeness_flags")
            if isinstance(cf, list):
                for c in cf:
                    if ("complete", c) not in seen:
                        seen.add(("complete", c))
                        reasons.append(f"complete:{c}")
        for m in members:
            tflag = m.get("translate_flag")
            if m.get("status") == "failed" or tflag:
                key = tflag or "failed"
                if ("translate", key) not in seen:
                    seen.add(("translate", key))
                    reasons.append(f"translate:{key}")
        if not reasons:
            continue

        ids = [m.get("id") for m in members]
        trs = [tr_by_id.get(i) for i in ids]

        def _join(field):
            vals = [t.get(field) for t in trs
                    if isinstance(t, dict) and isinstance(t.get(field), str) and t.get(field).strip()]
            return " ".join(v.strip() for v in vals) if vals else None

        starts = [t.get("start") for t in trs
                  if isinstance(t, dict) and isinstance(t.get("start"), (int, float))]
        ends = [t.get("end") for t in trs
                if isinstance(t, dict) and isinstance(t.get("end"), (int, float))]
        sim = lead.get("similarity")
        rows.append({
            "lead": gid,
            "ids": ids,
            "reasons": reasons,
            "similarity": (round(sim, 4) if isinstance(sim, (int, float)) else None),
            "hypothesis": lead.get("hypothesis"),
            "text_tts": _join("text_tts"),
            "src_en": _join("src_en"),
            "text_ru": _join("text_ru"),
            "start": (min(starts) if starts else None),
            "end": (max(ends) if ends else None),
            "speed": (round(sp, 4) if sp is not None else None),
        })
    rows.sort(key=lambda r: (r["lead"] is None, r["lead"]))
    return rows[:limit]


def render_run_report(run, offenders):
    """Compact ENGLISH Markdown block for ONE video (the codebase artifact norm is English; the
    Russian human narrative is the skill agent's job). Header + timings line + flags line, plus
    an offenders bullet list only when non-empty. Pure, no I/O."""
    vid = run.get("video_id")
    title = run.get("title")
    marker = "TRIAGE" if run.get("needs_triage") else "clean"
    head = f"### {vid}" + (f" — {title}" if title else "") + f"  [{marker}]"

    t = run.get("timings", {}) or {}
    src = t.get("video_sec_source")
    rtf = t.get("rtf")
    rtf_part = f"RTF {rtf} ({src})" if rtf is not None else f"RTF n/a ({src})"
    top3 = sorted((t.get("breakdown_pct", {}) or {}).items(),
                  key=lambda kv: kv[1], reverse=True)[:3]
    top_part = (" · top: " + ", ".join(f"{k} {v}%" for k, v in top3)) if top3 else ""
    timings_line = f"- timings: {t.get('total_wall_s', 0)}s wall · {rtf_part}{top_part}"

    tr = run.get("translate", {}) or {}
    v = run.get("verify", {}) or {}
    c = run.get("completeness", {}) or {}
    sp = run.get("speed", {}) or {}
    flags_line = (
        f"- flags: translate {tr.get('n_failed', 0)}/{tr.get('n_sentences', 0)}"
        f" · verify {v.get('n_flagged', 0)}"
        f" · completeness {c.get('n_flagged', 0)}"
        f" · speed med {sp.get('median')}/p95 {sp.get('p95')}/max {sp.get('max')}"
        f" (n>1.8 {sp.get('n_over_1_8', 0)})")

    lines = [head, timings_line, flags_line]
    if offenders:
        lines.append(f"- offenders ({len(offenders)}):")
        for o in offenders:
            snippet = (o.get("src_en") or "").strip().replace("\n", " ")[:60]
            reasons = ", ".join(o.get("reasons", []))
            lines.append(f"  - {o.get('id')} — {reasons} — {snippet}")
    return "\n".join(lines)
