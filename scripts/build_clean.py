"""Route E: cut a transcript into chunks, then join the sub-agents' cleaned chunks back into
work/<id>/clean.json + clean.md.

Same division of labour as build_translation.py / build_scout.py, for the same reason: the
sub-agent writes ONLY the fragile part -- the cleaned text of its own id range -- and this script
owns every deterministic decision, so the deliverable never rides on an LLM's discipline.

  --plan   prints the chunk cut as JSON. The orchestrator passes it to the workflow verbatim and
           never invents one: chunk boundaries decide what each agent can see, and a boundary
           chosen by hand (or by a model) is the one input nothing downstream can check.
  default  joins clean/<from>-<to>.json on id, enforces coverage, runs the loss detectors and
           renders the Markdown.

WHY THE LOSS DETECTORS EXIST AT ALL, and why they are cheap here. This route is the one place in
the repo where output and input are the SAME language and the SAME sentence order, so a lost line
is detectable by construction: every sentence id must come back, and what came back must still
contain the source's numbers and names. Route C cannot check any of this (a summary is ~200 words
against a whole transcript) and the translate seam cannot check names (the prompt PERMITS Russifying
them -- exactly why completeness.entity_loss was deleted on 2026-08-01, see DECISIONS). Same-language
cleaning does not carry that objection: a name stays a name, so the substring test is right about its
dominant input class. That reasoning does NOT travel back to completeness.py, which compares
across languages -- do not port these detectors there.

THE ENTITY DETECTOR IS LATIN-ONLY ON PURPOSE, INCLUDING ON RUSSIAN. Measured 2026-08-14 on
OAu3jkX8dK4 (a Russian talk on Unity, 1832 sentences): the shipped regex found 456 hits / 155
unique terms -- Addressables, Atlas, Auditor, Android -- because a Russian technical speaker says
the terms in English. A Cyrillic extension of the same pattern added 26 hits / 23 unique, of which
roughly half were ASR debris ("Гарбач", "Гиперхаге"). Widening it would trade a precise detector for
a noisy one, so it stays as it is and simply does not fire on Russian proper nouns.

WHAT IS FATAL AND WHAT IS NOT follows the repo rule (a MISSING artifact degrades, an INCONSISTENT
one raises, DECISIONS 2026-07-28):
  FATAL   a chunk file that is absent, unparseable, missing ids, carrying foreign ids, or holding
          a duplicate id. Each means the join cannot be trusted, and a transcript silently short a
          paragraph is precisely the defect this route cannot ship.
  WARN    every QUALITY signal -- short output, dropped numbers, dropped entities, a high share of
          emptied lines. These are judgement calls a human triages against the video; refusing to
          build over one would discard real agent work to enforce a preference.

AN EMPTY STRING IS A DECISION, A MISSING ID IS A BUG. A line that is pure filler ("So. Yeah.")
legitimately cleans to "" and is dropped from the Markdown while keeping its id in clean.json.
That is why the contract asks for every id back rather than for "the ids worth keeping": the two
failure modes look identical in a text file and could not be told apart afterwards.

Run with the .venv-asr python from the repo root:

    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\build_clean.py work\\<id> --plan
    .venv-asr\\Scripts\\python.exe -X utf8 scripts\\build_clean.py work\\<id>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# scripts/ is sys.path[0] when run as a file -- put the repo root first so `import overdub` resolves
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from overdub.workdir import WorkDir, replace_retry              # noqa: E402

# --- chunking -----------------------------------------------------------------
# Sentences per chunk. Chosen from the OUTPUT side, which is what actually constrains this task: a
# cleaning agent rewrites roughly as much as it reads, so ~80 transcript sentences land near 7k
# characters of output -- well inside the range where a model stays faithful, and far from the
# length where it starts summarising instead of cleaning. Smaller chunks would be safer still and
# cost proportionally more spawns (~8.5 s of latency each, measured on route C).
DEFAULT_CHUNK = 80
# How far the cut may slide from the target to land on a pause. A boundary inside a running
# sentence gives the next agent an opening it cannot parse, and gives the previous one a dangling
# tail -- both come back as clumsy prose no detector here can see.
_SLIDE = 0.15
# A trailing stub shorter than this fraction of the target is merged into the previous chunk
# instead of being spawned: a 4-sentence agent costs a full spawn to clean one paragraph.
_MIN_TAIL = 0.5


def plan_chunks(sentences: list[dict], target: int = DEFAULT_CHUNK) -> list[dict]:
    """Cut 0..n-1 into {from, to} ranges of about `target` sentences, breaking on the longest pause.

    Deterministic and pure: the same transcript always yields the same cut, which is what makes a
    re-run resumable per chunk. Ranges are INCLUSIVE on both ends and cover every id exactly once
    -- the assembler re-checks that rather than trusting it, because a planner bug and an agent
    that skipped a line are indistinguishable downstream.
    """
    n = len(sentences)
    if n == 0:
        return []
    target = max(1, target)
    slide = int(target * _SLIDE)
    chunks: list[dict] = []
    start = 0
    while start < n:
        end = min(start + target, n) - 1                  # inclusive, the un-slid default
        if end < n - 1 and slide:
            lo = max(start, end - slide)
            hi = min(n - 2, end + slide)                  # n-2: the cut sits BETWEEN i and i+1
            if lo <= hi:
                # widest silence in the window: the gap from this sentence's end to the next's start
                end = max(range(lo, hi + 1), key=lambda i: _gap_after(sentences, i))
        if n - 1 - end < target * _MIN_TAIL:              # absorb a stub tail rather than spawn for it
            end = n - 1
        chunks.append({"from": sentences[start]["id"], "to": sentences[end]["id"]})
        start = end + 1
    return chunks


def _gap_after(sentences: list[dict], i: int) -> float:
    """Silence between sentence i and i+1, or 0.0 when either timestamp is unusable."""
    try:
        gap = float(sentences[i + 1]["start"]) - float(sentences[i]["end"])
    except (IndexError, KeyError, TypeError, ValueError):
        return 0.0
    return max(gap, 0.0)


# --- language -----------------------------------------------------------------
# Route E cleans ENGLISH or RUSSIAN, a closed list (user decision 2026-08-14). It is detected from
# the transcript rather than read from cfg.source_lang, and that is not a shortcut: source_lang means
# "the language the dubbing pipeline EXPECTS", is "en" by hard constraint, and would force English
# onto a Russian video -- the same reasoning that made --transcribe-file ask the ASR instead
# (overdub/transcribefile.py). Detecting per video also lets one queue hold both.
_CYR_RE = re.compile(r"[а-яёА-ЯЁ]")
_LAT_RE = re.compile(r"[a-zA-Z]")
# Measured 2026-08-14 (Parakeet on both sides): a Russian technical talk sits at 96.0% Cyrillic among
# its alpha characters -- the other 4% is the English terms the speaker says in English -- while the
# English corpus on disk carries no Cyrillic at all. The wide band between these thresholds is where
# a transcript is neither, and the planner REFUSES there instead of guessing: an agent handed the
# wrong language block cleans against the wrong filler list, and nothing in the artifact says so.
#
# THE THRESHOLDS ARE ASYMMETRIC ON PURPOSE, and 0.70 is not a rounding of 0.5. Russian technical
# speech carries Latin script BY DEFAULT (the terms), so the Russian side needs room -- but only as
# much as the measurement asks for: 0.70 sits 26 points below the one Russian video on disk, and a
# transcript that is 30% Latin is no longer "Russian with terms", it is bilingual, which has no
# single filler list and is exactly what should be refused. English speech carries no Cyrillic at
# all in the corpus, so its side needs no such room.
_LANG_RU_MIN = 0.70
_LANG_EN_MAX = 0.05
LANGS = ("en", "ru")


def _cyr_share(text: str) -> float | None:
    """Cyrillic share of the alpha characters, or None when there are none to judge."""
    cyr, lat = len(_CYR_RE.findall(text)), len(_LAT_RE.findall(text))
    return cyr / (cyr + lat) if cyr + lat else None


def detect_lang(sentences: list[dict]) -> str | None:
    """'en' | 'ru' | None. None means "do not guess" and every caller treats it as such."""
    share = _cyr_share(" ".join(s.get("text", "") for s in sentences if isinstance(s, dict)))
    if share is None:
        return None
    if share >= _LANG_RU_MIN:
        return "ru"
    return "en" if share <= _LANG_EN_MAX else None


# --- loss detectors (same language in, same language out) ---------------------
_DIGITS_RE = re.compile(r"\d+")
# A capitalised token that is NOT sentence-initial: names, products, acronyms. The position filter
# is the whole precision of this detector -- every sentence starts with a capital, so counting
# those would drown the real entities in ordinary words.
_ENTITY_RE = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][A-Za-z0-9'’&.+-]{2,})\b", re.MULTILINE)
# Length ratios below which the pass stopped cleaning and started summarising. Filler removal on
# real speech lands near 0.85-0.95, so these sit well under the honest floor. HYPOTHESES, not
# measured constants -- say so out loud, and re-site them once a wave of real chunks exists.
_RATIO_WARN_CHUNK = 0.60
_RATIO_WARN_DOC = 0.65
# Share of lines cleaned to nothing that stops reading as filler removal.
_EMPTY_WARN = 0.25
# How far the Cyrillic share may move between source and cleaned text before the chunk reads as
# translated rather than cleaned (_script_drift). Wide because the two states it separates are not
# adjacent: honest cleaning moves it by a couple of points, a translation by ~0.9.
_DRIFT_MAX = 0.30
# How many examples a warning prints. Enough to recognise the defect, short of pasting the chunk.
_EXAMPLES = 5


def _missing_tokens(pattern: re.Pattern, src: str, out: str) -> list[str]:
    """Tokens matched in `src` that are absent from `out`, deduped, source order preserved."""
    have = out.casefold()
    return [t for t in dict.fromkeys(pattern.findall(src)) if t.casefold() not in have]


def _script_drift(src: str, out: str) -> bool:
    """True when a chunk came back in a different SCRIPT than it went in.

    This is the shape a TRANSLATION takes here, and it is the failure route E has to watch for now
    that both languages are live: the prompt forbids translating, an agent that ignores it produces
    fluent, complete, correctly-id'd text, and every other detector passes it. Ratio does not fire
    (a translation is about as long as its source), the id contract does not fire (nothing is
    missing), and the entity check is Latin-only, so a Russian chunk rendered into English scores
    BETTER on it.

    Script share is the cheap discriminator: cleaning removes filler in the source's own script, so
    it moves the share by a couple of points at most -- measured 2026-08-14, the 685 "вот" in
    OAu3jkX8dK4 are ~2k characters out of 146k -- while a translation inverts it. Symmetric on
    purpose: a Russian session translating an English transcript is the same defect mirrored.
    """
    a, b = _cyr_share(src), _cyr_share(out)
    return a is not None and b is not None and abs(a - b) >= _DRIFT_MAX


def _load_chunk(path: Path) -> dict[int, str]:
    """One agent's chunk file: [{id, text}] -> {id: text}. Exits on any shape it cannot trust."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        sys.exit(f"[FAIL] chunk {path.name} is missing -- its sub-agent did not finish; re-run "
                 f"that chunk alone (the others are on disk)")
    except ValueError as e:
        sys.exit(f"[FAIL] chunk {path.name} is not readable JSON ({e}) -- re-run that chunk")
    if not isinstance(raw, list):
        sys.exit(f"[FAIL] chunk {path.name} is a {type(raw).__name__}, expected a JSON list of "
                 f"{{id, text}} objects")
    out: dict[int, str] = {}
    for i, rec in enumerate(raw):
        if not isinstance(rec, dict):
            sys.exit(f"[FAIL] chunk {path.name} record {i} is {type(rec).__name__}, expected an "
                     f"object with 'id' and 'text'")
        try:
            sid = int(rec["id"])
        except (KeyError, TypeError, ValueError):
            sys.exit(f"[FAIL] chunk {path.name} record {i} has no usable 'id': {rec!r}")
        text = rec.get("text")
        if not isinstance(text, str):
            # An emptied line is legitimate and must be spelled "" -- a null would be laundered
            # into the literal "None" by str() and shipped as transcript text.
            sys.exit(f"[FAIL] chunk {path.name} id {sid}: 'text' is {type(text).__name__}, "
                     f"expected a string (use \"\" to drop a line)")
        if sid in out:
            sys.exit(f"[FAIL] chunk {path.name} has duplicate id {sid}")
        out[sid] = text.strip()
    return out


