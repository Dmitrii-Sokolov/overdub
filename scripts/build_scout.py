"""Assemble work/<id>/scout.json from a Sonnet sub-agent's minimal draft (route C).

Same division of labour as build_translation.py, for the same reason: the sub-agent writes ONLY
the judgement part and this script owns the deterministic rest, so the report contract never
rides on an LLM's discipline.

  sub-agent writes work/<id>/scout.draft.json  = {verdict, one_liner, paragraph}
  THIS script adds, from artifacts already on disk:
    video_id          the workdir name
    title             source.info.json (the scout download persists it)
    duration_sec      source.info.json, else max sentence end -- never a network call
    n_sentences       sentences.json
    timings           download / transcribe from timings.json; summarize from the draft's MTIME

`verdict` is a CLOSED vocabulary (_VERDICTS). An unknown value is FATAL rather than clamped --
unlike build_translation's `src`, which clamps because a bad anomaly label must never block a
dub. Here the verdict IS the artifact: the report sorts, colours and recommends on it, so a
clamped-to-"maybe" typo would silently downgrade a video the summarizer actually rated "watch".

WHY THE SUMMARIZE TIME COMES FROM THE FILESYSTEM. Sub-agents run outside this process, in
parallel, so timings.json cannot see them and there is no wall to record. The alternative --
having the sub-agent stamp its own started_at/finished_at -- is model self-measurement: it is
unverifiable and routinely invented. mtime(scout.draft.json) - wave_start is taken from the FS.
What it honestly measures is TIME-UNTIL-DONE FROM THE WAVE START, which for a queued agent
includes its wait for a slot; it is NOT the agent's own working time, and the report labels it
that way. Per-video values therefore do not sum to the wave's wall clock, by construction.

A draft OLDER than the wave start is a draft carried over from an earlier run (the skill's
resume filter deliberately skips an up-to-date summary). That is not an error and not a zero:
the timing is UNKNOWN, so it is written as null and warned about, never silently reported as
instant.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\build_scout.py work\\<id> --wave-start <epoch>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub.workdir import WorkDir, replace_retry        # noqa: E402

# Closed verdict vocabulary. Mirrored by scout_report.py's colour map and by the prompt in the
# overdub-scout skill -- three copies of one list, so changing it means changing all three. Kept
# as bare ASCII keys rather than Russian labels: the label is a PRESENTATION concern and belongs
# in the renderer, where it can be changed without invalidating every scout.json on disk.
_VERDICTS = ("watch", "maybe", "skip")

# Second, ORTHOGONAL axis (viewer-profile.md): what the video costs to consume, not what it is
# worth. A deep-dive that demands practice and a survey you can run while doing something else
# compete for different resources and are not comparable on one scale -- which is why this is a
# separate field rather than two more verdict values. REQUIRED, like the verdict: an optional
# attention label would be omitted exactly when the summarizer was least sure, which is when it
# matters most.
_ATTENTION = ("focus", "background")

# OPTIONAL third axis: is this a known-good author. Optional on purpose -- the trusted-author
# list in the profile is empty today, so every video would carry the same "new" value, and a
# column of one repeated value is noise that trains the reader to ignore that column. Absent
# means "not assessed"; the renderer shows a marker only for "trusted". Filling the profile's
# list later lights this up with NO code change here.
_AUTHOR = ("trusted", "new")

_ONE_LINER_MAX = 200        # visible cap, same discipline as runreport._SUMMARY_MAX_CHARS
_REASON_MAX = 240           # one sentence; the scan table's widest text column
_PARAGRAPH_MAX = 1500


_THUMB_W = 160              # rendered beside a title, and inlined as a data-URI: at ~5 KB each a
                            # 100-video queue costs ~0.7 MB of page, which a 320px source triples


def _ensure_thumb(work: WorkDir, info: dict) -> None:
    """Normalize whatever preview exists into work/<id>/thumb.jpg at _THUMB_W wide.

    ONE output, three possible inputs, because the report must not care which era a workdir
    comes from: a scout run after 2026-07-20 has yt-dlp's `source.audio.jpg` sitting there; an
    older one has nothing and gets a single best-effort fetch from the URL info.json already
    carries; and a workdir built by an earlier report run already has thumb.jpg and is left
    alone.

    NEVER RAISES. A missing preview is cosmetic — the row still carries verdict, reason and a
    link — so no failure here may cost the operator a scanned video. This is also the only
    network call in this script, and it is skipped entirely for the common case.
    """
    if work.thumb.exists():
        return
    src = next((p for p in sorted(work.root.glob("source.audio*.jpg"))), None)
    tmp = work.root / "thumb.src.jpg"
    if src is None:
        # smallest variant at least _THUMB_W wide beats `thumbnail`, which is maxresdefault
        # (~100 KB) — we are about to scale it down anyway
        cands = [t for t in (info.get("thumbnails") or [])
                 if isinstance(t, dict) and isinstance(t.get("width"), int)
                 and t["width"] >= _THUMB_W and t.get("url")]
        url = (min(cands, key=lambda t: t["width"])["url"] if cands
               else info.get("thumbnail") if isinstance(info.get("thumbnail"), str) else None)
        if not url:
            return
        try:
            with urllib.request.urlopen(url, timeout=15) as r:      # noqa: S310 — https, from yt-dlp
                tmp.write_bytes(r.read())
        except Exception as e:                                       # noqa: BLE001 — cosmetic
            print(f"[warn] {work.root.name}: preview fetch failed ({e}) — row renders without one")
            tmp.unlink(missing_ok=True)
            return
        src = tmp
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
             "-vf", f"scale={_THUMB_W}:-2", "-q:v", "6", str(work.thumb)],
            check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"[warn] {work.root.name}: preview scale failed ({e}) — row renders without one")
        work.thumb.unlink(missing_ok=True)
    finally:
        tmp.unlink(missing_ok=True)
        if src is not None and src != tmp:
            src.unlink(missing_ok=True)          # the full-size original is scrap once scaled


def _load_json(path: Path):
    """Tolerant read: None on missing/torn. Same contract every optional-artifact reader in this
    repo uses (runreport._load_json, cli._load_json)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _text_field(raw: dict, key: str, cap: int, path: Path) -> str:
    """One required prose field, validated and capped.

    EMPTY IS FATAL: both report lists render this field for every video, so an empty one is a
    hole in the deliverable, and the sub-agent that produced it needs re-running -- exactly the
    case the skill's `summary pending` line exists to surface. Over-length is NOT fatal: it is
    truncated with a visible marker and a [warn], because a verbose summarizer is a style
    problem, not a broken artifact, and losing the whole video from the report would be the
    larger failure."""
    val = raw.get(key)
    if not isinstance(val, str) or not val.strip():
        sys.exit(f"[FAIL] {path}: '{key}' is missing or empty -- re-run the sub-agent for this "
                 f"video (a report row cannot be rendered without it)")
    val = " ".join(val.split()) if key == "one_liner" else val.strip()
    if len(val) > cap:
        print(f"[warn] {path.parent.name}: '{key}' is {len(val)} chars, capped at {cap}")
        val = val[:cap].rstrip() + " …[truncated]"
    return val


