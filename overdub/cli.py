"""CLI entry point:  overdub <url> | --batch FILE  [--config overdub.toml] [--force] [--only STAGE ...]"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

from . import runreport
from .config import Config
from .pipeline import Context, STOP_NAME, Session, StopRequested, check_stop, run_pipeline
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
    p.add_argument("--video-major", action="store_true",
                   help="batch only: run each video through every stage before the next "
                        "(pre-2026-07-19 order; escape hatch if stage-major misbehaves)")
    args = p.parse_args(argv)
    if (args.url is None) == (args.batch is None):
        p.error("give exactly one of: URL or --batch FILE")
    if args.video_major and args.batch is None:
        p.error("--video-major applies to --batch only (a single video has nothing to amortise)")

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
    if only:
        # stage-major turns a typo into 8 sweeps of no-ops and then reports "12 ok" — a
        # silent failure this change amplifies, so the name is validated up front instead
        known = {st.name for st in all_stages(cfg)}
        bad = only - known
        if bad:
            p.error(f"unknown stage(s): {', '.join(sorted(bad))}; "
                    f"known: {', '.join(sorted(known))}")
    if urls is not None:
        run = _run_batch_video_major if args.video_major else _run_batch_stage_major
        sys.exit(run(urls, cfg, force=args.force, only=only))
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
    _rollup_and_print(work, cfg)
    return _export_output(ctx)


def _rollup_and_print(work: WorkDir, cfg: Config) -> None:
    """Refresh the per-run rollup and print the one-line digest (best-effort — never
    raises; build_run_report returns None on an --only download run that has no
    report/translation yet). Shared by _run_one and the stage-major finish sweep so the
    two batch orders cannot print different things."""
    run = runreport.build_run_report(work, cfg)
    if run:
        t = run["timings"]
        rtf = t["rtf"] if t["rtf"] is not None else "n/a"
        print(f"[report] RTF {rtf} ({t['video_sec_source']}) · flags {run['flags_total']}"
              f" · triage {'yes' if run['needs_triage'] else 'no'}")


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


def _run_batch_video_major(urls: list[str], cfg: Config, *, force: bool,
                           only: set[str] | None) -> int:
    """Videos outer, stages inner — the pre-2026-07-19 order, kept behind --video-major.

    Every video reloads every model (~72 s of pure model loading per video), which is why
    it is no longer the default; it stays reachable as the escape hatch that shares
    run_pipeline, _export_output and _summarize with the stage-major driver, so a bug in
    the stage contract shows up in BOTH orders and only an ordering bug shows up in one.
    """
    results: list[tuple[str, str, str]] = []        # (vid, status, detail)
    halted: str | None = None
    not_run: list[str] = []
    for i, url in enumerate(urls, 1):
        vid = video_id(url)
        # no pre-video checkpoint: run_pipeline's "before stage 'download'" check fires
        # first thing for every video and already covers the mux→next-download gap. True
        # for THIS order only — stage-major has no mux→download gap to cover.
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
    return _summarize(results, not_run, halted, cfg, order="video-major")


@dataclass
class _Job:
    """One video's slot in a stage-major batch. `status` is the cross-stage gate: only
    "run" jobs enter the next stage, so a failure at synthesize drops that video out of
    verify/assemble/mux without touching the others — the isolation that
    _run_batch_video_major's per-video try/except gives for free."""
    url: str
    vid: str
    ctx: Context
    status: str = "run"          # run | ok   | FAIL | stop  (4-char tags: summary alignment)
    detail: str = ""
    n_done: int = 0              # (stage, video) pairs of THIS run that returned cleanly. Only
                                 # used to tell "already through every stage" from "genuinely
                                 # not reached" when a STOP lands mid-sweep — a stop cannot
                                 # un-finish a video that is already done.


