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
GPU queue of its own.

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
import time
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub.config import Config                        # noqa: E402
from overdub.pipeline import STOP_NAME                   # noqa: E402
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


def drain_one(url: str, work: WorkDir) -> tuple[bool, str]:
    """Build this video's translation, then run its pipeline to MKV. (ok, detail)."""
    py = sys.executable
    code, out = _run([py, "-X", "utf8", str(_ROOT / "scripts" / "build_translation.py"),
                      str(work.root)])
    if code != 0:
        tail = out.strip().splitlines()[-1:] or ["(no output)"]
        return False, f"build failed: {tail[0]}"
    code, out = _run([py, "-X", "utf8", "-m", "overdub", url])
    if code != 0:
        tail = out.strip().splitlines()[-1:] or ["(no output)"]
        return False, f"pipeline exit {code}: {tail[0]}"
    return True, "drained"


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

    print(f"[drain] watching {len(urls)} video(s), poll {args.poll:.0f}s, "
          f"timeout {args.timeout:.0f}s")
    deadline = time.monotonic() + args.timeout
    while len(done) + len(failed) < len(urls):
        if (cfg.work_root / STOP_NAME).exists():
            # Observed, NOT consumed: the sweep's own checkpoint is what reports a halt per video.
            print("[drain] STOP present — leaving it for the pipeline and stopping here")
            break
        progressed = False
        for u in urls:
            if u in done or u in failed:
                continue
            w = works[u]
            if not (already_built(w) or draft_ready(w)):
                continue
            vid = video_id(u)
            print(f"[drain] {vid} ready — building and running its tail")
            ok, detail = drain_one(u, w)
            (done if ok else failed)[u] = detail
            print(f"[{'ok  ' if ok else 'FAIL'}] {vid}  {detail}")
            progressed = True
        if len(done) + len(failed) >= len(urls):
            break
        if time.monotonic() > deadline:
            print("[drain] timeout — the rest are left for the ordinary resume")
            break
        if not progressed:
            time.sleep(args.poll)

    pending = [u for u in urls if u not in done and u not in failed]
    print(f"\n[drain] {len(done)} drained, {len(failed)} failed, {len(pending)} pending")
    for u in pending:
        print(f"[    ] {video_id(u)}  no usable draft — the step-3 resume still owes it")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
