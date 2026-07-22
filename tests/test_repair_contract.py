"""Contract tests for --repair-asr, written blind to overdub/repair.py.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_repair_contract.py

Every case below is derived from the SPEC, not from the code: DECISIONS 2026-07-19
("Repairing a whisper hallucination: isolated-window re-ASR, not a full re-run"),
the `--repair-asr` design, and the README "Repairing an ASR defect" runbook. The author of
this file deliberately never read `overdub/repair.py` or `tests/test_repair.py` — a test
derived from the implementation can only pin what the implementation happens to do, and
the point of this file is to pin what was PROMISED.

The seam is `window_asr(t0, t1, condition_on_previous) -> list[W]`, injected into
repair_video. No whisper, no ffmpeg, no media, no network — the fake returns clip-relative
words exactly as `flatten()` would (it starts prev_end at 0.0), so the absolute-timeline
rule is observable rather than assumed.

Contracts under test:
  1. window widening — a collapsed sentence's OWN span is bogus (0.28 s for 69 chars), so
     the audio window must be grown by whole SENTENCES using the neighbours' real timings.
  2. the acceptance gate — accept ONLY when the cond=True and cond=False readings say the
     same words. Both directions: an accept and a reject.
  3. merge-and-renumber — ids contiguous 0..n-1 afterwards, and never a drop.
  4. delete, do not invent — the replacement is the window's OWN ASR output, verbatim.
  5. the preserved original is written once and never clobbered by a second pass.
  6. words.json is never rewritten (it is the raw record of what the ASR actually did).
  7. downstream invalidation fires on an accepted+changed repair and on nothing else.
  8. timestamps land on the ABSOLUTE timeline of source.wav, not on the clip's.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import repair  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.pipeline import Context  # noqa: E402
from overdub.stages.transcribe import W  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

URL = "https://youtu.be/repaircon1"          # 11-char id -> work/repaircon1


# --- fixture ------------------------------------------------------------------------

# The defect shape DECISIONS describes: whisper stamps a long garble onto a fraction of a
# second. id3 is 66 chars in 0.94 s = 70 ch/s, far over the 40 ch/s rate_implausible bound,
# while every neighbour sits at a sane ~15 ch/s. Neighbours are 3.0 s each with no gaps so
# the widening arithmetic below is exact rather than approximate.
DEFECT = "The model outputs the same phrase repeatedly and then it loops."
FILLER = [
    "Welcome back to the second part of this short course.",
    "Today we look at how the assistant handles long inputs.",
    "That behaviour is easier to see with a concrete example.",
    "So we will walk through one end to end and compare them.",
    "The difference shows up almost immediately in the output.",
    "That is the whole idea, and it generalises to other tools.",
    "Thanks for watching, and see you in the next lesson here.",
]


def _base_sentences() -> list[dict]:
    """8 sentences; id3 is the collapsed one. Contiguous timings, 3.0 s per healthy line."""
    out: list[dict] = []
    t = 0.0
    texts = FILLER[:3] + [DEFECT] + FILLER[3:]
    for i, text in enumerate(texts):
        dur = 0.94 if i == 3 else 3.0
        out.append({"id": i, "text": text, "start": round(t, 3), "end": round(t + dur, 3)})
        t += dur
    return out


def _norm(s: str) -> str:
    """The gate's own definition of 'the same words': letters and digits, lowercased."""
    return re.sub(r"[^0-9a-z]+", " ", s.lower()).strip()


def _words(text: str, *, t0: float = 0.2, per: float = 0.32) -> list[W]:
    """Clip-RELATIVE words, the way flatten() hands them back from a re-read of the clip."""
    toks = text.split()
    out, t = [], t0
    for i, tok in enumerate(toks):
        out.append(W(text=tok, start=round(t, 3), end=round(t + per, 3),
                     seg_end=(i == len(toks) - 1)))
        t += per
    return out


