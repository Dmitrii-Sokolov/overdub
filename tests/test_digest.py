"""Unit tests for scripts/build_digest.py + scripts/digest_report.py — route D, the digest page.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_digest.py   (or via pytest)

Pure string assembly and JSON over tmp dirs: no GPU, no network, no media, no yt-dlp, no model.

The load-bearing invariants, in the order they would silently break the deliverable:

  A MISSING PIECE OF THE DOCUMENT IS FATAL, A LONG ONE IS NOT. The page renders all five fields for
  every video, so an empty one is a hole in the deliverable and the sub-agent has to be re-run. A
  verbose writer is a style problem: truncate, warn, keep the video.

  POINTS ARE THE ARTIFACT. Route D exists to answer "what is covered", so a malformed item is fatal
  rather than skipped — silently dropping one produces a digest that is short by exactly the topic
  the reader was trying not to miss. The 3..8 band is editorial and only warns.

  A TIMESTAMP IS NAVIGATION, SO IT MUST BE REAL. An unparseable marker is dropped; one past the end
  of the video is dropped as fabricated and said out loud. A digest whose last marker sits in the
  first 60% of the runtime is warned about — that is the "I read the opening and stopped" failure,
  and it is invisible on the page.

  AN UNKNOWN TIMING IS NOT A ZERO. An agent that wrote no marker has no measurable window; the wave
  becomes a floor rather than a smaller measured number.

  A QUEUED VIDEO NEVER VANISHES, and the three unfinished states stay three. Each needs a different
  action (re-fetch / look at transcribe / respawn the sub-agent), so collapsing them hides which.

  ORDER IS THE QUEUE'S, and the page grades nothing: no verdict chip on a finished row, ever.

  PROSE IS ESCAPED. headline/thesis/points/title are raw LLM or YouTube text going into HTML.
"""

from __future__ import annotations

import html
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import build_digest  # noqa: E402
import digest_report  # noqa: E402
import scout_report  # noqa: E402  — the wave math is shared; one test pins the key it reads
from overdub.workdir import WorkDir  # noqa: E402

_DRAFT = {
    "headline": "Подкаст, ~59 мин: трое исследователей о том, что внутри модели.",
    "thesis": "Центральный тезис: «предсказание следующего слова» — верное, но бесполезное "
              "описание.",
    "points": [
        {"title": "Обобщение вместо запоминания", "at": "6:12",
         "text": "Контур «6+9» срабатывает и в арифметике, и при вычислении года выпуска."},
        {"title": "Язык мысли",
         "text": "Концепт «большой» общий для английского, французского и японского."},
        {"title": "Планирование вперёд", "at": "31:40",
         "text": "В рифмованном двустишии модель выбирает финальную рифму заранее."},
    ],
    "context": "Зачем: детектировать намерения до их реализации.\n\nОговорка: «микроскоп» "
               "работает примерно в 20% случаев.",
    "not_covered": "Нужны детали экспериментов и живая дискуссия — аргументация обеих позиций в "
                   "пересказ не вошла.",
}


def _draft(**over) -> dict:
    d = json.loads(json.dumps(_DRAFT))       # deep copy: tests mutate points
    d.update(over)
    return d


