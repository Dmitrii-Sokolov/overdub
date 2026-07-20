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


# --- source anomalies (DECISIONS 2026-07-19) ----------------------------------
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


# --- scout cards (DECISIONS 2026-07-20) ---------------------------------------
# A scout workdir has NO run.json by construction (runreport clears it when report.json and
# translation.json are both absent). Before scout mode that made the whole mode invisible here:
# build_run_report returned None, the dir went to `skipped`, and a PURE-scout batch printed
# "nothing to render" and wrote no file at all. The load-bearing invariants are that such a dir
# now renders as a CARD rather than vanishing, that the card fabricates no dub metrics it cannot
# have, that a dir with no sentences.json still lands in `skipped` (no silent nothing in EITHER
# direction), and that a zero-scout page is byte-identical to the pre-change output.

def _scout_workdir(tmp: Path, vid="vid00000002", *, n=431, summary=None, info=True,
                   sentences=True, ends=True) -> Path:
    work = tmp / vid
    (work / "segments").mkdir(parents=True)
    if sentences:
        # `ends` off = sentences with no numeric `end`, the only shape from which no duration at
        # all can be derived. Not reachable through `info` alone, which the duration tests need.
        (work / "sentences.json").write_text(json.dumps(
            [{"id": i, "text": f"s{i}", "start": float(i),
              **({"end": float(i) + 1.0} if ends else {})}
             for i in range(n)]), encoding="utf-8")
    if info:
        (work / "source.info.json").write_text(
            json.dumps({"title": "Scouted Talk", "duration": 2530.0}), encoding="utf-8")
    if summary is not None:
        (work / "summary.md").write_text(summary, encoding="utf-8")
    return work


