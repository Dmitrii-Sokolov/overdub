"""The shared report data layer: queue → ordered entries → batch-table cells → digest text.

Split out of runreport.py on 2026-07-22 along the section boundary that was already marked
there. The two halves answer different questions and have different consumers:

  - `runreport` reads ONE workdir's artifacts and rolls them up (run.json, triage rows). Its
    caller is the pipeline, per video, during a run.
  - this module resolves a QUEUE — many workdirs, in the operator's order — into what the two
    report surfaces render. Its callers are `scripts/run_report.py` and
    `scripts/scout_report.py`, after a run, never during one.

The dependency is one-way and must stay that way: this imports runreport, runreport imports
nothing from here. A back-import would put the queue walk inside the per-video rollup, which is
the shape the split exists to prevent.

WHY THIS LAYER EXISTS AT ALL (the queue-page merge, 2026-07-21). Both surfaces used to walk the
same queue over the same workdirs separately and had drifted doing it: n_flagged vs
n_actionable, diverged column sets, two different run.json-less special cases. Everything here
is the ONE shared answer to "what is in the queue, what state is each workdir in, and what are
the batch-table strings". Renderers keep only per-medium concerns — truncation, colour, markup.

Pure stdlib plus runreport and WorkDir; no model, no GPU, no network.
"""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path

from .runreport import (
    _load_json,
    build_run_report,
    flagged_units,
    read_summary,
    summarize_offenders,
)
from .workdir import WorkDir

# Same 11-char YouTube-id shape workdir.video_id and the other reporters use.
_YT_ID = re.compile(r"(?:v=|/shorts/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})")

_PLAYLIST_RE = re.compile(r"^#\s*playlist:\s*(?P<rest>.+)$", re.IGNORECASE)


def queue_playlist(path: Path) -> dict | None:
    """`# playlist: <title> | <url>` header → {title, url}. Either half may be omitted.

    A COMMENT rather than a CLI argument or a sidecar: the queue's provenance belongs with the
    queue, so rebuilding the report needs no remembered flag and no network. The parser already
    skips '#' lines, so every queue written before this existed keeps working, and one written
    with the header stays valid input to the pipeline itself.

    Only the FIRST match is used — a second header would be an edit someone forgot to finish,
    and picking one silently is better than concatenating two conflicting provenances."""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        m = _PLAYLIST_RE.match(line.strip())
        if not m:
            continue
        rest = m.group("rest").strip()
        title, _, url = rest.partition("|")
        title, url = title.strip(), url.strip()
        if not url and title.startswith(("http://", "https://")):
            title, url = "", title          # url-only header
        if not (title or url):
            return None
        return {"title": title or url, "url": url or None}
    return None


def queue_ids(path: Path) -> list[str]:
    """Queue order, preserved, deduped. The ONE parse every report surface shares (utf-8-sig
    strips a PowerShell BOM, '#' comments and blanks skipped). A line the regex misses is
    DROPPED here silently -- the skill's S1 gate is where an unmatched URL has to fail loud."""
    ids: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _YT_ID.search(line)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return ids


def classify_workdir(work) -> str:
    """The report shape a workdir has earned: "run" | "pending" | "scout" | "fetched" | "missing".

    One classifier for every report surface — the text digest and the triage HTML used to make
    this call separately and drifted (the "third divergence" the queue-page merge names).

      - "run":     report.json OR translation.json exists — the same two files build_run_report
                   gates on, so "run" means exactly "build_run_report would try to roll this up".
                   (A present-but-torn file still classifies "run"; the build then degrades to
                   None and the renderer keeps its honest skipped note.)
      - "pending": sentences.json parses to a list AND source.mkv exists — a promoted video
                   parked between download and translate (route B step 1 parks the WHOLE batch
                   like this until Sonnet writes translation.json; a workdir between --repair-asr
                   and its re-run has the same shape). Until this kind existed the state was
                   invisible on the triage page — a known gap.
      - "scout":   sentences.json parses to a list AND no source.mkv — --scout ran and stopped
                   there. An EMPTY list is still "scout": it parses, so transcribe ran and
                   produced nothing, and "0 sentences" is a louder report than a dropped row.
      - "fetched": source.wav exists — downloaded but never transcribed (or sentences.json is
                   unreadable, a defect to surface, not a transcript).
      - "missing": everything else — a typo'd path or an empty dir.

    source.mkv is the scout/pending discriminator, and the only fact on disk that settles it:
    scout writes audio only and never a container (DownloadStage._fetch_audio — the video-ready
    gate depends on it staying absent), and nothing in the pipeline ever deletes source.mkv
    (invalidate_downstream keeps it as a named survivor). Its presence is therefore a permanent
    record that the FULL download ran — the workdir is a parked dub, not a scout, and reporting
    it as a scout would present a video that needs RE-RUNNING as one that needs SUMMARIZING."""
    if work.report.exists() or work.translation.exists():
        return "run"
    sents = _load_json(work.sentences)
    if isinstance(sents, list):
        return "pending" if work.source_video.exists() else "scout"
    if work.source_audio.exists():
        return "fetched"
    return "missing"


