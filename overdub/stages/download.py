"""Download stage: yt-dlp fetches the source, ffmpeg extracts a 16k mono WAV for STT."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..pipeline import Context
from ..workdir import replace_retry


# yt-dlp's OWN retry knobs, not a loop of our own: it already distinguishes an extractor
# failure from a fragment failure from an HTTP error, and retries each at the right layer.
#
# Measured 2026-07-20: a 12-video scout batch lost two videos to `HTTP Error 403: Forbidden`
# and `Video unavailable`, and BOTH downloaded on the next run of the same command, with the
# same yt-dlp binary and the same URLs — transient, not a property of those videos (their
# audio-only formats were verified present afterwards). Stage-major hoists every download into
# the first minutes of a batch, so a queue arrives at YouTube as one burst; that is the shape
# these errors take. The resume contract already covered it — the operator re-ran and the batch
# completed — so this is not a bug fix, it is spending seconds inside the run to save a
# human-initiated re-run later.
#
# `exp=2:60` backs off 2, 4, 8 … capped at 60 s, which is what a rate-limit needs and what a
# fixed sleep gets wrong in both directions.
_RETRY_ARGV = [
    "--retries", "10",
    "--fragment-retries", "10",
    "--extractor-retries", "5",
    "--retry-sleep", "exp=2:60",
]


class DownloadStage:
    """Fetches the source and produces the two artifacts every later stage keys on.

    TWO GATES, one stage (scout mode, DECISIONS 2026-07-20):
      video-ready = source.mkv AND source.wav  — the unchanged full contract
      audio-ready = source.wav                 — enough for transcribe, and all scout needs

    `audio_only` is an INSTANCE flag, set by stages.scout_stages, because the scout stage LIST
    already differs from the full one: keeping the download variant in the same place means
    "what scout is" has exactly one definition instead of two that can drift.

    This stage MUST NEVER write sentences.json. summary.md survives a promotion only because
    the transcript does not change — the route-B mtime filter keys on it, and nothing else
    enforces that dependency.
    """

    name = "download"

    def __init__(self, *, audio_only: bool = False) -> None:
        self.audio_only = audio_only

    def done(self, ctx: Context) -> bool:
        """Consequence, deliberate (DECISIONS 2026-07-20): a PROMOTED video (scouted, then run
        without --scout) fails the video gate and re-downloads, re-fetching the audio bytes
        inside the merged MKV — ~5% extra traffic in exchange for zero new machinery. Do NOT
        "fix" this by letting the video gate accept source.wav: mux would then get a container
        with no video stream."""
        if self.audio_only:
            return ctx.work.source_audio.exists()
        return ctx.work.source_video.exists() and ctx.work.source_audio.exists()

    def run(self, ctx: Context) -> None:
        self._fetch_audio(ctx) if self.audio_only else self._fetch_video(ctx)

    def _fetch_video(self, ctx: Context) -> None:
        w = ctx.work
        # video kept intact (stream-copied at mux time — never re-encoded)
        subprocess.run(
            [
                "yt-dlp",
                *_RETRY_ARGV,
                "-f", "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b",
                "--merge-output-format", "mkv",
                "--write-info-json",
                "-o", str(w.source_video),
                ctx.url,
            ],
            check=True,
        )
        _extract_wav(w.source_video, w.source_audio)

    def _fetch_audio(self, ctx: Context) -> None:
        """Audio only: source.mkv is NEVER written, so the video-ready gate above stays False and
        a later promotion re-runs the full download. Writing a partial container here would pass
        that gate and hand mux a video-less file.

        `-f bestaudio` with NO '/best' tail, unlike the video branch's '/b'. The fallback would
        pull a full progressive VIDEO stream on a source with no audio-only format — scout
        silently doing the exact thing it exists to prevent, at ~20x the bytes. A hard failure
        there is correct and loud: the video drops out of the scout batch with a FAIL and the
        operator runs it in full mode deliberately. YouTube always has audio-only formats.

        Provenance note, so nobody "fixes" the rewrite later: the scout wav is decoded from
        bestaudio (typically opus/webm), a promoted video's wav from the ba[ext=m4a] inside the
        MKV. Same YouTube master, same timeline, so sentences.json timestamps — computed on the
        scout wav and never recomputed — stay valid and --repair-asr still clips correct windows.
        A repair run performed on the scout workdir clipped from bytes that no longer exist.
        Rejected alternative: skip the extraction when source.wav already exists. It saves the
        rewrite but leaves a wav from a DIFFERENT fetch as the permanent input to a full run —
        a stale artifact served as current.
        """
        w = ctx.work
        for stale in w.root.glob("source.audio.*"):    # orphan from a crashed or --force'd fetch:
            stale.unlink(missing_ok=True)              # would break the one-file invariant below
        subprocess.run(
            [
                "yt-dlp",
                *_RETRY_ARGV,
                "-f", "bestaudio",
                "--write-info-json",
                # the scout report shows a preview beside each title; grabbing it while we are
                # already talking to YouTube costs one request and keeps build_scout offline for
                # every workdir scouted from here on (it self-heals older ones over the network).
                # Failure to fetch it must never fail the video: --no-abort-on-error would be too
                # broad, so the file's absence is simply tolerated downstream.
                "--write-thumbnail", "--convert-thumbnails", "jpg",
                "-o", str(w.root / "source.audio.%(ext)s"),
                ctx.url,
            ],
            check=True,
        )
        self._normalize_info_json(w)
        media = [p for p in sorted(w.root.glob("source.audio.*"))
                 # .jpg is the --write-thumbnail/--convert-thumbnails sidecar (see build_scout.py's
                 # _ensure_thumb, which globs source.audio*.jpg for exactly this file) — a preview,
                 # never the fetched media, so it must not count toward the one-file invariant.
                 if not p.name.endswith(".info.json") and p.suffix.lower() != ".jpg"]
        if len(media) != 1:
            # Picking the first would silently transcribe whichever container sorted lowest —
            # and on a two-file glob one of them is by definition not what yt-dlp just fetched.
            raise RuntimeError(f"scout download: expected exactly one source.audio.* in {w.root}, "
                               f"got {[p.name for p in media]} — yt-dlp output template changed?")
        print(f"       [scout] audio {media[0].stat().st_size / 1e6:.1f} MB "
              f"({media[0].suffix or 'n/a'}) → source.wav")
        _extract_wav(media[0], w.source_audio)
        media[0].unlink(missing_ok=True)               # the wav is the artifact; the container scrap

    def _normalize_info_json(self, w) -> None:
        """--write-info-json derives the sidecar from the -o template AND the real container ext,
        so an audio fetch lands it as source.audio.<ext>.info.json — a name that NEITHER
        cli._title_of (which probes source.info.json and source.mkv.info.json) NOR
        runreport._build_run_report look at. Left alone, every scout workdir pays a 30 s networked
        `yt-dlp --print title` at report time (~50 minutes across a 100-video queue) AND a promoted
        video's run.json silently downgrades video_sec_source from "info_json" to
        "ffprobe"/"sentences". Two silent degradations.

        Renamed after the fact rather than pinned with an `-o infojson:` template: that relies on
        yt-dlp's ext-replacement semantics, which are not stable across versions. A glob + rename
        is version-independent.

        The rename is UNCONDITIONAL when a sidecar exists, deliberately clobbering any
        source.info.json already on disk. The only things that can have written one for a scout
        workdir are an earlier scout fetch (identical content) and _title_of's backfill, which
        writes `{"title": ...}` and NOTHING ELSE — keeping that one would drop `duration` and
        re-introduce exactly the video_sec_source downgrade this method exists to prevent. The
        fresh sidecar is always the superset.

        A miss WARNS loudly rather than raising — a missing title never justifies failing a video
        whose transcript is fine."""
        for cand in sorted(w.root.glob("source.audio*.info.json")):
            replace_retry(cand, w.info_json)
            return
        if not w.info_json.exists():
            print(f"[warn] scout: no info.json sidecar for {w.root.name} — title and duration "
                  f"will need a network lookup at report time")


def _extract_wav(src: Path, dst: Path) -> None:
    """16 kHz mono WAV — whisper's input, and the window source --repair-asr clips from.

    tmp + replace_retry, not `ffmpeg -y` straight onto dst: BOTH done() gates are existence
    checks with no checksum, so a run killed mid-extraction (thermals, a 2am reboot) leaves a
    TRUNCATED source.wav that every later resume accepts as complete — transcribe reads it,
    sentences.json comes out short, and nothing ever says so. Scout is what makes this
    load-bearing: its gate is the first in the pipeline with NO sibling artifact to contradict
    a torn file. Every other large artifact in this repo already goes through replace_retry."""
    tmp = dst.parent / (dst.name + ".tmp")
    tmp.unlink(missing_ok=True)                        # orphan from a prior crash
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src),
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            # explicit "-f wav": ffmpeg picks its output muxer from the EXTENSION, and the
            # atomic tmp above ends in ".tmp", which matches no muxer — without this the call
            # dies with "Unable to choose an output format" before writing a byte and takes
            # BOTH branches down (_fetch_video and _fetch_audio land here), i.e. the whole
            # pipeline, not just scout. Verified against ffmpeg 7.1.1: exit 127 without it.
            # Same hazard the repo already paid for once with soundfile on .../NNNNN.wav.tmp
            # (tts/silero.py, tts/f5_worker.py pass format="WAV") and already guards at
            # mux.py's "-f matroska" for .mkv.tmp. Do NOT "simplify" by renaming the tmp to
            # source.tmp.wav: that makes correctness depend on a filename this module also
            # globs over (source.audio.*).
            "-f", "wav",
            str(tmp),
        ],
        check=True,
    )
    replace_retry(tmp, dst)
