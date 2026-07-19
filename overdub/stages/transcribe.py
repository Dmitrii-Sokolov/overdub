"""Transcribe stage: faster-whisper large-v3 → word timestamps → sentences.json.

Word-level sentence resegmentation (design: transcribe-design workflow, see DECISIONS):
boundaries land ON a word by construction, so there is no fuzzy char→word remapping.
Whisper segment ends are carried as `seg_end`, a VAD/window artifact — NOT a pause (most
carry a 0.000 s gap to the next word). It is a pause prior ONLY together with real silence
(MIN_PAUSE_SEC, overlong-split branch 1), and a boundary signal after a period. Pure and
deterministic — no RNG.

Whisper runs with condition_on_previous_text=True (cfg.whisper_condition_on_previous) so it
PUNCTUATES from context: without it, long stretches came back as one 60-206 s terminator-free
block that the overlong-splitter had to bisect mid-phrase — the ROOT of the "period
mid-sentence" class (DECISIONS 2026-07-17). With it, real sentence boundaries carry real
periods and the overlong-splitter rarely fires. Measured safe (no repetition loop) on a music
video; flip the flag off for a source that makes whisper loop.

That flip is now automatic: TranscribeStage._guard measures the share of words flatten had to
stamp onto the MIN_WORD_DUR floor (floor_run_ratio — the signature of a collapsed alignment,
which is what the repetition loop leaves behind) and re-runs once with the flag off when it
exceeds cfg.transcribe_floor_run_max, keeping the retry only if it at least halves the ratio.
The guard is cause-based: downstream harm depends on the Russian text and on unit grouping,
neither of which exists yet at this stage.

Four passes: flatten (robustness) → sentence split (guarded) → duration-aware overlong
split (pause > clause > midpoint) → emit. The sentence is the unit of translation,
synthesis and timing sync downstream.
"""

from __future__ import annotations

import gc
import json
import re
import sys
from dataclasses import dataclass

from ..asr import load_whisper
from ..pipeline import Context

# ---- tunables (calibrate against Silero eugene comfortable length in QA) -----
MAX_SEC = 15.0          # audio-span cap before an overlong sentence is clause-split
MAX_CHARS = 240         # char cap before clause-split
HALLUC_RUN = 4          # >=N identical consecutive tokens => whisper hallucination
MIN_WORD_DUR = 0.02     # floor for a synthesized pseudo-word duration
MIN_SENT_CHARS = 15     # EN chars below which a sentence is "ultra-short" and merged into a
                        # neighbor: F5 sizes its duration canvas by text byte count, so tiny
                        # texts garble/echo the reference tail (the id43 "Решениям." class)
MERGE_GAP_MAX = 0.6     # never merge across a pause longer than this (seconds) — the gap
                        # becomes continuous synthesized speech, i.e. deliberate sync drift
MERGE_TOTAL_GAP_MAX = 1.5   # cap on the CUMULATIVE silence a chain of merges may absorb
                            # into one sentence (bounds worst-case drift of its tail words)
