"""Per-video work directory and the canonical artifact paths every stage reads/writes."""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path


def replace_retry(src, dst) -> None:
    """os.replace with a short bounded retry: Windows real-time AV holds freshly written
    files for a moment (the documented host failure mode). Shared by every stage that
    atomically flips a large artifact (segment wavs, dub_ru.wav, output.mkv, source_bed)."""
    for attempt in range(3):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == 2:
                raise
            time.sleep(0.1)

def jpeg_size(path: Path) -> tuple[int, int] | None:
    """(width, height) out of a JPEG's frame header, or None for anything unreadable.

    Lives here rather than in either script because BOTH ends of the scout preview need it and
    both already import this module: build_scout asks "is the thumb.jpg on disk wider than the
    width I now produce" before deciding to re-scale it, and scout_report needs the real ratio to
    give the preview's box an aspect-ratio -- it is painted as a CSS background so one copy of
    the bytes can serve both lists, and a background never sizes its own box.

    A PARSE, not an assumption: previews are scaled to a fixed width with a derived height, so
    the ratio follows the SOURCE. 16:9 covers nearly every YouTube preview and is a fine caller's
    fallback, but a 4:3 frame guessed as 16:9 gets cropped.

    NEVER RAISES. The preview is the one artifact nothing else depends on, so every failure here
    is a None the caller falls back on, not an exception that costs a report."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data.startswith(b"\xff\xd8"):
        return None
    i, n = 2, len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker == 0xFF:                                  # fill byte, skip one and re-read
            i += 1
            continue
        if marker in (0x01, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:      # standalone, no length
            i += 2
            continue
        seg = int.from_bytes(data[i + 2:i + 4], "big")
        if seg < 2:                                         # malformed: a length must cover itself
            return None
        # SOF0..SOF15 carry the frame header. C4/C8/CC share the range and are NOT frame headers
        # (Huffman table, JPEG extension, arithmetic coding conditioning) -- reading dimensions
        # out of one of those yields two plausible-looking numbers that are not the image's size.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            return (w, h) if w and h else None
        i += 2 + seg
    return None


_YT_ID = re.compile(r"(?:v=|/shorts/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})")


def video_id(url: str) -> str:
    """Stable per-video id: the YouTube 11-char id if present, else a url hash."""
    m = _YT_ID.search(url)
    return m.group(1) if m else hashlib.sha1(url.encode("utf-8")).hexdigest()[:11]


_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL",
             *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def safe_filename(name: str, max_len: int = 120) -> str:
    """Windows-safe file name component: forbidden/control chars → '_', length cap, no
    trailing dot/space (cap first — truncation can expose one), reserved device stems
    prefixed (defensive: the ' [<id>].mkv' suffix already breaks exact reserved names).
    Cyrillic passes through untouched (the forbidden set is pure ASCII)."""
    name = _FORBIDDEN.sub("_", name.strip())[:max_len].rstrip(" .")
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return name


@dataclass
class WorkDir:
    root: Path

    @classmethod
    def for_url(cls, url: str, work_root: Path) -> "WorkDir":
        root = Path(work_root) / video_id(url)
        (root / "segments").mkdir(parents=True, exist_ok=True)
        return cls(root)

    # --- artifact paths (one property per stage output) ---
    @property
    def source_video(self) -> Path: return self.root / "source.mkv"

    @property
    def source_audio(self) -> Path: return self.root / "source.wav"      # 16k mono, for whisper

    @property
    def info_json(self) -> Path: return self.root / "source.info.json"   # yt-dlp metadata (title)

    @property
    def words(self) -> Path: return self.root / "words.json"              # transcribe: raw flattened words (re-tuning)

    @property
    def sentences(self) -> Path: return self.root / "sentences.json"      # transcribe

    @property
    def summary(self) -> Path: return self.root / "summary.md"            # sonnet seam (informational, PLAN item 3)

    @property
    def thumb(self) -> Path: return self.root / "thumb.jpg"               # scout report: 160px preview, data-URI'd into the page

    @property
    def translation(self) -> Path: return self.root / "translation.json"  # translate (final)

    @property
    def translation_partial(self) -> Path: return self.root / "translation.jsonl"  # translate (append-only resume trail)

    @property
    def pronounce_audit(self) -> Path: return self.root / "pronounce_audit.json"  # translate (audit-only)

    @property
    def segments_dir(self) -> Path: return self.root / "segments"         # synthesize wavs

    @property
    def seg_manifest(self) -> Path: return self.root / "segments" / "manifest.json"

    def seg_wav(self, sid: int) -> Path:
        """Canonical per-segment wav path — single source of truth for synthesize / verify /
        assemble, so a naming drift can never silently produce missing-wav flags."""
        return self.root / "segments" / f"{sid:05d}.wav"

    @property
    def source_bed(self) -> Path: return self.root / "source_bed.wav"    # separate (Demucs no-vocals bed)

    @property
    def report(self) -> Path: return self.root / "report.json"           # verify flags + speed factors

    @property
    def dub_audio(self) -> Path: return self.root / "dub_ru.wav"          # assemble

    @property
    def en_srt(self) -> Path: return self.root / "en.srt"

    @property
    def ru_srt(self) -> Path: return self.root / "ru.srt"

    @property
    def output(self) -> Path: return self.root / "output.mkv"            # mux

    @property
    def pre_repair_sentences(self) -> Path:
        return self.root / "_pre-repair-sentences.json"   # --repair-asr: the TRUE original,
                                                          # written once, never clobbered

    @property
    def pre_repair_translation(self) -> Path:
        return self.root / "_pre-repair-translation.json"  # --repair-asr: the anomaly report
                                                           # (translation.json) just before the
                                                           # LATEST repair — overwritten per pass

    def invalidate_downstream(self) -> tuple[list[str], list[str]]:
        """Delete exactly the artifacts downstream of sentences.json. Returns (removed, failed)
        as workdir-relative names.

        An EXPLICIT named list, never a blanket wipe, and never a partial one: verify/assemble/
        mux done() all self-heal on manifest synth_key/units_key stamps and mtimes, so an
        INCOMPLETE delete mostly works and then silently ships a stale artifact — the one
        failure class this pipeline forbids. Each survivor is kept for a stated reason:
          source.mkv / source.wav / source.info.json — upstream of transcribe.
          words.json — a transcribe SIBLING, not downstream. DECISIONS 2026-07-19 keeps it as
            the raw record of what the ASR actually did, so asr.floor_ratio keeps reporting
            that this file had a collapse.
          source_bed.wav — NOT downstream: SeparateStage depends only on source.mkv and its
            done() is a bare existence check. Deleting it costs a pointless ~3 GB-VRAM
            htdemucs re-run.
          timings.json — record_stage_timing upserts per stage, so the download/transcribe
            walls stay valid. Deleting it understates total_wall_s and RTF forever, silently.
          out/<title> [<id>].mkv — self-heals: _export_output compares mtimes and a re-mux
            produces a new inode that reads newer (cli.py:171-184).
          segments/_atempo/ — a transient; assemble rmtree-rebuilds it and nothing reads it.

        report.json AND translation.json must BOTH go: runreport._build_run_report self-clears
        run.json only when both are absent.

        summary.md is DOWNSTREAM, not a survivor (added 2026-07-20): the summarizer's only input
        is sentences.json, so a repair makes the prose describe a transcript that no longer
        exists. Nothing in the Python code refreshes it — the only staleness check that exists is
        the mtime filter in the route-B skill, which never runs on the local Gemma route, while
        scripts/run_report.py and scripts/scout_report.py both render it unconditionally and with
        no staleness marker. D2 makes the summary informational, so deleting it costs nothing a
        re-run cannot rebuild; keeping it would let the operator triage a repaired dub against a
        description of the hallucination that was repaired out.
        """
        targets = [
            self.summary,                                # sonnet seam (derived from sentences)
            self.translation,                            # translate
            self.translation_partial,
            self.pronounce_audit,
            self.root / "translation.draft.json",        # route-B Sonnet draft: keyed by id, and
                                                         # a repair renumbers every later id
            self.seg_manifest,                           # synthesize
            self.report,                                 # verify + assemble + mux
            self.dub_audio,                              # assemble
            self.en_srt,
            self.ru_srt,
            self.output,                                 # mux
            self.root / "run.json",                      # derived rollup
            *sorted(self.segments_dir.glob("*.wav")),     # a repair renumbers ids → unit leaders move
        ]
        removed: list[str] = []
        failed: list[str] = []
        for p in targets:
            rel = str(p.relative_to(self.root)).replace("\\", "/")
            try:
                if p.exists():
                    p.unlink()
                    removed.append(rel)
            except OSError as e:
                failed.append(f"{p.name}: {e}")
        return removed, failed