def join(work: WorkDir, chunks: list[dict]) -> tuple[list[dict], dict]:
    """Read every chunk file, verify id coverage, return (records, stats).

    Records carry the SOURCE beside the cleaned text (`src`), which costs a few percent of the
    file and buys the only thing that makes this route auditable later: the pair is on disk, so
    what the cleaning pass changed stays checkable long after the agents are gone.
    """
    sentences = json.loads(work.sentences.read_text(encoding="utf-8"))
    if not isinstance(sentences, list) or not sentences:
        sys.exit(f"[FAIL] {work.sentences} is not a non-empty sentence list")

    cleaned: dict[int, str] = {}
    owner: dict[int, str] = {}
    chunk_rows: list[dict] = []                          # {name, src, out} -- the texts, not just
                                                         # their lengths: the script check needs them
    for ch in chunks:
        name = f"{ch['from']}-{ch['to']}.json"
        part = _load_chunk(work.clean_dir / name)
        expected = [s["id"] for s in sentences if ch["from"] <= s["id"] <= ch["to"]]
        missing = [i for i in expected if i not in part]
        if missing:
            sys.exit(f"[FAIL] chunk {name} is missing {len(missing)} sentence(s): ids "
                     f"{missing[:20]}{' ...' if len(missing) > 20 else ''} -- an emptied line must "
                     f"come back as \"\", never as an absent id; re-run this chunk")
        extra = [i for i in part if i not in set(expected)]
        if extra:
            sys.exit(f"[FAIL] chunk {name} carries {len(extra)} id(s) outside its own range "
                     f"{ch['from']}..{ch['to']}: {extra[:20]} -- two agents would be writing one "
                     f"line; re-run this chunk")
        ids = set(expected)
        chunk_rows.append({"name": name,
                           "src": " ".join(s["text"] for s in sentences if s["id"] in ids),
                           "out": " ".join(part[i] for i in expected)})
        for i in expected:
            cleaned[i] = part[i]
            owner[i] = name

    uncovered = [s["id"] for s in sentences if s["id"] not in cleaned]
    if uncovered:
        # The planner and the chunk files disagree about the transcript: usually a stale plan
        # against a repaired sentences.json, which renumbered everything.
        sys.exit(f"[FAIL] {len(uncovered)} sentence(s) are in no chunk at all: ids "
                 f"{uncovered[:20]}{' ...' if len(uncovered) > 20 else ''} -- re-run --plan and "
                 f"the missing chunks (a --repair-asr pass renumbers every id)")

    records = [{"id": s["id"], "start": s["start"], "end": s["end"],
                "src": s["text"], "text": cleaned[s["id"]]} for s in sentences]
    src_all = " ".join(r["src"] for r in records)
    out_all = " ".join(r["text"] for r in records)
    stats = {
        "n_sentences": len(records),
        "n_empty": sum(1 for r in records if not r["text"]),
        "src_chars": len(src_all),
        "out_chars": len(out_all),
        "ratio": round(len(out_all) / max(len(src_all), 1), 3),
        "missing_numbers": _missing_tokens(_DIGITS_RE, src_all, out_all),
        "missing_entities": _missing_tokens(_ENTITY_RE, src_all, out_all),
        "chunks": [{"name": c["name"],
                    "ratio": round(len(c["out"]) / max(len(c["src"]), 1), 3),
                    "drift": _script_drift(c["src"], c["out"])} for c in chunk_rows],
        "owner": owner,
    }
    return records, stats