class FakeASR:
    """The injected seam. `on_true`/`on_false` are the two readings; recording every call
    is itself part of the contract — the window must be read TWICE, once per flag value."""

    def __init__(self, on_true: str, on_false: str | None = None) -> None:
        self.on_true = on_true
        self.on_false = on_true if on_false is None else on_false
        self.calls: list[tuple[float, float, bool]] = []

    def __call__(self, t0: float, t1: float, cond: bool) -> list[W]:
        self.calls.append((t0, t1, cond))
        return _words(self.on_true if cond else self.on_false)


def _ctx(tmp: Path, sentences: list[dict] | None = None) -> Context:
    cfg = Config()
    cfg.work_root = tmp / "work"
    cfg.output_dir = tmp / "out"
    work = WorkDir.for_url(URL, cfg.work_root)
    work.sentences.write_text(
        json.dumps(sentences if sentences is not None else _base_sentences(),
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return Context(url=URL, cfg=cfg, work=work)


def _seed_downstream(work: WorkDir) -> dict[Path, bytes]:
    """Artifacts a repaired transcript invalidates, plus the two that must SURVIVE it."""
    files = {
        work.translation: b'[{"id": 0}]',
        work.report: b'{"flags": []}',
        work.summary: "# summary\nRussian blurb\n".encode("utf-8"),
        work.root / "run.json": b'{"video_id": "repaircon1"}',
        work.seg_wav(0): b"RIFFfake",
        # survivors
        work.words: b'[{"text": "collapsed", "start": 0.0, "end": 0.02}]',
        work.source_audio: b"RIFFsource",
    }
    for p, blob in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    return files


def _run(ctx: Context, *, ids=None, dry_run=False, asr=None):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        res = repair.repair_video(ctx, ids=ids, dry_run=dry_run, window_asr=asr)
    return res, buf.getvalue()


def _sents(work: WorkDir) -> list[dict]:
    return json.loads(work.sentences.read_text(encoding="utf-8"))


CLEAN = "The model outputs the same phrase once and then moves on to the next point."


# --- 1. window widening -------------------------------------------------------------

def test_widening_ignores_the_defects_own_span_and_uses_the_neighbours() -> None:
    """DECISIONS: 'a collapsed sentence's OWN span is bogus ... which is exactly why the
    widening is driven by the SURROUNDING sentences' real timings.'

    The seed's own span is 0.94 s — no usable audio. min_sec is 8.0, and widening steps by
    whole SENTENCES alternating left-first so the window stays centred on the defect:
      (3,3) 0.94  -> (2,3) 3.94  -> (2,4) 6.94  -> (1,4) 9.94 >= 8.0  STOP.
    """
    s = _base_sentences()
    lo, hi = repair.widen(s, 3, 3, min_sec=8.0)
    assert (lo, hi) == (1, 4), f"expected the window to widen to ids 1..4, got {lo}..{hi}"

    span = s[hi]["end"] - s[lo]["start"]
    assert span >= 8.0, f"widened window is {span:.2f} s, under the 8.0 s minimum"
    assert lo < 3 < hi, "the defect must sit strictly inside the widened window"


def test_widening_of_a_healthy_long_run_is_left_untouched() -> None:
    """'A run that already spans min_sec is returned untouched.' ids 0..2 span 9.0 s."""
    s = _base_sentences()
    assert repair.widen(s, 0, 2, min_sec=8.0) == (0, 2)


def test_a_file_shorter_than_min_sec_yields_the_whole_file() -> None:
    """Refusing would make short videos unrepairable; the GATE decides correctness, not
    the length. Whole file back, and no crash."""
    s = [{"id": 0, "text": "One.", "start": 0.0, "end": 1.0},
         {"id": 1, "text": "Two.", "start": 1.0, "end": 2.0}]
    assert repair.widen(s, 1, 1, min_sec=8.0) == (0, 1)


def test_clip_span_never_reaches_into_a_neighbours_speech() -> None:
    """The clip is padded but clamped: a neighbour's words inside the clip would be
    re-transcribed and then written over sentences we are not replacing."""
    s = _base_sentences()
    t0, t1 = repair.clip_span(s, 1, 4)
    assert t0 >= s[0]["end"], f"clip start {t0} reaches back into id0's speech"
    assert t1 <= s[5]["start"], f"clip end {t1} reaches forward into id5's speech"
    assert t0 <= s[1]["start"] and t1 >= s[4]["end"], "the clip must cover the whole window"


def test_touching_windows_merge_so_no_id_range_is_replaced_twice() -> None:
    """Two abutting windows would clip two abutting spans and read each without the
    other's context — a word on the seam could land in neither reading."""
    merged = repair.merge_windows([(0, 3, [1], ["rate"]), (4, 6, [5], ["dup"])])
    assert len(merged) == 1, f"touching ranges must fold, got {merged}"
    lo, hi, seeds, reasons = merged[0]
    assert (lo, hi) == (0, 6)
    assert sorted(seeds) == [1, 5] and sorted(reasons) == ["dup", "rate"]

    disjoint = repair.merge_windows([(0, 2, [1], ["a"]), (5, 7, [6], ["b"])])
    assert len(disjoint) == 2, "non-touching ranges must stay separate"


def test_auto_seeds_come_from_the_two_asr_detectors() -> None:
    """`auto` = the rate_implausible / dup_adjacent windows, read off sentences.json ALONE
    (repair must work before translate has ever run)."""
    seeds = repair.seed_ids_from_detectors(_base_sentences())
    assert 3 in seeds, f"the 70 ch/s collapsed sentence must seed a window, got {seeds}"
    assert set(seeds) == {3}, f"no healthy sentence may seed a window, got {seeds}"


# --- 2. the acceptance gate ---------------------------------------------------------

def test_gate_accepts_when_both_readings_say_the_same_words() -> None:
    asr = FakeASR(CLEAN)
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        (results, n_before, n_after), out = _run(ctx, ids=None, asr=asr)

    assert len(results) == 1, f"exactly one defect window expected, got {len(results)}"
    assert results[0].accepted, f"identical readings must be accepted; reason={results[0].reason!r}"
    assert n_before == 8
    assert {c[2] for c in asr.calls} == {True, False}, \
        f"the window must be read twice, cond=True and cond=False; got {asr.calls}"


def test_gate_is_insensitive_to_punctuation_and_case_only() -> None:
    """cond_on_previous_text's documented effect IS punctuation, so a punctuation-sensitive
    gate would test the flag rather than the audio and false-reject a good repair."""
    asr = FakeASR(CLEAN, CLEAN.upper().replace(".", "").replace(",", ""))
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        (results, _, _), _ = _run(ctx, ids=None, asr=asr)
    assert results[0].accepted, "case/punctuation-only differences must not reject"


def test_gate_rejects_when_the_readings_disagree_in_words() -> None:
    """'A rejection means the two readings disagreed, i.e. whisper is still guessing.'
    Nothing may be written on a reject — not the transcript, not the preserved original."""
    asr = FakeASR(CLEAN, "The model outputs an entirely different sentence about cats.")
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        before = ctx.work.sentences.read_bytes()
        files = _seed_downstream(ctx.work)
        (results, n_before, n_after), out = _run(ctx, ids=None, asr=asr)

        assert not results[0].accepted, "disagreeing readings must be rejected"
        assert n_after == n_before == 8, "a reject may not change the sentence count"
        assert ctx.work.sentences.read_bytes() == before, "a reject rewrote sentences.json"
        assert not ctx.work.pre_repair_sentences.exists(), \
            "a reject must not write the preserved original"
        for p, blob in files.items():
            assert p.exists() and p.read_bytes() == blob, \
                f"a reject invalidated {p.name} — nothing downstream changed"


def test_an_empty_reading_is_never_agreement() -> None:
    """Two empty readings agree trivially under naive equality, and accepting them would
    replace real sentences with nothing — the never-drop invariant this mode exists for."""
    assert not repair.readings_agree([], [])
    assert not repair.readings_agree(_words("..."), _words("..."))
    assert repair.readings_agree(_words("hello there"), _words("Hello, there."))
    assert not repair.readings_agree(_words("hello there"), _words("hello there there"))


# --- 3. merge and renumber ----------------------------------------------------------

def test_accept_merges_the_run_and_renumbers_ids_contiguously() -> None:
    """'each repair MERGES a run into the single verified sentence and renumbers to keep ids
    contiguous (the invariant duplicate_adjacent and implausible_rate both rely on).'"""
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        (results, n_before, n_after), _ = _run(ctx, ids=None, asr=FakeASR(CLEAN))
        after = _sents(ctx.work)

    assert results[0].accepted
    assert (n_before, n_after) == (8, 5), \
        f"ids 1..4 (4 sentences) must collapse to 1: expected 8 -> 5, got {n_before} -> {n_after}"
    assert [s["id"] for s in after] == list(range(len(after))), \
        f"ids must be contiguous from 0 after a repair, got {[s['id'] for s in after]}"
    assert len(after) == n_after


def test_repair_never_drops_the_sentences_outside_the_window() -> None:
    """Never-drop: everything outside the replaced run survives VERBATIM, only renumbered."""
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        (results, _, _), _ = _run(ctx, ids=None, asr=FakeASR(CLEAN))
        after = _sents(ctx.work)

    texts = [s["text"] for s in after]
    assert texts[0] == FILLER[0], "the sentence before the window was altered"
    assert texts[-3:] == FILLER[4:], f"the sentences after the window were altered: {texts[-3:]}"
    assert after[0]["start"] == 0.0 and after[0]["end"] == 3.0, "untouched timings drifted"
    assert len(after) >= 1


# --- 4. delete, do not invent -------------------------------------------------------

def test_the_replacement_text_is_the_windows_own_asr_output() -> None:
    """'Every replacement text is the isolated window's OWN output.' Nothing paraphrased,
    nothing stitched from the neighbours it replaced, nothing hand-repaired."""
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        (results, _, _), _ = _run(ctx, ids=None, asr=FakeASR(CLEAN))
        after = _sents(ctx.work)

    new = [s["text"] for s in after if s["text"] not in FILLER]
    assert len(new) == 1, f"expected exactly the window's one sentence, got {new}"
    assert _norm(new[0]) == _norm(CLEAN), \
        f"replacement is not the window's own reading:\n  got  {new[0]!r}\n  read {CLEAN!r}"
    assert _norm(DEFECT) not in _norm(" ".join(s["text"] for s in after)), \
        "the collapsed text survived the repair"
    # and the replaced neighbours' words were not smuggled into the new sentence
    for gone in (FILLER[1], FILLER[2], FILLER[3]):
        assert _norm(gone) not in _norm(new[0]), "a replaced neighbour's text was invented in"


# --- 5. the preserved original ------------------------------------------------------

def test_the_original_is_preserved_and_a_second_pass_does_not_clobber_it() -> None:
    """'keeps the original at work/<id>/_pre-repair-sentences.json (written once, never
    clobbered)'. The second pass is the whole point: after one repair the file on disk is
    already repaired, so a naive write would lose the TRUE original forever."""
    original = _base_sentences()
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), original)
        _run(ctx, ids=None, asr=FakeASR(CLEAN))
        first = json.loads(ctx.work.pre_repair_sentences.read_text(encoding="utf-8"))
        assert first == original, "the preserved original is not the pre-repair transcript"

        # second, explicit pass on the already-repaired file (ids were renumbered)
        second_reading = "A completely separate second repair of another sentence entirely."
        (results2, _, _), _ = _run(ctx, ids=[2], asr=FakeASR(second_reading))
        assert results2[0].accepted, "the second pass must actually run for this to mean anything"
        again = json.loads(ctx.work.pre_repair_sentences.read_text(encoding="utf-8"))

    assert again == original, \
        "the second repair pass clobbered the preserved original with the already-repaired text"


