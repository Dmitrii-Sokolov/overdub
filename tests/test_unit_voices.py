"""Unit tests for per-unit voices in the synthesize stage — 2026-10-27.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_unit_voices.py   (or via pytest)
No GPU, no Silero: a recording fake engine, a hand-written diar.json.

The failure classes this pins:

  * TWO SPEAKERS IN ONE UNIT. A unit is one engine call in one voice, so grouping must stop at a
    speaker change however short the gap.
  * THE VOICE DOES NOT REACH THE ENGINE, or the manifest does not say which voice a wav is in.
  * A FEMALE NARRATOR IN A MALE VOICE. A single-speaker video has no `speaker` on its sentences;
    its one speaker still decides the pool.
  * A VOICE CHANGE SERVED FROM CACHE — or re-rendering units whose voice did not change.
  * DIARIZATION OFF CHANGES THE VOICE. Off means tts_voice everywhere, whatever diar.json says.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from overdub.config import Config                                  # noqa: E402
from overdub.pipeline import Context                               # noqa: E402
from overdub.stages.synthesize import SynthesizeStage, build_units  # noqa: E402
from overdub.workdir import WorkDir                                # noqa: E402

MAN = {"speaker": 0, "words": 50, "share": 0.5, "main": True, "f0_hz": 96.0,
       "delta_f_hz": 955.0, "voiced_frames": 900, "pool": "male", "gender": "masculine"}
WOMAN = {"speaker": 1, "words": 50, "share": 0.5, "main": True, "f0_hz": 205.0,
         "delta_f_hz": 1090.0, "voiced_frames": 900, "pool": "female", "gender": "feminine"}


class _Engine:
    supports_seed = False

    def __init__(self, sample_rate: int) -> None:
        self.sample_rate = sample_rate
        self.calls: list[tuple[str, str | None]] = []

    def begin_video(self) -> None:
        return None

    def synthesize(self, text, path, *, seed=None, voice=None, **kw):
        self.calls.append((text, voice))
        sf.write(str(path), np.zeros(self.sample_rate // 10, dtype="float32"), self.sample_rate,
                 format="WAV")


def _seg(i, text, speaker=None):
    s = {"id": i, "start": i * 1.0, "end": i * 1.0 + 0.9, "src_en": "x", "text_ru": text,
         "text_tts": text, "status": "ok"}
    if speaker is not None:
        s["speaker"] = speaker
    return s


def _ctx(tmp: Path, segs, info, cfg: Config | None = None):
    work = WorkDir(root=tmp)
    (tmp / "segments").mkdir(parents=True, exist_ok=True)
    work.translation.write_text(json.dumps(segs, ensure_ascii=False), encoding="utf-8")
    if info is not None:
        work.diar.write_text(json.dumps({"speakers": len(info), "speakers_info": info,
                                         "segments": [], "meta": {}}), encoding="utf-8")
    cfg = cfg or Config()
    cfg.work_root = tmp.parent
    ctx = Context(url="https://youtu.be/x", cfg=cfg, work=work)
    engine = _Engine(cfg.tts_sample_rate)
    ctx.session.tts_engine = lambda c: engine                     # type: ignore[method-assign]
    return ctx, engine


def _run(ctx) -> list[dict]:
    SynthesizeStage().run(ctx)
    return json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))["units"]


def test_a_speaker_change_ends_the_unit() -> None:
    segs = [_seg(0, "а", 0), _seg(1, "б", 0), _seg(2, "в", 1), _seg(3, "г", 1)]
    units = build_units(segs, gap_max=5.0)
    assert [u["ids"] for u in units] == [[0, 1], [2, 3]]
    assert [u["speaker"] for u in units] == [0, 1]


def test_each_unit_is_rendered_and_recorded_in_its_speakers_voice() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx, engine = _ctx(Path(d), [_seg(0, "а", 0), _seg(1, "б", 1)], [MAN, WOMAN])
        units = _run(ctx)
        assert engine.calls == [("а", "eugene"), ("б", "xenia")], engine.calls
        assert [(u["speaker"], u["voice"]) for u in units] == [(0, "eugene"), (1, "xenia")]


def test_a_single_female_narrator_gets_a_female_voice() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx, engine = _ctx(Path(d), [_seg(0, "а"), _seg(1, "б")], [{**WOMAN, "speaker": 0}])
        _run(ctx)
        assert {v for _, v in engine.calls} == {"xenia"}, engine.calls


def test_no_diarization_keeps_tts_voice() -> None:
    for info, diarize in ((None, True), ([{**WOMAN, "speaker": 0}], False)):
        cfg = Config()
        cfg.diarize = diarize
        with tempfile.TemporaryDirectory() as d:
            ctx, engine = _ctx(Path(d), [_seg(0, "а")], info, cfg)
            _run(ctx)
            assert engine.calls == [("а", cfg.tts_voice)], (info, diarize, engine.calls)


def test_a_voice_change_rerenders_only_that_unit() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx, engine = _ctx(Path(d), [_seg(0, "а", 0), _seg(1, "б", 1)], [MAN, WOMAN])
        _run(ctx)
        assert SynthesizeStage().done(ctx) is True
        ctx.cfg.voice_palette_female = ("kseniya", "xenia")
        assert SynthesizeStage().done(ctx) is False
        engine.calls.clear()
        units = _run(ctx)
        assert engine.calls == [("б", "kseniya")], engine.calls
        assert [u["voice"] for u in units] == ["eugene", "kseniya"]
        assert SynthesizeStage().done(ctx) is True


def test_a_manifest_from_before_per_unit_voices_is_reused() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx, engine = _ctx(Path(d), [_seg(0, "а")], None)
        _run(ctx)
        doc = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
        for u in doc["units"]:
            del u["voice"], u["speaker"]
        ctx.work.seg_manifest.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        assert SynthesizeStage().done(ctx) is True
        engine.calls.clear()
        _run(ctx)
        assert engine.calls == []


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all unit-voice tests passed")
