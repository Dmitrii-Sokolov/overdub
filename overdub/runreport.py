"""Per-run observability: aggregate ONE workdir's ALREADY-PERSISTED artifacts into run.json.

This module never runs a model, never touches the GPU, never hits the network — it reads
report.json / translation.json / timings.json / sentences.json / source.info.json (all written
by earlier stages) and rolls them up. The ONE external call it may make is a best-effort
`ffprobe` on the source media to recover a video duration when yt-dlp left none — guarded, and
purely a fallback for the RTF denominator.

SCOPE, since 2026-07-22: one workdir, during a run. The QUEUE layer — resolving a queue file
into ordered entries, the batch-table cells, the digest text — moved to `overdub/queueview.py`,
which imports this module. The dependency is one-way by design; importing queueview from here
would put a many-workdir walk inside the per-video rollup the pipeline calls.

Pure stdlib on purpose (json/math/os/re/shutil/subprocess): the aggregation logic is unit-tested
without importing torch/whisper/soundfile, and the module has NO dependency on
pipeline/stages/cli/config internals (config is passed in), so importing it from pipeline.py
cannot create a cycle. It now has NO package imports at all.

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
  - the speed distribution metric is `combined_factor` (native compression × atempo top-up),
    NOT raw tts_speed — it is the real compression a listener hears and matches assemble's own
    `n_over_1_8_combined` triage bar (DECISIONS 2026-07-17: native ≥~1.3 drops words, atempo
    tops up the rest; the combined figure is the one that means "candidate broken").
"""

from __future__ import annotations

import json
import math
import os
import re
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
# Completeness flags that are informational only: they are counted and printed but never decide
# needs_triage. See completeness.py — length_short is the deliberately coarse weak signal.
# dup_adjacent and rate_implausible joined 2026-07-25: both read the EN SOURCE, so they
# describe an ASR defect a listener cannot fix by opening the dub (they were the top two
# contributors to a 23-of-24 triage rate). `--repair-asr` acts on those, not the listen queue.
# neg_loss joined 2026-07-27 on measured precision, not on theory: 24 inspected fires, 0 real
# (DECISIONS 2026-07-27). It stays COUNTED — `n_neg_loss` still prints and the offenders list
# still names it — because re-promotion has to be decidable off the same series that demoted it.
# entity_loss was the original member and its DETECTOR is gone as of 2026-08-01 (DECISIONS):
# demoting it was not enough, because an advisory flag still costs a line in every offenders
# list and an embedded player on the listen page — 1179 of 1186 units on the 19-video batch.
# The NAME stays in this set as a tombstone and must not be removed: every report.json written
# before that date still carries per-sentence entity_loss flags, and this set is subtractive
# (`flags - _ADVISORY_COMPLETENESS`), so dropping the name would silently promote a dead flag to
# ACTIONABLE and light up needs_triage on every historical workdir. Pinned by
# test_legacy_report_with_entity_loss_still_reads.
_ADVISORY_COMPLETENESS = frozenset({"length_short", "entity_loss",
                                    "dup_adjacent", "rate_implausible", "neg_loss"})

# Translate flags that do NOT decide needs_triage. english_echo measures the LATIN RATIO of a
# translation, which on route B is a deliberate output: the prompt keeps commands, filenames and
# set phrases in Latin, and pronounce.py voices them. Measured on the 2026-07-25 batch: 28 fires,
# 28 of them correct Sonnet behaviour (`task-master init`, `npm run dev`, `/update-doc initialize`,
# `contact-session-1.md`, `free-to-play`) — one video reported 15 actionable flags of which 11 were
# this. The count stays (a genuine echo is real, and `translate.n_failed` still prints it);
# it just stops sending a human to listen to a unit that was translated correctly.
_ADVISORY_TRANSLATE = frozenset({"english_echo"})

# Source anomalies the route-B translate sub-agent REPORTS on the English source
# (the source-anomaly pass).
# Same fixed-vocab discipline as above; "unknown" is the clamp bucket build_translation.py writes
# for a kind outside its own _SRC_KINDS, so a new/mistyped kind is counted, never dropped.
# Deliberately NOT named dup_adjacent: dup_neighbour is a different detector with different
# evidence (an LLM reading the text vs a string metric) and must never be conflated with the
# completeness flag in a digest line.
_SOURCE_KINDS = ("garbled", "truncated", "dup_neighbour", "enum_repeat",
                 "context_contradiction", "unknown")
