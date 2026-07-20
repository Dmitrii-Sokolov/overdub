"""Morning-triage HTML: one at-a-glance batch page with inline audio players.

Built ON TOP of the same per-run data the text digest surfaces (run.json + report.json +
translation.json), this renders a single self-contained HTML file: a batch table (which videos
need a listen) plus, per flagged render unit, its reasons, the EN/RU text, the ASR similarity +
what whisper heard back (the verify-triage payload), and an <audio> player for the unit's raw
TTS wav (`segments/<lead>.wav`). Open it after an overnight batch, listen to the flagged units,
done — no grepping report.json.

Audio, two modes:
  - DEFAULT (embed): each flagged unit's wav is base64-inlined as a data: URI, so every player is
    guaranteed to play and the page is portable (move it, share it). Only FLAGGED units are
    embedded (triage = a small fraction of a run), so the page stays a few MB, not gigabytes.
  - --link: reference the wavs by relative path instead (tiny page, zero copy) — but then the HTML
    must stay next to work/ so `<id>/segments/<lead>.wav` resolves under file://.

Read-only, no model / no GPU / no network (one best-effort ffprobe via build_run_report at most).
A work dir with no readable run.json is a skipped note, never a crash.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\triage_html.py --queue queue.txt
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\triage_html.py work\\<id> --out triage.html --link
"""

from __future__ import annotations

import argparse
import base64
import datetime
import html
import json
import os
import re
import sys
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub import runreport                              # noqa: E402
from overdub.config import Config                          # noqa: E402
from overdub.workdir import WorkDir                        # noqa: E402

_YT_ID = re.compile(r"(?:v=|/shorts/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})")


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _queue_ids(path: Path) -> list[str]:
    ids: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _YT_ID.search(line)
        if m:
            ids.append(m.group(1))
    return ids


# --- audio ---------------------------------------------------------------------
def _audio_src(wav: Path, out_dir: Path, *, embed: bool) -> str | None:
    """A value for <audio src=...>: a base64 data: URI (embed) or a relative path (link). None
    when the wav is missing/unreadable — the caller renders a 'no audio' note instead of a broken
    player. Only ever called for FLAGGED units, so embed size stays bounded."""
    if not wav.exists():
        return None
    if not embed:
        rel = os.path.relpath(str(wav), str(out_dir))
        return rel.replace(os.sep, "/")
    try:
        b = wav.read_bytes()
    except OSError:
        return None
    return "data:audio/wav;base64," + base64.b64encode(b).decode("ascii")


