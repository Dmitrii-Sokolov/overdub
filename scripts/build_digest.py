"""Assemble work/<id>/digest.json + digest.md from an Opus sub-agent's draft (route D).

Same division of labour as build_scout.py / build_translation.py, for the same reason: the
sub-agent writes ONLY the retelling and this script owns the deterministic rest, so the page
contract never rides on an LLM's discipline.

  D2 is TWO passes and this script reads the SECOND one's output:
      pass 1 (read)     work/<id>/digest.long.json   complete coverage, length unconstrained
      pass 2 (compress) work/<id>/digest.draft.json  the same document cut to ~1/3, to budget
      both files: {headline, thesis, points: [{title, text, at?}], context, not_covered}
  digest.long.json is never read here and never deleted: it is the record of what the read pass
  produced, and diffing the two is the only way to see what compression cost.
  THIS script adds, from artifacts already on disk:
    video_id          the workdir name
    title/channel/    source.info.json (every fetch persists it) -- a transcript carries none
      upload_date     of the three, and an invented channel or date is worse than an absent one
    duration_sec      source.info.json, else max sentence end -- never a network call
    n_sentences       sentences.json
    timings           two KINDS of number, deliberately kept apart and never summed together:
                        *_sec        the pipeline's wall clock per stage (timings.json.stages)
                        *_work_sec   the same stage measured from inside, load excluded
                        digest_sec   the video's whole D2 chain, mtime(digest.started) ->
                                     mtime(digest.draft.json) — i.e. read pass + compress pass, both
                                     agents, since the marker is the read pass's first act and the
                                     draft is the compressor's last. Absent when no marker was
                                     written. It is NOT one agent's window and must not be reported
                                     as one.
  and renders digest.md -- the same document as a pasteable Markdown file, DERIVED, never
  written by the agent (one source of truth; a hand-written .md would drift from the page).

WHAT IS FATAL AND WHAT IS NOT. Every prose field is REQUIRED and empty is fatal: the page
renders all five for every video, so an empty one is a hole in the deliverable and the sub-agent
needs re-running. Over-length is NOT fatal -- truncated with a visible marker and a [warn],
because a verbose writer is a style problem while losing the video from the page is a lost
video. `points` is fatal when it is not a non-empty list of well-formed items, and merely
WARNED about when the count sits outside 3..8: the band is editorial guidance (a genuinely
single-topic video has three points and a three-hour panel has eight), and refusing a digest
over its bullet count would discard real work to enforce a preference. An unparseable `at`
marker is dropped, not fatal -- it is navigation, and the point's text survives without it.

There is deliberately NO closed vocabulary here, unlike build_scout's `quality`: route D grades
nothing. That is the whole difference between the two routes -- scout answers "is this worth
dubbing", digest answers "what is in it", and a retelling has no verdict to typo.

WHY THE DIGEST TIMING COMES FROM THE FILESYSTEM (inherited verbatim from build_scout, and the
reasoning is the same). Sub-agents run outside this process and in parallel, so timings.json
cannot see them. The obvious alternative -- the agent stamping its own started_at/finished_at --
is model self-measurement: unverifiable and routinely invented. So the stamps come from the OS:
the agent's first action is to touch `digest.started`, its last is to write the draft, and mtime
supplies both times. The agent is never asked what time it is, only to touch a file.

NO NETWORK, and that includes the preview: `ensure_thumb_local` normalizes whatever preview
bytes the fetch already left in the workdir, and the ONE networked backfill in this repo stays
build_scout's (route C). A workdir predating the thumbnail sidecar therefore renders without a
picture on this page -- cosmetic, and the alternative is a second reason to talk to YouTube.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\build_digest.py work\\<id> --wave-start <epoch>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub.workdir import WorkDir, ensure_thumb_local, replace_retry     # noqa: E402

# Visible caps, same discipline as build_scout's _ONE_LINER_MAX: a cap truncates and warns, it
# never rejects.
#
# EACH ONE IS ~30% ABOVE THE BUDGET THE COMPRESSOR IS GIVEN (450 per point, 600 thesis, 700
# context, 350 worth-watching), and the gap is the whole design: a slight overrun keeps its prose, a
# systematic one gets cut and reported.
#
# THE BUDGET BELONGS TO THE COMPRESS PASS, NOT TO THE WRITER, and that is measured rather than
# stylistic. Asking the composing agent for a length does not work — same video, same transcript,
# only the wording of the brevity instruction changed:
#     sentence counts ("1-3 sentences")   11,266 chars   7 points   10 truncations
#     character budgets ("~450 chars")    11,591 chars   9 points   12 truncations
# Zero reduction against a predicted 3,500, because a model cannot count characters while composing
# and the budget line loses to the concrete instruction beside it. An EDITOR holding the text can
# count, which is why route D compresses in a second pass (DECISIONS 2026-07-30).
#
# Raising a cap without raising the compressor's budget only hides an overrun; lowering one below the
# budget truncates compliant output. Change them in pairs.
_HEADLINE_MAX = 240
_THESIS_MAX = 800
_CONTEXT_MAX = 900
_NOT_COVERED_MAX = 450
_POINT_TITLE_MAX = 120
# 900, not 600, and the gap between this and the compressor's 450 budget is DELIBERATE — it is the
# one cap set above what the model actually writes rather than at what we asked for. Three length
# levers were measured on real waves (2026-07-30) and only one instruction type is ever obeyed:
#     "1-3 sentences"        → 11.3k document (asked ~3.5k)
#     "up to ~450 chars"     → 11.6k document (asked ~3.5k)
#     "cut to one third"     → 2.78x / 2.85x / 2.87x / 2.88x / 2.89x   (five videos)
#     "cut to one fifth"     → 2.99x                                    (same video, same input)
# The ratio is not a knob: ~2.9x is the model's own compression rate for this edit, and asking for a
# deeper cut produced the same number. What IS obeyed exactly is the POINT COUNT (11->6, 9->5, 7->4,
# 6->4, 5->3, every run inside _points_ceiling). So the document's size is governed by the ladder,
# and this cap's job goes back to catching a runaway (a 3000-char "point") instead of enforcing a
# style — because a cap that enforces style deletes content, and it deletes the marginal finding
# first. Want a shorter page for long videos? Lower the ladder, not this number.
_POINT_TEXT_MAX = 900

# Advisory band for the number of points. The ceiling is DURATION-AWARE (see _points_ceiling): a
# flat 3..8 band let 6 points through on an 8-minute news segment on the first real wave — inside
# the band, so nothing fired, while the ladder in the prompt asks for 3-4 there. A flat band cannot
# express "padding", because padding is a ratio of points to material, not a count.
# Only the hard ceiling is fatal, and it exists to catch a sub-agent that pasted the transcript back
# as bullets instead of digesting it.
_POINTS_MIN = 3
_POINTS_HARD_MAX = 20

# (upper bound in minutes, points) — the prompt's ladder, as a number this script can check.
_POINTS_LADDER = ((25, 4), (120, 6))
_POINTS_LADDER_TOP = 8

# M:SS or H:MM:SS — the shape the prompt asks for, and the shape a reader can scrub to.
_AT_RE = re.compile(r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})$")

# A marker past the end of the video is a fabrication, not a rounding error. The slack covers the
# honest case: duration_source == "sentences" UNDERSTATES the runtime (trailing music is not
# transcribed), so a point legitimately placed near the end can land just past that floor.
_AT_SLACK_SEC = 120.0

# Below this share of the runtime the last marker suggests the digest read the opening and
# stopped — the failure mode that matters most for "did I miss anything", and the reason `at` is
# worth collecting at all. WARN ONLY: markers are optional, a video whose substance really is
# front-loaded exists, and this script must not turn an editorial judgement into a build failure.
_COVERAGE_MIN = 0.6


def _load_json(path: Path):
    """Tolerant read: None on missing/torn. Same contract every optional-artifact reader in this
    repo uses (runreport._load_json, build_scout._load_json)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _text_field(raw: dict, key: str, cap: int, path: Path, *, collapse: bool = False) -> str:
    """One required prose field, validated and capped. See the module docstring for why empty is
    fatal and over-length is not. `collapse` folds all whitespace into single spaces — used for
    the fields that must render as ONE line (headline, point titles), never for the paragraphs,
    whose blank lines are the writer's own structure."""
    val = raw.get(key)
    if not isinstance(val, str) or not val.strip():
        sys.exit(f"[FAIL] {path}: '{key}' is missing or empty -- re-run the sub-agent for this "
                 f"video (the page cannot render a digest without it)")
    val = " ".join(val.split()) if collapse else val.strip()
    if len(val) > cap:
        print(f"[warn] {path.parent.name}: '{key}' is {len(val)} chars, capped at {cap}")
        val = val[:cap].rstrip() + " …[truncated]"
    return val


