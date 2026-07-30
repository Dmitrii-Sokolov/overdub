"""Render the digest page: work/digest-report.html — what each queued video actually COVERS,
ready to publish as a Claude Artifact.

The sibling of scripts/scout_report.py and deliberately NOT a section of it: the two pages answer
different questions and are read at different moments. Scout answers "is this worth my evening",
before watching, and its fields are a grade and one line of justification. This page answers "what
was in it" — after watching, to check nothing was missed, or before, to know what to expect — and
its fields are a retelling: headline, thesis, the bullet list of what is covered, the context, and
an honest note on what the digest could NOT carry. Folding both onto one page would put a verdict
column next to a retelling and make the reader decide which one they came for.

BODY-ONLY HTML, on purpose: the output carries an inline <style> but no doctype/html/head/body,
because the Artifact publisher wraps the file in its own skeleton. Browsers render the fragment
fine on their own, so the same file opens locally by double-click.

ORDER IS THE QUEUE'S ORDER, never a sort — same rule as the scout page, for the same reason: the
page is read next to the playlist it came from, so position is information.

A queued video with no digest is rendered as an explicit state row, never dropped: silently
shortening the deliverable to the videos that happened to work is the failure both report surfaces
in this repo exist to prevent. The three states are told apart because they need different actions
(re-run the fetch / look at the transcribe output / respawn the sub-agent).

NO AUDIO, no dub metrics, no flagged units: a digest is about the SOURCE video, and nothing on
this page depends on a dub existing. A video that has been dubbed renders exactly like one that
has not.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\digest_report.py --queue queue.txt
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\digest_report.py work\\<id>
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import time
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build_digest                                        # noqa: E402 — sibling in scripts/
import scout_report                                        # noqa: E402 — sibling in scripts/
from overdub import queueview                              # noqa: E402
from overdub.config import Config                          # noqa: E402
from overdub.workdir import jpeg_size, replace_retry        # noqa: E402

# --- shared page furniture, re-bound rather than copied -------------------------------
# ONE theme and ONE set of duration formats across both report pages. The alternative was a second
# copy of ~230 lines of CSS plus the wave math, which would drift the moment either page was
# touched — and the wave math in particular carries three measured bug histories in its comments
# (see scout_report.totals_of), so a copy would be a copy of those too.
#
# Same shape as scout_report's own `_unit_html = dub_blocks.unit_html` re-binding, and the
# dependency is ONE-WAY: scout_report must never import this module. Everything bound here is page
# furniture (style, formatting, escaping); nothing is scout-specific judgement.
_CSS = scout_report._CSS
clock = scout_report.clock
secs = scout_report.secs
_thumb_box = scout_report._thumb_box
_thumb_css = scout_report._thumb_css
_title_link = scout_report._title_link
_thumb_b64 = scout_report._thumb_b64
_paragraphs = scout_report._paragraphs
_chip = scout_report._chip
_load_json = scout_report._load_json
queue_ids = queueview.queue_ids
queue_playlist = queueview.queue_playlist

# The two upstream states are the SAME facts the scout page names, with the same operator action,
# so they are re-bound too: two pages describing one broken download differently is how a reader
# learns to distrust both.
_NOT_DOWNLOADED = scout_report._NOT_DOWNLOADED
_NOT_TRANSCRIBED = scout_report._NOT_TRANSCRIBED
# This page's own state: the transcript is there and the sub-agent is not. Distinct from the scout
# page's «не отсканировано» in both label and action — the two routes have separate artifacts, and
# a video can legitimately be scouted and not digested (or the reverse).
_NO_DIGEST = {"label": "нет пересказа", "cls": "v-none",
              "why": "транскрипт есть, пересказа нет — суммаризатор (D2) для этого видео не "
                     "отработал; перезапусти его и пересобери страницу"}

# A finished digest. It is a STATE like the other three (so the tally, the card class and the
# counters all key on `v` the same way) but it is deliberately never rendered as a chip on a row or
# a card: there is no verdict on this page, so a badge saying «пересказано» on every finished row
# would be a column of one repeated value — the defect that retired the scout page's
# focus/background axis. Its empty `why` is what makes that safe: nothing to print.
_DONE = {"label": "пересказано", "cls": "d-ok", "why": ""}

_THEMES_MAX = 260       # the scan table's «темы» cell: the point titles joined, then truncated

# Digest-specific rules, appended after the shared sheet. Everything here is a component the
# scout page has no equivalent of; nothing redefines a shared token.
_CSS_DIGEST = """
<style>
/* the headline: the one line that says what the video IS — bigger than body prose, still not a
   heading (the card's heading is the title) */
