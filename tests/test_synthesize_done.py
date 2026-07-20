"""Unit tests for SynthesizeStage.done() — the manifest↔translation congruence gate.

Run: .venv-asr/Scripts/python.exe tests/test_synthesize_done.py   (or via pytest)
Filesystem only — no GPU, no engine, no worker. Guards the INBOX 2026-07-17 bug:
a complete manifest must NOT skip the stage over wavs rendered from a stale
translation (`--force --only translate` + plain rerun; bit the renorm A/B).

Since 2026-07-20 it also guards the mirror-image failure: the gate must stay INERT to
report-only fields added to the translation record (PLAN item 1's `src`/`src_note`).
Both directions are pinned, because a gate that cannot be fooled by a new key is
worthless if it also stopped noticing a changed one.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.config import Config  # noqa: E402
from overdub.stages.synthesize import SynthesizeStage  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402


def _ctx(tmp: Path, segs: list[dict], units: list[dict] | None, *, complete: bool = True):
    """Workdir with a translation.json and (optionally) a manifest; silero synth_key so
    done() needs no F5 assets on disk for its best-effort warning block."""
    work = WorkDir(root=tmp)
    (tmp / "segments").mkdir(parents=True, exist_ok=True)
    work.translation.write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
    if units is not None:
        cfg = Config()
        doc = {"sample_rate": 48000, "engine": "silero", "voice": "eugene",
               "synth_key": f"silero|eugene|sr={cfg.tts_sample_rate}",
               "units_key": "x", "complete": complete,
               "group_gap_max": cfg.group_gap_max, "base_speed": 1.0, "units": units}
        work.seg_manifest.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    cfg = Config()
    cfg.tts_engine = "silero"           # synth_key must not require F5 assets in a test env
    return SimpleNamespace(cfg=cfg, work=work)


def seg(i, text):
    return {"id": i, "start": i * 2.0, "end": i * 2.0 + 1.5, "src_en": f"en{i}",
            "text_ru": text, "text_tts": text, "status": "ok", "attempts": 1}


def unit(ids, text):
    return {"ids": ids, "path": f"segments/{ids[0]:05d}.wav", "samples": 100,
            "duration": 0.1, "sample_rate": 48000, "start": ids[0] * 2.0,
            "end": ids[-1] * 2.0 + 1.5, "target_sec": 1.5, "max_sec": None,
            "text_tts": text, "flag": None, "speed": None, "seed": None,
            "attempts": 1, "synth_sim": None}


def _run(segs, units, **kw) -> bool:
    with tempfile.TemporaryDirectory() as d:
        return SynthesizeStage().done(_ctx(Path(d), segs, units, **kw))


def test_matching_manifest_skips() -> None:
    segs = [seg(0, "первый"), seg(1, "второй")]
    assert _run(segs, [unit([0], "первый"), unit([1], "второй")]) is True


def test_stale_text_reruns() -> None:
    # the INBOX bug: translation re-run changed text_tts, manifest still complete
    segs = [seg(0, "первый"), seg(1, "НОВЫЙ перевод")]
    assert _run(segs, [unit([0], "первый"), unit([1], "второй")]) is False


def test_grown_translation_reruns() -> None:
    # re-transcribe added a sentence the manifest never rendered
    segs = [seg(0, "первый"), seg(1, "второй"), seg(2, "третий")]
    assert _run(segs, [unit([0], "первый"), unit([1], "второй")]) is False


def test_grouped_unit_matches_joined_text() -> None:
    # multi-member unit compares against the SAME join verify uses (single spaces)
    segs = [seg(0, "первый"), seg(1, "второй")]
    assert _run(segs, [unit([0, 1], "первый второй")]) is True


def test_grouped_unit_stale_member_reruns() -> None:
    segs = [seg(0, "первый"), seg(1, "ДРУГОЙ")]
    assert _run(segs, [unit([0, 1], "первый второй")]) is False


def test_report_only_fields_do_not_invalidate_the_manifest() -> None:
    """PLAN item 1 widened the translation record with `src`/`src_note` — REPORT fields the
    synthesize stage never renders from. If this gate compared whole records instead of the
    fields it actually uses (ids + joined text_tts), the first batch after that change would
    silently re-render every unit in every video: hours of GPU, no error, no flag, and the
    operator's only clue a longer night. Inertness to a new key is a contract, not luck."""
    segs = [seg(0, "первый"), seg(1, "второй")]
    segs[0]["src"] = "ok"
    segs[1]["src"] = "garbled"
    segs[1]["src_note"] = "source sentence duplicates its neighbour"
    assert _run(segs, [unit([0], "первый"), unit([1], "второй")]) is True


def test_report_only_fields_do_not_blind_the_staleness_check() -> None:
    """The other direction, and the reason the test above is not enough on its own: a record
    carrying report fields must STILL re-render when its text_tts actually changed. A gate
    that ignores the new keys by ignoring the whole record would pass the test above."""
    segs = [seg(0, "первый"), seg(1, "НОВЫЙ перевод")]
    segs[0]["src"] = "ok"
    segs[1]["src"] = "ok"
    assert _run(segs, [unit([0], "первый"), unit([1], "второй")]) is False


def test_report_only_fields_survive_grouping() -> None:
    """Grouped units join member text_tts; the report fields of a member must not leak into
    that join (a `src_note` folded into the joined text would re-render the whole group)."""
    segs = [seg(0, "первый"), seg(1, "второй")]
    segs[1]["src"] = "truncated"
    segs[1]["src_note"] = "cut mid-clause"
    assert _run(segs, [unit([0, 1], "первый второй")]) is True


def test_legacy_segments_doc_matches() -> None:
    # pre-units manifests adapt via units_of; identical text must still skip
    segs = [seg(0, "первый")]
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), segs, None)
        doc = {"sample_rate": 48000, "engine": "silero", "voice": "eugene",
               "complete": True,
               "segments": [{"id": 0, "text_tts": "первый", "samples": 100}]}
        ctx.work.seg_manifest.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        assert SynthesizeStage().done(ctx) is True


def test_incomplete_manifest_reruns() -> None:
    segs = [seg(0, "первый")]
    assert _run(segs, [unit([0], "первый")], complete=False) is False


def test_missing_translation_keeps_legacy_gate() -> None:
    # unreadable/absent translation.json → gate must not crash; legacy behavior (skip)
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), [seg(0, "первый")], [unit([0], "первый")])
        ctx.work.translation.unlink()
        assert SynthesizeStage().done(ctx) is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all synthesize.done tests passed")
