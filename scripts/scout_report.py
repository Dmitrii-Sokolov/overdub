"""Render the scout report: work/scout-report.html, ready to publish as a Claude Artifact.

Reads work/<id>/scout.json (written by build_scout.py) for every id in the QUEUE and renders two
lists over the same videos:

  1. a scan table  -- verdict, title, duration, video id, one-line description
  2. read cards    -- same order, verdict, title, the full paragraph

ORDER IS THE QUEUE'S ORDER, never a sort. The queue is the playlist the user handed over, and a
report that reorders it forces them to re-map every row onto the thing they actually have open.
This is a deliberate departure from triage_html.py, which sorts needs-triage first -- that page
answers "what is broken", where surfacing the worst first IS the job; this one answers "what is
in my queue", where position is information. Verdicts are shown, never sorted on.

BODY-ONLY HTML, on purpose: the output carries an inline <style> but no doctype/html/head/body,
because the Artifact publisher wraps the file in its own skeleton. Browsers render the fragment
fine on their own, so the same file opens locally by double-click. (triage_html.py emits a full
standalone page; it is not published, so it has no reason to be a fragment.)

A queued video with NO scout.json is rendered as an explicit "не отсканировано" row, never
dropped: silently shortening the deliverable to the videos that happened to work is the exact
failure the scout mode exists to prevent.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\scout_report.py --queue queue.txt
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
import time
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub.config import Config                          # noqa: E402
from overdub.workdir import replace_retry                  # noqa: E402

# Same 11-char YouTube-id shape workdir.video_id and the other reporters use.
_YT_ID = re.compile(r"(?:v=|/shorts/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})")

# The closed verdict vocabulary of build_scout.py, mapped to presentation. Labels live HERE and
# not in scout.json on purpose: relabelling is a rendering change and must not invalidate every
# artifact on disk. `rank` orders the SUMMARY counts only -- never the lists themselves.
_VERDICT = {
    "watch": {"label": "точно смотреть", "cls": "v-watch", "rank": 0},
    "maybe": {"label": "сомнительно", "cls": "v-maybe", "rank": 1},
    "skip":  {"label": "точно не смотреть", "cls": "v-skip", "rank": 2},
}
# A queued video with no scout.json is not one state but three, told apart by which artifact is
# missing. They need different actions from the operator, and collapsing them into one row hides
# which one applies: a failed download is re-run, a failed transcribe is investigated, a missing
# summary is a sub-agent to respawn.
_NOT_DOWNLOADED = {"label": "не скачано", "cls": "v-none", "rank": 3,
                   "why": "видео не скачалось — перезапусти команду S1 (обычно это транзиентная "
                          "ошибка YouTube и со второго раза проходит)"}
_NOT_TRANSCRIBED = {"label": "не расшифровано", "cls": "v-none", "rank": 3,
                    "why": "аудио есть, транскрипта нет — transcribe для этого видео не "
                           "отработал; смотри вывод S1"}
_MISSING = {"label": "не отсканировано", "cls": "v-none", "rank": 3,
            "why": "транскрипт есть, оценки нет — суммаризатор (S2) для этого видео не "
                   "отработал; перезапусти его и пересобери отчёт"}

# The cost axis, rendered as a QUIET outline chip next to the verdict. Deliberately not colour-
# coded: the verdict owns the page's colour, and a second coloured scale would compete with it
# for the same glance. Neither value is "worse" than the other -- they are different budgets.
_ATTENTION = {
    "focus": {"label": "концентрация", "cls": "a-focus"},
    "background": {"label": "фоновое", "cls": "a-bg"},
}
# Shown ONLY for a trusted author: a marker on every row would be a column of one value while
# the profile's trusted list is empty (build_scout._AUTHOR).
_TRUSTED = {"label": "доверенный автор", "cls": "a-trust"}


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


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
    """Queue order, preserved, deduped. Same parse as run_report/triage_html (utf-8-sig strips a
    PowerShell BOM, '#' comments and blanks skipped). A line the regex misses is DROPPED here and
    counted by the caller -- this is a read-only renderer, and the skill's S1 gate is where an
    unmatched URL has to fail loud."""
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


def clock(sec) -> str:
    """H:MM:SS / M:SS. '—' for unknown -- never '0:00', which reads as a measured zero."""
    if not isinstance(sec, (int, float)) or isinstance(sec, bool) or sec < 0:
        return "—"
    t = int(round(sec))
    h, m, s = t // 3600, (t // 60) % 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def secs(sec) -> str:
    """Short duration for the timing strip. '—' for unknown, same reason as clock()."""
    if not isinstance(sec, (int, float)) or isinstance(sec, bool) or sec < 0:
        return "—"
    return f"{sec:.0f} с" if sec < 90 else f"{sec / 60:.1f} мин"


# --------------------------------------------------------------------------- style
# Tokens first, components through the tokens: the dark palette is a token redefinition, so no
# component rule is ever duplicated per theme. Both the OS preference and the viewer's explicit
# toggle ([data-theme]) must win, in both directions -- hence the three blocks.
_CSS = """
<style>
.sr{--bg:#f7f8fa;--card:#ffffff;--ink:#141a21;--dim:#5b6875;--line:#dde3ea;
  --accent:#4a5b8c;--watch:#0d7f59;--maybe:#a86a10;--skip:#b03a52;
  --watch-bg:#e7f5ef;--maybe-bg:#fbf1de;--skip-bg:#fbeaee;--none-bg:#eef1f5;
  --ui:ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;
  --read:ui-serif,Georgia,"Times New Roman",serif;
  --mono:ui-monospace,"Cascadia Code",Consolas,monospace;
  background:var(--bg);color:var(--ink);font-family:var(--ui);line-height:1.55;
  padding:clamp(20px,4vw,48px);max-width:1080px;margin:0 auto;}