def test_the_anomaly_report_survives_its_own_repair() -> None:
    """The source-anomaly worklist lives INSIDE translation.json, and an
    accepted repair invalidates translation.json — so repairing the FIRST window off the
    report must leave the rest of the worklist readable, byte-exact, at
    _pre-repair-translation.json, while translation.json itself still goes."""
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        files = _seed_downstream(ctx.work)
        report = files[ctx.work.translation]
        (results, _, _), _ = _run(ctx, ids=None, asr=FakeASR(CLEAN))
        assert results[0].accepted
        assert not ctx.work.translation.exists(), \
            "translation.json is downstream and must still be invalidated"
        assert ctx.work.pre_repair_translation.exists(), \
            "the anomaly report was destroyed together with translation.json"
        assert ctx.work.pre_repair_translation.read_bytes() == report, \
            "the preserved report is not byte-identical to the pre-repair translation.json"


# --- 6. words.json --------------------------------------------------------------------

def test_words_json_is_never_rewritten() -> None:
    """'words.json is deliberately NOT rewritten — it is the raw record of what the ASR
    actually did, and asr.floor_ratio should keep reporting that these files had a collapse.'
    By rule, not by omission: it must survive an ACCEPTED repair untouched."""
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        files = _seed_downstream(ctx.work)
        raw = files[ctx.work.words]
        (results, _, _), _ = _run(ctx, ids=None, asr=FakeASR(CLEAN))
        assert results[0].accepted
        assert ctx.work.words.exists(), "words.json was deleted by a repair"
        assert ctx.work.words.read_bytes() == raw, "words.json was rewritten by a repair"


