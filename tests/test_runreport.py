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

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import runreport  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

_CFG = Config()


def _mkwork(tmp, *, report=None, translation=None, timings=None, sentences=None, info=None):
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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all runreport tests passed")