def at_sec(text: str) -> float | None:
    """"6:12" / "1:02:30" → seconds, or None for anything else (including 6:99 and 1:70:00).

    Parsed rather than trusted because the marker goes into the page as a place the reader will
    scrub to: a malformed one is dropped and the point renders without it."""
    if not isinstance(text, str):
        return None
    m = _AT_RE.match(text.strip())
    if not m:
        return None
    h, mm, ss = m.group(1), int(m.group(2)), int(m.group(3))
    if ss > 59 or (h is not None and mm > 59):
        return None
    return int(h or 0) * 3600 + mm * 60 + ss


def _points_ceiling(duration: float | None) -> int:
    """The prompt's ladder as a number this script can check: <=25 min → 4, <=2 h → 6, longer → 8.

    An unknown duration gets the TOP of the ladder, not the bottom: with nothing to compare against,
    a padding warning would be a guess, and this check exists to report a measured ratio."""
    if duration is None:
        return _POINTS_LADDER_TOP
    for upper_min, n in _POINTS_LADDER:
        if duration <= upper_min * 60:
            return n
    return _POINTS_LADDER_TOP


def _points(raw: dict, path: Path, duration: float | None) -> list[dict]:
    """The bullet list: [{title, text, at?}] — what the video actually covers.

    THIS is the field the whole route exists for ("what was touched on"), so its shape is
    checked hard and its editorial size is only advised on. A malformed ITEM is fatal rather
    than skipped: silently dropping one would produce a digest that is short by exactly the
    topic the reader was trying not to miss."""
    items = raw.get("points")
    if not isinstance(items, list) or not items:
        sys.exit(f"[FAIL] {path}: 'points' must be a non-empty JSON list of "
                 f"{{title, text}} objects -- got {type(items).__name__}")
    if len(items) > _POINTS_HARD_MAX:
        sys.exit(f"[FAIL] {path}: {len(items)} points -- that is a transcript, not a digest "
                 f"(hard ceiling {_POINTS_HARD_MAX}); re-run the sub-agent")
    out: list[dict] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            sys.exit(f"[FAIL] {path}: points[{i}] is {type(it).__name__}, expected an object "
                     f"with 'title' and 'text'")
        title = _text_field(it, "title", _POINT_TITLE_MAX, path, collapse=True)
        text = _text_field(it, "text", _POINT_TEXT_MAX, path)
        point = {"title": title, "text": text}
        rawat = it.get("at")
        if rawat is not None:
            sec = at_sec(rawat)
            if sec is None:
                print(f"[warn] {path.parent.name}: points[{i}] 'at' {rawat!r} is not M:SS or "
                      f"H:MM:SS -- dropped, the point keeps its text")
            elif duration is not None and sec > duration + _AT_SLACK_SEC:
                # Past the end of the video: the marker cannot be what it claims to be, so it is
                # dropped rather than shown. Said out loud because it is evidence about the
                # sub-agent (a fabricated timestamp), not just a cosmetic loss.
                print(f"[warn] {path.parent.name}: points[{i}] 'at' {rawat} is past the "
                      f"video's {duration:.0f}s -- dropped as fabricated")
            else:
                point["at"] = str(rawat).strip()
                point["at_sec"] = sec
        out.append(point)
    ceiling = _points_ceiling(duration)
    if len(out) < _POINTS_MIN:
        print(f"[warn] {path.parent.name}: {len(out)} points -- the prompt asks for at least "
              f"{_POINTS_MIN} (kept as written)")
    elif len(out) > ceiling:
        span = f"{duration / 60:.0f}-minute" if duration else "unknown-length"
        print(f"[warn] {path.parent.name}: {len(out)} points for a {span} video -- the ladder asks "
              f"for at most {ceiling} here; the extra ones are usually padding (kept as written)")
    # Coverage, measured only where the sub-agent left markers: if the LAST one sits in the first
    # 60% of the runtime, the digest probably describes the opening and stops. That is exactly the
    # silent failure "did I miss anything" cannot survive, and it is invisible on the page.
    spans = [p["at_sec"] for p in out if "at_sec" in p]
    if spans and duration and max(spans) < _COVERAGE_MIN * duration:
        print(f"[warn] {path.parent.name}: last point marker at {max(spans):.0f}s of a "
              f"{duration:.0f}s video -- the digest may cover only the opening; check the tail "
              f"of sentences.json before trusting it")
    return out


