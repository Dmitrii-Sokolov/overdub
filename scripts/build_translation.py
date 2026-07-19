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

from overdub.config import Config                       # noqa: E402
from overdub.normalize import normalize_for_tts         # noqa: E402
from overdub.stages.translate import _is_bad            # noqa: E402
from overdub.workdir import WorkDir                      # noqa: E402


def _load_draft(path: Path) -> dict[int, str]:
    """Draft the sub-agent wrote: JSON list [{id, text_ru}, ...] -> {id: text_ru}."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        sys.exit(f"[FAIL] draft {path} is not a JSON list")
    out: dict[int, str] = {}
    for i, rec in enumerate(raw):
        try:
            sid = int(rec["id"])
            text_ru = str(rec["text_ru"])
        except (TypeError, KeyError, ValueError) as e:
            sys.exit(f"[FAIL] draft record {i} missing id/text_ru ({e}): {rec!r}")
        if sid in out:
            sys.exit(f"[FAIL] draft has duplicate id {sid}")
        out[sid] = text_ru
    return out


def build(work: WorkDir, draft_path: Path, cfg: Config) -> tuple[int, int]:
    """Write work/<id>/translation.json from the draft. Returns (total, flagged)."""
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
    for s in sentences:                                  # sentence order is the source of truth
        sid = s["id"]
        src_en = s["text"]
        text_ru = draft[sid].strip()
        reason = _is_bad(text_ru, src_en, cfg)           # same gate as the Gemma path
        rec = {
            "id": sid, "start": s["start"], "end": s["end"], "src_en": src_en,
            "text_ru": text_ru, "text_tts": normalize_for_tts(text_ru),
            "status": "ok" if reason is None else "failed", "attempts": 1,
        }
        if reason is not None:
            rec["flag"] = reason                         # flagged, never hidden, never blocking
            n_fail += 1
        out.append(rec)

    ids = [o["id"] for o in out]
    if ids != list(range(len(sentences))):               # never-drop invariant (mirrors TranslateStage)
        sys.exit(f"[FAIL] translation ids not contiguous (never-drop invariant): {ids}")

    tmp = work.translation.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, work.translation)                    # atomic: never a torn translation.json
    return len(out), n_fail


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

    total, n_fail = build(work, draft_path, Config.load(args.config))
    print(f"[ok] {total} sentences -> {work.translation} ({n_fail} flagged)")


if __name__ == "__main__":
    main()
