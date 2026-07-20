"""Unit tests for scripts/build_scout.py + scripts/scout_report.py — the route-C report.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_scout_report.py   (or via pytest)

Pure string assembly and JSON over tmp dirs: no GPU, no network, no media, no yt-dlp. The
load-bearing invariants, in the order they would silently break the deliverable:

  ORDER IS THE QUEUE'S. The report exists to be read next to the playlist it came from, so a
  re-sorted row is a wrong row even when every field in it is right. Verdicts are shown, never
  sorted on — the opposite of triage_html, which sorts the worst first on purpose.

  A QUEUED VIDEO NEVER VANISHES. No scout.json → an explicit "не отсканировано" row, because a
  report that silently renders only the videos that worked reads as complete.

  THE VERDICT IS NEVER GUESSED. An unknown verdict is fatal in the helper (it is what the page
  colours and recommends on), unlike the anomaly labels build_translation clamps.

  PROSE IS ESCAPED. one_liner/paragraph/title are raw LLM or YouTube text going into HTML.

  AN UNKNOWN TIMING IS NOT A ZERO. A draft carried over from an earlier wave has no measurable
  summarize time; reporting 0 s would understate the pass and read as measured.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import build_scout  # noqa: E402
import scout_report  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

_DRAFT = {"verdict": "watch", "attention": "focus", "one_liner": "Однофразовое описание.",
          "reason": "Тема в активной работе, автор с позицией.",
          "paragraph": "Развёрнутый абзац о том, что разобрано в видео."}


def _workdir(root: Path, vid: str, *, draft=None, title=None, duration=734,
             stages=None) -> WorkDir:
    """A scouted workdir: sentences.json + info.json + timings.json + the sub-agent's draft.
    Mirrors exactly what --scout followed by an S2 sub-agent leaves on disk."""
    d = root / vid
    (d / "segments").mkdir(parents=True, exist_ok=True)
    (d / "sentences.json").write_text(json.dumps(
        [{"id": 0, "text": "One.", "start": 0.0, "end": 3.5},
         {"id": 1, "text": "Two.", "start": 3.5, "end": 9.0}]), encoding="utf-8")
    info = {"title": title if title is not None else f"Title {vid}"}
    if duration is not None:
        info["duration"] = duration
    (d / "source.info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    (d / "timings.json").write_text(json.dumps(
        {"stages": stages if stages is not None else {"download": 12.4, "transcribe": 88.1}}),
        encoding="utf-8")
    if draft is not None:
        (d / "scout.draft.json").write_text(json.dumps(draft, ensure_ascii=False),
                                            encoding="utf-8")
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
    assert doc["verdict"] == "watch"
    assert doc["video_id"] == "vid00000001"
    assert doc["duration_sec"] == 734 and doc["duration_source"] == "info_json"
    assert doc["n_sentences"] == 2
    assert doc["timings"]["download_sec"] == 12.4
    assert doc["timings"]["transcribe_sec"] == 88.1


def test_unknown_verdict_is_fatal() -> None:
    # Clamping to "maybe" would silently downgrade a video the summarizer rated "watch".
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft={**_DRAFT, "verdict": "смотреть"})
        try:
            _build(w)
        except SystemExit as e:
            assert "verdict" in str(e.code)
        else:
            raise AssertionError("an unknown verdict must exit, never be clamped")


def test_missing_or_unknown_attention_is_fatal() -> None:
    # The cost axis is REQUIRED: the profile schedules against deep-attention slots, so a video
    # with no cost label cannot be placed. An optional field would go missing exactly when the
    # summarizer was least sure — which is when it matters most.
    for bad in (None, "deep", ""):
        draft = {k: v for k, v in _DRAFT.items() if k != "attention"}
        if bad is not None:
            draft["attention"] = bad
        with tempfile.TemporaryDirectory() as d:
            w = _workdir(Path(d), "vid00000001", draft=draft)
            try:
                _build(w)
            except SystemExit as e:
                assert "attention" in str(e.code)
            else:
                raise AssertionError(f"attention={bad!r} must exit")


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


def test_the_wave_is_stored_as_raw_stamps_never_a_per_video_duration() -> None:
    # Measured 2026-07-20: 500 sentences reported 1506 s and 31 sentences 1252 s — every agent
    # was reporting the WAVE's length, not its own cost, so a per-video duration was data that
    # was not there. Two timestamps are facts; the duration was a wrong inference.
    start = time.time() - 40
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_DRAFT)
        doc = _build(w, wave_start=start)
    assert "summarize_sec" not in doc["timings"]
    assert doc["wave"]["start"] == round(start, 1)
    assert doc["wave"]["draft_at"] >= doc["wave"]["start"]


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
def _scouted(root: Path, vid: str, verdict: str, **kw) -> None:
    w = _workdir(root, vid, draft={**_DRAFT, "verdict": verdict, **kw})
    (root / vid / "scout.json").write_text(
        json.dumps(_build(w), ensure_ascii=False), encoding="utf-8")


def test_rows_follow_the_queue_not_the_verdict() -> None:
    # The whole point: "skip" first in the queue stays first on the page.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "skip", one_liner="Первое в очереди.")
        _scouted(root, "vid00000002", "watch", one_liner="Второе в очереди.")
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
        _scouted(root, "vid00000001", "watch")
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
        _scouted(root, "vid00000001", "watch")                   # complete
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
        _scouted(root, "vid00000001", "watch")
        # vid00000002 missing entirely
        _scouted(root, "vid00000003", "skip")
        q = _queue(root, ["vid00000001", "vid00000002", "vid00000003"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert '<td class="idx">2</td>' in page                       # the gap keeps its number
    assert page.index('<td class="idx">1</td>') < page.index('<td class="idx">3</td>')


def test_queue_runtime_is_reported_and_build_time_is_not() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch")                    # duration 734 from info.json
        _scouted(root, "vid00000002", "skip")
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
        _scouted(root, "vid00000001", "watch")
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
                     draft={k: v for k, v in _DRAFT.items() if k != "reason"})
        try:
            _build(w)
        except SystemExit as e:
            assert "reason" in str(e.code)
        else:
            raise AssertionError("a missing reason must exit")
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert page.count("Тема в активной работе, автор с позицией.") == 2   # table + card
    assert "Однофразовое описание." in page                               # still its own field
    assert "<th>Почему</th>" in page


def test_title_links_to_the_video_in_both_lists() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch")
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


def test_the_two_lists_link_to_each_other() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch")
        _scouted(root, "vid00000002", "skip")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    for n in (1, 2):
        assert f'<tr id="r{n}">' in page and f'href="#v{n}"' in page      # row → card
        assert f'id="v{n}"' in page and f'href="#r{n}"' in page           # card → row


def test_playlist_header_is_named_and_linked() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch")
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
        _scouted(root, "vid00000001", "watch")
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
        _scouted(root, "vid00000001", "watch")
        (root / "vid00000001" / "thumb.jpg").write_bytes(b"\xff\xd8\xff\xdb-fake-jpeg")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert page.count("data:image/jpeg;base64,") == 2          # table row + card
    assert "i.ytimg.com" not in page


def test_a_missing_thumbnail_renders_nothing_at_all() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch")                 # no thumb.jpg written
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "<img" not in page and "base64" not in page


def test_verdict_cost_and_runtime_share_one_cell_and_carry_the_jump() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch", attention="focus")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    row = page[page.index('<tr id="r1">'):page.index("</tr>", page.index('<tr id="r1">'))]
    assert 'href="#v1"' in row                                  # the jump moved onto the block
    for txt in ("точно смотреть", "концентрация", "12:14"):
        assert txt in row
    assert row.count("<td") == 5                                # idx, meta, name, о чём, почему


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
        for i, v in enumerate(("watch", "maybe", "skip"), 1):
            _scouted(root, f"vid0000000{i}", v)
        q = _queue(root, ["vid00000001", "vid00000002", "vid00000003"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    for cls in ("v-watch", "v-maybe", "v-skip"):
        assert f'chip {cls}' in page and f'card {cls}' in page


def test_attention_renders_as_a_quiet_tag_in_both_lists() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch", attention="focus")
        _scouted(root, "vid00000002", "maybe", attention="background")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert page.count("концентрация") == 2 and page.count("фоновое") == 2   # table + card
    assert "tag a-focus" in page
    # the cost axis must not borrow the verdict's colour classes — one coloured scale per page
    assert "tag v-watch" not in page


def test_trusted_author_marker_only_when_assessed() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch")                      # no author key
        _scouted(root, "vid00000002", "watch", author="trusted")
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


def test_a_scout_json_without_the_cost_axis_still_renders() -> None:
    # Forward-compat in the renderer only: build_scout REQUIRES the field from now on, but a
    # report must never crash on an artifact written by an older build.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        w = _workdir(root, "vid00000001", draft=_DRAFT)
        doc = _build(w)
        doc.pop("attention")
        (root / "vid00000001" / "scout.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0 and "точно смотреть" in page


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
        _scouted(root, "vid00000001", "watch")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    low = page.lower()
    for tag in ("<!doctype", "<html", "<head>", "<body"):
        assert tag not in low
    assert "<style>" in low                    # but it IS self-contained


def test_both_themes_are_defined() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _scouted(root, "vid00000001", "watch")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "prefers-color-scheme:dark" in page
    assert '[data-theme="dark"]' in page and '[data-theme="light"]' in page


# --- the timing strip must not lie ---------------------------------------------
def test_stage_totals_sum_and_the_wave_is_a_window_across_the_queue() -> None:
    entries = [
        {"timings": {"download_sec": 10.0, "transcribe_sec": 100.0},
         "wave": {"start": 1000.0, "draft_at": 1030.0}},
        {"timings": {"download_sec": 20.0, "transcribe_sec": 200.0},
         "wave": {"start": 1002.0, "draft_at": 1050.0}},
    ]
    t = scout_report.totals_of(entries)
    assert t["download"] == 30.0 and t["transcribe"] == 300.0
    # last draft (1050) minus FIRST start (1000) — the wave's wall clock, not any one agent's
    assert t["summarize"] == 50.0
    # deliberately no grand total: adding two sums to a wall clock produced a figure that was
    # neither the work done nor the elapsed time
    assert "total" not in t


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


if __name__ == "__main__":
    mod = sys.modules[__name__]
    tests = [(n, getattr(mod, n)) for n in dir(mod) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"all scout-report tests passed ({len(tests)})")
