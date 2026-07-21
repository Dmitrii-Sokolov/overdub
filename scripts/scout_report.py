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
    "high":   {"label": "высокое", "cls": "v-watch", "rank": 0},
    "medium": {"label": "среднее", "cls": "v-maybe", "rank": 1},
    "low":    {"label": "слабое", "cls": "v-skip", "rank": 2},
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

# The cost axis USED to live here as focus/background. Dropped 2026-07-20: on the first real
# queue 28 of 30 videos took the same value, and a field that never varies is a column that
# trains the reader to ignore it. "Требует концентрации" is now a clause the summarizer writes
# into the highlight, so it appears only when it is true.
#
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
  padding:clamp(20px,4vw,48px);max-width:1240px;margin:0 auto;}
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
/* :target — the card you just jumped to, so the landing is not a guess. The row had the same
   treatment until the card's back-link went away; with nothing linking to a row, it was a rule
   that could never fire. */
.sr .card:target{box-shadow:0 0 0 2px var(--accent);}

/* the verdict's justification, distinct from the description in both lists */
.sr td.why{color:var(--ink);}

/* the queue's source, above the counts */
.sr .src{margin:0;font-size:1.02rem;font-weight:560;}

/* The grade USED to also stripe the whole row. Dropped 2026-07-20: with a chip already naming
   it in words, the stripe was a second encoding of one fact, and it tinted the row so the eye
   read "this row is different" before reading what the row said. The chip is the marker now. */
.sr td.pic{width:1%;padding-right:0;}
/* runtime is its own column, right after the title: it is the number the reader budgets
   against, and buried at the end of a prose cell it was found only by hunting */
.sr td.dur{white-space:nowrap;}
/* the grade opens the highlight cell — the chip and the reason it earned read as one thought */
.sr td.why .chip{margin-right:8px;}
/* the description carries the jump, so it must read as text, not as a link */
.sr td.line a.jump{color:inherit;font-family:inherit;}
.sr td.line a.jump:hover{color:var(--accent);}

/* preview: fixed box so a missing one never shifts the column.

   160 here matches build_scout._THUMB_W exactly, and the guard in the tests is a CEILING, not
   an equality: rendering NARROWER than the file on disk stays legal (the card does it, at 84),
   rendering WIDER is what makes the column go soft. Raise this number and you must raise
   _THUMB_W with it — and re-fetch every preview already on disk, since _ensure_thumb skips a
   thumb.jpg that exists and will happily keep serving the old, now-too-small file.

   THE TRAP THIS BOX USED TO FALL INTO, kept written down because the element type is the only
   thing that defuses it: the Artifact skeleton wraps this fragment in its own reset, which
   carries `img{max-width:100%}`. Inside an auto-layout table that drops a preview's min-content
   contribution to ~0, so `td.pic{width:1%}` — which asks for the narrowest column that still
   fits the picture — squeezed it down to a sliver. Invisible locally (the fragment has no
   reset), wrong once published, which is the only place this page is read. A div is out of that
   selector's reach; make the preview an image element again and `max-width:none` becomes
   load-bearing again. The test enforces exactly that conditional, not the property.
   (Spelled out rather than written as a tag: this comment ships inside the page, and a literal
   one here would read as markup to every substring check in the tests.)

   The size comes from CSS in both lists (160 in the table, 84 in the card) off one element type,
   and the per-video rule supplies aspect-ratio — see _thumb_css_of for why it must. */
.sr .thumb{display:block;width:160px;border-radius:4px;aspect-ratio:16/9;
  background:var(--none-bg) center/cover no-repeat;}
.sr .cardhead .thumb{width:84px;margin:0;border-radius:3px;}
@media (max-width:640px){.sr .thumb{width:100px;}}
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

/* read cards: the severity stripe encodes the same verdict the chip states.
   The BOX is capped, not just the text inside it. The page widened to 1240px for the table's six
   columns; a card stretched to that width around a 66ch paragraph is mostly empty right-hand
   side, which reads as a rendering fault rather than as a measure. 62rem ≈ the padding plus that
   measure, so the border sits just past where the prose actually ends. */
.sr .card{background:var(--card);border:1px solid var(--line);border-radius:8px;
  border-left:3px solid var(--line);padding:16px 18px;max-width:62rem;}
.sr .card.v-watch{border-left-color:var(--watch);}
.sr .card.v-maybe{border-left-color:var(--maybe);}
.sr .card.v-skip{border-left-color:var(--skip);}
/* the card's header line: bigger type against a smaller preview, so number, title and runtime
   carry the row rather than the thumbnail dwarfing all three */
