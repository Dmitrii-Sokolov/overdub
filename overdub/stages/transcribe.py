"""Transcribe stage: faster-whisper large-v3 → word timestamps → sentences.json.

Word-level sentence resegmentation (design: transcribe-design workflow, see DECISIONS):
boundaries land ON a word by construction, so there is no fuzzy char→word remapping.
Whisper segment ends are carried as a `seg_end` pause-prior, used ONLY to pick a good
cut point when an overlong sentence must be split. Pure/deterministic — no RNG.

Four passes: flatten (robustness) → sentence split (guarded) → duration-aware overlong
split (pause > clause > midpoint) → emit. The sentence is the unit of translation,
synthesis and timing sync downstream.
"""

from __future__ import annotations

import gc
import json
import re
from dataclasses import dataclass

from ..asr import load_whisper
from ..pipeline import Context

# ---- tunables (calibrate against Silero eugene comfortable length in QA) -----
MAX_SEC = 15.0          # audio-span cap before an overlong sentence is clause-split
MAX_CHARS = 240         # char cap before clause-split
HALLUC_RUN = 4          # >=N identical consecutive tokens => whisper hallucination
MIN_WORD_DUR = 0.02     # floor for a synthesized pseudo-word duration

TERMINATORS = ".!?…"
_OPEN = set("\"'“‘«([")
_WRAP = "\"'“”‘’«»()[]{}"

# Abbreviations ending in '.' that do NOT end a sentence (dot-stripped, lowercased).
_ABBREV = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "rev", "hon", "pres",
    "etc", "eg", "ie", "cf", "vs", "al", "viz", "approx", "ca", "dept",
    "no", "vol", "fig", "pp", "ed", "est", "inc", "ltd", "co", "corp",
    "gen", "col", "capt", "sgt", "lt", "cmdr", "adm", "maj", "sen", "gov",
    "ave", "blvd", "rd", "mt", "ft", "us", "uk", "un", "eu", "phd", "ba", "ma",
    "am", "pm", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept",
    "oct", "nov", "dec",
}
# Clause-boundary conjunctions, used ONLY when splitting an overlong sentence.
_CONJ = {
    "and", "but", "or", "nor", "so", "yet", "because", "although", "though",
    "while", "whereas", "which", "that", "who", "when", "where", "since",
    "if", "as", "after", "before", "however", "therefore",
}
# Bare function words we avoid stranding at the LEFT end of an overlong-split fragment.
_STOP = {"the", "a", "an", "and", "or", "nor", "but", "so", "to", "of",
         "in", "for", "with", "at", "by", "as"}
_ALNUM = re.compile(r"[a-z0-9']+")


@dataclass
class W:
    text: str          # trimmed token (whisper's leading space removed)
    start: float
    end: float
    seg_end: bool      # True if last word of its whisper segment (a pause prior)


