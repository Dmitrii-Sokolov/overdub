"""Render the queue report: work/scout-report.html — scout grades AND dub triage on ONE page,
ready to publish as a Claude Artifact.

One page per queue (the separate morning-triage page was retired into this one on 2026-07-21,
PLAN item 2): entries come from
runreport.collect_entries — queue ids first, argv workdirs appended — and every workdir renders
exactly what it has earned. A scouted video keeps its grade and write-up; a dubbed one adds the
batch-table row, the flagged units with inline audio and the source-anomaly block; a
promoted-but-untranslated one gets an honest "в работе" state; a hole in the queue gets an
explicit state row, never a gap.

ORDER IS THE QUEUE'S ORDER, never a sort. The queue is the playlist the user handed over, and a
report that reorders it forces them to re-map every row onto the thing they actually have open —
position is information. The retired triage page sorted needs-triage first because its whole job
was "what is broken"; that morning-listen job is served here by the NAV BLOCK of anchors at the
top, which surfaces the worst without touching the order everything else is read in.

BODY-ONLY HTML, on purpose: the output carries an inline <style> but no doctype/html/head/body,
because the Artifact publisher wraps the file in its own skeleton. Browsers render the fragment
fine on their own, so the same file opens locally by double-click.

Audio, two modes (flagged units only — triage is a small fraction of a run, so the page stays
MBs, not gigabytes):
  - DEFAULT (embed): each flagged unit's wav is base64-inlined as a data: URI, so every player
    plays and the page is portable (move it, share it, publish it).
  - --link: reference the wavs by relative path instead (tiny page, zero copy) — but then the
    HTML must stay next to work/ so `<id>/segments/<lead>.wav` resolves under file://.

A queued video with NO artifacts at all is rendered as an explicit state row, never dropped:
silently shortening the deliverable to the videos that happened to work is the exact failure
the scout mode exists to prevent. An argv path with nothing to report is a named skip.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\scout_report.py --queue queue.txt
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\scout_report.py work\\<id> --link
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import sys
import time
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub import runreport                              # noqa: E402
from overdub.config import Config                          # noqa: E402
from overdub.workdir import jpeg_size, replace_retry       # noqa: E402

# Queue parsing is the shared data layer's now (one parse, three consumers) — the module-level
# aliases keep the public seam tests and callers already use.
queue_ids = runreport.queue_ids
queue_playlist = runreport.queue_playlist

# The closed verdict vocabulary of build_scout.py, mapped to presentation. Labels live HERE and
# not in scout.json on purpose: relabelling is a rendering change and must not invalidate every
# artifact on disk. Each dict is (label, cls) and nothing more: the tally and the unfinished
# counters iterate these in DECLARATION ORDER, so no ordering field rides along.
_VERDICT = {
    "high":   {"label": "высокое", "cls": "v-watch"},
    "medium": {"label": "среднее", "cls": "v-maybe"},
    "low":    {"label": "слабое", "cls": "v-skip"},
}
# A queued video with no grade is not one state but several, told apart by classify_workdir.
# They need different actions from the operator, and collapsing them into one row hides which
# one applies: a failed download is re-run, a failed transcribe is investigated, a missing
# summary is a sub-agent to respawn, a promoted video is a pipeline to resume.
_NOT_DOWNLOADED = {"label": "не скачано", "cls": "v-none",
                   "why": "видео не скачалось — перезапусти команду S1 (обычно это транзиентная "
                          "ошибка YouTube и со второго раза проходит)"}
_NOT_TRANSCRIBED = {"label": "не расшифровано", "cls": "v-none",
                    "why": "аудио есть, транскрипта нет — transcribe для этого видео не "
                           "отработал; смотри вывод S1"}
_MISSING = {"label": "не отсканировано", "cls": "v-none",
            "why": "транскрипт есть, оценки нет — суммаризатор (S2) для этого видео не "
                   "отработал; перезапусти его и пересобери отчёт"}
# kind "pending": a promoted video parked between download and translate (route B step 1 parks
# the WHOLE batch like this). Until this state existed the video was invisible on the triage
# page — the known gap this merge closes.
_PENDING = {"label": "в работе", "cls": "v-none",
            "why": "скачано полностью, перевод ещё не начат — видео продвинуто в дубляж; "
                   "прогони пайплайн дальше (маршрут A/B)"}
# kind "run" whose rollup degraded to None (torn artifacts) — rendered as a state, never as a
# fabricated row of zeros.
_NO_ROLLUP = {"label": "без свода", "cls": "v-none",
              "why": "артефакты дубляжа на месте, но run.json не собрался — битые "
                     "report.json/translation.json; смотри вывод пайплайна"}
# Dub states for a run that was never scouted: the row chip IS the dub verdict then, because
# it is the only assessment this video has.
_DUB_TRIAGE = {"label": "слушать", "cls": "t-triage",
               "why": "задублировано без разведки — есть проблемные юниты, слушай на карточке"}
_DUB_CLEAN = {"label": "чисто", "cls": "t-clean",
              "why": "задублировано без разведки — проверка чистая, слушать нечего"}

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
# toggle ([data-theme]) must win, in both directions -- hence the three blocks. Every colour the
# dub components brought over (badges, srcanom, ASR aside) is a token with a value in all three,
# same rule.
#
# The leading <meta charset> is not decoration either. The Artifact skeleton declares its own
# charset, so the published copy never needed one -- but this file is ALSO meant to be opened
# directly (see the module docstring: "opens locally by double-click"), and a file:// URL carries
# no Content-Type header for the browser to read UTF-8 off of. Without this tag a browser falls
# back to guessing and mangles every Cyrillic character in the report; with it, HTML5's "look in
# the first 1024 bytes" rule finds it before any Cyrillic byte does. Placing it before an explicit
# <head> is valid: browsers hoist stray head-only elements (meta/title/style/link) that appear
# before body content into an implicit head, same as the <style> tag right after it already relies on.
_CSS = """
<meta charset="utf-8">
<style>
.sr{--bg:#f7f8fa;--card:#ffffff;--ink:#141a21;--dim:#5b6875;--line:#dde3ea;
  --accent:#4a5b8c;--watch:#0d7f59;--maybe:#a86a10;--skip:#b03a52;
  --watch-bg:#e7f5ef;--maybe-bg:#fbf1de;--skip-bg:#fbeaee;--none-bg:#eef1f5;
  --purp:#7a4fa8;--purp-bg:#f2eafa;--orng:#b25415;--orng-bg:#fdeee2;
  --teal:#0b7285;--teal-bg:#e3f4f8;
  --ui:ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;
  --read:ui-serif,Georgia,"Times New Roman",serif;
  --mono:ui-monospace,"Cascadia Code",Consolas,monospace;
  background:var(--bg);color:var(--ink);font-family:var(--ui);line-height:1.55;
  padding:clamp(20px,4vw,48px);max-width:1240px;margin:0 auto;}