_SOURCE_LIMIT = 40      # mirrors summarize_offenders(limit=40) — keeps run.json small + diffable

# The summary is free-form Russian prose an LLM wrote (the video summary — INFORMATIONAL, it gates
# nothing). Two renderers consume it, so the sanitizing happens ONCE here at the read boundary and
# not in either renderer: a markdown heading inside the text would collide with the digest's own
# "### <vid>" block header and silently break block boundaries for the agent that parses the
# digest, and a runaway blob would wreck the digest's line flow and bloat the triage page. There is
# deliberately NO build_summary.py operator step — an operator step can be skipped, a read boundary
# both renderers go through cannot (same "centralize the shared transform" precedent report.py
# cites for normalize.py).
# 4000 chars is ~3x what a ~200-word Russian summary occupies — headroom, not a quality bar.
_SUMMARY_MAX_CHARS = 4000
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*")     # atx heading marker: strip the marker, keep the text


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
def _load_timings(work):
    """work/<id>/timings.json → the WHOLE document, or {} when absent. A torn file is reported
    once and treated as empty, because rebuilding from {} silently drops prior stage walls
    (understating total_wall/RTF) and that loss must stay visible."""
    path = work.root / "timings.json"
    doc = _load_json(path)
    if doc is None and path.exists():
        try:
            if path.read_text(encoding="utf-8").strip():
                print(f"[warn] {path.name} unreadable — prior stage timings discarded",
                      file=sys.stderr)
        except OSError:
            pass
    return path, (doc if isinstance(doc, dict) else {})


def record_stage_timing(work, stage, wall_s) -> None:
    """Upsert ONE stage's wall-clock into work/timings.json, atomically, preserving every other
    stage's entry. Called per stage by the pipeline, so an --only or resumed run rewrites only
    the stages it actually ran; skipped stages keep their last real timing. Tolerates a
    missing/torn file. MUST NOT raise into the caller — a failed timing write is a [warn], never
    a broken pipeline.

    Writes back the WHOLE document, not {"stages": ...}. It used to replace the file with just
    that one key, which was invisible while `stages` was the only section and silently ate
    `detail` the moment a second one existed."""
    try:
        path, doc = _load_timings(work)
        stages = doc.get("stages")
        if not isinstance(stages, dict):
            stages = {}
        stages[stage] = round(float(wall_s), 3)
        doc["stages"] = stages
        _atomic_write_json(path, doc)
    except Exception as e:                                  # noqa: BLE001 — must never propagate
        print(f"[warn] could not record timing for {stage!r}: {e}", file=sys.stderr)


def record_stage_detail(work, stage, **fields) -> None:
    """Upsert a stage's INNER measurements into work/timings.json → detail[<stage>].

    Kept apart from `stages` because the two answer different questions and must never be summed
    together. `stages[x]` is the pipeline's wall clock for the whole stage — model load included,
    which is what the run's cost actually was. `detail[x]` is what the stage measured about
    ITSELF (transcribe: decode time with the load excluded, and how many ASR passes ran), which
    is what a before/after optimization comparison needs and what the wall clock cannot give:
    load lands on whichever video happens to be first in the sweep.

    Same never-raises contract as record_stage_timing."""
    try:
        path, doc = _load_timings(work)
        detail = doc.get("detail")
        if not isinstance(detail, dict):
            detail = {}
        entry = detail.get(stage)
        if not isinstance(entry, dict):
            entry = {}
        entry.update(fields)
        detail[stage] = entry
        doc["detail"] = detail
        _atomic_write_json(path, doc)
    except Exception as e:                                  # noqa: BLE001 — must never propagate
        print(f"[warn] could not record detail for {stage!r}: {e}", file=sys.stderr)


