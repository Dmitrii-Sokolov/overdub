"""--repair-asr: isolated-window re-ASR — clip the defect window, read it twice, accept only on agreement, merge and renumber.

Proven manually 7/7 on the AI-Fluency batch (DECISIONS 2026-07-19): re-transcribing the WHOLE
file fixed 1 of 4 attempts, while clipping the defect window out of source.wav and re-reading
that clip alone fixed 7 of 7. A clipped 8-18 s window has no prior context for whisper to loop
on, which is the entire mechanism — so the stage's own _guard (a full-file halving rule) is
NEVER applied here.

Three rules carry the correctness of this mode:

DELETE, DO NOT INVENT. Every replacement text is the window's OWN ASR output. Nothing is
paraphrased, stitched from neighbours or hand-repaired; a window whose two readings disagree is
left exactly as it was and reported loudly.

IDS STAY CONTIGUOUS 0..n-1. An accepted run of k sentences is replaced by the window's m
sentences and the WHOLE file is renumbered. completeness.duplicate_adjacent and
completeness.implausible_rate both key on list POSITION, so a renumber miss lands every later
flag on the wrong sentence.

words.json IS NEVER REWRITTEN — by rule, not by omission. It is the raw record of what the ASR
actually did, and asr.floor_ratio must keep reporting that this file had a collapse.

This is NOT a Stage. It mutates artifacts outside the pipeline and must never re-run a
downstream stage itself (user decision D1): it rewrites sentences.json and DELETES exactly the
artifacts downstream of it, so the next ordinary run redoes translate → synthesize → verify →
assemble → mux honestly. TranscribeStage.done() still returns True afterwards, so no full ASR
pass is redone — but it is no longer a bare existence check: it also reads the asr_key stamp and
RAISES on a model/compute-type/beam mismatch. Hence the two provenance duties this module now
carries (check_decode_config, stamp_repaired): running no stage means nothing else can do them,
and invalidate_downstream deliberately preserves timings.json.

The gate proves STABILITY, not correctness: two identical readings of the same clip mean whisper
is no longer guessing, not that it heard right. Ears remain the final authority.

Importing norm_text/resegment across the module boundary is deliberate and carries the same
license scripts/build_translation.py states for _is_bad: a repaired sentence must be
byte-identical in shape and in sameness-definition to one the stage produced, so both sides
share one body rather than growing a second copy that drifts.

Resumability: a partial batch resumes by re-running the same command. Repair is per-video atomic
(sentences.json flips, then invalidation), and `auto` is idempotent because a repaired video's
detectors go silent (measured 2026-07-19: rate max 246 → 39.36, dup fires 0). Explicit-id mode
is NOT idempotent — the splice renumbered every later id.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from . import completeness
from .pipeline import Context
from .stages.transcribe import W, _stamped_key, norm_text, resegment, transcribe_words
from .workdir import WorkDir

CLIP_PAD_SEC = 0.25   # Pad the clip into the SILENCE around the window, never into a
                      # neighbour's speech. Exists because vad_filter=True with
                      # vad_parameters=dict(min_silence_duration_ms=500) are hardcoded
                      # literals in the transcribe() call: a clip cut flush against speech
                      # risks VAD eating an edge word. Not a Config key — it is a property
                      # of that hardcoded VAD setting, not an operator knob.

_CLIP_NAME = "_repair_window.wav"


# --- data types ---------------------------------------------------------------
@dataclass
class Window:
    lo: int                  # first ORIGINAL sentence id covered, inclusive
    hi: int                  # last  ORIGINAL sentence id covered, inclusive
    seeds: list[int]         # detector-hit / operator-named ids that seeded it
    reasons: list[str]       # sorted unique: "rate_implausible" | "dup_adjacent" | "explicit"
    t0: float                # padded clip start, absolute seconds, 3 dp
    t1: float                # padded clip end,   absolute seconds, 3 dp


@dataclass
class WindowResult:
    window: Window
    accepted: bool
    reason: str              # "identical" when accepted; else "readings differ" |
                             # "empty reading" | "empty span" | "asr error: <Type>: <msg>"
    old_texts: list[str]     # every text the window covers, in id order
    new_texts: list[str] = field(default_factory=list)   # accepted reading's texts ([] on reject)
    alt_texts: list[str] = field(default_factory=list)   # on a "readings differ" reject: the two
                                                         # raw readings [cond=False, cond=True],
                                                         # which is what the printed diff needs
    new_sents: list[dict] = field(default_factory=list)  # accepted reading's sentence dicts
    unchanged: bool = False  # accepted, but byte-identical to old_texts
    collateral: list[int] = field(default_factory=list)  # NON-seed ids the accepted reading
                                                         # rewrote — see _collateral_ids


# --- loading and the contiguity guard -----------------------------------------
def load_sentences(work: WorkDir) -> list[dict]:
    """sentences.json → list of {id,text,start,end}. RuntimeError, never assert: the
    never-drop invariants must survive python -O."""
    if not work.sentences.exists():
        raise RuntimeError(f"{work.sentences} not found — run transcribe first")
    sents = json.loads(work.sentences.read_text(encoding="utf-8"))
    if not isinstance(sents, list) or not sents:
        raise RuntimeError(f"{work.sentences} is not a non-empty sentence list")
    if [s.get("id") for s in sents] != list(range(len(sents))):
        raise RuntimeError(
            f"{work.sentences}: ids are not contiguous 0..{len(sents) - 1} — both detectors "
            f"key on list POSITION, so a desync lands every flag on the wrong sentence")
    return sents


# --- seeding ------------------------------------------------------------------
def seed_ids_from_detectors(sentences: list[dict]) -> dict[int, list[str]]:
    """{id: [reason, ...]} from the two ASR detectors, read off sentences.json ALONE.

    verify.py runs these on translation.json's src_en; that field is copied VERBATIM from
    sentences.json["text"] (translate.py keys resume on the equality, build_translation.py
    assigns it). So this is a field rename, not a second detector, and completeness.py is not
    touched. Repair must work before translate has ever run — `--repair-asr auto --batch` on a
    freshly transcribed queue is the whole point.
    """
    texts = [s.get("text") or "" for s in sentences]
    durs = [(s.get("end") or 0) - (s.get("start") or 0) for s in sentences]
    dups = completeness.duplicate_adjacent(texts)
    rates = completeness.implausible_rate(texts, durs)
    seeds: dict[int, list[str]] = {}
    for i in sorted(set(dups) | set(rates)):
        r: list[str] = []
        if i in dups:
            r.append("dup_adjacent")            # both pair members are already keys
        if i in rates:
            r.append("rate_implausible")
        seeds[i] = r
    return seeds


def explicit_seeds(ids: list[int], n: int) -> dict[int, list[str]]:
    """Operator-named ids → seeds. An id outside the file aborts the video WHOLE — no partial
    repair of a partly-valid id set, because a typo means the operator was reading a different
    file and guessing which ids they meant is the silent-failure class this repo forbids."""
    for i in ids:
        if not 0 <= i < n:
            raise RuntimeError(f"sentence id {i} out of range 0..{n - 1}")
    return {i: ["explicit"] for i in ids}


# --- window derivation (pure, no I/O) -----------------------------------------
def _runs(ids: list[int]) -> list[tuple[int, int]]:
    """Sorted unique ids → maximal runs of consecutive integers. [23,24,25,40] → [(23,25),(40,40)]"""
    out: list[tuple[int, int]] = []
    for i in sorted(set(ids)):
        if out and i == out[-1][1] + 1:
            out[-1] = (out[-1][0], i)
        else:
            out.append((i, i))
    return out


def _span(sentences: list[dict], lo: int, hi: int) -> float:
    return (sentences[hi].get("end") or 0.0) - (sentences[lo].get("start") or 0.0)


def widen(sentences: list[dict], lo: int, hi: int, *, min_sec: float) -> tuple[int, int]:
    """Grow a seed run outward by whole SENTENCES until its audio span reaches min_sec.

    Why sentences and not seconds: whatever run the widened window covers is what gets
    replaced by the window's reading, so the replaced id range and the audio window must be
    the same object. A window that ended mid-sentence would put a neighbour's words into a
    reading that then overwrites sentences we are not replacing — inventing a duplicate.

    A collapsed sentence's OWN span is bogus (0.28 s for 69 chars), which is exactly why the
    widening is driven by the SURROUNDING sentences' real timings.

    Alternates LEFT-first so the window is centred on the defect and the rule is deterministic
    (a test pins the exact id range). A run that already spans min_sec is returned untouched
    (the loop never runs), and one step may overshoot it when a neighbour is long: reaching
    min_sec is what makes the clip transcribable, and the actual span is printed. A file
    shorter than min_sec yields every sentence and is repaired anyway — refusing would make
    short videos unrepairable, and the acceptance gate, not the length, is what decides
    correctness.

    There is deliberately NO upper bound parameter. A `repair_window_max_sec` key existed
    until it was measured to be inert (2026-07-20 review): its only use was an early return on
    `span >= max_sec`, which for any max_sec >= min_sec can never change the result the
    `span < min_sec` loop below would give anyway, and for max_sec < min_sec silently returned
    a window SHORTER than the 8-18 s band DECISIONS 2026-07-19 proved the method in. An
    operator knob that cannot change any window is worse than no knob — it reads as a cost cap
    that is silently a no-op.
    """
    n = len(sentences)
    take_left = True
    while _span(sentences, lo, hi) < min_sec:
        can_l, can_r = lo > 0, hi < n - 1
        if not (can_l or can_r):
            break                            # both edges reached — take the whole transcript
        if take_left and can_l:
            lo -= 1
        elif can_r:
            hi += 1
        elif can_l:
            lo -= 1
        take_left = not take_left
    return lo, hi


def merge_windows(
    ranges: list[tuple[int, int, list[int], list[str]]],
) -> list[tuple[int, int, list[int], list[str]]]:
    """Sort by lo, then fold overlapping OR TOUCHING ranges (hi1 + 1 >= lo2) to a fixpoint,
    unioning seeds and reasons.

    Touching counts: two abutting windows would clip two abutting spans and re-ASR each
    without the other's context, and a word straddling the seam could land in neither
    reading. Merging is both cheaper and the only correct option. A merged window is NOT
    re-widened — merging only grows the span, so min_sec still holds — and its span is
    unbounded above: leaving two windows overlapping would double-replace an id range, which
    is a correctness violation, and no cost budget outranks that.
    """
    out: list[tuple[int, int, list[int], list[str]]] = []
    for lo, hi, seeds, reasons in sorted(ranges, key=lambda r: (r[0], r[1])):
        if out and out[-1][1] + 1 >= lo:
            p_lo, p_hi, p_seeds, p_reasons = out[-1]
            out[-1] = (p_lo, max(p_hi, hi),
                       sorted(set(p_seeds) | set(seeds)),
                       sorted(set(p_reasons) | set(reasons)))
            continue
        out.append((lo, hi, sorted(set(seeds)), sorted(set(reasons))))
    return out


def clip_span(sentences: list[dict], lo: int, hi: int) -> tuple[float, float]:
    """Padded audio span, clamped so the clip can NEVER contain a neighbour's speech."""
    n = len(sentences)
    t0 = sentences[lo]["start"] - CLIP_PAD_SEC
    t0 = max(t0, 0.0, sentences[lo - 1]["end"] if lo > 0 else 0.0)
    t0 = min(t0, sentences[lo]["start"])          # degenerate case: neighbour spans overlap
    t1 = sentences[hi]["end"] + CLIP_PAD_SEC
    if hi < n - 1:
        t1 = max(sentences[hi]["end"], min(t1, sentences[hi + 1]["start"]))
    return round(t0, 3), round(t1, 3)             # tail: ffmpeg clamps at EOF


