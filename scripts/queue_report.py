"""Render the queue report: work/queue-report.html — dub triage for a whole queue on ONE page,
ready to publish as a Claude Artifact.

One page per queue: entries come from queueview.collect_entries — queue ids first, argv workdirs
appended — and every workdir renders exactly what it has earned. A dubbed video gets the
batch-table row, the flagged units with inline audio and the source-anomaly block; a
transcribed-but-undubbed one (route E's state) gets an honest transcript card; a
promoted-but-untranslated one gets an honest "в работе" state; a hole in the queue gets an
explicit state row, never a gap.

ORDER IS THE QUEUE'S ORDER, never a sort. The queue is the playlist the user handed over, and a
report that reorders it forces them to re-map every row onto the thing they actually have open —
position is information. The morning-listen job is served by the NAV BLOCK of anchors at the
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
this page exists to prevent. An argv path with nothing to report is a named skip.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\queue_report.py --queue queue.txt
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\queue_report.py work\\<id> --link
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

import dub_blocks                                          # noqa: E402 — sibling in scripts/
from overdub import queueview                              # noqa: E402
from overdub.config import Config                          # noqa: E402
from overdub.workdir import jpeg_size, replace_retry       # noqa: E402

# Queue parsing is the shared data layer's now (one parse, three consumers) — the module-level
# aliases keep the public seam tests and callers already use.
queue_ids = queueview.queue_ids
queue_playlist = queueview.queue_playlist

# A queued video that has not earned a dub row is not one state but several, told apart by
# classify_workdir. They need different actions from the operator, and collapsing them into one
# row hides which one applies: a failed download is re-run, a failed transcribe is investigated,
# a promoted video is a pipeline to resume.
_NOT_DOWNLOADED = {"label": "не скачано", "cls": "v-none",
                   "why": "видео не скачалось — перезапусти команду шага 1 (обычно это "
                          "транзиентная ошибка YouTube и со второго раза проходит)"}
_NOT_TRANSCRIBED = {"label": "не расшифровано", "cls": "v-none",
                    "why": "аудио есть, транскрипта нет — transcribe для этого видео не "
                           "отработал; смотри вывод шага 1"}
# kind "transcribed": a transcript-only workdir (--transcribe-only ran and stopped — route E's
# state). A real state of its own: the video is readable, not dubbed, and needs no action here.
_TRANSCRIBED = {"label": "расшифровано", "cls": "v-none",
                "why": "есть транскрипт, дубляжа нет — видео прошло --transcribe-only "
                       "(маршрут E); для дубляжа прогони его через маршрут B"}
# kind "pending": a promoted video parked between download and translate (route B step 1 parks
# the WHOLE batch like this). Until this state existed the video was invisible on the triage
# page — the known gap this merge closes.
_PENDING = {"label": "в работе", "cls": "v-none",
            "why": "скачано полностью, перевод ещё не начат — видео продвинуто в дубляж; "
                   "прогони пайплайн дальше (маршрут B)"}
# kind "run" whose rollup degraded to None (torn artifacts) — rendered as a state, never as a
# fabricated row of zeros.
_NO_ROLLUP = {"label": "без свода", "cls": "v-none",
              "why": "артефакты дубляжа на месте, но run.json не собрался — битые "
                     "report.json/translation.json; смотри вывод пайплайна"}
# Dub states: the row chip IS the dub verdict. Deliberately NO "why": the unfinished states carry
# guidance text because they demand an ACTION, but a dub verdict is status — the chip says it
# all; details live in the dub table and on the card.
_DUB_TRIAGE = {"label": "слушать", "cls": "t-triage"}
_DUB_CLEAN = {"label": "чисто", "cls": "t-clean"}


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


# --------------------------------------------------------------------------- style
# Tokens first, components through the tokens: the dark palette is a token redefinition, so no
# component rule is ever duplicated per theme. Both the OS preference and the viewer's explicit
# toggle ([data-theme]) must win, in both directions -- hence the three blocks. Every colour the
# dub components use (badges, srcanom, ASR aside) is a token with a value in all three, same rule.
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
/* Full-bleed background. The tokens live on .sr (a fragment must not restyle :root), but the
   BODY behind the 1240px column belongs to the host page — which painted white gutters beside
   the content in every light host and worse in dark ones (operator report 2026-07-22). Body
   sits outside .sr's token scope, so these four raw colours are deliberate duplicates of --bg
   below; change one, change both. */
body{margin:0;background:#f7f8fa;}
@media (prefers-color-scheme:dark){body{background:#0f1419;}}
:root[data-theme="dark"] body{background:#0f1419;}
:root[data-theme="light"] body{background:#f7f8fa;}
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

/* links: the title goes out to the video, the number jumps within the page */
.sr a.ext{color:inherit;text-decoration:underline;text-decoration-color:var(--line);
  text-underline-offset:3px;}
.sr a.ext:hover{text-decoration-color:var(--accent);}
.sr a.jump{color:var(--dim);text-decoration:none;font-family:var(--mono);
  font-variant-numeric:tabular-nums;}
.sr a.jump:hover{color:var(--accent);}
.sr a:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px;}
/* :target — the card you just jumped to, so the landing is not a guess. */
.sr .card:target{box-shadow:0 0 0 2px var(--accent);}

/* preview: fixed box so a missing one never shifts anything.

   THE TRAP THIS BOX USED TO FALL INTO, kept written down because the element type is the only
   thing that defuses it: the Artifact skeleton wraps this fragment in its own reset, which
   carries `img{max-width:100%}`. Inside an auto-layout table that drops a preview's min-content
   contribution to ~0, so a width-1% cell — which asks for the narrowest column that still fits
   the picture — squeezed it down to a sliver. Invisible locally (the fragment has no reset),
   wrong once published, which is the only place this page is read. A div is out of that
   selector's reach; make the preview an image element again and `max-width:none` becomes
   load-bearing again. The test enforces exactly that conditional, not the property.
   (Spelled out rather than written as a tag: this comment ships inside the page, and a literal
   one here would read as markup to every substring check in the tests.)

   The size comes from CSS off one element type, and the per-video rule supplies aspect-ratio —
   see _thumb_css_of for why it must. */
.sr .thumb{display:block;width:160px;border-radius:4px;aspect-ratio:16/9;
  background:var(--none-bg) center/cover no-repeat;}
.sr .cardhead .thumb{width:84px;margin:0;border-radius:3px;}
@media (max-width:640px){.sr .thumb{width:100px;}}
.sr p.why{font-family:var(--ui);font-size:.92rem;color:var(--dim);margin:0 0 10px;
  padding-left:10px;border-left:2px solid var(--line);max-width:66ch;}
.sr .line{color:var(--dim);}
.sr p.line{margin:0 0 10px;font-size:.92rem;max-width:66ch;}

/* state chip: colour AND text, never colour alone */
.sr .chip{display:inline-block;white-space:nowrap;font-size:.76rem;font-weight:640;
  letter-spacing:.02em;padding:3px 9px;border-radius:999px;}
.sr .v-none{background:var(--none-bg);color:var(--dim);}
/* dub verdict chips: triage borrows the skip palette, clean the watch one, so red/green carries
   exactly one meaning here */
.sr .t-triage{background:var(--skip-bg);color:var(--skip);}
.sr .t-clean{background:var(--watch-bg);color:var(--watch);}

/* triage nav: the morning-listen entry points, an index instead of a re-sort */
.sr .nav{margin-top:14px;padding:10px 14px;border:1px solid var(--line);border-radius:8px;
  background:var(--card);font-size:.92rem;}
.sr .nav .lbl{color:var(--dim);margin-right:6px;}
.sr .nav a{color:var(--accent);text-decoration:none;}
.sr .nav a:hover{text-decoration:underline;}

/* cards: the severity stripe encodes the same verdict the chip states.
   The BOX is capped, not just the text inside it. The page is 1240px for the dub table's
   columns; a card stretched to that width around a 66ch paragraph is mostly empty right-hand
   side, which reads as a rendering fault rather than as a measure. */
.sr .card{background:var(--card);border:1px solid var(--line);border-radius:8px;
  border-left:3px solid var(--line);padding:16px 18px;max-width:62rem;}
.sr .card.t-triage{border-left-color:var(--skip);}
.sr .card.t-clean{border-left-color:var(--watch);}
/* the card's header line: bigger type against a smaller preview, so number, title and runtime
   carry the row rather than the thumbnail dwarfing all three */
.sr .cardhead{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:10px;}
.sr .cardhead .idx{font-size:1.15rem;}
.sr .cardhead .name{font-size:1.3rem;font-weight:600;}
.sr .cardhead .num{font-size:1.05rem;}
.sr .card p{font-family:var(--read);font-size:1rem;line-height:1.68;margin:0;
  max-width:66ch;color:var(--ink);}
.sr .card p + p{margin-top:1.1em;}

/* dub components: the rollup and unit meta are data → mono; prose stays serif via .card p */
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


# base64's whole alphabet, and nothing that could close a CSS url() or open a comment. The bytes
# are ours (base64 of a file we wrote), so this is belt-and-braces rather than a live threat --
# but a data URI goes into a <style> block now, where a stray ')' would end the rule and leave
# the rest of the page as garbage CSS instead of a missing picture.
_B64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")


def _thumb_box(e: dict) -> str:
    """The preview ELEMENT — a div painted by a per-video CSS rule, not an <img>.

    Why not <img>: a data-URI in a src is the bytes themselves, not a reference to them, and a
    CSS rule is declared once and applies to as many elements as carry the class, so the bytes
    land in the page exactly once however often the preview renders.

    The cost, accepted deliberately: loading="lazy" is an <img> attribute and has no background
    equivalent, so every preview decodes at load instead of on scroll.

    Absent preview renders nothing: the card still carries title, state and a link, and an
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
    # 16/9 is the fallback, not the assumption: ffmpeg scales to THUMB_W with a derived height,
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
    (queue_ids' regex guarantees the shape), so the URL is built, never taken from the artifact.
    An unfinished row still links: the whole point of that row is to go look at the thing."""
    href = f"https://www.youtube.com/watch?v={e['vid']}"
    return (f'<a class="ext" href="{html.escape(href)}" target="_blank" rel="noopener">'
            f'{html.escape(e["title"])}</a>')


# --- the dub layer moved out (2026-07-22) ---------------------------------------
# `_audio_src`, `_badges`, `_fmt_span`, `_unit_html`, `_srcanom_html` and `_dub_table` live
# in `scripts/dub_blocks.py`, re-bound below: everything that renders what a DUBBED video
# earned. What stays here is states, previews, cards and page assembly. dub_blocks must never
# import back — the temptation is `_title_link`, and the batch table deliberately links by
# video id instead.
_unit_html = dub_blocks.unit_html
_srcanom_html = dub_blocks.srcanom_html
_dub_table = dub_blocks.dub_table


def _chip(d: dict) -> str:
    return f'<span class="chip {d["cls"]}">{html.escape(d["label"])}</span>'


def _card(e: dict, out_dir: Path, *, embed: bool) -> str:
    """One card, whatever the workdir has earned. The invariant: a card NEVER fabricates dub
    metrics for a non-run kind — no RTF, no audio, no triage/clean chip."""
    v = e["v"]
    chips = []
    if e.get("dub"):
        chips.append(_chip(e["dub"]))
    if not chips:
        # A pipeline STATE is news and wears a chip. A torn rollup lands here too and keeps its
        # «без свода» chip — v is _NO_ROLLUP only when run.json failed to build, which is
        # exactly when there is no dub verdict to sit beside it.
        chips.append(_chip(v))

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
        row = queueview.batch_row(run)
        c = dict(row["cells"])
        sp = run.get("speed", {}) or {}
        # The rollup REUSES batch_row's cell strings (cp/adv are the actionable/advisory split —
        # never n_flagged: printing the pooled count here while the digest prints the split was
        # the original two-numbers-one-batch bug). med/p95 are card-only depth the
        # table deliberately omits, read off the same run.json.
        n_sent = (run.get("translate", {}) or {}).get("n_sentences", 0)
        rollup = (f"translate {c['tr']}/{n_sent}"
                  f" · verify {c['vf']} · completeness {c['cp']} (+{c['adv']} advisory)"
                  f" · speed med {sp.get('median')}/p95 {sp.get('p95')}/max {c['spd_max']}"
                  f" (n>1.8 {c['n_over']})")
        out.append(f'<p class="rollup">{html.escape(rollup)}</p>')
        out.append(_srcanom_html(run))
        if e["units"]:
            out.extend(_unit_html(u, e["work"].seg_wav(u.get("lead")), out_dir, embed=embed)
                       for u in e["units"])
        else:
            out.append('<p class="line">проблемных юнитов нет — слушать нечего.</p>')
    elif e["kind"] in ("pending", "transcribed"):
        out.append(f'<p class="why">{html.escape(v["why"])}</p>')
        out.append(_meta_line(e))
    else:
        # missing / fetched / run-without-rollup: the state is the whole story
        out.append(f'<p class="why">{html.escape(v["why"])}</p>')
    out.append("</article>")
    return "".join(out)


def _meta_line(e: dict) -> str:
    """Sentence count for a transcript-only card. Cost is the point: whether a video earns a dub
    is a question about length, and an EMPTY transcript ("предложений: 0") is a real answer —
    transcribe ran and found nothing — never a reason to drop the card."""
    n = e.get("n_sentences")
    return f'<p class="line">предложений: {n}</p>' if n is not None else ""


def render(entries: list[dict], queue_name: str | None, stamp: str,
           playlist: dict | None = None, *, out_dir: Path | None = None,
           embed: bool = True) -> str:
    # The counts are PIPELINE STATES, not verdicts. Each unfinished state is counted under its
    # OWN name: "не скачано: 3" hiding a failed transcribe would send the operator at the wrong
    # fix.
    tally_bits = []
    for state in (_TRANSCRIBED, _NOT_DOWNLOADED, _NOT_TRANSCRIBED, _NO_ROLLUP):
        n = sum(1 for e in entries if e["v"] is state)
        if n:
            tally_bits.append(f'{state["label"]}: {n}')
    n_pending = sum(1 for e in entries if e["kind"] == "pending")
    if n_pending:
        tally_bits.append(f'{_PENDING["label"]}: {n_pending}')
    dubs = [e for e in entries if e["kind"] == "run" and e["run"] is not None]
    n_triage = sum(1 for e in dubs if e["run"].get("needs_triage"))
    if dubs:
        tally_bits.append(f'слушать: {n_triage}')
        tally_bits.append(f'чисто: {len(dubs) - n_triage}')
    tally = " · ".join(tally_bits)

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
    if tally:
        out.append(f'<p class="sub">{html.escape(tally)}</p>')
    if dubs:
        # dub totals from the shared layer — the same numbers the digest's totals line prints
        tot = queueview.batch_totals([e["run"] for e in dubs])
        # H/M and a name for what the number IS. «wall 11778.0s» said neither (operator report
        # 2026-07-25): five digits of seconds is not a duration, and the figure is work SUMMED per
        # video — the route-B translate wave between transcribe and synthesize is outside every
        # stage timer, so it is always smaller than the night the operator actually spent.
        out.append(f'<p class="sub">{len(dubs)} видео · работа пайплайна '
                   f'{queueview.format_dur(tot["total_wall"], ru=True)} '
                   f'(сумма по видео, не время прогона) · '
                   f'throughput {tot["throughput"]} · '
                   f'{tot["n_triage"]} требуют прослушивания</p>')
        # The batch stage split — what to optimise, in the one place that sees the whole batch.
        # Per-video shares cannot answer it (one long video dominates its own row and nothing else),
        # which is why this is a batch-level line and not a column.
        if tot["stages"]:
            out.append('<p class="sub">этапы: ' + ' · '.join(
                f'{html.escape(name)} {queueview.format_dur(sec, ru=True)} {pct}%'
                for name, sec, pct in tot["stages"]) + '</p>')
    out.append("</header>")

    if n_triage:
        # The morning-listen job, served by NAVIGATION instead of by re-sorting the queue: the
        # worst videos get anchors, the queue keeps its order.
        links = " · ".join(
            f'<a href="#v{e["n"]}">{e["n"]} — {html.escape((e["title"] or e["vid"])[:40])}</a>'
            for e in dubs if e["run"].get("needs_triage"))
        out.append(f'<div class="nav"><span class="lbl">Требуют прослушивания:</span> '
                   f'{links}</div>')

    if dubs:
        out.append('<section class="sec"><div class="sechead"><h2>Дубляж</h2>'
                   '<p class="sub">Те же ячейки, что печатает текстовый дайджест — цифры '
                   'совпадают по построению.</p></div>')
        out.append(_dub_table(dubs))
        out.append("</section>")

    out.append('<section class="sec"><div class="sechead"><h2>Подробно</h2>'
               '<p class="sub">В порядке очереди — так же, как в плейлисте; карточка на видео.'
               '</p></div>')
    out.extend(_card(e, out_dir or Path("."), embed=embed) for e in entries)
    out.append("</section>")

    out.append('<p class="foot">overdub · очередь · состояние каждого видео и что в дубляже '
               'требует прослушивания.</p>')
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
    workdir is; this resolves how it LOOKS: which state leads the row (dub state > pipeline
    state), and which title/duration ladder applies."""
    views = []
    for e in entries:
        work, kind, run = e["work"], e["kind"], e["run"]
        dub = None
        if kind == "run" and run is not None:
            dub = _DUB_TRIAGE if run.get("needs_triage") else _DUB_CLEAN
        if kind == "run" and run is None:
            v = _NO_ROLLUP
        elif dub:
            v = dub
        elif kind == "pending":
            v = _PENDING
        elif kind == "transcribed":
            v = _TRANSCRIBED
        elif kind == "fetched":
            v = _NOT_TRANSCRIBED
        else:
            v = _NOT_DOWNLOADED
        # A title may exist even when nothing else does: the info.json sidecar lands before the
        # media on a partial fetch. Showing it beats a bare id for a row whose job is action.
        info = _load_json(work.info_json)
        info_title = info.get("title") if isinstance(info, dict) else None
        title = (run or {}).get("title") or info_title or e["vid"]
        # duration ladder: the run's measured video_sec first, then the collector's fallback
        duration = None
        if run is not None:
            duration = (run.get("timings", {}) or {}).get("video_sec")
        if duration is None:
            duration = e.get("duration_sec")
        views.append({
            "n": e["n"], "vid": e["vid"], "work": work, "kind": kind, "v": v,
            "dub": dub, "run": run, "units": e["units"],
            "thumb_b64": _thumb_b64(work.root / "thumb.jpg"),
            "thumb_wh": jpeg_size(work.root / "thumb.jpg"),
            "title": title, "duration": duration,
            "n_sentences": e.get("n_sentences"),
        })
    return views


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="queue_report",
        description="Render the queue report (dub triage, queue order) as publishable HTML.")
    p.add_argument("workdirs", nargs="*", type=Path, metavar="work/<id>",
                   help="per-video work dirs (appended after the queue)")
    p.add_argument("--queue", type=Path, default=None,
                   help="queue file — ALSO the report's row order")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"))
    p.add_argument("--out", type=Path, default=None,
                   help="output path (default: <work_root>/queue-report.html)")
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

    entries_raw, skipped = queueview.collect_entries(
        queue, args.workdirs, cfg.work_root, limit=args.limit, cfg=cfg)
    if not entries_raw:
        # argv paths that are neither a run nor a transcript: named, never a silent empty page
        print("[queue-report] nothing to render — "
              f"skipped (nothing to report): {', '.join(skipped) or '(none)'}")
        return 0
    entries = _views(entries_raw)

    out_path = args.out or (cfg.work_root / "queue-report.html")
    out_dir = out_path.resolve().parent
    embed = not args.link
    stamp = time.strftime("%Y-%m-%d %H:%M")
    page = render(entries,
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
                  for s in (_NOT_DOWNLOADED, _NOT_TRANSCRIBED, _NO_ROLLUP)]
    n_pending = sum(1 for e in entries if e["kind"] == "pending")
    if n_pending:
        unfinished.append((_PENDING, n_pending))
    unfinished = [(s, n) for s, n in unfinished if n]
    note = "".join(f', {n} {s["label"]}' for s, n in unfinished)
    # dubbed videos counted apart from transcript-only ones: "0 need triage" out of a count that
    # includes never-dubbed videos would be a lie about them
    dubs = [e for e in entries if e["kind"] == "run" and e["run"] is not None]
    n_triage = sum(1 for e in dubs if e["run"].get("needs_triage"))
    n_transcribed = sum(1 for e in entries if e["kind"] == "transcribed")
    n_units = sum(len(e["units"]) for e in entries)
    print(f"[queue-report] {out_path}  ({len(dubs)} video(s), "
          + (f"{n_transcribed} transcript-only, " if n_transcribed else "")
          + f"{n_triage} need triage, {n_units} flagged unit(s), "
          + ("embedded" if embed else "linked") + f" audio{note})")
    for s, n in unfinished:
        print(f'[queue-report] {n} × "{s["label"]}" — {s["why"]}')
    if skipped:
        print(f"[queue-report] skipped (nothing to report): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
