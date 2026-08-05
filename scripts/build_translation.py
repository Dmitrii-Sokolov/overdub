"""Assemble work/<id>/translation.json from a Sonnet sub-agent's minimal draft (route B).

README "Running" route B: the sub-agent translates and writes only the fragile, judgement
part -- {id, text_ru} per sentence. THIS script owns the deterministic, error-prone rest so
the translate-seam contract never rides on an LLM's discipline:

  - src_en / start / end   copied from sentences.json (join on id)
  - text_tts               overdub.normalize.normalize_for_tts(text_ru) -- the SAME function
                           the verify stage applies, so the ASR round-trip is exact by
                           construction (never let the LLM spell text_tts, DECISIONS)
  - status / flag          overdub.stages.translate._is_bad(...) gate -- the same reasons the
                           gate flags (empty / no_cyrillic / english_echo / runaway / refusal)
  - id-contiguity          enforced (exit, never a silent drop) exactly like TranslateStage.run
  - pronounce_audit.json   pronounce.audit_summary(...) -- the audit-only operator-triage
                           artifact the pipeline expects; without it route B silently loses
                           the only detector for the out-of-dict Latin-name silent-loss class
                           (DECISIONS 2026-07-17 item F)

The ONE judgement field beyond text_ru the sub-agent also owns is `src` -- its reading of the
ENGLISH source (the source-anomaly pass). A good translator is a defect BLEACHER: DECISIONS 2026-07-19,
RyvXxApfHkk id11's ASR garbage came back as plausible Russian on the first pass and vanished
from everything downstream, and rate_implausible / dup_adjacent are blind BY CONSTRUCTION to a
semantic garble that carries no timing anomaly and no repeated span. This script copies `src`
onto translation.json, clamps an unknown kind instead of dropping it, and COUNTS how many
records carried one at all -- so a skipped anomaly pass reports as "not scanned" rather than as
a clean-looking empty report. Every src defect is a [warn], NEVER an exit: a hard failure here
would leave translation.json unwritten, which stops the resume dead at TranslateStage.run -- i.e.
the report would have decided whether the video gets dubbed at all, and a report must never do
that.

Reusing the pipeline's own (partly private) helpers is deliberate: route B replaces only the
LLM call, so every downstream invariant stays byte-identical to what the stage itself enforces.
If _is_bad or normalize_for_tts change, this script inherits the change for free.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\build_translation.py work\\<id>

CHUNKED variant, for a transcript one sub-agent cannot cover in a single window:

    ... build_translation.py work\\<id> --plan          # the cut, as JSON, for the workflow
    ... build_translation.py work\\<id> --join          # chunk drafts -> draft -> translation.json

Same seam, same contract, one extra hop: each agent writes work/<id>/translate/<from>-<to>.json
in the ordinary draft record shape, --join concatenates them into translation.draft.json and the
build below proceeds unchanged. On THIS path the chunk files are the evidence a human checks and
translation.draft.json is derived from them (queue-contract §5) -- the reverse of the one-agent
path, where the draft is what the agent itself wrote.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub import pronounce                            # noqa: E402
from overdub.config import Config                       # noqa: E402
from overdub.normalize import normalize_for_tts         # noqa: E402
from overdub.runreport import record_stage_timing        # noqa: E402
from overdub.stages.translate import _is_bad            # noqa: E402
from overdub.workdir import WorkDir                      # noqa: E402

# Route E's cut, reused rather than re-derived. "Break the range on the longest pause, absorb a
# stub tail" is the same problem here as there, and the one thing worse than a cross-route import
# between two sibling helpers is two copies of a boundary rule that must agree with itself: the
# planner and the join BOTH compute the cut, so a drift would name chunk files nobody wrote.
from build_clean import plan_chunks                      # noqa: E402

# Sentences per chunk. A HYPOTHESIS off one measurement, not a measured constant, and labelled as
# such deliberately: on 2026-08-05 a 2259-sentence transcript (Karpathy, 3.5 h) defeated the
# single-agent route twice, at 1200 and at 1500 records written -- both while ALSO reading the
# whole 411 KB transcript. A chunk agent reads only its own slice, so 400 sits ~4x under the
# observed ceiling with the read cost removed too. Re-site it once a wave of long videos exists;
# smaller is always safe and costs one more spawn.
DEFAULT_CHUNK = 400

# Closed source-anomaly vocabulary. Mirrored in runreport._SOURCE_KINDS, which adds
# the "unknown" bucket this file clamps into -- keep the two in sync, one is the writer and the
# other the reader. See references/translate-contract.md for what each kind means.
_SRC_KINDS = ("ok", "garbled", "truncated", "dup_neighbour", "enum_repeat",
              "context_contradiction")
_SRC_NOTE_MAX = 200          # visible cap, same discipline as runreport._SUMMARY_MAX_CHARS


def _load_draft(path: Path) -> dict[int, tuple[str, str | None, str]]:
    """Draft the sub-agent wrote: JSON list [{id, text_ru, src, src_note?}, ...]
    -> {id: (text_ru, src|None, src_note)}. src is None when the record carried none
    (an UNSCANNED record -- counted, warned, never fatal: see build())."""
    # Named per message because the chunked path loads SIX of these per video: "record 12" with no
    # file in front of it addresses nothing an operator can re-run.
    who = f"draft {path.name}"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        sys.exit(f"[FAIL] {who} is not a JSON list")
    out: dict[int, tuple[str, str | None, str]] = {}
    for i, rec in enumerate(raw):
        try:
            sid = int(rec["id"])
            text_ru = rec["text_ru"]
        except (TypeError, KeyError, ValueError) as e:
            sys.exit(f"[FAIL] {who} record {i} missing id/text_ru ({e}): {rec!r}")
        if not isinstance(text_ru, str):
            # str() coercion would voice a JSON null literally ("None" -> "нон") and it
            # passes every _is_bad gate -- reject the type, don't launder it
            sys.exit(f"[FAIL] {who} record {i}: text_ru is not a string: {rec!r}")
        if sid in out:
            sys.exit(f"[FAIL] {who} has duplicate id {sid}")
        # src / src_note are REPORT fields -- a wrong id set produces a wrong DUB (hence the
        # exits above), a mislabeled report row produces a slightly-wrong report. Warn, degrade.
        src = rec.get("src") if isinstance(rec, dict) else None
        note = rec.get("src_note") if isinstance(rec, dict) else None
        if src is not None and not isinstance(src, str):
            print(f"[warn] draft record {i}: src is not a string ({src!r}) -> unscanned")
            src = None
        if not isinstance(note, str):
            if note is not None:
                print(f"[warn] draft record {i}: src_note is not a string -> dropped")
            note = ""
        out[sid] = (text_ru, src, note.strip())
    return out


def wave_wall_s(work: WorkDir, chunk_paths: list[Path] | None = None) -> float | None:
    """Wall-clock of the Sonnet translate wave for this video, in seconds, or None if unmeasurable.

    NOTHING ELSE RECORDS THIS. The LLM call left the host at the translate seam, so the wave is not
    a pipeline stage: `translate` appeared in the `stages` map of ZERO of 252 timings.json on
    2026-08-05, and the only other copy of the number is the `duration_ms` of a `Workflow`
    notification, which is per WAVE (not per video) and dies with the session. So every throughput
    figure the project publishes silently excludes the seam — measured the same day, a digest
    reading ×3.73 against an actual ×1.31.

    Both ends come off the filesystem because neither side can stamp a clock: the sub-agent is
    forbidden to report its own runtime (queue-contract §7 — it touches a marker and the filesystem
    stamps it), and a workflow script cannot call Date.now() at all (it would break resume).

      start = translate.started, touched by the agent as its FIRST action
      end   = the last thing an agent wrote: the draft, or the newest chunk file on the chunked
              path (there --join writes the draft itself, so the draft's mtime is OUR clock, not
              the agent's)

    Returns None rather than a guess in every case it cannot stand behind — a missing marker costs
    a timing and nothing else (§7), and a wrong number here would be laundered into total_wall_s
    and RTF, where nothing downstream could ever contradict it.
    """
    marker = work.root / "translate.started"
    if not marker.exists():
        return None
    ends = [p for p in (chunk_paths or []) if p.exists()]
    if not ends:
        draft = work.root / "translation.draft.json"
        if not draft.exists():
            return None
        ends = [draft]
    start = marker.stat().st_mtime
    end = max(p.stat().st_mtime for p in ends)
    if end <= start:
        return None                                      # stale marker from an earlier attempt
    # A marker older than the transcript belongs to a PREVIOUS translate of a since-repaired
    # sentences.json: measuring from it would bill this wave for the gap between two runs.
    if work.sentences.exists() and start < work.sentences.stat().st_mtime:
        return None
    return round(end - start, 3)


def join_chunks(work: WorkDir, chunks: list[dict]) -> tuple[Path, list[tuple[str, int]]]:
    """Concatenate work/<id>/translate/<from>-<to>.json into translation.draft.json.

    Verifies coverage the same way route E's join does, and for the same reason: a planner bug and
    an agent that stopped early are indistinguishable once the records are in one list. Each chunk
    must carry EXACTLY its own declared range -- a missing id costs a dub, an id outside the range
    means two agents wrote one sentence and the later one silently wins.

    Returns (draft_path, rows) where rows are (chunk name, record count) for the operator print.
    """
    sentences = json.loads(work.sentences.read_text(encoding="utf-8"))
    if not isinstance(sentences, list) or not sentences:
        sys.exit(f"[FAIL] {work.sentences} is not a non-empty sentence list")
    sent_ids = {s["id"] for s in sentences}

    merged: dict[int, tuple[str, str | None, str]] = {}
    rows: list[tuple[str, int]] = []
    for ch in chunks:
        name = f"{ch['from']}-{ch['to']}.json"
        path = work.translate_dir / name
        if not path.exists():
            # Also the shape a STALE plan takes: a --repair-asr pass renumbers every later id, so
            # the cut moves and the chunk files on disk are named for ranges nobody now asks for.
            sys.exit(f"[FAIL] chunk {name} is missing -- either its sub-agent did not finish (re-run "
                     f"that chunk alone; the others are on disk), or the plan is stale because a "
                     f"--repair-asr pass renumbered the ids (re-run --plan and translate the new cut)")
        part = _load_draft(path)
        expected = [i for i in sent_ids if ch["from"] <= i <= ch["to"]]
        missing = sorted(i for i in expected if i not in part)
        if missing:
            sys.exit(f"[FAIL] chunk {name} is missing {len(missing)} sentence(s): ids "
                     f"{missing[:20]}{' ...' if len(missing) > 20 else ''} -- re-run this chunk")
        extra = sorted(i for i in part if i not in set(expected))
        if extra:
            sys.exit(f"[FAIL] chunk {name} carries {len(extra)} id(s) outside its own range "
                     f"{ch['from']}..{ch['to']}: {extra[:20]} -- two agents would be writing one "
                     f"sentence; re-run this chunk")
        merged.update(part)
        rows.append((name, len(expected)))

    # No "is every sentence in some chunk" check here, deliberately: plan_chunks covers 0..n-1 by
    # construction (tests/test_build_translation.py asserts it), each chunk is verified against its
    # own declared range just above, and build() below re-checks the assembled draft against
    # sentences.json anyway. A fourth net over the same hole is code that cannot run.
    draft = []
    for sid in sorted(merged):
        text_ru, src, note = merged[sid]
        rec: dict = {"id": sid, "text_ru": text_ru}
        if src is not None:
            rec["src"] = src
        if note:
            rec["src_note"] = note
        draft.append(rec)

    path = work.root / "translation.draft.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)                                # atomic: never a torn draft
    return path, rows


def build(work: WorkDir, draft_path: Path, cfg: Config
          ) -> tuple[int, int, int, int, list[tuple[int, str, str, str]]]:
    """Write work/<id>/translation.json from the draft.

    Returns (total, flagged, source_anomalies, scanned, anomaly_rows) -- the rows are
    (id, kind, note, src_en) so main() can print each anomaly WITH its English source at the
    seam, hours before synthesize, where --repair-asr is still cheap."""
    sentences = json.loads(work.sentences.read_text(encoding="utf-8"))
    draft = _load_draft(draft_path)

    sent_ids = [s["id"] for s in sentences]
    missing = [i for i in sent_ids if i not in draft]
    if missing:
        sys.exit(f"[FAIL] draft is missing {len(missing)} sentence(s): ids "
                 f"{missing[:20]}{' ...' if len(missing) > 20 else ''}")
    extra = [i for i in draft if i not in set(sent_ids)]
    if extra:
        sys.exit(f"[FAIL] draft has {len(extra)} id(s) not in sentences.json: {extra[:20]}")

    out: list[dict] = []
    n_fail = 0
    n_scanned = n_anom = 0
    anom_rows: list[tuple[int, str, str, str]] = []
    for s in sentences:                                  # sentence order is the source of truth
        sid = s["id"]
        src_en = s["text"]
        text_ru, src, note = draft[sid]
        text_ru = text_ru.strip()
        reason = _is_bad(text_ru, src_en, cfg)           # the pipeline's own gate
        rec = {
            "id": sid, "start": s["start"], "end": s["end"], "src_en": src_en,
            "text_ru": text_ru, "text_tts": normalize_for_tts(text_ru),
            "status": "ok" if reason is None else "failed", "attempts": 1,
        }
        if reason is not None:
            rec["flag"] = reason                         # flagged, never hidden, never blocking
            n_fail += 1
        if src is not None:
            n_scanned += 1
            if src not in _SRC_KINDS:
                # clamp, never drop: an unknown kind must not vanish, and must not fail the
                # build either -- a report never gates a dub (the source-anomaly pass and the
                # video summary are both informational, DECISIONS 2026-07-20 D2).
                print(f"[warn] id {sid}: unknown src {src!r} -> unknown")
                note = f"[raw src={src!r}] {note}".strip()
                src = "unknown"
            # `src` is copied for EVERY scanned record, "ok" included: this file is written by
            # Python, not by an LLM, so the copy costs zero output tokens and ~1% of the record's
            # bytes, and it is what makes run.json's `scanned` derivable from translation.json
            # alone, forever, surviving --rebuild. The token argument applies to the DRAFT.
            rec["src"] = src
            if src != "ok":
                if not note:
                    print(f"[warn] id {sid}: src={src!r} with no src_note")
                rec["src_note"] = (note[:_SRC_NOTE_MAX].rstrip() + " …[truncated]"
                                   if len(note) > _SRC_NOTE_MAX else note)
                anom_rows.append((sid, src, rec["src_note"], src_en))
                n_anom += 1
        out.append(rec)

    ids = [o["id"] for o in out]
    if ids != list(range(len(sentences))):               # never-drop invariant (mirrors TranslateStage)
        sys.exit(f"[FAIL] translation ids not contiguous (never-drop invariant): {ids}")

    tmp = work.translation.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, work.translation)                    # atomic: never a torn translation.json

    # pronounce audit -- same audit-only artifact as TranslateStage.run (written, never
    # read back): operator triage of what the pipeline invented for Latin tokens
    audit = pronounce.audit_summary(work.root.name, out)
    atmp = work.pronounce_audit.with_suffix(".json.tmp")
    atmp.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(atmp, work.pronounce_audit)
    return len(out), n_fail, n_anom, n_scanned, anom_rows


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="build_translation",
        description="Assemble translation.json from a {id,text_ru} draft (route B / Sonnet).")
    p.add_argument("workdir", type=Path, help="per-video work dir, e.g. work/<id>")
    p.add_argument("--draft", type=Path, default=None,
                   help="draft JSON [{id,text_ru}] (default: <workdir>/translation.draft.json)")
    p.add_argument("--config", type=Path, default=Path("overdub.toml"),
                   help="TOML config for _is_bad thresholds; built-in defaults if absent")
    p.add_argument("--plan", action="store_true",
                   help="print the chunk cut as JSON and stop (chunked path, long transcripts)")
    p.add_argument("--join", action="store_true",
                   help="assemble the draft from <workdir>/translate/*.json first, then build")
    p.add_argument("--chunk", type=int, default=DEFAULT_CHUNK, metavar="N",
                   help=f"sentences per chunk (default {DEFAULT_CHUNK}). The SAME value must be "
                        f"used for --plan and for --join, or the chunk file names will not match.")
    args = p.parse_args(argv)

    work = WorkDir(args.workdir)
    if not work.sentences.exists():
        sys.exit(f"[FAIL] {work.sentences} not found -- run transcribe first")

    sentences = json.loads(work.sentences.read_text(encoding="utf-8"))
    if args.plan:
        # Printed as one JSON line so the orchestrator can hand it to the workflow verbatim
        # instead of retyping ranges -- the same handoff route E's --plan uses.
        print(json.dumps(plan_chunks(sentences, args.chunk), ensure_ascii=False))
        return

    chunk_paths: list[Path] = []
    if args.join:
        if args.draft:
            sys.exit("[FAIL] --join builds the draft from the chunk files; --draft contradicts it")
        plan = plan_chunks(sentences, args.chunk)
        draft_path, rows = join_chunks(work, plan)
        chunk_paths = [work.translate_dir / f"{c['from']}-{c['to']}.json" for c in plan]
        print(f"[ok] joined {len(rows)} chunk(s) -> {draft_path}")
        for name, n in rows:
            print(f"  chunk {name}  {n} sentences")
    else:
        draft_path = args.draft or (work.root / "translation.draft.json")
    if not draft_path.exists():
        sys.exit(f"[FAIL] draft not found: {draft_path}")

    total, n_fail, n_anom, n_scanned, anom_rows = build(work, draft_path,
                                                        Config.load(args.config))
    # The seam surface: step 2 runs HOURS before synthesize, so an anomaly named here is one a
    # human can still act on cheaply (--repair-asr <ids>, then re-run step 2 for that video).
    if n_scanned == 0:
        print("[warn] no record carried a 'src' field -- the source-anomaly pass did not run "
              "(see references/translate-contract.md); reported as scanned=false")
    elif n_scanned < total:
        print(f"[warn] only {n_scanned}/{total} records carried 'src' -- partial source scan")
    # The seam's own wall clock, recorded into the SAME map the pipeline's stages use, so the
    # digest's stage split and total_wall_s stop pretending translation is free. From here on a
    # run's total INCLUDES the seam and is not comparable with one from before 2026-08-05.
    wall = wave_wall_s(work, chunk_paths)
    if wall is None:
        print("[warn] translate wave not timed (no usable translate.started) -- the seam is "
              "missing from this video's total_wall_s and stage split")
    else:
        record_stage_timing(work, "translate", wall)
        print(f"[ok] translate wave {wall:.0f}s -> timings.json")

    print(f"[ok] {total} sentences -> {work.translation} "
          f"({n_fail} flagged, {n_anom} source anomalies, {n_scanned}/{total} src-scanned)")
    for sid, kind, note, src_en in anom_rows:
        print(f"  src {sid} [{kind}] {note}")
        print(f"      EN: {src_en[:100]}")


if __name__ == "__main__":
    main()