def collect_entries(queue, workdirs, work_root, *, limit=500, rebuild=False, cfg=None):
    """Resolve a queue + argv workdirs into ordered report entries — the ONE walk both report
    surfaces share. Returns (entries, skipped_names).

    Order: queue ids first (1-based position `n`, preserved even for a video that never
    downloaded — on a queue report, position IS information), then argv workdirs not already
    covered, `n` continuing. Dedup by normcased absolute path, first mention wins.

    Drop policy: a from_queue entry is NEVER dropped whatever its kind — silently shortening the
    deliverable to the videos that happened to work is the exact failure this layer exists to
    prevent (scout_report's rule). An argv workdir of kind "missing"/"fetched" has nothing to
    render and goes to skipped_names instead ("skipped" semantics: a typo'd path
    is printed and honest, never a fabricated card).

    Per entry: kind/n/vid/work/from_queue always; `run` + `units`/`offenders` for kind "run";
    `summary` for EVERY kind (a scout card needs it too); `scout` (parsed scout.json) for ANY
    kind — a dubbed video that was scouted keeps its grade next to its dub metrics;
    `n_sentences` + `duration_sec` for scout/pending kinds (info.json duration, fallback max
    sentence end — the same ladder the triage scout card used; deliberately NO ffprobe reach
    here, that stays build_run_report's fallback).

    `rebuild=True` forces build_run_report over the run.json load. Threaded here as a flag
    rather than handled by the caller because the only caller-side alternative is deleting
    run.json before calling — a read-only reporter must not destroy state to express a CLI
    flag. `cfg` is forwarded to build_run_report (which accepts it for signature parity and
    does not read it today; keeping the pass-through avoids both a config import here and a
    silent break if it ever does)."""
    entries: list[dict] = []
    skipped: list[str] = []
    seen: set[str] = set()

    ordered: list[tuple[Path, bool]] = [(Path(work_root) / vid, True) for vid in (queue or [])]
    ordered += [(Path(d), False) for d in (workdirs or [])]

    for path, from_queue in ordered:
        key = os.path.normcase(os.path.abspath(str(path)))
        if key in seen:
            continue
        seen.add(key)
        work = WorkDir(path)
        kind = classify_workdir(work)
        if not from_queue and kind in ("missing", "fetched"):
            skipped.append(path.name)
            continue
        entry = {
            "kind": kind, "n": len(entries) + 1, "vid": path.name, "work": work,
            "from_queue": from_queue, "run": None, "units": [], "offenders": [],
            "summary": read_summary(work),
            # scout.json read via root — build_scout writes it the same way (no WorkDir property)
            "scout": None,
        }
        scout_doc = _load_json(work.root / "scout.json")
        if isinstance(scout_doc, dict):
            entry["scout"] = scout_doc
        if kind == "run":
            run = None if rebuild else _load_json(work.root / "run.json")
            if run is None:
                # NOT pure — build_run_report unlinks a stale run.json when report.json and
                # translation.json are both unreadable, and may reach for ffprobe. Call it ONCE
                # and keep the result; never call it twice.
                run = build_run_report(work, cfg)
            entry["run"] = run
            if run is not None:
                report = _load_json(work.report)
                translation = _load_json(work.translation)
                entry["units"] = flagged_units(report, translation, limit) if report else []
                entry["offenders"] = summarize_offenders(report, translation) if report else []
        # For the other kinds build_run_report is deliberately NOT called: classify already
        # knows it would return None, and a collector that deletes files (the stale-run.json
        # unlink) as a side effect of READING a report is a trap. The batch sweep owns the
        # self-clear.
        if kind in ("scout", "pending"):
            sents = _load_json(work.sentences)
            sents = sents if isinstance(sents, list) else []
            entry["n_sentences"] = len(sents)
            info = _load_json(work.info_json)
            info = info if isinstance(info, dict) else {}
            dur = info.get("duration")
            if not isinstance(dur, (int, float)) or isinstance(dur, bool) or dur <= 0:
                # scout.json recorded this SAME ladder at scan time (build_scout: info → ends), so
                # when it is already parsed and carries a positive number it outranks a fresh
                # re-derivation from ends — which is exactly what the scout card reads (_views
                # prefers scout.json duration_sec), so both surfaces show one duration, not two.
                sd = entry["scout"].get("duration_sec") if isinstance(entry["scout"], dict) else None
                if isinstance(sd, (int, float)) and not isinstance(sd, bool) and sd > 0:
                    dur = sd
                else:
                    ends = [s.get("end") for s in sents
                            if isinstance(s, dict) and isinstance(s.get("end"), (int, float))]
                    dur = max(ends) if ends else None
            entry["duration_sec"] = dur
        entries.append(entry)
    return entries, skipped


