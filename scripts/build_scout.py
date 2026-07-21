"""Assemble work/<id>/scout.json from a Sonnet sub-agent's minimal draft (route C).

Same division of labour as build_translation.py, for the same reason: the sub-agent writes ONLY
the judgement part and this script owns the deterministic rest, so the report contract never
rides on an LLM's discipline.

  sub-agent writes work/<id>/scout.draft.json  = {quality, one_liner, highlight, paragraph}
  THIS script adds, from artifacts already on disk:
    video_id          the workdir name
    title             source.info.json (the scout download persists it)
    duration_sec      source.info.json, else max sentence end -- never a network call
    n_sentences       sentences.json
    timings           two KINDS of number, deliberately kept apart and never summed together:
                        *_sec        the pipeline's wall clock per stage (timings.json.stages) --
                                     model load included, i.e. what the run actually cost
                        *_work_sec   the same stage measured from inside, load and warmup
                                     excluded (timings.json.detail) -- what THIS video cost, and
                                     the only one of the two that compares across builds
                        summarize_sec  the sub-agent's own window, mtime(scout.started) ->
                                     mtime(scout.draft.json). Absent when it wrote no marker.

`quality` is a CLOSED vocabulary (_QUALITY). An unknown value is FATAL rather than clamped --
unlike build_translation's `src`, which clamps because a bad anomaly label must never block a
dub. Here the grade IS the artifact: the report colours and counts on it, so a
clamped-to-"maybe" typo would silently downgrade a video the summarizer actually rated "watch".

WHY THE SUMMARIZE TIMINGS COME FROM THE FILESYSTEM. Sub-agents run outside this process and in
parallel, so timings.json cannot see them. The obvious alternative -- the agent stamping its own
started_at/finished_at -- is model self-measurement: unverifiable and routinely invented. So the
stamps come from the filesystem: the agent's first action is to touch `scout.started`, its last
is to write `scout.draft.json`, and the OS supplies both times. The agent is never asked what
time it is, only to touch a file.

The first attempt stored a per-video duration, mtime(draft) - wave_start, and it was WRONG in a
way only real data exposed (measured 2026-07-20): a 500-sentence transcript reported 1506 s and
a 31-sentence one 1252 s. A 16x difference in input produced a 20% difference in "time", because
every agent finished near the end of the wave and each was therefore reporting the WAVE's length
rather than its own cost. The number looked per-video and was not.

Now the raw pair is stored and nothing is derived here. The only figure the wave honestly
supports is its WALL CLOCK -- last draft minus first start -- which needs the whole queue, so
scout_report computes it. A draft older than the wave start is a carry-over (the skill's resume
filter deliberately skips an up-to-date summary); its stamps are still recorded as the facts
they are, warned about, and excluded from the wall clock by the report.

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

from overdub.workdir import WorkDir, jpeg_size, replace_retry        # noqa: E402

# Closed verdict vocabulary. Mirrored by scout_report.py's colour map and by the prompt in the
# overdub-scout skill -- three copies of one list, so changing it means changing all three. Kept
# as bare ASCII keys rather than Russian labels: the label is a PRESENTATION concern and belongs
# in the renderer, where it can be changed without invalidating every scout.json on disk.
# Quality of the MATERIAL -- substance, currency, delivery -- and deliberately NOT "should this
# person watch it" (revised 2026-07-20). The previous verdict vocabulary was watch/maybe/skip,
# judged against the viewer profile, and the first real queue came back 0 watch / 1 maybe /
# 9 skip: a personal verdict is a decision taken FOR the reader, it collapses toward "no", and it
# cannot be checked against anything. An assessment of the material can: two people can disagree
# about whether to watch a well-made video, but not about whether it is well made.
#
# The viewer profile stays in the loop, demoted to context: it shapes WHAT gets named as the
# interesting part and what counts as already-known, never the grade.
_QUALITY = ("high", "medium", "low")

# OPTIONAL third axis: is this a known-good author. Optional on purpose -- the trusted-author
# list in the profile is empty today, so every video would carry the same "new" value, and a
# column of one repeated value is noise that trains the reader to ignore that column. Absent
# means "not assessed"; the renderer shows a marker only for "trusted". Filling the profile's
# list later lights this up with NO code change here.
_AUTHOR = ("trusted", "new")

_ONE_LINER_MAX = 200        # visible cap, same discipline as runreport._SUMMARY_MAX_CHARS
_HIGHLIGHT_MAX = 240        # one sentence; the scan table's widest text column
_PARAGRAPH_MAX = 1500


_THUMB_W = 160              # MUST be >= the width scout_report renders the preview at, or the
                            # scan table upscales the file into a wider slot and the result is
                            # soft. That is the ONLY hard rule here; everything else is weight.
                            #
                            # Inlined as a data-URI (the Artifact CSP blocks a remote src), and
                            # inlined TWICE per video -- scan row and card -- so this number is
                            # page weight, doubled. MEASURED on the 6-video Test queue, same
                            # frames re-encoded at both widths: 320px -> 66 KB on disk, 177 KB
                            # once base64'd into the page, which was 78% of a 226 KB report.
                            # 160px -> 23 KB and 63 KB, i.e. 35% of the bytes for the same
                            # rendered size, because scout_report draws the preview at 160.
                            #
                            # 320 was briefly kept as a 2x source for hi-DPI sharpness. Dropped:
                            # a scan-table preview is a thumbnail the reader glances at to
                            # recognize a video, not an image they study, and 3/4 of the page
                            # was being spent on retina detail nobody looks for.


def _ensure_thumb(work: WorkDir, info: dict) -> None:
    """Normalize whatever preview exists into work/<id>/thumb.jpg at _THUMB_W wide.

    ONE output, four possible inputs, because the report must not care which era a workdir comes
    from: a scout run after 2026-07-20 has yt-dlp's `source.audio.jpg` sitting there; an older
    one has nothing and gets a single best-effort fetch from the URL info.json already carries; a
    workdir whose thumb.jpg is already at most _THUMB_W wide is left alone; and one whose
    thumb.jpg is WIDER is re-scaled from itself.

    THAT LAST CASE IS THE WHOLE REASON THIS IS NOT `if exists: return` (2026-07-21). It was, and
    the result was that lowering _THUMB_W changed nothing for any workdir already on disk: every
    existing preview kept its old width forever and the reports kept carrying the old bytes. The
    size of this artifact has to be self-correcting, because the number that defines it lives in
    a different file from the files it governs. Re-scaling needs NO NETWORK -- a wider preview is
    its own best source.

    NEVER RAISES. A missing preview is cosmetic — the row still carries the grade, the highlight
    and a link — so no failure here may cost the operator a scanned video. A failed re-scale
    leaves the existing preview untouched rather than destroying a working one: ffmpeg writes to
    a temp path and the flip is atomic. The network call is skipped entirely for every case but
    the empty workdir.
    """
    fetched = work.root / "thumb.src.jpg"       # only written on the network path
    src = None
    if work.thumb.exists():
        wh = jpeg_size(work.thumb)
        # unreadable header -> leave it alone. The bytes may still decode in a browser, and
        # re-encoding something we cannot measure could as easily make it worse as better.
        if wh is None or wh[0] <= _THUMB_W:
            return
        src = work.thumb
    if src is None:
        src = next((p for p in sorted(work.root.glob("source.audio*.jpg"))), None)
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
                fetched.write_bytes(r.read())
        except Exception as e:                                       # noqa: BLE001 — cosmetic
            print(f"[warn] {work.root.name}: preview fetch failed ({e}) — row renders without one")
            fetched.unlink(missing_ok=True)
            return
        src = fetched
    # ffmpeg cannot read and write one path, and on the re-scale path src IS the destination --
    # so the output always goes to a temp and only replaces the real file once it exists
    out = work.root / "thumb.out.jpg"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
             "-vf", f"scale={_THUMB_W}:-2", "-q:v", "6", str(out)],
            check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"[warn] {work.root.name}: preview scale failed ({e}) — row renders without one")
        out.unlink(missing_ok=True)
    else:
        replace_retry(out, work.thumb)
    finally:
        fetched.unlink(missing_ok=True)
        if src not in (work.thumb, fetched):
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
                 f"{{quality, one_liner, highlight, paragraph}}, got {type(raw).__name__}")

    quality = raw.get("quality")
    if quality not in _QUALITY:
        sys.exit(f"[FAIL] {draft_path}: quality {quality!r} is not one of {_QUALITY} -- "
                 f"it is what the report colours on, so it is never guessed")
    author = raw.get("author")
    if author is not None and author not in _AUTHOR:
        # Clamped to absent, NOT fatal: unlike the two labels above, this axis is optional by
        # design (see _AUTHOR), and refusing the whole video over a mislabelled optional field
        # would drop a usable verdict from the report.
        print(f"[warn] {work.root.name}: author {author!r} is not one of {_AUTHOR} -- recorded "
              f"as not assessed")
        author = None
    one_liner = _text_field(raw, "one_liner", _ONE_LINER_MAX, draft_path)
    # The most interesting/useful thing IN the video, kept apart from WHAT it is (one_liner).
    # Replaced the old `reason` field, which justified a personal verdict: this states what the
    # material offers and leaves the decision entirely with the reader. It also carries the
    # "требует концентрации" note when the video needs undivided attention -- that used to be a
    # separate enum, and on the first real queue 28 of 30 videos took the same value, so a field
    # that never varies became a sentence that only appears when it is true.
    highlight = _text_field(raw, "highlight", _HIGHLIGHT_MAX, draft_path)
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
    timings_doc = timings_doc if isinstance(timings_doc, dict) else {}
    stages = timings_doc.get("stages")
    stages = stages if isinstance(stages, dict) else {}
    # detail[<stage>] — what the stage measured about itself, model load excluded. Absent for
    # any workdir transcribed before this existed, which is why every field below is optional.
    detail = timings_doc.get("detail")
    detail = detail if isinstance(detail, dict) else {}
    tr_detail = detail.get("transcribe")
    tr_detail = tr_detail if isinstance(tr_detail, dict) else {}

    def _num(d: dict, name: str, nd: int = 1):
        """Optional numeric field, rounded. nd=None means a COUNT: kept an int, because
        'asr_passes: 1.0' reads as a measurement of something continuous when it is a tally."""
        v = d.get(name)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return None
        return int(v) if nd is None else round(float(v), nd)

    def stage_sec(name: str):
        return _num(stages, name)

    # RAW STAMPS, not a derived per-video duration. Measured 2026-07-20 on a real wave: a
    # 500-sentence transcript reported 1506 s and a 31-sentence one 1252 s -- a 16x difference in
    # input producing a 20% difference in "time". Every agent finished near the end of the wave,
    # so each was reporting the WAVE's length, not its own cost. Publishing that as a per-video
    # number gave the appearance of data that was not there.
    #
    # Two timestamps are facts; the duration was an inference, and the wrong one. The only
    # honest figure the wave supports is its wall clock, and that needs the LAST draft against
    # the FIRST start -- neither of which this per-video script can see. scout_report derives it
    # across the queue.
    draft_at = os.path.getmtime(draft_path)
    wave = None
    if wave_start is not None:
        if draft_at < wave_start:
            print(f"[warn] {work.root.name}: scout.draft.json predates the wave start -- carried "
                  f"over from an earlier run, excluded from the wave's wall clock")
        wave = {"start": round(wave_start, 1), "draft_at": round(draft_at, 1)}

    # PER-VIDEO summarize cost, from the sub-agent's own marker file. This is the number the
    # wave stamps above cannot give: `wave.start` is shared by every agent in the spawn, so it
    # charges an agent for however long it sat behind the concurrency cap before it ever ran.
    #
    # Still filesystem-stamped, never self-reported -- the objection that killed the first
    # attempt (a model's own claim about its runtime is unverifiable and routinely invented)
    # applies just as much to a start time as to a duration. mtime is written by the OS; the
    # agent only has to touch the file.
    #
    # KNOWN FLOOR, not a measurement error to be silently ignored: the marker lands after the
    # agent's first tool round-trip, so a real 20-minute window reads a few seconds short. It
    # errs downward, and it degrades to ABSENT (an agent that never wrote the marker) rather
    # than to a wrong number.
    summarize_sec = None
    started = work.root / "scout.started"
    try:
        started_at = os.path.getmtime(started)
    except OSError:
        started_at = None
    if started_at is not None:
        if started_at <= draft_at:
            summarize_sec = round(draft_at - started_at, 1)
        else:
            # marker newer than the draft: a re-run that touched the marker and then failed, or
            # a carried-over draft. Either way the pair does not describe one agent's work.
            print(f"[warn] {work.root.name}: scout.started is newer than scout.draft.json -- "
                  f"the pair is not one agent's run, per-video summarize time recorded as unknown")

    return {
        "video_id": work.root.name,
        "title": title,
        "duration_sec": round(dur, 1) if dur is not None else None,
        "duration_source": dur_src,
        "n_sentences": len(sents),
        "quality": quality,
        "author": author,                            # None = not assessed (see _AUTHOR)
        "one_liner": one_liner,
        "highlight": highlight,
        "paragraph": paragraph,
        "timings": {
            # *_sec = the pipeline's wall clock for the stage, model load included. What the
            # run cost. Summed by the report.
            "download_sec": stage_sec("download"),
            "transcribe_sec": stage_sec("transcribe"),
            # *_work_sec = the same stage with the model load and warmup excluded, i.e. what
            # this VIDEO cost. This is the pair to compare across builds; the wall clock above
            # cannot be, because the load lands on whichever video the sweep happened to start
            # with. NEVER summed into the report's strip -- see scout_report.totals_of.
            "transcribe_work_sec": _num(tr_detail, "work_sec"),
            # 2 means the alignment guard re-ran ASR: that video cost roughly double for a
            # reason that has nothing to do with whatever optimization is being measured.
            "transcribe_asr_passes": _num(tr_detail, "asr_passes", None),
            # per-agent, from the marker file -- see the comment above. Absent when the agent
            # wrote no marker; never inferred from the wave.
            "summarize_sec": summarize_sec,
        },
        # raw epochs, never a per-video duration -- see the comment above `wave`
        "wave": wave,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="build_scout",
        description="Assemble work/<id>/scout.json from the sub-agent's scout.draft.json.")
    p.add_argument("workdir", type=Path, metavar="work/<id>")
    p.add_argument("--wave-start", type=float, default=None, metavar="EPOCH",
                   help="unix epoch seconds when the summarizer wave was spawned; stored with "
                        "the draft's mtime so the report can derive the WAVE's wall clock "
                        "(last draft minus first start). Omit and the wave is "
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
    # per-video figures shown next to the wall clocks, and only when they exist: an older
    # workdir has no detail section and a sub-agent that wrote no marker has no summarize time
    extra = "".join(
        f" {k}={t[k]}" for k in ("transcribe_work_sec", "transcribe_asr_passes", "summarize_sec")
        if t.get(k) is not None)
    print(f"[scout] {out}  quality={doc['quality']}  "
          f"{doc['n_sentences']} sentences  "
          f"dl={t['download_sec']}s tr={t['transcribe_sec']}s{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
