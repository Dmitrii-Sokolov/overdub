"""Unit tests for overdub/runreport.py — the per-run observability aggregation.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_runreport.py   (or via pytest)
Pure, no GPU, no network. Synthetic timings/report/translation/sentences/info artifacts are
written into a tmp work dir; the tests assert build_run_report's rollup. The load-bearing
invariant guarded here is UNIT-LEVEL dedup (report records fan out per sentence, sharing a
group_id) — speed/verify by_type must count UNITS, not member sentences — plus the video-sec
priority ladder, the rtf/breakdown math, translate by_type (unknown bucket), flags_total /
needs_triage, the both-inputs-absent → None contract, offender selection and the digest smoke.
The ffprobe branch is deliberately never depended on: every duration case avoids source media,
so the result is identical whether or not ffprobe is installed.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))   # scripts/run_report.py — its main() is the only
                                             # live call site of read_summary in that script

import run_report  # noqa: E402
from overdub import runreport  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

_CFG = Config()


def _mkwork(tmp, *, report=None, translation=None, timings=None, sentences=None, info=None,
            summary=None):
    """Write the requested synthetic artifacts into a fresh work dir; return its WorkDir."""
    root = Path(tmp)
    (root / "segments").mkdir(parents=True, exist_ok=True)
    if report is not None:
        (root / "report.json").write_text(json.dumps(report), encoding="utf-8")
    if translation is not None:
        (root / "translation.json").write_text(json.dumps(translation), encoding="utf-8")
    if timings is not None:
        (root / "timings.json").write_text(json.dumps(timings), encoding="utf-8")
    if sentences is not None:
        (root / "sentences.json").write_text(json.dumps(sentences), encoding="utf-8")
    if info is not None:
        (root / "source.info.json").write_text(json.dumps(info), encoding="utf-8")
    if summary is not None:                # plain text, NOT json.dumps — summary.md is Markdown
        (root / "summary.md").write_text(summary, encoding="utf-8")
    return WorkDir(root)


def _unit(sid, gid, *, status="ok", verify_flag=None, combined=None, speed=None,
          assemble_flag=None, completeness_flags=None, translate_flag=None):
    """One report segment record (unit-level fields duplicated across members share group_id)."""
    return {
        "id": sid, "group_id": gid, "status": status, "verify_flag": verify_flag,
        "combined_factor": combined, "speed_factor": speed, "assemble_flag": assemble_flag,
        "completeness_flags": completeness_flags or [], "translate_flag": translate_flag,
    }


def _two_unit_report(**verify_extra):
    """Report with 2 render units of 2 sentences each: unit A (ids 0,1 / group 0) flagged +
    fast (combined 2.0), unit B (ids 2,3 / group 2) clean + neutral (combined 1.0)."""
    segs = [
        _unit(0, 0, verify_flag="low_similarity", combined=2.0, speed=1.5),
        _unit(1, 0, verify_flag="low_similarity", combined=2.0, speed=1.5),
        _unit(2, 2, verify_flag=None, combined=1.0, speed=1.0),
        _unit(3, 2, verify_flag=None, combined=1.0, speed=1.0),
    ]
    rep = {
        "segments": segs,
        "verify": {"model": "small", "n_units": 2, "n_segments": 4, "n_flagged": 1,
                   "n_retried": 0, "n_repaired": 0},
        "completeness": {"n_sentences": 4, "n_flagged": 0, "n_num_loss": 0, "n_neg_loss": 0,
                         "n_entity_loss": 0, "n_length": 0},
        "assemble": {"duration_sec": 100.0, "n_sped": 1, "in_span_silence_sec": 5.0},
        "mux": {"dub_mix": "bed", "dub_gain_db": 3.0},
    }
    rep.update(verify_extra)
    return rep


# --- record_stage_timing ------------------------------------------------------
def test_record_stage_timing_upsert_and_rounding() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d)
        runreport.record_stage_timing(work, "download", 12.3456)
        runreport.record_stage_timing(work, "transcribe", 45.1)
        runreport.record_stage_timing(work, "download", 10.0)   # upsert overwrites ONLY download
        data = json.loads((Path(d) / "timings.json").read_text(encoding="utf-8"))
        assert data["stages"]["download"] == 10.0
        assert data["stages"]["transcribe"] == 45.1             # other stage preserved


def test_record_stage_timing_rounds_to_3dp() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d)
        runreport.record_stage_timing(work, "synthesize", 1.234567)
        data = json.loads((Path(d) / "timings.json").read_text(encoding="utf-8"))
        assert data["stages"]["synthesize"] == 1.235


# --- _percentile --------------------------------------------------------------
def test_percentile() -> None:
    assert runreport._percentile([5.0], 0.5) == 5.0                      # n==1
    assert runreport._percentile([1.0, 2.0, 3.0], 0.5) == 2.0           # median, odd
    assert runreport._percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5      # median, even
    # p95 of [1..10]: rank = 0.95*9 = 8.55 → 9.0 + 0.55*(10.0-9.0) = 9.55 (hand-computed)
    assert abs(runreport._percentile([float(i) for i in range(1, 11)], 0.95) - 9.55) < 1e-9


# --- build_run_report: unit dedup ---------------------------------------------
def test_build_unit_dedup_speed_and_verify() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[{"id": i, "status": "ok"} for i in range(4)])
        run = runreport.build_run_report(work, _CFG)
        # verify by_type counts UNITS: one low_similarity unit, not two member sentences
        assert run["verify"]["by_type"]["low_similarity"] == 1
        # speed over UNIT leaders [2.0, 1.0]: median 1.5, max 2.0, exactly ONE unit >= 1.8
        assert run["speed"]["metric"] == "combined_factor"
        assert run["speed"]["median"] == 1.5
        assert run["speed"]["max"] == 2.0
        assert run["speed"]["n_over_1_8"] == 1
        # assemble / mux copied straight through
        assert run["assemble"]["duration_sec"] == 100.0
        assert run["mux"]["dub_mix"] == "bed"
        # run.json actually written and equals the returned dict
        assert json.loads((Path(d) / "run.json").read_text(encoding="utf-8")) == run


# --- translate by_type --------------------------------------------------------
def test_translate_by_type_unknown_bucket() -> None:
    with tempfile.TemporaryDirectory() as d:
        translation = [
            {"id": 0, "status": "ok"},
            {"id": 1, "status": "failed", "flag": "runaway"},
            {"id": 2, "status": "failed", "flag": "not_a_real_flag"},   # unknown flag → unknown
            {"id": 3, "status": "failed"},                              # missing flag → unknown
        ]
        work = _mkwork(d, translation=translation)
        run = runreport.build_run_report(work, _CFG)
        assert run["translate"]["n_sentences"] == 4
        assert run["translate"]["n_failed"] == 3
        assert run["translate"]["by_type"]["runaway"] == 1
        assert run["translate"]["by_type"]["unknown"] == 2


# --- video_sec priority -------------------------------------------------------
def test_video_sec_info_json_wins() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, translation=[{"id": 0, "status": "ok"}],
                       info={"duration": 123.0, "title": "Demo"},
                       sentences=[{"id": 0, "end": 999.0}])    # loses to info_json
        run = runreport.build_run_report(work, _CFG)
        assert run["timings"]["video_sec"] == 123.0
        assert run["timings"]["video_sec_source"] == "info_json"
        assert run["title"] == "Demo"


def test_video_sec_falls_back_to_sentences() -> None:
    # No info_json, no source media in the tmp dir → ffprobe (if installed) finds nothing and
    # returns None → the sentences last-end bound wins. Deterministic w.r.t. ffprobe presence.
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, translation=[{"id": 0, "status": "ok"}],
                       sentences=[{"id": 0, "end": 12.0}, {"id": 1, "end": 42.0}])
        run = runreport.build_run_report(work, _CFG)
        assert run["timings"]["video_sec"] == 42.0
        assert run["timings"]["video_sec_source"] == "sentences"


def test_video_sec_none_when_nothing() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, translation=[{"id": 0, "status": "ok"}])
        run = runreport.build_run_report(work, _CFG)
        assert run["timings"]["video_sec"] is None
        assert run["timings"]["video_sec_source"] == "none"
        assert run["timings"]["rtf"] is None


# --- rtf / breakdown math -----------------------------------------------------
def test_rtf_and_breakdown() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, translation=[{"id": 0, "status": "ok"}],
                       timings={"stages": {"download": 10.0, "transcribe": 30.0}},
                       info={"duration": 80.0})
        run = runreport.build_run_report(work, _CFG)
        t = run["timings"]
        assert t["total_wall_s"] == 40.0
        assert t["rtf"] == 0.5                                   # 40 / 80
        assert t["breakdown_pct"] == {"download": 25.0, "transcribe": 75.0}


def test_zero_wall_rtf_null_breakdown_empty() -> None:
    # No timings and no duration source → total_wall 0 → rtf null, breakdown {}.
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, translation=[{"id": 0, "status": "ok"}])
        run = runreport.build_run_report(work, _CFG)
        assert run["timings"]["total_wall_s"] == 0
        assert run["timings"]["rtf"] is None
        assert run["timings"]["breakdown_pct"] == {}


# --- flags_total / needs_triage -----------------------------------------------
def test_needs_triage_true() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[{"id": i, "status": "ok"} for i in range(4)])
        run = runreport.build_run_report(work, _CFG)
        # 1 verify flag + 1 unit over 1.8, 0 translate/completeness/assemble flags
        assert run["flags_total"] == 1
        assert run["needs_triage"] is True


def test_needs_triage_false_clean_run() -> None:
    segs = [
        _unit(0, 0, verify_flag=None, combined=1.0, speed=1.0),
        _unit(1, 1, verify_flag=None, combined=1.2, speed=1.2),
    ]
    rep = {
        "segments": segs,
        "verify": {"n_units": 2, "n_segments": 2, "n_flagged": 0, "n_retried": 0, "n_repaired": 0},
        "completeness": {"n_sentences": 2, "n_flagged": 0, "n_num_loss": 0, "n_neg_loss": 0,
                         "n_entity_loss": 0, "n_length": 0},
        "assemble": {"duration_sec": 50.0, "n_sped": 0, "in_span_silence_sec": 1.0},
        "mux": {"dub_mix": "bed", "dub_gain_db": 0.0},
    }
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=rep,
                       translation=[{"id": 0, "status": "ok"}, {"id": 1, "status": "ok"}])
        run = runreport.build_run_report(work, _CFG)
        assert run["flags_total"] == 0
        assert run["speed"]["n_over_1_8"] == 0
        assert run["needs_triage"] is False


def test_dup_adjacent_is_actionable() -> None:
    # dup_adjacent is ACTIONABLE by construction: it is absent from _ADVISORY_COMPLETENESS, and
    # n_actionable is a set DIFFERENCE, so any name not listed there decides needs_triage. This
    # test is the only guard on that status — without it the flag silently demotes to advisory
    # the moment someone adds it to the advisory set.
    segs = [_unit(0, 0, verify_flag=None, combined=1.0, speed=1.0,
                  completeness_flags=["dup_adjacent"])]
    rep = {
        "segments": segs,
        "verify": {"n_units": 1, "n_segments": 1, "n_flagged": 0, "n_retried": 0, "n_repaired": 0},
        "completeness": {"n_sentences": 1, "n_flagged": 1, "n_num_loss": 0, "n_neg_loss": 0,
                         "n_entity_loss": 0, "n_length": 0, "n_dup_adjacent": 1},
        "assemble": {"duration_sec": 50.0, "n_sped": 0, "in_span_silence_sec": 1.0},
        "mux": {"dub_mix": "bed", "dub_gain_db": 0.0},
    }
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=rep, translation=[{"id": 0, "status": "ok"}])
        run = runreport.build_run_report(work, _CFG)
        assert run["completeness"]["n_dup_adjacent"] == 1
        assert run["completeness"]["n_actionable"] == 1
        assert run["completeness"]["n_advisory"] == 0
        assert run["speed"]["n_over_1_8"] == 0
        assert run["needs_triage"] is True


# --- both inputs absent -------------------------------------------------------
def test_returns_none_when_report_and_translation_absent() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, timings={"stages": {"download": 5.0}})   # only timings present
        run = runreport.build_run_report(work, _CFG)
        assert run is None
        assert not (Path(d) / "run.json").exists()                  # wrote nothing


# --- summarize_offenders ------------------------------------------------------
def test_summarize_offenders_selection_and_join() -> None:
    segs = [
        _unit(0, 0, verify_flag=None, combined=1.0),                        # clean → skipped
        _unit(1, 1, status="failed", translate_flag="runaway", combined=1.0),
        _unit(2, 2, verify_flag="low_similarity", combined=1.1),
        _unit(3, 3, combined=2.1, speed=1.9,
              completeness_flags=["neg_loss"], assemble_flag="bad_slot"),
    ]
    translation = [
        {"id": 1, "src_en": "one two three", "text_ru": "раз два"},
        {"id": 3, "src_en": "a longer english source sentence here", "text_ru": "рус"},
    ]
    offenders = runreport.summarize_offenders({"segments": segs}, translation)
    ids = [o["id"] for o in offenders]
    assert ids == [1, 2, 3]                                     # id 0 clean, sorted ascending
    o1 = next(o for o in offenders if o["id"] == 1)
    assert o1["reasons"] == ["translate:runaway"]
    assert o1["src_en"] == "one two three"                     # joined from translation
    o3 = next(o for o in offenders if o["id"] == 3)
    assert "assemble:bad_slot" in o3["reasons"]
    assert "complete:neg_loss" in o3["reasons"]
    assert any(r.startswith("speed:2.1") for r in o3["reasons"])
    assert o3["speed"] == 2.1
    o2 = next(o for o in offenders if o["id"] == 2)
    assert o2["src_en"] is None                                # id 2 not in translation → null


# --- render_run_report smoke --------------------------------------------------
def test_render_run_report_smoke() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[{"id": i, "status": "ok", "src_en": f"en {i}"}
                                    for i in range(4)])
        run = runreport.build_run_report(work, _CFG)
        report = json.loads((Path(d) / "report.json").read_text(encoding="utf-8"))
        offenders = runreport.summarize_offenders(report,
                                                  json.loads((Path(d) / "translation.json")
                                                             .read_text(encoding="utf-8")))
        out = runreport.render_run_report(run, offenders)
        assert isinstance(out, str) and out
        assert run["video_id"] in out
        assert "TRIAGE" in out                                  # this run needs triage


# --- summary sidecar (PLAN item 3 — informational, gates nothing) -----------------------------
def test_read_summary_absent_and_empty() -> None:
    # A missing summary is NORMAL, not an error: the summary gates nothing, so both renderers must
    # get None rather than an exception. Whitespace-only degrades to None too — an empty section
    # header with no prose under it is worse than no section at all.
    with tempfile.TemporaryDirectory() as d:
        assert runreport.read_summary(_mkwork(d)) is None
    with tempfile.TemporaryDirectory() as d:
        assert runreport.read_summary(_mkwork(d, summary="   \n\n  ")) is None


def test_read_summary_strips_headings() -> None:
    # The digest is Markdown and its own per-video header is "### <vid>". A heading inside the
    # summary would open a new block and silently break block boundaries for the skill agent that
    # parses the digest. Strip the marker, KEEP the text — never drop a line.
    with tempfile.TemporaryDirectory() as d:
        out = runreport.read_summary(_mkwork(d, summary="## Итог\n\nВидео про GPU."))
        assert "Итог" in out and "Видео про GPU." in out
        assert "#" not in out


def test_read_summary_truncates_runaway() -> None:
    # A runaway blob would wreck the digest's line flow and bloat the triage page. Truncation is
    # VISIBLE (the marker), never a silent drop — the pipeline's standing rule.
    with tempfile.TemporaryDirectory() as d:
        out = runreport.read_summary(_mkwork(d, summary="я" * 9000))
        assert len(out) < runreport._SUMMARY_MAX_CHARS + 40
        assert out.endswith("…[truncated]")


def test_render_run_report_without_summary_unchanged() -> None:
    # render_run_report has two live call sites that pass two positional args. The summary=None
    # path must stay BYTE-IDENTICAL to the pre-item-3 output — pinned here, not by inspection,
    # because an optional section that shifts existing output is a silent regression.
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[{"id": i, "status": "ok", "src_en": f"en {i}"}
                                    for i in range(4)])
        run = runreport.build_run_report(work, _CFG)
        report = json.loads((Path(d) / "report.json").read_text(encoding="utf-8"))
        offenders = runreport.summarize_offenders(report, None)
        out = runreport.render_run_report(run, offenders)        # TWO positional args
        assert out == runreport.render_run_report(run, offenders, None)
        assert "- summary" not in out


def test_render_run_report_with_summary() -> None:
    # The summary section must not be able to break the digest: every prose line indented two
    # spaces (the offender bullets' continuation shape), no line opening a Markdown block, and no
    # line past the file's ~96-column discipline.
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[{"id": i, "status": "ok"} for i in range(4)])
        run = runreport.build_run_report(work, _CFG)
        out = runreport.render_run_report(run, [], "Видео про GPU. Стоит смотреть.")
        assert "- summary (5 words):" in out
        assert "Стоит смотреть." in out
        block = out.split("- summary (5 words):\n", 1)[1]
        assert all(ln.startswith("  ") for ln in block.split("\n") if ln)
        # the digest's OWN header is "### <vid>", so scope this to the summary block: no line the
        # summary contributes may open a Markdown block of its own.
        assert not any(ln.lstrip().startswith("#") for ln in block.split("\n"))
        # only the summary block is wrapped — the pre-existing timings/flags lines are unwrapped
        # by design and already run past 96, so the width check belongs to the block alone.
        assert max(len(ln) for ln in block.split("\n")) <= 96


def test_summary_absent_from_run_json() -> None:
    # The summary is a SIDECAR by decision: run.json self-clears when report+translation are both
    # gone (a scout-mode workdir), so folding the summary into the rollup would make it invisible
    # in the one mode it is designed for. run.json's schema must stay untouched.
    # Same workdir for both builds — video_id is the dir name, so two tmp dirs could never match.
    tr = [{"id": i, "status": "ok"} for i in range(4)]
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(), translation=tr)
        runreport.build_run_report(work, _CFG)
        without = (Path(d) / "run.json").read_text(encoding="utf-8")
        (Path(d) / "summary.md").write_text("Видео про GPU.", encoding="utf-8")
        run = runreport.build_run_report(work, _CFG)
        with_summary = (Path(d) / "run.json").read_text(encoding="utf-8")
    assert "summary" not in run
    assert with_summary == without                              # byte-identical on disk


def test_run_report_main_reads_summary_md_off_the_workdir() -> None:
    # main() is the only live call site of read_summary in scripts/run_report.py — every test
    # above hands render_run_report the prose directly. Without this, dropping the third argument
    # from render_run_report(run, offenders, summary) makes item 3's output vanish from the
    # digest with the whole suite still green.
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[{"id": i, "status": "ok"} for i in range(4)],
                       summary="Видео про GPU. Стоит смотреть.")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert run_report.main([str(work.root)]) == 0
    assert "- summary (5 words):" in buf.getvalue()
    assert "Стоит смотреть." in buf.getvalue()


# --- by_type carries the full fixed vocab at 0 (load-bearing diff-without-None-guard) ---------
def test_by_type_carries_full_vocab_at_zero() -> None:
    # runreport's docstring makes it load-bearing that run.json always carries EVERY fixed-vocab
    # key at 0, so a consumer can diff two runs without None-guarding. Assert the full key sets —
    # a refactor to a defaultdict-of-seen-flags would satisfy the single-key checks but break this.
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[{"id": i, "status": "ok"} for i in range(4)])
        run = runreport.build_run_report(work, _CFG)
        assert set(run["translate"]["by_type"]) == set(runreport._TRANSLATE_FLAGS)
        assert set(run["verify"]["by_type"]) == set(runreport._VERIFY_FLAGS)


def test_verify_by_type_unknown_bucket() -> None:
    # a verify_flag outside the known vocab (future/older verify.py, hand edit) must land in the
    # "unknown" bucket, never silently vanish — symmetry with the translate path.
    segs = [_unit(0, 0, verify_flag="clipped_wav")]              # not in _VERIFY_FLAGS
    rep = {
        "segments": segs,
        "verify": {"n_units": 1, "n_segments": 1, "n_flagged": 1, "n_retried": 0, "n_repaired": 0},
        "completeness": {"n_sentences": 1, "n_flagged": 0, "n_num_loss": 0, "n_neg_loss": 0,
                         "n_entity_loss": 0, "n_length": 0},
    }
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=rep, translation=[{"id": 0, "status": "ok"}])
        run = runreport.build_run_report(work, _CFG)
        assert run["verify"]["by_type"]["unknown"] == 1
        assert sum(run["verify"]["by_type"].values()) == run["verify"]["n_flagged"]


# --- flags_total sums ALL four sources (completeness/assemble are 0 in the other tests) --------
def test_flags_total_counts_completeness_and_assemble() -> None:
    segs = [
        _unit(0, 0, verify_flag=None, combined=1.0, assemble_flag="bad_slot"),
        _unit(1, 1, verify_flag=None, combined=1.0),
    ]
    rep = {
        "segments": segs,
        "verify": {"n_units": 2, "n_segments": 2, "n_flagged": 0, "n_retried": 0, "n_repaired": 0},
        "completeness": {"n_sentences": 2, "n_flagged": 2, "n_num_loss": 1, "n_neg_loss": 1,
                         "n_entity_loss": 0, "n_length": 0},
        "assemble": {"duration_sec": 50.0, "n_sped": 0, "in_span_silence_sec": 1.0},
        "mux": {"dub_mix": "bed", "dub_gain_db": 0.0},
    }
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=rep,
                       translation=[{"id": 0, "status": "ok"}, {"id": 1, "status": "ok"}])
        run = runreport.build_run_report(work, _CFG)
        # verify 0 + completeness n_flagged 2 + assemble-flagged units 1 = 3
        assert run["flags_total"] == 3
        assert run["needs_triage"] is True


# --- speed is null (not a fabricated 1.0) when verify ran but assemble did not ------------------
def test_speed_null_when_unassembled() -> None:
    segs = [                                                    # combined/speed default to None
        _unit(0, 0, verify_flag="low_similarity"),
        _unit(1, 0, verify_flag="low_similarity"),
    ]
    rep = {                                                     # no assemble/mux: not run yet
        "segments": segs,
        "verify": {"n_units": 1, "n_segments": 2, "n_flagged": 1, "n_retried": 0, "n_repaired": 0},
        "completeness": {"n_sentences": 2, "n_flagged": 0, "n_num_loss": 0, "n_neg_loss": 0,
                         "n_entity_loss": 0, "n_length": 0},
    }
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=rep,
                       translation=[{"id": 0, "status": "ok"}, {"id": 1, "status": "ok"}])
        run = runreport.build_run_report(work, _CFG)
        assert run["speed"]["median"] is None and run["speed"]["p95"] is None
        assert run["speed"]["max"] is None
        assert run["speed"]["n_over_1_8"] == 0
        assert run["assemble"]["duration_sec"] is None          # un-run assemble stays null too


# --- n_over_1_8 trusts assemble's raw-float rollup over the rounded recompute -------------------
def test_n_over_prefers_assemble_rollup() -> None:
    # a unit whose 4-dp-rounded combined_factor is 1.8 but whose raw float was 1.79997: assemble
    # counted 0 over-1.8; run.json must trust that authoritative count, not recompute 1.
    segs = [_unit(0, 0, verify_flag=None, combined=1.8, speed=1.5)]
    rep = {
        "segments": segs,
        "verify": {"n_units": 1, "n_segments": 1, "n_flagged": 0, "n_retried": 0, "n_repaired": 0},
        "completeness": {"n_sentences": 1, "n_flagged": 0, "n_num_loss": 0, "n_neg_loss": 0,
                         "n_entity_loss": 0, "n_length": 0},
        "assemble": {"duration_sec": 50.0, "n_sped": 1, "in_span_silence_sec": 0.0,
                     "n_over_1_8_combined": 0},
        "mux": {"dub_mix": "bed", "dub_gain_db": 0.0},
    }
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=rep, translation=[{"id": 0, "status": "ok"}])
        run = runreport.build_run_report(work, _CFG)
        assert run["speed"]["max"] == 1.8                       # rounded value still surfaced
        assert run["speed"]["n_over_1_8"] == 0                  # count trusts assemble's rollup
        assert run["needs_triage"] is False


# --- ffprobe is the MIDDLE rung of the duration ladder (monkeypatched, keeps the suite pure) ----
def test_video_sec_ffprobe_rung() -> None:
    orig = runreport._ffprobe_duration
    runreport._ffprobe_duration = lambda work: 200.0            # simulate a successful probe
    try:
        with tempfile.TemporaryDirectory() as d:                # ffprobe beats sentences
            work = _mkwork(d, translation=[{"id": 0, "status": "ok"}],
                           sentences=[{"id": 0, "end": 42.0}])
            run = runreport.build_run_report(work, _CFG)
            assert run["timings"]["video_sec"] == 200.0
            assert run["timings"]["video_sec_source"] == "ffprobe"
        with tempfile.TemporaryDirectory() as d:                # info_json still beats ffprobe
            work = _mkwork(d, translation=[{"id": 0, "status": "ok"}],
                           info={"duration": 123.0}, sentences=[{"id": 0, "end": 42.0}])
            run = runreport.build_run_report(work, _CFG)
            assert run["timings"]["video_sec"] == 123.0
            assert run["timings"]["video_sec_source"] == "info_json"
    finally:
        runreport._ffprobe_duration = orig


# --- flagged_units (morning-triage HTML data) -------------------------------------------------
def test_flagged_units_dedup_reasons_and_join() -> None:
    # unit A (ids 0,1 / group 0): verify low_similarity + combined 2.0 on the leader, neg_loss
    # completeness on member 1, hypothesis on the leader only. unit B (ids 2,3 / group 2): clean.
    segs = [
        {"id": 0, "group_id": 0, "status": "ok", "verify_flag": "low_similarity",
         "similarity": 0.71, "hypothesis": "мы получили шестьдесят", "combined_factor": 2.0,
         "speed_factor": 1.5, "assemble_flag": None, "completeness_flags": [], "translate_flag": None},
        {"id": 1, "group_id": 0, "status": "ok", "verify_flag": "low_similarity",
         "similarity": 0.71, "hypothesis": None, "combined_factor": 2.0, "speed_factor": 1.5,
         "assemble_flag": None, "completeness_flags": ["neg_loss"], "translate_flag": None},
        {"id": 2, "group_id": 2, "status": "ok", "verify_flag": None, "similarity": 0.98,
         "hypothesis": None, "combined_factor": 1.0, "speed_factor": 1.0, "assemble_flag": None,
         "completeness_flags": [], "translate_flag": None},
        {"id": 3, "group_id": 2, "status": "ok", "verify_flag": None, "similarity": 0.98,
         "hypothesis": None, "combined_factor": 1.0, "speed_factor": 1.0, "assemble_flag": None,
         "completeness_flags": [], "translate_flag": None},
    ]
    translation = [
        {"id": 0, "src_en": "We hit sixty fps.", "text_ru": "Шестьдесят кадров.",
         "text_tts": "шестьдесят кадров", "start": 1.0, "end": 3.0},
        {"id": 1, "src_en": "It is not small.", "text_ru": "Это немало.",
         "text_tts": "это немало", "start": 3.0, "end": 5.0},
        {"id": 2, "src_en": "Clean two.", "text_ru": "Чисто два.", "start": 5.0, "end": 6.0},
        {"id": 3, "src_en": "Clean three.", "text_ru": "Чисто три.", "start": 6.0, "end": 7.0},
    ]
    rows = runreport.flagged_units({"segments": segs}, translation)
    assert len(rows) == 1                                       # only unit A; unit B is clean
    u = rows[0]
    assert u["lead"] == 0 and u["ids"] == [0, 1]                # lead = group_id = wav key
    assert "verify:low_similarity" in u["reasons"]
    assert any(r.startswith("speed:2.0") for r in u["reasons"])
    assert "complete:neg_loss" in u["reasons"]                  # unioned from member 1
    assert u["similarity"] == 0.71
    assert u["hypothesis"] == "мы получили шестьдесят"          # leader-only field carried
    assert u["src_en"] == "We hit sixty fps. It is not small."  # joined across members
    assert u["text_ru"] == "Шестьдесят кадров. Это немало."
    assert u["start"] == 1.0 and u["end"] == 5.0
    assert u["speed"] == 2.0


def test_flagged_units_translate_flag_on_member() -> None:
    segs = [{"id": 0, "group_id": 0, "status": "failed", "translate_flag": "runaway",
             "verify_flag": None, "combined_factor": 1.0, "completeness_flags": []}]
    rows = runreport.flagged_units(
        {"segments": segs},
        [{"id": 0, "src_en": "x", "text_ru": "y", "start": 0.0, "end": 1.0}])
    assert len(rows) == 1
    assert rows[0]["reasons"] == ["translate:runaway"]


# --- source anomalies (PLAN item 1 — advisory, gates nothing) ---------------------------------
# The signal exists because a good translator BLEACHES source damage (DECISIONS 2026-07-19), so
# these guard the two things that make it observable at all: "ok" as a positive claim (scanned),
# and the anomaly read happening BEFORE the status-ok skip in the translation loop.
def _tr(sid, *, status="ok", src=None, note=None, src_en=None):
    rec = {"id": sid, "status": status, "src_en": src_en if src_en is not None else f"en {sid}"}
    if src is not None:
        rec["src"] = src
    if note is not None:
        rec["src_note"] = note
    return rec


def test_source_scanned_clean_carries_full_vocab() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[_tr(i, src="ok") for i in range(4)])
        run = runreport.build_run_report(work, _CFG)
        s = run["source"]
        assert s["scanned"] is True and s["n_scanned"] == 4 and s["n_flagged"] == 0
        assert set(s["by_type"]) == set(runreport._SOURCE_KINDS)
        assert all(v == 0 for v in s["by_type"].values())
        assert s["items"] == []


def test_source_not_scanned_route_a() -> None:
    # Route A (local Gemma) writes no `src` at all. A consumer must be able to tell "not scanned"
    # from "scanned and clean" — that is the whole reason `scanned` is a field and not inferred.
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[_tr(i) for i in range(4)])
        run = runreport.build_run_report(work, _CFG)
        s = run["source"]
        assert s["scanned"] is False and s["n_scanned"] == 0 and s["n_flagged"] == 0


def test_source_partial_scan_is_not_scanned() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[_tr(0, src="ok"), _tr(1, src="ok"), _tr(2), _tr(3)])
        run = runreport.build_run_report(work, _CFG)
        assert run["source"]["scanned"] is False
        assert run["source"]["n_scanned"] == 2


def test_source_anomaly_counted_on_status_ok_record() -> None:
    # THE ordering regression test. A source anomaly is orthogonal to status: an anomalous English
    # sentence usually translates fine and carries status "ok". If the anomaly read ever moves
    # below the `status == "ok"` continue, the signal silently vanishes for the common case.
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[_tr(0, status="ok", src="truncated", note="ends mid-thought"),
                                    _tr(1, src="ok"), _tr(2, src="ok"), _tr(3, src="ok")])
        run = runreport.build_run_report(work, _CFG)
        s = run["source"]
        assert s["n_flagged"] == 1 and s["by_type"]["truncated"] == 1
        assert s["items"][0]["id"] == 0 and s["items"][0]["note"] == "ends mid-thought"
        assert s["items"][0]["src_en"] == "en 0"     # duplicated in: readable pre-synthesis


def test_source_unknown_kind_buckets() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[_tr(0, src="weird"), _tr(1, src="ok"),
                                    _tr(2, src="ok"), _tr(3, src="ok")])
        run = runreport.build_run_report(work, _CFG)
        assert run["source"]["by_type"]["unknown"] == 1
        assert run["source"]["items"][0]["kind"] == "unknown"


def test_source_items_capped_at_limit() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[_tr(i, src="garbled") for i in range(60)])
        run = runreport.build_run_report(work, _CFG)
        s = run["source"]
        assert s["n_flagged"] == 60                        # counted in full
        assert len(s["items"]) == runreport._SOURCE_LIMIT   # but run.json stays small/diffable
        ids = [it["id"] for it in s["items"]]
        assert ids == sorted(ids)


def test_source_anomalies_are_advisory_not_actionable() -> None:
    # Advisory in v1: an LLM told to report source damage has NO measured precision yet, and
    # entity_loss (marked 11 of 12 videos) is the precedent. Counted in flags_total, printed
    # everywhere, but never a reason to open the video. Promotion is a one-line change, gated on
    # one batch's measured fire rate.
    segs = [_unit(0, 0, verify_flag=None, combined=1.0, speed=1.0)]
    rep = {
        "segments": segs,
        "verify": {"n_units": 1, "n_segments": 1, "n_flagged": 0, "n_retried": 0, "n_repaired": 0},
        "completeness": {"n_sentences": 1, "n_flagged": 0, "n_num_loss": 0, "n_neg_loss": 0,
                         "n_entity_loss": 0, "n_length": 0},
        "assemble": {"duration_sec": 50.0, "n_sped": 0, "in_span_silence_sec": 1.0},
        "mux": {"dub_mix": "bed", "dub_gain_db": 0.0},
    }
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=rep, translation=[_tr(0, src="garbled", note="unintelligible")])
        run = runreport.build_run_report(work, _CFG)
        assert run["flags_total"] == 1                  # counted
        assert run["flags_actionable"] == 0             # but not actionable
        assert run["needs_triage"] is False             # and the run stays [clean]
        out = runreport.render_run_report(run, [])
        assert "[clean]" in out
        assert "- source anomalies (1):" in out         # advisory never costs visibility


def test_render_run_report_no_source_key_prints_nothing() -> None:
    # A run.json predating this schema has no "source" key — same degrade-to-silent contract as
    # every other optional block here. --rebuild backfills it.
    run = {"video_id": "vid00000001", "needs_triage": False,
           "timings": {}, "asr": {}, "translate": {"n_sentences": 4, "n_failed": 0},
           "verify": {}, "completeness": {}, "speed": {}}
    out = runreport.render_run_report(run, [])
    assert "source anomalies" not in out


def test_render_run_report_not_scanned_line() -> None:
    run = {"video_id": "vid00000001", "needs_triage": False,
           "timings": {}, "asr": {}, "translate": {"n_sentences": 4, "n_failed": 0},
           "verify": {}, "completeness": {}, "speed": {},
           "source": {"scanned": False, "n_scanned": 0, "n_flagged": 0,
                      "by_type": {}, "items": []}}
    out = runreport.render_run_report(run, [])
    assert "- source anomalies: not scanned" in out


def test_flagged_units_src_is_crossref_only() -> None:
    # Report-driven by design: an anomalous sentence whose unit came out CLEAN gains no row (no
    # audio to listen to, and a fabricated row would break the lead/wav join). A unit that is
    # already flagged gains a src: reason so the human sees WHY the English was suspect.
    segs = [_unit(0, 0, verify_flag="low_similarity", combined=1.0),
            _unit(1, 1, verify_flag=None, combined=1.0)]
    translation = [_tr(0, src="garbled", note="unintelligible"),
                   _tr(1, src="truncated", note="cut off")]
    rows = runreport.flagged_units({"segments": segs}, translation)
    assert [r["lead"] for r in rows] == [0]             # the clean unit 1 gains NO row
    assert "src:garbled" in rows[0]["reasons"]


def test_summarize_offenders_unchanged_by_src() -> None:
    # Deliberate NON-change: the digest already prints a dedicated "- source anomalies" section,
    # so adding src: to offender rows would double-print the same ids two bullets apart. The HTML
    # has no such section-adjacency, hence the asymmetry with flagged_units above.
    segs = [_unit(0, 0, verify_flag="low_similarity", combined=1.0)]
    without = runreport.summarize_offenders({"segments": segs}, [_tr(0)])
    with_src = runreport.summarize_offenders({"segments": segs},
                                             [_tr(0, src="garbled", note="unintelligible")])
    assert json.dumps(without, sort_keys=True) == json.dumps(with_src, sort_keys=True)


def test_flagged_units_empty_when_clean() -> None:
    segs = [{"id": 0, "group_id": 0, "status": "ok", "verify_flag": None,
             "combined_factor": 1.2, "completeness_flags": [], "assemble_flag": None}]
    assert runreport.flagged_units({"segments": segs}, None) == []


# --- shared report data layer: classify_workdir / collect_entries / batch_* ----
def _mkkind(root, vid, *, report=None, translation=None, sentences=None, info=None,
            summary=None, scout=None, run_json=None, mkv=False, wav=False):
    """Fabricate work/<vid> with exactly the named artifacts. Unlike _mkwork (one dir = the
    whole tmp root), collect_entries tests need several SIBLING dirs under one work root."""
    d = Path(root) / vid
    d.mkdir(parents=True, exist_ok=True)
    if report is not None:
        (d / "report.json").write_text(json.dumps(report), encoding="utf-8")
    if translation is not None:
        (d / "translation.json").write_text(json.dumps(translation), encoding="utf-8")
    if sentences is not None:
        (d / "sentences.json").write_text(json.dumps(sentences), encoding="utf-8")
    if info is not None:
        (d / "source.info.json").write_text(json.dumps(info), encoding="utf-8")
    if summary is not None:
        (d / "summary.md").write_text(summary, encoding="utf-8")
    if scout is not None:
        (d / "scout.json").write_text(json.dumps(scout), encoding="utf-8")
    if run_json is not None:
        (d / "run.json").write_text(json.dumps(run_json), encoding="utf-8")
    if mkv:
        (d / "source.mkv").write_bytes(b"\x00")
    if wav:
        (d / "source.wav").write_bytes(b"\x00")
    return d


def test_classify_workdir_matrix() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        cases = {
            "run-rep": dict(report={"segments": []}),           # report.json alone is a run
            "run-tr": dict(translation=[]),                     # translation.json alone too
            "pending": dict(sentences=[{"id": 0, "end": 1.0}], mkv=True),
            "scout": dict(sentences=[{"id": 0, "end": 1.0}]),
            "scout0": dict(sentences=[]),                       # EMPTY list parses -> still scout
            "fetched": dict(wav=True),
            "missing": dict(),
        }
        got = {vid: runreport.classify_workdir(WorkDir(_mkkind(root, vid, **files)))
               for vid, files in cases.items()}
        # torn sentences.json is NOT a transcript: with the audio present it stays "fetched"
        torn = _mkkind(root, "torn", wav=True)
        (torn / "sentences.json").write_text("{not json", encoding="utf-8")
        got["torn"] = runreport.classify_workdir(WorkDir(torn))
    assert got == {"run-rep": "run", "run-tr": "run", "pending": "pending", "scout": "scout",
                   "scout0": "scout", "fetched": "fetched", "missing": "missing",
                   "torn": "fetched"}


def test_classify_workdir_source_mkv_flips_scout_to_pending() -> None:
    # The discriminator itself: same transcript, the container's presence is the ONLY
    # difference between "scout this" and "a parked full dub" (nothing ever deletes source.mkv).
    with tempfile.TemporaryDirectory() as d:
        wd = _mkkind(Path(d), "vidFLIP00000", sentences=[{"id": 0, "end": 5.0}])
        work = WorkDir(wd)
        assert runreport.classify_workdir(work) == "scout"
        (wd / "source.mkv").write_bytes(b"\x00")
        assert runreport.classify_workdir(work) == "pending"


def test_collect_entries_queue_order_survives_a_missing_video() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _mkkind(root, "vidAAAAAAAAA", report=_two_unit_report(),
                translation=[{"id": i, "status": "ok"} for i in range(4)])
        _mkkind(root, "vidCCCCCCCCC", sentences=[{"id": 0, "end": 62.0}])
        # vidBBBBBBBBB has NO dir at all — the download never happened
        entries, skipped = runreport.collect_entries(
            ["vidAAAAAAAAA", "vidBBBBBBBBB", "vidCCCCCCCCC"], [], root, cfg=_CFG)
    assert [e["vid"] for e in entries] == ["vidAAAAAAAAA", "vidBBBBBBBBB", "vidCCCCCCCCC"]
    assert [e["n"] for e in entries] == [1, 2, 3]           # position preserved across the gap
    assert [e["kind"] for e in entries] == ["run", "missing", "scout"]
    assert all(e["from_queue"] for e in entries)
    assert skipped == []                        # a queue id is NEVER dropped, whatever its kind
    assert entries[0]["run"] is not None and entries[0]["run"]["video_id"] == "vidAAAAAAAAA"
    assert entries[0]["units"] and entries[0]["offenders"]  # kind "run" carries triage rows
    assert entries[2]["n_sentences"] == 1 and entries[2]["duration_sec"] == 62.0


def test_collect_entries_argv_dedup_and_numbering_continue() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _mkkind(root, "vidAAAAAAAAA", report=_two_unit_report(),
                translation=[{"id": i, "status": "ok"} for i in range(4)])
        _mkkind(root, "vidDDDDDDDDD", sentences=[{"id": 0, "end": 30.0}])
        entries, skipped = runreport.collect_entries(
            ["vidAAAAAAAAA"], [root / "vidAAAAAAAAA", root / "vidDDDDDDDDD"], root, cfg=_CFG)
    # the argv duplicate of a queued id is absorbed (normcased-abs-path dedup, queue wins)
    assert [(e["vid"], e["n"], e["from_queue"]) for e in entries] == [
        ("vidAAAAAAAAA", 1, True), ("vidDDDDDDDDD", 2, False)]
    assert skipped == []


def test_collect_entries_scout_json_rides_on_a_run_entry() -> None:
    # A dubbed video that was scouted first keeps its grade: scout.json is attached for ANY
    # kind, not only for scout cards.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _mkkind(root, "vidAAAAAAAAA", report=_two_unit_report(),
                translation=[{"id": i, "status": "ok"} for i in range(4)],
                scout={"quality": "high", "one_liner": "x"})
        entries, _ = runreport.collect_entries(None, [root / "vidAAAAAAAAA"], root, cfg=_CFG)
    assert entries[0]["kind"] == "run"
    assert entries[0]["scout"]["quality"] == "high"


def test_collect_entries_argv_typo_and_fetched_go_to_skipped() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _mkkind(root, "vidEMPTY0000")                       # nothing at all — a typo'd path
        _mkkind(root, "vidFETCHED00", wav=True)             # audio only, never transcribed
        entries, skipped = runreport.collect_entries(
            None, [root / "vidEMPTY0000", root / "vidFETCHED00"], root, cfg=_CFG)
    assert entries == []
    assert skipped == ["vidEMPTY0000", "vidFETCHED00"]


def test_collect_entries_rebuild_forces_recompute() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = _mkkind(root, "vidAAAAAAAAA", report=_two_unit_report(),
                     translation=[{"id": i, "status": "ok"} for i in range(4)],
                     run_json={"video_id": "stale"})
        loaded, _ = runreport.collect_entries(None, [wd], root, cfg=_CFG)
        rebuilt, _ = runreport.collect_entries(None, [wd], root, cfg=_CFG, rebuild=True)
    assert loaded[0]["run"]["video_id"] == "stale"          # the fast path trusts run.json
    assert rebuilt[0]["run"]["video_id"] == "vidAAAAAAAAA"  # --rebuild recomputes from artifacts


def test_batch_row_golden_cells() -> None:
    # These exact strings are the cross-surface contract (both renderers print them verbatim);
    # golden-pinned from a fabricated run.json so a formatting drift fails HERE, not in a
    # morning diff between the two surfaces.
    run = {
        "video_id": "vid00000001", "title": "Talk", "needs_triage": True,
        "timings": {"total_wall_s": 123.4, "rtf": 0.256, "video_sec": 482.0},
        "asr": {"floor_ratio": 0.0342},
        "translate": {"n_failed": 2, "n_sentences": 40},
        "verify": {"n_flagged": 1},
        "completeness": {"n_flagged": 8, "n_actionable": 3, "n_advisory": 5},
        "source": {"scanned": True, "n_flagged": 4},
        "speed": {"max": 2.13, "n_over_1_8": 1},
    }
    row = runreport.batch_row(run)
    assert row["video_id"] == "vid00000001"
    assert row["title"] == "Talk"                           # RAW — truncation is per-medium
    assert row["needs_triage"] is True
    assert row["cells"] == [
        ("wall_s", "123.4"), ("rtf", "0.256"), ("floor", "3.4%"), ("tr", "2"),
        ("vf", "1"), ("cp", "3"), ("adv", "5"), ("src", "4"),
        ("spd_max", "2.13"), ("n_over", "1"),
    ]


def test_batch_row_floor_na_src_dash_and_blank_wall() -> None:
    # A partial / route-A run: no words.json (floor n/a), src not scanned ("-", which must
    # never read as a clean 0), no timings (wall_s prints empty, rtf prints None — today's
    # exact strings, pinned).
    row = runreport.batch_row({"video_id": "v", "asr": {"floor_ratio": None},
                               "source": {"scanned": False, "n_flagged": 0}, "speed": {}})
    cells = dict(row["cells"])
    assert cells["floor"] == "n/a"
    assert cells["src"] == "-"
    assert cells["wall_s"] == ""
    assert cells["rtf"] == "None"
    assert cells["spd_max"] == "None"
    assert cells["n_over"] == "0"
    assert row["needs_triage"] is False


def test_batch_row_cp_falls_back_to_n_flagged_on_a_pre_schema_run() -> None:
    # A run.json written before the actionable/advisory split carried only completeness.n_flagged.
    # batch_row's cp cell must fall back to it (adv to 0) through the SAME chain
    # render_run_report's flags line uses — otherwise, on an old run, the digest's flags line said
    # 3 while both batch tables and the card rollup said 0 (the cross-surface divergence PLAN item
    # 2 kills). Assert both the cell and the digest line agree on the pre-schema number.
    run = {"video_id": "vid00000001", "needs_triage": True,
           "completeness": {"n_flagged": 3},           # pre-schema: no n_actionable / n_advisory
           "asr": {"floor_ratio": None},
           "source": {"scanned": False, "n_flagged": 0}, "speed": {}}
    cells = dict(runreport.batch_row(run)["cells"])
    assert cells["cp"] == "3"                           # fell back to n_flagged, not defaulted to 0
    assert cells["adv"] == "0"
    # and render_run_report's flags line reads the SAME 3 through its own fallback chain
    assert "completeness 3 (+0 advisory)" in runreport.render_run_report(run, [])


def test_batch_totals() -> None:
    runs = [
        {"timings": {"total_wall_s": 100.0, "video_sec": 300.0}, "needs_triage": True},
        {"timings": {"total_wall_s": 50.0, "video_sec": None}, "needs_triage": False},
    ]
    tot = runreport.batch_totals(runs)
    assert tot == {"total_wall": 150.0, "throughput": "×2.00", "n_triage": 1}
    assert runreport.batch_totals([])["throughput"] == "n/a"    # zero wall — nothing to divide


def test_batch_columns_is_the_single_header_source() -> None:
    # The header the digest prints IS " | ".join of BATCH_COLUMNS labels — one constant, no
    # second list to drift. Both the literal and the script's stdout are pinned.
    header = " | ".join(label for _key, label in runreport.BATCH_COLUMNS)
    assert header == ("video | title | wall_s | rtf | floor | tr | vf | cp | adv | src | "
                      "spd_max | >1.8 | triage")
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, report=_two_unit_report(),
                       translation=[{"id": i, "status": "ok"} for i in range(4)])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert run_report.main([str(work.root)]) == 0
    assert header in buf.getvalue()


def test_run_report_main_renders_a_scout_block() -> None:
    # The third divergence PLAN item 2 names: a scouted dir used to print "run the pipeline
    # first" — an instruction to dub a video the operator only asked to scout.
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, sentences=[{"id": 0, "end": 3.0}, {"id": 1, "end": 9.0}],
                       info={"title": "Scouted Talk", "duration": 2530.0},
                       summary="Видео про GPU. Стоит смотреть.")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert run_report.main([str(work.root)]) == 0
    out = buf.getvalue()
    assert "[scouted — transcript only, no dub]" in out
    assert "- 2 sentences · 42 min" in out
    assert "- summary (5 words):" in out                    # the scout deliverable is attached
    assert "run the pipeline first" not in out
    assert "── batch" not in out                            # and no fabricated batch row


def test_run_report_main_renders_a_pending_block() -> None:
    # A promoted video parked between download and translate (route B step 1) — previously
    # indistinguishable from a typo'd path in this digest. Duration falls back to sentence
    # ends (9 s → "<1 min", never a literal "None").
    with tempfile.TemporaryDirectory() as d:
        work = _mkwork(d, sentences=[{"id": 0, "end": 3.0}, {"id": 1, "end": 9.0}])
        (Path(d) / "source.mkv").write_bytes(b"\x00")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert run_report.main([str(work.root)]) == 0
    out = buf.getvalue()
    assert "[promoted — downloaded in full, translate has not started]" in out
    assert "- 2 sentences · <1 min" in out
    assert "run the pipeline first" not in out


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all runreport tests passed")