def lead_in(title: str) -> str:
    """Bold lead-in for a bullet, matching the reference digest's shape ("**Название.** текст").

    The period is added HERE and not asked of the model: a prompt that requests terminal
    punctuation gets it inconsistently, and "**Название**." vs "**Название.**" is exactly the kind
    of drift a deterministic renderer exists to remove.

    PUBLIC because both renderers need it — this file's Markdown and digest_report's HTML. The
    title is stored raw in digest.json on purpose: the punctuation is a presentation choice, and
    baking it into the artifact would freeze one renderer's decision into every file on disk."""
    return title if title[-1] in ".!?…:;," else title + "."


def render_md(doc: dict) -> str:
    """digest.json → the pasteable Markdown document, in the shape of the reference digest:
    bold headline, thesis paragraph, the bullet list under a label, the context paragraph, then
    the bold "worth watching if" line.

    DELIBERATE EXCEPTION to this repo's English-artifact norm, the same one queueview.
    render_summary_block carries: the labels here are part of a RUSSIAN document meant to be read
    and pasted by a Russian reader — do not "fix" them to English. Everything around them (field
    names, warnings, this docstring) stays English.

    No title/URL header on purpose: the reference document starts at the headline, and the page
    already carries title, link and preview. Adding them here would make the two surfaces
    disagree about what the document IS."""
    lines = [f"**{doc['headline']}**", "", doc["thesis"], ""]
    if doc.get("points"):
        lines += ["Ключевые находки:", ""]
        for p in doc["points"]:
            at = f" ({p['at']})" if p.get("at") else ""
            lines.append(f"- **{lead_in(p['title'])}**{at} {p['text']}")
        lines.append("")
    lines += [doc["context"], "", f"**Стоит смотреть, если** {doc['not_covered']}", ""]
    return "\n".join(lines)