def _main_out(argv) -> tuple[int, str]:
    """triage_html.main with stdout captured — no pytest here, so no capsys."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = triage_html.main(argv)
    return code, buf.getvalue()


def test_scout_workdir_renders_as_a_card_not_a_skip() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _scout_workdir(tmp, summary="Про трансформеры. Стоит дублировать.")
        out = tmp / "triage.html"
        code, log = _main_out([str(work), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "Стоит дублировать." in page
    assert "SCOUT" in page and "Scouted Talk" in page
    assert "431 sentences" in page and "42 min" in page
    assert "skipped (no run.json)" not in log


def test_page_renders_when_every_entry_is_a_scout_card() -> None:
    # Today this path wrote NO FILE AT ALL — "nothing to render", exit 0, silence.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        a = _scout_workdir(tmp, "vid00000002", summary="A")
        b = _scout_workdir(tmp, "vid00000003", summary="B")
        out = tmp / "triage.html"
        code, _ = _main_out([str(a), str(b), "--out", str(out)])
        assert code == 0
        assert out.exists()
        page = out.read_text(encoding="utf-8")
    assert "<table>" not in page                 # no batch table without a single dubbed run
    assert page.count('class="tag scout"') == 2
    assert "2 scouted" in page


def test_scout_card_fabricates_no_dub_metrics() -> None:
    # A scouted video has no RTF, no flags, no triage verdict. Rendering it as a table row of
    # "-" cells would read as a BROKEN DUB rather than as a different kind of run, and
    # borrowing the "clean" tag would report an undubbed video as verified.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _scout_workdir(tmp, summary="prose")
        out = tmp / "triage.html"
        _main_out([str(work), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    card = page.split('<section class="video"', 1)[1]
    for forbidden in ("<audio", "srcanom", "TRIAGE", "tag clean", "RTF", "<td>None</td>"):
        assert forbidden not in card, forbidden
    assert "<table>" not in page                 # and it never reaches the batch table


def test_scout_card_summary_is_escaped() -> None:
    # Raw LLM prose into HTML — the same rule the video block follows, via the shared helper.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _scout_workdir(tmp, summary="Опасно <script>alert(1)</script> & прочее")
        out = tmp / "triage.html"
        _main_out([str(work), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in page and "&amp;" in page
    assert "<script>" not in page


def test_scout_card_without_summary_says_so() -> None:
    # A transcribed-but-unsummarized video is a pipeline STATE, not an empty card.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _scout_workdir(tmp)               # no summary.md
        out = tmp / "triage.html"
        _main_out([str(work), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "no summary.md yet" in page
    assert 'class="summary"' not in page


def test_counters_exclude_scout_from_the_video_count() -> None:
    # "0 need triage" out of a count that includes never-dubbed videos is a lie about them.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        dubbed = tmp / "vid00000001"
        (dubbed / "segments").mkdir(parents=True)
        (dubbed / "run.json").write_text(json.dumps(_run()), encoding="utf-8")
        scout = _scout_workdir(tmp, "vid00000002", summary="s")
        out = tmp / "triage.html"
        code, log = _main_out([str(dubbed), str(scout), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "1 video(s), 1 scouted," in log
    assert "2 video(s)" not in log
    assert "1 video(s) · 1 scouted ·" in page
    assert "<table>" in page                     # the dubbed video still gets its table


def test_scout_clause_absent_when_no_scout_entries() -> None:
    # An ordinary batch's page and stdout must be byte-identical to the pre-change strings.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = tmp / "vid00000001"
        (work / "segments").mkdir(parents=True)
        (work / "run.json").write_text(json.dumps(_run()), encoding="utf-8")
        out = tmp / "triage.html"
        code, log = _main_out([str(work), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "scouted" not in log and "scouted" not in page
    assert "1 video(s), 0 need triage, 0 flagged unit(s)" in log
    assert "1 video(s) · 0 need triage · " in page


def test_workdir_with_no_sentences_is_still_skipped() -> None:
    # The other direction of "no silent nothing": an empty dir is a typo, not a scouted video.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _scout_workdir(tmp, sentences=False)
        out = tmp / "triage.html"
        code, log = _main_out([str(work), "--out", str(out)])
    assert code == 0
    assert "nothing to render" in log
    assert not out.exists()


def test_empty_sentences_renders_a_zero_card_not_a_skip() -> None:
    # The OTHER arm of "no silent nothing in EITHER direction", and the one the suite left
    # unpinned: a MISSING sentences.json is a typo'd path (skip), but an EMPTY one PARSED, so
    # transcribe RAN and found nothing. Reachable, not hypothetical: resegment([]) returns []
    # and TranscribeStage.run writes it unconditionally, so any speech-free video (music,
    # silence) lands here under vad_filter=True — and scout mode, a cheap pass over an unvetted
    # queue, is exactly where such a video turns up. Without this test, tightening the list
    # guard to `or not sents` keeps the suite green while re-filing a speech-free video as a
    # mistyped path — "nothing in this video" is a real promotion answer (don't dub it).
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _scout_workdir(tmp, n=0, summary="Пустой транскрипт.")
        out = tmp / "triage.html"
        code, log = _main_out([str(work), "--out", str(out)])
        assert code == 0
        assert out.exists()                      # NOT the "nothing to render" path
        page = out.read_text(encoding="utf-8")
    assert "0 sentences" in page                 # the count is reported, not suppressed
    assert 'class="tag scout"' in page           # rendered as a scout card, like any other
    assert "skipped (no run.json)" not in log    # never re-filed as a typo'd path


def test_half_finished_full_run_is_skipped_not_carded() -> None:
    # A full run that died in translate has the SAME run.json-absent shape as a scout workdir:
    # build_run_report keys on report.json + translation.json and never looks at the partial
    # translation.jsonl. So does route B's step 1 (`--only download transcribe`) for EVERY video
    # of the batch until Sonnet writes translation.json — the primary translate route. Carding
    # those would tell the operator to summarize a video that needs re-running, and would
    # contradict run_report.py about the same bytes. source.mkv separates them: scout never
    # writes a container, and invalidate_downstream keeps it as a named survivor.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _scout_workdir(tmp, "failedvid01", n=1, summary="prose")
        (work / "source.mkv").write_bytes(b"mkv")
        (work / "translation.jsonl").write_text('{"id": 0}\n', encoding="utf-8")
        out = tmp / "triage.html"
        code, log = _main_out([str(work), "--out", str(out)])
    assert code == 0
    assert "skipped (no run.json): failedvid01" in log or "nothing to render" in log
    assert "scouted" not in log
    assert not out.exists()          # nothing renderable → no page, same as before scout mode


def test_scout_card_duration_falls_back_to_sentence_ends() -> None:
    # The `[warn] scout: no info.json sidecar` case: yt-dlp wrote no sidecar, so the duration
    # comes from the last sentence `end`. The twin in cli._scout_status is pinned by
    # test_scout_status_falls_back_to_sentence_ends_for_duration; without this the triage_html
    # copy can be deleted outright with the whole suite still green.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _scout_workdir(tmp, summary="s", info=False)
        out = tmp / "triage.html"
        _main_out([str(work), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "7 min" in page                       # 431 s of sentences, not 42 min from info.json
    assert "431 sentences" in page
    assert "Scouted Talk" not in page            # no sidecar → no title, and no crash


def test_scout_card_without_any_duration_drops_the_clause() -> None:
    # video_sec is None when there is neither a sidecar nor a numeric sentence `end`. Every bit
    # in the rollup is DROPPED when its field is None — "None min" on the card would be a
    # fabricated metric, the exact thing the scout card exists to avoid.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _scout_workdir(tmp, summary="s", info=False, ends=False)
        out = tmp / "triage.html"
        _main_out([str(work), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    card = page.split('<section class="video"', 1)[1]
    assert "SCOUT" in card and "431 sentences" in card   # the card still renders
    assert " min" not in card                            # no duration clause at all
    assert "None" not in card                            # and never the literal


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all triage_html tests passed")
