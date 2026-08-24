"""Owner of work/<id>/timings.json — every read and every write of that file.

Split out of runreport.py on 2026-08-06, on the reader/writer line that module already draws for
itself: runreport AGGREGATES already-persisted artifacts into run.json and explicitly "never runs a
model, never touches the GPU". These functions are the other half — they are what the stages CALL
while running, and they are the only code allowed to write timings.json. Keeping one owner is the
point: `stages` and `detail` are upserted from six different call sites, and a second writer that
did not read-modify-write the whole document is exactly how `detail` got eaten the first time.

Pure stdlib, no package imports, so importing this from pipeline/stages/runreport can never create
a cycle — the same property runreport states about itself and the reason the JSON helpers below are
a private copy rather than an import (five modules in this repo carry that same six-line reader on
purpose; see build_scout._load_json).

Never raises. A timing is observability: losing one costs a number in a report, and it must never
cost a stage. Every public function here swallows its own failure into a [warn].
"""

from __future__ import annotations

import datetime
import json
import os
import sys


def now_iso() -> str:
    """UTC wall clock, ISO-8601 to the millisecond. String-sortable, and unambiguous across a DST
    step or a timezone change — a naive local stamp is neither, and a night's batch can straddle
    one."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def iso_from_epoch(ts) -> str:
    """A POSIX timestamp → the same string shape now_iso() produces.

    Exists so the ONE producer that cannot read its own clock — the translate seam, whose two ends
    are file mtimes because neither the sub-agent nor the workflow script may stamp a time — writes
    a field byte-comparable with every other span. Two formatters for one field is how a series
    becomes unsortable."""
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(
        timespec="milliseconds")


RUN_ID = f"{now_iso()}#{os.getpid()}"
"""Identity of THIS process, stamped into every span and run row it writes.

One id per process rather than a parameter threaded through the drivers, because a pipeline
invocation IS the unit: a single video and a 24-video batch are both one process, and both want
one window. It carries the pid because two runs can start in the same millisecond.

