"""Unit tests for overdub.repair — the isolated-window ASR repair (DECISIONS 2026-07-19).

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_repair.py   (or via pytest)
Filesystem only — no whisper, no ffmpeg, no media. The ASR seam is injected, so what is under
test is the MODE: window derivation off a bogus collapsed span, the identical-readings
acceptance gate, merge-and-renumber contiguity, the exact downstream delete set, the
never-clobber backup, and the usage errors that must fire before any side effect.

Guards the failure classes this mode exists to prevent: a replacement text that was INVENTED
rather than read off the window's own audio; a splice that drops or misnumbers a sentence (both
detectors key on list POSITION); a partial invalidation that silently ships a stale dub; and an
accepted-but-identical repair nuking hours of synthesis for no change.
"""

from __future__ import annotations

import contextlib
import inspect
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import cli, repair  # noqa: E402
from overdub.config import Config  # noqa: E402
from overdub.pipeline import STOP_NAME, Context  # noqa: E402
from overdub.stages.transcribe import W  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

_CFG = Config()
VID = "vid00000001"                              # exactly 11 chars, or video_id() falls through
URL = f"https://youtu.be/{VID}"                  # to its url-hash branch


# --- fixtures ------------------------------------------------------------------------
def _sent(i: int, text: str, start: float, end: float) -> dict:
    return {"id": i, "text": text, "start": start, "end": end}


_FILLER = [
    "Description goes beyond just writing prompts.",
    "The model can then call the tool it needs.",
    "Context is what separates a good answer from a bad one.",
    "Nothing here repeats the line before it.",
    "Every sentence carries its own distinct wording.",
    "Evaluation matters more than raw generation speed.",
    "A narrow scope beats a clever abstraction.",
]


def _even(n: int, *, dur: float = 4.0) -> list[dict]:
    """n back-to-back sentences of `dur` seconds — the neutral background a widening test
    measures a defect against. Texts are DELIBERATELY dissimilar: a fixture whose lines differ
    only in a trailing index trips duplicate_adjacent and every auto-seed test with it."""
    return [_sent(i, f"{_FILLER[i % len(_FILLER)]} ({i})", i * dur, i * dur + dur)
            for i in range(n)]


