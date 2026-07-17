"""CLI entry point:  overdub <url> | --batch FILE  [--config overdub.toml] [--force] [--only STAGE ...]"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

from .config import Config
from .pipeline import Context, STOP_NAME, StopRequested, check_stop, run_pipeline
from .stages import all_stages
from .workdir import WorkDir, replace_retry, safe_filename, video_id


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="overdub", description="Local YouTube→Russian dubbing")
    p.add_argument("url", nargs="?", help="YouTube video URL")
    p.add_argument("--batch", type=Path, metavar="FILE",
                   help="queue file: one URL per line, '#' comments and blank lines skipped")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"), help="TOML config path")
    p.add_argument("--force", action="store_true", help="re-run stages even if artifacts exist")
    p.add_argument("--only", nargs="+", metavar="STAGE", help="run only these stages")
    args = p.parse_args(argv)
    if (args.url is None) == (args.batch is None):
        p.error("give exactly one of: URL or --batch FILE")

    urls: list[str] | None = None
    if args.batch is not None:                      # usage errors before any side effects
        if not args.batch.is_file():
            p.error(f"queue file not found: {args.batch}")
        try:
            urls = _read_queue(args.batch)
        except UnicodeDecodeError:
            p.error(f"queue file is not UTF-8: {args.batch}")
        if not urls:
            p.error(f"queue file has no URLs: {args.batch}")

    cfg = Config.load(args.config)
    try:                                            # a stale STOP must never no-op this run
        check_stop(cfg.work_root, "startup")
    except StopRequested:
        stop = cfg.work_root / STOP_NAME
        if stop.exists():                           # unlink failed (AV hold / open handle) —
            # starting anyway would just re-halt at the first stage boundary
            sys.exit(f"[FAIL] stale {stop} could not be removed — remove it manually, re-run")
        print("[stop] stale STOP file removed — starting normally")

    only = set(args.only) if args.only else None
    if urls is not None:
        sys.exit(_run_batch(urls, cfg, force=args.force, only=only))
    try:
        _run_one(args.url, cfg, force=args.force, only=only)
    except StopRequested as e:
        print(f"[stop] STOP file honored — halted {e}; re-run the same command to resume")
        sys.exit(3)


def _run_one(url: str, cfg: Config, *, force: bool, only: set[str] | None) -> str | None:
    work = WorkDir.for_url(url, cfg.work_root)
    ctx = Context(url=url, cfg=cfg, work=work)
    print(f"overdub: {url}")
    print(f"work dir: {work.root}")
    run_pipeline(ctx, all_stages(cfg), force=force, only=only)
    return _export_output(ctx)


def _read_queue(path: Path) -> list[str]:
    """One URL per line; blank lines and full-line '#' comments skipped (no inline
    '#' stripping — '#' is legal in URLs). utf-8-sig strips a Notepad/PowerShell BOM
    that would otherwise glue to line 1. Dedupe by video_id: two spellings of one
    video share a workdir — running both would double-count and double-export."""
    urls: list[str] = []
    seen: dict[str, int] = {}
    for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        vid = video_id(line)
        if vid in seen:
            print(f"[dup ] {vid}  line {n} skipped (same video as line {seen[vid]})")
            continue
        seen[vid] = n
        urls.append(line)
    return urls


def _title_of(ctx: Context) -> str | None:
    """Title from persisted source.info.json; pre-change workdirs get one metadata-only
    yt-dlp call, persisted on success (self-heals: offline resumes stay offline-safe).
    None → caller names by video id. Never triggers a download."""
    # yt-dlp derives the sidecar name from the actual ext: source.info.json on the mkv
    # merge path, source.mkv.info.json on the single-format '/b' fallback — probe both
    for ij in (ctx.work.info_json, ctx.work.root / "source.mkv.info.json"):
        try:
            title = json.loads(ij.read_text(encoding="utf-8")).get("title")
            if title:
                return title
        except (OSError, ValueError):               # missing or torn (ValueError also covers
            pass                                    # a truncated UTF-8 seq) → backfill attempt
    try:                                            # --print implies --simulate: no download.
        # PYTHONUTF8=1: yt-dlp encodes piped stdout in the locale codepage — Cyrillic titles
        # get dropped/mangled on stock (non-UTF-8-ACP) Windows without it
        r = subprocess.run(["yt-dlp", "--print", "title", ctx.url], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=30,
                           env={**os.environ, "PYTHONUTF8": "1"})
        title = r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        title = ""
    if title:
        # plain write: the read path treats a torn file as missing and re-backfills
        ctx.work.info_json.write_text(json.dumps({"title": title}, ensure_ascii=False),
                                      encoding="utf-8")
        return title
    print(f"[warn] title unavailable for {video_id(ctx.url)} (offline?) — naming by video id")
    return None


def _export_output(ctx: Context) -> str | None:
    """Hardlink (copy fallback) work/<id>/output.mkv → output_dir/"<title> [<id>].mkv".
    output.mkv never moves — mux done() and resume depend on it. Returns the export
    name for the batch summary, or None when output.mkv doesn't exist (--only run)."""
    src = ctx.work.output
    if not src.exists():
        print("[info] no output.mkv yet — export skipped")
        return None
    vid = video_id(ctx.url)
    stem = safe_filename(_title_of(ctx) or "")
    name = f"{stem} [{vid}].mkv" if stem else f"[{vid}].mkv"
    out_dir = ctx.cfg.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob(f"*[[]{vid}[]].mkv"):   # stale exports of THIS video (late title
        if old.name != name:                        # backfill / changed sanitization)
            old.unlink(missing_ok=True)
            print(f"[out ] removed stale export: {old.name}")
    dst = out_dir / name
    # hardlink shares the inode (equal mtimes → up to date); a re-mux flips output.mkv
    # via .tmp + os.replace = NEW inode with newer mtime, so the stale link reads older.
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return name
    tmp = out_dir / (name + ".tmp")
    tmp.unlink(missing_ok=True)                     # orphan from a prior crash
    # hardlink coupling: dst and output.mkv become one NTFS file — an export left open in
    # a player without FILE_SHARE_DELETE blocks a later re-mux's replace of output.mkv
    # (loud FAIL, batch continues; close the player and re-run)
    try:
        os.link(src, tmp)                           # free on the common same-volume case
    except OSError:
        shutil.copy2(src, tmp)                      # cross-volume / FS without hardlinks
    replace_retry(tmp, dst)                         # atomic: never a torn visible export
    print(f"[out ] → {dst}")
    return name