def _stage_overhead(stages, detail):
    """({stage: overhead_s}, total) — what each stage spent OUTSIDE the work it measured itself.

    overhead = stages[x] - detail[x].work_sec: a model load, a worker spawn, a preflight check.
    Both numbers describe the SAME stage, so subtracting them is legitimate — the thing DECISIONS
    2026-07-20 forbids is summing a wall clock WITH a work figure and calling the result a cost.

    Three ways a stage is left out, all silent by design because each means "the overhead is not
    known", never "it was zero":
      - no detail entry (download, separate, verify, assemble, mux today);
      - a stage that was SKIPPED this run: record_stage_timing only writes for stages that
        actually ran, but detail from an EARLIER session survives in the same file, so the pair
        can straddle two runs. The stage wall is then the older one too (both keys are upserted),
        which keeps the subtraction internally consistent -- but a NEGATIVE result means they did
        not come from one session, and that is the case dropped below;
      - a non-numeric or missing work_sec.

    Dropping the negative case rather than clamping it to 0 is the point: a clamp would report a
    stage as pure work when the file is actually telling us the two halves disagree."""
    out: dict[str, float] = {}
    for stage, wall in stages.items():
        entry = detail.get(stage)
        work = entry.get("work_sec") if isinstance(entry, dict) else None
        if not isinstance(work, (int, float)) or isinstance(work, bool):
            continue
        gap = float(wall) - float(work)
        if gap < 0:
            continue
        out[stage] = round(gap, 3)
    return out, sum(out.values())


