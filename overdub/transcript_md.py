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


def body_lines(paras: list[dict]) -> list[str]:
    """Paragraphs -> markdown lines with periodic timecodes and, when several people talk, a
    `**Speaker N** [t]` line wherever the speaker changes. Labels are diarization ids, not names."""
    labelled = len({p.get("speaker") for p in paras}) > 1
    lines: list[str] = []
    last = None
    last_speaker = None
    for p in paras:
        sp = p.get("speaker")
        if labelled and sp != last_speaker:
            lines += [f"**Speaker {sp}** {stamp(p['start'])}", ""]
            last, last_speaker = p["start"], sp
        elif last is None or p["start"] - last >= STAMP_EVERY:
            lines += [f"**{stamp(p['start'])}**", ""]
            last = p["start"]
        lines += [p["text"], ""]
    return lines


def render_transcript(sentences: list[dict], *, title: str, duration: float | None,
                      description: str | None = None) -> str:
    """sentences.json -> the `--transcribe-only` deliverable. Pure: no I/O.

    `description` is the uploader's text verbatim: it usually carries chapter timecodes and the
    list of speakers, which the diarizer cannot name. It is placed before the body, under its own
    heading, so a reader can tell the uploader's words from the transcript.
    """
    n_speakers = len({s.get("speaker") for s in sentences if s.get("speaker") is not None})
    meta = [stamp(duration).strip("[]")] if duration else []
    if n_speakers > 1:
        meta.append(f"{n_speakers} speakers")
    head = [f"# {title}", "", " · ".join(meta), ""] if meta else [f"# {title}", ""]
    desc = (description or "").replace("\r\n", "\n").strip()
    if desc:
        head += ["## Description", "", desc, "", "## Transcript", ""]
    if not sentences:
        return "\n".join(head + ["_No speech detected._", ""])
    return "\n".join(head + body_lines(paragraphs(sentences)))


def write_transcript(work: WorkDir, sentences: list[dict], *, title: str | None,
                     duration: float | None, description: str | None = None) -> Path:
    """tmp + replace: a torn write would leave a half-transcript that still looks like a file."""
    tmp = work.transcript_md.with_suffix(".md.tmp")
    tmp.write_text(render_transcript(sentences, title=title or work.root.name, duration=duration,
                                     description=description),
                   encoding="utf-8")
    replace_retry(tmp, work.transcript_md)
    return work.transcript_md
