"""Unit tests for the mux TRACK SET — pure, no ffmpeg, no media, no numpy work.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_mux_tracks.py   (or via pytest)

Contract: only source.mkv is required. The dub and the two subtitle tracks are optional, and a
missing one is omitted END TO END — input, -map, codec, metadata and disposition together. The
failure this guards is specific: a -map that outlives its -i names an input that does not
exist, and ffmpeg reports that as a stream-specifier error at the END of an hour-long run,
which reads as "mux is broken", not as "there was no dub".

The full-track case is pinned VERBATIM against the argv that shipped before the tracks became
optional. That is the whole safety argument for the refactor: the normal path must be
byte-identical, or every muxed video since 2026-07-15 stops being comparable to the next one.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub.config import Config                                    # noqa: E402
from overdub.pipeline import Context                                 # noqa: E402
from overdub.stages.mux import (MuxStage, gained_tracks, mux_args,   # noqa: E402
                                tracks_on_disk)
from overdub.workdir import WorkDir                                  # noqa: E402

V, D, EN, RU, OUT = "src.mkv", "mix.wav", "en.srt", "ru.srt", "out.mkv.tmp"
ALL_SUBS = [("eng", EN), ("rus", RU)]

# The exact command mux.run built for a complete workdir before the tracks became optional.
_SHIPPED = [
    "ffmpeg", "-y", "-loglevel", "error",
    "-i", V, "-i", D, "-i", EN, "-i", RU,
    "-map", "0:v:0", "-map", "0:a:0", "-map", "1:a:0", "-map", "2:0", "-map", "3:0",
    "-c:v", "copy", "-c:a:0", "copy", "-c:a:1", "aac", "-b:a:1", "192k",
    "-c:s", "srt",
    "-metadata:s:a:0", "language=eng", "-metadata:s:a:0", "title=Original",
    "-metadata:s:a:1", "language=rus",
    "-metadata:s:a:1", "title=Russian dub (bed)",
    "-metadata:s:s:0", "language=eng", "-metadata:s:s:1", "language=rus",
    "-disposition:a:0", "0", "-disposition:a:1", "default",
    "-f", "matroska", OUT,
]


def _args(*, dub=D, subs=ALL_SUBS, mix="bed") -> list[str]:
    return mux_args(V, dub=dub, subs=subs, out=OUT, dub_mix=mix)


def _map_indices(cmd: list[str]) -> list[int]:
    return [int(cmd[i + 1].split(":")[0]) for i, tok in enumerate(cmd) if tok == "-map"]


def _n_inputs(cmd: list[str]) -> int:
    return sum(1 for tok in cmd if tok == "-i")


# --- the normal path may not move ---------------------------------------------
def test_full_track_set_is_byte_identical_to_the_shipped_command() -> None:
    assert _args() == _SHIPPED


def test_dub_mix_reaches_the_track_title() -> None:
    assert "title=Russian dub (duck)" in _args(mix="duck")


# --- degraded shapes ----------------------------------------------------------
def test_no_dub_drops_input_map_codec_and_disposition_together() -> None:
    cmd = _args(dub=None)
    assert D not in cmd                                   # no input
    assert "1:a:0" not in cmd                             # no map at the vacated index
    assert "aac" not in cmd and "-b:a:1" not in cmd        # no encoder for a track that is gone
    assert not [t for t in cmd if t.startswith("-disposition")]
    assert not [t for t in cmd if t.startswith("-metadata:s:a:1")]
    assert "-c:a:0" in cmd and "copy" in cmd               # the original is still stream-copied


def test_subtitle_inputs_shift_down_when_the_dub_is_absent() -> None:
    cmd = _args(dub=None)
    assert cmd[cmd.index(EN) - 1] == "-i" and cmd.index(EN) < cmd.index(RU)
    assert _map_indices(cmd) == [0, 0, 1, 2]               # v, orig, en, ru — no gap at 1


def test_only_en_srt_present_numbers_one_subtitle_stream() -> None:
    cmd = _args(subs=[("eng", EN)])
    assert "-metadata:s:s:0" in cmd and "-metadata:s:s:1" not in cmd
    assert cmd[cmd.index("-metadata:s:s:0") + 1] == "language=eng"


def test_only_ru_srt_present_lands_on_stream_zero_as_russian() -> None:
    # the lang travels with the FILE, not with a fixed slot: a lone ru.srt must not be
    # stamped eng just because it is the first subtitle stream
    cmd = _args(subs=[("rus", RU)])
    assert cmd[cmd.index("-metadata:s:s:0") + 1] == "language=rus"
    assert "-metadata:s:s:1" not in cmd


def test_no_subtitles_at_all_drops_the_subtitle_codec() -> None:
    cmd = _args(subs=[])
    assert "-c:s" not in cmd and "srt" not in cmd
    assert not [t for t in cmd if t.startswith("-metadata:s:s:")]


def test_video_and_original_audio_survive_every_combination() -> None:
    for dub in (D, None):
        for subs in ([], [("eng", EN)], [("rus", RU)], ALL_SUBS):
            cmd = mux_args(V, dub=dub, subs=subs, out=OUT, dub_mix="bed")
            assert "0:v:0" in cmd and "0:a:0" in cmd, (dub, subs)
            assert cmd[-3:] == ["-f", "matroska", OUT], (dub, subs)


def test_every_map_points_at_an_input_that_exists() -> None:
    # THE invariant the function exists for: an index past the last -i is an ffmpeg
    # stream-specifier error at the very end of a long run
    for dub in (D, None):
        for subs in ([], [("eng", EN)], [("rus", RU)], ALL_SUBS):
            cmd = mux_args(V, dub=dub, subs=subs, out=OUT, dub_mix="bed")
            n = _n_inputs(cmd)
            assert max(_map_indices(cmd)) < n, (dub, subs, cmd)
            assert sorted(set(_map_indices(cmd))) == list(range(n)), (dub, subs, cmd)


# --- gained_tracks: upgrade only ----------------------------------------------
def test_a_track_that_appeared_triggers_a_remux() -> None:
    stamped = {"dub": False, "en_srt": True, "ru_srt": False}
    now = {"dub": True, "en_srt": True, "ru_srt": True}
    assert gained_tracks(stamped, now) == ["dub", "ru_srt"]


def test_a_track_that_vanished_does_not() -> None:
    # workdir cleanup deletes binaries after a successful mux — re-muxing there would strip
    # the RU track out of an MKV that already shipped it
    stamped = {"dub": True, "en_srt": True, "ru_srt": True}
    assert gained_tracks(stamped, {"dub": False, "en_srt": True, "ru_srt": True}) == []


def test_no_stamp_yields_no_gain_claims() -> None:
    assert gained_tracks(None, {"dub": True}) == ["dub"]
    assert gained_tracks({"dub": True}, None) == []


# --- done(): the gate a degraded output must not survive ----------------------
def _workdir(td: str) -> Context:
    work = WorkDir.for_url("https://youtu.be/aaaaaaaaaaa", Path(td))
    return Context(url="u", cfg=Config(), work=work)


def _stamp(ctx: Context, tracks: dict) -> None:
    ctx.work.report.write_text(
        json.dumps({"mux": {"dub_mix": "bed", "tracks": tracks}}), encoding="utf-8")


def _touch(path: Path, mtime: float) -> None:
    path.write_bytes(b"x")
    os.utime(path, (mtime, mtime))


def test_degraded_output_stays_done_while_nothing_new_arrived() -> None:
    with tempfile.TemporaryDirectory() as td:
        ctx = _workdir(td)
        _touch(ctx.work.en_srt, 1000)
        _touch(ctx.work.output, 2000)
        _stamp(ctx, {"dub": False, "en_srt": True, "ru_srt": False})
        assert MuxStage().done(ctx) is True


def test_a_dub_arriving_with_an_older_mtime_still_remuxes() -> None:
    # the case the make-style mtime check CANNOT see: a hardlinked baseline (work-exp/) lands
    # with the mtime of the file it was linked from, which can predate output.mkv
    with tempfile.TemporaryDirectory() as td:
        ctx = _workdir(td)
        _touch(ctx.work.en_srt, 1000)
        _touch(ctx.work.output, 2000)
        _touch(ctx.work.dub_audio, 1500)                   # older than output.mkv
        _stamp(ctx, {"dub": False, "en_srt": True, "ru_srt": False})
        assert MuxStage().done(ctx) is False


def test_a_deleted_dub_does_not_force_a_downgrade_remux() -> None:
    with tempfile.TemporaryDirectory() as td:
        ctx = _workdir(td)
        _touch(ctx.work.en_srt, 1000)
        _touch(ctx.work.ru_srt, 1000)
        _touch(ctx.work.output, 2000)
        _stamp(ctx, {"dub": True, "en_srt": True, "ru_srt": True})
        assert MuxStage().done(ctx) is True


def test_tracks_on_disk_reads_the_three_optional_artifacts() -> None:
    with tempfile.TemporaryDirectory() as td:
        ctx = _workdir(td)
        assert tracks_on_disk(ctx.work) == {"dub": False, "en_srt": False, "ru_srt": False}
        _touch(ctx.work.ru_srt, 1000)
        assert tracks_on_disk(ctx.work) == {"dub": False, "en_srt": False, "ru_srt": True}


def test_a_legacy_report_without_a_tracks_stamp_keeps_the_old_gate() -> None:
    # pre-2026-07-28 workdirs: absent tracks means UNKNOWN, so nothing may be inferred from it
    with tempfile.TemporaryDirectory() as td:
        ctx = _workdir(td)
        _touch(ctx.work.output, 2000)
        _touch(ctx.work.dub_audio, 1500)
        ctx.work.report.write_text(json.dumps({"mux": {"dub_mix": "bed"}}), encoding="utf-8")
        assert MuxStage().done(ctx) is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all mux track-set tests passed")
