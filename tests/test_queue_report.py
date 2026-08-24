"""Unit tests for scripts/queue_report.py — the queue page (dub triage in queue order).

ONE page per queue since 2026-07-21 (the queue-page merge); the scouting half was deleted on
2026-08-24, so what this suite covers is the dub-triage surface, the pipeline-state cards, and
the cross-surface parity that keeps the digest (scripts/run_report.py) and this page agreeing
about the same bytes on disk.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_queue_report.py   (or via pytest)

Pure string assembly and JSON over tmp dirs: no GPU, no network, no media, no yt-dlp. The
load-bearing invariants, in the order they would silently break the deliverable:

  ORDER IS THE QUEUE'S. The report exists to be read next to the playlist it came from, so a
  re-sorted card is a wrong card even when every field in it is right. The morning-listen job is
  served by the nav block of anchors, without touching the order.

  A QUEUED VIDEO NEVER VANISHES. No artifacts → an explicit state card, because a report that
  silently renders only the videos that worked reads as complete.

  PROSE IS ESCAPED. Titles and translator notes are raw LLM or YouTube text going into HTML.

  NO FABRICATED DUB METRICS. A card never borrows a dub chip, an RTF or a player for a video
  that was never dubbed.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import dub_blocks  # noqa: E402
import queue_report  # noqa: E402
import run_report  # noqa: E402  — the cross-surface tests run both renderers over one workdir
from overdub import queueview  # noqa: E402
from overdub.workdir import THUMB_W, WorkDir, ensure_thumb_local, jpeg_size  # noqa: E402


def _queue(root: Path, ids: list[str]) -> Path:
    q = root / "queue.txt"
    q.write_text("\n".join(f"https://www.youtube.com/watch?v={i}" for i in ids) + "\n",
                 encoding="utf-8")
    return q


def _cfg(root: Path) -> Path:
    c = root / "overdub.toml"
    c.write_text(f'work_root = "{root.as_posix()}"\n', encoding="utf-8")
    return c


def _report(argv: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = queue_report.main(argv)
    return code, buf.getvalue()


def _dubbed(root: Path, vid: str, *, verify_flags=("low_similarity", None), translation=None,
            wav=(), title="Dub Talk", duration=300.0) -> Path:
    """A dubbed workdir: report.json + translation.json (+ info/timings) — the exact input
    shape build_run_report rolls up, so the page exercises the REAL data path, not a
    hand-shaped run dict. One report unit per verify_flags entry (unit i = sentence i);
    a flagged unit is also fast (combined 2.0) so it carries a speed reason too."""
    d = root / vid
    (d / "segments").mkdir(parents=True, exist_ok=True)
    segs = []
    for i, vf in enumerate(verify_flags):
        segs.append({"id": i, "group_id": i, "status": "ok", "verify_flag": vf,
                     "combined_factor": 2.0 if vf else 1.0, "speed_factor": 1.5 if vf else 1.0,
                     "assemble_flag": None, "completeness_flags": [], "translate_flag": None,
                     "similarity": 0.42 if vf else 0.98,
                     "hypothesis": "что-то не то" if vf else None})
    n_fl = sum(1 for vf in verify_flags if vf)
    report = {"segments": segs,
              "verify": {"model": "small", "n_units": len(segs), "n_segments": len(segs),
                         "n_flagged": n_fl, "n_retried": 0, "n_repaired": 0},
              "completeness": {"n_sentences": len(segs), "n_flagged": 0, "n_num_loss": 0,
                               "n_neg_loss": 0, "n_length": 0},
              "assemble": {"duration_sec": duration, "n_sped": n_fl,
                           "in_span_silence_sec": 0.0},
              "mux": {"dub_mix": "bed", "dub_gain_db": 3.0}}
    if translation is None:
        translation = [{"id": i, "status": "ok", "src_en": f"EN {i}", "text_ru": f"РУ {i}",
                       "text_tts": f"тэ-тэ-эс {i}", "start": float(i) * 3.0,
                        "end": float(i) * 3.0 + 3.0, "src": "ok"}
                       for i in range(len(segs))]
    (d / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    (d / "translation.json").write_text(json.dumps(translation, ensure_ascii=False),
                                        encoding="utf-8")
    (d / "source.info.json").write_text(json.dumps({"title": title, "duration": duration}),
                                        encoding="utf-8")
    (d / "timings.json").write_text(json.dumps({"stages": {"download": 5.0,
                                                           "synthesize": 55.0}}),
                                    encoding="utf-8")
    for sid in wav:
        (d / "segments" / f"{sid:05d}.wav").write_bytes(b"RIFF-fake-wav-bytes")
    return d


def _transcribed(root: Path, vid: str, *, n=431, info=True, ends=True, mkv=False) -> Path:
    """A transcript-only workdir (--transcribe-only shape; add mkv=True for the promoted
    'pending' shape). `ends` off = sentences with no numeric `end`, the only shape from which
    no duration at all can be derived."""
    d = root / vid
    (d / "segments").mkdir(parents=True, exist_ok=True)
    (d / "sentences.json").write_text(json.dumps(
        [{"id": i, "text": f"s{i}", "start": float(i),
          **({"end": float(i) + 1.0} if ends else {})} for i in range(n)]), encoding="utf-8")
    if info:
        (d / "source.info.json").write_text(
            json.dumps({"title": "Transcribed Talk", "duration": 2530.0}), encoding="utf-8")
    if mkv:
        (d / "source.mkv").write_bytes(b"mkv")
    return d


def _card_of(page: str, n: int) -> str:
    """The card slice for queue position n — everything between its anchor and its close."""
    return page.split(f'id="v{n}"', 1)[1].split("</article>", 1)[0]


# --- order, completeness, states ------------------------------------------------

def test_cards_follow_the_queue_order() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", title="Первое в очереди")
        _dubbed(root, "vid00000002", title="Второе в очереди")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert page.index("Первое в очереди") < page.index("Второе в очереди")
    assert page.index('id="v1"') < page.index('id="v2"')


def test_a_queued_video_without_artifacts_still_gets_a_card() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001", "vid00000002"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    # vid00000002 has no workdir at all → "не скачано", the state whose fix is re-running step 1
    assert "vid00000002" in page and "не скачано" in page
    assert "не скачано" in log                 # and the operator is told, not just the page


def test_unfinished_states_are_told_apart() -> None:
    # Each needs a DIFFERENT action: re-run the fetch / investigate transcribe / resume route B.
    # Collapsing them sends the operator to the wrong one.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")                              # complete dub
        _transcribed(root, "vid00000002")                         # transcript only (route E)
        (root / "vid00000003" / "segments").mkdir(parents=True)   # audio only, no transcript
        (root / "vid00000003" / "source.wav").write_bytes(b"RIFF")
        # vid00000004: nothing at all on disk
        q = _queue(root, [f"vid0000000{i}" for i in (1, 2, 3, 4)])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    for label in ("расшифровано", "не расшифровано", "не скачано"):
        assert label in page
    for label in ("не расшифровано", "не скачано"):
        assert label in log


def test_a_transcript_outranks_a_missing_wav() -> None:
    # A promotion rewrites source.wav and a cleanup can delete it; the transcript still proves
    # the download happened. Probing the wav first would order a pointless re-fetch.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = _transcribed(root, "vid00000001")
        assert not (wd / "source.wav").exists()
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "расшифровано" in page and "не скачано" not in page


def test_numbering_follows_the_queue_and_survives_a_gap() -> None:
    # The number is the reader's index into the playlist they have open, so a video that failed
    # to download must KEEP its position rather than being renumbered around.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        # vid00000002 missing entirely
        _dubbed(root, "vid00000003")
        q = _queue(root, ["vid00000001", "vid00000002", "vid00000003"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert '<span class="idx">2</span>' in page                   # the gap keeps its number
    assert page.index('id="v1"') < page.index('id="v3"')


def test_title_links_to_the_video() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "https://www.youtube.com/watch?v=vid00000001" in page
    assert 'rel="noopener"' in page


def test_an_unfetched_card_still_links_to_its_video() -> None:
    # That card exists to send the reader to look at the thing; a dead title defeats it.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        q = _queue(root, ["vid00000009"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "https://www.youtube.com/watch?v=vid00000009" in page


def test_the_card_number_is_a_label_not_a_link() -> None:
    # The reader arrives from the dub table or the nav; their own back gesture returns them, so
    # a jump back was a link that never earned its underline.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert 'id="v1"' in page
    assert 'href="#r1"' not in page
    assert '<span class="idx">1</span>' in page


def test_playlist_header_is_named_and_linked() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = root / "queue.txt"
        q.write_text("# playlist: AI Fluency | https://youtube.com/playlist?list=PL123\n"
                     "https://www.youtube.com/watch?v=vid00000001\n", encoding="utf-8")
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "AI Fluency" in page
    assert "https://youtube.com/playlist?list=PL123" in page


def test_playlist_header_is_optional_and_backward_compatible() -> None:
    # Every queue written before the header existed must keep working, header or not.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])                     # no header at all
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        assert code == 0
        assert queue_report.queue_playlist(q) is None
        # and the '#' line is still not mistaken for a video
        assert queue_report.queue_ids(q) == ["vid00000001"]


def test_playlist_header_accepts_a_bare_url() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        q = root / "queue.txt"
        q.write_text("# playlist: https://youtube.com/playlist?list=PL9\n", encoding="utf-8")
        pl = queue_report.queue_playlist(q)
    assert pl["url"] == "https://youtube.com/playlist?list=PL9"
    assert pl["title"] == "https://youtube.com/playlist?list=PL9"


def test_queue_order_dedupes_but_keeps_first_position() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        q = root / "queue.txt"
        q.write_text("https://youtu.be/vid00000001\n# comment\n\n"
                     "https://www.youtube.com/watch?v=vid00000002\n"
                     "https://www.youtube.com/watch?v=vid00000001\n", encoding="utf-8")
        assert queue_report.queue_ids(q) == ["vid00000001", "vid00000002"]


# --- the thumbnail --------------------------------------------------------------

def test_thumbnail_is_inlined_not_linked() -> None:
    # A remote src is blocked outright by the Artifact CSP — invisible exactly where the page is
    # meant to be read. The bytes ride a CSS rule (declared once), never an <img> src.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        (root / "vid00000001" / "thumb.jpg").write_bytes(b"\xff\xd8\xff\xdb-fake-jpeg")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert page.count("data:image/jpeg;base64,") == 1
    assert 'class="thumb t1"' in page
    assert "i.ytimg.com" not in page


def test_the_rendered_preview_never_asks_for_more_pixels_than_are_stored() -> None:
    # Two files, one number, and nothing but a comment holding them together — which is exactly
    # how the page once upscaled a 160px file into a 320px slot and went soft.
    #
    # A CEILING, not an equality: rendering NARROWER than the file on disk is the 2x-source case
    # (sharp on hi-DPI) and must stay allowed. Asserting equality would have failed the moment
    # the preview was halved — a guard that fires on the safe direction gets deleted, and then
    # the unsafe direction is unguarded too.
    widths = [int(w) for w in re.findall(r"\.thumb\{[^}]*?width:(\d+)px", queue_report._CSS)]
    assert widths, "no .thumb width in the CSS — the rule was renamed and this guard went blind"
    assert max(widths) <= THUMB_W


def test_the_preview_is_out_of_reach_of_the_artifact_skeletons_img_reset() -> None:
    # The published page is wrapped in a skeleton carrying `img{max-width:100%}`, which can
    # squeeze an <img> preview to a sliver — visible only after publishing, never when the
    # fragment is opened locally. The preview is a <div> now, which that selector cannot reach;
    # the conditional keeps the guard true whichever element the preview goes back to being.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        (root / "vid00000001" / "thumb.jpg").write_bytes(b"\xff\xd8\xff\xdb-fake-jpeg")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    # the static sheet is stripped first: it is prose about this very trap, and a tag named
    # inside a comment is not the page rendering one
    if "<img" in page.replace(queue_report._CSS, ""):
        assert "max-width:none" in queue_report._CSS, (
            "the preview is an <img> again — the skeleton's reset can reach it, and without "
            "max-width:none it collapses once published")


def _jpeg(w: int, h: int, marker: bytes = b"\xc0") -> bytes:
    """Minimal JPEG carrying nothing but a frame header of the given size."""
    sof = b"\xff" + marker + b"\x00\x11\x08" + h.to_bytes(2, "big") + w.to_bytes(2, "big")
    return b"\xff\xd8" + sof + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01" + b"\xff\xd9"


def test_jpeg_size_reads_the_frame_header() -> None:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.jpg"
        p.write_bytes(_jpeg(160, 90))
        assert jpeg_size(p) == (160, 90)
        p.write_bytes(_jpeg(160, 120))                    # a 4:3 source, the case 16/9 would crop
        assert jpeg_size(p) == (160, 120)


def test_jpeg_size_never_raises_and_never_guesses() -> None:
    # The preview is the one thing on the page nothing depends on — every failure here has to be
    # a None the caller falls back on, never an exception that costs the operator a report.
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.jpg"
        assert jpeg_size(p) is None                      # absent
        p.write_bytes(b"not a jpeg at all")
        assert jpeg_size(p) is None                      # wrong magic
        p.write_bytes(b"\xff\xd8" + b"\xff\xc0\x00\x01")              # length that cannot self-cover
        assert jpeg_size(p) is None
        # 0xC4 lives in the SOF range and is NOT a frame header — reading it would yield two
        # plausible numbers that are not the image's size, which is worse than admitting nothing
        p.write_bytes(_jpeg(160, 90, marker=b"\xc4"))
        assert jpeg_size(p) is None


def _ffmpeg() -> bool:
    """ffmpeg is an external binary the suite must not require — these cases skip without it
    rather than fail, since everything else here is pure string assembly over tmp dirs."""
    import shutil
    return shutil.which("ffmpeg") is not None


def test_an_oversized_preview_on_disk_is_rescaled_not_kept() -> None:
    # `if exists: return` meant lowering THUMB_W changed nothing for any workdir already on
    # disk: every preview kept its old width forever and the reports kept carrying the old bytes.
    # The artifact's size has to be self-correcting -- the number defining it lives in a
    # different file from the files it governs.
    if not _ffmpeg():
        return
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d) / "vid00000001")
        work.root.mkdir(parents=True)
        wide = THUMB_W * 2
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", f"color=c=red:s={wide}x{wide // 16 * 9}:d=1", "-frames:v", "1",
                        str(work.thumb)], check=True)
        assert jpeg_size(work.thumb)[0] == wide                  # precondition
        assert ensure_thumb_local(work) is True
        assert jpeg_size(work.thumb)[0] == THUMB_W
        # no scrap left behind, and above all the preview still exists
        assert not (work.root / "thumb.out.jpg").exists()


def test_a_preview_already_small_enough_is_left_untouched() -> None:
    # Re-encoding a correct file every run would be lossy for nothing.
    if not _ffmpeg():
        return
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d) / "vid00000001")
        work.root.mkdir(parents=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", f"color=c=red:s={THUMB_W}x90:d=1", "-frames:v", "1",
                        str(work.thumb)], check=True)
        before = work.thumb.read_bytes()
        assert ensure_thumb_local(work) is True
        assert work.thumb.read_bytes() == before


def test_an_unmeasurable_preview_is_left_alone_rather_than_re_encoded() -> None:
    # No ffmpeg needed: the guard returns before any subprocess. An unreadable header may still
    # be bytes a browser decodes, and re-encoding what we cannot measure can only guess.
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d) / "vid00000001")
        work.root.mkdir(parents=True)
        work.thumb.write_bytes(b"\xff\xd8 truncated before any SOF")
        before = work.thumb.read_bytes()
        assert ensure_thumb_local(work) is True
        assert work.thumb.read_bytes() == before


def test_a_full_download_sidecar_becomes_the_preview() -> None:
    # A full video fetch writes source.jpg (the -o template is source.mkv); the audio-only
    # fetch writes source.audio.jpg. ensure_thumb_local globs `source*.jpg` so both shapes
    # land, offline.
    if not _ffmpeg():
        return
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d) / "vid00000001")
        work.root.mkdir(parents=True)
        wide = THUMB_W * 2
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", f"color=c=red:s={wide}x{wide // 16 * 9}:d=1", "-frames:v", "1",
                        str(work.root / "source.jpg")], check=True)
        assert ensure_thumb_local(work) is True                  # NO network, no info.json
        assert jpeg_size(work.thumb)[0] == THUMB_W
        assert not (work.root / "source.jpg").exists()           # scrap once scaled
        assert not (work.root / "thumb.out.jpg").exists()


def test_an_empty_workdir_reports_no_preview_rather_than_reaching_for_one() -> None:
    # ensure_thumb_local is what the download stage calls, so it must be provably offline: no
    # sidecar and no thumb means False, never a fetch.
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(Path(d) / "vid00000001")
        work.root.mkdir(parents=True)
        assert ensure_thumb_local(work) is False
        assert not work.thumb.exists()


def test_the_preview_rule_carries_the_real_aspect_not_a_guess() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        (root / "vid00000001" / "thumb.jpg").write_bytes(_jpeg(160, 120))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    # a background box has no size of its own: get this wrong and the preview is either cropped
    # or zero pixels tall
    assert "aspect-ratio:160/120" in page
    assert "aspect-ratio:16/9;background-image" not in page       # the fallback did not fire


def test_an_unparseable_preview_still_renders_on_the_fallback_ratio() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        (root / "vid00000001" / "thumb.jpg").write_bytes(b"\xff\xd8 truncated before any SOF")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    # unreadable header is not a missing preview: the bytes may still be a picture the browser
    # can decode, so it is shown at 16:9 rather than dropped
    assert "aspect-ratio:16/9" in page
    assert page.count("data:image/jpeg;base64,") == 1


def test_a_missing_thumbnail_renders_nothing_at_all() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=(None, None))   # no thumb.jpg written
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    # same stripping as the reset guard: _CSS discusses the preview in prose, the page must not
    # RENDER one — no element, and above all no per-video rule carrying bytes for a file that
    # does not exist
    assert "<img" not in page.replace(queue_report._CSS, "")
    assert "base64" not in page and 'class="thumb' not in page


# --- the page shell -------------------------------------------------------------

def test_prose_and_title_are_escaped() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", title="<script>alert(1)</script>")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_page_is_a_body_fragment_for_the_artifact_publisher() -> None:
    # The publisher supplies doctype/head/body; emitting our own would nest documents.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    low = page.lower()
    for tag in ("<!doctype", "<html", "<head>", "<body"):
        assert tag not in low
    assert "<style>" in low                    # but it IS self-contained


def test_the_local_file_declares_its_own_charset() -> None:
    # The Artifact publisher sets charset on its own skeleton, so the published copy never needed
    # this -- but the module docstring promises the SAME file "opens locally by double-click", and
    # a file:// URL carries no Content-Type header for a browser to read UTF-8 off of. Without this
    # tag a browser guesses and mangles every Cyrillic character in the report. HTML5 only looks in
    # the first 1024 bytes for a charset declaration, so it must lead -- not just be present.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert '<meta charset="utf-8">' in page
    assert page.index('<meta charset="utf-8">') < 1024
    assert page.index('<meta charset="utf-8">') < page.index("<style>")


def test_both_themes_are_defined() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "prefers-color-scheme:dark" in page
    assert '[data-theme="dark"]' in page and '[data-theme="light"]' in page


def test_page_background_bleeds_past_the_content_column() -> None:
    # The .sr column caps at 1240px; the body behind it belongs to the host page, which painted
    # gutters beside the content (white in light hosts) — reported 2026-07-22, predates the
    # merge. Raw colours, not var(--bg): body sits outside .sr's token scope.
    assert "body{margin:0;background:#f7f8fa;}" in queue_report._CSS
    assert "@media (prefers-color-scheme:dark){body{background:#0f1419;}}" in queue_report._CSS
    assert ':root[data-theme="dark"] body{background:#0f1419;}' in queue_report._CSS
    assert ':root[data-theme="light"] body{background:#f7f8fa;}' in queue_report._CSS


def test_cli_requires_a_queue_or_a_workdir() -> None:
    # Neither positional workdirs nor --queue: there is no report to render and guessing a
    # queue file would be worse than saying so.
    buf = io.StringIO()
    try:
        with redirect_stdout(buf), redirect_stderr(buf):
            queue_report.main([])
    except SystemExit as e:
        assert e.code == 2                              # argparse usage-error exit code
    else:
        raise AssertionError("no --queue and no workdirs must be a usage error")


# --- source anomalies on the card (DECISIONS 2026-07-19, migrated) ----------------

def _src_translation():
    """Two OK-dub sentences, one carrying a source anomaly with hostile prose in the note."""
    return [{"id": 0, "status": "ok", "src_en": "EN 0", "text_ru": "РУ 0", "text_tts": "т 0",
             "start": 0.0, "end": 3.0, "src": "truncated",
             "src_note": "ends <script>alert(1)</script> & mid-thought"},
            {"id": 1, "status": "ok", "src_en": "EN 1", "text_ru": "РУ 1", "text_tts": "т 1",
             "start": 3.0, "end": 6.0, "src": "ok"}]


def test_srcanom_absent_when_source_is_clean() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")                    # every src is "ok"
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    # the static sheet is stripped first: _CSS carries the .srcanom RULE on every page; the
    # invariant is that no srcanom ELEMENT renders when the scan found nothing
    assert "srcanom" not in page.replace(queue_report._CSS, "")


def test_srcanom_rendered_and_escaped() -> None:
    # The note is raw LLM prose going into HTML — same escape rule as every other prose field.
    # Deliberately NO <audio> anywhere near it: the defect is in the ENGLISH source, so
    # listening to the Russian tells the operator nothing.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=(None, None), translation=_src_translation())
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    block = page.split('<div class="srcanom">', 1)[1].split("</div>", 1)[0]
    assert "аномалии источника (1)" in block and "truncated" in block
    assert "&lt;script&gt;" in block and "&amp;" in block
    assert "<script>" not in block
    assert "<audio" not in block


def test_srcanom_renders_without_flagged_units() -> None:
    # A clean-verify run can still carry a source anomaly, and that is exactly when the signal
    # is most actionable (--repair-asr is still cheap). The clean-units note stays too.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=(None, None), translation=_src_translation())
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "srcanom" in page
    assert "проблемных юнитов нет — слушать нечего." in page


def test_srcanom_item_renders_the_sentence_id() -> None:
    # The source-anomaly block prints the offending sentence id (the old "#19" pin) so the
    # operator can find it in translation.json / the transcript.
    translation = [
        {"id": 19, "status": "ok", "src_en": "EN", "text_ru": "РУ", "text_tts": "т",
         "start": 0.0, "end": 3.0, "src": "truncated", "src_note": "ends mid-thought"},
        {"id": 1, "status": "ok", "src_en": "EN 1", "text_ru": "РУ 1", "text_tts": "т 1",
         "start": 3.0, "end": 6.0, "src": "ok"}]
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=(None, None), translation=translation)
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    block = page.split('<div class="srcanom">', 1)[1].split("</div>", 1)[0]
    assert "#19" in block and "truncated" in block


# --- the dub table ---------------------------------------------------------------

def _dub_row_cells(page: str, n: int) -> list[str]:
    """The ten verbatim data cells of the dub-table row for queue position n."""
    m = re.search(rf'<td><a class="jump" href="#v{n}">[^<]*</a></td>(.*?)</tr>', page, re.S)
    assert m, f"no dub-table row for position {n}"
    return re.findall(r'<td class="num">([^<]*)</td>', m.group(1))


def test_dub_table_src_dash_when_unscanned() -> None:
    # "-" means NOT SCANNED (no anomaly pass / pre-schema); "0" means scanned AND clean.
    # Conflating the two would report an unscanned video as source-checked when nothing read it.
    no_src = [{"id": i, "status": "ok", "src_en": f"EN {i}", "text_ru": f"РУ {i}",
               "text_tts": f"т {i}", "start": float(i), "end": float(i) + 1.0}
              for i in range(2)]                        # unscanned: no src field at all
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vidNOSRC000", translation=no_src)
        _dubbed(root, "vidOKSRC000")                   # all src "ok" → scanned, clean
        q = _queue(root, ["vidNOSRC000", "vidOKSRC000"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    src_i = [k for k, _l in queueview.BATCH_COLUMNS].index("src") - 2   # minus video+title
    assert _dub_row_cells(page, 1)[src_i] == "-"
    assert _dub_row_cells(page, 2)[src_i] == "0"


def test_dub_table_colours_the_status_cell_by_column_key_not_index() -> None:
    # The triage colour class rides the «слушать»/«чисто» STATUS cell, keyed by column KEY —
    # never by cell index. The retired page hard-coded the index and the src column silently
    # landed on it, so adding a column mis-coloured a data cell. The status cell carries
    # t-triage/t-clean; the first data cell (wall_s) must not.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")                       # flagged → needs triage → «слушать»
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    row = re.search(r'<td><a class="jump" href="#v1">[^<]*</a></td>(.*?)</tr>', page, re.S).group(1)
    assert '<td class="t-triage">слушать</td>' in row       # the STATUS cell carries the colour
    # the first data cell (wall_s) is a plain num cell — the colour did not land on it by index
    first_cell = re.search(r'<td class="num">[^<]*</td>', row).group(0)
    assert "t-triage" not in first_cell and "t-clean" not in first_cell


# --- the state cards -------------------------------------------------------------

def test_transcript_only_card_fabricates_no_dub_metrics() -> None:
    # A transcript-only video has no RTF, no flags, no triage verdict. The page must not leak
    # ANY dub component onto its card or fabricate a dub table/nav around it — borrowing the
    # «чисто» chip would report an undubbed video as verified.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    card = _card_of(page, 1)
    for forbidden in ("<audio", "srcanom", "RTF", 'class="unit"', "слушать", "чисто"):
        assert forbidden not in card, forbidden
    assert "<th>wall_s</th>" not in page                # no dub table on a dub-free page
    assert "требуют прослушивания" not in page          # no dub totals, no nav


def test_counters_exclude_transcript_only_from_the_video_count() -> None:
    # "0 need triage" out of a count that includes never-dubbed videos is a lie about them:
    # stdout counts dubbed videos, transcript-only rides separately, and the page's dub totals
    # line counts only the dubbed.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vidDUBBED00", verify_flags=(None, None))
        _transcribed(root, "vidTRONLY00")
        q = _queue(root, ["vidDUBBED00", "vidTRONLY00"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "1 video(s), 1 transcript-only," in log
    assert "2 video(s)" not in log
    # dub totals: the dubbed one only. The figure is named «работа пайплайна» and printed in H/M
    # since 2026-07-25 — «wall 60.0s» said neither what it was nor how long that is.
    assert "1 видео · работа пайплайна" in page
    assert "2 видео · работа пайплайна" not in page
    assert "(сумма по видео, не время прогона)" in page
    assert " · wall " not in page
    # and the header tally names the transcript-only state
    assert "расшифровано: 1" in page


def test_transcript_only_clause_absent_on_a_dub_only_report() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=(None, None))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
    assert code == 0
    assert "transcript-only" not in log


def test_argv_typo_is_a_named_skip_but_a_queue_id_is_always_carded() -> None:
    # Both directions of "no silent nothing": an argv path with nothing to report is a named
    # skip and no page; the SAME empty dir named by the queue keeps its card — the queue is the
    # deliverable and position is information.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        empty = root / "vidEMPTY000"
        (empty / "segments").mkdir(parents=True)
        out = root / "r.html"
        code, log = _report([str(empty), "--config", str(_cfg(root)), "--out", str(out)])
        assert code == 0
        assert "nothing to render" in log and "skipped (nothing to report)" in log
        assert "vidEMPTY000" in log
        assert not out.exists()                         # nothing renderable → no page
        q = _queue(root, ["vidEMPTY000"])
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "не скачано" in page and "не скачано" in log


def test_empty_sentences_renders_a_zero_card_not_a_skip() -> None:
    # A MISSING sentences.json is a typo'd path, but an EMPTY one PARSED, so transcribe RAN and
    # found nothing — a real answer (don't dub it). The count is reported, never suppressed.
    # (Reachable: resegment([]) → [] under vad_filter=True on a speech-free video.)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vidEMPTY000", n=0, info=False)
        q = _queue(root, ["vidEMPTY000"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "предложений: 0" in page
    assert "расшифровано" in page                       # a real state, not a typo'd path
    assert "nothing to render" not in log


def test_pending_card_names_the_promoted_state() -> None:
    # source.mkv + a partial translation.jsonl is a full run parked at (or killed in) the
    # translate seam — route B step 1 parks the WHOLE batch like this. The page closes that
    # promoted-video-invisible gap with an honest state, and still fabricates no dub chip.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = _transcribed(root, "vidPARKED00", n=1, mkv=True)
        (wd / "translation.jsonl").write_text('{"id": 0}\n', encoding="utf-8")
        q = _queue(root, ["vidPARKED00"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "скачано полностью, перевод ещё не начат" in page
    assert "в работе" in log                            # and the operator is told
    assert "слушать" not in page and "чисто" not in page


def test_transcript_card_duration_falls_back_to_sentence_ends() -> None:
    # No info.json sidecar → the duration comes from the last sentence `end` (431 s → 7:11),
    # the title falls back to the id, and nothing crashes.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001", info=False)
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "7:11" in page                               # 431 s of sentences, not the sidecar
    assert "предложений: 431" in page
    assert "Transcribed Talk" not in page               # no sidecar → no title, and no crash


def test_transcript_card_without_any_duration_shows_a_dash_not_none() -> None:
    # Neither a sidecar nor a numeric sentence `end`: the duration is unknown, and the page's
    # convention for unknown is '—' — never a fabricated figure and never the literal "None".
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001", info=False, ends=False)
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    card = _card_of(page, 1)
    assert "предложений: 431" in card                   # the card still renders
    assert "None" not in card
    assert not re.search(r"\d+:\d\d", card)             # no fabricated clock anywhere on it
    assert "—" in card                                  # the unknown-duration dash instead


def test_transcript_card_takes_duration_from_info_json() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _transcribed(root, "vid00000001")               # info=True → duration 2530.0
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        card = _card_of(out.read_text(encoding="utf-8"), 1)
    assert "42:10" in card                              # 2530 s from info.json, clock-formatted


def test_torn_rollup_renders_the_state_not_a_fabricated_row() -> None:
    # report.json on disk but unreadable: run.json cannot build, and the card must say so
    # rather than rendering a healthy-looking row of zeros. The tally and the stdout unfinished
    # list both key on the same state.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = root / "vid00000001"
        (wd / "segments").mkdir(parents=True)
        (wd / "report.json").write_text("{not json", encoding="utf-8")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert "без свода: 1" in page                          # the page tally counts it
    assert "без свода" in log                              # stdout unfinished list names it
    card = _card_of(page, 1)
    assert '<span class="chip v-none">без свода</span>' in card


def test_card_rollup_shows_actionable_never_flagged() -> None:
    # The original two-numbers-one-batch bug, pinned forever: the retired page printed
    # completeness.n_flagged where the digest printed n_actionable (+n_advisory). The card
    # must show the split — never the pooled count.
    run_json = {
        "video_id": "vid00000001", "title": "T", "needs_triage": True,
        "timings": {"total_wall_s": 60.0, "rtf": 0.2, "video_sec": 300.0,
                    "video_sec_source": "info_json"},
        "asr": {"floor_ratio": 0.01},
        "translate": {"n_failed": 0, "n_sentences": 10},
        "verify": {"n_flagged": 0},
        "completeness": {"n_flagged": 8, "n_actionable": 3, "n_advisory": 5},
        "speed": {"median": 1.0, "p95": 1.1, "max": 1.2, "n_over_1_8": 0},
        "source": {"scanned": True, "n_flagged": 0},
    }
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = root / "vid00000001"
        (wd / "segments").mkdir(parents=True)
        (wd / "report.json").write_text(json.dumps({"segments": []}), encoding="utf-8")
        (wd / "run.json").write_text(json.dumps(run_json), encoding="utf-8")
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        card = _card_of(out.read_text(encoding="utf-8"), 1)
    assert "completeness 3 (+5 advisory)" in card
    assert "completeness 8" not in card


# --- audio: embed vs --link -------------------------------------------------------

def test_audio_is_embedded_by_default() -> None:
    # Embedded = the page is portable and publishable; only FLAGGED units pay the base64 cost.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", wav=(0,))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert page.count("data:audio/wav;base64,") == 1    # the one flagged unit, nothing else


def test_link_mode_references_audio_by_relative_path() -> None:
    # --link keeps the page tiny but chains it to work/: the src must be a forward-slash
    # relative path that resolves from the page's own directory under file://.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", wav=(0,))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        code, log = _report(["--queue", str(q), "--config", str(_cfg(root)),
                             "--out", str(out), "--link"])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert 'src="vid00000001/segments/00000.wav"' in page
    assert "data:audio/wav" not in page
    assert "linked audio" in log                        # the mode is named on stdout too


def test_link_mode_survives_an_out_dir_on_another_drive() -> None:
    # os.path.relpath raises ValueError across Windows mounts, and --out on another drive is
    # exactly that. The fallback is the absolute path: --link only ever promised a player that
    # works on this machine, and one unrelativizable href must not kill the whole page (this
    # crashed on the first real cross-drive --out, inherited from the retired triage page).
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "00000.wav"
        wav.write_bytes(b"RIFF")                        # existence is all the link arm checks
        other = "Z:\\elsewhere" if wav.drive.upper() != "Z:" else "Y:\\elsewhere"
        src = dub_blocks._audio_src(wav, Path(other), embed=False)
        assert src == str(wav).replace(os.sep, "/")     # absolute in, absolute out, no raise
        # The workdir usually arrives as a RELATIVE argv path (work\<id>) — the fallback must
        # STILL come out absolute, or the href resolves against the page's own (wrong) drive.
        old = os.getcwd()
        os.chdir(d)
        try:
            rel_src = dub_blocks._audio_src(Path("00000.wav"), Path(other), embed=False)
        finally:
            os.chdir(old)
    assert rel_src == str(wav).replace(os.sep, "/")     # relative in, absolute out


def test_flagged_unit_embeds_a_playable_source_in_both_modes() -> None:
    # A flagged unit's raw segment wav is playable from the card — a base64 data URI by
    # default, a relative path under --link with no base64. A real (tiny) WAV, so the payload is
    # a decodable file rather than arbitrary bytes.
    import wave
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        wd = _dubbed(root, "vid00000001", wav=())          # flagged unit 0; write its wav below
        with wave.open(str(wd / "segments" / "00000.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 160)               # 10 ms of silence
        q = _queue(root, ["vid00000001"])
        cfgp = _cfg(root)
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(cfgp), "--out", str(out)])
        embedded = out.read_text(encoding="utf-8")
        out2 = root / "r2.html"
        _report(["--queue", str(q), "--config", str(cfgp), "--out", str(out2), "--link"])
        linked = out2.read_text(encoding="utf-8")
    assert "data:audio/wav;base64," in embedded
    assert 'src="vid00000001/segments/00000.wav"' in linked
    assert "data:audio/wav" not in linked


def test_missing_wav_names_the_gap_not_a_dead_player() -> None:
    # A flagged unit whose wav is gone gets a note, never a broken <audio> element.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")                    # flagged unit, no wav on disk
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert "нет аудио (wav отсутствует)" in page
    assert "<audio" not in page


def test_limit_caps_flagged_units_per_video() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001", verify_flags=("low_similarity", "low_similarity"))
        q = _queue(root, ["vid00000001"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out),
                 "--limit", "1"])
        page = out.read_text(encoding="utf-8")
    assert page.count('class="unit"') == 1


def test_triage_nav_links_flagged_videos_and_is_absent_when_clean() -> None:
    # The morning-listen job is a nav block of anchors: the worst videos are one click away and
    # the queue keeps its order. A clean batch gets none.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vidFLAGGED0")
        _dubbed(root, "vidCLEAN000", verify_flags=(None, None))
        q = _queue(root, ["vidFLAGGED0", "vidCLEAN000"])
        out = root / "r.html"
        _report(["--queue", str(q), "--config", str(_cfg(root)), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
        nav = page.split('<div class="nav">', 1)[1].split("</div>", 1)[0]
        assert "Требуют прослушивания:" in nav
        assert 'href="#v1"' in nav and "Dub Talk" in nav
        assert 'href="#v2"' not in nav                  # the clean video earns no anchor
        # and a fully clean batch renders no nav at all
        q2 = _queue(root, ["vidCLEAN000"])
        out2 = root / "r2.html"
        _report(["--queue", str(q2), "--config", str(_cfg(root)), "--out", str(out2)])
        page2 = out2.read_text(encoding="utf-8")
    assert "Требуют прослушивания" not in page2


# --- cross-surface divergence (the acceptance test for the queue-page merge) -------

def test_the_two_surfaces_print_identical_batch_cells() -> None:
    # ONE dub workdir, BOTH renderers: every data cell of the batch row must be an IDENTICAL
    # string, and both headers must come from queueview.BATCH_COLUMNS. This is the whole point
    # of the merge — the digest and the page can no longer disagree about the same bytes.
    # The count is derived from BATCH_COLUMNS rather than hardcoded (was 10, 11 since the `flags`
    # column): a literal here means adding a column fails in a test about SAMENESS, which says
    # nothing about the column and trains the reader to bump the number.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _dubbed(root, "vid00000001")
        q = _queue(root, ["vid00000001"])
        cfgp = _cfg(root)
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert run_report.main(["--queue", str(q), "--config", str(cfgp)]) == 0
        digest = buf.getvalue()
        out = root / "r.html"
        code, _ = _report(["--queue", str(q), "--config", str(cfgp), "--out", str(out)])
        page = out.read_text(encoding="utf-8")
    assert code == 0
    assert " | ".join(lbl for _k, lbl in queueview.BATCH_COLUMNS) in digest
    for _k, lbl in queueview.BATCH_COLUMNS:
        assert f"<th>{html.escape(lbl)}</th>" in page
    row_line = next(ln for ln in digest.splitlines() if ln.startswith("vid00000001 | "))
    digest_cells = row_line.split(" | ")[2:-1]          # video, title | DATA CELLS | triage
    page_cells = _dub_row_cells(page, 1)
    n_data = len(queueview.BATCH_COLUMNS) - 3           # minus video, title, triage
    assert len(digest_cells) == len(page_cells) == n_data
    assert digest_cells == page_cells


def test_recording_a_stage_wall_clock_does_not_eat_the_per_video_detail() -> None:
    # record_stage_timing used to write {"stages": ...} back over the whole file, which was
    # invisible while `stages` was the only section and silently destroys `detail` now that a
    # second one exists. The transcribe stage writes both, in that order.
    from overdub import timings

    with tempfile.TemporaryDirectory() as d:
        w = WorkDir(Path(d))
        w.root.mkdir(parents=True, exist_ok=True)
        timings.record_stage_detail(w, "transcribe", work_sec=61.2, asr_passes=1)
        timings.record_stage_timing(w, "transcribe", 88.1)
        doc = json.loads((w.root / "timings.json").read_text(encoding="utf-8"))
    assert doc["stages"]["transcribe"] == 88.1
    assert doc["detail"]["transcribe"] == {"work_sec": 61.2, "asr_passes": 1}


if __name__ == "__main__":
    mod = sys.modules[__name__]
    tests = [(n, getattr(mod, n)) for n in dir(mod) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"all queue-report tests passed ({len(tests)})")