def _run_batch_stage_major(urls: list[str], cfg: Config, *, force: bool,
                           only: set[str] | None, stages=None, finalize=None) -> int:
    """Stages outer, videos inner — the default. Each model loads ONCE PER BATCH instead
    of once per video, because a model's lifetime is one stage sweep (pipeline.Session).

    `stages`/`finalize` are injectable so the traversal order, the status machine and the
    finish sweep are testable without a GPU, ffmpeg or yt-dlp.
    """
    stages = all_stages(cfg) if stages is None else stages
    finalize = _export_output if finalize is None else finalize
    session = Session()                              # one cache for the whole batch; cleared
                                                     # after EVERY stage sweep (see below)
    jobs = [_Job(url=u, vid=video_id(u),
                 ctx=Context(url=u, cfg=cfg, work=WorkDir.for_url(u, cfg.work_root),
                             session=session))
            for u in urls]
    for j in jobs:
        print(f"overdub: {j.url}")
        print(f"work dir: {j.ctx.work.root}")
    halted: str | None = None

    for st in stages:
        try:
            for i, j in enumerate(jobs, 1):
                if j.status != "run":                # excluded by an earlier stage — a
                    continue                         # dropped video is never revisited
                # header only for stages that can actually run — run_pipeline still gets
                # EVERY pair below, so the STOP checkpoint grid stays identical to
                # video-major's; this just keeps an --only run from logging 8 sweeps of
                # headers with nothing under them
                if only is None or st.name in only:
                    print(f"\n--- {st.name}  [{i}/{len(jobs)}] {j.vid}")
                failed = stopped = None
                try:
                    # ONE stage at a time: check_stop, the only/done filters and
                    # record_stage_timing all stay inside run_pipeline, so the
                    # per-(stage, video) checkpoint granularity and the STOP message text
                    # come for free and cannot drift between the two orders.
                    run_pipeline(j.ctx, [st], force=force, only=only, owns_session=False)
                except StopRequested as e:           # MUST precede `except Exception`
                    stopped = str(e)
                except Exception as e:               # KeyboardInterrupt passes through
                    traceback.print_exc()
                    failed = f"{st.name}: {type(e).__name__}: {e}"
                # handled OUTSIDE the handlers: while one is active the traceback pins
                # st.run's frame and every model local to it, so a session.clear() in there
                # would free nothing
                if failed is None and stopped is None:
                    j.n_done += 1
                if failed is not None:
                    j.status, j.detail = "FAIL", failed
                    session.clear()                  # a stage that raised may have left a
                                                     # poisoned engine — never reuse it
                if stopped is not None:
                    # check_stop CONSUMED the STOP file, so exactly ONE (stage, video) pair
                    # can ever observe it. Continuing to the next video would leave the rest
                    # of the batch running against an already-deleted STOP — the stop
                    # silently un-honored for 11 of 12 videos. Break BOTH loops.
                    j.status, j.detail = "stop", stopped
                    halted = f"{stopped}, video {j.vid}"
                    for k in jobs:
                        if k.status != "run":
                            continue
                        if k.n_done == len(stages):
                            # already through EVERY stage in this run — a stop arriving while a
                            # LATER video is still in the last sweep cannot un-finish it. Leaving
                            # it "run" keeps its export in the finish sweep; marking it "stop"
                            # would report six finished videos as "not reached" and ship none of
                            # them, which is a false diagnosis, not just a cosmetic one.
                            continue
                        k.status = "stop"
                        k.detail = (f"stopped after '{stages[k.n_done - 1].name}'" if k.n_done
                                    else f"not reached (stopped at '{st.name}')")
                    break
        finally:
            session.clear()                          # a model's lifetime is ONE stage sweep
        if halted:
            break

    # --- finish sweep: runs after a normal end AND after a stop (CPU-only; STOP is already
    # consumed and cannot re-fire). NOT hooked to the mux stage: `--only download transcribe`
    # filters mux out entirely, and that route still owes every video its run.json.
    for j in jobs:
        _rollup_and_print(j.ctx.work, cfg)           # EVERY job, failed ones included: a
        if j.status != "run":                        # skipped rollup leaves the batch sweep
            continue                                 # reading YESTERDAY's run.json
        try:
            j.detail = finalize(j.ctx) or "(no output.mkv)"
            j.status = "ok  "
        except Exception as e:                       # video-major catches an _export_output
            traceback.print_exc()                    # raise in its own except Exception —
            j.status, j.detail = "FAIL", f"export: {type(e).__name__}: {e}"

    return _summarize([(j.vid, j.status, j.detail) for j in jobs], [], halted, cfg,
                      order="stage-major")


def _summarize(results: list[tuple[str, str, str]], not_run: list[str], halted: str | None,
               cfg: Config, *, order: str) -> int:
    """Batch summary + run.json sweep + exit code. Shared by both orders."""
    print("\n── batch summary " + "─" * 30)
    for vid, status, detail in results:
        print(f"[{status}] {vid}  {detail}")
    for url in not_run:
        print(f"[    ] {video_id(url)}  not run")
    fails = sum(1 for _, s, _ in results if s == "FAIL")
    oks = sum(1 for _, s, _ in results if s == "ok  ")
    # "unfinished", not "not run": under stage-major a video that never finished was still
    # partly processed — it is "stopped at stage N", not "untouched"
    print(f"{oks} ok, {fails} failed, {len(results) - oks - fails + len(not_run)} unfinished")
    if halted:
        print(f"[stop] STOP file honored — halted {halted}; re-run the same command to resume")
    if fails:
        print("re-run the same command to retry failed videos (completed stages fast-skip)")

    # batch sweep: roll up each video's run.json (the driver wrote it). A missing/None
    # run.json (a video that failed before the rollup, or an --only download batch) is
    # skipped, never a crash — the summary above is the authoritative status; this is
    # triage sugar on top. The order is stamped because per-video RTF is NOT comparable
    # across orders: under stage-major each model's load time lands on whichever video went
    # first in that stage.
    runs = []
    for vid, _status, _detail in results:
        r = _load_run_json(cfg.work_root / vid / "run.json")
        if r is not None:
            runs.append(r)
    if runs:
        total_wall = round(sum((r.get("timings", {}) or {}).get("total_wall_s", 0) or 0
                               for r in runs), 1)
        sum_video = sum(((r.get("timings", {}) or {}).get("video_sec") or 0) for r in runs)
        triage = [r.get("video_id") for r in runs if r.get("needs_triage")]
        print(f"\n── batch sweep ({order}) " + "─" * 20)
        thru = f"×{sum_video / total_wall:.2f}" if total_wall > 0 else "n/a"
        print(f"{len(runs)} run(s) · total wall {total_wall}s · throughput {thru}")
        print(f"needs triage ({len(triage)}): {', '.join(triage) if triage else 'none'}")
    return 1 if fails else (3 if halted else 0)


def _load_run_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


if __name__ == "__main__":
    main()