def _run_batch(urls: list[str], cfg: Config, *, force: bool, only: set[str] | None) -> int:
    results: list[tuple[str, str, str]] = []        # (vid, status, detail)
    halted: str | None = None
    not_run: list[str] = []
    for i, url in enumerate(urls, 1):
        vid = video_id(url)
        # no pre-video checkpoint: run_pipeline's "before stage 'download'" check fires
        # first thing for every video and already covers the mux→next-download gap
        print(f"\n=== [{i}/{len(urls)}] {vid}  {url}")
        try:
            name = _run_one(url, cfg, force=force, only=only)
            results.append((vid, "ok  ", name or "(no output.mkv)"))
        except StopRequested as e:                  # from run_pipeline, between stages —
            results.append((vid, "stop", str(e)))   # MUST precede `except Exception`
            halted = f"{e}, video {i}/{len(urls)} ({vid})"
            not_run = urls[i:]
            break
        except Exception as e:                      # KeyboardInterrupt passes through
            traceback.print_exc()
            results.append((vid, "FAIL", f"{type(e).__name__}: {e}"))

    print("\n── batch summary " + "─" * 30)
    for vid, status, detail in results:
        print(f"[{status}] {vid}  {detail}")
    for url in not_run:
        print(f"[    ] {video_id(url)}  not run")
    fails = sum(1 for _, s, _ in results if s == "FAIL")
    oks = sum(1 for _, s, _ in results if s == "ok  ")
    print(f"{oks} ok, {fails} failed, {len(results) - oks - fails + len(not_run)} not run")
    if halted:
        print(f"[stop] STOP file honored — halted {halted}; re-run the same command to resume")
    if fails:
        print("re-run the same command to retry failed videos (completed stages fast-skip)")
    return 1 if fails else (3 if halted else 0)


if __name__ == "__main__":
    main()