.sr .card p.headline{font-family:var(--ui);font-size:1.02rem;font-weight:600;color:var(--ink);
  margin:0 0 10px;max-width:66ch;}
/* channel · date · sentence count: provenance, so mono and quiet */
.sr p.meta{font-family:var(--mono);font-size:.8rem;color:var(--dim);margin:0 0 12px;
  font-variant-numeric:tabular-nums;max-width:none;}
/* section labels inside a card — the digest's structure made visible, quieter than an h2 because
   the page has only one level of section. The labels themselves are NOT quoted here on purpose:
   this comment ships inside the published page, and a literal label in it reads as page content to
   every substring check in the tests (the same trap scout_report's preview box documents). */
.sr p.lbl{font-family:var(--ui);font-size:.74rem;font-weight:640;letter-spacing:.07em;
  text-transform:uppercase;color:var(--accent);margin:18px 0 8px;max-width:none;}
/* the bullet list: what the video covers. Serif like the rest of the reading column, because it
   is read, not scanned */
.sr ul.pts{margin:0;padding-left:20px;max-width:66ch;}
.sr ul.pts li{font-family:var(--read);font-size:1rem;line-height:1.68;margin:0 0 10px;
  color:var(--ink);}
.sr ul.pts li b{font-family:var(--ui);font-weight:640;font-size:.97rem;}
/* the timestamp: a place to scrub to, so mono and tabular — and never the thing the eye lands on */
.sr .at{font-family:var(--mono);font-size:.8rem;color:var(--dim);
  font-variant-numeric:tabular-nums;margin-right:2px;}
/* what the digest could NOT carry — the honesty line, boxed so it is never read as more prose */
.sr p.worth{font-family:var(--ui);font-size:.94rem;color:var(--ink);margin:18px 0 0;
  padding:10px 12px;border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:0 8px 8px 0;background:var(--bg);max-width:66ch;}
/* the themes column: a list inside a table cell, so it must stay dim and tight */
.sr td.themes{color:var(--dim);}
.sr td.themes .chip{margin-right:8px;}
/* a finished digest's card stripe: the neutral accent, not one of the verdict colours. Green
   here would read as a grade, and this page grades nothing. */
