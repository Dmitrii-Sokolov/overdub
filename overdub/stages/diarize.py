"""Diarize stage: who speaks each word → sentences re-cut at every speaker change.

Runs after transcribe on either ASR engine, in its own `.venv-parakeet` worker (streaming
Sortformer, up to 4 speakers). Its artifact is `diar.json` — the raw speaker segments plus the
speaker count — and that file is also what marks a workdir as diarized: a workdir from before
this stage has none, so a re-run diarizes it without re-decoding a word.

ONE SPEAKER CHANGES NOTHING. The transcript, and everything built on it, is left byte-for-byte
as it was; only diar.json appears. That is the case for nearly the whole corpus, which was picked
single-speaker on purpose, so an old video costs one diarization pass and no new translation.

MORE THAN ONE re-cuts sentences.json from words.json with a hard boundary at every speaker change
and a `speaker` on each sentence. When the cut differs from what is on disk, everything downstream
of the transcript is stale, and it goes the way --repair-asr sends it: the translation is copied
to `_pre-diarize-translation.json` first (it is the one artifact that cost a Sonnet pass), then
WorkDir.invalidate_downstream deletes the rest. The video re-enters route B for translation.

A TRANSCRIPT PASS DOES NOT PAY THAT PRICE. `--transcribe-only` asks for text, so under it
(`keep_dub`) a translated workdir with several speakers gets its cut in `transcript_view.json` and
nothing else changes: sentences.json, the translation and the dub stay. diar.json stays absent too,
because it would tell a later full run that this workdir needs no re-cut.

words.json is read, never written: it is the raw record of what the ASR heard (DECISIONS
2026-07-19), and the speaker of a word is derivable from it and diar.json at any time.

diar.json is written LAST, so a crash between the sentence rewrite and the invalidation leaves
the stage not-done and the next run repeats it — never a done stage over a half-applied cut.
"""

from __future__ import annotations

import bisect
import json
import os
import sys
import time

from ..pipeline import Context
from .transcribe import W, _ends_sentence, resegment

ISLAND_MAX_WORDS = 3    # a run of another speaker this short, starting inside an unfinished
                        # sentence, is the diarizer's error, not a turn. On the 2026-10-27 test
                        # videos every such island was the speaker's own word under the listener's
                        # overlapping "right" ("correct all the | time.", "Mac | minis."), the
                        # longest 2 words; real backchannels follow a FINISHED sentence and are
                        # never touched by this rule.
MAIN_SHARE = 0.03       # a speaker under this share of the words is an insert (a news clip, a
                        # quoted guest), not a participant: still its own voice, but voiced after
                        # the participants. Counting only speakers at or above it matched the
                        # user's participant counts on 88 of 89 calibration videos, the miss an
                        # under-count (windowed diarization + linking, 2026-10-27).


def _merged(intervals: list[tuple[float, float]]) -> tuple[list[float], list[float]]:
    """Union of one speaker's intervals as sorted, disjoint (starts, ends)."""
    starts: list[float] = []
    ends: list[float] = []
    for a, b in sorted(intervals):
        if ends and a <= ends[-1]:
            ends[-1] = max(ends[-1], b)
        else:
            starts.append(a)
            ends.append(b)
    return starts, ends


