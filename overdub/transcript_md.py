"""Sentences → readable transcript: paragraphs broken on pauses and speaker changes.

Shared by route E (scripts/build_clean.py, which feeds it agent-cleaned lines) and by
`--transcribe-only` (which feeds it the raw sentences.json). Both want the same thing from the
audio — where a paragraph ends — and that is a property of the timestamps, so it is decided here
once instead of by whoever happens to render.
"""

from __future__ import annotations

from pathlib import Path

from .workdir import WorkDir, replace_retry

# Pause that ends a paragraph, in seconds. A HYPOTHESIS sited on ordinary speech rhythm, not a
# measured constant: a breath inside a thought runs ~0.3-0.6 s, while a topic change is usually
# longer. Re-site it once a wave of real transcripts exists.
PARA_GAP = 1.0
# A paragraph this long is broken at the next sentence regardless of pauses -- a speaker who never
# pauses would otherwise produce one unreadable block per chunk.
PARA_MAX_CHARS = 900
# Seconds between timecodes. They are navigation, so one per paragraph would be noise and one per
# chapter would be useless.
STAMP_EVERY = 120.0


def stamp(sec: float) -> str:
    """Seconds -> [M:SS] or [H:MM:SS] past the hour."""
    s = int(sec)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"[{h}:{m:02d}:{s:02d}]" if h else f"[{m}:{s:02d}]"


def _gap(prev: dict, cur: dict) -> float:
    try:
        return max(float(cur["start"]) - float(prev["end"]), 0.0)
    except (KeyError, TypeError, ValueError):
        return 0.0


def paragraphs(records: list[dict]) -> list[dict]:
    """Group the non-empty lines into {start, text[, speaker]} paragraphs.

    The ONLY structural decision made here, and it is made on the audio rather than by an agent
    on purpose: a paragraph break is knowable from the timestamps and does not need judgement.
    Leaving it to agents would also make the breaks disagree across a chunk boundary, where
    neither agent can see the other's text.

    A change of speaker always breaks. `speaker` is carried onto the paragraph only when the
    records have one, so a single-speaker transcript keeps its old shape.
    """
    out: list[dict] = []
    cur: list[str] = []
    cur_start = 0.0
    cur_speaker = None
    prev: dict | None = None

    def flush() -> None:
        para = {"start": cur_start, "text": " ".join(cur)}
        if cur_speaker is not None:
            para["speaker"] = cur_speaker
        out.append(para)

    for r in records:
        if not r["text"]:
            continue                                     # emptied line: dropped here, kept in clean.json
        brk = prev is not None and (
            _gap(prev, r) >= PARA_GAP
            or r.get("speaker") != prev.get("speaker")
            or sum(len(t) + 1 for t in cur) >= PARA_MAX_CHARS)
        if brk and cur:
            flush()
            cur = []
        if not cur:
            cur_start = float(r["start"])
            cur_speaker = r.get("speaker")
        cur.append(r["text"])
        prev = r
    if cur:
        flush()
    return out


def body_lines(paras: list[dict], chapters: list[tuple[float, str]] | None = None) -> list[str]:
    """Paragraphs -> markdown lines with periodic timecodes and, when several people talk, a
    `**Speaker N** [t]` line wherever the speaker changes. Labels are diarization ids, not names.

    `chapters` are (start, title) pairs in time order; each opens a `### title [t]` heading before
    the first paragraph at or after its start. The heading carries the timecode and, when speakers
    are labelled, the label is repeated after it so a chapter never starts with an unattributed
    paragraph. A chapter with no paragraph at or after its start (the tail of a video that ends in
    silence) is dropped rather than left as a heading over nothing."""
    labelled = len({p.get("speaker") for p in paras}) > 1
    lines: list[str] = []
    last = None
    last_speaker = None
    pending = list(chapters or [])
    for p in paras:
        sp = p.get("speaker")
        while pending and pending[0][0] <= p["start"]:
            start, name = pending.pop(0)
            if pending and pending[0][0] <= p["start"]:
                continue                                  # several chapters before one paragraph: last wins
            lines += [f"### {name} {stamp(start)}", ""]
            last, last_speaker = p["start"], None
        if labelled and sp != last_speaker:
            lines += [f"**Speaker {sp}** {stamp(p['start'])}", ""]
            last, last_speaker = p["start"], sp
        elif last is None or p["start"] - last >= STAMP_EVERY:
            lines += [f"**{stamp(p['start'])}**", ""]
            last = p["start"]
        lines += [p["text"], ""]
    return lines