What it buys: a video whose stages all [skip] writes no span under the current id, so the run's
window is computed over the work that actually happened rather than over whatever timings the
workdir happens to hold from last week."""


# --- small pure helpers (private copy — see the module docstring) --------------
def _load_json(path):
    """Read+parse a JSON artifact, tolerating missing/torn files (returns None)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _atomic_write_json(path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_timings(work):
    """work/<id>/timings.json → (path, the WHOLE document), or (path, {}) when absent. A torn file
    is reported once and treated as empty, because rebuilding from {} silently drops prior stage
    walls (understating total_wall/RTF) and that loss must stay visible."""
    path = work.root / "timings.json"
    doc = _load_json(path)
    if doc is None and path.exists():
        try:
            if path.read_text(encoding="utf-8").strip():
                print(f"[warn] {path.name} unreadable — prior stage timings discarded",
                      file=sys.stderr)
        except OSError:
            pass
    return path, (doc if isinstance(doc, dict) else {})


def record_stage_timing(work, stage, wall_s) -> None:
    """Upsert ONE stage's wall-clock into work/timings.json, atomically, preserving every other
    stage's entry. Called per stage by the pipeline, so an --only or resumed run rewrites only
    the stages it actually ran; skipped stages keep their last real timing. Tolerates a
    missing/torn file. MUST NOT raise into the caller — a failed timing write is a [warn], never
    a broken pipeline.

    Writes back the WHOLE document, not {"stages": ...}. It used to replace the file with just
    that one key, which was invisible while `stages` was the only section and silently ate
    `detail` the moment a second one existed."""
    try:
        path, doc = load_timings(work)
        stages = doc.get("stages")
        if not isinstance(stages, dict):
            stages = {}
        stages[stage] = round(float(wall_s), 3)
        doc["stages"] = stages
        _atomic_write_json(path, doc)
    except Exception as e:                                  # noqa: BLE001 — must never propagate
        print(f"[warn] could not record timing for {stage!r}: {e}", file=sys.stderr)


def record_stage_detail(work, stage, **fields) -> None:
    """Upsert a stage's INNER measurements into work/timings.json → detail[<stage>].

    Kept apart from `stages` because the two answer different questions and must never be summed
    together. `stages[x]` is the pipeline's wall clock for the whole stage — model load included,
    which is what the run's cost actually was. `detail[x]` is what the stage measured about
    ITSELF (transcribe: decode time with the load excluded, and how many ASR passes ran), which
    is what a before/after optimization comparison needs and what the wall clock cannot give:
    load lands on whichever video happens to be first in the sweep.

    Same never-raises contract as record_stage_timing."""
    try:
        path, doc = load_timings(work)
        detail = doc.get("detail")
        if not isinstance(detail, dict):
            detail = {}
        entry = detail.get(stage)
        if not isinstance(entry, dict):
            entry = {}
        entry.update(fields)
        detail[stage] = entry
        doc["detail"] = detail
        _atomic_write_json(path, doc)
    except Exception as e:                                  # noqa: BLE001 — must never propagate
        print(f"[warn] could not record detail for {stage!r}: {e}", file=sys.stderr)


def record_stage_span(work, stage, *, enqueued, started, finished, clock=None) -> None:
    """Upsert ONE stage's absolute wall-clock WINDOW into work/timings.json → spans[<stage>].

    Three stamps, not two, and they are not interchangeable with `stages[x]`:

      enqueued — the runner decided this stage must run (it passed the --only and done() filters)
      started  — the stage body began, i.e. after any gating between the decision and the work
      finished — the body returned

    `clock` names where the stamps CAME FROM, and it decides whether `run_id` is written at all.
    Default None means "this process's own clock", the row gets `run_id`, and that id identifies
    the process that DID the work. Pass a string when the stamps describe work some other process
    did — the translate seam reads them off marker mtimes because neither a sub-agent nor a
    workflow script may stamp a clock — and the row gets `clock` INSTEAD of `run_id`.

    The absence is the point and is not a nicety: `run_id` exists so a consumer can compute a
    window over the work one invocation did. A foreign-clock span belongs to no invocation, so
    stamping it with the id of whichever process happened to WRITE it would silently fold the
    Sonnet wave into the run of `build_translation.py` — a group that never existed. Missing and
    zero are different answers here, same as everywhere else in this repo.

    `stages[x]` is a perf_counter DURATION. It cannot say WHEN a stage ran, so it cannot show two
    videos overlapping, and it cannot separate time spent waiting for a shared resource from time
    spent working — both land inside the one measurement. enqueued→started is the wait and
    started→finished is the work, and a stage that waits for nothing simply reports the two stamps
    a millisecond apart.

    Deliberately ADDITIVE: `stages[x]` keeps its meaning untouched. That float has already changed
    scope once (2026-08-05 — `overdub/CLAUDE.md`, corpus provenance) and every timings.json on disk is keyed to the
    current one, so a second silent redefinition would make the corpus unreadable rather than
    merely incomplete. The two also fail differently and that is worth having — perf_counter is
    monotonic and immune to a clock step, these stamps are comparable ACROSS videos and processes.

    Same upsert and never-raises contract as record_stage_timing: only stages that actually ran
    write a span, so a resumed run keeps the spans of the run that did the work.
    """
    try:
        path, doc = load_timings(work)
        spans = doc.get("spans")
        if not isinstance(spans, dict):
            spans = {}
        entry = {"enqueued": enqueued, "started": started, "finished": finished}
        entry.update({"run_id": RUN_ID} if clock is None else {"clock": clock})
        spans[stage] = entry
        doc["spans"] = spans
        _atomic_write_json(path, doc)
    except Exception as e:                                  # noqa: BLE001 — must never propagate
        print(f"[warn] could not record span for {stage!r}: {e}", file=sys.stderr)


def _elapsed_s(started, finished):
    """finished - started in seconds from two now_iso() strings, or None if either will not parse.
    None rather than 0.0: a missing elapsed must not read as an instant run."""
    try:
        t0 = datetime.datetime.fromisoformat(started)
        t1 = datetime.datetime.fromisoformat(finished)
    except (TypeError, ValueError):
        return None
    return round((t1 - t0).total_seconds(), 3)


def record_run(work_root, ids, *, started, finished, order, config_key) -> None:
    """Append ONE line to work/runs.jsonl: the elapsed window of this pipeline PROCESS.

    WHY IT EXISTS. `total_wall_s` in run.json is a SUM of per-stage walls for ONE video. Nothing
    anywhere records how long a queue actually took — and a sum stops being an elapsed time at all
    the moment two stages overlap. This file is the only record of the window itself.

    THE GRAIN IS ONE INVOCATION, which is why it is not named for a batch or a night: route B
    drives the pipeline more than once per queue (a pass up to the translate seam, then a resume),
    so "batch" would silently mean two different spans inside one series. A consumer that wants a
    night sums the lines it chose; nothing here decides that for it.

    `config_key` is what keeps the series comparable. A run of lines that silently spans an engine,
    voice or grouping change is worse than no series, because the change is invisible in exactly
    the numbers it moved — the trap run.json is already in (no engine field in any of them). The
    caller supplies the string; this module imports nothing and cannot build one.

    `audio_s` sums only the videos that HAVE a duration on disk and `audio_n` says how many that
    was, so a partial sum can never be read as the queue's total — the ratio this file exists to
    support is audio ÷ elapsed, and an unqualified numerator would overstate it silently.

    Never raises, and append-only: one short line written with a single write, so a torn line
    costs that line and not the file.
    """
    try:
        ids = list(ids)
        audio_s, audio_n = 0.0, 0
        for vid in ids:
            info = _load_json(work_root / vid / "source.info.json")
            dur = info.get("duration") if isinstance(info, dict) else None
            if isinstance(dur, (int, float)) and not isinstance(dur, bool) and dur > 0:
                audio_s += float(dur)
                audio_n += 1
        row = {"run_id": RUN_ID, "started": started, "finished": finished,
               "elapsed_s": _elapsed_s(started, finished), "order": order,
               "n": len(ids), "ids": ids,
               "audio_s": round(audio_s, 3), "audio_n": audio_n,
               "config_key": config_key}
        with open(work_root / "runs.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:                                  # noqa: BLE001 — must never propagate
        print(f"[warn] could not record the run window: {e}", file=sys.stderr)