# --- rendering (pure string assembly) -----------------------------------------
_CSS = """
:root{color-scheme:light dark;--bg:#fbfbfd;--fg:#1a1a1e;--muted:#6b6b76;--card:#fff;
--line:#e5e5ea;--en:#3a5bd9;--ru:#1a1a1e;--triage:#c0392b;--clean:#1f9d55;
--b-verify:#d98c00;--b-speed:#c0392b;--b-complete:#8e44ad;--b-translate:#d35400;--b-assemble:#555;
--b-src:#0b7285}
@media (prefers-color-scheme:dark){:root{--bg:#131316;--fg:#e7e7ea;--muted:#9a9aa4;--card:#1c1c21;
--line:#2c2c33;--en:#7aa2ff;--ru:#e7e7ea;--triage:#ff6b5e;--clean:#4ad07d}}
*{box-sizing:border-box}
body{margin:0;padding:24px;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
h1{font-size:20px;margin:0 0 4px}h2{font-size:17px;margin:0 0 8px}
.meta{color:var(--muted);font-size:13px;margin:0 0 20px}
table{border-collapse:collapse;width:100%;font-size:13px;margin-bottom:28px;overflow-x:auto;display:block}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600}
td.yes{color:var(--triage);font-weight:600}td.no{color:var(--clean)}
a{color:var(--en);text-decoration:none}a:hover{text-decoration:underline}
.video{margin:0 0 32px;padding-top:8px;border-top:2px solid var(--line)}
.tag{display:inline-block;font-size:11px;font-weight:700;padding:1px 7px;border-radius:9px;
color:#fff;vertical-align:middle;margin-left:6px}
.tag.triage{background:var(--triage)}.tag.clean{background:var(--clean)}
.rollup{color:var(--muted);font-size:13px;margin:0 0 14px}
.summary{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--en);
border-radius:0 8px 8px 0;padding:10px 14px;margin:0 0 16px;font-size:14px;line-height:1.55}
.summary p{margin:0 0 8px}.summary p:last-child{margin:0}
.unit{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 12px}
.reasons{margin-bottom:6px}
.badge{display:inline-block;font-size:11px;font-weight:600;padding:1px 7px;border-radius:6px;
color:#fff;margin:0 5px 4px 0}
.badge.verify{background:var(--b-verify)}.badge.speed{background:var(--b-speed)}
.badge.complete{background:var(--b-complete)}.badge.translate{background:var(--b-translate)}
.badge.assemble{background:var(--b-assemble)}
.uid{color:var(--muted);font-size:12px;margin-bottom:8px}
.en{color:var(--en);display:block;margin-bottom:2px}.ru{color:var(--ru);display:block}
.asr{font-size:12.5px;color:var(--muted);margin-top:8px;padding:6px 8px;border-left:3px solid var(--b-verify);
background:color-mix(in srgb,var(--b-verify) 8%,transparent);border-radius:0 6px 6px 0}
.asr b{color:var(--fg);font-weight:600}
audio{width:100%;margin-top:10px;height:34px}
.noaudio{display:inline-block;margin-top:10px;font-size:12px;color:var(--triage)}
.clean-list{color:var(--muted);font-size:13px}
.srcanom{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--b-src);
border-radius:0 8px 8px 0;padding:10px 14px;margin:0 0 16px;font-size:13.5px}
.srcanom .lbl{color:var(--muted);font-size:12px;margin:0 0 6px;text-transform:uppercase;
letter-spacing:.04em}
.srcanom ul{margin:0;padding-left:18px}.srcanom li{margin-bottom:6px}
.srcanom .k{color:var(--b-src);font-weight:600}
.srcanom .en{color:var(--en);display:block;font-size:12.5px}
.badge.src{background:var(--b-src)}
"""


def _badges(reasons: list[str]) -> str:
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
    ids = u.get("ids") or []
    span = _fmt_span(u.get("start"), u.get("end"))
    sp = u.get("speed")
    sim = u.get("similarity")
    parts = [f'#{u.get("lead")}', f'ids {ids}', span]
    if sp is not None:
        parts.append(f'speed ×{sp}')
    if sim is not None:
        parts.append(f'sim {sim}')
    meta = " · ".join(html.escape(str(p)) for p in parts)

    lines = ['<div class="unit">',
             f'  <div class="reasons">{_badges(u.get("reasons") or [])}</div>',
             f'  <div class="uid">{meta}</div>',
             '  <div class="text">']
    if u.get("src_en"):
        lines.append(f'    <span class="en">EN: {html.escape(u["src_en"])}</span>')
    if u.get("text_ru"):
        lines.append(f'    <span class="ru">RU: {html.escape(u["text_ru"])}</span>')
    lines.append('  </div>')
    # verify triage: what the round-trip EXPECTED vs what whisper HEARD back
    if u.get("hypothesis") is not None and any(r.startswith("verify:") for r in (u.get("reasons") or [])):
        exp = html.escape(u.get("text_tts") or "")
        heard = html.escape(u.get("hypothesis") or "")
        lines.append(f'  <div class="asr"><b>expected:</b> {exp}<br><b>heard:</b> {heard}</div>')
    src = _audio_src(wav, out_dir, embed=embed)
    if src is not None:
        lines.append(f'  <audio controls preload="none" src="{src}"></audio>')
    else:
        lines.append('  <div class="noaudio">no audio (wav missing)</div>')
    lines.append('</div>')
    return "\n".join(lines)


