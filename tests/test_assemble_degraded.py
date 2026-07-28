"""Unit tests for assemble's DEGRADED exits — pure + tmpdir, no ffmpeg, no audio, no models.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_assemble_degraded.py   (or via pytest)

Contract: a MISSING upstream artifact degrades, an INCONSISTENT one still raises. With no
translation.json the stage writes en.srt off sentences.json; with no manifest it writes both
srt tracks off translation.json's source timings; neither builds a dub, both stamp
`assemble.degraded`, and neither raises — so mux still gets a workdir it can ship. The
never-drop invariants (id contiguity, unit coverage) are untouched by all of this: they mean
the artifacts DISAGREE, and a confidently wrong dub is worse than no dub.

The mtime half is not cosmetic. The degraded branch has no done() gate of its own (the gate is
the dub, which does not exist), so it re-runs on every resume; if it rewrote an identical srt
each time, mux's make-style freshness check would re-encode a multi-GB container forever.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.config import Config                                        # noqa: E402
from overdub.pipeline import Context                                     # noqa: E402
from overdub.stages.assemble import (AssembleStage, _write_srt,          # noqa: E402
                                     source_timed_rows)
from overdub.workdir import WorkDir                                      # noqa: E402

SENTS = [{"id": 0, "text": "First line.", "start": 0.0, "end": 2.0},
         {"id": 1, "text": "Second line.", "start": 2.0, "end": 4.0}]
TRANS = [{"id": 0, "src_en": "First line.", "text_ru": "Первая строка.",
          "text_tts": "Первая строка.", "start": 0.0, "end": 2.0, "status": "ok"},
         {"id": 1, "src_en": "Second line.", "text_ru": "Вторая строка.",
          "text_tts": "Вторая строка.", "start": 2.0, "end": 4.0, "status": "ok"}]


def _ctx(td: str) -> Context:
    work = WorkDir.for_url("https://youtu.be/aaaaaaaaaaa", Path(td))
    return Context(url="u", cfg=Config(), work=work)


def _write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def _stamp(ctx: Context) -> dict:
    return json.loads(ctx.work.report.read_text(encoding="utf-8"))["assemble"]


# --- source_timed_rows (pure) -------------------------------------------------
def test_rows_come_off_source_timings_and_the_named_field() -> None:
    assert source_timed_rows(TRANS, "text_ru") == [(0.0, 2.0, "Первая строка."),
                                                   (2.0, 4.0, "Вторая строка.")]
    assert source_timed_rows(SENTS, "text") == [(0.0, 2.0, "First line."),
                                                (2.0, 4.0, "Second line.")]


def test_a_record_without_usable_timings_is_skipped_not_defaulted_to_zero() -> None:
    # a cue stacked at the origin is worse than an absent one: it covers the real first line
    recs = [{"text": "no timings"}, {"text": "bad", "start": None, "end": 3.0},
            {"text": "good", "start": 1.0, "end": 2.0}]
    assert source_timed_rows(recs, "text") == [(1.0, 2.0, "good")]


def test_a_missing_field_becomes_an_empty_string_not_a_crash() -> None:
    assert source_timed_rows([{"start": 0.0, "end": 1.0}], "text_ru") == [(0.0, 1.0, "")]


def test_none_and_empty_inputs_are_tolerated() -> None:
    assert source_timed_rows(None, "text") == [] and source_timed_rows([], "text") == []


# --- degraded exits -----------------------------------------------------------
def test_no_translation_writes_en_srt_off_the_transcript_and_does_not_raise() -> None:
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        _write(ctx.work.sentences, SENTS)
        AssembleStage().run(ctx)                            # must not raise
        assert ctx.work.en_srt.exists()
        assert "First line." in ctx.work.en_srt.read_text(encoding="utf-8")
        assert not ctx.work.ru_srt.exists()                 # nothing was translated
        assert not ctx.work.dub_audio.exists()
        assert _stamp(ctx) == {"degraded": "no_translation", "wrote": ["en.srt"]}


def test_no_transcript_at_all_writes_nothing_and_still_does_not_raise() -> None:
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        AssembleStage().run(ctx)
        assert not ctx.work.en_srt.exists() and not ctx.work.ru_srt.exists()
        assert _stamp(ctx) == {"degraded": "no_transcript", "wrote": []}


def test_a_torn_translation_json_degrades_rather_than_raising() -> None:
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        _write(ctx.work.sentences, SENTS)
        ctx.work.translation.write_text("{ not json", encoding="utf-8")
        AssembleStage().run(ctx)
        assert _stamp(ctx)["degraded"] == "no_translation"


def test_an_empty_translation_list_is_treated_as_absent() -> None:
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        _write(ctx.work.sentences, SENTS)
        _write(ctx.work.translation, [])
        AssembleStage().run(ctx)
        assert _stamp(ctx)["degraded"] == "no_translation"


def test_no_manifest_writes_both_subtitle_tracks_off_source_timings() -> None:
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        _write(ctx.work.sentences, SENTS)
        _write(ctx.work.translation, TRANS)
        AssembleStage().run(ctx)
        assert _stamp(ctx) == {"degraded": "no_synthesis", "wrote": ["en.srt", "ru.srt"]}
        assert "Первая строка." in ctx.work.ru_srt.read_text(encoding="utf-8")
        assert "First line." in ctx.work.en_srt.read_text(encoding="utf-8")
        assert not ctx.work.dub_audio.exists()


def test_the_degraded_stamp_replaces_a_previous_assemble_rollup() -> None:
    # the old numbers describe a dub this workdir can no longer produce; leaving them would
    # let run.json report a duration and a fill median for audio that is not there
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        _write(ctx.work.report, {"segments": [], "assemble": {"duration_sec": 900.0,
                                                              "fill_median": 0.71}})
        _write(ctx.work.sentences, SENTS)
        AssembleStage().run(ctx)
        assert "duration_sec" not in _stamp(ctx) and "fill_median" not in _stamp(ctx)


def test_a_degraded_run_preserves_foreign_report_fields() -> None:
    # report.json is co-owned; a degraded assemble must not eat verify's half
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        _write(ctx.work.report, {"segments": [{"id": 0, "similarity": 0.99}],
                                 "verify": {"n_units": 1}})
        _write(ctx.work.sentences, SENTS)
        AssembleStage().run(ctx)
        rep = json.loads(ctx.work.report.read_text(encoding="utf-8"))
        assert rep["verify"] == {"n_units": 1}
        assert rep["segments"] == [{"id": 0, "similarity": 0.99}]


def test_a_stale_dub_is_announced_not_deleted() -> None:
    # deleting a binary on a degraded path could destroy the last good take of a video whose
    # translation.json was merely moved aside
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        _write(ctx.work.sentences, SENTS)
        ctx.work.dub_audio.write_bytes(b"stale")
        AssembleStage().run(ctx)
        assert ctx.work.dub_audio.exists()


# --- _write_srt identity ------------------------------------------------------
def test_rewriting_identical_rows_leaves_the_file_untouched() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "en.srt"
        rows = [(0.0, 2.0, "First line."), (2.0, 4.0, "Second line.")]
        _write_srt(path, rows)
        first = path.stat().st_mtime_ns
        _write_srt(path, rows)
        assert path.stat().st_mtime_ns == first


def test_changed_rows_do_rewrite_the_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "en.srt"
        _write_srt(path, [(0.0, 2.0, "First line.")])
        _write_srt(path, [(0.0, 2.0, "Changed line.")])
        assert "Changed line." in path.read_text(encoding="utf-8")


def test_a_degraded_rerun_does_not_touch_an_identical_srt() -> None:
    # what the identity guard actually buys: mux re-muxes on an srt newer than output.mkv,
    # and this branch re-runs on every resume
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        _write(ctx.work.sentences, SENTS)
        AssembleStage().run(ctx)
        first = ctx.work.en_srt.stat().st_mtime_ns
        AssembleStage().run(ctx)
        assert ctx.work.en_srt.stat().st_mtime_ns == first


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all assemble degraded-exit tests passed")