def _work(tmp: Path, sentences: list[dict] | None, **artifacts: str) -> WorkDir:
    """Fabricate a workdir. `artifacts` maps a workdir-relative name to its text content."""
    work = WorkDir(root=tmp)
    (tmp / "segments").mkdir(parents=True, exist_ok=True)
    if sentences is not None:
        work.sentences.write_text(json.dumps(sentences, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    for name, content in artifacts.items():
        p = tmp / name.replace("|", "/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return work


def _ctx(work: WorkDir, cfg: Config | None = None) -> Context:
    cfg = Config() if cfg is None else cfg
    cfg.work_root = work.root.parent
    return Context(url=URL, cfg=cfg, work=work)


def _words(text: str, *, t0: float = 0.0, step: float = 0.5) -> list[W]:
    """Clip-RELATIVE words, one per whitespace token — what the real seam hands back."""
    toks = text.split()
    return [W(tok, t0 + i * step, t0 + i * step + step, seg_end=(i == len(toks) - 1))
            for i, tok in enumerate(toks)]


def _fake_asr(mapping):
    """(t0, t1, cond) -> list[W]. `mapping` is {cond: text} for every window, or a callable
    (t0, t1, cond) -> text. A str means both readings agree."""
    def window_asr(t0: float, t1: float, cond: bool) -> list[W]:
        m = mapping(t0, t1, cond) if callable(mapping) else mapping
        if isinstance(m, Exception):                 # a window whose clip/ASR blows up
            raise m
        return _words(m if isinstance(m, str) else m[cond])
    return window_asr


def _quiet(fn, *a, **kw):
    """The mode prints its whole report; a test log does not need it."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


def _exits(fn, *a, **kw) -> bool:
    try:
        _quiet(fn, *a, **kw)
    except SystemExit:
        return True
    return False


# --- window derivation ---------------------------------------------------------------

def test_widen_reaches_min_from_a_collapsed_span() -> None:
    # The real defect shape: 69 chars stamped onto 0.28 s (RyvXxApfHkk#11). Clipping that span
    # yields no usable audio, so the widening must be driven by the NEIGHBOURS' real timings.
    sents = [_sent(0, "a", 0.0, 4.0), _sent(1, "b", 4.0, 8.0),
             _sent(2, "The LLM is used to analyze and categorize data, like the LLM, or LLM.",
                   8.0, 8.28),
             _sent(3, "c", 8.28, 12.0), _sent(4, "d", 12.0, 16.0)]
    lo, hi = repair.widen(sents, 2, 2, min_sec=8.0)
    assert (lo, hi) == (1, 3), (lo, hi)
    assert repair._span(sents, lo, hi) >= 8.0


def test_widen_alternates_left_first_and_is_deterministic() -> None:
    # Left-first centres the window on the defect; the exact range is pinned so the rule cannot
    # drift into "whichever neighbour happened to be shorter".
    sents = _even(9, dur=2.0)
    assert repair.widen(sents, 4, 4, min_sec=8.0) == (2, 5)


def test_widen_never_grows_a_seed_run_already_past_min() -> None:
    # A seed run this long already has enough audio; padding it further only costs ASR time.
    sents = _even(6, dur=10.0)
    assert repair.widen(sents, 1, 2, min_sec=8.0) == (1, 2)


def test_widen_has_no_upper_bound_and_overshoots_to_reach_min() -> None:
    # Reaching min_sec is what makes the clip transcribable, so a long neighbour is swallowed
    # whole. Pins the DELETION of repair_window_max_sec (2026-07-20): it could never change any
    # window for max_sec >= min_sec, and below min_sec it silently returned a window shorter
    # than the 8-18 s band the method was proven in — an operator knob that was a no-op.
    sents = [_sent(0, "a", 0.0, 40.0), _sent(1, "b", 40.0, 40.3), _sent(2, "c", 40.3, 44.0)]
    lo, hi = repair.widen(sents, 1, 1, min_sec=8.0)
    assert repair._span(sents, lo, hi) > 18.0
    assert "max_sec" not in inspect.signature(repair.widen).parameters
    assert "max_sec" not in inspect.signature(repair.derive_windows).parameters


def test_window_at_file_start_extends_right_only() -> None:
    sents = _even(6, dur=2.0)
    lo, hi = repair.widen(sents, 0, 0, min_sec=8.0)
    assert lo == 0 and hi > 0


def test_window_at_file_end_extends_left_only() -> None:
    sents = _even(6, dur=2.0)
    lo, hi = repair.widen(sents, 5, 5, min_sec=8.0)
    assert hi == 5 and lo < 5


def test_whole_file_shorter_than_min_yields_every_sentence() -> None:
    # Refusing would make short videos unrepairable; the GATE, not the length, decides.
    sents = _even(4, dur=1.0)
    assert repair.widen(sents, 1, 1, min_sec=8.0) == (0, 3)


def test_windows_merge_when_overlapping() -> None:
    # Two overlapping windows would double-replace an id range — a correctness violation.
    sents = _even(12, dur=2.0)
    seeds = {4: ["rate_implausible"], 6: ["dup_adjacent"]}
    ws = repair.derive_windows(sents, seeds, min_sec=8.0)
    assert len(ws) == 1
    assert ws[0].reasons == ["dup_adjacent", "rate_implausible"]
    assert ws[0].seeds == [4, 6]


def test_windows_merge_when_adjacent() -> None:
    # Touching counts: a word straddling the seam could land in NEITHER reading.
    merged = repair.merge_windows([(0, 3, [1], ["explicit"]), (4, 7, [5], ["explicit"])])
    assert len(merged) == 1 and merged[0][0] == 0 and merged[0][1] == 7


def test_merge_is_a_fixpoint() -> None:
    merged = repair.merge_windows([(0, 4, [0], ["a"]), (3, 8, [4], ["b"]), (9, 11, [10], ["c"])])
    assert len(merged) == 1 and merged[0][:2] == (0, 11)
    assert merged[0][3] == ["a", "b", "c"]


def test_seed_pair_gives_one_window() -> None:
    # dup_adjacent's {i: i+1, i+1: i} shape must not produce two windows over one defect.
    sents = _even(10, dur=5.0)
    ws = repair.derive_windows(sents, {3: ["dup_adjacent"], 4: ["dup_adjacent"]}, min_sec=8.0)
    assert len(ws) == 1 and ws[0].lo <= 3 and ws[0].hi >= 4


def test_clip_pad_never_reaches_a_neighbour() -> None:
    # 0.1 s gap with a 0.25 s pad: the clip must stop at the neighbour's end, never inside its
    # speech — a swallowed neighbour word would be re-emitted into sentences we do not replace.
    sents = [_sent(0, "a", 0.0, 4.0), _sent(1, "b", 4.1, 8.0), _sent(2, "c", 8.1, 12.0)]
    t0, t1 = repair.clip_span(sents, 1, 1)
    assert t0 == 4.0 and t1 == 8.1


def test_clip_pad_applies_when_there_is_silence() -> None:
    sents = [_sent(0, "a", 0.0, 4.0), _sent(1, "b", 6.0, 10.0), _sent(2, "c", 12.0, 16.0)]
    t0, t1 = repair.clip_span(sents, 1, 1)
    assert t0 == 5.75 and t1 == 10.25


# --- seeding -------------------------------------------------------------------------

def test_auto_seeds_read_sentences_json_without_translation() -> None:
    # --repair-asr auto --batch on a freshly transcribed queue is the whole point: no
    # translation.json exists yet, so the detectors must run off sentences.json alone.
    sents = _even(4, dur=4.0)
    sents[2] = _sent(2, "x" * 200, 8.0, 9.0)                 # 200 ch/s, far past the 40 bound
    seeds = repair.seed_ids_from_detectors(sents)
    assert 2 in seeds and "rate_implausible" in seeds[2]


def test_auto_seeds_include_both_dup_members() -> None:
    # Both members are flagged; the operator (and the window) must see the pair, not one half.
    dup = "The model can then call the tool again and again."
    sents = [_sent(0, "Something else entirely here.", 0.0, 4.0),
             _sent(1, dup, 4.0, 8.0), _sent(2, dup, 8.0, 12.0)]
    seeds = repair.seed_ids_from_detectors(sents)
    assert seeds[1] == ["dup_adjacent"] and seeds[2] == ["dup_adjacent"]


def test_auto_on_a_clean_transcript_yields_no_windows() -> None:
    # The property that makes an auto batch re-run resumable AND idempotent.
    assert repair.seed_ids_from_detectors(_even(8, dur=4.0)) == {}


def test_noncontiguous_sentences_json_raises() -> None:
    # RuntimeError, not assert: the never-drop invariants must survive python -O.
    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), [_sent(0, "a", 0.0, 1.0), _sent(2, "b", 1.0, 2.0)])
        try:
            repair.load_sentences(work)
            raise AssertionError("non-contiguous ids must raise")
        except RuntimeError as e:
            assert "contiguous" in str(e)


def test_explicit_id_out_of_range_aborts_the_whole_video() -> None:
    # ids [3, 999] on a 10-sentence file: NOTHING is written — no partial repair of a
    # partly-valid id set, because the operator was clearly reading a different file.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        sents = _even(10, dur=4.0)
        work = _work(tmp, sents, **{"translation.json": "[]"})
        before = work.sentences.read_bytes()
        try:
            _quiet(repair.repair_video, _ctx(work), ids=[3, 999], dry_run=False,
                   window_asr=_fake_asr("whatever"))
            raise AssertionError("an out-of-range id must raise")
        except RuntimeError as e:
            assert "out of range" in str(e)
        assert work.sentences.read_bytes() == before
        assert work.translation.exists()
        assert not work.pre_repair_sentences.exists()


# --- the gate ------------------------------------------------------------------------

def test_gate_accepts_identical_words_differing_only_in_punctuation_and_case() -> None:
    # Pins the chosen definition of "identical". condition_on_previous_text's documented effect
    # IS punctuation, so raw string equality would test the FLAG, not the audio, and would
    # false-reject a proven repair on one comma.
    a = _words("The model can then call the tool again")
    b = _words("the model can, then call the Tool again.")
    assert repair.readings_agree(a, b)


def test_gate_rejects_when_one_word_differs() -> None:
    # The gate did real accept/reject work in the manual 7/7 run — it is the criterion.
    a = _words("The model can then call the tool again")
    b = _words("The model then calls the tool again")
    assert not repair.readings_agree(a, b)


def test_gate_rejects_a_repeated_clause() -> None:
    # The real defect shape: extra/repeated words shift the alphanumeric stream by tens of
    # percent and can never survive the comparison.
    a = _words("The LLM is used to analyze and categorize data")
    b = _words("The LLM is used to analyze and categorize data, like the LLM, or LLM.")
    assert not repair.readings_agree(a, b)


def test_gate_rejects_two_empty_readings() -> None:
    # Accepting would replace real sentences with nothing — deleting without a replacement.
    assert not repair.readings_agree([], [])
    assert not repair.readings_agree(_words("... --- ,,,"), _words("!!! ??? ;;;"))


# --- splice and timings ---------------------------------------------------------------

def test_timings_are_offset_by_t0_and_rounded_to_3dp() -> None:
    # flatten() starts prev_end at 0.0, so a window's stamps come back CLIP-relative.
    shifted = repair.offset_words(_words("one two three"), 412.1)
    assert shifted[0].start == 412.1
    new = repair.clamp_into(
        [{"id": 0, "text": "t", "start": 412.1, "end": 413.6000000001}], 412.0, 500.0)
    assert new[0]["end"] == 413.6


def test_window_timings_are_clamped_into_the_span() -> None:
    # A VAD/timestamp overrun escaping the window would corrupt a neighbour's slot in assemble.
    new = repair.clamp_into([{"start": 9.0, "end": 25.0}, {"start": -3.0, "end": 12.0}],
                            10.0, 20.0)
    assert new[0]["start"] == 10.0 and new[0]["end"] == 20.0
    assert new[1]["start"] == 10.0


def test_replacement_text_is_the_windows_own_asr_output() -> None:
    # Pins "delete, do not invent": the spliced text must equal resegment() of the injected
    # reading, verbatim — nothing paraphrased, nothing stitched from neighbours.
    from overdub.stages.transcribe import resegment
    reading = "Description goes beyond just writing prompts. And that is the point."
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, _even(9, dur=4.0))
        _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
               window_asr=_fake_asr(reading))
        out = json.loads(work.sentences.read_text(encoding="utf-8"))
    expected = [s["text"] for s in resegment(_words(reading))]
    assert [s["text"] for s in out if s["text"] in expected] == expected


def test_splice_renumbers_contiguously_and_preserves_neighbours() -> None:
    sents = _even(6, dur=4.0)
    new = [{"id": 0, "text": "merged", "start": 12.0, "end": 20.0}]
    out = repair.splice([dict(s) for s in sents], [(3, 4, new)])
    assert [s["id"] for s in out] == list(range(len(out))) == list(range(5))
    assert out[3]["text"] == "merged"
    assert out[4]["text"] == sents[5]["text"] and out[4]["start"] == sents[5]["start"]
    assert all(set(s) == {"id", "text", "start", "end"} for s in out)


def test_two_disjoint_windows_applied_in_one_pass() -> None:
    # A sequential application would corrupt the second: the first replacement already shifted
    # every later index.
    sents = _even(10, dur=4.0)
    out = repair.splice([dict(s) for s in sents], [
        (1, 2, [{"id": 0, "text": "A", "start": 4.0, "end": 12.0}]),
        (6, 8, [{"id": 0, "text": "B", "start": 24.0, "end": 36.0}]),
    ])
    assert [s["text"] for s in out] == [sents[0]["text"], "A", sents[3]["text"],
                                        sents[4]["text"], sents[5]["text"], "B", sents[9]["text"]]
    assert [s["id"] for s in out] == list(range(7))


def test_splice_refuses_overlapping_replacements() -> None:
    sents = _even(6, dur=4.0)
    try:
        repair.splice(sents, [(1, 3, [{"id": 0, "text": "A", "start": 4.0, "end": 16.0}]),
                              (3, 4, [{"id": 0, "text": "B", "start": 12.0, "end": 20.0}])])
        raise AssertionError("overlapping replacements must raise, never double-replace")
    except RuntimeError as e:
        assert "overlap" in str(e)


# --- write / invalidate / mode behaviour ----------------------------------------------

_DOWNSTREAM = ["summary.md", "translation.json", "translation.jsonl", "pronounce_audit.json",
               "translation.draft.json", "report.json", "dub_ru.wav", "en.srt", "ru.srt",
               "output.mkv", "run.json"]
# summary.md is DOWNSTREAM by decision (2026-07-20), not an oversight: its only input is
# sentences.json, nothing in the Python code refreshes it, and both run_report.py and
# triage_html.py render it unconditionally with no staleness marker. Listing it here — in
# EITHER list — is what makes the choice visible to a future edit; before this it appeared in
# neither, so a change in either direction would have gone unnoticed by this file.
_SURVIVORS = ["words.json", "sentences.json", "source.wav", "source.mkv",
              "source.info.json", "source_bed.wav", "timings.json"]


def _all_artifacts() -> dict:
    art = {name: "x" for name in _DOWNSTREAM + _SURVIVORS}
    art["segments|manifest.json"] = "{}"
    art["segments|00000.wav"] = "w"
    art["segments|00007.wav"] = "w"
    return art


def test_invalidate_deletes_exactly_the_downstream_set() -> None:
    # One assertion per file so a regression NAMES the file. An incomplete delete does not fail
    # loudly — verify/assemble/mux done() self-heal and then silently ship a stale artifact.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, _even(3), **_all_artifacts())
        removed, failed = work.invalidate_downstream()
        assert failed == []
        for name in _DOWNSTREAM:
            assert not (tmp / name).exists(), name
            assert name in removed, name
        assert not work.seg_manifest.exists()
        assert not (tmp / "segments" / "00000.wav").exists()
        assert not (tmp / "segments" / "00007.wav").exists()
        for name in _SURVIVORS:
            assert (tmp / name).exists(), name


def test_words_json_is_never_rewritten() -> None:
    # By rule, not by omission: words.json is the raw record of what the ASR actually did, and
    # asr.floor_ratio must keep reporting that this file had a collapse.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, _even(9, dur=4.0), **{"words.json": '[{"text": "raw"}]'})
        before = work.words.read_bytes()
        _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
               window_asr=_fake_asr("A completely different reading of the window."))
        assert work.words.read_bytes() == before


def test_backup_written_once_and_never_clobbered() -> None:
    # A second repair pass must not overwrite the TRUE original with an already-repaired file.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, _even(9, dur=4.0))
        original = work.sentences.read_bytes()
        _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
               window_asr=_fake_asr("First repair reading of this window."))
        assert work.pre_repair_sentences.read_bytes() == original
        _quiet(repair.repair_video, _ctx(work), ids=[2], dry_run=False,
               window_asr=_fake_asr("Second repair reading of another window."))
        assert work.pre_repair_sentences.read_bytes() == original


def test_translation_backup_tracks_the_latest_repair() -> None:
    # Opposite policy to the sentences backup: the anomaly report must describe the transcript
    # just before the LATEST repair, so a second pass OVERWRITES the preserved copy —
    # write-once would keep a stale report while destroying the fresh one.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, _even(9, dur=4.0),
                     **{"translation.json": '[{"id": 0, "src": "old-report"}]'})
        first = work.translation.read_bytes()
        _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
               window_asr=_fake_asr("First repair reading of this window."))
        assert work.pre_repair_translation.read_bytes() == first
        assert not work.translation.exists()
        # translate re-ran and produced a NEW report; the next repair must preserve THAT one
        second = b'[{"id": 0, "src": "new-report"}]'
        work.translation.write_bytes(second)
        _quiet(repair.repair_video, _ctx(work), ids=[2], dry_run=False,
               window_asr=_fake_asr("Second repair reading of another window."))
        assert work.pre_repair_translation.read_bytes() == second


def test_dry_run_does_not_write_the_translation_backup() -> None:
    # Same gating as the sentences backup: a dry run preserves nothing, invalidates nothing.
    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), _even(9, dur=4.0), **{"translation.json": "[]"})
        _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=True,
               window_asr=_fake_asr("A brand new reading of this whole window."))
        assert not work.pre_repair_translation.exists()
        assert work.translation.exists()


def test_no_translation_backup_when_translate_never_ran() -> None:
    # Repair must keep working on a freshly transcribed queue with no translation.json at all
    # (seed_ids_from_detectors) — and then there is no report to preserve.
    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), _even(9, dur=4.0))
        _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
               window_asr=_fake_asr("A completely different reading of the window."))
        assert not work.pre_repair_translation.exists()


def test_rejected_window_changes_nothing() -> None:
    # One accepted + one rejected: only the accepted range moved, the rejected texts are
    # byte-identical.
    sents = _even(20, dur=4.0)
    keep_lo, keep_hi = 15, 17

    def mapping(t0, t1, cond):
        if t0 >= sents[keep_lo]["start"] - 1.0:          # the second window: readings disagree
            return "one reading here" if cond else "a different reading here"
        return "The accepted replacement reading."

    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), sents)
        (results, _, _), _ = _quiet(repair.repair_video, _ctx(work), ids=[4, 16],
                                    dry_run=False, window_asr=_fake_asr(mapping))
        out = json.loads(work.sentences.read_text(encoding="utf-8"))
    assert [r.accepted for r in results] == [True, False]
    texts = [s["text"] for s in out]
    for orig in sents[keep_lo:keep_hi + 1]:
        assert orig["text"] in texts, orig["text"]
    assert [s["id"] for s in out] == list(range(len(out)))


def test_all_windows_rejected_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, _even(9, dur=4.0), **{"translation.json": "[]"})
        before = work.sentences.read_bytes()
        _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
               window_asr=_fake_asr({False: "reading one here", True: "reading two here"}))
        assert work.sentences.read_bytes() == before
        assert not work.pre_repair_sentences.exists()
        assert work.translation.exists()


def test_unchanged_accept_does_not_invalidate() -> None:
    # What makes a repeat pass safe on a FINISHED dub: an accept that reproduces the existing
    # text must not nuke hours of synthesis.
    # Two sentences of 4 s: seeding id 1 widens left to (0, 1), so the window covers the whole
    # file and the injected reading can be exactly what is already on disk.
    sents = [_sent(0, "First sentence of the file.", 0.0, 4.0),
             _sent(1, "The window text itself.", 4.0, 8.0)]
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, sents, **{"translation.json": "[]", "output.mkv": "x"})
        before = work.sentences.read_bytes()
        _quiet(repair.repair_video, _ctx(work), ids=[1], dry_run=False,
               window_asr=_fake_asr(" ".join(s["text"] for s in sents)))
        assert work.sentences.read_bytes() == before
        assert work.translation.exists() and work.output.exists()
        assert not work.pre_repair_sentences.exists()


def test_dry_run_writes_nothing_but_reports_the_same_decisions() -> None:
    sents = _even(9, dur=4.0)
    reading = "A brand new reading of this whole window."
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, sents, **{"translation.json": "[]"})
        snapshot = {p.name: p.read_bytes() for p in tmp.rglob("*") if p.is_file()}
        (dry, _, _), out = _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=True,
                                  window_asr=_fake_asr(reading))
        assert {p.name: p.read_bytes() for p in tmp.rglob("*") if p.is_file()} == snapshot
        assert "WOULD ACCEPT" in out
    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), sents, **{"translation.json": "[]"})
        (live, _, _), _ = _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
                                 window_asr=_fake_asr(reading))
    assert [(r.accepted, r.reason, r.new_texts) for r in dry] == \
           [(r.accepted, r.reason, r.new_texts) for r in live]


def test_dry_run_reports_the_projected_sentence_count() -> None:
    # A dry run used to return n_before twice, so cli labelled EVERY dry run with an accepted
    # window "(unchanged)" — printed directly under a preview showing 3 sentences collapse
    # into 1. The projected count is free (new_sents is already populated) and must be real
    # while the disk stays untouched.
    sents = _even(9, dur=3.0)                        # ids 3-5 widen to reach 8 s: 3 -> 1
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, sents, **{"translation.json": "[]"})
        snapshot = {p.name: p.read_bytes() for p in tmp.rglob("*") if p.is_file()}
        (results, n_before, n_after), out = _quiet(
            repair.repair_video, _ctx(work), ids=[4], dry_run=True,
            window_asr=_fake_asr("One single replacement reading for the window."))
        assert {p.name: p.read_bytes() for p in tmp.rglob("*") if p.is_file()} == snapshot
    assert results[0].accepted and results[0].window.lo == 3 and results[0].window.hi == 5
    assert (n_before, n_after) == (9, 7), f"dry run must project 9 -> 7, got {n_before} -> {n_after}"


def test_a_rewritten_unflagged_neighbour_is_reported_as_collateral() -> None:
    # Widening pulls in sentences no detector flagged. Replacing them is by design (the audio
    # window and the replaced range must be one object), but `unchanged` is all-or-nothing over
    # the window, so a clean neighbour rewritten by a clipped second opinion used to read as a
    # plain "1 accepted, 0 rejected" — the "Claude" -> "Cloud" class.
    sents = _even(9, dur=3.0)                        # window 3-5, seed 4
    with tempfile.TemporaryDirectory() as d:
        (results, _, _), out = _quiet(
            repair.repair_video, _ctx(_work(Path(d), sents)), ids=[4], dry_run=True,
            window_asr=_fake_asr("Completely fresh wording across the entire window."))
    assert results[0].accepted
    assert results[0].collateral == [3, 5], results[0].collateral
    assert "collateral edit on unflagged id(s) 3, 5" in out


def test_a_preserved_neighbour_is_not_collateral() -> None:
    # The counterpart: only the seed changed, so the warning must stay silent. Punctuation and
    # resegmentation differences may not register as a rewrite — only the words changing may.
    sents = _even(9, dur=3.0)
    reading = f"{sents[3]['text']} Totally different words here. {sents[5]['text']}"
    with tempfile.TemporaryDirectory() as d:
        (results, _, _), out = _quiet(
            repair.repair_video, _ctx(_work(Path(d), sents)), ids=[4], dry_run=True,
            window_asr=_fake_asr(reading))
    assert results[0].accepted
    assert results[0].collateral == [], results[0].collateral
    assert "collateral" not in out


def test_asr_error_in_one_window_rejects_only_that_window() -> None:
    # One bad window never drops the rest of the video or the batch.
    sents = _even(20, dur=4.0)

    def mapping(t0, t1, cond):
        if t0 >= sents[15]["start"] - 1.0:
            return RuntimeError("ffmpeg clip failed")
        return "The accepted replacement reading."

    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), sents)
        (results, n_before, n_after), out = _quiet(
            repair.repair_video, _ctx(work), ids=[4, 16], dry_run=False,
            window_asr=_fake_asr(mapping))
    assert [r.accepted for r in results] == [True, False]
    assert results[1].reason.startswith("asr error: RuntimeError")
    assert n_after != n_before                       # the other window still applied


def test_transcribe_still_done_after_repair() -> None:
    # D1's intent: the next ordinary run must NOT redo a full ASR pass.
    from overdub.stages.transcribe import TranscribeStage
    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), _even(9, dur=4.0))
        ctx = _ctx(work)
        _quiet(repair.repair_video, ctx, ids=[4], dry_run=False,
               window_asr=_fake_asr("A replacement reading for the window."))
        assert TranscribeStage().done(ctx)


def test_repair_runs_no_downstream_stage() -> None:
    # D1: repair only invalidates. If it ever reached the stage list, this raises.
    real = cli.all_stages

    def boom(cfg):
        raise AssertionError("repair must never build or run the stage list")

    cli.all_stages = boom
    try:
        with tempfile.TemporaryDirectory() as d:
            work = _work(Path(d), _even(9, dur=4.0))
            _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
                   window_asr=_fake_asr("A replacement reading for the window."))
    finally:
        cli.all_stages = real


def test_cli_explicit_ids_with_batch_is_a_usage_error() -> None:
    # Exit 2, before any side effect.
    with tempfile.TemporaryDirectory() as d:
        q = Path(d) / "queue.txt"
        q.write_text(URL + "\n", encoding="utf-8")
        assert _exits(cli.main, ["--batch", str(q), "--repair-asr", "23,24"])
        assert _exits(cli.main, [URL, "--repair-asr", "twenty-three"])
        assert _exits(cli.main, [URL, "--repair-asr", "-4"])


def test_cli_repair_with_force_only_or_video_major_is_a_usage_error() -> None:
    # A silent no-op at 2am is the failure mode these guards exist to prevent.
    assert _exits(cli.main, [URL, "--repair-asr", "auto", "--force"])
    assert _exits(cli.main, [URL, "--repair-asr", "auto", "--only", "transcribe"])
    assert _exits(cli.main, [URL, "--repair-dry-run"])
    with tempfile.TemporaryDirectory() as d:
        q = Path(d) / "queue.txt"
        q.write_text(URL + "\n", encoding="utf-8")
        assert _exits(cli.main, ["--batch", str(q), "--repair-asr", "auto", "--video-major"])


def test_auto_mode_routed_through_repair_video_derives_and_applies_a_window() -> None:
    # ids=None must reach seed_ids_from_detectors. Every other repair_video test names explicit
    # ids, so before this one `seeds = {} if ids is None` passed the whole suite while
    # `--repair-asr auto --batch` — D3's primary mode, the one that runs before translation.json
    # exists — reported "no defect windows" for every video in an overnight queue and exited 0.
    sents = _even(8, dur=4.0)
    sents[2] = _sent(2, "x" * 200, 8.0, 9.0)                 # 200 ch/s: rate_implausible
    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), sents)
        (results, n_before, n_after), out = _quiet(
            repair.repair_video, _ctx(work), ids=None, dry_run=False,
            window_asr=_fake_asr("The window read back cleanly this time around."))
        after = json.loads(work.sentences.read_text(encoding="utf-8"))
    assert results and results[0].accepted, out
    assert results[0].window.lo <= 2 <= results[0].window.hi
    assert "x" * 200 not in [s["text"] for s in after]       # the collapse is gone
    assert n_after != n_before or [s["text"] for s in after] != [s["text"] for s in sents]


def test_a_clean_auto_sweep_needs_neither_source_wav_nor_ffmpeg() -> None:
    # window_asr is deliberately NOT injected here: this exercises the REAL make_window_asr
    # preflight. A video with no defect windows needs no audio, no ffmpeg and no whisper, so it
    # must report clean rather than FAIL — reachable whenever source.wav was pruned to save disk
    # on a hundred-hour batch, or the repair runs from a shell without ffmpeg on PATH.
    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), _even(8, dur=4.0))             # clean, and no source.wav
        assert not work.source_audio.exists()
        (results, n_before, n_after), out = _quiet(
            repair.repair_video, _ctx(work), ids=None, dry_run=False)
    assert results == [] and n_before == n_after
    assert "no defect windows" in out


def test_accepted_repair_invalidates_the_downstream_artifacts() -> None:
    # D1's core contract. test_invalidate_deletes_exactly_the_downstream_set proves the METHOD;
    # this proves repair_video CALLS it. Without the call, translate/verify/assemble/mux done()
    # all still return True on the next ordinary run, which then ships a dub built from the
    # PRE-repair transcript — silently.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        work = _work(tmp, _even(9, dur=4.0),
                     **{"translation.json": "[]", "report.json": "[]", "output.mkv": "x",
                        "summary.md": "Видео про GPU."})
        _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
               window_asr=_fake_asr("A genuinely different reading of this window."))
        for name in ("translation.json", "report.json", "output.mkv", "summary.md"):
            assert not (tmp / name).exists(), name
        assert work.sentences.exists() and work.pre_repair_sentences.exists()


def test_a_failed_downstream_delete_raises_and_never_reports_success() -> None:
    # A PARTIAL invalidation self-heals into a stale artifact, so the operator must not be able
    # to walk past it. Reachable on Windows in normal use: out/<title>.mkv open in a player →
    # unlink raises WinError 32. Without the raise, --batch walks on to the next video.
    real = WorkDir.invalidate_downstream
    WorkDir.invalidate_downstream = lambda self: ([], ["output.mkv: locked"])
    try:
        with tempfile.TemporaryDirectory() as d:
            work = _work(Path(d), _even(9, dur=4.0))
            try:
                _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
                       window_asr=_fake_asr("A replacement reading for the window."))
                raise AssertionError("a failed downstream delete must raise")
            except RuntimeError as e:
                assert "could not be deleted" in str(e)
    finally:
        WorkDir.invalidate_downstream = real


def test_spliced_timings_are_rebased_into_the_window() -> None:
    # Read off the sentences.json repair_video actually produced, not off offset_words in
    # isolation: without the t0 shift, clip-relative stamps (0.0-3.0 s) are CLAMPED up to t0 and
    # the repaired sentence lands as start == end — a zero-duration slot that splice's monotone
    # guard does not catch (equal starts are non-decreasing) and assemble has no slot for.
    sents = _even(9, dur=4.0)
    before = {s["text"] for s in sents}
    with tempfile.TemporaryDirectory() as d:
        work = _work(Path(d), sents)
        (results, _, _), _ = _quiet(repair.repair_video, _ctx(work), ids=[4], dry_run=False,
                                    window_asr=_fake_asr("Six plain words for this window here"))
        out = json.loads(work.sentences.read_text(encoding="utf-8"))
    w = results[0].window
    assert w.t0 > 0.0                                        # or the test proves nothing
    new = [s for s in out if s["text"] not in before]
    assert new
    for s in new:
        assert w.t0 <= s["start"] < s["end"] <= w.t1, s


# --- the CLI driver: exit codes and the missing-transcript rows -----------------------

def _repair_cli(tmp: Path, urls: list[str], *, ids, window_asr) -> int:
    cfg = Config()
    cfg.work_root = tmp
    return _quiet(cli._run_repair, urls, cfg, ids=ids, dry_run=False,
                  window_asr=window_asr)[0]


def test_explicit_ids_without_a_transcript_is_a_failure_not_a_skip() -> None:
    # auto legitimately passes over a not-yet-transcribed video; explicit ids cannot — the
    # operator named ids in a file that does not exist, so exiting 0 lets a
    # `repair && resume` wrapper ship the UNREPAIRED transcript believing the repair applied.
    # Mirrors the out-of-range-id contract, which already exits 1.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        (tmp / VID).mkdir()                                  # a workdir with no sentences.json
        assert _repair_cli(tmp, [URL], ids=[5], window_asr=_fake_asr("x")) == 1
        assert _repair_cli(tmp, [URL], ids=None, window_asr=_fake_asr("x")) == 0


def test_a_fail_outranks_an_honored_stop() -> None:
    # _summarize resolves this collision as `1 if fails else (3 if halted else 0)`; two batch
    # drivers in one module must not disagree. A supervisor that reads 3 as "thermal pause,
    # resume tonight" would otherwise never surface the video that needs eyes.
    bad, good, rest = "vid0000000a", "vid0000000b", "vid0000000c"
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        defective = _even(9, dur=4.0)
        defective[4] = _sent(4, "x" * 200, 16.0, 17.0)       # so auto derives a window here
        _work(tmp / bad, [_sent(0, "a", 0.0, 1.0), _sent(2, "b", 1.0, 2.0)])   # non-contiguous
        _work(tmp / good, defective)
        _work(tmp / rest, _even(9, dur=4.0))

        def asr(t0, t1, cond):                               # the good video drops the STOP file
            (tmp / STOP_NAME).write_text("", encoding="utf-8")
            return _words("A replacement reading for the window.")

        code = _repair_cli(tmp, [f"https://youtu.be/{v}" for v in (bad, good, rest)],
                           ids=None, window_asr=asr)
    assert code == 1                                         # not 3 — the FAIL wins


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all repair tests passed")
