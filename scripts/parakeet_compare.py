"""Compare a Parakeet words.json against the whisper words.json the pipeline already shipped.

RUNS IN `.venv-asr` — the opposite side of scripts/parakeet_worker.py. This half imports the REAL
`overdub.stages.transcribe` (resegment, norm_text, floor_run_ratio), so the structural numbers
below are what the pipeline would actually build from each transcript, not a re-implementation.

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\parakeet_compare.py
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\parakeet_compare.py --whisper-root work-exp\\parakeet\\fixture-whisper

WHAT THE NUMBERS MEAN — read before quoting any of them

disagree ... Word-level edit rate between the two transcripts: (sub+ins+del) / len(whisper).
             NOT a word error rate. Neither side is ground truth, so this says how FAR APART they
             are and says nothing about which one is right. A high number is a pointer at a diff
             file, never a verdict.
sim ........ Agreement of the same alignment: eq / max(len(whisper), len(parakeet)) in WORDS.
             Deliberately NOT the repo's char-level SequenceMatcher (repair.readings_agree,
             asr_probe). That one is quadratic, and it is applied there to a 7-minute fixture
             video; this corpus holds 4.5-hour ones, where the flat word stream is a ~900 000
             character string and one call did not finish in ten minutes (measured 2026-08-06).
             The word alignment is computed once per video and both sim and the edit counts are
             read off it, so the two numbers can never disagree about what matched.
n_sent ..... resegment() output. The sentence is the unit of translation, synthesis and timing
             sync, so a transcript that keeps the words and moves the boundaries has still changed
             what the pipeline gets fed.
term_rate .. Share of word tokens ending in a terminator (.!?…). This is what sentence splitting
             RUNS ON: whisper punctuates from rolling context (condition_on_previous), Parakeet
             from its own decoder with no cross-file context. A large gap here predicts a large
             n_sent gap and is the single most load-bearing structural difference.
floor ...... floor_run_ratio: share of words on the MIN_WORD_DUR (0.02 s) floor in a chain. It is
             the pipeline's own collapse detector. Parakeet stamps on an 80 ms grid, so its value
             is structurally ~0 — that is not a health score, it means THE DETECTOR DOES NOT APPLY
             to this engine. Reported so the deadness is visible rather than mistaken for a win.
gap_max .... Largest silent span between consecutive words. Parakeet's known long-audio failure is
             DROPPING material, which looks exactly like a hole the other side does not have.
nonlatin ... Share of non-ASCII-letter characters in the Parakeet text. The model auto-detects
             language and cannot be forced to English; a drifted video shows up here.

DELIBERATELY ABSENT: any pass/fail rule. Same reason asr_probe states it — every attempt to encode
an adoption rule in code produced a rule that was wrong in a way nobody noticed until it executed.
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

from overdub.stages.transcribe import (      # noqa: E402
    MAX_SEC,
    W,
    floor_run_ratio,
    norm_text,
    resegment,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_words(path: Path) -> list[W]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [W(d["text"], float(d["start"]), float(d["end"]), bool(d.get("seg_end", False)))
            for d in data]


def _tokens(flat: list[W]) -> list[str]:
    """Normalized word tokens — the alignment unit. Empty ones (a bare '...' token) are dropped:
    they carry no identity and would count as an edit against a side that never emitted them."""
    return [t for t in (norm_text(w.text) for w in flat) if t]


def _align(a: list[str], b: list[str]) -> list:
    """Word-level opcodes. THE single alignment per video — sim, the edit counts and the diff file
    are all read off this one call, so no two of them can disagree about what matched."""
    return SequenceMatcher(None, a, b, autojunk=False).get_opcodes()


def _edit_counts(a: list[str], b: list[str], opcodes: list) -> dict:
    sub = ins = dele = eq = 0
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            eq += i2 - i1
        elif tag == "replace":
            sub += max(i2 - i1, j2 - j1)
        elif tag == "insert":
            ins += j2 - j1
        elif tag == "delete":
            dele += i2 - i1
    total = max(len(a), 1)
    return {"eq": eq, "sub": sub, "ins": ins, "del": dele,
            "sim": round(eq / max(len(a), len(b), 1), 4),
            "disagree": round((sub + ins + dele) / total, 4)}


def _structure(flat: list[W]) -> dict:
    sents = resegment(flat)
    durs = [s["end"] - s["start"] for s in sents] or [0.0]
    chars = [len(s["text"]) for s in sents] or [0]
    terms = sum(1 for w in flat if w.text.strip().rstrip("\"'”’»)]}")[-1:] in ".!?…")
    ratio, longest = floor_run_ratio(flat)
    gaps = [flat[i + 1].start - flat[i].end for i in range(len(flat) - 1)] or [0.0]
    speech = sum(w.end - w.start for w in flat)
    return {
        "n_words": len(flat),
        "n_sent": len(sents),
        "sent_dur_med": round(statistics.median(durs), 2),
        "sent_chars_med": int(statistics.median(chars)),
        "sent_at_cap": sum(1 for d in durs if d >= MAX_SEC - 0.01),
        "term_rate": round(terms / max(len(flat), 1), 4),
        "floor": round(ratio, 4),
        "floor_run": longest,
        "gap_max": round(max(gaps), 2),
        "speech_sec": round(speech, 1),
        "span_sec": round(flat[-1].end - flat[0].start, 1) if flat else 0.0,
    }


def _nonlatin_share(flat: list[W]) -> float:
    letters = [c for w in flat for c in w.text if c.isalpha()]
    if not letters:
        return 0.0
    return round(sum(1 for c in letters if ord(c) > 127) / len(letters), 4)


def _write_diff(path: Path, vid: str, a_flat: list[W], b_flat: list[W], opcodes: list) -> None:
    """Word diff with timecodes and context — the point of the whole script.

    A suspicious number must be readable as text (asr_probe's rule). Each hunk is stamped with the
    whisper-side time so it can be listened to, because the ear is the only adjudicator here.

    Takes the opcodes rather than recomputing them: on a 4.5-hour video the alignment is the
    expensive part of this script, and a second call could also drift from the one the numbers
    were read off."""
    a, b = _tokens(a_flat), _tokens(b_flat)
    a_times = [w.start for w in a_flat if norm_text(w.text)]
    lines = [f"# {vid}   whisper={len(a)} words   parakeet={len(b)} words", ""]
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            continue
        t = a_times[min(i1, len(a_times) - 1)] if a_times else 0.0
        ctx_l = " ".join(a[max(0, i1 - 6):i1])
        ctx_r = " ".join(a[i2:i2 + 6])
        lines += [
            f"[{int(t) // 60:02d}:{int(t) % 60:02d}] {tag}",
            f"   ...{ctx_l} <<< {' '.join(a[i1:i2]) or '-'} >>> {ctx_r}...     (whisper)",
            f"   ...{ctx_l} <<< {' '.join(b[j1:j2]) or '-'} >>> {ctx_r}...     (parakeet)",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--whisper-root", type=Path, default=ROOT / "work")
    ap.add_argument("--parakeet-root", type=Path, default=ROOT / "work-exp" / "parakeet" / "out")
    ap.add_argument("--out", type=Path, default=ROOT / "work-exp" / "parakeet" / "report")
    ap.add_argument("--diffs", type=int, default=20, help="write diff files for the N worst by sim")
    args = ap.parse_args()

    rows, skipped, one_sided, failures = [], [], [], []
    opcodes_by_id: dict = {}
    for pdir in sorted(args.parakeet_root.glob("*/words.json")):
        vid = pdir.parent.name
        wpath = args.whisper_root / vid / "words.json"
        if not wpath.exists():
            skipped.append(vid)
            continue
        w_flat, p_flat = _load_words(wpath), _load_words(pdir)
        if not w_flat or not p_flat:
            # An EMPTY side is a result, not a skip: whisper writes [] for a no-speech video
            # (stages/translate.py's empty-transcript case), so "whisper empty, parakeet 400
            # words" is a hallucination report and the reverse is a dropped video. Counting these
            # as "nothing to compare" would hide the loudest failure the corpus can produce.
            one_sided.append({"id": vid, "whisper_words": len(w_flat), "parakeet_words": len(p_flat)})
            continue
        w_tok, p_tok = _tokens(w_flat), _tokens(p_flat)
        meta = {}
        mpath = pdir.parent / "meta.json"
        if mpath.exists():
            meta = json.loads(mpath.read_text(encoding="utf-8"))
        t0 = time.perf_counter()
        opcodes = _align(w_tok, p_tok)
        row = {
            "id": vid,
            "audio_min": round(meta.get("audio_sec", 0) / 60, 1),
            **_edit_counts(w_tok, p_tok, opcodes),
            "nonlatin": _nonlatin_share(p_flat),
            "wall_sec": meta.get("wall_sec"),
            "rtf": meta.get("rtf"),
            "vram_mb": meta.get("vram_peak_mb"),
            "chunks": meta.get("chunks"),
            "whisper": _structure(w_flat),
            "parakeet": _structure(p_flat),
        }
        rows.append(row)
        opcodes_by_id[vid] = opcodes
        print(f"  {len(rows):3d}. {vid}  {row['audio_min']:6.1f} min  sim {row['sim']:.3f}  "
              f"({time.perf_counter() - t0:.1f}s)", file=sys.stderr)

    # Videos the worker could not decode at all leave a meta.json with an "error" and no
    # words.json, so the loop above never sees them. They are the most important rows in a
    # long-audio experiment — an OOM at 4 hours IS the finding — and must not be invisible.
    for mpath in sorted(args.parakeet_root.glob("*/meta.json")):
        if (mpath.parent / "words.json").exists():
            continue
        err = json.loads(mpath.read_text(encoding="utf-8")).get("error", "unknown")
        failures.append({"id": mpath.parent.name, "error": err})

    if not rows:
        print("no comparable pairs found", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(
        json.dumps({"compared": rows, "one_sided": one_sided, "failed": failures,
                    "no_whisper_side": skipped}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    flat_keys = ["id", "audio_min", "sim", "disagree", "sub", "ins", "del", "nonlatin",
                 "wall_sec", "rtf", "vram_mb", "chunks"]
    struct_keys = ["n_words", "n_sent", "term_rate", "sent_dur_med", "sent_at_cap", "floor",
                   "gap_max", "speech_sec"]
    header = flat_keys + [f"w_{k}" for k in struct_keys] + [f"p_{k}" for k in struct_keys]
    csv = [",".join(header)]
    for r in rows:
        csv.append(",".join(str(r.get(k, "")) for k in flat_keys)
                   + "," + ",".join(str(r["whisper"][k]) for k in struct_keys)
                   + "," + ",".join(str(r["parakeet"][k]) for k in struct_keys))
    (args.out / "summary.csv").write_text("\n".join(csv), encoding="utf-8")

    worst = sorted(rows, key=lambda r: r["sim"])[:args.diffs]
    ddir = args.out / "diffs"
    ddir.mkdir(exist_ok=True)
    for r in worst:
        _write_diff(ddir / f"{r['id']}.txt", r["id"],
                    _load_words(args.whisper_root / r["id"] / "words.json"),
                    _load_words(args.parakeet_root / r["id"] / "words.json"),
                    opcodes_by_id[r["id"]])

    def med(f):
        return round(statistics.median([f(r) for r in rows]), 4)

    print(f"videos compared: {len(rows)}")
    print(f"  sim        median {med(lambda r: r['sim'])}   "
          f"min {min(r['sim'] for r in rows)}   max {max(r['sim'] for r in rows)}")
    print(f"  disagree   median {med(lambda r: r['disagree'])}")
    print(f"  words      whisper {sum(r['whisper']['n_words'] for r in rows)}   "
          f"parakeet {sum(r['parakeet']['n_words'] for r in rows)}")
    print(f"  sentences  whisper {sum(r['whisper']['n_sent'] for r in rows)}   "
          f"parakeet {sum(r['parakeet']['n_sent'] for r in rows)}")
    print(f"  term_rate  whisper {med(lambda r: r['whisper']['term_rate'])}   "
          f"parakeet {med(lambda r: r['parakeet']['term_rate'])}")
    print(f"  floor      whisper {med(lambda r: r['whisper']['floor'])}   "
          f"parakeet {med(lambda r: r['parakeet']['floor'])}")
    print(f"  gap_max    whisper {med(lambda r: r['whisper']['gap_max'])}s   "
          f"parakeet {med(lambda r: r['parakeet']['gap_max'])}s")
    print(f"  nonlatin   max {max(r['nonlatin'] for r in rows)}")
    rtfs = [r["rtf"] for r in rows if r.get("rtf")]
    if rtfs:
        print(f"  rtf        median {round(statistics.median(rtfs), 5)}   "
              f"vram max {max((r['vram_mb'] or 0) for r in rows)} MB")
    for label, items in (("one-sided (one transcript empty)", one_sided),
                         ("failed to decode", failures),
                         ("no whisper words.json", [{"id": v} for v in skipped])):
        if items:
            print(f"  {label}: {len(items)} — " + ", ".join(str(x.get('id')) for x in items[:12])
                  + (" …" if len(items) > 12 else ""))
    print(f"\nwrote {args.out / 'summary.csv'} and {len(worst)} diff files under {ddir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