def _video_html(run: dict, units: list[dict], work: WorkDir, out_dir: Path, *,
                embed: bool, summary: str | None = None) -> str:
    vid = run.get("video_id")
    title = run.get("title")
    triage = bool(run.get("needs_triage"))
    tag = '<span class="tag triage">TRIAGE</span>' if triage else '<span class="tag clean">clean</span>'
    head = html.escape(str(vid)) + (f' — {html.escape(title)}' if title else '')
    t = run.get("timings", {}) or {}
    sp = run.get("speed", {}) or {}
    tr = run.get("translate", {}) or {}
    v = run.get("verify", {}) or {}
    c = run.get("completeness", {}) or {}
    rtf = t.get("rtf")
    rollup = (f'RTF {rtf if rtf is not None else "n/a"} ({html.escape(str(t.get("video_sec_source")))})'
              f' · wall {t.get("total_wall_s", 0)}s · flags: translate {tr.get("n_failed", 0)}/'
              f'{tr.get("n_sentences", 0)} · verify {v.get("n_flagged", 0)} · completeness '
              f'{c.get("n_flagged", 0)} · speed med {sp.get("median")}/p95 {sp.get("p95")}/max '
              f'{sp.get("max")} (n&gt;1.8 {sp.get("n_over_1_8", 0)})')
    out = [f'<section class="video" id="v-{html.escape(str(vid))}">',
           f'  <h2>{head} {tag}</h2>',
           f'  <p class="rollup">{rollup}</p>']
    if summary:
        # summary.md is Markdown but this page has no markdown renderer (none is offline-safe to
        # add). runreport.read_summary already stripped heading markers, so paragraphs are the only
        # structure left. Escape first — this is raw LLM prose going straight into HTML.
        paras = [html.escape(p.strip()).replace("\n", " ")
                 for p in summary.split("\n\n") if p.strip()]
        out.append('  <div class="summary">' + "".join(f"<p>{p}</p>" for p in paras) + '</div>')
    # Source anomalies (PLAN item 1) — content first, then defects. Rendered even when `units` is
    # empty: a pre-synthesis workdir is exactly when this signal is most actionable (--repair-asr
    # is still cheap there). Deliberately NO <audio> player, and deliberately not routed through
    # flagged_units: the defect is in the ENGLISH source, so listening to the Russian tells the
    # operator nothing. html.escape on every field — raw LLM prose into HTML, same rule as summary.
    s = run.get("source", {}) or {}
    items = s.get("items") or []
    if items:
        li = []
        for it in items:
            li.append(f'<li><b>#{html.escape(str(it.get("id")))}</b> '
                      f'<span class="k">{html.escape(str(it.get("kind")))}</span> — '
                      f'{html.escape(it.get("note") or "")}'
                      f'<span class="en">EN: {html.escape(it.get("src_en") or "")}</span></li>')
        out.append(f'  <div class="srcanom"><p class="lbl">source anomalies '
                   f'({len(items)}) — defect is in the ENGLISH source; no audio to check</p>'
                   f'<ul>{"".join(li)}</ul></div>')
    if units:
        for u in units:
            out.append(_unit_html(u, work.seg_wav(u.get("lead")), out_dir, embed=embed))
    else:
        out.append('  <p class="clean-list">no flagged units — nothing to listen to.</p>')
    out.append('</section>')
    return "\n".join(out)


def _batch_table(runs: list[dict]) -> str:
    head = ("video", "title", "RTF", "wall", "tr", "vf", "cp", "src", "spd max", "&gt;1.8",
            "status")
    rows = ["<tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>"]
    for r in runs:
        t = r.get("timings", {}) or {}
        sp = r.get("speed", {}) or {}
        triage = bool(r.get("needs_triage"))
        vid = html.escape(str(r.get("video_id")))
        cells = [
            f'<a href="#v-{vid}">{vid}</a>',
            html.escape((r.get("title") or "")[:40]),
            html.escape(str(t.get("rtf"))),
            html.escape(str(t.get("total_wall_s", ""))),
            str((r.get("translate", {}) or {}).get("n_failed", 0)),
            str((r.get("verify", {}) or {}).get("n_flagged", 0)),
            str((r.get("completeness", {}) or {}).get("n_flagged", 0)),
            # src: advisory source-anomaly count. "-" means NOT SCANNED (route A, or a
            # pre-schema run.json) -- never conflate that with a scanned-and-clean "0".
            # --rebuild backfills the block for runs that predate it.
            (str((r.get("source", {}) or {}).get("n_flagged", 0))
             if (r.get("source", {}) or {}).get("scanned") else "-"),
            html.escape(str(sp.get("max"))),
            str(sp.get("n_over_1_8", 0)),
            '<span>needs triage</span>' if triage else '<span>clean</span>',
        ]
        cls = ' class="yes"' if triage else ' class="no"'
        status_i = len(cells) - 1              # the triage cell is always last — index, never a
        tds = "".join(f"<td>{cells[0]}</td>" if i == 0     # hardcoded number that a new column
                      else (f"<td{cls}>{cells[i]}</td>"    # would silently mis-colour
                            if i == status_i else f"<td>{cells[i]}</td>")
                      for i in range(len(cells)))
        rows.append(f"<tr>{tds}</tr>")
    return "<table>\n" + "\n".join(rows) + "\n</table>"


