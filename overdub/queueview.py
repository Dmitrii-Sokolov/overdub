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
    ("video", "video"), ("title", "title"), ("wall", "wall"), ("rtf", "rtf"),
    # `flags` leads the flag group as act/total: the operator's first question about a row is "how
    # much is wrong with this one", and answering it used to mean adding five columns by eye
    # (operator report 2026-07-25). The five stay — they say WHAT is wrong, which the sum cannot.
    ("flags", "flags"),
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
        # a duration, not a raw second count — same rule as the totals line (format_dur)
        ("wall", format_dur(t.get("total_wall_s"))),
        ("rtf", str(t.get("rtf"))),
        # actionable/total. Both numbers, because either alone misleads: "2" hides that 21 other
        # things fired, "21" reads as a disaster when 19 are advisory names the operator has
        # already been told to ignore.
        ("flags", f"{run.get('flags_actionable', 0)}/{run.get('flags_total', 0)}"),
        ("floor", f"{fr:.1%}" if fr is not None else "n/a"),
        ("tr", str((run.get("translate", {}) or {}).get("n_failed", 0))),
        ("vf", str((run.get("verify", {}) or {}).get("n_flagged", 0))),
        # cp = ACTIONABLE completeness flags; adv = advisory-only ones (length_short,
        # dup_adjacent, rate_implausible, neg_loss), counted but never a reason to open the
        # video — see the advisory set in
        # runreport. PRE-SCHEMA FALLBACK CONTRACT: a run.json written before the
        # actionable/advisory split carried only n_flagged, so cp falls back to it (adv to 0).
        # This MUST be the same chain render_run_report's flags line uses (n_actionable →
        # n_flagged) — otherwise, on an old run.json, the digest's flags line and these
        # table/card cells report different numbers for the same completeness (the cross-surface
        # divergence the merge exists to kill).
        ("cp", str(cp.get("n_actionable", cp.get("n_flagged", 0)))),
        ("adv", str(cp.get("n_advisory", 0))),
        # src: advisory source-anomaly count. "-" means NOT SCANNED (a translation written
        # without the source-anomaly pass, or a pre-schema run.json) -- never conflate that with
        # a scanned-and-clean "0". --rebuild backfills.
        ("src", str(src.get("n_flagged", 0)) if src.get("scanned") else "-"),
        ("spd_max", str(sp.get("max"))),
        ("n_over", str(sp.get("n_over_1_8", 0))),
    ]
    return {"video_id": str(run.get("video_id")), "title": run.get("title"),
            "needs_triage": bool(run.get("needs_triage")), "cells": cells}


# Longest MIN_WORD_DUR chain at/above which the digest names an alignment collapse. A REPORTING
# threshold, not a pipeline gate (transcribe._guard owns that, on the ratio): 40 sits above every
# healthy video measured on the 2026-07-25 batch (max 30) and below both collapsed ones (45, 82).
_FLOOR_CHAIN_HINT = 40


def format_dur(sec, *, ru: bool = False) -> str:
    """Seconds → the LARGEST fitting unit with one decimal: "3.3h" / «3.3 ч», "47.3m", "18.4s".

    ONE unit, never two (operator rule 2026-07-25): "3h 16m" made the reader parse two numbers
    and then add them, and mixed forms across a report cannot be compared at a glance — a column
    of "3.3h / 0.8h / 12.4m" sorts by eye, "3h 16m / 47m / 12m" does not. Exists at all because
    11778.0s was the only form three batch footers had for a night's work.

    Returns "—" for a non-number: a measured zero prints "0.0s", an unknown never gets to look
    like one (same contract as scout_report.clock, which stays H:MM:SS — a video's RUNTIME is a
    timecode you scrub to, not a quantity you compare)."""
    if not isinstance(sec, (int, float)) or isinstance(sec, bool) or sec < 0:
        return "—"
    h_u, m_u, s_u = (" ч", " мин", " с") if ru else ("h", "m", "s")
    if sec >= 3600:
        return f"{sec / 3600:.1f}{h_u}"
    if sec >= 60:
        return f"{sec / 60:.1f}{m_u}"
    return f"{sec:.1f}{s_u}"


