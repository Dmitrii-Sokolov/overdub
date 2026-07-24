"""ASR decode-config probe — measure one decode variant against the shipped config.

Built 2026-07-22 to replace a 3100-line sweep harness that never produced a number. It answers
the "Transcribe speed" roadmap question and nothing else, and it deliberately stops short of a
verdict: it prints the noise floor beside the effect and writes the word-stream diffs. **The
verdict comes from reading the diffs.** Every attempt here to encode an adoption rule in code
produced a rule that was wrong in a way nobody noticed until it was executed.

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\asr_probe.py --variant beam1
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\asr_probe.py --variant int8 --repeats 4
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\asr_probe.py --variant beam1 --report-only

Read-only w.r.t. the pipeline: it reads work/<id>/source.wav and writes only under --out
(default work-exp/asr-probe/, gitignored). It calls transcribe_words, the SAME body the stage
and --repair-asr use, so it cannot drift from what production decodes.

WHAT THE NUMBERS MEAN, and what they cannot tell you
----------------------------------------------------
work_sec .... Timed around transcribe_words alone; the model load and warmup are outside it.
              NOT comparable to the production stage's work_sec, which also covers _guard's
              second pass, resegment and two artifact writes. Compare probe to probe.

              MEASURED CONFOUND, and the reason for the block order below: this host drifts
              MONOTONICALLY FASTER over a session. On HEAD, shipped config, 3 repeats, block 3
              ran 8-29% faster than block 1 on all six videos, same direction every time
              (2026-07-22). That is not noise — averaging does not remove it and more repeats
              only tighten a biased estimate. It is also NOT the "RTF 0.39 cold vs 0.60 hot"
              recorded in DECISIONS 2026-07-19, which points the other way; the cause is
              unidentified, so it is controlled for rather than modelled.

sim ......... Char-level SequenceMatcher over norm_text of the flat word stream — the repo's one
              definition of "the same words" (repair.readings_agree). The SAME-VARIANT pair is
              the noise floor: whisper's temperature fallback samples, so two identical runs
              already differ. A cross-variant sim inside that floor means the variant changed
              nothing detectable. Below it means it changed something — NOT that it changed
              something bad. Read the diff.

floor_ratio . Share of words on the MIN_WORD_DUR floor in a chain: the signature of a collapsed
              word alignment (stages/transcribe.py). This one has a hard consequence rather than
              an opinion — above cfg.transcribe_floor_run_max the pipeline's own guard fires and
              re-runs ASR, so a variant that pushes videos over that line costs a second pass on
              them and can be a net LOSS at any speedup.

n_sentences . Resegmentation output. The sentence is the unit of translation, synthesis and
              timing sync, so a variant that keeps the words and moves the boundaries has still
              changed the pipeline's input. Recorded, never alarmed on.

diff.txt .... The point. A suspicious number must be readable as text.

DELIBERATELY ABSENT: any pass/fail verdict, any threshold besides the one the pipeline itself
enforces (transcribe_floor_run_max), any scoring against the human transcripts (that is
docs/repair-fixture.md's job, and its ground truth contains a known error).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub.asr import load_whisper                                    # noqa: E402
from overdub.config import Config                                       # noqa: E402
from overdub.stages.transcribe import (                                 # noqa: E402
    floor_run_ratio, norm_text, resegment, transcribe_words,
)

ROOT = Path(__file__).resolve().parents[1]

# The fixture six: 41 min of audio, ~3.5 min per pass. Short enough to iterate on, and the one
# corpus with human-verified transcripts if a diff ever needs adjudicating (docs/repair-fixture.md).
# NOT the production shape (those run 20-36 min), so a speedup measured here is a direction, not
# a production number — say so when quoting it.
VIDEOS = ["2YCaBqP8muw", "DmgujoZ1mmk", "RyvXxApfHkk",
          "W4Ua6XFfX9w", "W5cga7xipRI", "ytEN_iAk09c"]

# Overrides applied on top of the shipped config. "control" is the shipped config itself and is
# always measured, always in the same session — a stored baseline cannot control for the drift.
VARIANTS: dict[str, dict] = {
    "control": {},
    # MEASURED AND REJECTED 2026-07-22 — kept so the result is reproducible, not as a candidate.
    # 1.17x at best, two of six videos slower, "Claude" -> "Cloud" 23x, commas -> periods,
    # floor_ratio over the guard threshold on 2 of 6. See overdub.toml's whisper_beam_size note.
    "beam1": {"beam_size": 1},
    "int8": {"compute_type": "int8_float16"},
    "distil": {"model": "distil-large-v3"},        # not in the HF cache; first run downloads it
    "threads2": {"num_workers": 2},                # no threaded driver yet — measures nothing today
    # NOT a speed lever. This one exists to re-test a CAUSAL CLAIM this project has been treating
    # as settled since 2026-07-17 — that condition_on_previous_text=False is what produces
    # terminator-free blocks, and =True is what produces repetition loops. See PLAN, "The
    # condition_on_previous claim". Needs axes this probe does not have yet; read the item first.
    "nocond": {"cond": False},
}


def blocks(names: list[str], repeats: int) -> list[tuple[str, int]]:
    """Block order, MIRRORED on even repeats: A B / B A / A B / B A ...

    The host drifts monotonically faster within a session (see the module docstring), so a fixed
    order confounds "later" with "the variant". Mirroring makes each variant's mean position
    identical across a PAIR of repeats, which is exactly what cancels a linear drift — and it is
    why an even --repeats is worth more than one more odd repeat.
    """
    out: list[tuple[str, int]] = []
    for rep in range(1, repeats + 1):
        order = names if rep % 2 else list(reversed(names))
        out.extend((name, rep) for name in order)
    return out


def cell(out: Path, vid: str, variant: str, rep: int) -> Path:
    return out / f"{vid}__{variant}__r{rep}.json"


def measure(out: Path, cfg: Config, names: list[str], vids: list[str], repeats: int) -> None:
    for pos, (variant, rep) in enumerate(blocks(names, repeats), 1):
        over = VARIANTS[variant]
        todo = [v for v in vids if not cell(out, v, variant, rep).exists()]
        if not todo:
            print(f"[{pos}/{len(blocks(names, repeats))}] {variant} r{rep}: present, skipped")
            continue
        print(f"[{pos}/{len(blocks(names, repeats))}] {variant} r{rep}: {len(todo)} cells, "
              f"loading {over.get('model', cfg.whisper_model)} ...")
        model = load_whisper(over.get("model", cfg.whisper_model), cfg.whisper_device,
                             over.get("compute_type", cfg.compute_type_for("transcribe")),
                             beam_size=over.get("beam_size", cfg.whisper_beam_size),
                             num_workers=over.get("num_workers", 1))
        try:
            for vid in todo:
                t0 = time.perf_counter()
                flat = transcribe_words(
                    model, ROOT / "work" / vid / "source.wav", language=cfg.source_lang,
                    beam_size=over.get("beam_size", cfg.whisper_beam_size),
                    condition_on_previous=over.get("cond", cfg.whisper_condition_on_previous))
                work_s = time.perf_counter() - t0
                ratio, longest = floor_run_ratio(flat)
                sents = resegment(flat)
                cell(out, vid, variant, rep).write_text(json.dumps({
                    "video": vid, "variant": variant, "repeat": rep, "block_position": pos,
                    "work_sec": round(work_s, 2), "n_words": len(flat),
                    "n_sentences": len(sents), "floor_ratio": round(ratio, 4),
                    "floor_longest": longest,
                    "text": " ".join(w.text for w in flat),
                }, ensure_ascii=False), encoding="utf-8")
                print(f"    {vid}  {work_s:7.1f}s  {len(flat):5d} words  {len(sents):4d} sents  "
                      f"floor {ratio:.1%}")
        finally:
            del model
            try:
                import gc

                import torch
                gc.collect()
                torch.cuda.empty_cache()
            except Exception:                       # torch absent or already torn down
                pass


def _load(out: Path, vid: str, variant: str, repeats: int) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for r in range(1, repeats + 1)
            if (p := cell(out, vid, variant, r)).exists()]


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_text(a), norm_text(b), autojunk=False).ratio()


def _pairs(vals: list) -> list[tuple]:
    return [(vals[i], vals[j]) for i in range(len(vals)) for j in range(i + 1, len(vals))]


def report(out: Path, names: list[str], vids: list[str], repeats: int, floor_max: float) -> None:
    cand = [n for n in names if n != "control"]
    for variant in cand:
        print("\n" + "=" * 96)
        print(f"{variant.upper()} vs control — {len(vids)} videos, {repeats} repeats each")
        print(f"{'video':<14}{'ctl min':>9}{'var min':>9}{'speedup':>9}"
              f"{'floor sim':>11}{'cross sim':>11}{'ctl floor%':>12}{'var floor%':>12}")
        tot_c = tot_v = 0.0
        for vid in vids:
            c, v = _load(out, vid, "control", repeats), _load(out, vid, variant, repeats)
            if not c or not v:
                print(f"{vid:<14}  (missing cells — rerun without --report-only)")
                continue
            mc, mv = min(x["work_sec"] for x in c), min(x["work_sec"] for x in v)
            tot_c, tot_v = tot_c + mc, tot_v + mv
            # the noise floor is EVERY same-variant pair on both sides, not one anchored pair:
            # anchoring on repeat 1 makes one bad draw define the whole band
            same = [_sim(a["text"], b["text"]) for a, b in _pairs(c) + _pairs(v)]
            cross = [_sim(a["text"], b["text"]) for a in c for b in v]
            fc = statistics.median(x["floor_ratio"] for x in c)
            fv = statistics.median(x["floor_ratio"] for x in v)
            mark = "!" if fv > floor_max >= fc else " "
            print(f"{vid:<14}{mc:>9.1f}{mv:>9.1f}{mc / mv:>8.2f}x"
                  f"{(min(same) if same else 0):>11.4f}{(min(cross) if cross else 0):>11.4f}"
                  f"{fc * 100:>11.2f}%{fv * 100:>11.2f}%{mark}")
        if tot_v:
            print(f"{'TOTAL':<14}{tot_c:>9.1f}{tot_v:>9.1f}{tot_c / tot_v:>8.2f}x")
        print("  'floor sim' is the WORST same-variant pair — the run-to-run noise. A 'cross sim'")
        print("  at or above it means no detectable text change. Below it, read the diff.")
        print(f"  '!' marks a video the variant pushed over transcribe_floor_run_max "
              f"({floor_max:.1%}): the pipeline's alignment guard fires there and re-runs ASR,")
        print("  so those videos cost a second pass and can erase the speedup.")

        for vid in vids:
            c, v = _load(out, vid, "control", repeats), _load(out, vid, variant, repeats)
            if not c or not v:
                continue
            a, b = c[0]["text"].split(), v[0]["text"].split()
            lines = []
            for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
                if tag == "equal":
                    continue
                lines.append(f"[{tag}] control: {' '.join(a[max(0, i1 - 6):i2 + 6])}\n"
                             f"        {variant}: {' '.join(b[max(0, j1 - 6):j2 + 6])}\n")
            p = out / f"{vid}__diff_control_vs_{variant}.txt"
            p.write_text(f"{len(lines)} differing block(s)\n\n" + "\n".join(lines),
                         encoding="utf-8")
            print(f"  {p.name}: {len(lines)} differing block(s)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="asr_probe", formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)
    p.add_argument("--config", type=Path, default=Path("overdub.toml"))
    p.add_argument("--variant", action="append", default=[],
                   help=f"one of {', '.join(k for k in VARIANTS if k != 'control')} "
                        f"(repeatable); control is always measured alongside")
    p.add_argument("--repeats", type=int, default=2,
                   help="passes per variant (default 2). EVEN values are worth more than odd: "
                        "the mirrored block order cancels the host's session drift in pairs")
    p.add_argument("--videos", default="", help="comma-separated ids (default: the fixture six)")
    p.add_argument("--out", type=Path, default=Path("work-exp/asr-probe"))
    p.add_argument("--dry-run", action="store_true", help="print the plan, touch no GPU")
    p.add_argument("--report-only", action="store_true", help="re-report existing cells, no GPU")
    args = p.parse_args(argv)

    # Config.load returns DEFAULTS for a missing path, so a typo'd --config would silently
    # measure a config we do not ship — the exact silent failure this repo forbids.
    if not Path(args.config).exists():
        p.error(f"config not found: {args.config} — run from the repo root, or pass --config")
    cfg = Config.load(args.config)
    unknown = [v for v in args.variant if v not in VARIANTS]
    if unknown:
        p.error(f"unknown variant(s) {unknown}; known: {', '.join(VARIANTS)}")
    if not args.variant:
        p.error("nothing to compare — pass at least one --variant")
    names = ["control"] + [v for v in dict.fromkeys(args.variant)]
    vids = [v.strip() for v in args.videos.split(",") if v.strip()] or VIDEOS

    out = Path(args.out).resolve()
    work_root = Path(cfg.work_root).resolve()
    if out == work_root or work_root in out.parents:
        p.error(f"--out {out} is inside work_root {work_root} — this probe never writes into the "
                f"pipeline's workdirs")
    missing = [v for v in vids if not (ROOT / "work" / v / "source.wav").exists()]
    if missing:
        p.error(f"no source.wav for {missing}")

    plan = blocks(names, args.repeats)
    print(f"{len(names)} variants x {len(vids)} videos x {args.repeats} repeats = "
          f"{len(plan) * len(vids)} cells in {len(plan)} blocks")
    print("  order: " + " ".join(f"{n}r{r}" for n, r in plan))
    if args.repeats % 2:
        print(f"  [warn] --repeats {args.repeats} is ODD, so the mirrored order does not fully "
              f"cancel the session drift; the last repeat is unpaired", file=sys.stderr)
    if args.dry_run:
        print("dry run — no model loaded")
        return 0
    if not args.report_only:
        out.mkdir(parents=True, exist_ok=True)
        measure(out, cfg, names, vids, args.repeats)
    report(out, names, vids, args.repeats, cfg.transcribe_floor_run_max)
    return 0


if __name__ == "__main__":
    sys.exit(main())
