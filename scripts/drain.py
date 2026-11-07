"""Drain a route-B queue video by video WHILE the Sonnet wave is still running.

THE PROBLEM. The wave is a full barrier today: the orchestrator fans out every translator at
once, waits for all of them, builds every translation.json, and only then resumes the pipeline.
So the whole post-translate tail — synthesize, assemble, separate, mux — starts after the LAST
agent finishes, even though the FIRST video's translation was ready minutes earlier. Measured on
the 2026-08-06 baseline: a 787.9 s wave followed by a 1145.6 s tail, with the machine idle for
most of the wave.

WHAT THIS DOES. Watches for each video's `translation.draft.json` to appear, and the moment one
does, builds that video's translation.json and runs its pipeline to MKV — while the other agents
are still writing. Videos are drained ONE AT A TIME on purpose: the tail contains `separate`
(htdemucs, the one GPU stage left in it), and serializing here is what keeps this from needing a
GPU queue of its own. The exception is mux, the last stage: it uses no GPU, so each video's mux
is started in the background (config `mux_concurrency` at once, bounded by RAM) and the next
video's tail starts beside it.

WHY A WATCHER AND NOT A PIPELINE CHANGE. Nothing in the pipeline can do this. The drafts are
written by sub-agents the orchestrator dispatches, so the only thing that knows a video is ready
is the filesystem. And nothing NEW is needed downstream: `TranslateStage.done()` is
"translation.json exists", so a plain per-video `-m overdub <url>` fast-skips download, transcribe
and translate and runs exactly the tail. This script is therefore a scheduler and not a stage — it
owns no artifact, enforces no contract, and every file it produces is produced by the same code
the ordinary resume would have run.

WHAT IT DELIBERATELY DOES NOT DO. It never decides that a video is finished with, never writes a
completion artifact, and never shortens the queue (queue-contract §3). A video whose agent failed
simply never gets a usable draft, is reported as `pending` at the deadline, and is left for the
ordinary step-3 resume — which is also what happens to a video on the CHUNKED path, whose draft is
derived rather than written by one agent (§5) and whose build the orchestrator still owns.

Run it in the background right after the Workflow call, from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\drain.py --queue queue.txt

It REPLACES the separate sweep and the per-video build loop in the route-B runbook: draining a
video runs both, in the right order, so the two cannot race on that video's timings.json.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub import host                                 # noqa: E402
from overdub.config import Config                        # noqa: E402
from overdub.pipeline import STOP_NAME                   # noqa: E402
from overdub.stages import all_stages                    # noqa: E402
from overdub.stages import mux as mux_stage             # noqa: E402
from overdub.stages import separate as separate_stage   # noqa: E402
from overdub.workdir import WorkDir, video_id            # noqa: E402

_POLL_S = 5.0
_ROOT = Path(__file__).resolve().parent.parent


def queue_urls(path: Path) -> list[str]:
    """The queue's URLs, comments and blanks dropped — the same shape every route reads."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def draft_ready(work: WorkDir) -> bool:
    """Is the draft on disk, parseable, AND covering every sentence in the transcript?

    COVERAGE, not parseability, is the readiness test, and the difference is not academic — it
    cost two videos on the first real run (2026-08-07). A sub-agent builds the draft in batches
    and REWRITES the whole file each time, so every intermediate state is perfectly valid JSON
    holding a prefix of the records. A parse-only check waves those through, the build then exits
    on the missing ids, and the video is reported failed while its agent was still working.

    Reading it as "not yet" costs one more poll. Reading it as ready costs the video: nothing
    re-queues it, because from the drain's side a build failure is a real failure.

    A draft that never completes (the INCOMPLETE case the route-B skill documents) simply stays
    unready until the deadline and is reported `pending`, which is the honest answer — the step-3
    resume still owes it.
    """
    try:
        draft = json.loads((work.root / "translation.draft.json").read_text(encoding="utf-8"))
        sents = json.loads(work.sentences.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(draft, list) or not isinstance(sents, list) or not sents:
        return False
    want = {s.get("id") for s in sents if isinstance(s, dict)}
    got = {r.get("id") for r in draft if isinstance(r, dict)}
    return want <= got


def already_built(work: WorkDir) -> bool:
    """translation.json exists and is not older than the transcript it must describe."""
    t = work.translation
    if not t.exists():
        return False
    if not work.sentences.exists():
        return True
    return t.stat().st_mtime >= work.sentences.stat().st_mtime


def _run(argv: list[str]) -> tuple[int, str]:
    """Run a child from the repo root, capturing everything. Never raises."""
    try:
        r = subprocess.run(argv, cwd=str(_ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:                                # noqa: BLE001 — a scheduler never dies
        return 1, f"{type(e).__name__}: {e}"


def _last_line(out: str) -> str:
    return (out.strip().splitlines()[-1:] or ["(no output)"])[0]


def drain_one(url: str, work: WorkDir, tail_stages: list[str]) -> tuple[bool, str]:
    """Build this video's translation, then run its pipeline up to (not including) mux.

    mux is split off because it is the one tail stage that needs nothing the NEXT video wants: no
    GPU, no model, only cores and RAM. Run inline it held the next video's synthesize and separate
    back for its whole encode; started in the background (MuxPool) it overlaps them."""
    py = sys.executable
    code, out = _run([py, "-X", "utf8", str(_ROOT / "scripts" / "build_translation.py"),
                      str(work.root)])
    if code != 0:
        return False, f"build failed: {_last_line(out)}"
    code, out = _run([py, "-X", "utf8", "-m", "overdub", url, "--only", *tail_stages])
    if code != 0:
        return False, f"pipeline exit {code}: {_last_line(out)}"
    return True, "tail done"


class MuxPool:
    """Background `-m overdub <url> --only mux` children, at most `width` at once, admitted by
    `admits` — host.ram_admission's rule, the one the stage-major mux sweep uses too."""

    def __init__(self, width: int, admits):
        self.width, self.admits = max(1, width), admits
        self.running: dict[str, tuple[subprocess.Popen, object, int]] = {}

    def fits(self, need: int) -> bool:
        """May one more mux needing `need` bytes start now?"""
        if not self.running:
            return True
        if len(self.running) >= self.width:
            return False
        return self.fits_beside(need)

    def fits_beside(self, need: int) -> bool:
        """Do `need` bytes of other work fit beside the running muxes? Always true with none."""
        return self.admits([n for _p, _f, n in self.running.values()], need)

    def start(self, url: str, need: int) -> None:
        log = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
        # unbuffered, so the child's stdout and stderr land in the log in the order they were
        # written and the last line of a failure is its exception, not a flushed progress line
        proc = subprocess.Popen([sys.executable, "-X", "utf8", "-u", "-m", "overdub", url,
                                 "--only", "mux"],
                                cwd=str(_ROOT), stdout=log, stderr=subprocess.STDOUT)
        self.running[url] = (proc, log, need)

    def reap(self, block: bool = False) -> list[tuple[str, bool, str]]:
        """(url, ok, detail) for every child that has exited; with block, waits for at least one."""
        while True:
            out = []
            for url, (proc, log, _n) in list(self.running.items()):
                if proc.poll() is None:
                    continue
                del self.running[url]
                log.seek(0)
                text = log.read()
                log.close()
                out.append((url, proc.returncode == 0,
                            "drained" if proc.returncode == 0
                            else f"mux exit {proc.returncode}: {_last_line(text)}"))
            if out or not block or not self.running:
                return out
            time.sleep(1.0)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="drain", description=__doc__.split("\n", 1)[0])
    p.add_argument("--queue", type=Path, required=True)
    p.add_argument("--config", type=Path, default=Path("overdub.toml"))
    p.add_argument("--timeout", type=float, default=3600.0,
                   help="give up waiting for the remaining drafts after this many seconds")
    p.add_argument("--poll", type=float, default=_POLL_S)
    args = p.parse_args(argv)

    # Line-buffer stdout. This runs in the BACKGROUND beside a wave, so its output is always
    # redirected, and Python block-buffers a redirected stream: on the first real run the log
    # stayed empty for 20 minutes while the drain was working normally. For a scheduler nobody
    # watches interactively, the log is the only evidence it is alive.
    with contextlib.suppress(Exception):                  # not worth failing a run over
        sys.stdout.reconfigure(line_buffering=True)

    cfg = Config.load(args.config) if args.config.exists() else Config()
    urls = queue_urls(args.queue)
    if not urls:
        print("[FAIL] queue is empty", file=sys.stderr)
        return 2
    works = {u: WorkDir.for_url(u, cfg.work_root) for u in urls}
    done: dict[str, str] = {}
    failed: dict[str, str] = {}
    tail_stages = [st.name for st in all_stages(cfg) if st.name != "mux"]
    muxes = MuxPool(int(getattr(cfg, "mux_concurrency", 1) or 1), host.ram_admission())

    def settle_muxes(block: bool = False) -> None:
        for u, ok, detail in muxes.reap(block):
            (done if ok else failed)[u] = detail
            print(f"[{'ok  ' if ok else 'FAIL'}] {video_id(u)}  {detail}")

    print(f"[drain] watching {len(urls)} video(s), poll {args.poll:.0f}s, "
          f"timeout {args.timeout:.0f}s, up to {muxes.width} mux(es) in the background")
    deadline = time.monotonic() + args.timeout
    while len(done) + len(failed) < len(urls):
        settle_muxes()
        if (cfg.work_root / STOP_NAME).exists():
            # Observed, NOT consumed: the sweep's own checkpoint is what reports a halt per video.
            print("[drain] STOP present — leaving it for the pipeline and stopping here")
            break
        progressed = False
        for u in urls:
            if u in done or u in failed or u in muxes.running:
                continue
            w = works[u]
            if not (already_built(w) or draft_ready(w)):
                continue
            vid = video_id(u)
            # the tail runs BESIDE the background muxes, and its separate is the biggest single
            # allocation in the pipeline: a long previous mux plus this separate can exceed RAM,
            # which on Windows pages instead of failing — a slow night with no error in it
            tail_need = separate_stage.ram_need(w, cfg)
            while not muxes.fits_beside(tail_need):
                settle_muxes(block=True)
            print(f"[drain] {vid} ready — building and running its tail")
            ok, detail = drain_one(u, w, tail_stages)
            if not ok:
                failed[u] = detail
                print(f"[FAIL] {vid}  {detail}")
            else:
                need = mux_stage.ram_need(w)
                while not muxes.fits(need):
                    settle_muxes(block=True)
                muxes.start(u, need)
                print(f"[drain] {vid} tail done — mux started in the background "
                      f"({len(muxes.running)} running)")
            progressed = True
        if len(done) + len(failed) + len(muxes.running) >= len(urls):
            if not muxes.running:
                break
            settle_muxes(block=True)
            continue
        if time.monotonic() > deadline:
            print("[drain] timeout — the rest are left for the ordinary resume")
            break
        if not progressed:
            time.sleep(args.poll)

    while muxes.running:                                  # a mux already started is finished, never
        settle_muxes(block=True)                          # abandoned: its tail is paid for
    pending = [u for u in urls if u not in done and u not in failed]
    print(f"\n[drain] {len(done)} drained, {len(failed)} failed, {len(pending)} pending")
    for u in pending:
        print(f"[    ] {video_id(u)}  no usable draft — the step-3 resume still owes it")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