def report(stats: dict) -> None:
    """Print the quality signals. Every one of them is advisory -- see the module docstring."""
    for ch in stats["chunks"]:
        if ch.get("drift"):
            # First, and worded harder than the others: this one is not a judgement call. Cleaning
            # never changes script, so the chunk was translated and the text on the page is not the
            # text in the audio.
            print(f"[warn] chunk {ch['name']} came back in a DIFFERENT SCRIPT than its source -- "
                  f"that is a translation, not a cleaning pass; re-run this chunk alone")
        if ch["ratio"] < _RATIO_WARN_CHUNK:
            print(f"[warn] chunk {ch['name']} kept {ch['ratio']:.0%} of its source -- that is "
                  f"summarising, not cleaning; re-run this chunk alone")
    if stats["ratio"] < _RATIO_WARN_DOC:
        print(f"[warn] the document kept {stats['ratio']:.0%} of the transcript -- check it "
              f"against the video before publishing")
    empty_share = stats["n_empty"] / max(stats["n_sentences"], 1)
    if empty_share > _EMPTY_WARN:
        print(f"[warn] {stats['n_empty']}/{stats['n_sentences']} lines ({empty_share:.0%}) were "
              f"emptied -- filler removal does not reach that share; check a chunk by hand")
    if stats["missing_numbers"]:
        n = stats["missing_numbers"]
        print(f"[warn] {len(n)} number(s) in the transcript are absent from the clean text: "
              f"{', '.join(n[:_EXAMPLES])}{' ...' if len(n) > _EXAMPLES else ''}")
    if stats["missing_entities"]:
        e = stats["missing_entities"]
        # Deliberately noisier than the number check: ASR spells names inconsistently, so a name
        # the agent CORRECTED reads as a loss here. Triage hint, never a verdict.
        print(f"[warn] {len(e)} capitalised term(s) dropped: "
              f"{', '.join(e[:_EXAMPLES])}{' ...' if len(e) > _EXAMPLES else ''} "
              f"(a corrected spelling also lands here)")