def _f(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _norm(text: str) -> str:
    return re.sub(r"\W", "", text.lower())


# ---- 1. robustness pre-pass: lazy generator → clean, monotonic word list -----
def flatten(segments) -> list[W]:
    flat: list[W] = []
    prev_end = 0.0
    for seg in segments:
        words = getattr(seg, "words", None)
        if not words:                                   # .words is None/empty
            txt = (getattr(seg, "text", "") or "").strip()
            if not txt:
                continue
            s = max(_f(getattr(seg, "start", None), prev_end), prev_end)
            e = max(_f(getattr(seg, "end", None), s), s + MIN_WORD_DUR)
            flat.append(W(txt, s, e, seg_end=True))
            prev_end = e
            continue
        n = len(words)
        for i, w in enumerate(words):
            tok = (getattr(w, "word", "") or "").strip()
            if not tok:                                 # empty/whitespace word
                continue
            s = max(_f(getattr(w, "start", None), prev_end), prev_end)  # clamp monotone
            e = max(_f(getattr(w, "end", None), s), s + MIN_WORD_DUR)   # never zero-length (would /0 in atempo)
            flat.append(W(tok, s, e, seg_end=(i == n - 1)))
            prev_end = e
    return _dehallucinate(flat)


def _dehallucinate(flat: list[W]) -> list[W]:
    """Collapse a run of identical consecutive tokens into one, absorbing the run's
    time span. Long runs (>=HALLUC_RUN) are always whisper silence-loops. Short 2-3x
    runs collapse ONLY with a strong artifact signal — a near-zero-duration duplicate
    ("and and…89.36-89.36"), or byte-identical tokens carrying a terminator
    ("situations. situations.") — so legitimate "that that" / "go. Go" survive."""
    out: list[W] = []
    i, n = 0, len(flat)
    while i < n:
        j = i
        key = _norm(flat[i].text)
        while key and j + 1 < n and _norm(flat[j + 1].text) == key:
            j += 1
        run = flat[i:j + 1]
        collapse = False
        if key and len(run) >= HALLUC_RUN:
            collapse = True
        elif key and len(run) >= 2:
            near_zero = any((w.end - w.start) < MIN_WORD_DUR for w in run)
            identical = len({w.text for w in run}) == 1
            has_term = _core(flat[i].text)[-1:] in TERMINATORS
            collapse = near_zero or (identical and has_term)
        if collapse:
            out.append(W(flat[i].text, flat[i].start, flat[j].end, flat[j].seg_end))
        else:
            out.extend(run)
        i = j + 1
    return out


# ---- 2. sentence boundary decision (word-level, guarded) ---------------------
def _core(tok: str) -> str:
    return tok.strip().strip(_WRAP)


def _first_char(w: "W | None") -> str:
    if w is None:
        return ""
    c = _core(w.text)
    return c[0] if c else ""


def _ends_sentence(cur: W, nxt: "W | None") -> bool:
    core = _core(cur.text)
    if not core or core[-1] not in TERMINATORS:
        return False
    stripped = core.rstrip(TERMINATORS)
    next_char = _first_char(nxt)

    if core.endswith("…") or core.endswith("..."):      # ellipsis: split only if a new sentence starts
        return nxt is None or next_char.isupper() or next_char in _OPEN

    if core[-1] == ".":
        norm = stripped.replace(".", "").lower()
        if norm in _ABBREV:                             # Dr.  etc.  e.g.  U.S.
            return False
        if len(norm) == 1 and norm.isalpha():           # initial "J."
            return False
        if nxt is None:
            return True
        return next_char.isupper() or next_char.isdigit() or next_char in _OPEN

    return True                                         # '!' / '?' : strong terminators


# ---- 3. duration-aware overlong split (pause > clause > hard midpoint) --------
def _too_long(flat: list[W], lo: int, hi: int) -> bool:
    dur = flat[hi].end - flat[lo].start
    chars = sum(len(flat[k].text) + 1 for k in range(lo, hi + 1))
    return dur > MAX_SEC or chars > MAX_CHARS


def _bare(w: W) -> str:
    """First alnum token of a word, lowercased (e.g. 'The,' -> 'the'); '' if none."""
    m = _ALNUM.match(_core(w.text).lower())
    return m.group(0) if m else ""


def _leading_conj(w: W) -> bool:
    return _bare(w) in _CONJ


def _split_overlong(flat: list[W], lo: int, hi: int) -> list[tuple[int, int]]:
    if hi - lo < 3 or not _too_long(flat, lo, hi):
        return [(lo, hi)]
    mid = flat[lo].start + (flat[hi].end - flat[lo].start) / 2.0

    def nearest(cands: list[int]) -> "int | None":
        return min(cands, key=lambda k: abs(flat[k].end - mid)) if cands else None

    interior = list(range(lo, hi))                      # cut AFTER word k (lo..hi-1)
    # (1) real speaker pause, but never one that strands a bare function word on the left;
    # if every pause would, skip to clause/midpoint rather than cut on 'the'/'to'/'and'.
    cut = nearest([k for k in interior if flat[k].seg_end and _bare(flat[k]) not in _STOP])
    if cut is None:                                                  # (2) clause seam
        cut = nearest([k for k in interior
                       if _core(flat[k].text)[-1:] in {",", ";", ":"}
                       or _leading_conj(flat[k + 1])])
    if cut is None:                                                  # (3) hard midpoint
        cut = min(interior, key=lambda k: abs(flat[k].end - mid))
    return _split_overlong(flat, lo, cut) + _split_overlong(flat, cut + 1, hi)


# ---- 4. assemble sentence dicts ----------------------------------------------
def resegment(flat: list[W]) -> list[dict]:
    """Clean word list → list of sentence dicts. Pure, deterministic, no I/O."""
    if not flat:
        return []
    ranges: list[tuple[int, int]] = []
    start = 0
    for i, w in enumerate(flat):
        nxt = flat[i + 1] if i + 1 < len(flat) else None
        if _ends_sentence(w, nxt):
            ranges.append((start, i))
            start = i + 1
    if start < len(flat):                               # unterminated tail
        ranges.append((start, len(flat) - 1))

    out: list[dict] = []
    for lo, hi in ranges:
        for a, b in _split_overlong(flat, lo, hi):
            text = " ".join(flat[k].text for k in range(a, b + 1)).strip()
            if not text:
                continue
            out.append({
                "id": len(out),                         # assigned last → always contiguous
                "text": text,
                "start": round(flat[a].start, 3),
                "end": round(flat[b].end, 3),
            })
    return out


class TranscribeStage:
    name = "transcribe"

    def done(self, ctx: Context) -> bool:
        return ctx.work.sentences.exists()

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        model = load_whisper(cfg.whisper_model, cfg.whisper_device, cfg.whisper_compute_type)
        try:
            segments, _info = model.transcribe(
                str(ctx.work.source_audio),
                language=cfg.source_lang, beam_size=5,
                word_timestamps=True, vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                condition_on_previous_text=False,
            )
            flat = flatten(segments)                    # consumes the lazy generator
        finally:
            del model
            gc.collect()
            try:
                import torch
                torch.cuda.empty_cache()
            except Exception:
                pass

        # raw words persisted so resegmentation can be re-tuned without re-running ASR
        ctx.work.words.write_text(
            json.dumps(
                [{"text": w.text, "start": w.start, "end": w.end, "seg_end": w.seg_end} for w in flat],
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        sentences = resegment(flat)
        ctx.work.sentences.write_text(
            json.dumps(sentences, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"       {len(flat)} words → {len(sentences)} sentences")
