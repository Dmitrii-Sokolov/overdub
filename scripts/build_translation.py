"""Assemble work/<id>/translation.json from a Sonnet sub-agent's minimal draft (route B).

README "Running" route B: the sub-agent translates and writes only the fragile, judgement
part -- {id, text_ru} per sentence. THIS script owns the deterministic, error-prone rest so
the translate-seam contract never rides on an LLM's discipline:

  - src_en / start / end   copied from sentences.json (join on id)
  - text_tts               overdub.normalize.normalize_for_tts(text_ru) -- the SAME function
                           the verify stage applies, so the ASR round-trip is exact by
                           construction (never let the LLM spell text_tts, DECISIONS)
  - status / flag          overdub.stages.translate._is_bad(...) gate -- the same reasons the
                           in-pipeline Gemma path flags (empty / no_cyrillic / english_echo /
                           runaway / refusal)
  - id-contiguity          enforced (exit, never a silent drop) exactly like TranslateStage.run
  - pronounce_audit.json   pronounce.audit_summary(...) -- the audit-only operator-triage
                           artifact the local route writes; without it route B silently loses
                           the only detector for the out-of-dict Latin-name silent-loss class
                           (DECISIONS 2026-07-17 item F)

The ONE judgement field beyond text_ru the sub-agent also owns is `src` -- its reading of the
ENGLISH source (the source-anomaly pass). A good translator is a defect BLEACHER: DECISIONS 2026-07-19,
RyvXxApfHkk id11's ASR garbage came back as plausible Russian on the first pass and vanished
from everything downstream, and rate_implausible / dup_adjacent are blind BY CONSTRUCTION to a
semantic garble that carries no timing anomaly and no repeated span. This script copies `src`
onto translation.json, clamps an unknown kind instead of dropping it, and COUNTS how many
records carried one at all -- so a skipped anomaly pass reports as "not scanned" rather than as
a clean-looking empty report. Every src defect is a [warn], NEVER an exit: a report must never
gate a dub, and a hard failure here would leave translation.json unwritten and hand that video
to the silent local-Gemma path at resume.

Reusing the pipeline's own (partly private) helpers is deliberate: route B replaces only the
LLM call, so every downstream invariant stays byte-identical to the local route. If _is_bad or
normalize_for_tts change, this script inherits the change for free.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\build_translation.py work\\<id>
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
from overdub.stages.translate import _is_bad            # noqa: E402
from overdub.workdir import WorkDir                      # noqa: E402

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
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        sys.exit(f"[FAIL] draft {path} is not a JSON list")
    out: dict[int, tuple[str, str | None, str]] = {}
    for i, rec in enumerate(raw):
        try:
            sid = int(rec["id"])
            text_ru = rec["text_ru"]
        except (TypeError, KeyError, ValueError) as e:
            sys.exit(f"[FAIL] draft record {i} missing id/text_ru ({e}): {rec!r}")
        if not isinstance(text_ru, str):
            # str() coercion would voice a JSON null literally ("None" -> "нон") and it
            # passes every _is_bad gate -- reject the type, don't launder it
            sys.exit(f"[FAIL] draft record {i}: text_ru is not a string: {rec!r}")
        if sid in out:
            sys.exit(f"[FAIL] draft has duplicate id {sid}")
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
        reason = _is_bad(text_ru, src_en, cfg)           # same gate as the Gemma path
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
    args = p.parse_args(argv)

    work = WorkDir(args.workdir)
    if not work.sentences.exists():
        sys.exit(f"[FAIL] {work.sentences} not found -- run transcribe first")
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
    print(f"[ok] {total} sentences -> {work.translation} "
          f"({n_fail} flagged, {n_anom} source anomalies, {n_scanned}/{total} src-scanned)")
    for sid, kind, note, src_en in anom_rows:
        print(f"  src {sid} [{kind}] {note}")
        print(f"      EN: {src_en[:100]}")


if __name__ == "__main__":
    main()