def read_summary(work):
    """work/<id>/summary.md → sanitized prose, or None when absent/empty/unreadable.

    A SIDECAR, deliberately not folded into run.json: run.json is derived and self-clears when
    report.json + translation.json are both gone (a scout-mode workdir), so routing the
    summary through the rollup would make it invisible in the one mode it was designed for. Keeping
    the rollup small and diffable is load-bearing besides.

    Never raises: a missing summary is NORMAL (it gates nothing — the v1 summary is informational)
    and an unreadable one degrades to None, the same contract _load_json gives every other optional
    artifact this module reads."""
    try:
        raw = work.summary.read_text(encoding="utf-8")
    except (OSError, ValueError):                 # ValueError: torn UTF-8, mirrors _load_json
        return None
    lines = [_HEADING.sub("", ln).rstrip() for ln in raw.replace("\r\n", "\n").split("\n")]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if not text:
        return None
    if len(text) > _SUMMARY_MAX_CHARS:            # visible truncation, never a silent drop
        text = text[:_SUMMARY_MAX_CHARS].rstrip() + " …[truncated]"
    return text


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
    detail = timings_doc.get("detail") if isinstance(timings_doc, dict) else None
    detail = detail if isinstance(detail, dict) else {}
    overhead, total_overhead = _stage_overhead(stages, detail)
    work_stages = sorted(overhead)
    # A stage's overhead is stages[x] - detail[x].work_sec: two measurements of the SAME stage
    # subtracted, which is legitimate, unlike summing a wall clock with a work figure (the thing
    # DECISIONS 2026-07-20 forbids). total_work_s is total_wall minus every overhead we KNOW, so
    # it is an upper bound while coverage is partial -- which is why work_complete travels with
    # it and nothing here silently presents it as the finished number.
    total_work = round(total_wall - total_overhead, 3) if work_stages else None
    work_complete = bool(stages) and set(work_stages) == set(stages)

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
    rtf_work = (round(total_work / video_sec, 3)
                if (total_work is not None and video_sec) else None)
    breakdown = ({k: round(v / total_wall * 100, 1) for k, v in stages.items()}
                 if total_wall else {})

    # --- asr alignment health (recomputed from words.json, no new artifact) ---
    # Same function the transcribe guard gates on, so the report and the guard can never
    # disagree. Reported EVERY run, not only when the guard fires: whisper's temperature
    # fallback samples, so this scores the RUN and only a series of runs shows whether a
    # threshold sits between the healthy and collapsed populations or inside their overlap.
    from .stages.transcribe import W as _W          # local: stages imports pipeline, which
    from .stages.transcribe import floor_run_ratio  # imports this module (cycle at import time)

    words = _load_json(work.words)
    if isinstance(words, list) and words:
        flat = [_W(str(w.get("text", "")), float(w.get("start") or 0.0),
                   float(w.get("end") or 0.0), bool(w.get("seg_end")))
                for w in words if isinstance(w, dict)]
        f_ratio, f_run = floor_run_ratio(flat)
        asr_block = {"n_words": len(flat), "floor_ratio": round(f_ratio, 4),
                     "floor_longest_run": f_run}
    else:
        asr_block = {"n_words": 0, "floor_ratio": None, "floor_longest_run": None}

    # Uncovered speech (Parakeet only — the transcribe stage stamps these; whisper workdirs and
    # every pre-2026-08-06 one simply have no key and read as None). NOT recomputed here the way
    # floor_ratio is: the spans are defined against the VAD's own segments, which live in the
    # worker's venv and are not on disk, so the stage's stamp is the only record there will ever
    # be. `unrecovered` is the actionable one — speech that a second read ALSO failed to
    # transcribe, i.e. a stretch of the video that will ship with no dub under it.
    tdetail = (_load_timings(work)[1].get("detail") or {}).get("transcribe") or {}
    if "holes_unrecovered" in tdetail or "asr_repair_windows" in tdetail:
        asr_block["holes"] = int(tdetail.get("asr_repair_windows") or 0)
        asr_block["hole_sec"] = float(tdetail.get("hole_sec") or 0.0)
        asr_block["hole_words_recovered"] = int(tdetail.get("hole_words_recovered") or 0)
        asr_block["holes_unrecovered"] = int(tdetail.get("holes_unrecovered") or 0)
        asr_block["hole_sec_unrecovered"] = float(tdetail.get("hole_sec_unrecovered") or 0.0)

    # --- translate -----------------------------------------------------------
    tr_by_type = {k: 0 for k in _TRANSLATE_FLAGS}
    sa_by_type = {k: 0 for k in _SOURCE_KINDS}
    sa_items: list[dict] = []
    n_sentences = n_failed = n_scanned = 0
    if isinstance(translation, list):
        n_sentences = len(translation)
        for rec in translation:
            if not isinstance(rec, dict):
                continue
            # A source anomaly is ORTHOGONAL to status: an anomalous English sentence usually
            # translates fine and therefore carries status "ok". This read MUST precede the
            # status-ok `continue` below or the whole signal disappears for the common case.
            src = rec.get("src")
            if isinstance(src, str):                 # "ok" counts as scanned -- the attestation
                n_scanned += 1
                if src != "ok":
                    kind = src if src in sa_by_type else "unknown"
                    sa_by_type[kind] += 1
                    if len(sa_items) < _SOURCE_LIMIT:
                        sa_items.append({
                            "id": rec.get("id"),
                            "kind": kind,
                            "note": (rec.get("src_note") or "")[:200],
                            "src_en": (rec.get("src_en") or "")[:100]})
            if rec.get("status") == "ok":
                continue
            n_failed += 1
            flag = rec.get("flag")
            tr_by_type[flag if flag in tr_by_type else "unknown"] += 1
    n_src = sum(sa_by_type.values())

    # --- pronounce audit (counts only; the token table stays in its own file) -
    # pronounce.audit_events' docstring said "nothing ever reads it back", and that WAS the hole:
    # the 2026-07-25 batch invented 1587 fallback pronunciations across 653 distinct Latin tokens
    # (readme → ар-и-эй-ди-эм-и, heroes → херос ×50, builder → буилдер) and not one number reached
    # run.json, the digest, the queue page or triage. The dictionary fixes went in with that batch;
    # these counts are what stops the NEXT batch from hiding the same class.
    #
    # COUNTS, not the tokens: the audit file is already on disk beside run.json and can be long
    # (12 KB on one video here). `n_invented` is the pair's sum, so a consumer has one number to
    # trend without deciding what "letters" means. Absent file → all None, never 0: a workdir
    # built before this artifact existed, and a torn workdir, must not report a measured zero.
    pa = _load_json(work.pronounce_audit)
    pa_tokens = pa.get("tokens") if isinstance(pa, dict) else None
    if isinstance(pa_tokens, dict):
        by_via: dict[str, int] = {}
        for rec in pa_tokens.values():
            if isinstance(rec, dict):
                n = rec.get("count")
                by_via[str(rec.get("via"))] = by_via.get(str(rec.get("via")), 0) + (
                    int(n) if isinstance(n, int) else 1)
        pronounce_block = {
            "n_distinct": len(pa_tokens),
            "n_fallback": by_via.get("fallback", 0),
            "n_letters": by_via.get("letters", 0),
            "n_invented": by_via.get("fallback", 0) + by_via.get("letters", 0),
        }
    else:
        pronounce_block = {"n_distinct": None, "n_fallback": None,
                           "n_letters": None, "n_invented": None}

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

    # --- completeness (seven ints copied straight from the verify-side rollup) -
    cr = report.get("completeness") if isinstance(report, dict) else None
    cr = cr if isinstance(cr, dict) else {}
    completeness = {k: int(cr.get(k, 0) or 0) for k in
                    ("n_sentences", "n_flagged", "n_num_loss", "n_neg_loss",
                     "n_length", "n_dup_adjacent", "n_rate_implausible")}

    # Split completeness by what a human can ACT on. length_short is documented in
    # completeness.py as the weak, deliberately-coarse signal; pooling it into needs_triage
    # marked 11 of 12 videos in the AI-Fluency batch as needing a look, which carries the same
    # information as marking none. It stays counted and printed; it just stops deciding whether
    # a human opens the video.
    #
    # 2026-07-25 adds the second half of the same argument, measured on a 24-video batch that came
    # back 23/24 needing triage — the metric had died again. dup_adjacent and rate_implausible
    # inspect the EN SOURCE (completeness.py says so in its own docstring): they report an ASR
    # defect, and opening the dub does not let a human fix a sentence whisper duplicated. They are
    # the top two contributors to that 23 (35 and 54 hits). Advisory for the SAME reason, still
    # counted, still printed, still in the offenders list — the source-anomaly pass and
    # `--repair-asr` are where a source defect gets acted on, not the listen queue.
    segs_all = report.get("segments") if isinstance(report, dict) else None
    segs_all = segs_all if isinstance(segs_all, list) else []
    n_comp_actionable = sum(
        1 for s in segs_all
        if isinstance(s, dict) and (set(s.get("completeness_flags") or []) - _ADVISORY_COMPLETENESS)
    )
    completeness["n_actionable"] = n_comp_actionable
    completeness["n_advisory"] = max(completeness["n_flagged"] - n_comp_actionable, 0)

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
    flags_total = (n_failed + v_n_flagged + completeness["n_flagged"] + n_assemble_flagged
                   + n_src)
    # Source anomalies are ADVISORY in v1: counted in flags_total, printed everywhere, but they
    # do NOT move flags_actionable or needs_triage. An LLM asked to report source damage has no
    # measured precision yet, and _ADVISORY_COMPLETENESS above demoted (and 2026-08-01 deleted)
    # entity_loss for exactly this reason -- it marked 11 of 12 videos, which carries the same
    # information as marking none. Promotion is ONE line (add n_src to flags_actionable) and is gated on one batch's
    # measured fire rate; this demotion is provisional, not permanent.
    # needs_triage answers "does a human have to OPEN this video", so only actionable flags and
    # speed offenders decide it; flags_total keeps counting everything for trend/comparison.
    # n_failed_actionable drops the advisory translate flags (english_echo) for the reason stated
    # at _ADVISORY_TRANSLATE: on route B they mark correct output. n_failed itself is untouched —
    # `translate 28/4321` keeps printing in the digest, and by_type still names the split.
    n_failed_actionable = n_failed - sum(tr_by_type[k] for k in _ADVISORY_TRANSLATE)
    flags_actionable = (max(n_failed_actionable, 0) + v_n_flagged + n_comp_actionable
                        + n_assemble_flagged)
    # A degraded tail is NOT a flag count — it is a property of the finished container, and it
    # has to reach a human some other way than the export name, which is deliberately unchanged
    # (the MKV lands in out/ looking exactly like a real dub). `degraded` is true when assemble
    # stamped a reason OR mux shipped without one of its three optional tracks. Absent stamps
    # (a legacy report, a stage that never ran) read as False, never as a measured degradation.
    mux_tracks = mr.get("tracks") if isinstance(mr.get("tracks"), dict) else None
    degraded = bool(ar.get("degraded")) or (mux_tracks is not None
                                            and not all(mux_tracks.values()))
    # Unrecovered speech is ACTIONABLE and joins needs_triage directly, unlike every advisory flag
    # above. The distinction those make is "can a human do anything about it" — here they can and
    # must: the VAD heard speech, two independent decodes produced no words for it, so that
    # stretch of the finished MKV plays with no dub under it and nothing else in the report says
    # so. It is also RARE by construction (every hole measured 2026-08-06 was recovered on the
    # second read), so it cannot flood the flag the way entity_loss did at 11 of 12.
    n_unrecovered = int(asr_block.get("holes_unrecovered") or 0)
    needs_triage = flags_actionable > 0 or n_over > 0 or degraded or n_unrecovered > 0

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
            # The load-excluded half. `rtf` above still bills the whole wall clock, on purpose:
            # it is what the run cost, and stage-major lands every model load on whichever video
            # happens to be first, so it is not comparable ACROSS videos or builds. rtf_work is,
            # to the extent work_coverage says it is -- and `work_complete` is the flag that
            # keeps a partial figure from being read as a finished one.
            "detail": detail,
            "overhead_s": overhead,
            "total_overhead_s": round(total_overhead, 3),
            "total_work_s": total_work,
            "rtf_work": rtf_work,
            "work_coverage": work_stages,
            "work_complete": work_complete,
        },
        "asr": asr_block,
        "translate": {
            "n_sentences": n_sentences,
            "n_failed": n_failed,
            "by_type": tr_by_type,
        },
        "pronounce": pronounce_block,
        # src_en is duplicated into `items` DELIBERATELY: this block must be readable in a
        # transcribe+translate-only workdir, where report.json does not exist. Discovering the
        # anomaly hours before synthesize is the entire point of the signal, so it must not
        # depend on a post-synthesis artifact. `scanned` is first-class rather than inferred
        # from n_flagged == 0 because a translation written without the anomaly pass carries no
        # `src` at all -- a consumer must render "not scanned" there, NEVER "clean".
        "source": {
            "scanned": bool(n_sentences) and n_scanned == n_sentences,
            "n_scanned": n_scanned,
            "n_flagged": n_src,
            "by_type": sa_by_type,
            "items": sa_items,
        },
        "verify": {
            # Absent stamp = a report from before the switch existed, when the round-trip was
            # unconditional — so it reads True, never False. Guessing the other way would relabel
            # every historical run as unscanned.
            "roundtrip": bool(vr.get("roundtrip", True)),
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
            # Both None on a report written before 2026-07-25 — absent is UNKNOWN, never a
            # measured zero, same rule as the pronounce block. The speed block above cannot
            # carry this: its metric is floored at 1.0, so it reads "clean" on an under-filled
            # dub by construction.
            "fill_median": ar.get("fill_median"),
            "slot_silence_sec": ar.get("slot_silence_sec"),
            # fill_median describes the TRANSLATION's size (raw/slot, before any tempo change);
            # these describe what assembly did about it. Keeping them apart is what lets a run
            # say "the text was short AND the stretch covered N of them".
            "n_stretched": ar.get("n_stretched"),
            "min_stretch_factor": ar.get("min_stretch_factor"),
            # Why no dub was built, when that happened: "no_transcript" / "no_translation" /
            # "no_synthesis". None on every normal run — this key exists only to name a
            # degradation, so a consumer must read null as "not degraded", not as "unknown".
            "degraded": ar.get("degraded"),
        },
        "mux": {
            "dub_mix": mr.get("dub_mix"),
            "dub_gain_db": mr.get("dub_gain_db"),
            # {"dub": bool, "en_srt": bool, "ru_srt": bool} — what the container ACTUALLY
            # carries. None for a report written before 2026-07-28 (unknown, not "complete").
            "tracks": mux_tracks,
        },
        "degraded": degraded,
        "flags_total": flags_total,
        "flags_actionable": flags_actionable,
        "flags_advisory": max(flags_total - flags_actionable, 0),
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
        # Source anomalies are a CROSS-REFERENCE, never a row-maker -- hence this sits AFTER the
        # `not reasons` bail, not before it. An anomalous sentence whose unit came out clean gains
        # no row: there is no audio to listen to, and a fabricated row would break the lead/wav
        # join. run["source"]["items"] is the complete authority; this only tells a human already
        # looking at a flagged unit WHY the English was suspect.
        for m in members:
            trec = tr_by_id.get(m.get("id"))
            kind = trec.get("src") if isinstance(trec, dict) else None
            if kind and kind != "ok" and ("src", kind) not in seen:
                seen.add(("src", kind))
                reasons.append(f"src:{kind}")

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


# --- the queue layer moved out (2026-07-22) ------------------------------------
# `queue_ids`, `queue_playlist`, `classify_workdir`, `collect_entries`, `BATCH_COLUMNS`,
# `batch_row`, `batch_totals`, `render_summary_block` and `render_run_report` now live in
# `overdub/queueview.py`. The seam is the one this section marker already drew: everything above
# reads ONE workdir during a run, everything moved resolves a QUEUE after one. queueview imports
# this module; nothing here may import queueview, or the queue walk lands back inside the
# per-video rollup.