@media (prefers-color-scheme:dark){.sr{--bg:#0f1419;--card:#171e26;--ink:#e6ecf2;--dim:#93a1b0;
  --line:#2a3541;--accent:#8fa3d8;--watch:#4cc79a;--maybe:#e0a84b;--skip:#e8798f;
  --watch-bg:#132a22;--maybe-bg:#2b2213;--skip-bg:#2b171d;--none-bg:#1c242d;
  --purp:#c9a7ee;--purp-bg:#251b31;--orng:#e8985c;--orng-bg:#2e1f14;
  --teal:#5fc6dd;--teal-bg:#12262c;}}
:root[data-theme="dark"] .sr{--bg:#0f1419;--card:#171e26;--ink:#e6ecf2;--dim:#93a1b0;
  --line:#2a3541;--accent:#8fa3d8;--watch:#4cc79a;--maybe:#e0a84b;--skip:#e8798f;
  --watch-bg:#132a22;--maybe-bg:#2b2213;--skip-bg:#2b171d;--none-bg:#1c242d;
  --purp:#c9a7ee;--purp-bg:#251b31;--orng:#e8985c;--orng-bg:#2e1f14;
  --teal:#5fc6dd;--teal-bg:#12262c;}
:root[data-theme="light"] .sr{--bg:#f7f8fa;--card:#ffffff;--ink:#141a21;--dim:#5b6875;
  --line:#dde3ea;--accent:#4a5b8c;--watch:#0d7f59;--maybe:#a86a10;--skip:#b03a52;
  --watch-bg:#e7f5ef;--maybe-bg:#fbf1de;--skip-bg:#fbeaee;--none-bg:#eef1f5;
  --purp:#7a4fa8;--purp-bg:#f2eafa;--orng:#b25415;--orng-bg:#fdeee2;
  --teal:#0b7285;--teal-bg:#e3f4f8;}

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
.sr p.line{margin:0 0 10px;font-size:.92rem;max-width:66ch;}

/* verdict chip: colour AND text, never colour alone */
.sr .chip{display:inline-block;white-space:nowrap;font-size:.76rem;font-weight:640;
  letter-spacing:.02em;padding:3px 9px;border-radius:999px;}
.sr .v-watch{background:var(--watch-bg);color:var(--watch);}
.sr .v-maybe{background:var(--maybe-bg);color:var(--maybe);}
.sr .v-skip{background:var(--skip-bg);color:var(--skip);}
.sr .v-none{background:var(--none-bg);color:var(--dim);}
/* dub verdict chips: triage borrows the skip palette, clean the watch one — same two colours
   the reader already decoded for the grades, no third meaning of red/green on one page */
.sr .t-triage{background:var(--skip-bg);color:var(--skip);}
.sr .t-clean{background:var(--watch-bg);color:var(--watch);}

/* cost axis: outline, no fill — quieter than the verdict on purpose */
.sr .tag{display:inline-block;white-space:nowrap;font-size:.72rem;font-weight:560;
  letter-spacing:.02em;padding:2px 8px;border-radius:999px;border:1px solid var(--line);
  color:var(--dim);}
.sr .a-focus{border-color:var(--accent);color:var(--accent);}
.sr .a-trust{border-style:dashed;}

/* triage nav: the morning-listen entry points, an index instead of a re-sort */
.sr .nav{margin-top:14px;padding:10px 14px;border:1px solid var(--line);border-radius:8px;
  background:var(--card);font-size:.92rem;}
.sr .nav .lbl{color:var(--dim);margin-right:6px;}
.sr .nav a{color:var(--accent);text-decoration:none;}
.sr .nav a:hover{text-decoration:underline;}

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
.sr .card.t-triage{border-left-color:var(--skip);}
.sr .card.t-clean{border-left-color:var(--watch);}
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

/* dub components, restyled onto the scout tokens (ported from the retired triage page):
   the rollup and unit meta are data → mono; prose stays serif via .card p */
.sr .rollup{font-family:var(--mono);font-size:.85rem;color:var(--dim);
  font-variant-numeric:tabular-nums;margin:0 0 10px;max-width:none;}
.sr .unit{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:0 0 10px;
  background:var(--bg);}
.sr .reasons{margin-bottom:6px;}
/* reason badges keep the MACHINE codes (verify:low_similarity …) — the vocabulary the operator
   greps report.json with; a translated label would break that round-trip */
.sr .badge{display:inline-block;font-size:.72rem;font-weight:640;letter-spacing:.02em;
  padding:2px 8px;border-radius:999px;margin:0 5px 4px 0;font-family:var(--mono);}
.sr .badge.verify{background:var(--maybe-bg);color:var(--maybe);}
.sr .badge.speed{background:var(--skip-bg);color:var(--skip);}
.sr .badge.complete{background:var(--purp-bg);color:var(--purp);}
.sr .badge.translate{background:var(--orng-bg);color:var(--orng);}
.sr .badge.assemble{background:var(--none-bg);color:var(--dim);}
.sr .badge.src{background:var(--teal-bg);color:var(--teal);}
.sr .uid{font-family:var(--mono);font-size:.8rem;color:var(--dim);margin-bottom:6px;}
.sr .unit .en{display:block;color:var(--accent);font-size:.92rem;font-family:var(--ui);}
.sr .unit .ru{display:block;font-size:.95rem;font-family:var(--ui);}
/* the verify round-trip: what the TTS was asked to say vs what whisper heard back */
.sr .asr{font-size:.85rem;color:var(--dim);margin-top:8px;padding:6px 10px;
  border-left:2px solid var(--maybe);background:var(--maybe-bg);border-radius:0 6px 6px 0;}
.sr .asr b{color:var(--ink);font-weight:600;}
.sr audio{width:100%;margin-top:10px;height:34px;}
.sr .noaudio{display:inline-block;margin-top:8px;font-size:.8rem;color:var(--skip);}
/* source anomalies: a defect in the ENGLISH source — deliberately no player anywhere near it */
.sr .srcanom{margin:0 0 12px;padding:10px 12px;border:1px solid var(--line);
  border-left:3px solid var(--teal);border-radius:0 8px 8px 0;background:var(--card);
  font-size:.9rem;}
.sr .srcanom .lbl{color:var(--dim);font-size:.78rem;letter-spacing:.04em;
  text-transform:uppercase;margin:0 0 6px;max-width:none;font-family:var(--ui);}
.sr .srcanom ul{margin:0;padding-left:18px;}
.sr .srcanom li{margin-bottom:6px;}
.sr .srcanom .k{color:var(--teal);font-weight:600;}
.sr .srcanom .en{display:block;color:var(--accent);font-size:.85rem;}

.sr .foot{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);
  color:var(--dim);font-size:.82rem;}
</style>
"""


def _row(e: dict) -> str:
    """One scan-table row. Everything that came from an LLM or a video title is escaped -- raw
    prose into HTML is the one place a report can break itself."""
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


# --- audio (ported from the retired triage page) --------------------------------
def _audio_src(wav: Path, out_dir: Path, *, embed: bool) -> str | None:
    """A value for <audio src=...>: a base64 data: URI (embed) or a relative path (link). None
    when the wav is missing/unreadable — the caller renders a 'no audio' note instead of a broken
    player. Only FLAGGED units are ever passed here, so embed size stays bounded — the page
    stays MBs, not GBs."""
    if not wav.exists():
        return None
    if not embed:
        # --out on another drive than work/ makes a relative path impossible on Windows
        # (relpath raises ValueError across mounts). Fall back to the absolute path: --link
        # only ever promised a player that works on THIS machine, and killing the whole
        # render over one audio href is the wrong trade. Inherited crash from the retired
        # triage page; bit the first real cross-drive --out.
        try:
            rel = os.path.relpath(str(wav), str(out_dir))
        except ValueError:
            # abspath, not str(wav): the workdir usually arrives as a RELATIVE argv path
            # (work\<id>), and a relative href would resolve against the PAGE's directory —
            # exactly the drive the wav is not on.
            return os.path.abspath(str(wav)).replace(os.sep, "/")
        return rel.replace(os.sep, "/")
    try:
        b = wav.read_bytes()
    except OSError:
        return None
    return "data:audio/wav;base64," + base64.b64encode(b).decode("ascii")


def _badges(reasons: list[str]) -> str:
    """Reason badges carry the MACHINE codes verbatim (verify:low_similarity, speed:2.13 …) —
    the same vocabulary report.json and the digest use, so the operator can grep across all
    three surfaces. An unknown category falls into the neutral assemble style rather than
    being dropped."""
    out = []
    for r in reasons:
        cat = r.split(":", 1)[0]
        cls = (cat if cat in ("verify", "speed", "complete", "translate", "assemble", "src")
               else "assemble")
        out.append(f'<span class="badge {cls}">{html.escape(r)}</span>')
    return "".join(out)


def _fmt_span(a, b) -> str:
    def clk(t):
        t = int(round(t))
        return f"{t // 60}:{t % 60:02d}"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return f"{clk(a)}–{clk(b)}"
    return "—"


def _unit_html(u: dict, wav: Path, out_dir: Path, *, embed: bool) -> str:
    """One flagged render unit: reasons, meta, EN/RU text, the verify round-trip pair, and the
    player for the RAW segment wav (pre-atempo — what verification actually heard)."""
    ids = u.get("ids") or []
    span = _fmt_span(u.get("start"), u.get("end"))
    parts = [f'#{u.get("lead")}', f'ids {ids}', span]
    if u.get("speed") is not None:
        parts.append(f'speed ×{u["speed"]}')
    if u.get("similarity") is not None:
        parts.append(f'sim {u["similarity"]}')
    meta = " · ".join(html.escape(str(p)) for p in parts)

    lines = ['<div class="unit">',
             f'<div class="reasons">{_badges(u.get("reasons") or [])}</div>',
             f'<div class="uid">{meta}</div>']
    if u.get("src_en"):
        lines.append(f'<span class="en">EN: {html.escape(u["src_en"])}</span>')
    if u.get("text_ru"):
        lines.append(f'<span class="ru">RU: {html.escape(u["text_ru"])}</span>')
    # verify triage: what the round-trip EXPECTED vs what whisper HEARD back
    if u.get("hypothesis") is not None and any(r.startswith("verify:")
                                               for r in (u.get("reasons") or [])):
        exp = html.escape(u.get("text_tts") or "")
        heard = html.escape(u.get("hypothesis") or "")
        lines.append(f'<div class="asr"><b>ожидалось:</b> {exp}<br>'
                     f'<b>услышано:</b> {heard}</div>')
    src = _audio_src(wav, out_dir, embed=embed)
    if src is not None:
        lines.append(f'<audio controls preload="none" src="{src}"></audio>')
    else:
        lines.append('<div class="noaudio">нет аудио (wav отсутствует)</div>')
    lines.append("</div>")
    return "".join(lines)


def _srcanom_html(run: dict) -> str:
    """The source-anomaly block, or "" when the scan found nothing. Rendered even when there are
    no flagged units: a pre-synthesis workdir is exactly when this signal is most actionable
    (--repair-asr is still cheap there). Deliberately NO <audio> player and deliberately not
    routed through flagged_units: the defect is in the ENGLISH source, so listening to the
    Russian tells the operator nothing. html.escape on every field — raw LLM prose into HTML."""
    s = run.get("source", {}) or {}
    items = s.get("items") or []
    if not items:
        return ""
    li = []
    for it in items:
        li.append(f'<li><b>#{html.escape(str(it.get("id")))}</b> '
                  f'<span class="k">{html.escape(str(it.get("kind")))}</span> — '
                  f'{html.escape(it.get("note") or "")}'
                  f'<span class="en">EN: {html.escape(it.get("src_en") or "")}</span></li>')
    return (f'<div class="srcanom"><p class="lbl">аномалии источника ({len(items)}) — '
            f'дефект в английском исходнике, слушать русское аудио бессмысленно</p>'
            f'<ul>{"".join(li)}</ul></div>')


def _dub_table(dubs: list[dict]) -> str:
    """The dub batch table. Header labels come from runreport.BATCH_COLUMNS and the ten data
    cells are printed VERBATIM from batch_row(run)["cells"] — the same strings the text digest
    prints, so the two surfaces can never again disagree about the same run (PLAN item 2). The
    cell vocabulary is machine-formatted numbers ("123.4", "n/a", "-", "3.4%"), no HTML-active
    characters by construction, hence no escape on them."""
    ths = "".join(f"<th>{html.escape(label)}</th>" for _key, label in runreport.BATCH_COLUMNS)
    rows = [f"<thead><tr>{ths}</tr></thead>", "<tbody>"]
    for e in dubs:
        row = runreport.batch_row(e["run"])
        needs = row["needs_triage"]
        # video/title/triage are the per-medium ends of the row: the digest truncates to 24 and
        # prints yes/no; this page links, escapes and colours. The middle is the contract.
        cells: list[tuple[str, str]] = [
            ("video", f'<a class="jump" href="#v{e["n"]}">{html.escape(row["video_id"])}</a>'),
            ("title", html.escape((row["title"] or "")[:40])),
        ]
        cells += row["cells"]
        cells.append(("triage", "слушать" if needs else "чисто"))
        tds = []
        for key, val in cells:
            if key == "triage":
                # coloured via a class keyed BY COLUMN KEY, never by cell index: the retired
                # page hard-coded the triage cell's index and the src column landed on it
                # silently (PLAN item 2) — adding a column here cannot mis-colour anything
                tds.append(f'<td class="{"t-triage" if needs else "t-clean"}">{val}</td>')
            elif key in ("video", "title"):
                tds.append(f"<td>{val}</td>")
            else:
                tds.append(f'<td class="num">{val}</td>')
        rows.append(f"<tr>{''.join(tds)}</tr>")
    rows.append("</tbody>")
    return f'<div class="wrap"><table>{"".join(rows)}</table></div>'


def _chip(d: dict) -> str:
    return f'<span class="chip {d["cls"]}">{html.escape(d["label"])}</span>'


def _card(e: dict, out_dir: Path, *, embed: bool) -> str:
    """One card, whatever the workdir has earned. The invariant inherited from both parents: a
    card NEVER fabricates dub metrics for a non-run kind — no RTF, no audio, no triage/clean
    chip. A scouted video keeps its grade next to its dub chips (scout.json survives promotion;
    it is not in invalidate_downstream's target list)."""
    v = e["v"]
    chips = []
    if e.get("grade"):
        chips.append(_chip(e["grade"]))
    if e.get("dub"):
        chips.append(_chip(e["dub"]))
    if not chips:
        chips.append(_chip(v))          # pipeline state — the only assessment this video has
    elif v is _NO_ROLLUP:
        # ...but a torn rollup rides ALONGSIDE a surviving grade chip: run.json failed to build
        # though the dub artifacts are on disk, and that «без свода» state is news the grade
        # cannot carry. Everywhere else v already equals the grade/dub chip, so this only fires
        # for a scouted-then-torn video.
        chips.append(_chip(v))
    if e.get("author") == "trusted":
        chips.append('<span class="tag a-trust">' + html.escape(_TRUSTED["label"]) + "</span>")

    out = [
        f'<article class="card {v["cls"]}" id="v{e["n"]}">',
        '<div class="cardhead">',
        # the number is a LABEL here, not a link: the reader arrived from the table and their
        # own back gesture already returns them, so a jump back was a link that never earned
        # its underline and one more thing competing with the title
        f'<span class="idx">{e["n"]}</span>',
        _thumb_box(e),
        f'<span class="name">{_title_link(e)}</span>',
        "".join(chips),
        f'<span class="num">{clock(e["duration"])}</span></div>',
    ]

    if e["kind"] == "run" and e["run"] is not None:
        run = e["run"]
        row = runreport.batch_row(run)
        c = dict(row["cells"])
        sp = run.get("speed", {}) or {}
        # The rollup REUSES batch_row's cell strings (cp/adv are the actionable/advisory split —
        # never n_flagged: printing the pooled count here while the digest prints the split was
        # the original two-numbers-one-batch bug, PLAN item 2). med/p95 are card-only depth the
        # table deliberately omits, read off the same run.json.
        n_sent = (run.get("translate", {}) or {}).get("n_sentences", 0)
        rollup = (f"translate {c['tr']}/{n_sent}"
                  f" · verify {c['vf']} · completeness {c['cp']} (+{c['adv']} advisory)"
                  f" · speed med {sp.get('median')}/p95 {sp.get('p95')}/max {c['spd_max']}"
                  f" (n>1.8 {c['n_over']})")
        out.append(f'<p class="rollup">{html.escape(rollup)}</p>')
        out.append(_srcanom_html(run))
        if e["summary"]:
            out.append(_paragraphs(e["summary"]))
        elif e.get("paragraph"):
            out.append(_paragraphs(e["paragraph"]))
        if e["units"]:
            out.extend(_unit_html(u, e["work"].seg_wav(u.get("lead")), out_dir, embed=embed)
                       for u in e["units"])
        else:
            out.append('<p class="line">проблемных юнитов нет — слушать нечего.</p>')
    elif e["kind"] == "pending":
        # The promoted-video state line — before the merge this workdir was invisible on the
        # triage page (skipped as "no run.json") and mislabelled on the scout page.
        out.append('<p class="line">в работе — скачано полностью, перевод ещё не начат</p>')
        out.append(_meta_line(e))
        if e["summary"]:
            out.append(_paragraphs(e["summary"]))
        elif e.get("paragraph"):
            out.append(_paragraphs(e["paragraph"]))
    elif e["kind"] == "scout":
        out.append(f'<p class="why">{html.escape(e["highlight"])}</p>')
        out.append(_meta_line(e))
        if e.get("grade"):
            out.append(_paragraphs(e["paragraph"]))
        elif e["summary"]:
            out.append(_paragraphs(e["summary"]))
        else:
            # A transcribed-but-unsummarized video is a pipeline STATE, not an empty card.
            # Saying so keeps a half-finished scout pass from reading as a video with nothing
            # to say. (Exact phrase pinned by the migrated tests.)
            out.append('<p class="line">no summary.md yet — run the scout summarizer '
                       '(overdub-scout skill, step S2).</p>')
    else:
        # missing / fetched / run-without-rollup: the state is the whole story
        out.append(f'<p class="why">{html.escape(e["highlight"])}</p>')
        out.append(_paragraphs(e["paragraph"]))
    out.append("</article>")
    return "".join(out)


def _meta_line(e: dict) -> str:
    """Sentence count for a transcript-only card. Cost is the point: whether a video earns a dub
    is a question about length, and an EMPTY transcript ("предложений: 0") is a real answer —
    transcribe ran and found nothing — never a reason to drop the card."""
    n = e.get("n_sentences")
    return f'<p class="line">предложений: {n}</p>' if n is not None else ""


def _paragraphs(text: str) -> str:
    """Blank-line-separated blocks → separate <p>. The SPLIT IS THE WRITER'S (summarizer or
    scout agent): it is the only party that knows where the meaning turns, and a renderer
    chopping every N sentences would cut mid-thought. A single-block paragraph still renders —
    as one <p>, exactly as before — so an older artifact is never mangled to force a shape."""
    parts = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    return "".join(f"<p>{html.escape(p)}</p>" for p in parts or [text])


def render(entries: list[dict], totals: dict, queue_name: str | None, stamp: str,
           playlist: dict | None = None, *, out_dir: Path | None = None,
           embed: bool = True) -> str:
    counts = {k: sum(1 for e in entries if e["v"] is _VERDICT[k]) for k in _VERDICT}
    tally = " · ".join(f'{_VERDICT[k]["label"]}: {counts[k]}' for k in _VERDICT)
    # each unfinished state counted under its OWN name: "не отсканировано: 3" hiding a failed
    # download would send the operator to respawn a summarizer that has nothing to read
    for state in (_NOT_DOWNLOADED, _NOT_TRANSCRIBED, _MISSING, _NO_ROLLUP):
        n = sum(1 for e in entries if e["v"] is state)
        if n:
            tally += f' · {state["label"]}: {n}'
    # pending is counted by KIND, not by chip identity: a graded pending wears its grade chip
    # but is still a video parked mid-promotion, and hiding that count hides the resume work
    n_pending = sum(1 for e in entries if e["kind"] == "pending")
    if n_pending:
        tally += f' · {_PENDING["label"]}: {n_pending}'
    dubs = [e for e in entries if e["kind"] == "run" and e["run"] is not None]
    n_triage = sum(1 for e in dubs if e["run"].get("needs_triage"))
    if dubs:
        tally += f' · слушать: {n_triage} · чисто: {len(dubs) - n_triage}'

    t = totals
    # the per-video preview rules ride right behind the static sheet: they are generated CSS, and
    # separating them keeps _CSS a constant the tests can assert against
    out = [_CSS, _thumb_css(entries), '<div class="sr">']
    out.append('<header class="head">')
    out.append("<h1>Очередь</h1>")
    if playlist:
        # the source the queue came from, named at the top: without it the report is a list of
        # videos with no answer to "which playlist was this again"
        name = html.escape(playlist["title"])
        src = (f'<a class="ext" href="{html.escape(playlist["url"])}" target="_blank" '
               f'rel="noopener">{name}</a>' if playlist.get("url") else name)
        out.append(f'<p class="src">{src}</p>')
    source_note = (f'из <code>{html.escape(queue_name)}</code> · ' if queue_name else "")
    out.append(f'<p class="sub">{len(entries)} видео {source_note}{html.escape(stamp)}</p>')
    out.append(f'<p class="sub">{html.escape(tally)}</p>')
    # The scout timing strip renders only when scout timings exist: on a pure-dub queue every
    # figure would be a dash, and a strip of dashes reads as a broken report, not as "no scout".
    if any(t[k] is not None for k in ("download", "transcribe", "summarize")):
        out.append('<dl class="times">')
        # The queue's own runtime leads: it is what the reader budgets against. The pipeline
        # columns after it are what the machine spent, which is a different question.
        content = clock(t["content"]) + ("+" if t["content_missing"] else "")
        # same '+' convention on the wave: an agent that wrote no marker has no known start, so
        # it can only widen the window past what was measured. Measured 2026-07-21: 1 of 6
        # agents skipped the marker, and without this the figure would read as exact.
        summarize = secs(t["summarize"]) + ("+" if t.get("summarize_unmeasured") else "")
        # pipeline stages in the order they ran, their total, then the queue's own runtime last —
        # it is a different KIND of number (what there is to watch, not what the machine spent),
        # so it sits after the sum rather than inside the run of things that add up
        for label, val in (("скачивание", secs(t["download"])),
                           ("транскрибация", secs(t["transcribe"])),
                           ("суммаризация, волна", summarize),
                           ("хронометраж очереди", content)):
            out.append(f'<div class="t"><dt>{label}</dt><dd>{val}</dd></div>')
        out.append("</dl>")
        # No grand total any more, so the note no longer has to excuse one: it just says what the
        # third figure IS, since a wall clock beside two sums is the one thing a reader would
        # otherwise mis-add.
        out.append('<p class="sub" style="margin-top:8px">Первые две колонки — суммарная работа '
                   'по видео. Суммаризация шла параллельно, поэтому там wall-clock всей волны: '
                   'складывать их между собой нельзя.</p>')
    if dubs:
        # dub totals from the shared layer — the same numbers the digest's totals line prints
        tot = runreport.batch_totals([e["run"] for e in dubs])
        out.append(f'<p class="sub">{len(dubs)} видео · wall {tot["total_wall"]}s · '
                   f'throughput {tot["throughput"]} · '
                   f'{tot["n_triage"]} требуют прослушивания</p>')
    out.append("</header>")

    if n_triage:
        # The morning-listen job, served by NAVIGATION instead of by re-sorting the queue: the
        # worst videos get anchors, the queue keeps its order.
        links = " · ".join(
            f'<a href="#v{e["n"]}">{e["n"]} — {html.escape((e["title"] or e["vid"])[:40])}</a>'
            for e in dubs if e["run"].get("needs_triage"))
        out.append(f'<div class="nav"><span class="lbl">Требуют прослушивания:</span> '
                   f'{links}</div>')

    # The scan table needs at least one scout.json to have anything scout-shaped to say; a
    # pure-dub queue skips it (states still show on the cards) rather than rendering a table
    # of dashes.
    if any(e.get("scout_doc") for e in entries):
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

    if dubs:
        out.append('<section class="sec"><div class="sechead"><h2>Дубляж</h2>'
                   '<p class="sub">Те же ячейки, что печатает текстовый дайджест — цифры '
                   'совпадают по построению.</p></div>')
        out.append(_dub_table(dubs))
        out.append("</section>")

    out.append('<section class="sec"><div class="sechead"><h2>Подробно</h2>'
               '<p class="sub">Тот же порядок, карточка на видео.</p></div>')
    out.extend(_card(e, out_dir or Path("."), embed=embed) for e in entries)
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


def _views(entries: list[dict]) -> list[dict]:
    """collect_entries rows → render-ready view dicts. The shared layer answers WHAT each
    workdir is; this resolves how it LOOKS: which chip leads the row (grade > dub state >
    pipeline state), which title/duration ladder applies, and which scout presentation fields
    ride along."""
    views = []
    for e in entries:
        work, kind, run = e["work"], e["kind"], e["run"]
        doc = e["scout"] if isinstance(e.get("scout"), dict) else None
        grade = _VERDICT.get(doc.get("quality")) if doc else None
        dub = None
        if kind == "run" and run is not None:
            dub = _DUB_TRIAGE if run.get("needs_triage") else _DUB_CLEAN
        # A TORN dub layer is the news and must win the v-slot even when a surviving scout.json
        # could otherwise colour the row a grade: report.json / translation.json are on disk but
        # run.json did not build. The tally and main()'s unfinished list both key on
        # `e["v"] is _NO_ROLLUP`, so letting a grade win here would silently drop the video from
        # the «без свода» count — a torn dub reported as a healthy graded scout. The grade CHIP
        # still renders beside the state on the card (e["grade"] is kept below); only v is claimed.
        if kind == "run" and run is None:
            v = _NO_ROLLUP
        elif grade:
            v = grade
        elif dub:
            v = dub
        elif kind == "pending":
            v = _PENDING
        elif kind == "scout":
            v = _MISSING
        elif kind == "fetched":
            v = _NOT_TRANSCRIBED
        else:
            v = _NOT_DOWNLOADED
        # A title may exist even when nothing else does: the info.json sidecar lands before the
        # media on a partial fetch. Showing it beats a bare id for a row whose job is action.
        info = _load_json(work.info_json)
        info_title = info.get("title") if isinstance(info, dict) else None
        title = ((doc or {}).get("title") or (run or {}).get("title")
                 or info_title or e["vid"])
        # duration ladder: the scout artifact first (it survives promotion and was already
        # sanity-checked), then the run's measured video_sec, then the collector's fallback
        duration = (doc or {}).get("duration_sec")
        if duration is None and run is not None:
            duration = (run.get("timings", {}) or {}).get("video_sec")
        if duration is None:
            duration = e.get("duration_sec")
        # The card's fallback prose. ONLY the pure-state cards (missing/fetched/torn rollup)
        # reuse the state's why text as their body; run/pending/scout cards have their own
        # prose logic (summary → scout paragraph → state phrase) and echoing the why here
        # would print the pipeline state as if it were a write-up about the video.
        if grade:
            paragraph = (doc or {}).get("paragraph") or ""
        elif kind in ("missing", "fetched") or (kind == "run" and run is None):
            paragraph = v["why"]
        else:
            paragraph = ""
        views.append({
            "n": e["n"], "vid": e["vid"], "work": work, "kind": kind, "v": v,
            "grade": grade, "dub": dub, "run": run, "units": e["units"],
            "summary": e["summary"], "scout_doc": doc,
            "author": (doc or {}).get("author"),
            "thumb_b64": _thumb_b64(work.root / "thumb.jpg"),
            "thumb_wh": jpeg_size(work.root / "thumb.jpg"),
            "title": title, "duration": duration,
            "one_liner": ((doc or {}).get("one_liner") or "—") if grade else "—",
            "highlight": ((doc or {}).get("highlight") or "—") if grade else v["why"],
            "paragraph": paragraph,
            "n_sentences": e.get("n_sentences"),
            "timings": (doc or {}).get("timings") if isinstance((doc or {}).get("timings"), dict)
                       else {},
            "wave": (doc or {}).get("wave") if isinstance((doc or {}).get("wave"), dict)
                    else None,
        })
    return views


def totals_of(entries: list[dict]) -> dict:
    """Pipeline stages are SUMS — they ran one after another, so their sum is the work done.
    Summarization is a WALL CLOCK: the sub-agents run concurrently, so summing their windows
    would exceed the elapsed time and mean nothing (2026-07-21: 1053 s of agent windows inside a
    311 s wave). It spans the first agent's own start to the last draft — see the comment on the
    grouping below for why the operator's `wave.start` stamp is NOT that start.

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
    # The wave runs from the FIRST AGENT'S OWN START, not from `wave.start`.
    #
    # `wave.start` is stamped by the operator before spawning, so the span from it to the last
    # draft also contains however long it took to get the sub-agents running. That gap used to be
    # seconds. Once S2 moved to a workflow it stopped being: on 2026-07-21 the invocation took
    # eight attempts and the report printed 9.4 min for a 192 s wave -- 371 s of it was the
    # orchestrator retrying a tool call, filed under "суммаризация". Fixing the invocation
    # dropped the same figure to 5.4 min against a 311 s wave, which confirmed the split but
    # left the definition wrong.
    #
    # Each agent's real start is recoverable from what build_scout already stores:
    # `draft_at - summarize_sec`, both filesystem-stamped. So the wave is
    # `max(draft_at) - min(draft_at - summarize_sec)` and the stamp is no longer part of it.
    #
    # STILL GROUPED BY START, one window per wave, windows summed -- a queue is routinely
    # summarized in several waves (the resume filter re-runs only what needs it, so carried
    # videos keep an older wave's start forever), and spanning them all would bill the idle
    # hours between waves as summarization.
    groups: dict[float, list[tuple[float, float | None]]] = {}
    for e in entries:
        w = e.get("wave")
        if not isinstance(w, dict):
            continue
        st, dr = w.get("start"), w.get("draft_at")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (st, dr)):
            continue
        if dr < st:                       # carry-over from an earlier wave, not part of this one
            continue
        sec = (e.get("timings") or {}).get("summarize_sec")
        ok = isinstance(sec, (int, float)) and not isinstance(sec, bool) and sec >= 0
        groups.setdefault(st, []).append((dr, sec if ok else None))

    windows, sm_unmeasured = [], 0
    for rows in groups.values():
        starts = [dr - sec for dr, sec in rows if sec is not None]
        # an agent that wrote no marker: its draft still bounds the END of the wave, but its
        # start is unknown, so it can only make the window WIDER than measured -- counted, and
        # rendered with a '+' the same way a missing duration marks the queue runtime a floor
        sm_unmeasured += sum(1 for _, sec in rows if sec is None)
        if starts:
            windows.append(max(dr for dr, _ in rows) - min(starts))
    sm = sum(windows) if windows else None
    # Total runtime of the QUEUE itself — the number the operator budgets against ("do I have
    # 9 hours of watching here or 90 minutes"). Missing durations are skipped, not zeroed, and
    # the count of skipped rows travels with it so the figure can be read as a floor rather than
    # a measurement when part of the queue never scanned.
    durs = [e["duration"] for e in entries
            if isinstance(e.get("duration"), (int, float)) and not isinstance(e["duration"], bool)]
    return {"download": dl, "transcribe": tr, "summarize": sm,
            "summarize_unmeasured": sm_unmeasured,
            "content": sum(durs) if durs else None,
            "content_missing": len(entries) - len(durs)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="scout_report",
        description="Render the queue report (scout grades + dub triage, queue order) as "
                    "publishable HTML.")
    p.add_argument("workdirs", nargs="*", type=Path, metavar="work/<id>",
                   help="per-video work dirs (appended after the queue)")
    p.add_argument("--queue", type=Path, default=None,
                   help="queue file — ALSO the report's row order")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"))
    p.add_argument("--out", type=Path, default=None,
                   help="output path (default: <work_root>/scout-report.html)")
    p.add_argument("--link", action="store_true",
                   help="reference wavs by relative path instead of embedding (smaller page; "
                        "the HTML must then stay next to work/)")
    p.add_argument("--limit", type=int, default=500,
                   help="max flagged units rendered per video (default 500)")
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

    entries_raw, skipped = runreport.collect_entries(
        queue, args.workdirs, cfg.work_root, limit=args.limit, cfg=cfg)
    if not entries_raw:
        # argv paths that are neither a run nor a transcript: named, never a silent empty page
        print("[scout-report] nothing to render — "
              f"skipped (nothing to report): {', '.join(skipped) or '(none)'}")
        return 0
    entries = _views(entries_raw)

    out_path = args.out or (cfg.work_root / "scout-report.html")
    out_dir = out_path.resolve().parent
    embed = not args.link
    stamp = time.strftime("%Y-%m-%d %H:%M")
    page = render(entries, totals_of(entries),
                  args.queue.name if args.queue is not None else None, stamp, playlist,
                  out_dir=out_dir, embed=embed)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(page, encoding="utf-8")
    replace_retry(tmp, out_path)

    # Each unfinished state named on stdout too, with the action it needs — the operator reads
    # this line before opening the page, and "3 incomplete" would not say which of the
    # different fixes applies.
    unfinished = [(s, sum(1 for e in entries if e["v"] is s))
                  for s in (_NOT_DOWNLOADED, _NOT_TRANSCRIBED, _MISSING, _NO_ROLLUP)]
    n_pending = sum(1 for e in entries if e["kind"] == "pending")
    if n_pending:
        unfinished.append((_PENDING, n_pending))
    unfinished = [(s, n) for s, n in unfinished if n]
    note = "".join(f', {n} {s["label"]}' for s, n in unfinished)
    # dubbed videos counted apart from scouted ones: "0 need triage" out of a count that
    # includes never-dubbed videos would be a lie about them (the retired page's rule, kept)
    dubs = [e for e in entries if e["kind"] == "run" and e["run"] is not None]
    n_triage = sum(1 for e in dubs if e["run"].get("needs_triage"))
    n_scouts = sum(1 for e in entries if e["kind"] == "scout")
    n_units = sum(len(e["units"]) for e in entries)
    print(f"[scout-report] {out_path}  ({len(dubs)} video(s), "
          + (f"{n_scouts} scouted, " if n_scouts else "")
          + f"{n_triage} need triage, {n_units} flagged unit(s), "
          + ("embedded" if embed else "linked") + f" audio{note})")
    for s, n in unfinished:
        print(f'[scout-report] {n} × "{s["label"]}" — {s["why"]}')
    if skipped:
        print(f"[scout-report] skipped (nothing to report): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