# --- rendering ----------------------------------------------------------------
# Pause that ends a paragraph, in seconds. A HYPOTHESIS sited on ordinary speech rhythm, not a
# measured constant: a breath inside a thought runs ~0.3-0.6 s, while a topic change is usually
# longer. Re-site it once a wave of real transcripts exists.
_PARA_GAP = 1.0
# A paragraph this long is broken at the next sentence regardless of pauses -- a speaker who never
# pauses would otherwise produce one unreadable block per chunk.
_PARA_MAX_CHARS = 900
# Seconds between timecodes. They are navigation, so one per paragraph would be noise and one per
# chapter would be useless.
_STAMP_EVERY = 120.0


def _stamp(sec: float) -> str:
    """Seconds -> [M:SS] or [H:MM:SS] past the hour."""
    s = int(sec)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"[{h}:{m:02d}:{s:02d}]" if h else f"[{m}:{s:02d}]"


def paragraphs(records: list[dict]) -> list[dict]:
    """Group the non-empty cleaned lines into {start, text} paragraphs.

    The ONLY structural decision this route makes, and it is made here rather than by the agents
    on purpose: a paragraph break is a property of the audio (a pause), so it is knowable from the
    timestamps and does not need judgement. Leaving it to the agents would also make the breaks
    disagree across a chunk boundary, where neither agent can see the other's text.
    """
    out: list[dict] = []
    cur: list[str] = []
    cur_start = 0.0
    prev: dict | None = None
    for r in records:
        if not r["text"]:
            continue                                     # emptied line: dropped here, kept in clean.json
        brk = prev is not None and (
            _gap(prev, r) >= _PARA_GAP or sum(len(t) + 1 for t in cur) >= _PARA_MAX_CHARS)
        if brk and cur:
            out.append({"start": cur_start, "text": " ".join(cur)})
            cur = []
        if not cur:
            cur_start = float(r["start"])
        cur.append(r["text"])
        prev = r
    if cur:
        out.append({"start": cur_start, "text": " ".join(cur)})
    return out