def derive_windows(sentences: list[dict], seeds: dict[int, list[str]], *,
                   min_sec: float) -> list[Window]:
    """Seeds → windows sorted ascending by lo, disjoint and non-touching."""
    ranges: list[tuple[int, int, list[int], list[str]]] = []
    for lo, hi in _runs(list(seeds)):
        ids = [i for i in seeds if lo <= i <= hi]
        reasons = sorted({r for i in ids for r in seeds[i]})
        w_lo, w_hi = widen(sentences, lo, hi, min_sec=min_sec)
        ranges.append((w_lo, w_hi, ids, reasons))
    out: list[Window] = []
    for lo, hi, ids, reasons in merge_windows(ranges):
        t0, t1 = clip_span(sentences, lo, hi)
        out.append(Window(lo=lo, hi=hi, seeds=ids, reasons=reasons, t0=t0, t1=t1))
    return out


# --- the acceptance gate ------------------------------------------------------
def readings_agree(a: list[W], b: list[W]) -> bool:
    """True iff the two readings say the same WORDS. Definition of 'identical': equality of
    norm_text(" ".join(w.text for w in reading)) — i.e. letters and digits only, lowercased;
    case-, punctuation- and whitespace-insensitive. Compared on the FLAT word list, before
    resegment, so the gate does not depend on resegmenter tuning.

    Why normalized and not raw string equality: condition_on_previous_text is the flag whose
    documented effect IS punctuation (DECISIONS 2026-07-17), so a punctuation-sensitive gate
    would be testing the flag rather than the audio and would false-REJECT a proven repair on
    one comma. It cannot add a false ACCEPT: the defect class here is EXTRA or REPEATED words
    ("...like the LLM, or LLM."), which shifts the alphanumeric stream by tens of percent and
    can never survive this comparison. The one manual text override in the 7/7 run
    ("Anthropics Cloud Models" -> "Anthropic's Claude models", DECISIONS 2026-07-19) was a
    human edit made AFTER an accepted window, not a gate decision — and it differs in words,
    not just case, so it would fail this gate anyway.

    An empty or all-punctuation reading is NEVER agreement, even against another empty one:
    accepting it would replace real sentences with nothing, i.e. delete without a
    replacement — the never-drop invariant this whole mode exists to preserve.

    This gate did real accept/reject work in the manual run. It is the criterion, not a
    formality — but it proves STABILITY, not correctness (see the module docstring's caveat).
    """
    ka = norm_text(" ".join(w.text for w in a))
    kb = norm_text(" ".join(w.text for w in b))
    return bool(ka) and ka == kb