.sr .card.d-ok{border-left-color:var(--accent);}
</style>
"""


def _themes(e: dict) -> str:
    """The point titles as one scannable cell — this page's answer to "what is touched on", at a
    glance and without opening the card.

    Truncated with a visible marker rather than dropped: a reader scanning the column is looking
    for a topic, and half the list beats none. The card carries every point in full."""
    titles = [p["title"] for p in e.get("points", []) if isinstance(p, dict) and p.get("title")]
    if not titles:
        return ""
    joined = " · ".join(titles)
    return joined if len(joined) <= _THEMES_MAX else joined[:_THEMES_MAX].rstrip() + " …"


def _row(e: dict) -> str:
    """One scan-table row. Everything that came from an LLM or a video title is escaped -- raw
    prose into HTML is the one place a report can break itself."""
    # The state chip opens the LAST cell, exactly as the grade chip does on the scout page — and a
    # finished digest carries none, so the chip means "something is missing here" and nothing else.
    v = e["v"]
    themes = _themes(e)
    last = (html.escape(themes) if themes
            else _chip(v) + html.escape(v.get("why", "—")))
    return (
        f'<tr id="r{e["n"]}">'
        f'<td class="idx">{e["n"]}</td>'
        f'<td class="pic">{_thumb_box(e)}</td>'
        f'<td class="name">{_title_link(e)}</td>'
        # runtime next to the title: it is scanned down the column ("what fits in an evening"),
        # which a value buried in prose cannot be
        f'<td class="num dur">{clock(e["duration"])}</td>'
        # the jump lives on the headline — the cell the reader is already looking at when they
        # decide they want the whole digest
        f'<td class="line"><a class="jump" href="#v{e["n"]}" title="подробнее">'
        f'{html.escape(e["headline"])}</a></td>'
        f'<td class="themes">{last}</td>'
        "</tr>"
    )


def _points_html(points: list[dict]) -> str:
    """The bullet list: bold lead-in, optional timestamp, then the text. Same shape as digest.md's
    bullets (build_digest.lead_in owns the punctuation for both), so the page and the pasteable
    file cannot render one point two ways."""
    out = ["<ul class=\"pts\">"]
    for p in points:
        at = (f'<span class="at">{html.escape(str(p["at"]))}</span> ' if p.get("at") else "")
        out.append(f'<li><b>{html.escape(build_digest.lead_in(p["title"]))}</b> '
                   f'{at}{html.escape(p["text"])}</li>')
    out.append("</ul>")
    return "".join(out)


def _meta_line(e: dict) -> str:
    """channel · upload date · sentence count, whichever exist.

    Renders nothing when none do, rather than a row of dashes. The upload date matters more here
    than on the scout page: a digest reads as timeless prose, and "what is covered" in a
    fast-moving field is only true as of a date."""
    bits = []
    if e.get("channel"):
        bits.append(html.escape(e["channel"]))
    if e.get("upload_date"):
        d = e["upload_date"]
        bits.append(f"{d[:4]}-{d[4:6]}-{d[6:]}")          # YYYYMMDD → ISO, never a guessed locale
    if e.get("n_sentences") is not None:
        bits.append(f"предложений: {e['n_sentences']}")
    return f'<p class="meta">{" · ".join(bits)}</p>' if bits else ""


def _card(e: dict) -> str:
    """One card: the digest itself, or the state that stands in for it.

    A card NEVER fabricates the parts a video has not earned — no bullet list for an
    undigested video, no thesis assembled out of the state text. The state IS the whole story
    then, and it says which action clears it."""
    v = e["v"]
    out = [
        f'<article class="card {v["cls"]}" id="v{e["n"]}">',
        '<div class="cardhead">',
        f'<span class="idx">{e["n"]}</span>',
        _thumb_box(e),
        f'<span class="name">{_title_link(e)}</span>',
        "" if e.get("doc") else _chip(v),
        f'<span class="num">{clock(e["duration"])}</span></div>',
    ]
    if not e.get("doc"):
        out.append(f'<p class="why">{html.escape(v["why"])}</p>')
        out.append(_meta_line(e))
        out.append("</article>")
        return "".join(out)

    out.append(f'<p class="headline">{html.escape(e["headline"])}</p>')
    out.append(_meta_line(e))
    out.append(_paragraphs(e["thesis"]))
    if e.get("points"):
        out.append('<p class="lbl">Ключевые находки</p>')
        out.append(_points_html(e["points"]))
    out.append('<p class="lbl">Зачем и оговорки</p>')
    out.append(_paragraphs(e["context"]))
    out.append(f'<p class="worth"><b>Стоит смотреть, если</b> '
               f'{html.escape(e["not_covered"])}</p>')
    out.append("</article>")
    return "".join(out)


def render(entries: list[dict], totals: dict, queue_name: str | None, stamp: str,
           playlist: dict | None = None) -> str:
    n_done = sum(1 for e in entries if e.get("doc"))
    tally = f'{_DONE["label"]}: {n_done}'
    # each unfinished state counted under its OWN name: "нет пересказа: 3" hiding a failed download
    # would send the operator to respawn a sub-agent that has nothing to read
    for state in (_NO_DIGEST, _NOT_TRANSCRIBED, _NOT_DOWNLOADED):
        n = sum(1 for e in entries if e["v"] is state)
        if n:
            tally += f' · {state["label"]}: {n}'
    n_points = sum(len(e.get("points") or []) for e in entries)
    if n_points:
        tally += f" · тем: {n_points}"

    t = totals
    out = [_CSS, _CSS_DIGEST, _thumb_css(entries), '<div class="sr">']
    out.append('<header class="head">')
    out.append("<h1>Пересказ очереди</h1>")
    if playlist:
        name = html.escape(playlist["title"])
        src = (f'<a class="ext" href="{html.escape(playlist["url"])}" target="_blank" '
               f'rel="noopener">{name}</a>' if playlist.get("url") else name)
        out.append(f'<p class="src">{src}</p>')
    source_note = (f'из <code>{html.escape(queue_name)}</code> · ' if queue_name else "")
    out.append(f'<p class="sub">{len(entries)} видео {source_note}{html.escape(stamp)}</p>')
    out.append(f'<p class="sub">{html.escape(tally)}</p>')
    # The strip renders only when some timing exists: a queue digested from transcripts that were
    # already on disk has no download or transcribe figure, and a strip of dashes reads as a broken
    # report rather than as "nothing ran".
    if any(t[k] is not None for k in ("download", "transcribe", "summarize")):
        out.append('<dl class="times">')
        content = clock(t["content"]) + ("+" if t["content_missing"] else "")
        # same '+' convention on the wave as the scout page: an agent that wrote no marker has no
        # known start, so it can only make the window WIDER than what was measured
        wave = secs(t["summarize"]) + ("+" if t.get("summarize_unmeasured") else "")
        for label, val in (("скачивание", secs(t["download"])),
                           ("транскрибация", secs(t["transcribe"])),
                           ("пересказ, волна", wave),
                           ("хронометраж очереди", content)):
            out.append(f'<div class="t"><dt>{label}</dt><dd>{val}</dd></div>')
        out.append("</dl>")
        out.append('<p class="sub" style="margin-top:8px">Первые две колонки — суммарная работа '
                   'по видео (ноль, если транскрипты уже лежали). Пересказ шёл параллельно, '
                   'поэтому там wall-clock всей волны: складывать их между собой нельзя.</p>')
    out.append("</header>")

    # The scan table needs something CONTENT-shaped to say; with no digest anywhere it would be a
    # column of state text, which is what the cards already say better.
    if n_done:
        out.append('<section class="sec"><div class="sechead"><h2>Что в очереди</h2>'
                   '<p class="sub">В порядке очереди — так же, как в плейлисте.</p></div>')
        out.append('<div class="wrap"><table><thead><tr>'
                   # the number and preview columns carry no label: "№" over a column of numbers,
                   # and a word over a column of images, say nothing the contents do not
                   "<th></th><th></th><th>Название</th><th>Время</th><th>Что это</th>"
                   "<th>Темы</th>"
                   "</tr></thead><tbody>")
        out.extend(_row(e) for e in entries)
        out.append("</tbody></table></div></section>")

    out.append('<section class="sec"><div class="sechead"><h2>Пересказы</h2>'
               '<p class="sub">Тот же порядок, карточка на видео.</p></div>')
    out.extend(_card(e) for e in entries)
    out.append("</section>")

    # The honest footer, and it is not decoration: every word on this page was derived from an ASR
    # transcript, so a mangled name or number can be the pipeline's, not the speaker's.
    out.append('<p class="foot">overdub · digest · пересказы собраны по ASR-транскриптам: '
               'имена, цифры и термины могли исказиться уже на входе. Страница говорит, что '
               '<em>затронуто</em> — она не заменяет просмотр.</p>')
    out.append("</div>")
    return "\n".join(out)


def _views(entries: list[dict]) -> list[dict]:
    """collect_entries rows → render-ready view dicts.

    The shared layer answers WHAT each workdir is (kind, title fallbacks, duration ladder); this
    resolves how it LOOKS on THIS page, which is one question: is there a digest, and if not,
    which of the three states applies.

    digest.json is read here rather than in queueview on purpose: it is one file read, and the
    shared collector must not grow a per-route artifact list — scout.json is in there because BOTH
    surfaces render grades, while nothing but this page reads a digest."""
    views = []
    for e in entries:
        work, kind, run = e["work"], e["kind"], e["run"]
        doc = _load_json(work.root / "digest.json")
        doc = doc if isinstance(doc, dict) and doc.get("headline") else None
        if doc:
            v = _DONE
        elif kind in ("scout", "pending", "run"):
            # a transcript exists (every one of those kinds implies one) — so the missing piece is
            # the sub-agent, whatever else the workdir has been through
            v = _NO_DIGEST
        elif kind == "fetched":
            v = _NOT_TRANSCRIBED
        else:
            v = _NOT_DOWNLOADED
        # A title may exist even when nothing else does: the info.json sidecar lands before the
        # media on a partial fetch. Showing it beats a bare id for a row whose job is action.
        info = _load_json(work.info_json)
        info_title = info.get("title") if isinstance(info, dict) else None
        title = ((doc or {}).get("title") or (run or {}).get("title") or info_title or e["vid"])
        # duration ladder: the digest artifact first (it recorded the same ladder at build time),
        # then the run's measured video_sec, then the collector's own fallback
        duration = (doc or {}).get("duration_sec")
        if duration is None and run is not None:
            duration = (run.get("timings", {}) or {}).get("video_sec")
        if duration is None:
            duration = e.get("duration_sec")
        views.append({
            "n": e["n"], "vid": e["vid"], "work": work, "kind": kind, "v": v, "doc": doc,
            "title": title, "duration": duration,
            "thumb_b64": _thumb_b64(work.root / "thumb.jpg"),
            "thumb_wh": jpeg_size(work.root / "thumb.jpg"),
            # content fields, straight from the artifact — no fallback ladder anywhere in here.
            # A digest is one document written by one agent in one pass: assembling a headline out
            # of summary.md while the bullets came from somewhere else would be a page that reads
            # like a digest and is not one. Missing → the state row.
            "headline": (doc or {}).get("headline") or "—",
            "thesis": (doc or {}).get("thesis") or "",
            "points": (doc or {}).get("points") or [],
            "context": (doc or {}).get("context") or "",
            "not_covered": (doc or {}).get("not_covered") or "",
            "channel": (doc or {}).get("channel")
                       or (info.get("channel") if isinstance(info, dict) else None),
            "upload_date": (doc or {}).get("upload_date"),
            "n_sentences": (doc or {}).get("n_sentences", e.get("n_sentences")),
            "timings": (doc or {}).get("timings") if isinstance((doc or {}).get("timings"), dict)
                       else {},
            "wave": (doc or {}).get("wave") if isinstance((doc or {}).get("wave"), dict)
                    else None,
        })
    return views


def totals_of(entries: list[dict]) -> dict:
    """The page's timing strip, computed by scout_report.totals_of over this page's key.

    Reused rather than re-derived: the wave math is subtle (windows grouped per wave, each window
    spanning the first agent's OWN start to the last draft, an unmeasured agent widening it rather
    than zeroing it) and it carries three measured bug histories in its comments. A second copy
    would be a copy of those too."""
    return scout_report.totals_of(entries, wave_key="digest_sec")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="digest_report",
        description="Render the digest page (what each queued video covers, queue order) as "
                    "publishable HTML.")
    p.add_argument("workdirs", nargs="*", type=Path, metavar="work/<id>",
                   help="per-video work dirs (appended after the queue)")
    p.add_argument("--queue", type=Path, default=None,
                   help="queue file — ALSO the page's row order")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"))
    p.add_argument("--out", type=Path, default=None,
                   help="output path (default: <work_root>/digest-report.html)")
    args = p.parse_args(argv)

    cfg = Config.load(args.config)
    queue: list[str] | None = None
    playlist = None
    if args.queue is not None:
        if not args.queue.is_file():
            p.error(f"queue file not found: {args.queue}")
        queue = queue_ids(args.queue)
        playlist = queue_playlist(args.queue)
        if not queue:
            p.error(f"queue file has no recognizable video ids: {args.queue}")
    if not args.workdirs and not queue:
        p.error("give at least one work/<id> dir and/or --queue FILE")

    # limit=0: this page renders no flagged units, so the collector must not spend anything
    # assembling them. Everything else about the walk (order, dedup, kinds, the never-drop-a-queued
    # -video rule) is exactly what the scout page gets.
    entries_raw, skipped = queueview.collect_entries(
        queue, args.workdirs, cfg.work_root, limit=0, cfg=cfg)
    if not entries_raw:
        print("[digest-report] nothing to render — "
              f"skipped (nothing to report): {', '.join(skipped) or '(none)'}")
        return 0
    entries = _views(entries_raw)

    out_path = args.out or (cfg.work_root / "digest-report.html")
    stamp = time.strftime("%Y-%m-%d %H:%M")
    page = render(entries, totals_of(entries),
                  args.queue.name if args.queue is not None else None, stamp, playlist)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(page, encoding="utf-8")
    replace_retry(tmp, out_path)

    n_done = sum(1 for e in entries if e.get("doc"))
    n_points = sum(len(e.get("points") or []) for e in entries)
    unfinished = [(s, sum(1 for e in entries if e["v"] is s))
                  for s in (_NO_DIGEST, _NOT_TRANSCRIBED, _NOT_DOWNLOADED)]
    unfinished = [(s, n) for s, n in unfinished if n]
    note = "".join(f', {n} {s["label"]}' for s, n in unfinished)
    print(f"[digest-report] {out_path}  ({n_done}/{len(entries)} digested, "
          f"{n_points} point(s){note})")
    # Each unfinished state named with the action it needs — the operator reads this line before
    # opening the page, and "3 incomplete" would not say which of the three fixes applies.
    for s, n in unfinished:
        print(f'[digest-report] {n} × "{s["label"]}" — {s["why"]}')
    if skipped:
        print(f"[digest-report] skipped (nothing to report): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