# --- 7. downstream invalidation -------------------------------------------------------

def test_accepted_repair_invalidates_exactly_the_downstream_artifacts() -> None:
    """'deletes exactly the artifacts downstream of sentences.json ... It never re-runs a
    stage itself.' summary.md included (workdir.invalidate_downstream, 2026-07-20)."""
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        _seed_downstream(ctx.work)
        (results, _, _), _ = _run(ctx, ids=None, asr=FakeASR(CLEAN))
        assert results[0].accepted

        for p in (ctx.work.translation, ctx.work.report, ctx.work.summary,
                  ctx.work.root / "run.json", ctx.work.seg_wav(0)):
            assert not p.exists(), f"{p.name} is downstream of sentences.json and must be deleted"
        assert ctx.work.source_audio.exists(), "source.wav is UPSTREAM and must survive"
        assert ctx.work.sentences.exists(), "sentences.json itself must survive (rewritten)"


def test_dry_run_decides_but_writes_nothing() -> None:
    """--repair-dry-run: 'decide and report, write nothing (the re-ASR still runs — that IS
    the decision)'. So the verdict must be real while the disk is untouched."""
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        files = _seed_downstream(ctx.work)
        before = ctx.work.sentences.read_bytes()
        asr = FakeASR(CLEAN)
        (results, n_before, n_after), out = _run(ctx, ids=None, dry_run=True, asr=asr)

        assert asr.calls, "dry-run must still perform the re-ASR — that IS the decision"
        assert results[0].accepted, "dry-run must report the verdict it would have applied"
        assert ctx.work.sentences.read_bytes() == before, "dry-run rewrote sentences.json"
        assert not ctx.work.pre_repair_sentences.exists(), "dry-run wrote the preserved original"
        for p, blob in files.items():
            assert p.exists() and p.read_bytes() == blob, f"dry-run invalidated {p.name}"