# --- offsetting, clamping, splicing -------------------------------------------
def offset_words(flat: list[W], t0: float) -> list[W]:
    """Clip-relative → absolute. flatten() starts prev_end at 0.0, so a window's timestamps
    come back relative to the clip. Applying the shift BEFORE resegment is safe: every rule
    in the resegmenter (_too_long, _gap_after, MIN_PAUSE_SEC, _merge_short's gaps, the
    midpoint) is difference-based and therefore translation-invariant; only the emitted
    start/end are absolute."""
    return [W(w.text, w.start + t0, w.end + t0, w.seg_end) for w in flat]


def clamp_into(new: list[dict], t0: float, t1: float) -> list[dict]:
    """Keep a VAD/timestamp overrun from escaping the window and corrupting a neighbour's
    slot in assemble. Re-rounded to 3 dp because transcribe writes round(..., 3) and a drift
    would change the file's formatting."""
    for s in new:
        s["start"] = round(min(max(s["start"], t0), t1), 3)
        s["end"] = round(min(max(s["end"], t0), t1), 3)
    return new


def splice(sentences: list[dict],
           repls: list[tuple[int, int, list[dict]]]) -> list[dict]:
    """Replace each accepted (lo, hi) run with its own new sentences and RENUMBER 0..m-1.

    ONE left-to-right pass over sorted disjoint replacements — applying them one at a time
    would invalidate every later index. A run of k sentences may become any number m >= 1 of
    new ones; 1 is the observed case (DECISIONS: "whisper emitted extra sentences where the
    window shows one"), not a requirement.
    """
    prev_hi = -1
    for lo, hi, new in repls:
        if lo <= prev_hi:
            raise RuntimeError(f"repair: replacements overlap or are unsorted at ids {lo}-{hi}")
        if not 0 <= lo <= hi < len(sentences):
            raise RuntimeError(f"repair: replacement range {lo}-{hi} outside 0..{len(sentences) - 1}")
        if not new:
            raise RuntimeError(f"repair: empty replacement for ids {lo}-{hi} — never drop")
        prev_hi = hi

    out: list[dict] = []
    i = 0
    for lo, hi, new in repls:
        out.extend(sentences[i:lo])
        out.extend(dict(r) for r in new)
        i = hi + 1
    out.extend(sentences[i:])

    for k, rec in enumerate(out):
        rec["id"] = k
    if not out:
        raise RuntimeError("repair: splice produced an empty transcript")
    if [r["id"] for r in out] != list(range(len(out))):
        raise RuntimeError("repair: spliced ids are not contiguous — the detectors key on position")
    starts = [r["start"] for r in out]
    if any(b < a for a, b in zip(starts, starts[1:])):
        raise RuntimeError("repair: spliced starts are not monotone — an offset bug, not a defect")
    return out