def _count(info: dict, key: str) -> int | None:
    v = info.get(key)
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def _compact(n: int) -> str:
    """1_234 -> 1.2K, 2_120_661 -> 2.1M. One decimal, none under a thousand."""
    for div, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= div:
            return f"{n / div:.1f}".rstrip("0").rstrip(".") + suffix
    return str(n)


def _facts(info: dict) -> str:
    """The channel / date / popularity line. Every field is optional: a missing or mistyped one is
    left out rather than printed as `None` or `0`, since the sidecar may come from an old backfill."""
    parts: list[str] = []
    channel = info.get("channel")
    if isinstance(channel, str) and channel:
        followers = _count(info, "channel_follower_count")
        parts.append(f"{channel} ({_compact(followers)} subscribers)" if followers is not None
                     else channel)
    date = info.get("upload_date")
    if isinstance(date, str) and len(date) == 8 and date.isdigit():
        parts.append(f"{date[:4]}-{date[4:6]}-{date[6:]}")
    for key, noun in (("view_count", "views"), ("like_count", "likes")):
        n = _count(info, key)
        if n is not None:
            parts.append(f"{_compact(n)} {noun}")
    return " · ".join(parts)


def _chapters(info: dict) -> list[tuple[float, str]]:
    raw = info.get("chapters")
    out = [(float(c["start_time"]), c["title"].strip()) for c in raw
           if isinstance(c, dict) and isinstance(c.get("title"), str) and c["title"].strip()
           and isinstance(c.get("start_time"), (int, float)) and not isinstance(c["start_time"], bool)
           ] if isinstance(raw, list) else []
    return sorted(out, key=lambda c: c[0])


def render_transcript(sentences: list[dict], *, title: str, duration: float | None,
                      info: dict | None = None) -> str:
    """sentences.json -> the `--transcribe-only` deliverable. Pure: no I/O.

    `info` is the yt-dlp sidecar. From it come the channel / date / popularity line, the chapters
    (as headings inside the body) and the uploader's description, verbatim: it usually carries the
    speaker list, which the diarizer cannot name. The description sits before the body under its
    own heading, so a reader can tell the uploader's words from the transcript.
    """
    info = info if isinstance(info, dict) else {}
    n_speakers = len({s.get("speaker") for s in sentences if s.get("speaker") is not None})
    meta = [f"Duration: {stamp(duration).strip('[]')}"] if duration else []
    if n_speakers > 1:
        meta.append(f"{n_speakers} speakers")
    head = [f"# {title}", ""]
    for line in (" · ".join(meta), _facts(info)):
        if line:
            head += [line, ""]
    desc = (info.get("description") if isinstance(info.get("description"), str) else "")
    desc = desc.replace("\r\n", "\n").strip()
    if desc:
        head += ["## Description", "", desc, "", "## Transcript", ""]
    if not sentences:
        return "\n".join(head + ["_No speech detected._", ""])
    return "\n".join(head + body_lines(paragraphs(sentences), _chapters(info)))


def write_transcript(work: WorkDir, sentences: list[dict], *, title: str | None,
                     duration: float | None, info: dict | None = None) -> Path:
    """tmp + replace: a torn write would leave a half-transcript that still looks like a file."""
    tmp = work.transcript_md.with_suffix(".md.tmp")
    tmp.write_text(render_transcript(sentences, title=title or work.root.name, duration=duration,
                                     info=info),
                   encoding="utf-8")
    replace_retry(tmp, work.transcript_md)
    return work.transcript_md