def batch_totals(runs) -> dict:
    """Batch footer numbers: {total_wall, wall_dur, throughput, n_triage, stages} — run_report's
    totals math moved verbatim. throughput is video-seconds per wall-second ("×1.54" style);
    "n/a" on zero wall (an all-resumed batch where no stage ran leaves nothing to divide by).

    `wall_dur` is the same number as a readable duration, because every surface printing
    `total_wall` printed raw seconds. NAMING, read before reusing it: this is the SUM of per-video
    stage walls, NOT the elapsed time of the batch — on route B the Sonnet translate wave sits
    between transcribe and synthesize with no stage timer over it, so the 2026-07-25 batch summed
    3.3h inside a ~5.2 h night. Every caller must label it as work summed per video; `totals_of`
    in scout_report refuses to add a work sum to a wall clock for the same reason, and this must
    not become the back door that does it.

    `stages` is [(name, sec, pct), ...] descending — the batch-level stage split, which is the
    number an optimisation decision actually needs. Per-video `breakdown_pct` already existed but
    answered a different question: one 26-minute video's shares say nothing about where a night
    went. Empty list when no stage timing survived."""
    total_wall = round(sum((r.get("timings", {}) or {}).get("total_wall_s", 0) or 0
                           for r in runs), 1)
    sum_video = sum(((r.get("timings", {}) or {}).get("video_sec") or 0) for r in runs)
    thru = f"×{sum_video / total_wall:.2f}" if total_wall > 0 else "n/a"
    n_triage = sum(1 for r in runs if r.get("needs_triage"))
    per_stage: dict[str, float] = {}
    for r in runs:
        for name, val in ((r.get("timings", {}) or {}).get("stages", {}) or {}).items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                per_stage[name] = per_stage.get(name, 0.0) + float(val)
    stages = [(n, round(v, 1), round(100 * v / total_wall, 1) if total_wall else 0.0)
              for n, v in sorted(per_stage.items(), key=lambda kv: -kv[1])]
    return {"total_wall": total_wall, "wall_dur": format_dur(total_wall),
            "throughput": thru, "n_triage": n_triage, "stages": stages}


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
    timings_line = (f"- timings: {format_dur(t.get('total_wall_s', 0))} "
                    f"({t.get('total_wall_s', 0)}s) · {rtf_part}{work_part}")
    # EVERY stage with its own duration, descending — not the old "top: a%, b%, c%". Three shares
    # out of seven cannot answer "what do I optimise": the tail was invisible, and a percentage
    # with no seconds beside it cannot be compared across videos of different lengths (operator
    # report 2026-07-25). breakdown_pct is preferred over recomputing so this line and run.json
    # can never disagree; the seconds come from stages, the same dict breakdown_pct was built from.
    pct = t.get("breakdown_pct", {}) or {}
    st = t.get("stages", {}) or {}
    ordered = sorted(pct.items(), key=lambda kv: -kv[1])
    stages_line = ("- stages: " + " · ".join(
        f"{name} {format_dur(st.get(name))} {share}%" for name, share in ordered)) if ordered \
        else None

    a = run.get("asr", {}) or {}
    fr = a.get("floor_ratio")
    # The chain, not the ratio, is what a long collapse shows up in — and until now BOTH numbers
    # printed bare, so a video whose timings whisper invented in one stretch read like any other.
    # Measured 2026-07-25 across 24 videos: chains ran 4..30 on the healthy ones, 45 and 82 on the
    # two whose worst units then needed atempo ×2.3 and ×5.4 (invented timings → impossible slots).
    # ADVISORY ONLY, deliberately: transcribe._guard gates on the RATIO because floor_run_ratio's
    # own docstring measured the chain as non-separating (a healthy video reached 17), and
    # cfg.transcribe_floor_run_max is a calibrated number with a DECISIONS record — this line adds
    # a hint for the operator, it does not re-gate anything. The named action is real: seeding for
    # `--repair-asr auto` keys on dup_adjacent / rate_implausible, which fire in exactly the
    # stretch a floor chain marks.
    hint = ""
    if isinstance(a.get("floor_longest_run"), int) and a["floor_longest_run"] >= _FLOOR_CHAIN_HINT:
        hint = "  ← alignment collapse suspected; try --repair-asr auto on this video"
    asr_line = (f"- asr: {a.get('n_words', 0)} words · floor {fr:.2%} "
                f"(longest chain {a.get('floor_longest_run')}){hint}"
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

    # The pronunciation audit, printed only when it has numbers (a pre-schema run.json and any
    # workdir built before the artifact existed both carry None — see the pronounce block in
    # runreport). It is ADVISORY and deliberately not in flags_actionable: every one is a token the
    # pipeline had to invent a Russian reading for, most of them fine. The COUNT is the point —
    # 1587 invented readings in a 24-video batch reached no surface at all before 2026-07-25, so
    # nothing could tell a normal video (28 events) from the one that needs dictionary work (203).
    pr = run.get("pronounce", {}) or {}
    pron_line = (f"- pronounce: {pr.get('n_invented')} invented readings "
                 f"({pr.get('n_fallback')} by rule, {pr.get('n_letters')} letter-spelled) "
                 f"over {pr.get('n_distinct')} distinct latin tokens"
                 if pr.get("n_invented") is not None else None)

    # Slot fill — the one number the speed line above CANNOT carry: speed_factor is floored at
    # 1.0, so an under-filled dub reads "clean" there by construction (8zJlKmgMT44 reported
    # median 1.0 / p95 1.0 while ~23% of its dub was silence). Printed only when the assemble
    # block has it; a run.json predating 2026-07-25 carries None, which is UNKNOWN, not 1.0.
    # Reads in BOTH directions on purpose: the same corpus holds videos at 1.02-1.15, where the
    # slot is too SHORT and atempo is doing the work.
    asm = run.get("assemble", {}) or {}
    stretched = asm.get("n_stretched")
    fill_line = (f"- fill: med {asm.get('fill_median')} raw/slot"
                 f" · slot silence {format_dur(asm.get('slot_silence_sec') or 0)}"
                 + (f" · stretched {stretched} (min ×{asm.get('min_stretch_factor')})"
                    if stretched else "")
                 if asm.get("fill_median") is not None else None)

    lines = [head, timings_line]
    if stages_line:
        lines.append(stages_line)
    lines += [asr_line, flags_line]
    if fill_line:
        lines.append(fill_line)
    if pron_line:
        lines.append(pron_line)
    # Source anomalies, rendered whenever non-empty INDEPENDENT of the
    # [clean]/[TRIAGE] marker — they are advisory, and advisory must never cost visibility.
    # Machine bullets stay together, so this sits after the flags line and before the prose.
    # A run.json predating this schema has no "source" key at all → nothing prints, exactly like
    # every other block here (hence the `"source" in run` guard on the not-scanned line: absent
    # is UNKNOWN, not unscanned); --rebuild backfills it. A run.json that HAS the block always
    # gets one of the two lines, so an unscanned translation reads "not scanned" rather than
    # silently clean.
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
        lines.append("- source anomalies: not scanned (the src pass did not run)")
    if summary:
        lines.append(render_summary_block(summary))
    if offenders:
        lines.append(f"- offenders ({len(offenders)}):")
        for o in offenders:
            snippet = (o.get("src_en") or "").strip().replace("\n", " ")[:60]
            reasons = ", ".join(o.get("reasons", []))
            lines.append(f"  - {o.get('id')} — {reasons} — {snippet}")
    return "\n".join(lines)