# The batch digest table: ONE ordered (key, label) source of truth for both renderers
# (the queue-page merge — the two batch tables had drifted to different column sets showing
# different completeness numbers for the same run). The label row is exactly what the text
# digest prints.
BATCH_COLUMNS = (
    ("video", "video"), ("title", "title"), ("wall_s", "wall_s"), ("rtf", "rtf"),
    ("floor", "floor"), ("tr", "tr"), ("vf", "vf"), ("cp", "cp"), ("adv", "adv"),
    ("src", "src"), ("spd_max", "spd_max"), ("n_over", ">1.8"), ("triage", "triage"),
)


def batch_row(run) -> dict:
    """One batch-table row from a run.json dict: {video_id, title, needs_triage, cells}.

    `cells` is the ten DATA columns (wall_s .. n_over) as (key, text) pairs, formatted here
    once — these exact strings are the cross-surface contract, printed verbatim by both the
    text digest and the HTML table so the two surfaces can never again disagree about the same
    run. Title and triage are returned RAW instead: their rendering is per-medium (the digest
    truncates the title to 24 chars and prints yes/no; the HTML escapes, links and colours),
    and a pre-rendered string would force one medium's choice on the other."""
    t = run.get("timings", {}) or {}
    sp = run.get("speed", {}) or {}
    fr = (run.get("asr", {}) or {}).get("floor_ratio")
    src = run.get("source", {}) or {}
    cp = run.get("completeness", {}) or {}
    cells = [
        ("wall_s", str(t.get("total_wall_s", ""))),
        ("rtf", str(t.get("rtf"))),
        ("floor", f"{fr:.1%}" if fr is not None else "n/a"),
        ("tr", str((run.get("translate", {}) or {}).get("n_failed", 0))),
        ("vf", str((run.get("verify", {}) or {}).get("n_flagged", 0))),
        # cp = ACTIONABLE completeness flags; adv = advisory-only ones (entity_loss /
        # length_short), counted but never a reason to open the video — see the advisory set in
        # runreport. PRE-SCHEMA FALLBACK CONTRACT: a run.json written before the
        # actionable/advisory split carried only n_flagged, so cp falls back to it (adv to 0).
        # This MUST be the same chain render_run_report's flags line uses (n_actionable →
        # n_flagged) — otherwise, on an old run.json, the digest's flags line and these
        # table/card cells report different numbers for the same completeness (the cross-surface
        # divergence the merge exists to kill).
        ("cp", str(cp.get("n_actionable", cp.get("n_flagged", 0)))),
        ("adv", str(cp.get("n_advisory", 0))),
        # src: advisory source-anomaly count. "-" means NOT SCANNED (route A, or a pre-schema
        # run.json) -- never conflate that with a scanned-and-clean "0". --rebuild backfills.
        ("src", str(src.get("n_flagged", 0)) if src.get("scanned") else "-"),
        ("spd_max", str(sp.get("max"))),
        ("n_over", str(sp.get("n_over_1_8", 0))),
    ]
    return {"video_id": str(run.get("video_id")), "title": run.get("title"),
            "needs_triage": bool(run.get("needs_triage")), "cells": cells}


def batch_totals(runs) -> dict:
    """Batch footer numbers: {total_wall, throughput, n_triage} — run_report's totals math moved
    verbatim. throughput is video-seconds per wall-second ("×1.54" style); "n/a" on zero wall
    (an all-resumed batch where no stage ran leaves nothing to divide by)."""
    total_wall = round(sum((r.get("timings", {}) or {}).get("total_wall_s", 0) or 0
                           for r in runs), 1)
    sum_video = sum(((r.get("timings", {}) or {}).get("video_sec") or 0) for r in runs)
    thru = f"×{sum_video / total_wall:.2f}" if total_wall > 0 else "n/a"
    n_triage = sum(1 for r in runs if r.get("needs_triage"))
    return {"total_wall": total_wall, "throughput": thru, "n_triage": n_triage}


def render_summary_block(summary):
    """The digest's summary section: a '- summary (N words):' header plus the prose wrapped to the
    digest width and indented two spaces, matching the offender bullets' continuation shape.

    DELIBERATE EXCEPTION to render_run_report's English-artifact norm below: this text is REQUIRED
    to be Russian (the video summary) — do not 'fix' it. Paragraph breaks are flattened to single
    newlines (a blank line would terminate the digest's bullet list); the triage HTML keeps them.
    Heading markers are already gone — read_summary strips them — so no line here can start a new
    block."""
    paras = [p for p in summary.split("\n\n") if p.strip()]
    body = [textwrap.fill(" ".join(p.split()), width=94,
                          initial_indent="  ", subsequent_indent="  ") for p in paras]
    return f"- summary ({len(summary.split())} words):\n" + "\n".join(body)