# --- clip + dual re-ASR (the injectable seam) ---------------------------------
def make_window_asr(ctx: Context):
    """Returns (t0, t1, condition_on_previous) -> list[W]. THE seam: repair_video takes it as
    a parameter so the whole mode is testable without a GPU, ffmpeg or media — the same
    injection habit as _run_batch_stage_major's stages=/finalize=.

    Preflight here rather than in repair_video: these are exactly the things the REAL seam
    needs, and an injected seam needs none of them.
    """
    if not ctx.work.source_audio.exists():
        raise RuntimeError("source.wav missing — repair needs the audio; re-run download")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH — required to clip the repair window")
    tmp = ctx.work.root / _CLIP_NAME
    state: dict = {"span": None}

    def window_asr(t0: float, t1: float, condition_on_previous: bool) -> list[W]:
        if state["span"] != (t0, t1):
            # input-side -ss so the clip's t=0 IS t0. Output-side -t (DURATION), not -to: the
            # meaning of -to after an input-side -ss has varied between ffmpeg versions, so the
            # in-repo precedent (scripts/lv_pick_refs.py) is deliberately NOT followed here.
            # No -ar/-ac/-c:a: source.wav is already 16 kHz mono pcm_s16le and the WAV muxer
            # preserves rate, channels and format.
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t0:.3f}",
                            "-i", str(ctx.work.source_audio), "-t", f"{t1 - t0:.3f}", str(tmp)],
                           check=True)
            state["span"] = (t0, t1)
        # session-owned and fetched lazily: a clean `auto` sweep never loads whisper at all,
        # and a batch loads large-v3 ONCE. A locally constructed WhisperModel would double
        # its ~3.1 GB and defeat that.
        model = ctx.session.whisper(ctx.cfg, ctx.cfg.whisper_model, role="transcribe")
        # _guard is NEVER applied to a window: its halving rule is full-file semantics, and a
        # clipped window has no prior context to loop on (DECISIONS 2026-07-19). The beam is the
        # STAGE's beam, deliberately — a window decoded at a different width would splice in a
        # sentence that is a different kind of artifact from its neighbours (transcribe_words).
        return transcribe_words(model, tmp, language=ctx.cfg.source_lang,
                                beam_size=ctx.cfg.whisper_beam_size,
                                condition_on_previous=condition_on_previous)

    return window_asr