def render_page(entries: list[dict], out_dir: Path, *, embed: bool) -> str:
    """entries: [{run, units, work, summary}]. Videos needing triage sort first. Pure string assembly."""
    entries = sorted(entries, key=lambda e: (not e["run"].get("needs_triage"),
                                             str(e["run"].get("video_id"))))
    runs = [e["run"] for e in entries]
    n_triage = sum(1 for r in runs if r.get("needs_triage"))
    total_wall = round(sum((r.get("timings", {}) or {}).get("total_wall_s", 0) or 0 for r in runs), 1)
    sum_video = sum(((r.get("timings", {}) or {}).get("video_sec") or 0) for r in runs)
    thru = f"×{sum_video / total_wall:.2f}" if total_wall > 0 else "n/a"
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    meta = (f"generated {ts} · {len(runs)} video(s) · {n_triage} need triage · "
            f"total wall {total_wall}s · throughput {thru}"
            + ("" if embed else " · audio: relative links (keep this file next to work/)"))

    body = [_batch_table(runs)] if runs else []
    for e in entries:
        body.append(_video_html(e["run"], e["units"], e["work"], out_dir,
                                embed=embed, summary=e.get("summary")))

    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>overdub — morning triage</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        "<h1>overdub — morning triage</h1>\n"
        f'<p class="meta">{html.escape(meta)}</p>\n'
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="triage_html",
        description="Morning-triage HTML: flagged units with inline audio, one page per batch.")
    p.add_argument("workdirs", nargs="*", type=Path, metavar="work/<id>",
                   help="per-video work dirs")
    p.add_argument("--queue", type=Path, default=None,
                   help="queue file of URLs (ids → <work_root>/<id>)")
    p.add_argument("--out", type=Path, default=None,
                   help="output HTML path (default: <work_root>/triage.html)")
    p.add_argument("--link", action="store_true",
                   help="reference wavs by relative path instead of embedding (smaller page; the "
                        "HTML must then stay next to work/)")
    p.add_argument("--limit", type=int, default=500,
                   help="max flagged units rendered per video (default 500)")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"),
                   help="TOML config (for work_root); built-in defaults if absent")
    args = p.parse_args(argv)

    cfg = Config.load(args.config)
    out_path = args.out or (cfg.work_root / "triage.html")
    out_dir = out_path.resolve().parent
    embed = not args.link

    dirs: list[Path] = []
    seen: set[str] = set()

    def add(d: Path) -> None:
        key = os.path.normcase(os.path.abspath(str(d)))
        if key not in seen:
            seen.add(key)
            dirs.append(d)

    for wd in args.workdirs:
        add(wd)
    if args.queue is not None:
        if not args.queue.is_file():
            p.error(f"queue file not found: {args.queue}")
        for vid in _queue_ids(args.queue):
            add(cfg.work_root / vid)
    if not dirs:
        p.error("give at least one work/<id> dir and/or --queue FILE")

    entries: list[dict] = []
    skipped: list[str] = []
    for d in dirs:
        work = WorkDir(d)
        run = _load_json(work.root / "run.json")
        if run is None:
            run = runreport.build_run_report(work, cfg)
        if run is None:
            skipped.append(d.name)
            continue
        report = _load_json(work.report)
        translation = _load_json(work.translation)
        units = runreport.flagged_units(report, translation, args.limit) if report else []
        entries.append({"run": run, "units": units, "work": work,
                        "summary": runreport.read_summary(work)})

    if not entries:
        print(f"[triage] nothing to render — no readable run.json in: {', '.join(skipped) or '(none)'}",
              file=sys.stderr)
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(render_page(entries, out_dir, embed=embed), encoding="utf-8")
    os.replace(tmp, out_path)

    n_triage = sum(1 for e in entries if e["run"].get("needs_triage"))
    n_units = sum(len(e["units"]) for e in entries)
    print(f"[triage] {out_path}  ({len(entries)} video(s), {n_triage} need triage, "
          f"{n_units} flagged unit(s){', embedded audio' if embed else ', linked audio'})")
    if skipped:
        print(f"[triage] skipped (no run.json): {', '.join(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
