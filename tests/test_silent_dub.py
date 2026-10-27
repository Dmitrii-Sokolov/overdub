"""A silent dub never reaches an export — tmpdir + tiny wavs, no ffmpeg, no models.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_silent_dub.py   (or via pytest)

The incident (2026-08-04): per-segment wavs deleted, manifest kept. synthesize fast-skipped on
the manifest, assemble flagged every unit and wrote a full-length dub of digital silence, and
mux.done() saw that dub as NEWER than three good exports. Two gates close it, and both RAISE
before writing anything, so whatever dub and export already exist stay as they were:
assemble refuses a manifest whose voiced wavs are gone; mux refuses a dub with no signal,
whatever produced it.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.config import Config                                    # noqa: E402
from overdub.pipeline import Context                                 # noqa: E402
from overdub.stages import assemble as assemble_mod                  # noqa: E402
from overdub.stages import mux as mux_mod                            # noqa: E402
from overdub.workdir import WorkDir                                  # noqa: E402

SR = 24000
TRANS = [{"id": 0, "src_en": "One.", "text_ru": "Один.", "text_tts": "Один.",
          "start": 0.0, "end": 1.0, "status": "ok"},
         {"id": 1, "src_en": "Two.", "text_ru": "Два.", "text_tts": "Два.",
          "start": 1.0, "end": 2.0, "status": "ok"}]


def _ctx(td: str) -> Context:
    work = WorkDir.for_url("https://youtu.be/aaaaaaaaaaa", Path(td))
    return Context(url="u", cfg=Config(), work=work)


def _manifest(ctx: Context, samples: int) -> None:
    units = [{"ids": [t["id"]], "start": t["start"], "end": t["end"], "samples": samples,
              "text_tts": t["text_tts"]} for t in TRANS]
    ctx.work.seg_manifest.parent.mkdir(parents=True, exist_ok=True)
    ctx.work.seg_manifest.write_text(
        json.dumps({"units": units, "sample_rate": SR, "complete": True}), encoding="utf-8")


def _no_ffmpeg_needed(monkeypatch, module) -> None:
    # both gates sit before the first ffmpeg call; the PATH check above them is all that is faked
    monkeypatch.setattr(module.shutil, "which", lambda _name: "ffmpeg")


# --- assemble: the manifest names voiced wavs that are gone ------------------
def test_assemble_raises_on_missing_voiced_wavs_and_keeps_the_old_dub(monkeypatch) -> None:
    _no_ffmpeg_needed(monkeypatch, assemble_mod)
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        ctx.work.translation.write_text(json.dumps(TRANS, ensure_ascii=False), encoding="utf-8")
        _manifest(ctx, samples=SR)                         # voiced, but no wav on disk
        ctx.work.dub_audio.write_bytes(b"previous good dub")
        try:
            assemble_mod.AssembleStage().run(ctx)
        except RuntimeError as e:
            assert "2 of 2 voiced unit wav(s)" in str(e)
        else:
            raise AssertionError("assemble built a dub from a manifest whose wavs are gone")
        assert ctx.work.dub_audio.read_bytes() == b"previous good dub"


def test_an_unvoiced_unit_without_a_wav_is_not_a_disagreement(monkeypatch) -> None:
    # synth_error / empty_tts units carry samples == 0 and may legitimately have no wav; they
    # keep their per-unit flag path instead of failing the video. Whatever assemble does next
    # on this toy workdir is not the point — only that THIS gate stays quiet.
    _no_ffmpeg_needed(monkeypatch, assemble_mod)
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        ctx.work.translation.write_text(json.dumps(TRANS, ensure_ascii=False), encoding="utf-8")
        _manifest(ctx, samples=0)
        try:
            assemble_mod.AssembleStage().run(ctx)
        except Exception as e:                             # noqa: BLE001
            assert "voiced unit wav" not in str(e), e


# --- mux: the dub has no signal ----------------------------------------------
def test_peak_of_digital_silence_is_below_the_bar_and_speech_is_far_above() -> None:
    with tempfile.TemporaryDirectory() as td:
        quiet, loud, empty = (Path(td) / n for n in ("q.wav", "l.wav", "e.wav"))
        sf.write(str(quiet), np.full(SR, 1e-5, dtype="float32"), SR, subtype="PCM_16")
        sf.write(str(loud), (0.3 * np.sin(np.arange(SR) / 10)).astype("float32"), SR,
                 subtype="PCM_16")
        sf.write(str(empty), np.zeros(SR, dtype="float32"), SR, subtype="PCM_16")
        assert mux_mod.dub_peak_dbfs(empty) == float("-inf")
        assert mux_mod.dub_peak_dbfs(quiet) < mux_mod._SILENT_PEAK_DBFS
        assert mux_mod.dub_peak_dbfs(loud) > -20.0


def test_mux_refuses_a_silent_dub_and_leaves_the_export_alone(monkeypatch) -> None:
    _no_ffmpeg_needed(monkeypatch, mux_mod)
    with tempfile.TemporaryDirectory() as td:
        ctx = _ctx(td)
        ctx.work.source_video.write_bytes(b"video")
        ctx.work.source_bed.write_bytes(b"bed")
        _manifest(ctx, samples=SR)
        sf.write(str(ctx.work.dub_audio), np.zeros(2 * SR, dtype="float32"), SR,
                 subtype="PCM_16")
        ctx.work.output.write_bytes(b"good export")
        try:
            mux_mod.MuxStage().run(ctx)
        except RuntimeError as e:
            assert "silent" in str(e)
        else:
            raise AssertionError("mux shipped a silent dub")
        assert ctx.work.output.read_bytes() == b"good export"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