# --- per-window driver --------------------------------------------------------
def _collateral_ids(w: Window, old_texts: list[str], new_texts: list[str]) -> list[int]:
    """NON-seed ids covered by the window whose text the accepted reading did NOT reproduce.

    widen() is right that the audio window and the replaced id range must be one object, so a
    window always replaces clean neighbours too — that is by design and is not narrowed here.
    What was missing is the DISTINCTION: `unchanged` is all-or-nothing over the whole window,
    so an intended edit to a seeded sentence and a rewrite of a neighbour that carried no
    defect hypothesis both report as "1 accepted, 0 rejected". Only the seeds have evidence of
    being wrong; for everyone else the automation is preferring a clipped second opinion over
    the full-file reading, which has strictly MORE context — that is how "Claude" became
    "Cloud" on 2YCaBqP8muw, with both readings agreeing (the gate proves STABILITY, not
    correctness). This repo flags, never blocks, so the answer is a signal, not a veto.

    Survival test: norm_text of the old sentence must appear as a contiguous run inside
    norm_text of the whole new reading. norm_text drops whitespace and punctuation, so the
    join is a single character stream and resegmentation alone can never register as a
    rewrite — only the words changing can.
    """
    key = norm_text(" ".join(new_texts))
    return [sid for sid, text in zip(range(w.lo, w.hi + 1), old_texts)
            if sid not in w.seeds and norm_text(text) not in key]