def build(work: WorkDir, wave_start: float | None) -> dict:
    draft_path = work.root / "digest.draft.json"
    raw = _load_json(draft_path)
    if raw is None:
        # NEVER falls back to digest.long.json, even when one is sitting right beside it: that file
        # is the READ pass's output, and shipping it as the digest would silently publish the
        # uncompressed version — a format regression with no signal anywhere. A loud failure sends
        # the operator to re-run the cheap half instead.
        extra = (" (digest.long.json IS present, so the read pass finished and the COMPRESS pass did"
                 " not -- re-run D2 with this id in compressOnly)"
                 if (work.root / "digest.long.json").exists() else "")
        sys.exit(f"[FAIL] {draft_path} is missing or not readable JSON -- the sub-agent for this "
                 f"video did not finish{extra}")
    if not isinstance(raw, dict):
        # A list here means the sub-agent reused the TRANSLATION draft shape. Saying so beats a
        # bare type error: it is the one wrong shape a route-B-trained agent actually produces.
        sys.exit(f"[FAIL] {draft_path} is not a JSON object -- expected "
                 f"{{headline, thesis, points, context, not_covered}}, got {type(raw).__name__}")

    sents = _load_json(work.sentences)
    if not isinstance(sents, list):
        sys.exit(f"[FAIL] {work.sentences} is missing or unreadable -- this workdir has no "
                 f"transcript (run the D1 command first); the sub-agent had nothing to read")

    info = _load_json(work.info_json)
    info = info if isinstance(info, dict) else {}
    title = info.get("title") if isinstance(info.get("title"), str) else None
    # channel first, uploader as the fallback: yt-dlp fills both for YouTube but only `uploader`
    # for some extractors, and the page prints whichever exists rather than a bare id.
    channel = next((info[k] for k in ("channel", "uploader")
                    if isinstance(info.get(k), str) and info[k].strip()), None)
    upload = info.get("upload_date")
    upload = upload if isinstance(upload, str) and re.fullmatch(r"\d{8}", upload) else None
    ensure_thumb_local(work)              # cosmetic, offline, never fatal — see the docstring

    dur = info.get("duration")
    if not isinstance(dur, (int, float)) or isinstance(dur, bool) or dur <= 0:
        # Fallback, never a network call: the last sentence's end is a FLOOR on the real duration
        # (trailing music/silence is not transcribed), so it can understate — which is why the
        # `at` guard above carries slack. Recorded with its source so the page can say which.
        ends = [s.get("end") for s in sents
                if isinstance(s, dict) and isinstance(s.get("end"), (int, float))]
        dur, dur_src = (max(ends), "sentences") if ends else (None, "none")
    else:
        dur, dur_src = float(dur), "info_json"

    headline = _text_field(raw, "headline", _HEADLINE_MAX, draft_path, collapse=True)
    thesis = _text_field(raw, "thesis", _THESIS_MAX, draft_path)
    context = _text_field(raw, "context", _CONTEXT_MAX, draft_path)
    not_covered = _text_field(raw, "not_covered", _NOT_COVERED_MAX, draft_path)
    points = _points(raw, draft_path, dur)

    timings_doc = _load_json(work.root / "timings.json")
    timings_doc = timings_doc if isinstance(timings_doc, dict) else {}
    stages = timings_doc.get("stages")
    stages = stages if isinstance(stages, dict) else {}
    detail = timings_doc.get("detail")
    detail = detail if isinstance(detail, dict) else {}
    tr_detail = detail.get("transcribe")
    tr_detail = tr_detail if isinstance(tr_detail, dict) else {}

    def _num(d: dict, name: str, nd: int | None = 1):
        """Optional numeric field, rounded. nd=None means a COUNT: kept an int, because
        'asr_passes: 1.0' reads as a measurement of something continuous when it is a tally."""
        v = d.get(name)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return None
        return int(v) if nd is None else round(float(v), nd)

    # RAW STAMPS, not a derived per-video duration — build_scout's docstring records what happened
    # when a wave-relative duration was published as a per-video number (a 16x difference in input
    # producing a 20% difference in "time", because every agent finished near the end of the wave).
    # The only figure a wave honestly supports is its wall clock, which needs the whole queue, so
    # digest_report derives it and this script stores the two facts it has.
    draft_at = os.path.getmtime(draft_path)
    wave = None
    if wave_start is not None:
        if draft_at < wave_start:
            print(f"[warn] {work.root.name}: digest.draft.json predates the wave start -- "
                  f"carried over from an earlier run, excluded from the wave's wall clock")
        wave = {"start": round(wave_start, 1), "draft_at": round(draft_at, 1)}

    # PER-VIDEO cost, from the sub-agent's own marker. `wave.start` cannot give this: it is shared
    # by every agent in the spawn, so it charges an agent for however long it sat behind the
    # concurrency cap. KNOWN FLOOR — the marker lands after the agent's first tool round-trip — and
    # it degrades to ABSENT rather than to a wrong number.
    digest_sec = None
    started = work.root / "digest.started"
    try:
        started_at = os.path.getmtime(started)
    except OSError:
        started_at = None
    if started_at is None:
        # The agent wrote its real artifact and skipped the marker: the digest is fine and only
        # the timing is lost. SAID OUT LOUD because the loss is otherwise perfectly silent — the
        # workdir looks complete and the wave quietly rests on one fewer sample.
        print(f"[warn] {work.root.name}: no digest.started marker -- the digest is intact, but "
              f"this video contributes no per-video time and the wave becomes a floor")
    elif started_at <= draft_at:
        digest_sec = round(draft_at - started_at, 1)
    else:
        print(f"[warn] {work.root.name}: digest.started is newer than digest.draft.json -- "
              f"the pair is not one agent's run, per-video digest time recorded as unknown")

    return {
        "video_id": work.root.name,
        "title": title,
        "channel": channel,
        "upload_date": upload,                        # YYYYMMDD or None — never inferred
        "duration_sec": round(dur, 1) if dur is not None else None,
        "duration_source": dur_src,
        "n_sentences": len(sents),
        "headline": headline,
        "thesis": thesis,
        "points": points,
        "context": context,
        "not_covered": not_covered,
        "timings": {
            # *_sec = the pipeline's wall clock for the stage, model load included. What the run
            # cost, and what the page's strip sums.
            "download_sec": _num(stages, "download"),
            "transcribe_sec": _num(stages, "transcribe"),
            # *_work_sec = the same stage with the load and warmup excluded, i.e. what this VIDEO
            # cost — the pair to compare across builds. NEVER summed into the strip.
            "transcribe_work_sec": _num(tr_detail, "work_sec"),
            # 2 means the alignment guard re-ran ASR: that video cost roughly double for a reason
            # unrelated to whatever is being measured.
            "transcribe_asr_passes": _num(tr_detail, "asr_passes", None),
            # per-agent, from the marker file. Absent when the agent wrote none; never inferred.
            "digest_sec": digest_sec,
        },
        # raw epochs, never a per-video duration — see the comment above `wave`
        "wave": wave,
    }


