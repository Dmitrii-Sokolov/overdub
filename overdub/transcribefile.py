"""`--transcribe-file`: a LOCAL media file → a readable markdown transcript. No dub, no workdir.

WHY THIS IS NOT A PIPELINE STAGE. Every stage keys on a WorkDir built from a YouTube video id,
and the artifacts it leaves are inputs to the next stage. This mode has no next stage: it reads a
file the operator already has and writes one document. Threading it through the pipeline would
mean inventing a video id for a local path and leaving a half-populated workdir behind, which is
the "artifacts that DISAGREE" shape the repo raises on everywhere else.

THE ONE ROUTE THAT IS NOT EN→RU. The pipeline's hard constraint is English in, Russian out; here
there is no translation, so the source language is whatever the file happens to be and the ASR
detects it. Parakeet-TDT v3 is multilingual and CANNOT be told a language (scripts/parakeet_worker
docstring); whisper is asked for `language=None`, i.e. its own detector, rather than
cfg.source_lang — a config key that means "the language the dubbing pipeline expects" and would
force English onto a file that is not.

Everything below the word list is the pipeline's own: _dehallucinate and resegment are imported
from the transcribe stage, so a sentence here is a sentence THERE. A second definition of what a
sentence is would drift within a month.
"""

from __future__ import annotations

import sys
import tempfile
import time
import wave
from pathlib import Path

from .config import Config
from .pipeline import Session
from .stages.transcribe import W, _dehallucinate, resegment, transcribe_words

_SR = 16000
_BYTES_PER_SEC = _SR * 2                 # 16 kHz mono s16 — the wav every ASR path here reads


def clock(sec) -> str:
    """H:MM:SS / M:SS timecode. Deliberately not queueview.format_dur ("6.7m"): these are
    positions to scrub to in a player, not quantities to compare across a report."""
    t = int(round(sec))
    h, m, s = t // 3600, (t // 60) % 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def default_out(src: Path) -> Path:
    """`<dir>/<name>.transcript.md`, beside the source. Built from the STEM, so a second run on
    the same file overwrites its own transcript instead of accumulating `.mp4.md`, `.mkv.md`."""
    return src.parent / (src.stem + ".transcript.md")


def is_pipeline_wav(src: Path) -> bool:
    """True when the file already IS the 16 kHz mono s16 wav the ASR paths read.

    Skipping the ffmpeg pass for such a file is not the point — the point is that this mode then
    needs no external tool at all for that input, which is what makes it testable without ffmpeg
    and usable on a host that has none. Anything unreadable as a wav is simply not one; the
    caller extracts and ffmpeg gives the real diagnosis if the file is broken.
    """
    try:
        with wave.open(str(src), "rb") as w:
            return (w.getnchannels() == 1 and w.getframerate() == _SR
                    and w.getsampwidth() == 2)
    except (OSError, wave.Error):
        return False


def _audio_sec(wav: Path) -> float:
    return wav.stat().st_size / _BYTES_PER_SEC


def _decode(wav: Path, cfg: Config, session: Session) -> tuple[list[W], dict]:
    """(words, engine meta) for a 16 kHz mono wav, through whichever engine cfg selects.

    Mirrors TranscribeStage.run rather than calling it, because that method's contract is a
    WorkDir: it writes words.json/sentences.json and stamps timings.json. The parts worth sharing
    are the ones that decide what the TEXT is, and those are imported, not copied.
    """
    if cfg.asr_engine == "parakeet":
        raw, meta = session.parakeet(cfg).transcribe(wav)
        flat = [W(w["text"], float(w["start"]), float(w["end"]), bool(w.get("seg_end", False)))
                for w in raw]
        return _dehallucinate(flat), meta
    model = session.whisper(cfg, cfg.whisper_model, role="transcribe")
    flat = transcribe_words(model, wav, language=None,
                            beam_size=cfg.whisper_beam_size,
                            condition_on_previous=cfg.whisper_condition_on_previous)
    return flat, {}


def render(sentences: list[dict], *, source: Path, asr_key: str,
           audio_sec: float | None = None) -> str:
    """Sentences → the document. Pure: no I/O, so the format is testable on its own.

    One line per sentence with its start timecode, and NO second copy of the same text without
    them. Two renderings of one transcript in one file is two things to keep in sync for a reader
    who can already ignore a prefix.

    The header carries the asr_key for the same reason timings.json does: a transcript with no
    record of which engine produced it cannot be compared with the next one.
    """
    dur = f"{clock(audio_sec)} · " if audio_sec is not None else ""
    head = [f"# {source.name}", "", f"{dur}{asr_key} · {len(sentences)} sentences", ""]
    if not sentences:
        # Not an empty document: a file with no speech is a RESULT, and it has to be
        # distinguishable from a run that produced nothing because it broke.
        return "\n".join(head + ["_No speech detected._", ""])
    body = [f"**[{clock(s['start'])}]** {s['text']}" for s in sentences]
    return "\n".join(head + ["\n".join(f"{line}\n" for line in body)])


def transcribe_file(src: Path, cfg: Config, *, out: Path | None = None,
                    session: Session | None = None, decode=None) -> Path:
    """Transcribe `src` and write the markdown. Returns the path written.

    `decode` is injectable — (wav) -> (words, meta) — so the mode is testable without a GPU, an
    ASR venv or media, exactly as repair takes `window_asr`. The audio conversion needs no such
    hatch: a source that is already a pipeline wav goes straight through (is_pipeline_wav).
    """
    from .asr import asr_key
    from .stages.download import _extract_wav

    dst = default_out(src) if out is None else out
    session = Session() if session is None else session
    decode = (lambda wav: _decode(wav, cfg, session)) if decode is None else decode

    with tempfile.TemporaryDirectory(prefix="overdub-file-") as tmp:
        if is_pipeline_wav(src):
            wav = src
        else:
            wav = Path(tmp) / "source.wav"
            print(f"[file] {src.name} → 16 kHz mono wav")
            _extract_wav(src, wav)
        t0 = time.perf_counter()
        flat, meta = decode(wav)
        sentences = resegment(flat)
        work_s = time.perf_counter() - t0
        audio_sec = _audio_sec(wav)

    print(f"[file] {len(flat)} words → {len(sentences)} sentences  ({work_s:.1f}s excl. "
          f"model load)")
    unrecovered = meta.get("holes_unrecovered") or []
    if unrecovered:
        # The worker already re-read these once and still got nothing. Same warning the stage
        # prints, for the same reason: silent missing speech reads as a quiet stretch.
        print(f"[warn] {len(unrecovered)} span(s) of speech have NO words after a second read "
              f"({meta.get('hole_sec_unrecovered', 0.0):.0f}s total, first at "
              f"{unrecovered[0][0]:.0f}s) — that part of the file needs an ear", file=sys.stderr)
    if not flat:
        print("[file] no speech detected — the transcript says so rather than being empty")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(render(sentences, source=src, asr_key=asr_key(cfg), audio_sec=audio_sec),
                   encoding="utf-8")
    return dst