def repair_window(sentences: list[dict], w: Window, *, window_asr) -> WindowResult:
    old_texts = [s["text"] for s in sentences[w.lo:w.hi + 1]]
    if w.t1 - w.t0 <= 0:
        return WindowResult(window=w, accepted=False, reason="empty span", old_texts=old_texts)
    try:
        a = window_asr(w.t0, w.t1, False)
        b = window_asr(w.t0, w.t1, True)
    except Exception as e:                       # noqa: BLE001 — one bad window never drops the
        return WindowResult(window=w, accepted=False,      # rest of the video or the batch
                            reason=f"asr error: {type(e).__name__}: {e}", old_texts=old_texts)
    if not readings_agree(a, b):
        return WindowResult(window=w, accepted=False, reason="readings differ",
                            old_texts=old_texts,
                            alt_texts=[" ".join(x.text for x in a).strip(),
                                       " ".join(x.text for x in b).strip()])
    # cond=False is emitted: its provenance is the reason the method works (a clipped window has
    # no prior context to loop on); True is the control. The punctuation argument that made True
    # the pipeline default (DECISIONS 2026-07-17) was a 60-206 s full-file problem.
    new = clamp_into(resegment(offset_words(a, w.t0)), w.t0, w.t1)
    if not new:
        return WindowResult(window=w, accepted=False, reason="empty reading", old_texts=old_texts)
    new_texts = [s["text"] for s in new]
    return WindowResult(window=w, accepted=True, reason="identical", old_texts=old_texts,
                        new_texts=new_texts, new_sents=new, unchanged=new_texts == old_texts,
                        collateral=_collateral_ids(w, old_texts, new_texts))


# --- operator surface ---------------------------------------------------------
def _mmss(t: float) -> str:
    return f"{int(t) // 60:02d}:{t % 60:05.2f}"


def _print_window(r: WindowResult, i: int, n: int, *, dry_run: bool) -> None:
    """Old and new texts print IN FULL, never truncated — they are the entire point of the
    report. Every text the window covers is printed, not just the seeds, because widening
    replaces clean neighbours too and the operator must see that — and when one of those
    neighbours actually CHANGED, a [warn] line names it, so the operator does not have to diff
    the old/new blocks by hand to find it."""
    w = r.window
    print(f"--- window {i}/{n}  ids {w.lo}-{w.hi}  [{_mmss(w.t0)}-{_mmss(w.t1)}]  "
          f"{w.t1 - w.t0:.1f}s  ({', '.join(w.reasons) or 'explicit'})")
    for sid, text in zip(range(w.lo, w.hi + 1), r.old_texts):
        print(f"       old {sid} | {text}")
    if r.accepted:
        for text in r.new_texts:
            print(f"       new    | {text}")
        verdict = "WOULD ACCEPT" if dry_run else "accepted"
        note = " (text unchanged)" if r.unchanged else ""
        print(f"       [ok  ] {verdict} — both readings identical{note}")
        if r.collateral:
            # The old/new blocks above already show it; this line is what an operator scanning
            # a multi-video sweep actually reads, and it names the ids so the diff is targeted.
            ids = ", ".join(str(i) for i in r.collateral)
            print(f"       [warn] collateral edit on unflagged id(s) {ids} — "
                  f"no detector flagged these; verify before resuming", file=sys.stderr)
        print("       ids renumbered — re-derive ids before another explicit pass")
        return
    if r.alt_texts:
        print(f"       cond=False | {r.alt_texts[0]}", file=sys.stderr)
        print(f"       cond=True  | {r.alt_texts[1]}", file=sys.stderr)
    print(f"       [FAIL] REJECTED ({r.reason}) — nothing changed for ids {w.lo}-{w.hi}",
          file=sys.stderr)