def build(work: WorkDir, wave_start: float | None) -> dict:
    draft_path = work.root / "scout.draft.json"
    raw = _load_json(draft_path)
    if raw is None:
        sys.exit(f"[FAIL] {draft_path} is missing or not readable JSON -- the sub-agent for this "
                 f"video did not finish")
    if not isinstance(raw, dict):
        # A list here means the sub-agent reused the TRANSLATION draft shape. Saying so beats a
        # bare type error: it is the one wrong shape a route-B-trained agent actually produces.
        sys.exit(f"[FAIL] {draft_path} is not a JSON object -- expected "
                 f"{{verdict, attention, one_liner, paragraph}}, got {type(raw).__name__}")

    verdict = raw.get("verdict")
    if verdict not in _VERDICTS:
        sys.exit(f"[FAIL] {draft_path}: verdict {verdict!r} is not one of {_VERDICTS} -- "
                 f"a verdict is what the report sorts and colours on, so it is never guessed")
    attention = raw.get("attention")
    if attention not in _ATTENTION:
        sys.exit(f"[FAIL] {draft_path}: attention {attention!r} is not one of {_ATTENTION} -- "
                 f"the profile makes deep-attention slots the scarce resource, so a video with "
                 f"no cost label cannot be scheduled against one")
    author = raw.get("author")
    if author is not None and author not in _AUTHOR:
        # Clamped to absent, NOT fatal: unlike the two labels above, this axis is optional by
        # design (see _AUTHOR), and refusing the whole video over a mislabelled optional field
        # would drop a usable verdict from the report.
        print(f"[warn] {work.root.name}: author {author!r} is not one of {_AUTHOR} -- recorded "
              f"as not assessed")
        author = None
    one_liner = _text_field(raw, "one_liner", _ONE_LINER_MAX, draft_path)
    # WHY the verdict, kept apart from WHAT the video is (one_liner) and from the full write-up
    # (paragraph). Separate because the scan table has to answer both questions at a glance and
    # one field cannot: "разбор оркестрации агентов" does not say whether to watch it, and
    # "тема в активной работе" does not say what it is about. Required for the same reason the
    # verdict is: an unexplained verdict is one the reader has to take on faith.
    reason = _text_field(raw, "reason", _REASON_MAX, draft_path)
    paragraph = _text_field(raw, "paragraph", _PARAGRAPH_MAX, draft_path)

    sents = _load_json(work.sentences)
    if not isinstance(sents, list):
        sys.exit(f"[FAIL] {work.sentences} is missing or unreadable -- this workdir was never "
                 f"scouted (run --scout first); the summarizer had nothing to read")

    info = _load_json(work.info_json)
    info = info if isinstance(info, dict) else {}
    title = info.get("title") if isinstance(info.get("title"), str) else None
    _ensure_thumb(work, info)                   # cosmetic, never fatal — see the docstring

    dur = info.get("duration")
    if not isinstance(dur, (int, float)) or isinstance(dur, bool) or dur <= 0:
        # Fallback, never a network call: the last sentence's end is a floor on the real
        # duration (trailing music/silence is not transcribed), so it can UNDERSTATE. Recorded
        # with its source so the report can say which one it showed.
        ends = [s.get("end") for s in sents
                if isinstance(s, dict) and isinstance(s.get("end"), (int, float))]
        dur, dur_src = (max(ends), "sentences") if ends else (None, "none")
    else:
        dur, dur_src = float(dur), "info_json"

    timings_doc = _load_json(work.root / "timings.json")
    stages = timings_doc.get("stages") if isinstance(timings_doc, dict) else None
    stages = stages if isinstance(stages, dict) else {}

    def stage_sec(name: str):
        v = stages.get(name)
        return round(float(v), 1) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    summarize_sec = None
    if wave_start is not None:
        elapsed = os.path.getmtime(draft_path) - wave_start
        if elapsed < 0:
            print(f"[warn] {work.root.name}: scout.draft.json predates the wave start -- carried "
                  f"over from an earlier run, summarize time recorded as unknown")
        else:
            summarize_sec = round(elapsed, 1)

    return {
        "video_id": work.root.name,
        "title": title,
        "duration_sec": round(dur, 1) if dur is not None else None,
        "duration_source": dur_src,
        "n_sentences": len(sents),
        "verdict": verdict,
        "attention": attention,
        "author": author,                            # None = not assessed (see _AUTHOR)
        "one_liner": one_liner,
        "reason": reason,
        "paragraph": paragraph,
        "timings": {
            "download_sec": stage_sec("download"),
            "transcribe_sec": stage_sec("transcribe"),
            # time-until-done from the wave start, NOT the agent's own working time (see module
            # docstring). null = unknown, never 0.
            "summarize_sec": summarize_sec,
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="build_scout",
        description="Assemble work/<id>/scout.json from the sub-agent's scout.draft.json.")
    p.add_argument("workdir", type=Path, metavar="work/<id>")
    p.add_argument("--wave-start", type=float, default=None, metavar="EPOCH",
                   help="unix epoch seconds when the summarizer wave was spawned; the draft's "
                        "mtime minus this is the per-video summarize time. Omit and the timing "
                        "is recorded as unknown rather than guessed.")
    args = p.parse_args(argv)
    if not args.workdir.is_dir():
        p.error(f"work dir not found: {args.workdir}")

    work = WorkDir(args.workdir)
    doc = build(work, args.wave_start)

    out = work.root / "scout.json"
    # tmp + replace: the report reads this file, and a torn write would drop the video from the
    # deliverable with no error anywhere. Same discipline as every other artifact flip here.
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    replace_retry(tmp, out)
    t = doc["timings"]
    print(f"[scout] {out}  verdict={doc['verdict']}/{doc['attention']}  "
          f"{doc['n_sentences']} sentences  "
          f"dl={t['download_sec']}s tr={t['transcribe_sec']}s sum={t['summarize_sec']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