@media (prefers-color-scheme:dark){.sr{--bg:#0f1419;--card:#171e26;--ink:#e6ecf2;--dim:#93a1b0;
  --line:#2a3541;--accent:#8fa3d8;--watch:#4cc79a;--maybe:#e0a84b;--skip:#e8798f;
  --watch-bg:#132a22;--maybe-bg:#2b2213;--skip-bg:#2b171d;--none-bg:#1c242d;}}
:root[data-theme="dark"] .sr{--bg:#0f1419;--card:#171e26;--ink:#e6ecf2;--dim:#93a1b0;
  --line:#2a3541;--accent:#8fa3d8;--watch:#4cc79a;--maybe:#e0a84b;--skip:#e8798f;
  --watch-bg:#132a22;--maybe-bg:#2b2213;--skip-bg:#2b171d;--none-bg:#1c242d;}
:root[data-theme="light"] .sr{--bg:#f7f8fa;--card:#ffffff;--ink:#141a21;--dim:#5b6875;
  --line:#dde3ea;--accent:#4a5b8c;--watch:#0d7f59;--maybe:#a86a10;--skip:#b03a52;
  --watch-bg:#e7f5ef;--maybe-bg:#fbf1de;--skip-bg:#fbeaee;--none-bg:#eef1f5;}

.sr h1{font-size:clamp(1.5rem,3.4vw,2.1rem);font-weight:650;letter-spacing:-.02em;
  text-wrap:balance;margin:0 0 6px;}
.sr h2{font-size:1.02rem;font-weight:640;letter-spacing:.08em;text-transform:uppercase;
  color:var(--accent);margin:0;}
.sr .sub{color:var(--dim);font-size:.92rem;margin:0;}
.sr .head{display:flex;flex-direction:column;gap:6px;margin-bottom:24px;}
.sr .sec{display:flex;flex-direction:column;gap:14px;margin-top:40px;}
.sr .sechead{display:flex;flex-direction:column;gap:3px;border-bottom:1px solid var(--line);
  padding-bottom:10px;}

/* timing strip: data, so mono + tabular figures */
.sr .times{display:flex;flex-wrap:wrap;gap:1px;background:var(--line);border:1px solid var(--line);
  border-radius:8px;overflow:hidden;margin-top:14px;}
.sr .t{flex:1 1 130px;background:var(--card);padding:10px 14px;}
.sr .t dt{color:var(--dim);font-size:.74rem;letter-spacing:.05em;text-transform:uppercase;
  margin:0 0 3px;}
.sr .t dd{margin:0;font-family:var(--mono);font-size:1.06rem;font-variant-numeric:tabular-nums;}

.sr .wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--card);}
.sr table{border-collapse:collapse;width:100%;font-size:.93rem;}
.sr th{text-align:left;font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;
  color:var(--dim);font-weight:600;padding:10px 12px;border-bottom:1px solid var(--line);
  white-space:nowrap;}
.sr td{padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:top;}
.sr tr:last-child td{border-bottom:none;}
.sr .num{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap;
  color:var(--dim);}
.sr .name{font-weight:560;}
/* queue position: mono + tabular so the column stays a ruler, dim so it never competes */
.sr .idx{font-family:var(--mono);font-variant-numeric:tabular-nums;color:var(--dim);
  white-space:nowrap;}
.sr td.idx{text-align:right;}

/* links: the title goes out to the video, the number jumps within the page */
.sr a.ext{color:inherit;text-decoration:underline;text-decoration-color:var(--line);
  text-underline-offset:3px;}
.sr a.ext:hover{text-decoration-color:var(--accent);}
.sr a.jump{color:var(--dim);text-decoration:none;font-family:var(--mono);
  font-variant-numeric:tabular-nums;}
.sr a.jump:hover{color:var(--accent);}
.sr a:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px;}
/* :target — the row/card you just jumped to, so the landing is not a guess */
.sr tr:target td{background:var(--none-bg);}
.sr .card:target{box-shadow:0 0 0 2px var(--accent);}

/* the verdict's justification, distinct from the description in both lists */
.sr td.why{color:var(--ink);}

/* the queue's source, above the counts */
.sr .src{margin:0;font-size:1.02rem;font-weight:560;}

/* verdict + cost + runtime as one stacked block, and the row's jump target */
.sr td.meta{width:1%;}
.sr .meta a.jump{display:flex;flex-direction:column;align-items:flex-start;gap:4px;}
.sr .metaline{display:block;}

/* preview: fixed box so a missing one never shifts the column */
.sr .thumb{display:block;width:160px;height:auto;border-radius:4px;margin-bottom:6px;
  background:var(--none-bg);}
.sr .cardhead .thumb{width:120px;margin:0 4px 0 0;}
@media (max-width:640px){.sr .thumb{width:120px;}}
.sr p.why{font-family:var(--ui);font-size:.92rem;color:var(--dim);margin:0 0 10px;
  padding-left:10px;border-left:2px solid var(--line);max-width:66ch;}
.sr .line{color:var(--dim);}

/* verdict chip: colour AND text, never colour alone */
.sr .chip{display:inline-block;white-space:nowrap;font-size:.76rem;font-weight:640;
  letter-spacing:.02em;padding:3px 9px;border-radius:999px;}
.sr .v-watch{background:var(--watch-bg);color:var(--watch);}
.sr .v-maybe{background:var(--maybe-bg);color:var(--maybe);}
.sr .v-skip{background:var(--skip-bg);color:var(--skip);}
.sr .v-none{background:var(--none-bg);color:var(--dim);}

/* cost axis: outline, no fill — quieter than the verdict on purpose */
.sr .tag{display:inline-block;white-space:nowrap;font-size:.72rem;font-weight:560;
  letter-spacing:.02em;padding:2px 8px;border-radius:999px;border:1px solid var(--line);
  color:var(--dim);}
.sr .a-focus{border-color:var(--accent);color:var(--accent);}
.sr .a-trust{border-style:dashed;}

/* read cards: the severity stripe encodes the same verdict the chip states */
.sr .card{background:var(--card);border:1px solid var(--line);border-radius:8px;
  border-left:3px solid var(--line);padding:16px 18px;}
.sr .card.v-watch{border-left-color:var(--watch);}
.sr .card.v-maybe{border-left-color:var(--maybe);}
.sr .card.v-skip{border-left-color:var(--skip);}
.sr .cardhead{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px;margin-bottom:8px;}
.sr .cardhead .name{font-size:1.04rem;}
.sr .card p{font-family:var(--read);font-size:1rem;line-height:1.68;margin:0;
  max-width:66ch;color:var(--ink);}
.sr .foot{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);
  color:var(--dim);font-size:.82rem;}