# --- decode provenance --------------------------------------------------------
def check_decode_config(ctx: Context) -> "str | None":
    """Warn when a repair's decode config differs from the one that produced the transcript.

    Returns the stamped asr_key (None on a pre-stamp workdir — the existing corpus predates the
    stamp, exactly as TranscribeStage.done() argues).

    This is transcribe_words' "must not drift" rule surfaced at the only entry point that could
    break it. --repair-asr runs NO stage, so TranscribeStage.done() never executes (cli.py
    branches to _run_repair before the pipeline), and a beam-1 window spliced into a beam-5
    transcript is the "different kind of artifact from its neighbours" the shared body exists to
    prevent. Compared on asr_key_core: cond is EXPECTED to differ here — the emitted reading is
    always the clipped cond=False one.

    It warns rather than refuses (2026-07-22, same reversal as done()): the refusing version ran
    ahead of the no-defect-windows early return, so a repair that would have changed nothing
    still exited 1 and marked the video FAIL in a batch.
    """
    from .asr import asr_key, asr_key_core

    stamped = _stamped_key(ctx)
    want = asr_key(ctx.cfg)
    if stamped is not None and asr_key_core(stamped) != asr_key_core(want):
        print(f"[warn] repair: {ctx.work.root.name} was transcribed at [{stamped}] but the "
              f"current ASR config is [{want}]. A window decoded at another model/compute "
              f"type/beam splices in a sentence of a different KIND from its neighbours — "
              f"restore the ASR config or re-transcribe the video if that matters here.",
              file=sys.stderr)
    return stamped


def stamp_repaired(ctx: Context, stamped: "str | None", n_windows: int) -> None:
    """Record that this transcript is no longer ONE uniform decode.

    A repaired transcript is the full-file reading with n windows of the CLIPPED cond=False
    reading spliced into it (repair_window emits `a`). check_decode_config has already refused
    anything but a cond difference, so `cond=mixed` is the whole of what moved — and it is the
    truth, where continuing to claim the pure value is not. Without this the guard's headline
    claim (the on-disk key names the decode that produced this transcript) is false on the ONE
    command whose entire purpose is rewriting a transcript in place: no stage runs, and
    WorkDir.invalidate_downstream deliberately preserves timings.json.

    A pre-stamp workdir gets the COUNT but no key: its base decode is genuinely unknown, and an
    invented stamp is a worse record than none. The count is cumulative across passes — the same
    "counter that explains an outlier" role asr_passes plays for the guard.
    """
    from . import runreport
    from .asr import asr_key

    detail = runreport._load_timings(ctx.work)[1].get("detail") or {}
    prior = (detail.get("transcribe") or {}).get("asr_repair_windows")
    fields: dict = {"asr_repair_windows": (prior if isinstance(prior, int) else 0) + n_windows}
    if stamped is not None:
        fields["asr_key"] = asr_key(ctx.cfg, cond="mixed")
    runreport.record_stage_detail(ctx.work, "transcribe", **fields)