def assign_speakers(words: list[dict], segments: list[dict]) -> list["int | None"]:
    """A speaker per word: the one whose segments overlap the word most, or — for a word that
    falls in a gap between segments — the one whose nearest segment is closest to its midpoint.

    Speakers are renumbered 0, 1, … in order of first appearance among the WORDS, so the numbers
    are stable across runs and a diarizer label that owns no word (a false split of a few frames)
    simply never gets one. None for every word only when there are no segments at all.
    """
    if not segments:
        return [None] * len(words)
    per: dict[str, tuple[list[float], list[float]]] = {}
    for label in {s["speaker"] for s in segments}:
        per[label] = _merged([(s["start"], s["end"]) for s in segments if s["speaker"] == label])

    raw: list[str] = []
    for w in words:
        s, e = float(w["start"]), float(w["end"])
        best, best_ov = None, 0.0
        for label, (starts, ends) in per.items():
            ov = 0.0
            i = bisect.bisect_right(ends, s)
            while i < len(starts) and starts[i] < e:
                ov += min(e, ends[i]) - max(s, starts[i])
                i += 1
            if ov > best_ov:
                best, best_ov = label, ov
        if best is None:
            mid = (s + e) / 2.0
            dist = {}
            for label, (starts, ends) in per.items():
                j = bisect.bisect_left(starts, mid)
                cands = [starts[j] - mid] if j < len(starts) else []
                if j > 0:
                    cands.append(mid - ends[j - 1])
                dist[label] = min(max(0.0, c) for c in cands)
            best = min(sorted(dist), key=lambda k: dist[k])
        raw.append(best)
    return _renumber(raw)


def _renumber(labels: list) -> list[int]:
    order: dict = {}
    for label in labels:
        order.setdefault(label, len(order))
    return [order[label] for label in labels]


def smooth_islands(flat: list[W]) -> None:
    """Give a short run of another speaker back to the one it interrupts, in place.

    A speaker may change mid-sentence only with a real turn — more than ISLAND_MAX_WORDS words.
    A change right after a finished sentence is never touched, so "Right." / "Nice." between two
    of the other person's sentences keep their own speaker. Left to right, so a chain of islands
    ("Mac" / "minis.") resolves to the speaker before the first of them.
    """
    i = 1
    while i < len(flat):
        prev = flat[i - 1]
        if flat[i].speaker == prev.speaker or _ends_sentence(prev, flat[i]):
            i += 1
            continue
        j = i
        while j + 1 < len(flat) and flat[j + 1].speaker == flat[i].speaker:
            j += 1
        if j - i + 1 <= ISLAND_MAX_WORDS:
            for k in range(i, j + 1):
                flat[k].speaker = prev.speaker
        i = j + 1


def speaker_timbres(flat: list[W], audio, sr: int) -> list[dict]:
    """Per speaker: words, their share, whether that makes a main participant, median F0, ΔF,
    voice pool and grammatical gender, measured over that speaker's own words. A single-speaker
    video reports one entry, speaker 0 — its narrator needs a pool and a gender just as much."""
    from ..timbre import grammatical_gender, pool_of, timbre

    spans: dict[int, list[tuple[float, float]]] = {}
    for w in flat:
        spans.setdefault(w.speaker or 0, []).append((w.start, w.end))
    out = []
    for spk in sorted(spans):
        t = timbre(audio, sr, spans[spk])
        share = len(spans[spk]) / len(flat)
        out.append({"speaker": spk, "words": len(spans[spk]), "share": round(share, 4),
                    "main": share >= MAIN_SHARE, **t,
                    "pool": pool_of(t["f0_hz"], t["delta_f_hz"]),
                    "gender": grammatical_gender(t["f0_hz"], t["delta_f_hz"])})
    return out


