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
    def translation(self) -> Path: return self.root / "translation.json"  # translate (final)

    @property
    def translation_partial(self) -> Path: return self.root / "translation.jsonl"  # translate (append-only resume trail)

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