MIN_PAUSE_SEC = 0.20    # a seg_end is a REAL pause only if the next word starts this much
                        # later: whisper ends segments mid-phrase (73% of corpus seg_ends
                        # have a 0.000 s gap), so seg_end alone is a VAD artifact

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
# Words an overlong sentence may be cut BEFORE (branch 2). ONLY unambiguous clause openers:
# coordinating conjunctions + subordinators that cannot double as a determiner / preposition /
# pronoun. "that/which/who/as/if/when/where/before/after/since/while" are DELIBERATELY absent —
# once branch 1 is gap-gated this next-word test goes from ~11 to ~110 cuts, and cutting before
# those severs a verb from its object ("feel | that satisfaction") or a relative clause from its
# head, reproducing the id150 standalone-fragment cascade the whole cluster exists to kill.
_CUT_BEFORE = {
    "and", "but", "or", "nor", "so", "yet",
    "because", "although", "though", "whereas", "however", "therefore",
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


def floor_run_ratio(flat: list[W]) -> tuple[float, int]:
    """(share of words sitting on the MIN_WORD_DUR floor in a chain, longest such run).

    Signature of a COLLAPSED whisper word alignment, not of fast speech: flatten's monotone
    clamp sets start=prev_end whenever whisper hands back a start at or before the previous
    word's end, and the floor then stretches the word to exactly MIN_WORD_DUR. One such word
    is ordinary (whisper stamps on a 20 ms grid); a CHAIN of them means whisper returned no
    usable timing for that stretch and flatten manufactured a plausible-looking one. Only
    chained hits count — an isolated grid-aligned short word is not evidence.

    Measured on the 12-video AI-Fluency batch: healthy sources ≤4.1%, the repetition-looping
    source 9.1%. The ratio separates; the longest run does NOT (a healthy 128-sentence video
    also reached 17), so the caller gates on the ratio and reports the run only as context.
    """
    if not flat:
        return 0.0, 0
    hits = longest = cur = 0
    for i, w in enumerate(flat):
        on_floor = abs((w.end - w.start) - MIN_WORD_DUR) < 1e-6
        chained = i > 0 and abs(w.start - flat[i - 1].end) < 1e-6
        if on_floor and chained:
            hits += 1
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return hits / len(flat), longest


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
        if next_char.isupper() or next_char.isdigit() or next_char in _OPEN:
            return True
        # whisper emitted a period AND ended its segment: a real boundary even though it
        # lowercased the next word ("...isn't just a tool. it's a technology...")
        return cur.seg_end

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


def _gap_after(flat: list[W], k: int) -> float:
    return flat[k + 1].start - flat[k].end      # k < hi <= len-1 by caller construction


def _ok_cut(flat: list[W], k: int) -> bool:
    """Never end a fragment on a bare function word ('...games at' / '...see how the'), and
    never cut INSIDE a hyphenated compound whisper split into two tokens ('shake' | '-up')."""
    return _bare(flat[k]) not in _STOP and not flat[k + 1].text.lstrip().startswith("-")


def _leading_conj(w: W) -> bool:
    return _bare(w) in _CUT_BEFORE


def _split_overlong(flat: list[W], lo: int, hi: int) -> list[tuple[int, int]]:
    if hi - lo < 3 or not _too_long(flat, lo, hi):
        return [(lo, hi)]
    mid = flat[lo].start + (flat[hi].end - flat[lo].start) / 2.0

    def nearest(cands: list[int]) -> "int | None":
        return min(cands, key=lambda k: abs(flat[k].end - mid)) if cands else None

    interior = list(range(lo, hi))                      # cut AFTER word k (lo..hi-1)
    # (1) a REAL speaker pause: seg_end ALONE is a whisper VAD artifact (most land mid-phrase
    # with a 0.000 s gap — the id149/id188 ear bugs), so require measurable silence. No branch
    # may strand a bare function word on the left.
    cut = nearest([k for k in interior if flat[k].seg_end
                   and _gap_after(flat, k) >= MIN_PAUSE_SEC and _ok_cut(flat, k)])
    if cut is None:                                                  # (2) clause seam
        cut = nearest([k for k in interior
                       if (_core(flat[k].text)[-1:] in {",", ";", ":"}
                           or _leading_conj(flat[k + 1])) and _ok_cut(flat, k)])
    if cut is None:                                                  # (3) hard midpoint:
        # _ok_cut is a sort PREFERENCE here, never a filter — branch (3) must always cut
        cut = min(interior, key=lambda k: (not _ok_cut(flat, k), abs(flat[k].end - mid)))
    return _split_overlong(flat, lo, cut) + _split_overlong(flat, cut + 1, hi)


# ---- 3b. ultra-short sentence merge (F5 short-text failure class) --------------
def _chars(flat: list[W], a: int, b: int) -> int:
    return sum(len(flat[k].text) + 1 for k in range(a, b + 1)) - 1


def _merge_short(flat: list[W], spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge ultra-short sentences (< MIN_SENT_CHARS) into an adjacent one. Neighbor with
    the smaller inter-sentence gap wins, tie → previous (short fragments usually append to
    the preceding thought); a merge never crosses MERGE_GAP_MAX, never violates _too_long
    (the overlong splitter's work must not be undone), and a CHAIN of merges never absorbs
    more than MERGE_TOTAL_GAP_MAX of internal silence in one sentence (absorbed gaps become
    continuous synthesized speech, i.e. cumulative sync drift). Isolated shorts across long
    pauses stay — the synthesize reseed-retry is their net. Fixpoint: a merged result that
    is still short is re-examined, so chains of fragments collapse fully."""
    spans = list(spans)
    absorbed = [0.0] * len(spans)                        # internal gap already swallowed per span
    i = 0
    while i < len(spans):
        a, b = spans[i]
        if _chars(flat, a, b) >= MIN_SENT_CHARS:
            i += 1
            continue
        gap_prev = flat[a].start - flat[spans[i - 1][1]].end if i > 0 else None
        gap_next = flat[spans[i + 1][0]].start - flat[b].end if i + 1 < len(spans) else None
        ok_prev = (gap_prev is not None and gap_prev <= MERGE_GAP_MAX
                   and absorbed[i - 1] + gap_prev + absorbed[i] <= MERGE_TOTAL_GAP_MAX
                   and not _too_long(flat, spans[i - 1][0], b))
        ok_next = (gap_next is not None and gap_next <= MERGE_GAP_MAX
                   and absorbed[i] + gap_next + absorbed[i + 1] <= MERGE_TOTAL_GAP_MAX
                   and not _too_long(flat, a, spans[i + 1][1]))
        if ok_prev and ok_next:                          # both fit: smaller gap, tie → prev
            ok_next = gap_next < gap_prev
            ok_prev = not ok_next
        if ok_prev:
            spans[i - 1] = (spans[i - 1][0], b)
            absorbed[i - 1] += gap_prev + absorbed[i]
            del spans[i], absorbed[i]
            i -= 1                                       # re-examine the merged result
        elif ok_next:
            spans[i] = (a, spans[i + 1][1])
            absorbed[i] += gap_next + absorbed[i + 1]
            del spans[i + 1], absorbed[i + 1]            # stay at i: re-examine
        else:
            i += 1
    return spans


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

    spans = [ab for lo, hi in ranges for ab in _split_overlong(flat, lo, hi)]
    spans = _merge_short(flat, spans)

    out: list[dict] = []
    for a, b in spans:
        text = " ".join(flat[k].text for k in range(a, b + 1)).strip()
        if not text:
            continue
        out.append({
            "id": len(out),                             # assigned last → always contiguous
            "text": text,
            "start": round(flat[a].start, 3),
            "end": round(flat[b].end, 3),
        })
    return out


class TranscribeStage:
    name = "transcribe"

    def done(self, ctx: Context) -> bool:
        return ctx.work.sentences.exists()

    def _guard(self, ctx: Context, asr, flat: list[W]) -> list[W]:
        """Re-run once with context feedback OFF when the word alignment looks collapsed.

        Whisper's repetition loop is fed by condition_on_previous_text, and it takes the word
        alignment down with it: the run comes back with a chain of floor-stamped words that
        flatten had to manufacture (see floor_run_ratio). Those fake timings are not cosmetic —
        synthesize hands each unit's span to F5 as a native-speed target, so a collapsed stretch
        makes the engine compress until it drops words outright, and assemble tops the rest up
        with atempo. Observed on 4szRHy_CT7s: one slot at 294 char/s, atempo x8.79.

        Cause-based on purpose. The HARM cannot be predicted here (it depends on the Russian
        text, which does not exist until translate, and on unit grouping absorbing free gaps —
        measured: a sentence at 178 char/s still finished at speed x1.37 because the gap after
        it swallowed the spill). So this guards the data defect, not its downstream effect.

        The retry is kept only if it at least HALVES the ratio: the flag is on for a reason
        (punctuation — DECISIONS 2026-07-17), so a marginal win does not justify losing it.
        """
        limit = ctx.cfg.transcribe_floor_run_max
        if limit <= 0 or not ctx.cfg.whisper_condition_on_previous:
            return flat
        ratio, longest = floor_run_ratio(flat)
        if ratio <= limit:
            return flat

        print(f"       [guard] word alignment looks collapsed: {ratio:.1%} of words on the "
              f"{MIN_WORD_DUR}s floor (longest chain {longest}, limit {limit:.1%}) — "
              f"re-running with condition_on_previous_text=False", file=sys.stderr)
        alt = asr(False)
        alt_ratio, alt_longest = floor_run_ratio(alt)
        if alt_ratio <= ratio / 2:
            print(f"       [guard] retry accepted: {ratio:.1%} → {alt_ratio:.1%} "
                  f"(longest chain {longest} → {alt_longest})", file=sys.stderr)
            return alt
        print(f"       [guard] retry REJECTED: {ratio:.1%} → {alt_ratio:.1%} is not a halving — "
              f"keeping the original. Timings in this video are suspect; check the run report "
              f"for speed offenders.", file=sys.stderr)
        return flat

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        model = load_whisper(cfg.whisper_model, cfg.whisper_device, cfg.whisper_compute_type)
        try:
            def asr(condition_on_previous: bool) -> list[W]:
                segments, _info = model.transcribe(
                    str(ctx.work.source_audio),
                    language=cfg.source_lang, beam_size=5,
                    word_timestamps=True, vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    condition_on_previous_text=condition_on_previous,
                )
                return flatten(segments)                # consumes the lazy generator

            flat = asr(cfg.whisper_condition_on_previous)
            flat = self._guard(ctx, asr, flat)
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