def _workdir(root: Path, vid: str, *, draft=None, title="Заголовок видео", channel="Канал",
             upload="20260712", duration=3600, sentences=2, stages=None, detail=None,
             started_ago=None) -> WorkDir:
    """A transcribed workdir plus (optionally) the sub-agent's draft — exactly what D1 followed by
    a D2 sub-agent leaves on disk. `started_ago` writes digest.started that many seconds before
    the draft, i.e. what the marker means."""
    d = root / vid
    (d / "segments").mkdir(parents=True, exist_ok=True)
    sents = [{"id": i, "text": f"Sentence {i}.", "start": i * 30.0, "end": i * 30.0 + 25.0}
             for i in range(sentences)]
    (d / "sentences.json").write_text(json.dumps(sents), encoding="utf-8")
    info = {}
    if title is not None:
        info["title"] = title
    if channel is not None:
        info["channel"] = channel
    if upload is not None:
        info["upload_date"] = upload
    if duration is not None:
        info["duration"] = duration
    (d / "source.info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    doc = {"stages": stages if stages is not None else {"download": 9.1, "transcribe": 74.6}}
    if detail is not None:
        doc["detail"] = detail
    (d / "timings.json").write_text(json.dumps(doc), encoding="utf-8")
    if draft is not None:
        (d / "digest.draft.json").write_text(json.dumps(draft, ensure_ascii=False),
                                             encoding="utf-8")
        if started_ago is not None:
            marker = d / "digest.started"
            marker.write_text("", encoding="utf-8")
            at = os.path.getmtime(d / "digest.draft.json")
            os.utime(marker, (at - started_ago, at - started_ago))
    return WorkDir(d)


def _build(work: WorkDir, wave_start=None) -> tuple[dict, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        doc = build_digest.build(work, wave_start)
    return doc, buf.getvalue()


def _fails(work: WorkDir) -> str:
    """The FAIL message, asserted rather than just 'it raised': every guarded path ends in
    sys.exit(), so 'SystemExit' alone is true whether or not the intended guard fired."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            build_digest.build(work, None)
    except SystemExit as e:
        return str(e)
    raise AssertionError("expected build_digest to fail")


def _cfg(root: Path) -> Path:
    c = root / "overdub.toml"
    c.write_text(f'work_root = "{root.as_posix()}"\n', encoding="utf-8")
    return c


def _queue(root: Path, ids: list[str]) -> Path:
    q = root / "queue.txt"
    q.write_text("\n".join(f"https://www.youtube.com/watch?v={i}" for i in ids) + "\n",
                 encoding="utf-8")
    return q


def _page(root: Path, ids: list[str]) -> tuple[str, str]:
    """Render the page over a queue of ids. Returns (html, stdout)."""
    q, cfg = _queue(root, ids), _cfg(root)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = digest_report.main(["--queue", str(q), "--config", str(cfg)])
    assert code == 0
    return (root / "digest-report.html").read_text(encoding="utf-8"), buf.getvalue()


def _dubbed(root: Path, vid: str, *, title="Dub Talk", duration=300.0) -> Path:
    """A dubbed workdir, trimmed to what the DIGEST page needs from one: classify_workdir → "run"
    and a rollup that build_run_report can actually produce (so the test exercises the REAL data
    path the collector takes, not a hand-shaped run dict). Everything dub-specific is here only
    because the rollup needs it — this page renders none of it, which is what the tests below pin."""
    d = root / vid
    (d / "segments").mkdir(parents=True, exist_ok=True)
    segs = [{"id": 0, "group_id": 0, "status": "ok", "verify_flag": None, "combined_factor": 1.0,
             "speed_factor": 1.0, "assemble_flag": None, "completeness_flags": [],
             "translate_flag": None, "similarity": 0.98, "hypothesis": None}]
    (d / "report.json").write_text(json.dumps({
        "segments": segs,
        "verify": {"model": "small", "n_units": 1, "n_segments": 1, "n_flagged": 0,
                   "n_retried": 0, "n_repaired": 0},
        "completeness": {"n_sentences": 1, "n_flagged": 0, "n_num_loss": 0, "n_neg_loss": 0,
                         "n_entity_loss": 0, "n_length": 0},
        "assemble": {"duration_sec": duration, "n_sped": 0, "in_span_silence_sec": 0.0},
        "mux": {"dub_mix": "bed", "dub_gain_db": 3.0}}), encoding="utf-8")
    (d / "translation.json").write_text(json.dumps(
        [{"id": 0, "status": "ok", "src_en": "EN 0", "text_ru": "РУ 0", "text_tts": "тэ 0",
          "start": 0.0, "end": 3.0, "src": "ok"}], ensure_ascii=False), encoding="utf-8")
    (d / "source.info.json").write_text(json.dumps({"title": title, "duration": duration}),
                                        encoding="utf-8")
    (d / "timings.json").write_text(json.dumps({"stages": {"download": 5.0, "synthesize": 55.0}}),
                                    encoding="utf-8")
    return d


def _digested(root: Path, vid: str, *, draft=None, **kw) -> WorkDir:
    """A workdir carried all the way to digest.json + digest.md, through the real helper."""
    w = _workdir(root, vid, draft=draft if draft is not None else _draft(), **kw)
    buf = io.StringIO()
    with redirect_stdout(buf):
        build_digest.main([str(w.root)])
    return w


# --- build_digest: the document contract --------------------------------------
def test_valid_draft_merges_artifacts() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(), sentences=7)
        doc, _ = _build(w)
        assert doc["video_id"] == "vid00000001"
        assert doc["title"] == "Заголовок видео"
        assert doc["channel"] == "Канал"
        assert doc["upload_date"] == "20260712"
        assert doc["duration_sec"] == 3600.0 and doc["duration_source"] == "info_json"
        assert doc["n_sentences"] == 7
        assert doc["headline"].startswith("Подкаст")
        assert [p["title"] for p in doc["points"]] == [
            "Обобщение вместо запоминания", "Язык мысли", "Планирование вперёд"]
        assert doc["timings"]["download_sec"] == 9.1
        assert doc["timings"]["transcribe_sec"] == 74.6


def test_uploader_is_the_channel_fallback() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(), channel=None)
        (w.root / "source.info.json").write_text(
            json.dumps({"title": "T", "uploader": "Кто-то", "duration": 600},
                       ensure_ascii=False), encoding="utf-8")
        doc, _ = _build(w)
        assert doc["channel"] == "Кто-то"


def test_absent_metadata_is_none_never_invented() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(),
                     title=None, channel=None, upload=None, duration=None, sentences=4)
        doc, _ = _build(w)
        assert doc["title"] is None and doc["channel"] is None and doc["upload_date"] is None
        # the fallback is the last sentence's end (a FLOOR on the runtime), and it says so
        assert doc["duration_source"] == "sentences" and doc["duration_sec"] == 115.0


def test_malformed_upload_date_is_dropped() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(), upload="12 июля 2026")
        doc, _ = _build(w)
        assert doc["upload_date"] is None


def test_every_prose_field_is_required() -> None:
    for key in ("headline", "thesis", "context", "not_covered"):
        with tempfile.TemporaryDirectory() as d:
            bad = _draft()
            del bad[key]
            w = _workdir(Path(d), "vid00000001", draft=bad)
            msg = _fails(w)
            assert key in msg and "missing or empty" in msg


def test_blank_field_is_as_fatal_as_a_missing_one() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(thesis="   \n  "))
        assert "thesis" in _fails(w)


def test_overlong_field_is_capped_not_fatal() -> None:
    with tempfile.TemporaryDirectory() as d:
        long = "я" * (build_digest._HEADLINE_MAX + 60)
        w = _workdir(Path(d), "vid00000001", draft=_draft(headline=long))
        doc, out = _build(w)
        assert "[truncated]" in doc["headline"]
        assert len(doc["headline"]) <= build_digest._HEADLINE_MAX + 20
        assert "capped at" in out


def test_headline_is_collapsed_to_one_line() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(headline="Подкаст,\n  ~59 мин"))
        doc, _ = _build(w)
        assert doc["headline"] == "Подкаст, ~59 мин"


def test_paragraph_breaks_survive_in_prose_fields() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft())
        doc, _ = _build(w)
        # the writer's own structure: the renderer honours blank lines and never invents them
        assert "\n\n" in doc["context"]


def test_draft_must_be_an_object() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft())
        (w.root / "digest.draft.json").write_text('[{"id": 0}]', encoding="utf-8")
        msg = _fails(w)
        assert "not a JSON object" in msg and "headline" in msg


def test_missing_draft_is_fatal() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001")
        assert "did not finish" in _fails(w)


def test_missing_transcript_is_fatal() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft())
        w.sentences.unlink()
        msg = _fails(w)
        assert "no transcript" in msg and "D1" in msg


# --- build_digest: points, the field the route exists for ---------------------
def test_points_must_be_a_nonempty_list() -> None:
    for bad in ([], {}, "три пункта", None):
        with tempfile.TemporaryDirectory() as d:
            w = _workdir(Path(d), "vid00000001", draft=_draft(points=bad))
            assert "'points' must be a non-empty JSON list" in _fails(w)


def test_malformed_point_is_fatal_never_skipped() -> None:
    with tempfile.TemporaryDirectory() as d:
        pts = _DRAFT["points"] + [{"title": "Без текста"}]
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=pts))
        msg = _fails(w)
        assert "text" in msg and "missing or empty" in msg
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=["строка"]))
        assert "expected an object" in _fails(w)


def test_too_few_points_warns_but_keeps_the_digest() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=_DRAFT["points"][:2]))
        doc, out = _build(w)
        assert len(doc["points"]) == 2 and "asks for at least 3" in out


def test_the_point_ladder_is_checked_against_the_runtime() -> None:
    """A flat 3..8 band let 6 points through on an 8-minute news segment (first real wave,
    2026-07-30) — inside the band, so nothing fired, while the ladder asks for 3-4 there. Padding is
    a ratio of points to material, so the ceiling has to know the runtime."""
    six = [{"title": f"Пункт {i}", "text": "Текст."} for i in range(6)]
    with tempfile.TemporaryDirectory() as d:                       # 8 min → ceiling 4
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=six), duration=8 * 60)
        doc, out = _build(w)
        assert len(doc["points"]) == 6                              # warned, never rejected
        assert "6 points for a 8-minute video" in out and "at most 4" in out
    with tempfile.TemporaryDirectory() as d:                       # 90 min → ceiling 6, silent
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=six), duration=90 * 60)
        _, out = _build(w)
        assert "usually padding" not in out
    with tempfile.TemporaryDirectory() as d:                       # 3 h → ceiling 8, silent
        eight = [{"title": f"Пункт {i}", "text": "Текст."} for i in range(8)]
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=eight), duration=3 * 3600)
        _, out = _build(w)
        assert "usually padding" not in out


def test_unknown_duration_gets_the_top_of_the_ladder() -> None:
    with tempfile.TemporaryDirectory() as d:
        # no info.json duration and no sentence ends → nothing to compare against, so a padding
        # warning would be a guess. Six points must pass silently.
        six = [{"title": f"Пункт {i}", "text": "Текст."} for i in range(6)]
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=six), duration=None)
        (w.root / "sentences.json").write_text(
            json.dumps([{"id": 0, "text": "S."}]), encoding="utf-8")
        doc, out = _build(w)
        assert doc["duration_sec"] is None and "usually padding" not in out


def test_a_transcript_pasted_back_as_bullets_is_fatal() -> None:
    with tempfile.TemporaryDirectory() as d:
        pts = [{"title": f"Пункт {i}", "text": "Текст."} for i in range(25)]
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=pts))
        assert "that is a transcript, not a digest" in _fails(w)


def test_at_sec_parses_only_real_timecodes() -> None:
    assert build_digest.at_sec("6:12") == 372
    assert build_digest.at_sec("0:00") == 0
    assert build_digest.at_sec("1:02:30") == 3750
    for bad in ("6:99", "1:70:00", "612", "", "6:1", "около 6:12", None, 372):
        assert build_digest.at_sec(bad) is None


def test_timestamps_are_kept_with_their_seconds() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(), duration=7200)
        doc, _ = _build(w)
        assert doc["points"][0]["at"] == "6:12" and doc["points"][0]["at_sec"] == 372
        assert "at" not in doc["points"][1]                  # optional, absent stays absent


def test_unparseable_timestamp_is_dropped_with_a_warning() -> None:
    with tempfile.TemporaryDirectory() as d:
        pts = json.loads(json.dumps(_DRAFT["points"]))
        pts[0]["at"] = "около 6 минут"
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=pts))
        doc, out = _build(w)
        assert "at" not in doc["points"][0]
        assert "not M:SS" in out
        assert doc["points"][0]["text"]                      # the point itself survives


def test_timestamp_past_the_end_is_dropped_as_fabricated() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(), duration=600)
        doc, out = _build(w)
        # 6:12 is inside 10 minutes, 31:40 is not
        assert doc["points"][0]["at"] == "6:12"
        assert "at" not in doc["points"][2]
        assert "fabricated" in out


def test_slack_covers_a_duration_derived_from_sentences() -> None:
    with tempfile.TemporaryDirectory() as d:
        # duration floor 115 s; a marker at 1:30 is inside it, 3:00 is inside the slack window
        pts = [{"title": "Начало", "at": "1:30", "text": "Т."},
               {"title": "Конец", "at": "3:00", "text": "Т."},
               {"title": "Мимо", "at": "9:00", "text": "Т."}]
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=pts), duration=None, sentences=4)
        doc, out = _build(w)
        assert doc["points"][0]["at"] == "1:30" and doc["points"][1]["at"] == "3:00"
        assert "at" not in doc["points"][2] and "fabricated" in out


def test_front_loaded_digest_is_warned_about() -> None:
    with tempfile.TemporaryDirectory() as d:
        pts = [{"title": f"Пункт {i}", "at": f"{i}:00", "text": "Текст."} for i in (1, 3, 5)]
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=pts), duration=3600)
        doc, out = _build(w)
        assert "may cover only the opening" in out
        assert len(doc["points"]) == 3                        # warned, never rejected


def test_full_span_digest_is_not_warned_about() -> None:
    with tempfile.TemporaryDirectory() as d:
        pts = [{"title": "Начало", "at": "2:00", "text": "Т."},
               {"title": "Середина", "at": "25:00", "text": "Т."},
               {"title": "Конец", "at": "52:00", "text": "Т."}]
        w = _workdir(Path(d), "vid00000001", draft=_draft(points=pts), duration=3600)
        _, out = _build(w)
        assert "may cover only the opening" not in out


# --- build_digest: timings are stamped, never self-reported -------------------
def test_marker_gives_the_per_video_window() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(), started_ago=42)
        doc, out = _build(w)
        assert doc["timings"]["digest_sec"] == 42.0
        assert "no digest.started" not in out


def test_absent_marker_is_unknown_not_zero() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft())
        doc, out = _build(w)
        assert doc["timings"]["digest_sec"] is None
        assert "no digest.started marker" in out and "becomes a floor" in out


def test_marker_newer_than_the_draft_is_not_one_run() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(), started_ago=-30)
        doc, out = _build(w)
        assert doc["timings"]["digest_sec"] is None
        assert "not one agent's run" in out


def test_wave_stores_raw_stamps_and_flags_a_carry_over() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(), started_ago=10)
        draft_at = os.path.getmtime(w.root / "digest.draft.json")
        doc, out = _build(w, draft_at - 100)
        assert doc["wave"]["draft_at"] == round(draft_at, 1)
        assert "predates the wave start" not in out
        doc2, out2 = _build(w, draft_at + 100)               # draft older than the wave: carried over
        assert "predates the wave start" in out2
        assert doc2["wave"]["start"] == round(draft_at + 100, 1)


def test_no_wave_start_records_unknown_rather_than_guessing() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft())
        doc, _ = _build(w)
        assert doc["wave"] is None


def test_work_sec_and_asr_passes_ride_along_when_measured() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _workdir(Path(d), "vid00000001", draft=_draft(),
                     detail={"transcribe": {"work_sec": 61.2, "asr_passes": 2}})
        doc, _ = _build(w)
        assert doc["timings"]["transcribe_work_sec"] == 61.2
        # a COUNT stays an int: "asr_passes: 2.0" reads as a continuous measurement
        assert doc["timings"]["transcribe_asr_passes"] == 2
        assert isinstance(doc["timings"]["transcribe_asr_passes"], int)


# --- build_digest: the Markdown twin -----------------------------------------
def test_lead_in_adds_one_period_and_never_two() -> None:
    assert build_digest.lead_in("Язык мысли") == "Язык мысли."
    assert build_digest.lead_in("Plan A / Plan B.") == "Plan A / Plan B."
    assert build_digest.lead_in("Думает ли модель?") == "Думает ли модель?"


def test_markdown_matches_the_reference_shape() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _digested(Path(d), "vid00000001")
        md = (w.root / "digest.md").read_text(encoding="utf-8")
        lines = md.splitlines()
        assert lines[0].startswith("**Подкаст") and lines[0].endswith("**")
        assert "Ключевые находки:" in md
        assert "- **Обобщение вместо запоминания.** (6:12) Контур" in md
        assert "- **Язык мысли.** Концепт" in md              # no timestamp, no empty parens
        assert md.rstrip().endswith(_DRAFT["not_covered"])
        assert "**Стоит смотреть, если** Нужны детали" in md
        # no title/URL header: the page owns identity, this file is the document
        assert not md.startswith("#")


def test_build_writes_both_artifacts_atomically() -> None:
    with tempfile.TemporaryDirectory() as d:
        w = _digested(Path(d), "vid00000001")
        assert (w.root / "digest.json").is_file() and (w.root / "digest.md").is_file()
        assert not list(w.root.glob("*.tmp"))
        doc = json.loads((w.root / "digest.json").read_text(encoding="utf-8"))
        assert doc["headline"] and len(doc["points"]) == 3


# --- digest_report: the page --------------------------------------------------
def _table_rows(page: str) -> list[tuple[str, str]]:
    """(row number, row html) in the order the scan TABLE emits them.

    Reading positions out of the whole page cannot tell a re-sorted table from a re-sorted card
    list, and the table is the half a sort would break first. Written after a mutation check found
    the earlier version of these tests blind: every fixture had the same title, so sorting rows by
    title was a no-op and the mutant survived. Distinct titles AND distinct headlines below are
    part of the check, not decoration."""
    body = page.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    rows = []
    for frag in body.split('<tr id="r')[1:]:
        n, rest = frag.split('"', 1)
        rows.append((n, rest))
    return rows


def test_row_order_is_the_queues_order() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        # names chosen so that ANY sort — by title, by headline, alphabetical or reverse — differs
        # from the queue's order
        ids = ["vid00000001", "vid00000002", "vid00000003"]
        names = ["Че", "Ах", "Бэ"]
        for vid, name in zip(ids, names):
            _digested(root, vid, title=f"{name} видео",
                      draft=_draft(headline=f"Заголовок {name}."))
        page, _ = _page(root, ids)
        rows = _table_rows(page)
        assert [n for n, _ in rows] == ["1", "2", "3"]
        for name, (_, row) in zip(names, rows):
            assert f"{name} видео" in row and f"Заголовок {name}." in row
        # the cards follow the same order, and the first occurrence of each headline is its row
        assert page.index("Заголовок Че.") < page.index("Заголовок Ах.")
        assert page.index('id="v1"') < page.index('id="v2"') < page.index('id="v3"')


def test_reversed_queue_reverses_the_page() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        ids = ["vid00000001", "vid00000002"]
        for i, vid in enumerate(ids):
            _digested(root, vid, title=f"Видео {i + 1}",
                      draft=_draft(headline=f"Заголовок {i + 1}."))
        page, _ = _page(root, list(reversed(ids)))
        rows = _table_rows(page)
        assert "Видео 2" in rows[0][1] and "Видео 1" in rows[1][1]
        assert page.index("Заголовок 2.") < page.index("Заголовок 1.")


def test_a_finished_row_carries_no_verdict_chip() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _digested(root, "vid00000001")
        page, _ = _page(root, ["vid00000001"])
        # the tally names the count; nothing on the row or the card wears it as a badge
        assert "пересказано: 1" in page
        assert page.count('class="chip') == 0
        assert "нет пересказа" not in page


def test_themes_cell_lists_what_is_covered() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _digested(root, "vid00000001")
        page, _ = _page(root, ["vid00000001"])
        assert "Обобщение вместо запоминания · Язык мысли · Планирование вперёд" in page
        assert "<th>Темы</th>" in page


def test_long_theme_list_is_truncated_not_dropped() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        pts = [{"title": "Очень длинный заголовок пункта номер " + str(i), "text": "Текст."}
               for i in range(8)]
        _digested(root, "vid00000001", draft=_draft(points=pts))
        page, _ = _page(root, ["vid00000001"])
        assert "Очень длинный заголовок пункта номер 0" in page
        assert " …" in page


def test_card_carries_the_whole_document() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _digested(root, "vid00000001")
        page, _ = _page(root, ["vid00000001"])
        assert "Ключевые находки" in page and "Зачем и оговорки" in page
        assert "<b>Стоит смотреть, если</b>" in page
        for p in _DRAFT["points"]:
            assert html.escape(p["text"]) in page
        assert '<span class="at">6:12</span>' in page
        # the writer's paragraph break in `context` became two paragraphs, not one block
        assert page.count("<p>Зачем: детектировать") == 1
        assert "работает примерно в 20% случаев" in page


def test_meta_line_carries_channel_and_date() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _digested(root, "vid00000001")
        page, _ = _page(root, ["vid00000001"])
        assert "Канал · 2026-07-12 · предложений: 2" in page


def test_prose_is_escaped() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        pts = [{"title": "<b>жирный</b>", "text": 'кавычки "и" <script>alert(1)</script>'},
               {"title": "Второй", "text": "Текст & ещё."},
               {"title": "Третий", "text": "Текст."}]
        _digested(root, "vid00000001",
                  draft=_draft(points=pts, headline="Заголовок <i>с</i> тегами."),
                  title="Название & <b>всё</b>")
        page, _ = _page(root, ["vid00000001"])
        assert "<script>alert(1)</script>" not in page
        assert "&lt;script&gt;" in page
        assert "&lt;i&gt;" in page and "Название &amp; &lt;b&gt;" in page


def test_the_three_unfinished_states_stay_three() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _digested(root, "vid00000001")
        _workdir(root, "vid00000002")                        # transcript, no digest
        (root / "vid00000003" / "segments").mkdir(parents=True)
        (root / "vid00000003" / "source.wav").write_bytes(b"RIFF")   # fetched, not transcribed
        (root / "vid00000004" / "segments").mkdir(parents=True)      # nothing at all
        ids = ["vid00000001", "vid00000002", "vid00000003", "vid00000004"]
        page, out = _page(root, ids)
        for label in ("нет пересказа", "не расшифровано", "не скачано"):
            assert label in page and label in out
        assert "пересказано: 1" in page
        # every queued video is still on the page, in position
        assert all(f'id="v{i}"' in page for i in (1, 2, 3, 4))
        # each state prints the action that clears it
        assert "перезапусти его и пересобери страницу" in out


def test_an_undigested_card_fabricates_nothing() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _workdir(root, "vid00000001")
        page, _ = _page(root, ["vid00000001"])
        assert "Ключевые находки" not in page and "Стоит смотреть" not in page
        assert "нет пересказа" in page
        # with no digest anywhere the scan table is skipped rather than filled with state text
        assert "<th>Темы</th>" not in page


def test_torn_digest_json_reads_as_missing() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        w = _workdir(root, "vid00000001", draft=_draft())
        (w.root / "digest.json").write_text('{"headline": "оборван', encoding="utf-8")
        page, _ = _page(root, ["vid00000001"])
        assert "нет пересказа" in page


def test_a_dubbed_video_with_no_digest_is_a_hole_not_a_dub_row() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        page, out = _page(root, ["vid00000001"])
        # the dub is not this page's subject: a dubbed video with no digest is exactly as
        # unfinished here as an untouched one, and nothing about the dub may stand in for it
        assert "нет пересказа" in page and "нет пересказа" in out
        # tokens that only exist once a page RENDERS the dub layer. Deliberately not bare class
        # names: the shared stylesheet defines .rollup and audio rules for the scout page, so
        # matching those would test the CSS instead of the content (caught writing this test).
        for dub_ish in ("слушать", "чисто", "RTF", "<audio", '<p class="rollup"', "throughput",
                        "translate 1/1"):
            assert dub_ish not in page


def test_a_dubbed_video_with_a_digest_renders_like_any_other() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _digested(root, "vid00000001")
        _dubbed(root, "vid00000001")                 # promoted afterwards: same workdir, now "run"
        page, _ = _page(root, ["vid00000001"])
        assert "пересказано: 1" in page
        assert "Ключевые находки" in page and "Обобщение вместо запоминания" in page
        # the artifact's own title and duration outrank the ones the dub rollup carries
        assert "Заголовок видео" in page and "Dub Talk" not in page
        assert "1:00:00" in page and "5:00" not in page
        for dub_ish in ("слушать", "чисто", "<audio", '<p class="rollup"', "throughput"):
            assert dub_ish not in page


def test_page_is_a_body_fragment() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _digested(root, "vid00000001")
        page, _ = _page(root, ["vid00000001"])
        low = page.lower()
        for tag in ("<!doctype", "<html", "<head>", "<body"):
            assert tag not in low
        assert '<meta charset="utf-8">' in page              # the file also opens by double-click
        assert page.lstrip().startswith("<meta")


def test_timing_strip_reads_the_digest_wave_not_the_scout_one() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        w = _workdir(root, "vid00000001", draft=_draft(), started_ago=90)
        draft_at = os.path.getmtime(w.root / "digest.draft.json")
        buf = io.StringIO()
        with redirect_stdout(buf):
            build_digest.main([str(w.root), "--wave-start", str(draft_at - 120)])
        page, _ = _page(root, ["vid00000001"])
        assert "пересказ, волна" in page
        entries = digest_report._views(
            [{"n": 1, "vid": "vid00000001", "work": w, "kind": "scout", "run": None,
              "summary": None, "n_sentences": 2, "duration_sec": 3600}])
        assert digest_report.totals_of(entries)["summarize"] == 90.0
        # the shared helper keyed on the SCOUT field must find nothing here — the two waves are
        # different measurements and reading the wrong key would silently report 0 videos measured
        assert scout_report.totals_of(entries)["summarize"] is None
        assert scout_report.totals_of(entries)["summarize_unmeasured"] == 1


def test_unmeasured_wave_is_marked_a_floor() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        w1 = _workdir(root, "vid00000001", draft=_draft(), started_ago=60)
        w2 = _workdir(root, "vid00000002", draft=_draft())            # no marker
        draft_at = os.path.getmtime(w1.root / "digest.draft.json")
        for w in (w1, w2):
            buf = io.StringIO()
            with redirect_stdout(buf):
                build_digest.main([str(w.root), "--wave-start", str(draft_at - 90)])
        page, _ = _page(root, ["vid00000001", "vid00000002"])
        # the '+' says the window can only be wider than what was measured: one of the two agents
        # wrote no marker, so its start is unknown and the wave is a floor, not a measurement
        assert "<dt>пересказ, волна</dt><dd>1.0 мин+</dd>" in page


def test_playlist_header_is_named_on_the_page() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _digested(root, "vid00000001")
        q = root / "queue.txt"
        q.write_text("# playlist: Мой плейлист | https://youtube.com/playlist?list=PL1\n"
                     "https://www.youtube.com/watch?v=vid00000001\n", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stdout(buf):
            digest_report.main(["--queue", str(q), "--config", str(_cfg(root))])
        page = (root / "digest-report.html").read_text(encoding="utf-8")
        assert "Мой плейлист" in page and "list=PL1" in page


def test_argv_workdir_with_nothing_to_report_is_named_not_rendered() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "vid00000009" / "segments").mkdir(parents=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = digest_report.main([str(root / "vid00000009"), "--config", str(_cfg(root))])
        out = buf.getvalue()
        assert code == 0 and "nothing to render" in out and "vid00000009" in out


if __name__ == "__main__":
    mod = sys.modules[__name__]
    tests = [(n, getattr(mod, n)) for n in dir(mod) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"all digest tests passed ({len(tests)})")
