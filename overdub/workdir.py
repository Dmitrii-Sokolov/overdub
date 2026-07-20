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
        scripts/run_report.py and scripts/triage_html.py both render it unconditionally and with
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