.sr .cardhead{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:10px;}
.sr .cardhead .idx{font-size:1.15rem;}
.sr .cardhead .name{font-size:1.3rem;font-weight:600;}
.sr .cardhead .num{font-size:1.05rem;}
/* the page widened for the table's six columns, so the prose caps its OWN measure: a 1240px
   line is unreadable, and the card is the one place on this page meant to be read, not scanned */
.sr .card p{font-family:var(--read);font-size:1rem;line-height:1.68;margin:0;
  max-width:66ch;color:var(--ink);}
/* the summarizer splits by meaning; without a visible gap that split does nothing for the
   reader, which is what it looked like on the first real report */
.sr .card p + p{margin-top:1.1em;}
.sr .foot{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);
  color:var(--dim);font-size:.82rem;}
</style>
"""


def _row(e: dict) -> str:
    """One scan-table row. Everything that came from an LLM or a video title is escaped -- same
    rule as triage_html: raw prose into HTML is the one place a report can break itself."""
    # The grade is a CHIP opening the highlight cell, not a column of its own and no longer a
    # tint on the row: it is one short word, and giving it a column cost width the prose columns
    # needed. It leads the highlight because the grade and the reason it earned are one thought —
    # under the title it sat between the title and the description and split them.
    v = e["v"]
    trusted = ('<span class="tag a-trust">' + html.escape(_TRUSTED["label"]) + "</span>"
               if e.get("author") == "trusted" else "")
    return (
        f'<tr id="r{e["n"]}">'
        f'<td class="idx">{e["n"]}</td>'
        f'<td class="pic">{_thumb_box(e)}</td>'
        f'<td class="name">{_title_link(e)}{trusted}</td>'
        # runtime next to the title, not at the end of a prose cell: it is scanned down the
        # column ("what fits in an evening"), which a value buried in text cannot be
        f'<td class="num dur">{clock(e["duration"])}</td>'
        # the jump lives on the description — the cell the reader is already looking at when
        # they decide they want more, and a wider target than the number it replaced
        f'<td class="line"><a class="jump" href="#v{e["n"]}" title="подробнее">'
        f'{html.escape(e["one_liner"])}</a></td>'
        f'<td class="why"><span class="chip {v["cls"]}">{html.escape(v["label"])}</span>'
        f'{html.escape(e["highlight"])}</td>'
        "</tr>"
    )


# base64's whole alphabet, and nothing that could close a CSS url() or open a comment. The bytes
# are ours (base64 of a file we wrote), so this is belt-and-braces rather than a live threat --
# but a data URI goes into a <style> block now, where a stray ')' would end the rule and leave
# the rest of the page as garbage CSS instead of a missing picture.
_B64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


def _thumb_box(e: dict) -> str:
    """The preview ELEMENT — a div painted by a per-video CSS rule, not an <img>.

    Why not <img>: the preview appears twice per video (scan row and card), and a data-URI in a
    src is the bytes themselves, not a reference to them. HTML has no way to say "the same image
    as that one", so two <img> tags meant two copies of every preview in the file — measured at
    78% of a 226 KB report. A CSS rule is declared once and applies to as many elements as carry
    the class, so the bytes land in the page exactly once.

    The cost, accepted deliberately: loading="lazy" is an <img> attribute and has no background
    equivalent, so every preview now decodes at load instead of on scroll.

    Absent preview renders nothing: the row still carries verdict, reason and a link, and an
    empty placeholder box would be noise."""
    if not _thumb_css_of(e):
        return ""
    # the position, not the video id: an id may start with a digit or '-', neither of which is a
    # valid CSS identifier start, and escaping them is a rule nobody would remember to keep
    return f'<div class="thumb t{e["n"]}"></div>'


def _thumb_css_of(e: dict) -> str:
    """The per-video rule, or "" when there is no usable preview.

    aspect-ratio is NOT optional here and not decoration: a background image never contributes
    to the size of its box, so without it the div is zero pixels tall and the preview is simply
    invisible. <img> needed none of this -- it reads its own dimensions out of the file -- which
    is exactly the convenience given up in exchange for inlining the bytes once."""
    b64 = e.get("thumb_b64")
    if not b64 or not _B64.match(b64):
        return ""
    wh = e.get("thumb_wh")
    # 16/9 is the fallback, not the assumption: ffmpeg scales to _THUMB_W with a derived height,
    # so the ratio follows the SOURCE. Guessing wrong crops the preview (background-size:cover),
    # which is why the real numbers are parsed out of the file and this line is the last resort.
    w, h = wh if wh else (16, 9)
    return (f'.sr .t{e["n"]}{{aspect-ratio:{w}/{h};'
            f'background-image:url(data:image/jpeg;base64,{b64});}}')


def _thumb_css(entries: list[dict]) -> str:
    """All per-video rules as one <style> block, or "" when no entry has a preview."""
    rules = [css for css in (_thumb_css_of(e) for e in entries) if css]
    return f"<style>{''.join(rules)}</style>" if rules else ""


def _title_link(e: dict) -> str:
    """Title as a link to the video. The id is the 11-char YouTube id the queue was parsed with
    (queue_ids' regex guarantees the shape), so the URL is built, never taken from the artifact —
    a url field written by an LLM would be a link the reader trusts and we never validated.
    An unscanned row still links: the whole point of that row is to go look at the thing."""
    href = f"https://www.youtube.com/watch?v={e['vid']}"
    return (f'<a class="ext" href="{html.escape(href)}" target="_blank" rel="noopener">'
            f'{html.escape(e["title"])}</a>')



def _card(e: dict) -> str:
    v = e["v"]
    return (
        f'<article class="card {v["cls"]}" id="v{e["n"]}">'
        f'<div class="cardhead">'
        # the number is a LABEL here, not a link: the reader arrived from the table and their
        # own back gesture already returns them, so a jump back was a link that never earned
        # its underline and one more thing competing with the title
        f'<span class="idx">{e["n"]}</span>'
        f'{_thumb_box(e)}'
        f'<span class="name">{_title_link(e)}</span>'
        f'<span class="chip {v["cls"]}">{html.escape(v["label"])}</span>'
        # same markers the table row carries: two lists that show different signals for one
        # video make the reader wonder which of them is out of date
        + ('<span class="tag a-trust">' + html.escape(_TRUSTED["label"]) + "</span>"
           if e.get("author") == "trusted" else "") +
        f'<span class="num">{clock(e["duration"])}</span></div>'
        # what the video actually offers leads, before the description: it is the reason the
        # reader followed the link here
        f'<p class="why">{html.escape(e["highlight"])}</p>'
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
    # the per-video preview rules ride right behind the static sheet: they are generated CSS, and
    # separating them keeps _CSS a constant the tests can assert against
    out = [_CSS, _thumb_css(entries), '<div class="sr">']
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
                       ("суммаризация, волна", secs(t["summarize"])),
                       ("хронометраж очереди", content)):
        out.append(f'<div class="t"><dt>{label}</dt><dd>{val}</dd></div>')
    out.append("</dl>")
    # No grand total any more, so the note no longer has to excuse one: it just says what the
    # third figure IS, since a wall clock beside two sums is the one thing a reader would
    # otherwise mis-add.
    out.append('<p class="sub" style="margin-top:8px">Первые две колонки — суммарная работа по '
               'видео. Суммаризация шла параллельно, поэтому там wall-clock всей волны: '
               'складывать их между собой нельзя.</p>')
    out.append("</header>")

    out.append('<section class="sec"><div class="sechead"><h2>Список</h2>'
               '<p class="sub">В порядке очереди — так же, как в плейлисте.</p></div>')
    out.append('<div class="wrap"><table><thead><tr>'
               # the number and preview columns carry no label: "№" over a column of numbers,
               # and a word over a column of images, say nothing the contents do not
               "<th></th><th></th><th>Название</th><th>Время</th><th>О чём</th>"
               "<th>Самое интересное</th>"
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


def jpeg_size(path: Path) -> tuple[int, int] | None:
    """(width, height) out of a JPEG's frame header, or None for anything unreadable.

    Exists because the preview is painted as a CSS background so one copy of the bytes can serve
    both lists, and a background never sizes its own box — the div needs an explicit aspect-ratio
    or it renders zero pixels tall. <img> read these numbers itself; this is the price of the
    single copy.

    A PARSE, not an assumption: _ensure_thumb scales to _THUMB_W with a derived height, so the
    ratio is the SOURCE's. 16:9 covers nearly every YouTube preview and is the caller's fallback,
    but a 4:3 frame guessed as 16:9 gets cropped, and cropping the one picture in a row is worse
    than a few lines of header walking.

    Never raises — same contract as everything else on the preview path."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data.startswith(b"\xff\xd8"):
        return None
    i, n = 2, len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0xFF:                                  # fill byte, skip one and re-read
            i += 1
            continue
        if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:      # standalone, no length
            i += 2
            continue
        seg = int.from_bytes(data[i + 2:i + 4], "big")
        if seg < 2:                                         # malformed: a length must cover itself
            return None
        # SOF0..SOF15 carry the frame header. C4/C8/CC share the range and are NOT frame headers
        # (Huffman table, JPEG extension, arithmetic coding conditioning) — reading dimensions out
        # of one of those yields two plausible-looking numbers that are not the image's size.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            return (w, h) if w and h else None
        i += 2 + seg
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
        if not isinstance(doc, dict) or doc.get("quality") not in _VERDICT:
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
                "one_liner": "—", "highlight": state["why"], "paragraph": state["why"],
                "timings": {},
            })
            continue
        entries.append({
            "n": n,
            "vid": doc.get("video_id") or vid,
            "v": _VERDICT[doc["quality"]],
            # tolerated as absent: a scout.json written before the cost axis existed still
            # renders, it just carries no tag (build_scout requires the field going forward)
            "author": doc.get("author"),
            "thumb_b64": _thumb_b64(work_root / vid / "thumb.jpg"),
            "thumb_wh": jpeg_size(work_root / vid / "thumb.jpg"),
            "title": doc.get("title") or vid,
            "duration": doc.get("duration_sec"),
            "one_liner": doc.get("one_liner") or "",
            # tolerated as absent so a scout.json written before this field existed still
            # renders; build_scout requires it going forward
            "highlight": doc.get("highlight") or "—",
            "paragraph": doc.get("paragraph") or "",
            "timings": doc.get("timings") if isinstance(doc.get("timings"), dict) else {},
            "wave": doc.get("wave") if isinstance(doc.get("wave"), dict) else None,
        })
    return entries