def test_an_unchanged_reading_does_not_invalidate_anything() -> None:
    """Invalidation is the expensive half (translate -> mux all re-run). A window whose
    reading reproduces the text already on disk changed nothing, so nothing downstream is
    stale and nothing may be deleted."""
    same = "Welcome back to the second part of this short course."
    sentences = [{"id": 0, "text": same, "start": 0.0, "end": 3.0}]
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), sentences)
        files = _seed_downstream(ctx.work)
        (results, _, _), _ = _run(ctx, ids=[0], asr=FakeASR(same))

        assert results[0].accepted
        assert results[0].unchanged, \
            f"a reading identical to the transcript must read as unchanged: {results[0].new_texts}"
        for p, blob in files.items():
            assert p.exists() and p.read_bytes() == blob, \
                f"an unchanged repair invalidated {p.name}"


# --- 8. absolute timeline -------------------------------------------------------------

def test_repaired_timestamps_are_absolute_not_clip_relative() -> None:
    """flatten() starts prev_end at 0.0, so a window's words come back RELATIVE to the clip.
    Left unshifted, the repaired sentence would claim to start near 0.0 and assemble would
    drop the dub at the top of the video. It must land inside the clip's absolute span."""
    s = _base_sentences()
    t0, t1 = repair.clip_span(s, 1, 4)
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        _run(ctx, ids=None, asr=FakeASR(CLEAN))
        after = _sents(ctx.work)

    new = next(x for x in after if x["text"] not in FILLER)
    assert new["start"] >= t0 - 1e-6, \
        f"repaired start {new['start']} is before the clip start {t0} — clip-relative leak"
    assert new["end"] <= t1 + 1e-6, \
        f"repaired end {new['end']} overruns the clip end {t1} — it would eat id5's slot"
    assert new["start"] > s[0]["end"], \
        f"repaired start {new['start']} sits in a sentence the window never covered"
    assert new["end"] > new["start"]
    # monotone, non-overlapping file after the splice — assemble depends on it
    for a, b in zip(after, after[1:]):
        assert a["end"] <= b["start"] + 1e-6, f"overlap after repair: {a} / {b}"


