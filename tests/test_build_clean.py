"""Unit tests for scripts/build_clean.py — the route-E chunk planner and transcript assembler.

Run: .venv-asr/Scripts/python.exe tests/test_build_clean.py   (or via pytest)
Filesystem only. Guards the two contracts this route rests on: the chunk cut covers every id
exactly once (so a plan and its join can never disagree), and a chunk draft that is short, foreign
or duplicated fails LOUD instead of shipping a transcript quietly missing a paragraph.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import build_clean  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402


def _sent(i, text="A sentence of ordinary length.", start=None, end=None):
    return {"id": i, "text": text, "start": i * 2.0 if start is None else start,
            "end": i * 2.0 + 1.5 if end is None else end}


def _join(sentences: list[dict], drafts: dict[str, list[dict]], chunks=None):
    """Write sentences + chunk drafts into a tmp workdir, run join(), return (records, stats)."""
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(root=Path(d))
        work.sentences.write_text(json.dumps(sentences, ensure_ascii=False), encoding="utf-8")
        work.clean_dir.mkdir(parents=True, exist_ok=True)
        for name, rows in drafts.items():
            (work.clean_dir / name).write_text(json.dumps(rows, ensure_ascii=False),
                                               encoding="utf-8")
        return build_clean.join(work, chunks or build_clean.plan_chunks(sentences))


def _exits(sentences, drafts, chunks=None) -> bool:
    try:
        _join(sentences, drafts, chunks)
        return False
    except SystemExit:
        return True


# --- chunk planner ------------------------------------------------------------
# The cut is re-derived at join time from the same function, so a planner that loses or repeats an
# id does not produce a bad plan — it produces a build that cannot be completed at all.
def test_plan_covers_every_id_exactly_once() -> None:
    sents = [_sent(i) for i in range(250)]
    chunks = build_clean.plan_chunks(sents, target=80)
    covered = [i for c in chunks for i in range(c["from"], c["to"] + 1)]
    assert covered == list(range(250))


def test_plan_ranges_are_contiguous_and_ordered() -> None:
    chunks = build_clean.plan_chunks([_sent(i) for i in range(500)], target=60)
    assert chunks[0]["from"] == 0 and chunks[-1]["to"] == 499
    for a, b in zip(chunks, chunks[1:]):
        assert b["from"] == a["to"] + 1


def test_plan_empty_transcript_is_no_chunks() -> None:
    assert build_clean.plan_chunks([], target=80) == []


def test_plan_short_transcript_is_one_chunk() -> None:
    assert build_clean.plan_chunks([_sent(i) for i in range(12)], 80) == [{"from": 0, "to": 11}]


def test_plan_breaks_on_the_longest_pause() -> None:
    # A 4 s silence after id 17, inside the slide window around a target of 20 (which is +-3
    # sentences). The cut must land there rather than on the arithmetic boundary at 19: a chunk
    # edge inside running speech hands the next agent an opening it cannot parse.
    sents = [_sent(i, start=i * 2.0, end=i * 2.0 + 1.5) for i in range(40)]
    for i in range(18, 40):
        sents[i]["start"] += 4.0
        sents[i]["end"] += 4.0
    chunks = build_clean.plan_chunks(sents, target=20)
    assert chunks[0]["to"] == 17


def test_plan_absorbs_a_stub_tail() -> None:
    # 84 sentences at target 80 would leave a 4-sentence chunk — a full spawn to clean one
    # paragraph. It is merged into its predecessor instead.
    chunks = build_clean.plan_chunks([_sent(i) for i in range(84)], target=80)
    assert len(chunks) == 1 and chunks[0] == {"from": 0, "to": 83}


def test_plan_survives_missing_timestamps() -> None:
    # A gap that cannot be computed is 0.0, never an exception: the planner must not be the thing
    # that fails on a transcript the rest of the pipeline accepts.
    sents = [{"id": i, "text": "x"} for i in range(40)]
    covered = [i for c in build_clean.plan_chunks(sents, 10) for i in range(c["from"], c["to"] + 1)]
    assert covered == list(range(40))


# --- join: what must be fatal -------------------------------------------------
def test_join_happy_path() -> None:
    sents = [_sent(0, "So, um, we tested it."), _sent(1, "It failed twice.")]
    recs, stats = _join(sents, {"0-1.json": [{"id": 0, "text": "We tested it."},
                                             {"id": 1, "text": "It failed twice."}]})
    assert [r["id"] for r in recs] == [0, 1]
    assert recs[0]["text"] == "We tested it."
    assert recs[0]["src"] == "So, um, we tested it."      # the pair stays on disk, auditable
    assert recs[0]["start"] == 0.0 and recs[0]["end"] == 1.5
    assert stats["n_empty"] == 0


def test_join_missing_id_is_fatal() -> None:
    # THE defect this route cannot ship: a line that silently vanished. An emptied line must be
    # spelled "" — see the next test — so an absent id is never ambiguous.
    assert _exits([_sent(0), _sent(1)], {"0-1.json": [{"id": 0, "text": "Kept."}]})


def test_join_empty_string_is_legal_and_counted() -> None:
    recs, stats = _join([_sent(0, "So. Yeah."), _sent(1, "Real content here.")],
                        {"0-1.json": [{"id": 0, "text": ""},
                                      {"id": 1, "text": "Real content here."}]})
    assert recs[0]["text"] == "" and stats["n_empty"] == 1
    assert len(recs) == 2                                  # the id survives in the document


def test_join_foreign_id_is_fatal() -> None:
    # Two agents writing one line: the id belongs to the next chunk's owner.
    assert _exits([_sent(0), _sent(1), _sent(2)],
                  {"0-1.json": [{"id": 0, "text": "a"}, {"id": 1, "text": "b"},
                                {"id": 2, "text": "c"}], "2-2.json": [{"id": 2, "text": "c"}]},
                  chunks=[{"from": 0, "to": 1}, {"from": 2, "to": 2}])


def test_join_duplicate_id_is_fatal() -> None:
    assert _exits([_sent(0), _sent(1)],
                  {"0-1.json": [{"id": 0, "text": "a"}, {"id": 0, "text": "b"},
                                {"id": 1, "text": "c"}]})


def test_join_null_text_is_fatal_never_laundered() -> None:
    # str() coercion would put the literal "None" into the transcript, and it reads as a word.
    assert _exits([_sent(0)], {"0-0.json": [{"id": 0, "text": None}]})


def test_join_missing_chunk_file_is_fatal() -> None:
    assert _exits([_sent(i) for i in range(4)], {})


def test_join_unparseable_chunk_is_fatal() -> None:
    with tempfile.TemporaryDirectory() as d:
        work = WorkDir(root=Path(d))
        work.sentences.write_text(json.dumps([_sent(0)]), encoding="utf-8")
        work.clean_dir.mkdir(parents=True, exist_ok=True)
        (work.clean_dir / "0-0.json").write_text("{not json", encoding="utf-8")
        try:
            build_clean.join(work, [{"from": 0, "to": 0}])
            raise AssertionError("expected SystemExit")
        except SystemExit:
            pass


def test_join_object_instead_of_list_is_fatal() -> None:
    # The shape a scout-trained agent produces: route C's draft is an object, this one is a list.
    assert _exits([_sent(0)], {"0-0.json": {"id": 0, "text": "a"}})


def test_join_id_in_no_chunk_is_fatal() -> None:
    # A stale plan against a repaired transcript: --repair-asr renumbered every id.
    assert _exits([_sent(i) for i in range(3)],
                  {"0-0.json": [{"id": 0, "text": "a"}]},
                  chunks=[{"from": 0, "to": 0}])


# --- join: the quality signals, none of them fatal ----------------------------
def test_ratio_measured_per_chunk_and_per_document() -> None:
    sents = [_sent(0, "x" * 100), _sent(1, "y" * 100)]
    _, stats = _join(sents, {"0-1.json": [{"id": 0, "text": "x" * 20},
                                          {"id": 1, "text": "y" * 20}]})
    assert stats["ratio"] < build_clean._RATIO_WARN_DOC
    assert stats["chunks"][0]["ratio"] < build_clean._RATIO_WARN_CHUNK
    build_clean.report(stats)                              # advisory only: must not raise


def test_dropped_number_is_reported() -> None:
    _, stats = _join([_sent(0, "It took 40 minutes and cost 12 dollars.")],
                     {"0-0.json": [{"id": 0, "text": "It took 40 minutes."}]})
    assert stats["missing_numbers"] == ["12"]


def test_dropped_entity_is_reported() -> None:
    _, stats = _join([_sent(0, "We compared Postgres against Redis today.")],
                     {"0-0.json": [{"id": 0, "text": "We compared Postgres today."}]})
    assert stats["missing_entities"] == ["Redis"]


def test_sentence_initial_capital_is_not_an_entity() -> None:
    # Every sentence starts with a capital, so counting those would drown the real names.
    _, stats = _join([_sent(0, "Testing is useful."), _sent(1, "Really it is.")],
                     {"0-1.json": [{"id": 0, "text": "Testing is useful."},
                                   {"id": 1, "text": "Indeed it is."}]})
    assert stats["missing_entities"] == []


# --- rendering ----------------------------------------------------------------
def test_paragraph_breaks_on_a_pause() -> None:
    recs = [{"id": 0, "start": 0.0, "end": 1.0, "src": "", "text": "First thought."},
            {"id": 1, "start": 1.2, "end": 2.0, "src": "", "text": "Still the same one."},
            {"id": 2, "start": 5.0, "end": 6.0, "src": "", "text": "A new one."}]
    paras = build_clean.paragraphs(recs)
    assert len(paras) == 2
    assert paras[0]["text"] == "First thought. Still the same one."
    assert paras[1]["start"] == 5.0


def test_paragraph_breaks_on_length_without_any_pause() -> None:
    # A speaker who never pauses would otherwise produce one unreadable block per chunk.
    recs = [{"id": i, "start": i * 1.0, "end": i * 1.0 + 0.95, "src": "",
             "text": "word " * 40} for i in range(10)]
    assert len(build_clean.paragraphs(recs)) > 1


def test_emptied_lines_are_dropped_from_the_prose() -> None:
    recs = [{"id": 0, "start": 0.0, "end": 1.0, "src": "So.", "text": ""},
            {"id": 1, "start": 1.1, "end": 2.0, "src": "Real.", "text": "Real content."}]
    paras = build_clean.paragraphs(recs)
    assert len(paras) == 1 and paras[0]["text"] == "Real content."
    assert paras[0]["start"] == 1.1                        # the paragraph starts at real speech


def test_stamp_format_crosses_the_hour() -> None:
    assert build_clean._stamp(0) == "[0:00]"
    assert build_clean._stamp(372) == "[6:12]"
    assert build_clean._stamp(3750) == "[1:02:30]"


def test_render_md_stamps_and_header() -> None:
    doc = {"video_id": "abc12345678", "title": "A Talk", "channel": "Some Channel",
           "upload_date": "20260731",
           "paragraphs": [{"start": 0.0, "text": "Opening words."},
                          {"start": 20.0, "text": "Still early."},
                          {"start": 600.0, "text": "Much later."}]}
    md = build_clean.render_md(doc)
    assert md.startswith("# A Talk")
    assert "2026-07-31" in md and "Some Channel" in md
    assert "[0:00]" in md and "[10:00]" in md
    assert "[0:20]" not in md                              # inside the stamp interval
    assert "Still early." in md


def test_render_md_without_metadata_falls_back_to_the_id() -> None:
    md = build_clean.render_md({"video_id": "abc12345678", "title": None, "channel": None,
                                "upload_date": None, "paragraphs": []})
    assert md.startswith("# abc12345678")
    assert "youtube.com/watch?v=abc12345678" in md


def test_bad_upload_date_is_never_guessed() -> None:
    assert build_clean._iso("2026-07-31") is None and build_clean._iso(None) is None
    assert build_clean._iso("20260731") == "2026-07-31"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all build_clean tests passed")