def _gap(prev: dict, cur: dict) -> float:
    try:
        return max(float(cur["start"]) - float(prev["end"]), 0.0)
    except (KeyError, TypeError, ValueError):
        return 0.0


def render_md(doc: dict) -> str:
    """clean.json -> the deliverable. Metadata header, then timecoded paragraphs.

    Everything here is DERIVED: nothing in this file was
    written by an agent, so the Markdown and the JSON can never tell different stories.
    """
    head = [f"# {doc['title']}"] if doc.get("title") else ["# " + doc["video_id"]]
    meta = [v for v in (doc.get("channel"),
                        _iso(doc.get("upload_date")),
                        f"https://www.youtube.com/watch?v={doc['video_id']}") if v]
    head += ["", " · ".join(meta), ""]

    lines: list[str] = []
    last = None
    for p in doc["paragraphs"]:
        if last is None or p["start"] - last >= _STAMP_EVERY:
            lines += [f"**{_stamp(p['start'])}**", ""]
            last = p["start"]
        lines += [p["text"], ""]
    return "\n".join(head + lines)


def _iso(yyyymmdd: str | None) -> str | None:
    """20260731 -> 2026-07-31. None for anything else -- a date is never guessed."""
    if isinstance(yyyymmdd, str) and re.fullmatch(r"\d{8}", yyyymmdd):
        return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
    return None