# --- per-video orchestration --------------------------------------------------
def repair_video(ctx: Context, *, ids: list[int] | None, dry_run: bool,
                 window_asr=None) -> tuple[list[WindowResult], int, int]:
    """(results, n_before, n_after). ids=None means auto. NEVER runs a downstream stage
    (user decision D1) — it only invalidates, so the next ordinary run redoes translate →
    synthesize → verify → assemble → mux honestly."""
    owns_clip = window_asr is None
    sentences = load_sentences(ctx.work)
    stamped = check_decode_config(ctx)     # before any GPU time: a foreign decode config makes
                                           # every window a mixed-kind splice, not a repair
    n_before = len(sentences)

    seeds = (seed_ids_from_detectors(sentences) if ids is None
             else explicit_seeds(ids, n_before))
    if not seeds:
        print("       no defect windows")
        return [], n_before, n_before

    windows = derive_windows(sentences, seeds, min_sec=ctx.cfg.repair_window_min_sec)
    print(f"       {len(seeds)} seed id(s) → {len(windows)} window(s)")
    # make_window_asr's preflight (source.wav on disk, ffmpeg on PATH) runs HERE, not at entry:
    # a video with no defect windows needs neither, and an eager preflight turned a clean `auto`
    # sweep into a FAIL row on any workdir whose source.wav had been pruned to save disk — the
    # same laziness make_window_asr already gives the whisper load.
    window_asr = make_window_asr(ctx) if owns_clip else window_asr

    results: list[WindowResult] = []
    try:
        for i, w in enumerate(windows, 1):
            r = repair_window(sentences, w, window_asr=window_asr)
            _print_window(r, i, len(windows), dry_run=dry_run)
            results.append(r)
    finally:
        if owns_clip:
            (ctx.work.root / _CLIP_NAME).unlink(missing_ok=True)

    repls = [(r.window.lo, r.window.hi, r.new_sents) for r in results if r.accepted]
    changed = any(r.accepted and not r.unchanged for r in results)
    if dry_run or not changed:
        # The `unchanged` guard is load-bearing: it is what makes a repeat repair pass safe on
        # a finished dub — an accept that reproduces the existing text must not nuke hours of
        # synthesis.
        print("[dry ] nothing written" if dry_run
              else "[info] transcript unchanged — nothing invalidated")
        # A dry run must still return the count it WOULD have produced: returning n_before
        # twice made every dry run with an accepted window report "(unchanged)" under a
        # preview showing 3 sentences collapsing to 1. Arithmetic, not splice(): splice raises
        # on overlap/empty replacement, which would turn a preview into a FAIL row.
        projected = n_before + sum(len(r.new_sents) - (r.window.hi - r.window.lo + 1)
                                   for r in results if r.accepted)
        return results, n_before, (projected if dry_run else n_before)

    if not ctx.work.pre_repair_sentences.exists():
        tmp = ctx.work.pre_repair_sentences.with_suffix(".json.tmp")
        tmp.write_text(ctx.work.sentences.read_text(encoding="utf-8"), encoding="utf-8")
        os.replace(tmp, ctx.work.pre_repair_sentences)
        print(f"       backup: {ctx.work.pre_repair_sentences.name} (created)")
    else:
        print("       backup kept (earlier original preserved — not clobbered)")

    if ctx.work.translation.exists():
        # The source-anomaly worklist lives INSIDE translation.json (per-record "src" fields,
        # route B), and invalidate_downstream() below deletes it — so repairing the first
        # window off that report must not destroy the rest of the list. Unlike the sentences
        # backup this one OVERWRITES on every repair: the preserved report must describe the
        # transcript just before the LATEST repair — write-once would keep a stale report
        # while destroying the fresh one, which is the same loss all over again. Byte-exact
        # copy, gated exactly like the sentences backup (never on dry-run/unchanged), and
        # skipped entirely when translate never ran (see seed_ids_from_detectors).
        tmp = ctx.work.pre_repair_translation.with_suffix(".json.tmp")
        tmp.write_bytes(ctx.work.translation.read_bytes())
        os.replace(tmp, ctx.work.pre_repair_translation)
        print(f"       backup: {ctx.work.pre_repair_translation.name} "
              f"(overwritten per repair; its ids predate this renumbering)")

    out = splice(sentences, repls)
    n_after = len(out)
    tmp = ctx.work.sentences.with_suffix(".json.tmp")   # atomic: never a torn sentences.json
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ctx.work.sentences)
    # immediately after the transcript flips and BEFORE the invalidation that can raise: the
    # stamp describes what is on disk, and what is on disk is now repaired
    stamp_repaired(ctx, stamped, len(repls))

    removed, failed = ctx.work.invalidate_downstream()
    print(f"       invalidated: {', '.join(removed) if removed else 'nothing downstream'}")
    if failed:
        # A PARTIAL delete self-heals into a stale artifact, so the operator must not be able
        # to walk past it.
        for f in failed:
            print(f"       [FAIL] could not delete {f}", file=sys.stderr)
        raise RuntimeError(f"{len(failed)} downstream artifact(s) could not be deleted — "
                           f"remove them by hand before the next run")
    # words.json is never opened. Not by omission — by rule (DECISIONS 2026-07-19).
    return results, n_before, n_after