# --- explicit-id mode -----------------------------------------------------------------

def test_an_out_of_range_explicit_id_aborts_the_video_whole() -> None:
    """'An id outside the file aborts the video WHOLE — no partial repair of a partly-valid
    id set, because a typo means the operator was reading a different file.'"""
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d))
        before = ctx.work.sentences.read_bytes()
        raised = False
        try:
            _run(ctx, ids=[3, 99], asr=FakeASR(CLEAN))
        except Exception:
            raised = True
        assert raised, "a partly-valid explicit id set must abort, not repair what it can"
        assert ctx.work.sentences.read_bytes() == before, "an aborted video was still modified"
        assert not ctx.work.pre_repair_sentences.exists()


def test_explicit_ids_repair_a_window_the_detectors_cannot_see() -> None:
    """README: explicit ids are STRONGER than auto, not a legacy convenience — the detectors
    are blind to a hallucinated word that splits one sentence into two plausible halves."""
    split = [
        {"id": 0, "text": FILLER[0], "start": 0.0, "end": 3.0},
        {"id": 1, "text": "Description goes beyond distinction.", "start": 3.0, "end": 6.0},
        {"id": 2, "text": "just writing prompts.", "start": 6.0, "end": 9.0},
        {"id": 3, "text": FILLER[1], "start": 9.0, "end": 12.0},
    ]
    assert repair.seed_ids_from_detectors(split) == {}, \
        "fixture invalid: the detectors were supposed to be blind to this shape"

    reading = "Description goes beyond just writing prompts."
    with tempfile.TemporaryDirectory() as d:
        ctx = _ctx(Path(d), split)
        (results, n_before, n_after), _ = _run(ctx, ids=[1, 2], asr=FakeASR(reading))
        after = _sents(ctx.work)

    assert results[0].accepted
    assert n_before == 4 and n_after < 4, "the two halves must merge into one sentence"
    assert [x["id"] for x in after] == list(range(len(after)))
    assert any(_norm(reading) == _norm(x["text"]) for x in after), \
        f"the merged sentence is not the window's reading: {[x['text'] for x in after]}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all repair-contract tests passed")