def _load_json(path: Path):
    """Tolerant read: None on missing/torn -- the contract every optional-artifact reader here
    uses (runreport._load_json, build_scout._load_json)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, text: str) -> None:
    """tmp + replace: a torn write would leave a half-transcript that still looks like a file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    replace_retry(tmp, path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="build_clean",
        description="Route E: plan the chunk cut, or join the cleaned chunks into "
                    "clean.json + clean.md.")
    p.add_argument("workdir", type=Path, metavar="work/<id>")
    p.add_argument("--plan", action="store_true",
                   help="print the chunk cut as JSON and exit -- the workflow's `jobs` argument. "
                        "Never hand-write one: the assembler re-derives the same cut and fails on "
                        "any id it cannot account for.")
    p.add_argument("--chunk", type=int, default=DEFAULT_CHUNK, metavar="N",
                   help=f"sentences per chunk (default {DEFAULT_CHUNK}). The same value must be "
                        f"used for --plan and for the join, or the chunk file names will not match.")
    p.add_argument("--lang", choices=LANGS,
                   help="override the detected transcript language. Needed only when the detector "
                        "refuses (a transcript that is neither clearly English nor clearly "
                        "Russian); it does not change the chunk cut, only which cleaning rules the "
                        "sub-agents are given.")
    args = p.parse_args(argv)
    if not args.workdir.is_dir():
        p.error(f"work dir not found: {args.workdir}")

    work = WorkDir(args.workdir)
    sentences = _load_json(work.sentences)
    if not isinstance(sentences, list) or not sentences:
        sys.exit(f"[FAIL] {work.sentences} is missing or unreadable -- this workdir has no "
                 f"transcript; run the E1 command first")
    chunks = plan_chunks(sentences, args.chunk)
    lang = args.lang or detect_lang(sentences)

    if args.plan:
        # An unknown language is FATAL here and only here. The plan is what the sub-agents are
        # driven from, and a cleaner with no language block would fall back to its own judgement
        # about what a filler is -- the one decision this route never delegates to a model.
        if lang is None:
            sys.exit(f"[FAIL] {work.sentences} is neither clearly English nor clearly Russian "
                     f"(route E cleans those two) -- if you know what it is, re-run with "
                     f"--lang en|ru; otherwise this transcript is not for this route")
        print(json.dumps({"video_id": work.root.name, "n_sentences": len(sentences),
                          "lang": lang, "chunks": chunks}, ensure_ascii=False))
        return 0

    records, stats = join(work, chunks)
    info = _load_json(work.info_json)
    info = info if isinstance(info, dict) else {}
    doc = {
        "video_id": work.root.name,
        # DEGRADES rather than raises, unlike --plan above: by join time the agents have already
        # run, and refusing here would discard finished work over a signal that only decides which
        # advisory checks are worth printing (a MISSING artifact degrades, DECISIONS 2026-07-28).
        "lang": lang,
        "title": info.get("title") if isinstance(info.get("title"), str) else None,
        "channel": next((info[k] for k in ("channel", "uploader")
                         if isinstance(info.get(k), str) and info[k].strip()), None),
        "upload_date": info.get("upload_date"),
        "n_sentences": stats["n_sentences"],
        "n_empty": stats["n_empty"],
        "ratio": stats["ratio"],
        "sentences": records,
        "paragraphs": paragraphs(records),
    }
    _write(work.clean_doc, json.dumps(doc, ensure_ascii=False, indent=2))
    _write(work.clean_md, render_md(doc))

    report(stats)
    print(f"[clean] {work.clean_md}  {lang or 'lang?'}  {stats['n_sentences']} sentences -> "
          f"{len(doc['paragraphs'])} paragraphs  {stats['out_chars']} chars "
          f"({stats['ratio']:.0%} of source, {stats['n_empty']} emptied)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
