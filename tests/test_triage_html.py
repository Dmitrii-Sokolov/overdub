"""Unit tests for scripts/triage_html.py — the summary block's escaping and its optional-ness.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_triage_html.py   (or via pytest)
Pure string assembly, no GPU / no network / no media: _video_html and render_page are fed a
run-shaped dict and a WorkDir over a tmp path, and nothing here reaches a wav. The load-bearing
invariants are that a MISSING summary renders no block at all (the summary is informational — it
gates nothing, so its absence is the normal case, PLAN item 3) and that the prose, which is raw
LLM output going straight into HTML, is escaped before it lands on the page.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import triage_html  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402


def _run(vid="vid00000001") -> dict:
    """A run dict carrying only the keys _video_html touches. The id is exactly 11 chars — the
    shape workdir.video_id produces, so nothing falls through to its url-hash branch."""
    return {
        "video_id": vid, "title": "Demo", "needs_triage": False,
        "timings": {"rtf": 0.5, "total_wall_s": 10.0, "video_sec_source": "info_json"},
        "speed": {"median": 1.0, "p95": 1.1, "max": 1.2, "n_over_1_8": 0},
        "translate": {"n_failed": 0, "n_sentences": 4},
        "verify": {"n_flagged": 0},
        "completeness": {"n_flagged": 0},
    }


# --- the summary block is OPTIONAL -------------------------------------------
def test_summary_absent_renders_no_block() -> None:
    # A video with no summary.md is the normal case, not an error — the page must render exactly
    # as it did before item 3, with no empty container left behind.
    with tempfile.TemporaryDirectory() as d:
        out = triage_html._video_html(_run(), [], WorkDir(Path(d)), Path(d), embed=False)
        assert 'class="summary"' not in out
        assert 'class="rollup"' in out                 # the rest of the video block is untouched


def test_summary_escaped_and_paragraphed() -> None:
    # Raw LLM prose going into HTML: unescaped, a stray tag would break the page (or worse).
    # Blank lines are the only structure read_summary leaves, so they become <p> boundaries.
    with tempfile.TemporaryDirectory() as d:
        out = triage_html._video_html(_run(), [], WorkDir(Path(d)), Path(d), embed=False,
                                      summary="Первый <b>абзац</b>.\n\nВторой & третий.")
        block = out.split('<div class="summary">', 1)[1].split("</div>", 1)[0]
        assert "&lt;b&gt;" in block and "&amp;" in block
        assert "<b>" not in block                      # never the live tag
        assert block.count("<p>") == 2                 # two paragraphs, not one blob


def test_render_page_passes_summary_through() -> None:
    # render_page reads the key with .get, so an entries dict built without it (a future scout-page
    # caller) must still render rather than KeyError.
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d))
        with_key = triage_html.render_page(
            [{"run": _run(), "units": [], "work": work, "summary": "Стоит смотреть."}],
            Path(d), embed=False)
        assert "Стоит смотреть." in with_key
        without_key = triage_html.render_page(
            [{"run": _run(), "units": [], "work": work}], Path(d), embed=False)
        assert 'class="summary"' not in without_key


def test_main_reads_summary_md_off_the_workdir() -> None:
    # The ONLY call site of runreport.read_summary in this script is main(); everything above
    # passes `summary=` in by hand. Without this, deleting the "summary": read_summary(work)
    # key from main's entries dict makes item 3's output vanish from the page with the whole
    # suite still green.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = tmp / "vid00000001"
        (work / "segments").mkdir(parents=True)
        (work / "run.json").write_text(json.dumps(_run()), encoding="utf-8")
        (work / "summary.md").write_text("Стоит смотреть целиком.", encoding="utf-8")
        out = tmp / "triage.html"
        assert triage_html.main([str(work), "--out", str(out)]) == 0
        page = out.read_text(encoding="utf-8")
    assert "Стоит смотреть целиком." in page
    assert 'class="summary"' in page


# --- source anomalies (PLAN item 1) -------------------------------------------
# Deliberately NOT routed through flagged_units and deliberately player-less: the defect is in the
# ENGLISH source, so listening to the Russian tells the operator nothing. The load-bearing cases
# are that the section stays absent when there is nothing to report, that it renders in a
# PRE-SYNTHESIS workdir (units == [], which is exactly when --repair-asr is still cheap), and that
# the note — raw LLM prose — is escaped.
def _run_src(items, *, scanned=True):
    r = _run()
    r["source"] = {"scanned": scanned, "n_scanned": len(items), "n_flagged": len(items),
                   "by_type": {}, "items": items}
    return r


def test_source_absent_renders_no_block() -> None:
    with tempfile.TemporaryDirectory() as d:
        out = triage_html._video_html(_run(), [], WorkDir(Path(d)), Path(d), embed=False)
        assert "srcanom" not in out


def test_source_section_rendered_and_escaped() -> None:
    items = [{"id": 19, "kind": "truncated",
              "note": "ends <script>alert(1)</script> & mid-thought",
              "src_en": "Description goes beyond distinction."}]
    with tempfile.TemporaryDirectory() as d:
        out = triage_html._video_html(_run_src(items), [], WorkDir(Path(d)), Path(d), embed=False)
        block = out.split('<div class="srcanom">', 1)[1].split("</div>", 1)[0]
        assert "#19" in block and "truncated" in block
        assert "&lt;script&gt;" in block and "&amp;" in block
        assert "<script>" not in block
        assert "<audio" not in block          # no player, by design — nothing to listen to


def test_source_section_renders_without_units() -> None:
    # A pre-synthesis workdir has no flagged units at all; the section must still appear.
    items = [{"id": 3, "kind": "garbled", "note": "unintelligible", "src_en": "en 3"}]
    with tempfile.TemporaryDirectory() as d:
        out = triage_html._video_html(_run_src(items), [], WorkDir(Path(d)), Path(d), embed=False)
        assert "srcanom" in out
        assert "no flagged units" in out      # the clean-units note is untouched


def test_batch_table_src_dash_when_unscanned() -> None:
    # "-" means NOT SCANNED (route A / pre-schema); "0" means scanned AND clean. Conflating the
    # two would report a Gemma-route video as source-checked when nothing ever read it.
    unscanned = _run()
    unscanned["source"] = {"scanned": False, "n_scanned": 0, "n_flagged": 0,
                           "by_type": {}, "items": []}
    row = triage_html._batch_table([unscanned]).splitlines()[-2]
    assert "<td>-</td>" in row
    clean = _run_src([])
    assert "<td>0</td>" in triage_html._batch_table([clean]).splitlines()[-2]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all triage_html tests passed")