def _write_atomic(path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class DiarizeStage:
    name = "diarize"

    def __init__(self, *, keep_dub: bool = False) -> None:
        self.keep_dub = keep_dub

    def done(self, ctx: Context) -> bool:
        if not ctx.cfg.diarize or ctx.work.diar.exists():
            return True
        # the view stands in for diar.json only while the translation it spares exists; without
        # one, run() owes sentences.json the real re-cut
        return (self.keep_dub and ctx.work.transcript_view.exists()
                and ctx.work.translation.exists())

    def _write_view(self, ctx: Context, flat: list[W], n: int) -> None:
        """A repaired sentences.json is copied as it is: words.json predates the repair, so a cut
        from it would undo the repair, and unlabelled text is the smaller loss."""
        repaired = ctx.work.pre_repair_sentences.exists()
        view = (json.loads(ctx.work.sentences.read_text(encoding="utf-8")) if repaired
                else resegment(flat))
        _write_atomic(ctx.work.transcript_view, json.dumps(view, ensure_ascii=False, indent=2))
        print(f"       {n} speakers → {ctx.work.transcript_view.name} (finished dub kept"
              + (", repaired text unlabelled)" if repaired else ")"))

    def run(self, ctx: Context) -> None:
        from .. import timings

        words = json.loads(ctx.work.words.read_text(encoding="utf-8"))
        t0 = time.perf_counter()
        if words:
            segments, meta = ctx.session.diarizer(ctx.cfg).diarize(ctx.work.source_audio)
        else:
            segments, meta = [], {"skipped": "no words"}     # no speech: nothing to attribute
        flat = [W(w["text"], float(w["start"]), float(w["end"]), bool(w.get("seg_end")), lab)
                for w, lab in zip(words, assign_speakers(words, segments))]
        smooth_islands(flat)
        if flat and flat[0].speaker is not None:
            for w, lab in zip(flat, _renumber([w.speaker for w in flat])):
                w.speaker = lab
        n = len({w.speaker for w in flat if w.speaker is not None})

        if n >= 2 and self.keep_dub and ctx.work.translation.exists():
            self._write_view(ctx, flat, n)
            return

        rewritten = False
        if n >= 2 and ctx.work.pre_repair_sentences.exists():
            # a repaired transcript is no longer derivable from words.json, so a re-cut from the
            # words would silently undo the repair
            raise RuntimeError(
                f"{ctx.work.root.name}: {n} speakers found, but sentences.json was rewritten by "
                f"--repair-asr and cannot be re-cut from words.json without losing the repair. "
                f"Set diarize = false for this run or re-transcribe the video.")
        if n >= 2:
            new = resegment(flat)
            old = json.loads(ctx.work.sentences.read_text(encoding="utf-8"))
            if new != old:
                if ctx.work.translation.exists():
                    ctx.work.pre_diarize_translation.write_bytes(ctx.work.translation.read_bytes())
                    print(f"       backup: {ctx.work.pre_diarize_translation.name}")
                _write_atomic(ctx.work.sentences, json.dumps(new, ensure_ascii=False, indent=2))
                rewritten = True
                removed, failed = ctx.work.invalidate_downstream()
                if removed:
                    print(f"       invalidated: {', '.join(removed)}")
                if failed:
                    for f in failed:
                        print(f"       [FAIL] could not delete {f}", file=sys.stderr)
                    raise RuntimeError(f"{len(failed)} downstream artifact(s) could not be deleted "
                                       f"— remove them by hand before the next run")
            print(f"       {n} speakers → {len(new)} sentences"
                  + (" (transcript re-cut)" if rewritten else " (cut unchanged)"))
        else:
            print(f"       {n} speaker{'s' if n != 1 else ''} — transcript unchanged")

        info = []
        if flat:
            import soundfile as sf

            # int16, not float: a 4-hour source stays ~0.5 GB, and timbre() casts only its frames
            audio, sr = sf.read(str(ctx.work.source_audio), dtype="int16")
            info = speaker_timbres(flat, audio, sr)
            for s in info:
                print(f"       speaker {s['speaker']}: F0 {s['f0_hz']} Hz, ΔF {s['delta_f_hz']} Hz "
                      f"→ {s['pool']} pool, {s['gender']}")

        ctx.work.transcript_view.unlink(missing_ok=True)     # sentences.json speaks for itself now
        _write_atomic(ctx.work.diar, json.dumps(
            {"speakers": n, "speakers_info": info, "segments": segments, "meta": meta},
            ensure_ascii=False, indent=1))
        timings.record_stage_detail(ctx.work, "diarize", work_sec=round(time.perf_counter() - t0, 3),
                                    speakers=n, rewritten=rewritten, model=meta.get("model"))