def totals_of(entries: list[dict]) -> dict:
    """Pipeline stages are SUMS — they ran one after another, so their sum is the work done.
    Summarization is a WALL CLOCK, derived across the whole queue as `last draft − first wave
    start`, because the sub-agents ran concurrently and no per-video figure survives contact
    with that (2026-07-20: 500 sentences → 1506 s, 31 sentences → 1252 s, i.e. every agent was
    reporting the wave, not itself).

    THERE IS DELIBERATELY NO GRAND TOTAL. The previous version added the two sums to the wall
    clock and called it "итого обработка"; that number is neither the work done nor the elapsed
    time, and a footnote saying the columns do not add up does not rescue a number that should
    not have been added. Anything wanting a true wall clock needs the pass stamped end to end,
    which nothing does today."""
    def col(key, fn):
        vals = [e["timings"].get(key) for e in entries]
        vals = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        return fn(vals) if vals else None

    dl, tr = col("download_sec", sum), col("transcribe_sec", sum)
    # carry-overs (draft older than the start) are excluded: they were not part of this wave,
    # and a stale draft would stretch the window to whenever it happened to be written
    waves = [w for w in (e.get("wave") for e in entries)
             if isinstance(w, dict)
             and isinstance(w.get("start"), (int, float))
             and isinstance(w.get("draft_at"), (int, float))
             and w["draft_at"] >= w["start"]]
    # GROUPED BY START, one window per wave, windows summed. A queue is routinely summarized in
    # SEVERAL waves -- the skill's resume filter re-runs build_scout only for the videos that
    # need a new summary, so the ones carried forward keep the OLD wave's start forever. Taking
    # `max(draft) - min(start)` across the whole queue then spans every wave AND the idle time
    # between them: two 20-minute waves five hours apart reported five and a half hours of
    # "summarization". That is the same mistake the per-video duration was (2026-07-20) -- a
    # wall clock presented as work -- one level up, so it is fixed the same way: measure only
    # what was actually running, never the gaps.
    last: dict[float, float] = {}
    for w in waves:
        last[w["start"]] = max(last.get(w["start"], w["start"]), w["draft_at"])
    sm = sum(end - start for start, end in last.items()) if last else None
    # Total runtime of the QUEUE itself — the number the operator budgets against ("do I have
    # 9 hours of watching here or 90 minutes"). Missing durations are skipped, not zeroed, and
    # the count of skipped rows travels with it so the figure can be read as a floor rather than
    # a measurement when part of the queue never scanned.
    durs = [e["duration"] for e in entries
            if isinstance(e.get("duration"), (int, float)) and not isinstance(e["duration"], bool)]
    return {"download": dl, "transcribe": tr, "summarize": sm,
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
