"""The dub layer's HTML blocks: flagged-unit players, the source-anomaly list, the batch table.

Split out of scripts/scout_report.py on 2026-07-22. These six functions came in as a group when
the retired triage page was merged into the scout report (2026-07-21) and they still are one:
everything here renders what a DUBBED video earned — its flagged units with audio, the anomalies
found in its English source, its row in the batch table. Nothing here knows about grades,
previews, cards or page assembly, which is what stayed behind.

The dependency is one-way and must stay so: scout_report imports this, this imports nothing from
scout_report. The temptation to reach back is `_title_link` — do not; `_dub_table` links by video
id on purpose, since the batch table's first column IS the id (the digest prints the same one).

`queueview.BATCH_COLUMNS` / `batch_row` are imported directly rather than passed in: they are the
cross-surface contract, and routing them through an argument would let a caller substitute a
different column set, which is exactly the divergence the merge exists to prevent.
"""

from __future__ import annotations

import base64
import html
import os
from pathlib import Path

# `overdub` resolves because the importing script (scout_report.py) puts the repo root on
# sys.path before importing this module — the same preamble every script in this directory has.
from overdub import queueview


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


def unit_html(u: dict, wav: Path, out_dir: Path, *, embed: bool) -> str:
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


def srcanom_html(run: dict) -> str:
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


def dub_table(dubs: list[dict]) -> str:
    """The dub batch table. Header labels come from queueview.BATCH_COLUMNS and the ten data
    cells are printed VERBATIM from batch_row(run)["cells"] — the same strings the text digest
    prints, so the two surfaces can never again disagree about the same run. The
    cell vocabulary is machine-formatted numbers ("123.4", "n/a", "-", "3.4%"), no HTML-active
    characters by construction, hence no escape on them."""
    ths = "".join(f"<th>{html.escape(label)}</th>" for _key, label in queueview.BATCH_COLUMNS)
    rows = [f"<thead><tr>{ths}</tr></thead>", "<tbody>"]
    for e in dubs:
        row = queueview.batch_row(e["run"])
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
                # silently — adding a column here cannot mis-colour anything
                tds.append(f'<td class="{"t-triage" if needs else "t-clean"}">{val}</td>')
            elif key in ("video", "title"):
                tds.append(f"<td>{val}</td>")
            else:
                tds.append(f'<td class="num">{val}</td>')
        rows.append(f"<tr>{''.join(tds)}</tr>")
    rows.append("</tbody>")
    return f'<div class="wrap"><table>{"".join(rows)}</table></div>'
