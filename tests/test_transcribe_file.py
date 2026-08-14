"""Unit tests for --transcribe-file: a local media file → one markdown transcript.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_transcribe_file.py   (or via pytest)
No GPU, no ASR venv, no ffmpeg, no network. The decode is injected the way repair takes
`window_asr`, and the audio path is exercised with a real 16 kHz mono wav written by stdlib
`wave` — which is exactly the input is_pipeline_wav must let through untouched.

The failure classes this pins:

  * THE MODE STEALS A RUNNING BATCH'S STOP. cli.main's stale-STOP sweep CONSUMES work/STOP. This
    mode owns no workdir, so it must return before that line — otherwise transcribing a file while
    a batch runs silently un-halts the batch.
  * IT SILENTLY BECOMES EN-ONLY. The pipeline is EN→RU by contract and cfg.source_lang says so;
    this route must NOT pass that key to whisper, or a Russian file comes back as English mush.
  * A NO-SPEECH FILE PRODUCES AN EMPTY DOCUMENT. "No speech" is a result and has to read as one —
    an empty file is indistinguishable from a run that broke.
  * A STAGE FLAG IS ACCEPTED AND IGNORED. --force/--only/--scout/--repair-asr select stages; this
    mode runs none, so accepting one would promise work that never happens.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import wave
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from overdub import cli, transcribefile                      # noqa: E402
from overdub.config import Config                            # noqa: E402
from overdub.stages.transcribe import W                      # noqa: E402


def _quiet(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


def _usage_error(fn, *a, **kw) -> str:
    """argv that must die at the argparse gate. Returns the captured stderr.

    Asserts the CODE is argparse's 2, not merely that something exited: every guarded path in
    main() ends in sys.exit(), so "raised SystemExit" is true whether or not the guard exists.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            fn(*a, **kw)
        except SystemExit as e:
            code = e.code
        else:
            raise AssertionError("expected a usage error, but the call returned normally")
    assert code == 2, f"expected argparse's exit code 2, got {code!r} — the guard did not fire"
    return buf.getvalue()


