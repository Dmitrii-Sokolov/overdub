"""Unit tests for scripts/build_scout.py + scripts/scout_report.py — the queue report.

ONE page per queue since 2026-07-21 (PLAN item 2), so this suite covers all three surfaces it
merges: the scout grades, the dub-triage surface folded in from the retired morning-triage page,
and the cross-surface parity that keeps the digest (scripts/run_report.py) and this page agreeing
about the same bytes on disk.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_scout_report.py   (or via pytest)

Pure string assembly and JSON over tmp dirs: no GPU, no network, no media, no yt-dlp. The
load-bearing invariants, in the order they would silently break the deliverable:

  ORDER IS THE QUEUE'S. The report exists to be read next to the playlist it came from, so a
  re-sorted row is a wrong row even when every field in it is right. Verdicts are shown, never
  sorted on — the morning-listen job the retired triage page served by sorting the worst first
  is served here by the nav block of anchors, without touching the order.

  A QUEUED VIDEO NEVER VANISHES. No scout.json → an explicit "не отсканировано" row, because a
  report that silently renders only the videos that worked reads as complete.

  THE VERDICT IS NEVER GUESSED. An unknown verdict is fatal in the helper (it is what the page
  colours and recommends on), unlike the anomaly labels build_translation clamps.

  PROSE IS ESCAPED. one_liner/paragraph/title are raw LLM or YouTube text going into HTML.

  AN UNKNOWN TIMING IS NOT A ZERO. A draft carried over from an earlier wave has no measurable
  summarize time; reporting 0 s would understate the pass and read as measured.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import build_scout  # noqa: E402
import run_report  # noqa: E402  — the cross-surface tests run both renderers over one workdir
import scout_report  # noqa: E402
from overdub import runreport  # noqa: E402
from overdub.workdir import WorkDir, jpeg_size  # noqa: E402

_DRAFT = {"quality": "high", "one_liner": "Однофразовое описание.",
          "highlight": "Замеры с описанной методологией и случаи, где схема ломается.",
          "paragraph": "Развёрнутый абзац о том, что разобрано в видео."}


def _workdir(root: Path, vid: str, *, draft=None, title=None, duration=734,
             stages=None, detail=None, started_ago=None) -> WorkDir:
    """A scouted workdir: sentences.json + info.json + timings.json + the sub-agent's draft.
    Mirrors exactly what --scout followed by an S2 sub-agent leaves on disk.

    `detail` fills timings.json's per-video section; `started_ago` writes the sub-agent's
    scout.started marker that many seconds before the draft."""
    d = root / vid
    (d / "segments").mkdir(parents=True, exist_ok=True)
    (d / "sentences.json").write_text(json.dumps(
        [{"id": 0, "text": "One.", "start": 0.0, "end": 3.5},
         {"id": 1, "text": "Two.", "start": 3.5, "end": 9.0}]), encoding="utf-8")
    info = {"title": title if title is not None else f"Title {vid}"}
    if duration is not None:
        info["duration"] = duration
    (d / "source.info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    doc = {"stages": stages if stages is not None else {"download": 12.4, "transcribe": 88.1}}
    if detail is not None:
        doc["detail"] = detail
    (d / "timings.json").write_text(json.dumps(doc), encoding="utf-8")
    if draft is not None:
        (d / "scout.draft.json").write_text(json.dumps(draft, ensure_ascii=False),
                                            encoding="utf-8")
        if started_ago is not None:
            # the marker the sub-agent touches first, backdated relative to the draft it wrote
            marker = d / "scout.started"
            marker.write_text("", encoding="utf-8")
            draft_at = os.path.getmtime(d / "scout.draft.json")
            os.utime(marker, (draft_at - started_ago, draft_at - started_ago))
    return WorkDir(d)


def _queue(root: Path, ids: list[str]) -> Path:
    q = root / "queue.txt"
    q.write_text("\n".join(f"https://www.youtube.com/watch?v={i}" for i in ids) + "\n",
                 encoding="utf-8")
    return q


def _cfg(root: Path) -> Path:
    c = root / "overdub.toml"
    c.write_text(f'work_root = "{root.as_posix()}"\n', encoding="utf-8")
    return c


def _build(work: WorkDir, wave_start=None) -> dict:
    with redirect_stdout(io.StringIO()):
        return build_scout.build(work, wave_start)


def _report(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = scout_report.main(argv)
    return code, buf.getvalue()


# --- build_scout: the verdict is the artifact ---------------------------------
def test_valid_draft_merges_artifacts() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT)
        doc = _build(w)
    assert doc["quality"] == "high"
    assert doc["video_id"] == "vid00000001"
    assert doc["duration_sec"] == 734 and doc["duration_source"] == "info_json"
    assert doc["n_sentences"] == 2
    assert doc["timings"]["download_sec"] == 12.4
    assert doc["timings"]["transcribe_sec"] == 88.1


def test_unknown_quality_is_fatal() -> None:
    # Clamping to "medium" would silently downgrade a video the summarizer rated "high".
    for bad in (None, "отличное", ""):
        draft = {k: v for k, v in _DRAFT.items() if k != "quality"}
        if bad is not None:
            draft["quality"] = bad
        with tempfile.TemporaryDirectory() as d:
            w = _workdir(Path(d), "vid00000001", draft=draft)
            try:
                _build(w)
            except SystemExit as e:
                assert "quality" in str(e.code)
            else:
                raise AssertionError(f"quality={bad!r} must exit, never be clamped")


def test_the_grade_is_about_the_material_not_the_reader() -> None:
    # Renamed axis, and the rename is the point: the first real queue came back 0 watch /
    # 1 maybe / 9 skip under a personal verdict. Two people can disagree about whether to watch
    # a well-made video; they cannot disagree about whether it is well made.
    assert build_scout._QUALITY == ("high", "medium", "low")
    assert not hasattr(build_scout, "_VERDICTS")
    assert not hasattr(build_scout, "_ATTENTION")      # cost axis folded into the highlight text


def test_author_is_optional_and_a_bad_value_is_clamped_not_fatal() -> None:
    # Opposite of the verdict/attention contract, deliberately: the trusted list is empty today,
    # so this axis is optional, and dropping a usable verdict over a mislabelled optional field
    # would cost more than it saves.
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT)
        assert _build(w)["author"] is None                      # absent → not assessed
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft={**_DRAFT, "author": "легенда"})
        assert _build(w)["author"] is None                      # unknown → clamped, still built
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft={**_DRAFT, "author": "trusted"})
        assert _build(w)["author"] == "trusted"


def test_empty_prose_field_is_fatal() -> None:
    # Both lists render this field for every row; an empty one is a hole in the deliverable.
    for key in ("one_liner", "paragraph"):
        with tempfile.TemporaryDirectory() as d:
            w = _workdir(Path(d), "vid00000001", draft={**_DRAFT, key: "   "})
            try:
                _build(w)
            except SystemExit as e:
                assert key in str(e.code)
            else:
                raise AssertionError(f"an empty {key} must exit")


def test_translation_shaped_draft_names_the_mistake() -> None:
    # A route-B-trained sub-agent's one plausible wrong shape: a LIST of per-sentence records.
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=[{"id": 0, "text_ru": "..."}])
        try:
            _build(w)
        except SystemExit as e:
            assert "JSON object" in str(e.code)
        else:
            raise AssertionError("a list-shaped draft must exit")


def test_duration_falls_back_to_the_last_sentence_end() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT, duration=None)
        doc = _build(w)
    assert doc["duration_sec"] == 9.0 and doc["duration_source"] == "sentences"


def test_the_wave_alone_never_yields_a_per_video_summarize_time() -> None:
    # Measured 2026-07-20: 500 sentences reported 1506 s and 31 sentences 1252 s — every agent
    # was reporting the WAVE's length, not its own cost, so a per-video duration was data that
    # was not there. Two timestamps are facts; the duration was a wrong inference. The wave may
    # never be turned back into a per-video number, marker or no marker.
    start = time.time() - 40
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT)      # no scout.started
        doc = _build(w, wave_start=start)
    assert doc["timings"]["summarize_sec"] is None
    assert doc["wave"]["start"] == round(start, 1)
    assert doc["wave"]["draft_at"] >= doc["wave"]["start"]


def test_the_marker_gives_the_agent_its_own_summarize_time() -> None:
    # The per-video number the wave cannot give: measured from the agent's OWN first action, so
    # time spent queued behind the concurrency cap is not billed to it.
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT, started_ago=90.0)
        doc = _build(w, wave_start=time.time() - 4000)          # wave far wider than the agent
    assert doc["timings"]["summarize_sec"] == 90.0              # its own window, not the wave's


def test_a_marker_newer_than_the_draft_is_refused_not_negated() -> None:
    # A respawn that touched the marker and then died, or a carried-over draft: the pair does
    # not describe one agent's run. Absent beats a negative number presented as a measurement.
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT, started_ago=-120.0)
        with redirect_stdout(io.StringIO()) as buf:
            doc = build_scout.build(w, None)
    assert doc["timings"]["summarize_sec"] is None
    assert "scout.started is newer" in buf.getvalue()           # and the operator is told


def test_transcribe_reports_its_own_cost_apart_from_the_stage_wall_clock() -> None:
    # stages.transcribe includes the model load and warmup, which land on whichever video the
    # sweep started with; detail.transcribe.work_sec is what THIS video cost. Both are kept.
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT,
                     stages={"download": 12.4, "transcribe": 88.1},
                     detail={"transcribe": {"work_sec": 61.25, "asr_passes": 2}})
        doc = _build(w)
    t = doc["timings"]
    assert t["transcribe_sec"] == 88.1            # wall clock, load included — the run's cost
    assert t["transcribe_work_sec"] == 61.2       # this video's cost, load excluded
    # a tally, not a measurement: 2 rather than 2.0, or the field reads as continuous
    assert t["transcribe_asr_passes"] == 2 and isinstance(t["transcribe_asr_passes"], int)


def test_a_workdir_without_the_detail_section_still_builds() -> None:
    # Every workdir transcribed before detail existed. The per-video fields are absent, never
    # backfilled from the wall clock — which would restate the load as this video's cost.
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT)      # no detail key at all
        doc = _build(w)
    assert doc["timings"]["transcribe_sec"] == 88.1
    assert doc["timings"]["transcribe_work_sec"] is None
    assert doc["timings"]["transcribe_asr_passes"] is None


def test_a_carried_over_draft_keeps_its_stamps_and_leaves_the_wave() -> None:
    # The skill's resume filter deliberately skips an up-to-date summary, so a draft older than
    # the wave is NORMAL. Its stamps are still facts; it just must not stretch the wall clock.
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT)
        doc = _build(w, wave_start=time.time() + 600)
    assert doc["wave"]["draft_at"] < doc["wave"]["start"]
    assert scout_report.totals_of([{"timings": {}, "wave": doc["wave"]}])["summarize"] is None


def test_missing_wave_start_leaves_the_wave_absent() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT)
        doc = _build(w)
    assert doc["wave"] is None


def test_missing_sentences_is_fatal() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        w = _workdir(root, "vid00000001", draft=_DRAFT)
        (root / "vid00000001" / "sentences.json").unlink()
        try:
            _build(w)
        except SystemExit as e:
            assert "sentences" in str(e.code)
        else:
            raise AssertionError("a workdir that was never scouted must exit")


# --- scout_report: order, completeness, escaping -------------------------------
def _scouted(root: Path, vid: str, quality: str, **kw) -> None:
    w = _workdir(root, vid, draft={**_DRAFT, "quality": quality, **kw})
    (root / vid / "scout.json").write_text(
        json.dumps(_build(w), ensure_ascii=False), encoding="utf-8")


def test_rows_follow_the_queue_not_the_verdict() -> None:
    # The whole point: "skip" first in the queue stays first on the page.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "low", one_liner="Первое в очереди.")
        _scouted(root, "vid00000002", "high", one_liner="Второе в очереди.")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert page.index("Первое в очереди.") < page.index("Второе в очереди.")
    # and again in the second list, which must not re-order either
    assert page.index("vid00000001") < page.index("vid00000002")


def test_a_queued_video_without_scout_json_still_gets_a_row() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    # vid00000002 has no workdir at all → "не скачано", the state whose fix is re-running S1
    assert "vid00000002" in page and "не скачано" in page
    assert "не скачано" in log                 # and the operator is told, not just the page


def test_three_unfinished_states_are_told_apart() -> None:
    # Each needs a DIFFERENT fix: re-run S1 / investigate transcribe / respawn the summarizer.
    # Collapsing them sends the operator to the wrong one.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")                   # complete
        _workdir(root, "vid00000002", draft=None)                # sentences, no scout.json
        (root / "vid00000003" / "segments").mkdir(parents=True)   # audio only, no transcript
        (root / "vid00000003" / "source.wav").write_bytes(b"RIFF")
        # vid00000004: nothing at all on disk
        q = _queue(root, [f"vid0000000{i}" for i in (1, 2, 3, 4)])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    for label in ("не отсканировано", "не расшифровано", "не скачано"):
        assert label in page and label in log


def test_a_transcript_outranks_a_missing_wav() -> None:
    # A promotion rewrites source.wav and a cleanup can delete it; the transcript still proves
    # the download happened. Probing the wav first would order a pointless re-fetch.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _workdir(root, "vid00000001", draft=None)                # sentences.json, no source.wav
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "не отсканировано" in page and "не скачано" not in page


def test_numbering_follows_the_queue_and_survives_a_gap() -> None:
    # The number is the reader's index into the playlist they have open, so a video that failed
    # to download must KEEP its position rather than being renumbered around.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        # vid00000002 missing entirely
        _scouted(root, "vid00000003", "low")
        q = _queue(root, ["vid00000001", "vid00000002", "vid00000003"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert '<td class="idx">2</td>' in page                       # the gap keeps its number
    assert page.index('<td class="idx">1</td>') < page.index('<td class="idx">3</td>')


def test_queue_runtime_is_reported_and_build_time_is_not() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")                    # duration 734 from info.json
        _scouted(root, "vid00000002", "low")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "хронометраж очереди" in page
    assert "24:28" in page                                        # 734 × 2 = 1468 s, no hours
    assert "сборка отчёта" not in page


def test_queue_runtime_marks_itself_a_floor_when_a_row_has_no_duration() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001", "vid00000002"])           # second never scanned
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "12:14+" in page          # the '+' says "at least this much", not a measurement


def test_reason_is_required_and_distinct_from_the_description() -> None:
    # "о чём" and "почему смотреть" answer different questions; one field cannot carry both,
    # and the scan table asks both at a glance.
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001",
                     draft={k: v for k, v in _DRAFT.items() if k != "highlight"})
        try:
            _build(w)
        except SystemExit as e:
            assert "highlight" in str(e.code)
        else:
            raise AssertionError("a missing reason must exit")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert page.count(_DRAFT["highlight"]) == 2                           # table + card
    assert "Однофразовое описание." in page                               # still its own field
    assert "<th>Самое интересное</th>" in page


def test_title_links_to_the_video_in_both_lists() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert page.count("https://www.youtube.com/watch?v=vid00000001") == 2
    assert 'rel="noopener"' in page


def test_an_unscanned_row_still_links_to_its_video() -> None:
    # That row exists to send the reader to look at the thing; a dead title defeats it.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        q = _queue(root, ["vid00000009"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "https://www.youtube.com/watch?v=vid00000009" in page


def test_the_table_links_into_the_cards_and_the_card_number_is_not_a_link() -> None:
    # One direction only: the table is the index, the cards are what it indexes. The back-link
    # on the card number duplicated the browser's own back gesture and competed with the title.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        _scouted(root, "vid00000002", "low")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    for n in (1, 2):
        assert f'<tr id="r{n}"' in page and f'href="#v{n}"' in page       # row → card
        assert f'id="v{n}"' in page                                       # the card is there
        assert f'href="#r{n}"' not in page                                # but nothing links back
        assert f'<span class="idx">{n}</span>' in page                    # the number is a label


def test_playlist_header_is_named_and_linked() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = root / "queue.txt"
        q.write_text("# playlist: AI Fluency | https://youtube.com/playlist?list=PL123\n"
                     "https://www.youtube.com/watch?v=vid00000001\n", encoding="utf-8")
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "AI Fluency" in page
    assert "https://youtube.com/playlist?list=PL123" in page


def test_playlist_header_is_optional_and_backward_compatible() -> None:
    # Every queue written before the header existed must keep working, header or not.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001"])                     # no header at all
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        assert code == 0
        assert scout_report.queue_playlist(q) is None
        # and the '#' line is still not mistaken for a video
        assert scout_report.queue_ids(q) == ["vid00000001"]


def test_playlist_header_accepts_a_bare_url() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        q = root / "queue.txt"
        q.write_text("# playlist: https://youtube.com/playlist?list=PL9\n", encoding="utf-8")
        pl = scout_report.queue_playlist(q)
    assert pl["url"] == "https://youtube.com/playlist?list=PL9"
    assert pl["title"] == "https://youtube.com/playlist?list=PL9"


def test_paragraph_splits_on_blank_lines_and_survives_a_single_block() -> None:
    # The split is the summarizer's call — the renderer must honour it, and must not invent one.
    assert scout_report._paragraphs("один\n\nдва\n\nтри").count("<p>") == 3
    assert scout_report._paragraphs("одним куском").count("<p>") == 1


def test_thumbnail_is_inlined_not_linked() -> None:
    # A remote src is blocked outright by the Artifact CSP — invisible exactly where the page is
    # meant to be read.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        (root / "vid00000001" / "thumb.jpg").write_bytes(b"\xff\xd8\xff\xdb-fake-jpeg")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    # ONCE, though the preview is shown twice (scan row and card). A data-URI in a src is the
    # bytes themselves, so two <img> tags meant two copies of every preview — 78% of a 226 KB
    # report. The CSS rule is declared once and both elements wear its class.
    assert page.count("data:image/jpeg;base64,") == 1
    assert page.count('class="thumb t1"') == 2                 # ...and it IS still shown twice
    assert "i.ytimg.com" not in page


def test_the_rendered_preview_never_asks_for_more_pixels_than_are_stored() -> None:
    # Two files, one number, and nothing but a comment holding them together — which is exactly
    # how the scan table ended up upscaling a 160px file into a 320px slot and going soft.
    #
    # A CEILING, not an equality: rendering NARROWER than the file on disk is the 2x-source case
    # (sharp on hi-DPI) and must stay allowed. Asserting equality would have failed the moment
    # the preview was halved — a guard that fires on the safe direction gets deleted, and then
    # the unsafe direction is unguarded too.
    widths = [int(w) for w in re.findall(r"\.thumb\{[^}]*?width:(\d+)px", scout_report._CSS)]
    assert widths, "no .thumb width in the CSS — the rule was renamed and this guard went blind"
    assert max(widths) <= build_scout._THUMB_W


def test_the_preview_is_out_of_reach_of_the_artifact_skeletons_img_reset() -> None:
    # The published page is wrapped in a skeleton carrying `img{max-width:100%}`. In an
    # auto-layout table that drops the preview's min-content contribution to ~0, and
    # `td.pic{width:1%}` then squeezes the column to a sliver — visible only after publishing,
    # never when the fragment is opened locally.
    #
    # A CONDITIONAL, because the defusing moved: the preview is a <div> now, which that selector
    # cannot reach, so `max-width:none` became dead weight and was dropped. Asserting the
    # property would pin a fix to a mechanism that no longer applies; asserting the implication
    # keeps the guard true whichever element the preview goes back to being.
    assert "td.pic{width:1%" in scout_report._CSS      # the half that makes the trap possible
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        (root / "vid00000001" / "thumb.jpg").write_bytes(b"\xff\xd8\xff\xdb-fake-jpeg")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    # the static sheet is stripped first: it is prose about this very trap, and a tag named
    # inside a comment is not the page rendering one
    if "<img" in page.replace(scout_report._CSS, ""):
        assert "max-width:none" in scout_report._CSS, (
            "the preview is an <img> again — the skeleton's reset can reach it, and without "
            "max-width:none the column collapses once published")


def _jpeg(w: int, h: int, marker: bytes = b"\xc0") -> bytes:
    """Minimal JPEG carrying nothing but a frame header of the given size."""
    sof = b"\xff" + marker + b"\x00\x11\x08" + h.to_bytes(2, "big") + w.to_bytes(2, "big")
    return b"\xff\xd8" + sof + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01" + b"\xff\xd9"


def test_jpeg_size_reads_the_frame_header() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.jpg"
        p.write_bytes(_jpeg(160, 90))
        assert jpeg_size(p) == (160, 90)
        p.write_bytes(_jpeg(160, 120))                    # a 4:3 source, the case 16/9 would crop
        assert jpeg_size(p) == (160, 120)


def test_jpeg_size_never_raises_and_never_guesses() -> None:
    # The preview is the one thing on the page nothing depends on — every failure here has to be
    # a None the caller falls back on, never an exception that costs the operator a report.
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.jpg"
        assert jpeg_size(p) is None                      # absent
        p.write_bytes(b"not a jpeg at all")
        assert jpeg_size(p) is None                      # wrong magic
        p.write_bytes(b"\xff\xd8" + b"\xff\xc0\x00\x01")              # length that cannot self-cover
        assert jpeg_size(p) is None
        # 0xC4 lives in the SOF range and is NOT a frame header — reading it would yield two
        # plausible numbers that are not the image's size, which is worse than admitting nothing
        p.write_bytes(_jpeg(160, 90, marker=b"\xc4"))
        assert jpeg_size(p) is None


def _ffmpeg() -> bool:
    """ffmpeg is an external binary the suite must not require — these two cases skip without it
    rather than fail, since everything else here is pure string assembly over tmp dirs."""
    import shutil
    return shutil.which("ffmpeg") is not None


def test_an_oversized_preview_on_disk_is_rescaled_not_kept() -> None:
    # `if exists: return` meant lowering _THUMB_W changed nothing for any workdir already on
    # disk: every preview kept its old width forever and the reports kept carrying the old bytes.
    # The artifact's size has to be self-correcting -- the number defining it lives in a
    # different file from the files it governs.
    if not _ffmpeg():
        return
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d) / "vid00000001")
        work.root.mkdir(parents=True)
        wide = build_scout._THUMB_W * 2
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", f"color=c=red:s={wide}x{wide // 16 * 9}:d=1", "-frames:v", "1",
                        str(work.thumb)], check=True)
        assert jpeg_size(work.thumb)[0] == wide                  # precondition
        build_scout._ensure_thumb(work, {})
        assert jpeg_size(work.thumb)[0] == build_scout._THUMB_W
        # no scrap left behind, and above all the preview still exists
        assert not (work.root / "thumb.out.jpg").exists()
        assert not (work.root / "thumb.src.jpg").exists()


def test_a_preview_already_small_enough_is_left_untouched() -> None:
    # Re-encoding a correct file every run would be lossy for nothing.
    if not _ffmpeg():
        return
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d) / "vid00000001")
        work.root.mkdir(parents=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", f"color=c=red:s={build_scout._THUMB_W}x90:d=1", "-frames:v", "1",
                        str(work.thumb)], check=True)
        before = work.thumb.read_bytes()
        build_scout._ensure_thumb(work, {})
        assert work.thumb.read_bytes() == before


def test_an_unmeasurable_preview_is_left_alone_rather_than_re_encoded() -> None:
    # No ffmpeg needed: the guard returns before any subprocess. An unreadable header may still
    # be bytes a browser decodes, and re-encoding what we cannot measure can only guess.
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d) / "vid00000001")
        work.root.mkdir(parents=True)
        work.thumb.write_bytes(b"\xff\xd8 truncated before any SOF")
        before = work.thumb.read_bytes()
        build_scout._ensure_thumb(work, {})
        assert work.thumb.read_bytes() == before


def test_the_preview_rule_carries_the_real_aspect_not_a_guess() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        (root / "vid00000001" / "thumb.jpg").write_bytes(_jpeg(160, 120))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    # a background box has no size of its own: get this wrong and the preview is either cropped
    # or zero pixels tall
    assert "aspect-ratio:160/120" in page
    assert "aspect-ratio:16/9;background-image" not in page       # the fallback did not fire


def test_an_unparseable_preview_still_renders_on_the_fallback_ratio() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        (root / "vid00000001" / "thumb.jpg").write_bytes(b"\xff\xd8 truncated before any SOF")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    # unreadable header is not a missing preview: the bytes may still be a picture the browser
    # can decode, so it is shown at 16:9 rather than dropped
    assert "aspect-ratio:16/9" in page
    assert page.count("data:image/jpeg;base64,") == 1


def test_a_missing_thumbnail_renders_nothing_at_all() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")                 # no thumb.jpg written
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    # same stripping as the reset guard: _CSS discusses the preview in prose, the page must not
    # RENDER one — no element, and above all no per-video rule carrying bytes for a file that
    # does not exist
    assert "<img" not in page.replace(scout_report._CSS, "")
    assert "base64" not in page and 'class="thumb' not in page


def test_the_row_is_six_cells_and_the_jump_sits_on_the_description() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    start = page.index('<tr id="r1"')
    row = page[start:page.index("</tr>", start)]
    assert row.count("<td") == 6            # №, превью, название, время, о чём, самое интересное
    # the jump rides the description — the cell the reader is already reading when they want more
    assert '<td class="line"><a class="jump" href="#v1"' in row
    # runtime is its OWN column, right after the title — scanned down the column, not hunted for
    # at the end of a prose cell
    assert '<td class="num dur">12:14</td>' in row
    assert row.index('<td class="name">') < row.index('<td class="num dur">')
    # the grade opens the highlight cell rather than sitting under the title
    assert '<td class="why"><span class="chip v-watch">высокое</span>' in row
    assert '<td class="name">' in row and "высокое" not in row[row.index('<td class="name">'):
                                                              row.index('<td class="num dur">')]


def test_the_video_id_column_is_gone_from_both_lists() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        w = _workdir(root, "vid00000001", draft=_DRAFT, title="Заголовок без кода")
        (root / "vid00000001" / "scout.json").write_text(
            json.dumps(_build(w), ensure_ascii=False), encoding="utf-8")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "<th>Код</th>" not in page
    # the id survives only inside the video link, which is where it is still useful
    assert page.count("vid00000001") == page.count("watch?v=vid00000001") == 2


def test_every_verdict_gets_its_own_colour_class() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for i, v in enumerate(("high", "medium", "low"), 1):
            _scouted(root, f"vid0000000{i}", v)
        q = _queue(root, ["vid00000001", "vid00000002", "vid00000003"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    for cls in ("v-watch", "v-maybe", "v-skip"):
        assert f'chip {cls}' in page and f'card {cls}' in page


def test_the_row_itself_carries_no_grade_colour() -> None:
    # The chip already names the grade in words AND in colour. Striping the row too tinted it
    # before the reader had read anything, so the row is neutral now and the chip is the marker.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        _scouted(root, "vid00000002", "low")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert '<tr id="r1">' in page and '<tr id="r2">' in page      # no verdict class on the row
    assert "tbody tr" not in page                                  # and no rule left to apply one
    # the colour that remains is the chip's, in the highlight cell
    assert '<span class="chip v-watch">высокое</span>' in page
    assert '<span class="chip v-skip">слабое</span>' in page


def test_trusted_author_marker_only_when_assessed() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")                      # no author key
        _scouted(root, "vid00000002", "high", author="trusted")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert page.count("доверенный автор") == 2                      # only the second video


def test_unscanned_row_carries_no_cost_label() -> None:
    # Inventing a cost for a video nobody assessed would fabricate the one number the operator
    # schedules against.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        q = _queue(root, ["vid00000009"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "не скачано" in page               # nothing on disk → the download state
    assert "концентрация" not in page and "фоновое" not in page


def test_a_scout_json_without_the_highlight_still_renders() -> None:
    # Forward-compat in the renderer only: build_scout REQUIRES the field from now on, but a
    # report must never crash on an artifact written by an older build.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        w = _workdir(root, "vid00000001", draft=_DRAFT)
        doc = _build(w)
        doc.pop("highlight")
        (root / "vid00000001" / "scout.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0 and "высокое" in page


def test_prose_and_title_are_escaped() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        w = _workdir(root, "vid00000001", title="<script>alert(1)</script>",
                     draft={**_DRAFT, "one_liner": "a <b>& b</b>",
                            "paragraph": "<img src=x onerror=y>"})
        (root / "vid00000001" / "scout.json").write_text(
            json.dumps(_build(w), ensure_ascii=False), encoding="utf-8")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in page
    assert "<img src=x" not in page
    assert "&lt;script&gt;" in page


def test_page_is_a_body_fragment_for_the_artifact_publisher() -> None:
    # The publisher supplies doctype/head/body; emitting our own would nest documents.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    low = page.lower()
    for tag in ("<!doctype", "<html", "<head>", "<body"):
        assert tag not in low
    assert "<style>" in low                    # but it IS self-contained


def test_the_local_file_declares_its_own_charset() -> None:
    # The Artifact publisher sets charset on its own skeleton, so the published copy never needed
    # this -- but the module docstring promises the SAME file "opens locally by double-click", and
    # a file:// URL carries no Content-Type header for a browser to read UTF-8 off of. Without this
    # tag a browser guesses and mangles every Cyrillic character in the report. HTML5 only looks in
    # the first 1024 bytes for a charset declaration, so it must lead -- not just be present.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert '<meta charset="utf-8">' in page
    assert page.index('<meta charset="utf-8">') < 1024
    assert page.index('<meta charset="utf-8">') < page.index("<style>")


def test_both_themes_are_defined() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "prefers-color-scheme:dark" in page
    assert '[data-theme="dark"]' in page and '[data-theme="light"]' in page


# --- the timing strip must not lie ---------------------------------------------
def test_the_wave_starts_at_the_first_AGENT_not_at_the_operator_stamp() -> None:
    # `wave.start` (1000) is stamped before spawning, so the span from it also contains however
    # long it took to get the agents running. Measured 2026-07-21: eight invocation attempts put
    # 371 s of tool-call retries inside a 192 s wave and the report printed 9.4 min.
    # The agents' own starts are 1005 and 1010 (draft_at - summarize_sec), so the wave is 45 s.
    entries = [
        {"timings": {"download_sec": 10.0, "transcribe_sec": 100.0, "summarize_sec": 25.0},
         "wave": {"start": 1000.0, "draft_at": 1030.0}},
        {"timings": {"download_sec": 20.0, "transcribe_sec": 200.0, "summarize_sec": 40.0},
         "wave": {"start": 1000.0, "draft_at": 1050.0}},
    ]
    t = scout_report.totals_of(entries)
    assert t["download"] == 30.0 and t["transcribe"] == 300.0
    assert t["summarize"] == 45.0            # 1050 - 1005; the old definition gave 50
    assert t["summarize_unmeasured"] == 0
    # deliberately no grand total: adding two sums to a wall clock produced a figure that was
    # neither the work done nor the elapsed time
    assert "total" not in t


def test_a_resumed_queue_does_not_bill_the_gap_between_waves_as_summarization() -> None:
    # The resume case, which is the NORMAL one: the skill re-runs build_scout only for videos
    # needing a new summary, so a carried-forward video keeps its original wave's start forever.
    # Spanning the whole queue would charge the hour BETWEEN the waves to summarization.
    entries = [
        {"timings": {"summarize_sec": 15.0}, "wave": {"start": 1000.0, "draft_at": 1020.0}},
        {"timings": {"summarize_sec": 12.0}, "wave": {"start": 4600.0, "draft_at": 4620.0}},
    ]
    t = scout_report.totals_of(entries)
    assert t["summarize"] == 27.0            # 15 + 12, the two windows — never ~3620
    one = [{"timings": {"summarize_sec": 15.0}, "wave": {"start": 1000.0, "draft_at": 1020.0}}]
    assert scout_report.totals_of(one)["summarize"] == 15.0


def test_an_agent_without_a_marker_makes_the_wave_a_floor_not_a_lie() -> None:
    # Measured 2026-07-21: 1 of 6 agents wrote both artifacts and skipped the marker. Its summary
    # is intact and only its start is unknown — which can only make the real wave WIDER, so the
    # figure is a floor and must be rendered as one rather than as an exact number.
    entries = [
        {"timings": {"summarize_sec": 40.0}, "wave": {"start": 1000.0, "draft_at": 1050.0}},
        {"timings": {}, "wave": {"start": 1000.0, "draft_at": 1060.0}},      # no marker
    ]
    t = scout_report.totals_of(entries)
    assert t["summarize"] == 50.0            # 1060 (its draft still ends the wave) - 1010
    assert t["summarize_unmeasured"] == 1


def test_a_wave_with_no_markers_at_all_reports_unknown_not_the_stamp() -> None:
    # Every workdir summarized before the marker existed. Falling back to `wave.start` here would
    # quietly reintroduce the orchestration overhead this whole change removes.
    entries = [{"timings": {}, "wave": {"start": 1000.0, "draft_at": 1050.0}}]
    t = scout_report.totals_of(entries)
    assert t["summarize"] is None
    assert t["summarize_unmeasured"] == 1


def test_recording_a_stage_wall_clock_does_not_eat_the_per_video_detail() -> None:
    # record_stage_timing used to write {"stages": ...} back over the whole file, which was
    # invisible while `stages` was the only section and silently destroys `detail` now that a
    # second one exists. The transcribe stage writes both, in that order.
    from overdub import runreport

    with tempfile.TemporaryDirectory() as d:
        w = WorkDir(Path(d))
        w.root.mkdir(parents=True, exist_ok=True)
        runreport.record_stage_detail(w, "transcribe", work_sec=61.2, asr_passes=1)
        runreport.record_stage_timing(w, "transcribe", 88.1)
        doc = json.loads((w.root / "timings.json").read_text(encoding="utf-8"))
    assert doc["stages"]["transcribe"] == 88.1
    assert doc["detail"]["transcribe"] == {"work_sec": 61.2, "asr_passes": 1}


def test_the_report_never_sums_the_per_video_figures() -> None:
    # Per-video summarize times OVERLAP — the agents run concurrently — so their sum exceeds the
    # wave's wall clock and means nothing. Same for work_sec against the stage wall clock. The
    # strip carries the wall clocks; totals_of must not learn to add the others.
    # Two agents that overlap heavily, which is what a working fan-out looks like: 900 s and
    # 800 s of work inside a 900 s wave. The fixture is coherent on purpose — the numbers here
    # used to imply agents starting before the wave existed, which stopped being harmless once
    # the wave was derived from them.
    entries = [
        {"timings": {"download_sec": 1.0, "transcribe_sec": 100.0,
                     "transcribe_work_sec": 60.0, "summarize_sec": 900.0},
         "wave": {"start": 990.0, "draft_at": 1900.0}},     # ran 1000..1900
        {"timings": {"download_sec": 2.0, "transcribe_sec": 200.0,
                     "transcribe_work_sec": 180.0, "summarize_sec": 800.0},
         "wave": {"start": 990.0, "draft_at": 1850.0}},     # ran 1050..1850
    ]
    t = scout_report.totals_of(entries)
    assert t["transcribe"] == 300.0          # the wall clocks, as before
    assert t["summarize"] == 900.0           # 1900 - 1000, the WAVE — never 1700
    assert not any(k.endswith("work") or k == "summarize_per_video" for k in t)


def test_unknown_timings_render_as_a_dash_not_a_zero() -> None:
    assert scout_report.secs(None) == "—"
    assert scout_report.clock(None) == "—"
    entries = [{"timings": {}, "wave": None}]
    t = scout_report.totals_of(entries)
    assert t["download"] is None and t["summarize"] is None
    assert t["content"] is None                # no durations at all → not a zero-length queue


def test_queue_order_dedupes_but_keeps_first_position() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        q = root / "queue.txt"
        q.write_text("https://youtu.be/vid00000001\n# comment\n\n"
                     "https://www.youtube.com/watch?v=vid00000002\n"
                     "https://www.youtube.com/watch?v=vid00000001\n", encoding="utf-8")
        assert scout_report.queue_ids(q) == ["vid00000001", "vid00000002"]


# --- the merged dub surface ------------------------------------------------------
# Migrated from the retired morning-triage page's own suite when that page was folded into
# this one (2026-07-21, PLAN item 2). Each test keeps its parent's INTENT — escaping, the
# "-"-vs-"0" src cell, no fabricated dub metrics on a scout card, skip-vs-card discrimination,
# the exact no-summary phrase, embed vs --link, --limit — re-pinned against the merged markup.

def _dubbed(root: Path, vid: str, *, verify_flags=("low_similarity", None), translation=None,
            summary=None, wav=(), title="Dub Talk", duration=300.0) -> Path:
    """A dubbed workdir: report.json + translation.json (+ info/timings) — the exact input
    shape build_run_report rolls up, so the page exercises the REAL data path, not a
    hand-shaped run dict. One report unit per verify_flags entry (unit i = sentence i);
    a flagged unit is also fast (combined 2.0) so it carries a speed reason too."""
    d = root / vid
    (d / "segments").mkdir(parents=True, exist_ok=True)
    segs = []
    for i, vf in enumerate(verify_flags):
        segs.append({"id": i, "group_id": i, "status": "ok", "verify_flag": vf,
                     "combined_factor": 2.0 if vf else 1.0, "speed_factor": 1.5 if vf else 1.0,
                     "assemble_flag": None, "completeness_flags": [], "translate_flag": None,
                     "similarity": 0.42 if vf else 0.98,
                     "hypothesis": "что-то не то" if vf else None})
    n_fl = sum(1 for vf in verify_flags if vf)
    report = {"segments": segs,
              "verify": {"model": "small", "n_units": len(segs), "n_segments": len(segs),
                         "n_flagged": n_fl, "n_retried": 0, "n_repaired": 0},
              "completeness": {"n_sentences": len(segs), "n_flagged": 0, "n_num_loss": 0,
                               "n_neg_loss": 0, "n_entity_loss": 0, "n_length": 0},
              "assemble": {"duration_sec": duration, "n_sped": n_fl,
                           "in_span_silence_sec": 0.0},
              "mux": {"dub_mix": "bed", "dub_gain_db": 3.0}}
    if translation is None:
        translation = [{"id": i, "status": "ok", "src_en": f"EN {i}", "text_ru": f"РУ {i}",
                       "text_tts": f"тэ-тэ-эс {i}", "start": float(i) * 3.0,
                        "end": float(i) * 3.0 + 3.0, "src": "ok"}
                       for i in range(len(segs))]
    (d / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    (d / "translation.json").write_text(json.dumps(translation, ensure_ascii=False),
                                        encoding="utf-8")
    (d / "source.info.json").write_text(json.dumps({"title": title, "duration": duration}),
                                        encoding="utf-8")
    (d / "timings.json").write_text(json.dumps({"stages": {"download": 5.0,
                                                           "synthesize": 55.0}}),
                                    encoding="utf-8")
    for sid in wav:
        (d / "segments" / f"{sid:05d}.wav").write_bytes(b"RIFF-fake-wav-bytes")
    if summary is not None:
        (d / "summary.md").write_text(summary, encoding="utf-8")
    return d


def _transcribed(root: Path, vid: str, *, n=431, info=True, ends=True, summary=None,
                 mkv=False) -> Path:
    """A transcript-only workdir (scout shape; add mkv=True for the promoted 'pending' shape).
    `ends` off = sentences with no numeric `end`, the only shape from which no duration at all
    can be derived."""
    d = root / vid
    (d / "segments").mkdir(parents=True, exist_ok=True)
    (d / "sentences.json").write_text(json.dumps(
        [{"id": i, "text": f"s{i}", "start": float(i),
          **({"end": float(i) + 1.0} if ends else {})} for i in range(n)]), encoding="utf-8")
    if info:
        (d / "source.info.json").write_text(
            json.dumps({"title": "Scouted Talk", "duration": 2530.0}), encoding="utf-8")
    if summary is not None:
        (d / "summary.md").write_text(summary, encoding="utf-8")
    if mkv:
        (d / "source.mkv").write_bytes(b"mkv")
    return d


def _card_of(page: str, n: int) -> str:
    """The card slice for queue position n — everything between its anchor and its close."""
    return page.split(f'id="v{n}"', 1)[1].split("</article>", 1)[0]


def test_run_card_summary_is_escaped_and_paragraphed() -> None:
    # Raw LLM prose going into HTML: unescaped, a stray tag would break the page (or worse).
    # Blank lines are the only structure read_summary leaves, so they become <p> boundaries.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", summary="Первый <b>абзац</b>.\n\nВторой & третий.")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        card = _card_of(out.read_text(encoding="utf-8"), 1)
    assert "&lt;b&gt;" in card and "&amp;" in card
    assert "<b>абзац" not in card                       # never the live tag
    assert card.count("<p>") == 2                       # two paragraphs, not one blob
    # (only _paragraphs emits bare <p>; the rollup/state lines all carry a class)


def test_run_card_without_summary_renders_no_prose() -> None:
    # A video with no summary.md is the normal case, not an error — the card keeps its rollup
    # and units and grows no empty prose container.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        card = _card_of(out.read_text(encoding="utf-8"), 1)
    assert 'class="rollup"' in card                     # the dub block is untouched
    assert card.count("<p>") == 0                       # and no prose block appeared


def test_main_reads_summary_md_off_a_dubbed_workdir() -> None:
    # main() is the only place the summary is read off the workdir — and this is also the
    # positional-workdirs-without---queue entry point the merge made optional.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = _dubbed(root, "vid00000001", summary="Стоит смотреть целиком.")
        out = root / "r.html"
        code, _ = _report([str(wd), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "Стоит смотреть целиком." in page


def test_cli_requires_a_queue_or_a_workdir() -> None:
    # Neither positional workdirs nor --queue: there is no report to render and guessing a
    # queue file would be worse than saying so.
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            scout_report.main([])
    except SystemExit as e:
        assert e.code == 2                              # argparse usage-error exit code
    else:
        raise AssertionError("no --queue and no workdirs must be a usage error")


# --- source anomalies on the card (DECISIONS 2026-07-19, migrated) ----------------
def _src_translation():
    """Two OK-dub sentences, one carrying a source anomaly with hostile prose in the note."""
    return [{"id": 0, "status": "ok", "src_en": "EN 0", "text_ru": "РУ 0", "text_tts": "т 0",
             "start": 0.0, "end": 3.0, "src": "truncated",
             "src_note": "ends <script>alert(1)</script> & mid-thought"},
            {"id": 1, "status": "ok", "src_en": "EN 1", "text_ru": "РУ 1", "text_tts": "т 1",
             "start": 3.0, "end": 6.0, "src": "ok"}]


def test_srcanom_absent_when_source_is_clean() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")                    # every src is "ok"
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    # the static sheet is stripped first: _CSS carries the .srcanom RULE on every page; the
    # invariant is that no srcanom ELEMENT renders when the scan found nothing
    assert "srcanom" not in page.replace(scout_report._CSS, "")


def test_srcanom_rendered_and_escaped() -> None:
    # The note is raw LLM prose going into HTML — same escape rule as every other prose field.
    # Deliberately NO <audio> anywhere near it: the defect is in the ENGLISH source, so
    # listening to the Russian tells the operator nothing.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=(None, None), translation=_src_translation())
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    block = page.split('<div class="srcanom">', 1)[1].split("</div>", 1)[0]
    assert "аномалии источника (1)" in block and "truncated" in block
    assert "&lt;script&gt;" in block and "&amp;" in block
    assert "<script>" not in block
    assert "<audio" not in block


def test_srcanom_renders_without_flagged_units() -> None:
    # A clean-verify run can still carry a source anomaly, and that is exactly when the signal
    # is most actionable (--repair-asr is still cheap). The clean-units note stays too.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=(None, None), translation=_src_translation())
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "srcanom" in page
    assert "проблемных юнитов нет — слушать нечего." in page


def _dub_row_cells(page: str, n: int) -> list[str]:
    """The ten verbatim data cells of the dub-table row for queue position n."""
    m = re.search(rf'<td><a class="jump" href="#v{n}">[^<]*</a></td>(.*?)</tr>', page, re.S)
    assert m, f"no dub-table row for position {n}"
    return re.findall(r'<td class="num">([^<]*)</td>', m.group(1))


def test_dub_table_src_dash_when_unscanned() -> None:
    # "-" means NOT SCANNED (route A / pre-schema); "0" means scanned AND clean. Conflating the
    # two would report a Gemma-route video as source-checked when nothing ever read it.
    no_src = [{"id": i, "status": "ok", "src_en": f"EN {i}", "text_ru": f"РУ {i}",
               "text_tts": f"т {i}", "start": float(i), "end": float(i) + 1.0}
              for i in range(2)]                        # route A: no src field at all
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vidNOSRC000", translation=no_src)
        _dubbed(root, "vidOKSRC000")                   # all src "ok" → scanned, clean
        q = _queue(root, ["vidNOSRC000", "vidOKSRC000"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    src_i = [k for k, _l in runreport.BATCH_COLUMNS].index("src") - 2   # minus video+title
    assert _dub_row_cells(page, 1)[src_i] == "-"
    assert _dub_row_cells(page, 2)[src_i] == "0"


def test_scout_card_fabricates_no_dub_metrics() -> None:
    # A scouted video has no RTF, no flags, no triage verdict. The merged page must not leak
    # ANY dub component onto its card or fabricate a dub table/nav around it — borrowing the
    # «чисто» chip would report an undubbed video as verified. Pinned in both parents; forever.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    card = _card_of(page, 1)
    for forbidden in ("<audio", "srcanom", "RTF", 'class="unit"', "слушать", "чисто"):
        assert forbidden not in card, forbidden
    assert "<th>wall_s</th>" not in page                # no dub table on a pure-scout page
    assert "требуют прослушивания" not in page          # no dub totals, no nav


def test_counters_exclude_scouts_from_the_video_count() -> None:
    # "0 need triage" out of a count that includes never-dubbed videos is a lie about them.
    # Kept from the retired page: stdout counts dubbed videos, scouts ride separately, and the
    # page's dub totals line counts only the dubbed.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vidDUBBED00", verify_flags=(None, None))
        _scouted(root, "vidSCOUTED0", "high")
        q = _queue(root, ["vidDUBBED00", "vidSCOUTED0"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "1 video(s), 1 scouted," in log
    assert "2 video(s)" not in log
    assert "1 видео · wall" in page                     # dub totals: the dubbed one only
    assert "2 видео · wall" not in page


def test_argv_typo_is_a_named_skip_but_a_queue_id_is_always_carded() -> None:
    # Both directions of "no silent nothing": an argv path with nothing to report is a named
    # skip and no page; the SAME empty dir named by the queue keeps its row — the queue is the
    # deliverable and position is information.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        empty = root / "vidEMPTY000"
        (empty / "segments").mkdir(parents=True)
        out = root / "r.html"
        code, log = _report([str(empty), "--config", str(_cfg(root)), "--out", str(out)])
        assert code == 0
        assert "nothing to render" in log and "skipped (nothing to report)" in log
        assert "vidEMPTY000" in log
        assert not out.exists()                         # nothing renderable → no page
        q = _queue(root, ["vidEMPTY000"])
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "не скачано" in page and "не скачано" in log


def test_empty_sentences_renders_a_zero_card_not_a_skip() -> None:
    # A MISSING sentences.json is a typo'd path, but an EMPTY one PARSED, so transcribe RAN and
    # found nothing — a real promotion answer (don't dub it). The count is reported, never
    # suppressed. (Reachable: resegment([]) → [] under vad_filter=True on a speech-free video.)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vidEMPTY000", n=0, info=False, summary="Пустой транскрипт.")
        q = _queue(root, ["vidEMPTY000"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "предложений: 0" in page
    assert "не отсканировано" in page                   # a scout STATE, not a typo'd path
    assert "nothing to render" not in log


def test_pending_card_names_the_promoted_state() -> None:
    # source.mkv + a partial translation.jsonl is a full run parked at (or killed in) the
    # translate seam — route B step 1 parks the WHOLE batch like this. The retired triage page
    # SKIPPED it and the old scout page mislabelled it "не отсканировано"; the merged page
    # closes that promoted-video-invisible gap with an honest state, and still fabricates no
    # dub chip for it.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = _transcribed(root, "vidPARKED00", n=1, summary="prose", mkv=True)
        (wd / "translation.jsonl").write_text('{"id": 0}\n', encoding="utf-8")
        q = _queue(root, ["vidPARKED00"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "в работе — скачано полностью, перевод ещё не начат" in page
    assert "в работе" in log                            # and the operator is told
    assert "слушать" not in page and "чисто" not in page
    assert "не отсканировано" not in page               # never mislabelled as an S2 gap


def test_scout_card_duration_falls_back_to_sentence_ends() -> None:
    # No info.json sidecar → the duration comes from the last sentence `end` (431 s → 7:11),
    # the title falls back to the id, and nothing crashes.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001", info=False, summary="s")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "7:11" in page                               # 431 s of sentences, not the sidecar
    assert "предложений: 431" in page
    assert "Scouted Talk" not in page                   # no sidecar → no title, and no crash


def test_scout_card_without_any_duration_shows_a_dash_not_none() -> None:
    # Neither a sidecar nor a numeric sentence `end`: the duration is unknown, and the page's
    # convention for unknown is '—' — never a fabricated figure and never the literal "None".
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001", info=False, ends=False, summary="s")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    card = _card_of(page, 1)
    assert "предложений: 431" in card                   # the card still renders
    assert "None" not in card


def test_ungraded_scout_without_summary_keeps_the_exact_phrase() -> None:
    # A transcribed-but-unsummarized video is a pipeline STATE, not an empty card. The phrase
    # names the exact fix (respawn S2) and is pinned verbatim across the merge.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001")               # no summary.md, no scout.json
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "no summary.md yet — run the scout summarizer (overdub-scout skill, step S2)." in page


# --- audio: embed vs --link (migrated) --------------------------------------------
def test_audio_is_embedded_by_default() -> None:
    # Embedded = the page is portable and publishable; only FLAGGED units pay the base64 cost.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", wav=(0,))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert page.count("data:audio/wav;base64,") == 1    # the one flagged unit, nothing else


def test_link_mode_references_audio_by_relative_path() -> None:
    # --link keeps the page tiny but chains it to work/: the src must be a forward-slash
    # relative path that resolves from the page's own directory under file://.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", wav=(0,))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out), "--link"])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert 'src="vid00000001/segments/00000.wav"' in page
    assert "data:audio/wav" not in page
    assert "linked audio" in log                        # the mode is named on stdout too


def test_missing_wav_names_the_gap_not_a_dead_player() -> None:
    # A flagged unit whose wav is gone gets a note, never a broken <audio> element.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")                    # flagged unit, no wav on disk
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "нет аудио (wav отсутствует)" in page
    assert "<audio" not in page


def test_limit_caps_flagged_units_per_video() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=("low_similarity", "low_similarity"))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out),
                 "--limit", "1"])
        page = out.read_text(encoding="utf-8")
    assert page.count('class="unit"') == 1


def test_triage_nav_links_flagged_videos_and_is_absent_when_clean() -> None:
    # The morning-listen job moved from re-sorting the queue to a nav block of anchors: the
    # worst videos are one click away and the queue keeps its order. A clean batch gets none.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vidFLAGGED0")
        _dubbed(root, "vidCLEAN000", verify_flags=(None, None))
        q = _queue(root, ["vidFLAGGED0", "vidCLEAN000"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
        nav = page.split('<div class="nav">', 1)[1].split("</div>", 1)[0]
        assert "Требуют прослушивания:" in nav
        assert 'href="#v1"' in nav and "Dub Talk" in nav
        assert 'href="#v2"' not in nav                  # the clean video earns no anchor
        # and a fully clean batch renders no nav at all
        q2 = _queue(root, ["vidCLEAN000"])
        out2 = root / "r2.html"
        _report(["--queue", str(q2), "--config", str(_cfg(root)), "--out", str(out2)])
        page2 = out2.read_text(encoding="utf-8")
    assert "Требуют прослушивания" not in page2


# --- cross-surface divergence (the acceptance test for PLAN item 2) ----------------
def test_the_two_surfaces_print_identical_batch_cells() -> None:
    # ONE dub workdir, BOTH renderers: the ten data cells of the batch row must be IDENTICAL
    # strings, and both headers must come from runreport.BATCH_COLUMNS. This is the whole point
    # of the merge — the digest and the page can no longer disagree about the same bytes.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])
        cfgp = _cfg(root)
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert run_report.main(["--queue", str(q), "--config", str(cfgp)]) == 0
        digest = buf.getvalue()
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(cfgp), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert " | ".join(lbl for _k, lbl in runreport.BATCH_COLUMNS) in digest
    for _k, lbl in runreport.BATCH_COLUMNS:
        assert f"<th>{html.escape(lbl)}</th>" in page
    row_line = next(ln for ln in digest.splitlines() if ln.startswith("vid00000001 | "))
    digest_cells = row_line.split(" | ")[2:-1]          # video, title | TEN CELLS | triage
    page_cells = _dub_row_cells(page, 1)
    assert len(digest_cells) == len(page_cells) == 10
    assert digest_cells == page_cells


def test_card_rollup_shows_actionable_never_flagged() -> None:
    # The original two-numbers-one-batch bug, pinned forever: the retired page printed
    # completeness.n_flagged where the digest printed n_actionable (+n_advisory). The merged
    # card must show the split — never the pooled count.
    run_json = {
        "video_id": "vid00000001", "title": "T", "needs_triage": True,
        "timings": {"total_wall_s": 60.0, "rtf": 0.2, "video_sec": 300.0,
                    "video_sec_source": "info_json"},
        "asr": {"floor_ratio": 0.01},
        "translate": {"n_failed": 0, "n_sentences": 10},
        "verify": {"n_flagged": 0},
        "completeness": {"n_flagged": 8, "n_actionable": 3, "n_advisory": 5},
        "speed": {"median": 1.0, "p95": 1.1, "max": 1.2, "n_over_1_8": 0},
        "source": {"scanned": True, "n_flagged": 0},
    }
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = root / "vid00000001"
        (wd / "segments").mkdir(parents=True)
        (wd / "report.json").write_text(json.dumps({"segments": []}), encoding="utf-8")
        (wd / "run.json").write_text(json.dumps(run_json), encoding="utf-8")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        card = _card_of(out.read_text(encoding="utf-8"), 1)
    assert "completeness 3 (+5 advisory)" in card
    assert "completeness 8" not in card


def test_torn_rollup_beside_a_grade_still_counts_as_without_rollup() -> None:
    # A scouted-then-dubbed video whose run.json failed to build (torn report.json) used to let
    # the surviving grade chip win the row: the «без свода» state vanished from the tally and the
    # unfinished list (both key on `e["v"] is _NO_ROLLUP`), a silent failure. The torn dub layer
    # is the news — it must claim the v-slot and be counted, with the grade chip riding beside it.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "high")              # valid scout.json + sentences/info
        (root / "vid00000001" / "report.json").write_text("{not json", encoding="utf-8")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "без свода: 1" in page                          # the page tally counts it
    assert "без свода" in log                               # stdout unfinished list names it
    card = _card_of(page, 1)
    assert '<span class="chip v-none">без свода</span>' in card   # the state chip is on the card
    assert "высокое" in card                               # ...beside the surviving grade chip


def test_duration_ladder_reads_scout_json_before_sentence_ends() -> None:
    # With no info.json, the digest re-derived duration from sentence ends while the card read
    # scout.json's duration_sec — two durations for one dir. collect_entries now reads the SAME
    # scout.json number the card does, so both surfaces show one duration.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        vid = "vid00000001"
        wd = root / vid
        (wd / "segments").mkdir(parents=True)
        (wd / "sentences.json").write_text(json.dumps(
            [{"id": 0, "text": "s", "start": 0.0, "end": 30.5}]), encoding="utf-8")
        # scout.json carries duration_sec=300; NO info.json; sentence ends top out at 30.5
        (wd / "scout.json").write_text(json.dumps(
            {**_DRAFT, "video_id": vid, "quality": "high", "duration_sec": 300.0,
             "n_sentences": 1, "timings": {}, "wave": None}, ensure_ascii=False),
            encoding="utf-8")
        q = _queue(root, [vid])
        cfgp = _cfg(root)
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert run_report.main(["--queue", str(q), "--config", str(cfgp)]) == 0
        digest = buf.getvalue()
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(cfgp), "--out", str(out)])
        card = _card_of(out.read_text(encoding="utf-8"), 1)
    assert "5 min" in digest              # 300 s from scout.json, not the 30.5-derived "1 min"
    assert "1 min" not in digest
    assert "5:00" in card                 # and the card shows the same 300 s


# --- migrated pins re-asserted against the merged page ----------------------------
def test_ungraded_scout_summary_is_rendered_and_escaped() -> None:
    # T1: an ungraded scout card (sentences + summary.md, NO scout.json) still renders its prose,
    # and that prose is raw LLM output going into HTML — a stray tag must never render live.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001",
                     summary="Опасно <script>alert(1)</script> & прочее.\n\nВторой абзац.")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        card = _card_of(out.read_text(encoding="utf-8"), 1)
    assert "&lt;script&gt;" in card and "&amp;" in card
    assert "<script>" not in card                          # never the live tag
    assert "Второй абзац." in card                         # the prose is visible


def test_no_duration_card_renders_no_clock_at_all() -> None:
    # T2: neither info.json nor a numeric sentence `end` nor a scout duration — the duration is
    # unknown, and the page's convention for unknown is '—'. Stronger than "no literal None":
    # forbid the rendered clock SHAPE (M:SS / H:MM:SS), which is what a fabricated duration is.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001", info=False, ends=False, summary="s")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        card = _card_of(out.read_text(encoding="utf-8"), 1)
    assert "предложений: 431" in card                      # the card still renders
    assert not re.search(r"\d+:\d\d", card)                # no fabricated clock anywhere on it
    assert "—" in card                                     # the unknown-duration dash instead


def test_transcript_only_card_takes_duration_from_info_json() -> None:
    # T3: with an info.json sidecar present, a transcript-only (ungraded scout) card shows the
    # clock-formatted info duration — the old "42 min" pin, now the merged card's clock 42:10.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001", summary="s")     # info=True → duration 2530.0
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        card = _card_of(out.read_text(encoding="utf-8"), 1)
    assert "42:10" in card                                 # 2530 s from info.json, clock-formatted


def test_srcanom_item_renders_the_sentence_id() -> None:
    # T4: the source-anomaly block prints the offending sentence id (the old "#19" pin) so the
    # operator can find it in translation.json / the transcript.
    translation = [
        {"id": 19, "status": "ok", "src_en": "EN", "text_ru": "РУ", "text_tts": "т",
         "start": 0.0, "end": 3.0, "src": "truncated", "src_note": "ends mid-thought"},
        {"id": 1, "status": "ok", "src_en": "EN 1", "text_ru": "РУ 1", "text_tts": "т 1",
         "start": 3.0, "end": 6.0, "src": "ok"}]
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=(None, None), translation=translation)
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    block = page.split('<div class="srcanom">', 1)[1].split("</div>", 1)[0]
    assert "#19" in block and "truncated" in block


def test_scouted_clause_absent_on_a_scout_free_report() -> None:
    # T5 (absence direction): a report with no scout entries must not print a "scouted" clause on
    # stdout — the count only appears when scouts are actually present.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=(None, None))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
    assert code == 0
    assert "scouted" not in log


# --- new pins mutation testing proved unguarded ----------------------------------
def test_flagged_unit_embeds_a_playable_source_in_both_modes() -> None:
    # T6: a flagged unit's raw segment wav is playable from the card — a base64 data URI by
    # default, a relative path under --link with no base64. A real (tiny) WAV, so the payload is a
    # decodable file rather than arbitrary bytes.
    import wave
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = _dubbed(root, "vid00000001", wav=())          # flagged unit 0; write its wav below
        with wave.open(str(wd / "segments" / "00000.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 160)               # 10 ms of silence
        q = _queue(root, ["vid00000001"])
        cfgp = _cfg(root)
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(cfgp), "--out", str(out)])
        embedded = out.read_text(encoding="utf-8")
        out2 = root / "r2.html"
        _report(["--queue", str(q), "--config", str(cfgp), "--out", str(out2), "--link"])
        linked = out2.read_text(encoding="utf-8")
    assert "data:audio/wav;base64," in embedded
    assert 'src="vid00000001/segments/00000.wav"' in linked
    assert "data:audio/wav" not in linked


def test_dub_table_colours_the_status_cell_by_column_key_not_index() -> None:
    # T7: the triage colour class rides the «слушать»/«чисто» STATUS cell, keyed by column KEY —
    # never by cell index. The retired page hard-coded the index and the src column silently
    # landed on it, so adding a column mis-coloured a data cell. The status cell carries
    # t-triage/t-clean; the first data cell (wall_s) must not.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")                       # flagged → needs triage → «слушать»
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    row = re.search(r'<td><a class="jump" href="#v1">[^<]*</a></td>(.*?)</tr>', page, re.S).group(1)
    assert '<td class="t-triage">слушать</td>' in row       # the STATUS cell carries the colour
    # the first data cell (wall_s) is a plain num cell — the colour did not land on it by index
    first_cell = re.search(r'<td class="num">[^<]*</td>', row).group(0)
    assert "t-triage" not in first_cell and "t-clean" not in first_cell


if __name__ == "__main__":
    mod = sys.modules[__name__]
    tests = [(n, getattr(mod, n)) for n in dir(mod) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"all scout-report tests passed ({len(tests)})")
