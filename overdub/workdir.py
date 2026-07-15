"""Per-video work directory and the canonical artifact paths every stage reads/writes."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_YT_ID = re.compile(r"(?:v=|/shorts/|youtu\.be/|/embed/)([A-Za-z0-9_-]{11})")


def video_id(url: str) -> str:
    """Stable per-video id: the YouTube 11-char id if present, else a url hash."""
    m = _YT_ID.search(url)
    return m.group(1) if m else hashlib.sha1(url.encode("utf-8")).hexdigest()[:11]


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