def render_run_report(run, offenders, summary=None):
    """Compact ENGLISH Markdown block for ONE video (the codebase artifact norm is English; the
    Russian human narrative is the skill agent's job). Header + timings line + flags line, an
    optional Russian summary section, plus an offenders bullet list only when non-empty. Pure, no
    I/O — the caller reads the sidecar."""
    vid = run.get("video_id")
    title = run.get("title")
    marker = "TRIAGE" if run.get("needs_triage") else "clean"
    head = f"### {vid}" + (f" — {title}" if title else "") + f"  [{marker}]"

    t = run.get("timings", {}) or {}
    src = t.get("video_sec_source")
    rtf = t.get("rtf")
    rtf_part = f"RTF {rtf} ({src})" if rtf is not None else f"RTF n/a ({src})"
    # The load-excluded pair, printed ONLY when it exists — a run.json predating the detail
    # entries has neither key and prints exactly what it always did. `~` marks partial coverage:
    # some stages still report no work_sec, so the figure is an upper bound, and a bare number
    # would read as the finished one. The coverage list itself stays in run.json rather than the
    # digest line, which is already at its width.
    work_part = ""
    if t.get("rtf_work") is not None:
        mark = "" if t.get("work_complete") else "~"
        work_part = f" · work {t.get('total_work_s')}s / RTF{mark} {t['rtf_work']}"
    top3 = sorted((t.get("breakdown_pct", {}) or {}).items(),
                  key=lambda kv: kv[1], reverse=True)[:3]
    top_part = (" · top: " + ", ".join(f"{k} {v}%" for k, v in top3)) if top3 else ""
    timings_line = f"- timings: {t.get('total_wall_s', 0)}s wall · {rtf_part}{work_part}{top_part}"

    a = run.get("asr", {}) or {}
    fr = a.get("floor_ratio")
    asr_line = (f"- asr: {a.get('n_words', 0)} words · floor {fr:.2%} "
                f"(longest chain {a.get('floor_longest_run')})"
                if fr is not None else "- asr: no words.json")

    tr = run.get("translate", {}) or {}
    v = run.get("verify", {}) or {}
    c = run.get("completeness", {}) or {}
    sp = run.get("speed", {}) or {}
    flags_line = (
        f"- flags: translate {tr.get('n_failed', 0)}/{tr.get('n_sentences', 0)}"
        f" · verify {v.get('n_flagged', 0)}"
        f" · completeness {c.get('n_actionable', c.get('n_flagged', 0))}"
        f" (+{c.get('n_advisory', 0)} advisory)"
        f" · speed med {sp.get('median')}/p95 {sp.get('p95')}/max {sp.get('max')}"
        f" (n>1.8 {sp.get('n_over_1_8', 0)})")

    lines = [head, timings_line, asr_line, flags_line]
    # Source anomalies, rendered whenever non-empty INDEPENDENT of the
    # [clean]/[TRIAGE] marker — they are advisory, and advisory must never cost visibility.
    # Machine bullets stay together, so this sits after the flags line and before the prose.
    # A run.json predating this schema has no "source" key at all → nothing prints, exactly like
    # every other block here (hence the `"source" in run` guard on the not-scanned line: absent
    # is UNKNOWN, not unscanned); --rebuild backfills it. A run.json that HAS the block always
    # gets one of the two lines, so route A reads "not scanned" rather than silently clean.
    s = run.get("source", {}) or {}
    n_sent = (run.get("translate", {}) or {}).get("n_sentences")
    if s.get("n_flagged"):
        lines.append(f"- source anomalies ({s['n_flagged']}):")
        for it in (s.get("items") or []):
            note = (it.get("note") or "").strip().replace("\n", " ")
            en = (it.get("src_en") or "").strip().replace("\n", " ")[:60]
            lines.append(f"  - {it.get('id')} [{it.get('kind')}] {note}")
            lines.append(f"    EN: {en}")
    elif "source" in run and isinstance(n_sent, int) and n_sent and not s.get("scanned"):
        lines.append("- source anomalies: not scanned (route A, or the src pass did not run)")
    if summary:
        lines.append(render_summary_block(summary))
    if offenders:
        lines.append(f"- offenders ({len(offenders)}):")
        for o in offenders:
            snippet = (o.get("src_en") or "").strip().replace("\n", " ")[:60]
            reasons = ", ".join(o.get("reasons", []))
            lines.append(f"  - {o.get('id')} — {reasons} — {snippet}")
    return "\n".join(lines)