def _wav(path: Path, *, seconds: float = 1.0, rate: int = 16000, channels: int = 1) -> Path:
    """A real, readable wav of digital silence — no numpy, no soundfile, no ffmpeg."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds) * channels)
    return path


def _words(text: str, *, start: float = 0.0, step: float = 0.4) -> list[W]:
    return [W(tok, start + i * step, start + i * step + 0.3, seg_end=False)
            for i, tok in enumerate(text.split())]


# --- the document ---------------------------------------------------------------------

def test_every_sentence_carries_its_start_timecode() -> None:
    doc = transcribefile.render(
        [{"id": 0, "text": "Первое предложение.", "start": 0.0, "end": 2.0},
         {"id": 1, "text": "Второе предложение.", "start": 65.4, "end": 68.0}],
        source=Path("D:/In/clip.mp4"), asr_key="parakeet-tdt-0.6b-v3|vad=True", audio_sec=68.0)
    assert "**[0:00]** Первое предложение." in doc, doc
    assert "**[1:05]** Второе предложение." in doc, doc


def test_an_hour_in_reads_as_hours_not_ninety_minutes() -> None:
    doc = transcribefile.render([{"id": 0, "text": "Late.", "start": 3725.0, "end": 3726.0}],
                                source=Path("clip.mp4"), asr_key="k", audio_sec=3726.0)
    assert "**[1:02:05]**" in doc, doc


def test_the_header_names_the_file_and_the_decode_config() -> None:
    # Same reason timings.json stamps asr_key: a transcript with no record of what produced it
    # cannot be compared with the next one.
    doc = transcribefile.render([{"id": 0, "text": "Hi.", "start": 0.0, "end": 1.0}],
                                source=Path("D:/In/clip.mp4"), asr_key="parakeet|vad=True",
                                audio_sec=402.0)
    assert doc.startswith("# clip.mp4\n"), doc
    assert "parakeet|vad=True" in doc and "6:42" in doc and "1 sentences" in doc, doc


def test_the_text_appears_exactly_once() -> None:
    # A second copy without timecodes would be two renderings of one transcript to keep in sync.
    doc = transcribefile.render([{"id": 0, "text": "Only once.", "start": 0.0, "end": 1.0}],
                                source=Path("clip.mp4"), asr_key="k")
    assert doc.count("Only once.") == 1, doc


def test_no_speech_says_so_instead_of_writing_an_empty_document() -> None:
    doc = transcribefile.render([], source=Path("silent.mp4"), asr_key="k", audio_sec=900.0)
    assert "No speech detected" in doc, doc
    assert "0 sentences" in doc, doc


# --- the audio gate -------------------------------------------------------------------

def test_a_pipeline_wav_is_recognized_and_needs_no_ffmpeg() -> None:
    with tempfile.TemporaryDirectory() as d:
        assert transcribefile.is_pipeline_wav(_wav(Path(d) / "a.wav")) is True


def test_a_wav_at_the_wrong_rate_or_width_is_not_a_pipeline_wav() -> None:
    # 44.1 kHz stereo is what a media file's audio actually is — it MUST go through ffmpeg, or
    # the Parakeet worker rejects it ("expected 16 kHz") halfway into the run.
    with tempfile.TemporaryDirectory() as d:
        assert transcribefile.is_pipeline_wav(
            _wav(Path(d) / "b.wav", rate=44100, channels=2)) is False


def test_a_non_wav_is_not_a_pipeline_wav() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.mp4"
        p.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        assert transcribefile.is_pipeline_wav(p) is False


def test_the_default_output_sits_beside_the_source_and_is_stable() -> None:
    # Built from the stem: a second run must overwrite its own transcript, not add ".mp4.md".
    assert transcribefile.default_out(Path("D:/In/clip.mp4")) == Path("D:/In/clip.transcript.md")
    assert transcribefile.default_out(Path("D:/In/clip.mkv")) == Path("D:/In/clip.transcript.md")


# --- end to end, with the decode injected ---------------------------------------------

def test_it_writes_the_transcript_beside_the_source() -> None:
    with tempfile.TemporaryDirectory() as d:
        src = _wav(Path(d) / "clip.wav", seconds=4.0)
        first = "The first sentence is long enough to stand alone."
        second = "And the second one also clears the merge threshold."
        decode = lambda wav: (_words(first) + _words(second, start=30.0), {})  # noqa: E731
        dst, _ = _quiet(transcribefile.transcribe_file, src, Config(), decode=decode)
        assert dst == Path(d) / "clip.transcript.md"
        doc = dst.read_text(encoding="utf-8")
        assert first in doc and second in doc, doc
        # resegment ran: two sentences, two timecoded lines — not one blob of words
        assert doc.count("**[") == 2, doc


def test_out_overrides_the_destination_and_creates_its_directory() -> None:
    with tempfile.TemporaryDirectory() as d:
        src = _wav(Path(d) / "clip.wav")
        out = Path(d) / "sub" / "dir" / "text.md"
        dst, _ = _quiet(transcribefile.transcribe_file, src, Config(), out=out,
                        decode=lambda wav: (_words("A sentence long enough to survive."), {}))
        assert dst == out and out.is_file()


def test_an_empty_decode_still_writes_a_transcript() -> None:
    # The no-speech contract the pipeline already has (DECISIONS 2026-08-06), at this seam.
    with tempfile.TemporaryDirectory() as d:
        src = _wav(Path(d) / "silent.wav")
        dst, out = _quiet(transcribefile.transcribe_file, src, Config(), decode=lambda w: ([], {}))
        assert "No speech detected" in dst.read_text(encoding="utf-8")
        assert "no speech" in out.lower(), out


def test_unrecovered_speech_spans_are_reported_not_swallowed() -> None:
    # The worker already re-read these once and got nothing. Missing speech is silent by nature:
    # it reads as a quiet stretch in the document.
    with tempfile.TemporaryDirectory() as d:
        src = _wav(Path(d) / "clip.wav")
        meta = {"holes_unrecovered": [[30.0, 71.0]], "hole_sec_unrecovered": 41.0}
        _, out = _quiet(transcribefile.transcribe_file, src, Config(),
                        decode=lambda wav: (_words("A sentence long enough to survive."), meta))
        assert "NO words after a second read" in out, out
        assert "30" in out, out


def test_the_decoded_wav_is_the_source_itself_when_it_is_already_16k_mono() -> None:
    # Not a micro-optimization: it is what makes this mode work on a host with no ffmpeg, and
    # what makes these tests possible at all.
    with tempfile.TemporaryDirectory() as d:
        src = _wav(Path(d) / "clip.wav")
        seen: list[Path] = []

        def decode(wav):
            seen.append(Path(wav))
            return _words("A sentence long enough to survive."), {}

        _quiet(transcribefile.transcribe_file, src, Config(), decode=decode)
        assert seen == [src], seen


def test_the_language_is_never_forced_to_the_pipelines_source_lang() -> None:
    """The EN→RU constraint belongs to the DUBBING pipeline. This route reads whatever file it is
    given, so whisper must get language=None (its own detector) and Parakeet cannot be told at
    all. Passing cfg.source_lang here would turn a Russian file into English mush."""
    calls: list[dict] = []

    class _FakeSession:
        def whisper(self, cfg, model, *, role):
            return object()

        def parakeet(self, cfg):
            raise AssertionError("the whisper path must not start the parakeet worker")

    def _spy(model, audio_path, *, language, beam_size, condition_on_previous):
        calls.append({"language": language, "beam_size": beam_size})
        return []

    real = transcribefile.transcribe_words
    transcribefile.transcribe_words = _spy
    try:
        cfg = Config(asr_engine="whisper")
        assert cfg.source_lang == "en"          # the pipeline's contract, deliberately not used
        transcribefile._decode(Path("x.wav"), cfg, _FakeSession())
    finally:
        transcribefile.transcribe_words = real
    assert calls == [{"language": None, "beam_size": cfg.whisper_beam_size}], calls


# --- the CLI gate ---------------------------------------------------------------------

def test_a_url_and_a_file_together_are_a_usage_error() -> None:
    with tempfile.TemporaryDirectory() as d:
        src = _wav(Path(d) / "clip.wav")
        err = _usage_error(cli.main, ["https://youtu.be/x", "--transcribe-file", str(src)])
        assert "exactly one of" in err, err


def test_a_batch_and_a_file_together_are_a_usage_error() -> None:
    with tempfile.TemporaryDirectory() as d:
        src = _wav(Path(d) / "clip.wav")
        q = Path(d) / "queue.txt"
        q.write_text("https://youtu.be/x\n", encoding="utf-8")
        err = _usage_error(cli.main, ["--batch", str(q), "--transcribe-file", str(src)])
        assert "exactly one of" in err, err


def test_no_input_at_all_is_still_a_usage_error() -> None:
    assert "exactly one of" in _usage_error(cli.main, [])


def test_stage_flags_are_refused_rather_than_ignored() -> None:
    with tempfile.TemporaryDirectory() as d:
        src = _wav(Path(d) / "clip.wav")
        for flag in (["--force"], ["--only", "transcribe"], ["--scout"],
                     ["--repair-asr", "auto"]):
            err = _usage_error(cli.main, ["--transcribe-file", str(src), *flag])
            assert "does not apply to --transcribe-file" in err, (flag, err)


def test_out_without_the_mode_is_a_usage_error() -> None:
    # Otherwise `overdub <url> --out x.md` looks like it redirects the export and does nothing.
    err = _usage_error(cli.main, ["https://youtu.be/x", "--out", "x.md"])
    assert "--out applies to --transcribe-file only" in err, err


def test_a_missing_file_dies_at_the_gate_before_any_work() -> None:
    err = _usage_error(cli.main, ["--transcribe-file", "D:/nope/missing.mp4"])
    assert "file not found" in err, err


def test_the_mode_returns_before_the_stale_STOP_sweep_consumes_a_live_STOP() -> None:
    """cli.main's startup sweep DELETES work/STOP. Transcribing a file while a batch runs must not
    un-halt that batch — so this mode has to return before that line, not after it."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = tmp / "work"
        work.mkdir()
        stop = work / "STOP"
        stop.write_text("", encoding="utf-8")
        cfg_file = tmp / "overdub.toml"
        cfg_file.write_text(f'work_root = "{work.as_posix()}"\n', encoding="utf-8")
        src = _wav(tmp / "clip.wav")

        called: list[Path] = []

        def _fake(src_path, cfg, *, out, session=None, decode=None):
            called.append(Path(src_path))
            return tmp / "clip.transcript.md"

        real = transcribefile.transcribe_file
        transcribefile.transcribe_file = _fake
        try:
            try:
                _quiet(cli.main, ["--transcribe-file", str(src), "--config", str(cfg_file)])
            except SystemExit as e:
                assert e.code == 0, e.code
        finally:
            transcribefile.transcribe_file = real
        assert called == [src], called
        assert stop.exists(), "the mode consumed a STOP file it has no business touching"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all transcribe-file tests passed")