</style>
"""


def _row(e: dict) -> str:
    """One scan-table row. Everything that came from an LLM or a video title is escaped -- same
    rule as triage_html: raw prose into HTML is the one place a report can break itself."""
    # Verdict, cost and runtime are three short values that used to eat three columns and
    # squeeze the two prose columns that carry the actual content. Stacked into one cell they
    # read as a block and give the width back. The whole block is the jump link into the
    # write-up — a bigger, more obvious target than the bare number it replaced.
    return (
        f'<tr id="r{e["n"]}">'
        f'<td class="idx">{e["n"]}</td>'
        f'<td class="meta"><a class="jump" href="#v{e["n"]}" '
        f'title="подробнее">{_meta_block(e)}</a></td>'
        f'<td class="name">{_thumb_img(e)}{_title_link(e)}</td>'
        f'<td class="line">{html.escape(e["one_liner"])}</td>'
        f'<td class="why">{html.escape(e["reason"])}</td>'
        "</tr>"
    )


def _meta_block(e: dict) -> str:
    """Verdict / attention / runtime as three stacked lines."""
    v = e["v"]
    a = _ATTENTION.get(e.get("attention"))
    out = [f'<span class="chip {v["cls"]}">{html.escape(v["label"])}</span>']
    if a:
        out.append(f'<span class="tag {a["cls"]}">{html.escape(a["label"])}</span>')
    if e.get("author") == "trusted":
        out.append(f'<span class="tag {_TRUSTED["cls"]}">{html.escape(_TRUSTED["label"])}</span>')
    out.append(f'<span class="num">{clock(e["duration"])}</span>')
    return "".join(f"<span class=\"metaline\">{x}</span>" for x in out)


def _thumb_img(e: dict) -> str:
    """The preview, inlined as a data-URI. A remote src would be blocked outright by the
    Artifact CSP — i.e. invisible in the one place this page is meant to be read — so the bytes
    travel with the page or not at all. Absent preview renders nothing: the row still carries
    verdict, reason and a link, and an empty placeholder box would be noise."""
    b64 = e.get("thumb_b64")
    if not b64:
        return ""
    return (f'<img class="thumb" src="data:image/jpeg;base64,{b64}" alt="" '
            f'loading="lazy" width="160">')


def _title_link(e: dict) -> str:
    """Title as a link to the video. The id is the 11-char YouTube id the queue was parsed with
    (queue_ids' regex guarantees the shape), so the URL is built, never taken from the artifact —
    a url field written by an LLM would be a link the reader trusts and we never validated.
    An unscanned row still links: the whole point of that row is to go look at the thing."""
    href = f"https://www.youtube.com/watch?v={e['vid']}"
    return (f'<a class="ext" href="{html.escape(href)}" target="_blank" rel="noopener">'
            f'{html.escape(e["title"])}</a>')


def _tags(e: dict) -> str:
    """The cost axis, plus the trusted-author marker when there is one. An unscanned row has
    neither — showing a cost for a video nobody assessed would invent the one number the
    operator schedules against."""
    out = []
    a = _ATTENTION.get(e.get("attention"))
    if a:
        out.append(f'<span class="tag {a["cls"]}">{html.escape(a["label"])}</span>')
    if e.get("author") == "trusted":
        out.append(f'<span class="tag {_TRUSTED["cls"]}">{html.escape(_TRUSTED["label"])}</span>')
    return " ".join(out)


def _card(e: dict) -> str:
    v = e["v"]
    return (
        f'<article class="card {v["cls"]}" id="v{e["n"]}">'
        f'<div class="cardhead">'
        f'<a class="jump" href="#r{e["n"]}" title="назад к списку">{e["n"]}</a>'
        f'{_thumb_img(e)}'
        f'<span class="name">{_title_link(e)}</span>'
        f'<span class="chip {v["cls"]}">{html.escape(v["label"])}</span>'
        f'{_tags(e)}'
        f'<span class="num">{clock(e["duration"])}</span></div>'
        # the verdict's justification leads, before the description: the reader arrived here
        # from a chip and the first thing they owe is why that chip says what it says
        f'<p class="why">{html.escape(e["reason"])}</p>'
        f'{_paragraphs(e["paragraph"])}'
        "</article>"
    )


def _paragraphs(text: str) -> str:
    """Blank-line-separated blocks → separate <p>. The SPLIT IS THE SUMMARIZER'S: it is the only
    party that knows where the meaning turns, and a renderer chopping every N sentences would
    cut mid-thought. A single-block paragraph still renders — as one <p>, exactly as before —
    so an older scout.json is never mangled to force a shape onto it."""
    parts = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    return "".join(f"<p>{html.escape(p)}</p>" for p in parts or [text])


def render(entries: list[dict], totals: dict, queue_name: str, stamp: str,
           playlist: dict | None = None) -> str:
    counts = {k: sum(1 for e in entries if e["v"] is _VERDICT[k]) for k in _VERDICT}
    tally = " · ".join(f'{_VERDICT[k]["label"]}: {counts[k]}' for k in _VERDICT)
    # each unfinished state counted under its OWN name: "не отсканировано: 3" hiding a failed
    # download would send the operator to respawn a summarizer that has nothing to read
    for state in (_NOT_DOWNLOADED, _NOT_TRANSCRIBED, _MISSING):
        n = sum(1 for e in entries if e["v"] is state)
        if n:
            tally += f' · {state["label"]}: {n}'

    t = totals
    out = [_CSS, '<div class="sr">']
    out.append('<header class="head">')
    out.append("<h1>Разведка очереди</h1>")
    if playlist:
        # the source the queue came from, named at the top: without it the report is a list of
        # videos with no answer to "which playlist was this again"
        name = html.escape(playlist["title"])
        src = (f'<a class="ext" href="{html.escape(playlist["url"])}" target="_blank" '
               f'rel="noopener">{name}</a>' if playlist.get("url") else name)
        out.append(f'<p class="src">{src}</p>')
    out.append(f'<p class="sub">{len(entries)} видео из <code>{html.escape(queue_name)}</code> · '
               f'{html.escape(stamp)}</p>')
    out.append(f'<p class="sub">{html.escape(tally)}</p>')
    out.append('<dl class="times">')
    # The queue's own runtime leads: it is what the reader budgets against. The pipeline columns
    # after it are what the machine spent, which is a different question and a smaller number.
    content = clock(t["content"]) + ("+" if t["content_missing"] else "")
    # pipeline stages in the order they ran, their total, then the queue's own runtime last —
    # it is a different KIND of number (what there is to watch, not what the machine spent),
    # so it sits after the sum rather than inside the run of things that add up
    for label, val in (("скачивание", secs(t["download"])),
                       ("транскрибация", secs(t["transcribe"])),
                       ("суммаризация", secs(t["summarize"])),
                       ("итого обработка", secs(t["total"])),
                       ("хронометраж очереди", content)):
        out.append(f'<div class="t"><dt>{label}</dt><dd>{val}</dd></div>')
    out.append("</dl>")
    # The one thing a timing strip must never do is imply the columns add up. They do not: the
    # summarizers run in parallel, so their column is a WALL clock while the pipeline stages are
    # sums -- stated here rather than left for the reader to discover as an arithmetic bug.
    out.append('<p class="sub" style="margin-top:8px">Суммаризация шла параллельно — это '
               'wall-clock всей волны, а не сумма по видео; поэтому колонки не складываются '
               'в «итого» арифметически.</p>')
    out.append("</header>")

    out.append('<section class="sec"><div class="sechead"><h2>Список</h2>'
               '<p class="sub">В порядке очереди — так же, как в плейлисте.</p></div>')
    out.append('<div class="wrap"><table><thead><tr>'
               # the number column keeps its width but loses its label: "№" over a column of
               # numbers says nothing the numbers do not
               "<th></th><th></th><th>Название</th><th>О чём</th><th>Почему</th>"
               "</tr></thead><tbody>")
    out.extend(_row(e) for e in entries)
    out.append("</tbody></table></div></section>")

    out.append('<section class="sec"><div class="sechead"><h2>Подробно</h2>'
               '<p class="sub">Тот же порядок, абзац на видео.</p></div>')
    out.extend(_card(e) for e in entries)
    out.append("</section>")

    out.append('<p class="foot">overdub · scout · вердикты выставлены по '
               '<code>.claude/viewer-profile.md</code>; они рекомендация, а не решение.</p>')
    out.append("</div>")
    return "\n".join(out)


def _thumb_b64(path: Path) -> str | None:
    """thumb.jpg → base64, or None when absent/unreadable. Never raises: the preview is the one
    thing on this page that nothing depends on."""
    try:
        return base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return None


def collect(ids: list[str], work_root: Path) -> list[dict]:
    """Queue order in, render-ready entries out. A missing/unreadable scout.json becomes a
    MISSING entry rather than a gap, so the report's row count always equals the queue's."""
    entries = []
    # 1-based position in the QUEUE, assigned before any state branch: the number is the reader's
    # index into the playlist they have open, so it must survive a video that failed to download
    # — a report that renumbers around gaps stops matching the thing it is read against.
    for n, vid in enumerate(ids, 1):
        doc = _load_json(work_root / vid / "scout.json")
        if not isinstance(doc, dict) or doc.get("verdict") not in _VERDICT:
            d = work_root / vid
            # Strongest evidence first: a transcript proves the download happened, whatever the
            # media looks like now (a promotion rewrites source.wav; a cleanup can delete it).
            # Probing source.wav first would report a scouted video as "not downloaded" and send
            # the operator to re-fetch something that is already transcribed.
            if (d / "sentences.json").exists():
                state = _MISSING
            elif (d / "source.wav").exists():
                state = _NOT_TRANSCRIBED
            else:
                state = _NOT_DOWNLOADED
            # A title may still exist even when nothing else does: the info.json sidecar lands
            # before the media on a partial fetch, and _title_of backfills one. Showing it beats
            # showing a bare id for a row whose whole job is to be actioned.
            info = _load_json(d / "source.info.json")
            title = info.get("title") if isinstance(info, dict) else None
            entries.append({
                "n": n, "vid": vid, "v": state, "title": title or vid, "duration": None,
                "one_liner": "—", "reason": state["why"], "paragraph": state["why"],
                "timings": {},
            })
            continue
        entries.append({
            "n": n,
            "vid": doc.get("video_id") or vid,
            "v": _VERDICT[doc["verdict"]],
            # tolerated as absent: a scout.json written before the cost axis existed still
            # renders, it just carries no tag (build_scout requires the field going forward)
            "attention": doc.get("attention"),
            "author": doc.get("author"),
            "thumb_b64": _thumb_b64(work_root / vid / "thumb.jpg"),
            "title": doc.get("title") or vid,
            "duration": doc.get("duration_sec"),
            "one_liner": doc.get("one_liner") or "",
            # tolerated as absent so a scout.json written before this field existed still
            # renders; build_scout requires it going forward
            "reason": doc.get("reason") or "—",
            "paragraph": doc.get("paragraph") or "",
            "timings": doc.get("timings") if isinstance(doc.get("timings"), dict) else {},
        })
    return entries


def totals_of(entries: list[dict]) -> dict:
    """Pipeline stages are SUMS (they ran one after another); summarization is a MAX, because the
    sub-agents ran concurrently and the wave's wall clock is the largest time-until-done, not the
    sum of them. `total` adds those two different kinds together deliberately — it is the honest
    approximation of the pass's wall clock, and the page says so in words."""
    def col(key, fn):
        vals = [e["timings"].get(key) for e in entries]
        vals = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        return fn(vals) if vals else None

    dl, tr = col("download_sec", sum), col("transcribe_sec", sum)
    sm = col("summarize_sec", max)
    total = sum(v for v in (dl, tr, sm) if isinstance(v, (int, float)))
    # Total runtime of the QUEUE itself — the number the operator budgets against ("do I have
    # 9 hours of watching here or 90 minutes"). Missing durations are skipped, not zeroed, and
    # the count of skipped rows travels with it so the figure can be read as a floor rather than
    # a measurement when part of the queue never scanned.
    durs = [e["duration"] for e in entries
            if isinstance(e.get("duration"), (int, float)) and not isinstance(e["duration"], bool)]
    return {"download": dl, "transcribe": tr, "summarize": sm, "total": total,
            "content": sum(durs) if durs else None,
            "content_missing": len(entries) - len(durs)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="scout_report",
        description="Render the scout report (two lists, queue order) as publishable HTML.")
    p.add_argument("--queue", type=Path, required=True,
                   help="queue file — ALSO the report's row order")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"))
    p.add_argument("--out", type=Path, default=None,
                   help="output path (default: <work_root>/scout-report.html)")
    args = p.parse_args(argv)
    if not args.queue.is_file():
        p.error(f"queue file not found: {args.queue}")

    cfg = Config.load(args.config)
    ids = queue_ids(args.queue)
    if not ids:
        p.error(f"queue file has no recognizable video ids: {args.queue}")

    entries = collect(ids, cfg.work_root)
    out_path = args.out or (cfg.work_root / "scout-report.html")
    stamp = time.strftime("%Y-%m-%d %H:%M")
    page = render(entries, totals_of(entries), args.queue.name, stamp,
                  queue_playlist(args.queue))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(page, encoding="utf-8")
    replace_retry(tmp, out_path)

    # Each unfinished state named on stdout too, with the action it needs — the operator reads
    # this line before opening the page, and "3 incomplete" would not say which of the three
    # different fixes applies.
    unfinished = [(s, sum(1 for e in entries if e["v"] is s))
                  for s in (_NOT_DOWNLOADED, _NOT_TRANSCRIBED, _MISSING)]
    unfinished = [(s, n) for s, n in unfinished if n]
    note = "".join(f', {n} {s["label"]}' for s, n in unfinished)
    print(f"[scout-report] {out_path}  ({len(entries)} video(s){note})")
    for s, n in unfinished:
        print(f'[scout-report] {n} × "{s["label"]}" — {s["why"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