def _write(path: Path, text: str) -> None:
    """tmp + replace: the page reads these files, and a torn write would drop the video from the
    deliverable with no error anywhere. Same discipline as every other artifact flip here."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    replace_retry(tmp, path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="build_digest",
        description="Assemble work/<id>/digest.json + digest.md from the sub-agent's "
                    "digest.draft.json.")
    p.add_argument("workdir", type=Path, metavar="work/<id>")
    p.add_argument("--wave-start", type=float, default=None, metavar="EPOCH",
                   help="unix epoch seconds when the digest wave was spawned; stored with the "
                        "draft's mtime so the page can derive the WAVE's wall clock (last draft "
                        "minus first start). Omit and the wave is recorded as unknown rather "
                        "than guessed.")
    args = p.parse_args(argv)
    if not args.workdir.is_dir():
        p.error(f"work dir not found: {args.workdir}")

    work = WorkDir(args.workdir)
    doc = build(work, args.wave_start)
    _write(work.root / "digest.json", json.dumps(doc, ensure_ascii=False, indent=2))
    _write(work.root / "digest.md", render_md(doc))

    t = doc["timings"]
    extra = "".join(f" {k}={t[k]}" for k in ("transcribe_work_sec", "digest_sec")
                    if t.get(k) is not None)
    n_at = sum(1 for pt in doc["points"] if pt.get("at"))
    print(f"[digest] {work.root / 'digest.json'}  {len(doc['points'])} points "
          f"({n_at} timestamped)  {doc['n_sentences']} sentences  "
          f"dl={t['download_sec']}s tr={t['transcribe_sec']}s{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
