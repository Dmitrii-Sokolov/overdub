"""Parakeet-TDT worker — transcribe a corpus of source.wav into whisper-shaped words.json.

RUNS IN `.venv-parakeet`, NEVER in `.venv-asr`. NeMo pulls 137 packages and downgrades numpy
(2.5.1 -> 2.4.6 as resolved 2026-08-06), so it is quarantined in its own venv exactly like
demucs — the pipeline venv must not be gambled on an experiment. That is also why this file
imports NOTHING from `overdub`: the package is not installed over there, and the only thing the
two sides need to agree on is the words.json SHAPE.

    .venv-parakeet\\Scripts\\python.exe -X utf8 scripts\\parakeet_worker.py --root work
    .venv-parakeet\\Scripts\\python.exe -X utf8 scripts\\parakeet_worker.py --root work-exp\\parakeet\\fixture

Output per video, under --out/<id>/:
    words.json  [{"text","start","end","seg_end"}]  — same keys as overdub's own words.json, so
                scripts/parakeet_compare.py can read both sides through one reader.
    meta.json   audio/wall seconds, RTF, peak VRAM, chunk count, decode settings, or an error.

WHAT IS DELIBERATELY NOT HERE: resegmentation, similarity, any verdict. Those live in the
compare script, which runs in `.venv-asr` and imports the REAL `overdub.stages.transcribe`
functions — a second copy of resegment() on this side would be a second definition of what a
sentence is.

Three facts about this model that shape the code:
  * timestamps land on an 80 ms grid (10 ms features x8 subsampling), so `seg_end` and word
    durations are coarser than whisper's ~20 ms. Nothing here rounds them further.
  * greedy TDT is DETERMINISTIC — re-running a video reproduces it byte for byte. That is why
    `--force` exists but no repeat/averaging machinery does.
  * language is auto-detected and CANNOT be forced. An English source coming back in another
    script is a real failure mode; this worker records the text as-is and lets compare count it.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "nvidia/parakeet-tdt-0.6b-v3"

# Long-audio policy. Full attention is quadratic and the model card's "24 minutes" is measured on
# an A100 80GB — this host has 12 GB, and the corpus holds videos over 4 hours. So: local
# attention for everything (uniform decode config across the corpus is what makes the numbers
# comparable), plus time-domain chunking above CHUNK_THRESHOLD_SEC.
#
# THE CHUNK SIZE IS A MEMORY DECISION, NOT A QUALITY ONE, AND WINDOWS WILL NOT TELL YOU WHEN YOU
# GET IT WRONG. Measured 2026-08-06 at CHUNK_SEC=1200: every video over ~25 min peaked at exactly
# 10813 MB of a 12282 MB card, and decode time stayed linear up to 211 min of audio (49 s) then
# jumped 6.7x at 233 min (328 s) — with a 271-min video still running after 24 minutes. There is
# no OOM in that story: at the ceiling the WDDM driver spills VRAM into system RAM instead of
# failing, so the symptom is 100% GPU utilisation at a twentieth of the throughput. A crash would
# have been the kinder outcome. Halved to 10 min chunks, and the allocator cache is now dropped
# between chunks (see transcribe_one) so the peak cannot ratchet across a long file.
ATT_CONTEXT = [128, 128]        # frames each side; x80 ms = ~10 s of context per direction
CHUNK_THRESHOLD_SEC = 900.0     # 15 min — below this a video decodes in one pass
CHUNK_SEC = 600.0               # 10 min per chunk
CHUNK_OVERLAP_SEC = 15.0        # seam padding; words are cut at the MIDDLE of it (see _stitch)

VAD_DROP_GAP_SEC = 10.0         # non-speech longer than this is never shown to the model. Well
                                # above any rhetorical pause, so it only catches music, silence and
                                # dead air — see speech_blocks for why shorter gaps must survive.
VAD_PAD_MS = 400                # Silero's own padding around each detected segment
VAD_MIN_SILENCE_MS = 2000       # VAD_PAD_MS and this are faster-whisper's settings, not Silero's
                                # defaults, and they are copied deliberately: whisper has run this
                                # exact VAD over this exact corpus for months, so its tuning is the
                                # only one with evidence behind it. Silero's defaults (30 ms pad,
                                # 100 ms silence) cut A-ne5uwPMYw into 73 segments and dropped a
                                # 13.6 s stretch of real speech between two of them (2026-08-06);
                                # at these values the same file comes back as 3 segments covering
                                # 97% of it.
VAD_EDGE_PAD_SEC = 0.5          # extra head/tail room per block, so a block boundary never lands
                                # on the attack of the first word or the tail of the last

HOLE_MIN_SEC = 4.0              # shortest uncovered stretch worth a second read. Below this the
                                # recovered text is a few words and the re-read costs a decode.
HOLE_MERGE_GAP_SEC = 2.0        # adjacent empty segments closer than this are one hole
HOLE_PAD_SEC = 5.0              # context around a hole when it is re-read alone. The hole is a
                                # BOUNDARY artefact — the same audio decodes fine in a different
                                # window — so the clip must carry enough neighbouring speech for
                                # the decoder to lock on before it reaches the missing part.
HOLE_MAX_PER_VIDEO = 20         # a file needing more than this is not suffering the known defect;
                                # it is broken in some other way and should be reported, not
                                # ground through 50 extra decodes.


def _load_model(attn: str):
    import nemo.collections.asr as nemo_asr
    import torch

    t0 = time.perf_counter()
    model = nemo_asr.models.ASRModel.from_pretrained(model_name=MODEL_ID)
    model.eval()
    if torch.cuda.is_available():
        model = model.to(torch.device("cuda"))
    if attn == "local":
        # Both calls, in this order, are what the NeMo team prescribes for long audio on a small
        # card: the attention change alone still runs the subsampling conv over the whole
        # sequence and that is where a long file blows up first.
        model.change_attention_model("rel_pos_local_attn", ATT_CONTEXT)
        model.change_subsampling_conv_chunking_factor(1)
    print(f"[parakeet] {MODEL_ID} ({attn} attention) loaded in {time.perf_counter() - t0:.1f}s",
          file=sys.stderr)
    return model


def _read_wav(path: Path):
    """(mono float32 @16k, duration_sec). The corpus is written by overdub's own ffmpeg call
    (16 kHz mono pcm_s16le), so this asserts rather than resamples: a silent resample would make
    one row of the comparison a different measurement from the rest."""
    import soundfile as sf

    audio, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if sr != 16000:
        raise RuntimeError(f"{path.name}: expected 16 kHz, got {sr} — not the pipeline's wav")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio, len(audio) / float(sr)


def _windows(duration: float) -> list[tuple[float, float]]:
    if duration <= CHUNK_THRESHOLD_SEC:
        return [(0.0, duration)]
    out, start = [], 0.0
    while start < duration:
        end = min(start + CHUNK_SEC, duration)
        out.append((start, end))
        if end >= duration:
            break
        start = end - CHUNK_OVERLAP_SEC
    return out


_vad_model = None


def speech_blocks(audio, sr: int = 16000, *, want_segments: bool = False):
    """Contiguous regions worth decoding, or [] when the file has no speech at all.

    With `want_segments` returns (blocks, segments): the merged decode regions AND the raw VAD
    segments they were built from. The raw segments are what the coverage check needs — a block
    legitimately contains pauses, a segment does not, so "this segment produced no words" is a
    defect while "this block has a quiet stretch" is not.

    WHY THIS EXISTS. Parakeet decodes whatever it is handed and invents words on non-speech:
    measured 2026-08-06, three videos whose whisper transcript is empty came back with 110, 32 and
    6 words, one of them "That's the seven three" fifteen times over a 15-minute silent file.
    Whisper never produced those because faster-whisper runs Silero VAD internally
    (vad_filter=True) — NeMo has no such thing, so the filter has to live here.

    WHAT IT DOES NOT DO: it does not strip the pauses INSIDE speech. Cutting every silence out and
    decoding a concatenated buffer would be faster still, but the model punctuates off prosody, and
    sentence splitting downstream runs entirely on that punctuation — so squeezing the pauses out
    would buy speed with the one signal this pipeline cannot afford to lose. Only non-speech longer
    than VAD_DROP_GAP_SEC is withheld; shorter silences stay in place, untouched, inside a block.

    Blocks are CONTIGUOUS ranges of the original audio, so a word's timestamp is just its
    in-block time plus the block start — no offset map, nothing to get subtly wrong.

    Returns [] for "no speech" (the caller then writes an empty transcript without loading a
    single second into the model) and None when the VAD itself is unavailable, which is a
    different thing and must not be silently read as silence.
    """
    global _vad_model
    try:
        import torch
        from silero_vad import get_speech_timestamps, load_silero_vad
    except ImportError:
        return (None, None) if want_segments else None
    if _vad_model is None:
        _vad_model = load_silero_vad()
    stamps = get_speech_timestamps(torch.from_numpy(audio), _vad_model, sampling_rate=sr,
                                   speech_pad_ms=VAD_PAD_MS,
                                   min_silence_duration_ms=VAD_MIN_SILENCE_MS)
    if not stamps:
        return ([], []) if want_segments else []
    dur = len(audio) / float(sr)
    segments = [(s["start"] / sr, s["end"] / sr) for s in stamps]
    blocks: list[list[float]] = []
    for a, b in segments:
        if blocks and a - blocks[-1][1] <= VAD_DROP_GAP_SEC:
            blocks[-1][1] = b
        else:
            blocks.append([a, b])
    padded = [(max(0.0, a - VAD_EDGE_PAD_SEC), min(dur, b + VAD_EDGE_PAD_SEC)) for a, b in blocks]
    return (padded, segments) if want_segments else padded


def uncovered_spans(segments: list[tuple[float, float]], words: list[dict]) -> list[tuple[float, float]]:
    """VAD segments that produced no words at all, merged into spans worth re-reading.

    THE DEFECT THIS FINDS. Parakeet drops stretches of real speech: measured 2026-08-06 over 146
    videos, 20 spans of >=5 s where whisper transcribed and Parakeet returned nothing, the largest
    40.8 s / 125 words. Half of them survive every VAD setting tried, so this is the decoder's
    behaviour and not a gate that can be tuned out. It is also SILENT — a hole reads downstream as
    a video that simply had a quiet minute, and the dub then plays the original English there.

    Gaps are looked for INSIDE a VAD segment, never across wall-clock. That is what makes a long
    silence in the transcript evidence rather than a guess: the VAD cut its segments at every
    silence of VAD_MIN_SILENCE_MS or more, so by construction a segment contains no pause that
    long — and a 4-second stretch with no words inside one is therefore speech nobody transcribed.
    Scoring whole segments instead does not work at these settings: with min_silence at 2 s a
    12-minute video is often ONE segment, which is never entirely empty, and the 41 s hole in
    dwvBOwDjT64 went undetected until this was keyed on gaps (2026-08-06).
    """
    if not segments:
        return []
    starts = sorted(w["start"] for w in words)
    ends = [w["end"] for w in sorted(words, key=lambda w: w["start"])]
    spans: list[list[float]] = []
    for a, b in segments:
        i = bisect.bisect_left(starts, a)
        cursor = a
        while i < len(starts) and starts[i] < b:
            if starts[i] - cursor >= HOLE_MIN_SEC:
                spans.append([cursor, starts[i]])
            cursor = max(cursor, ends[i])
            i += 1
        if b - cursor >= HOLE_MIN_SEC:
            spans.append([cursor, b])

    merged: list[list[float]] = []
    for a, b in spans:
        if merged and a - merged[-1][1] <= HOLE_MERGE_GAP_SEC:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged if b - a >= HOLE_MIN_SEC]


def _stitch(per_window: list[tuple[float, float, list[dict]]]) -> list[dict]:
    """Concatenate per-window word lists, cutting each seam at the MIDDLE of the overlap.

    Both windows decode the overlap region, so both have an opinion about it; taking either
    window's full output duplicates words, and taking the earlier one's always loses the word the
    seam splits. Cutting at the midpoint keeps every word exactly once and puts the arbitrary
    choice where the two windows are equally (un)informed.

    The trim applies ONLY where two windows genuinely overlap. With VAD on, consecutive windows can
    belong to different speech blocks with a gap of dead air between them — trimming there would
    silently drop the last 7.5 s of every block, i.e. real words at the end of every speech region.
    """
    words: list[dict] = []
    for i, (w_start, w_end, ws) in enumerate(per_window):
        prev_end = per_window[i - 1][1] if i > 0 else None
        next_start = per_window[i + 1][0] if i + 1 < len(per_window) else None
        lo = (prev_end - CHUNK_OVERLAP_SEC / 2.0) if prev_end is not None and prev_end > w_start else -1e9
        hi = (w_end - CHUNK_OVERLAP_SEC / 2.0) if next_start is not None and next_start < w_end else 1e9
        words.extend(w for w in ws if lo <= w["start"] < hi)
    return words


def _to_words(result, offset: float) -> list[dict]:
    """NeMo hypothesis -> overdub words.json shape, timestamps shifted by the window offset.

    `seg_end` is reconstructed from the model's SEGMENT timestamps rather than invented: in
    whisper it marks a VAD/window edge, here it marks the model's own punctuation-driven segment
    boundary. Different provenance, same downstream role (a pause prior) — compare reports it
    separately so the difference stays visible instead of being smoothed over here.
    """
    stamps = getattr(result, "timestamp", None) or {}
    raw_words = stamps.get("word") or []
    seg_ends = {round(float(s["end"]), 3) for s in (stamps.get("segment") or [])}
    out = []
    for w in raw_words:
        text = (w.get("word") or w.get("text") or "").strip()
        if not text:
            continue
        start = float(w["start"]) + offset
        end = float(w["end"]) + offset
        out.append({
            "text": text,
            "start": round(start, 3),
            "end": round(end, 3),
            "seg_end": round(float(w["end"]), 3) in seg_ends,
        })
    return out


def _fill_holes(model, audio, segments, words: list[dict]) -> tuple[list, int]:
    """Re-read every uncovered speech span alone, splice the words back in.

    Mechanically this is the repo's own `--repair-asr`: clip the defect window out of the source
    and read that clip by itself. Proven on the five largest holes 2026-08-06 — all five came back,
    with MORE words than whisper had there (166 vs 125 on the 41 s one) and text that matches
    whisper's reading. The hole is a boundary artefact, not deafness: the same samples decode fine
    once they are not at the end of a long window.

    Only words STARTING inside the hole are kept. The clip is padded on both sides, so its edges
    re-transcribe audio that already has words; taking those too would duplicate them, and taking
    the pad's version over the original would let a 5 s clip overrule a full-context read.

    Returns (holes, recovered_word_count) and mutates `words` in place — the caller stamps both
    into meta.json, because a hole that could NOT be recovered has to stay visible.
    """
    if not segments:
        return [], 0
    holes = uncovered_spans(segments, words)
    if not holes:
        return [], 0
    if len(holes) > HOLE_MAX_PER_VIDEO:
        print(f"       [warn] {len(holes)} uncovered spans — beyond the {HOLE_MAX_PER_VIDEO} this "
              f"repairs; decoding the first {HOLE_MAX_PER_VIDEO} only", file=sys.stderr)
        holes = holes[:HOLE_MAX_PER_VIDEO]

    dur = len(audio) / 16000.0
    added = 0
    for a, b in holes:
        lo, hi = max(0.0, a - HOLE_PAD_SEC), min(dur, b + HOLE_PAD_SEC)
        clip = audio[int(lo * 16000):int(hi * 16000)]
        if not len(clip):
            continue
        got = [w for w in _to_words(model.transcribe([clip], timestamps=True, batch_size=1,
                                                     verbose=False)[0], lo)
               if a <= w["start"] < b]
        words.extend(got)
        added += len(got)
    words.sort(key=lambda w: (w["start"], w["end"]))
    return holes, added


def transcribe_one(model, wav: Path, *, use_vad: bool = True) -> tuple[list[dict], dict]:
    import torch

    audio, duration = _read_wav(wav)

    blocks, segments = speech_blocks(audio, want_segments=True) if use_vad else (None, None)
    vad_state = "off"
    if blocks is not None:
        vad_state = "on"
        if not blocks:
            # No speech anywhere: return before the model sees a single sample. This is the whole
            # point of the gate — the three videos that produced invented words on 2026-08-06 all
            # measured exactly zero speech segments here.
            return [], {"audio_sec": round(duration, 1), "wall_sec": 0.0, "rtf": 0.0,
                        "chunks": 0, "n_words": 0, "vram_peak_mb": None,
                        "vad": "on", "vad_speech_sec": 0.0, "vad_blocks": 0,
                        "holes": [], "hole_sec": 0.0, "hole_words_recovered": 0}
    elif use_vad:
        print("       [warn] silero-vad unavailable — decoding without a speech gate; "
              "non-speech stretches may come back as invented words", file=sys.stderr)

    if blocks:
        # A block is a contiguous slice of the ORIGINAL audio, so a long one still needs the
        # memory chunking; the windows are computed inside the block and shifted onto it.
        wins = [(b0 + s, b0 + e) for b0, b1 in blocks for s, e in _windows(b1 - b0)]
        speech_sec = sum(b - a for a, b in blocks)
    else:
        wins = _windows(duration)
        speech_sec = duration

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()

    t0 = time.perf_counter()
    per_window = []
    for start, end in wins:
        clip = audio[int(start * 16000):int(end * 16000)]
        results = model.transcribe([clip], timestamps=True, batch_size=1, verbose=False)
        per_window.append((start, end, _to_words(results[0], start)))
        # NEVER call torch.cuda.empty_cache() between chunks here. Tried 2026-08-06 to bound the
        # peak; every chunked video then died with `CUDA error: an illegal memory access` on its
        # SECOND window, and the first failure poisons the context so the whole batch cascades
        # (17/17 in 8 s). NeMo's TDT greedy decoder replays a CUDA GRAPH, and a graph holds the
        # raw addresses of the buffers captured into it — handing those blocks back to the
        # allocator makes the next replay read freed memory. Bounding the peak is the CHUNK SIZE's
        # job, and only that: same-sized chunks let the allocator reuse the same blocks anyway.
    words = _stitch(per_window)
    holes, recovered = _fill_holes(model, audio, segments, words)
    wall = time.perf_counter() - t0

    meta = {
        "audio_sec": round(duration, 1),
        "wall_sec": round(wall, 2),
        "rtf": round(wall / duration, 5) if duration else None,
        "chunks": len(wins),
        "n_words": len(words),
        "vram_peak_mb": (round(torch.cuda.max_memory_allocated() / 1e6, 1)
                         if torch.cuda.is_available() else None),
        "vad": vad_state,
        "vad_speech_sec": round(speech_sec, 1),
        "vad_blocks": len(blocks) if blocks else 0,
        # Both numbers, always. `holes: 3, recovered: 0` is a video to look at by hand; reporting
        # only the recovery would make a failed repair indistinguishable from a clean decode.
        "holes": [[round(a, 1), round(b, 1)] for a, b in holes],
        "hole_sec": round(sum(b - a for a, b in holes), 1),
        "hole_words_recovered": recovered,
    }
    return words, meta


def serve(attn: str, use_vad: bool) -> int:
    """Line protocol on stdin/stdout, one request per line, so the PIPELINE can use this venv.

    Loading the model costs 10-30 s. The pipeline is stage-major — every video in a batch passes
    through transcribe before anything else runs — so a subprocess per video would pay that load
    165 times over a 165-video batch (30-80 min of pure model loading). This mode is what makes
    `overdub.parakeet` able to hold ONE process for a whole stage sweep, exactly as Session holds
    one WhisperModel today.

    Request : {"wav": "<path>"}                        one JSON object per line
    Response: {"words": [...], "meta": {...}}  or  {"error": "..."}
    A malformed line answers with an error and keeps serving; only EOF ends the loop, so one bad
    video cannot take the sweep down with it.

    THE PROTOCOL STREAM IS A PRIVATE DUP OF FD 1, NOT sys.stdout. Loading the NeMo model leaves
    fd 1 unusable when it is a pipe — the first `print` after `from_pretrained` dies with
    `OSError: [Errno 22] Invalid argument` (2026-08-06, reproduced end-to-end through the real
    pipeline). So the descriptor is duplicated BEFORE the model is touched and fd 1 is then
    re-pointed at stderr: anything NeMo, lightning or a stray print writes lands with the other
    diagnostics, and the caller's stdout carries protocol lines and nothing else.
    """
    proto_fd = os.dup(1)
    os.dup2(2, 1)
    proto = os.fdopen(proto_fd, "w", encoding="utf-8", buffering=1)

    def reply(obj) -> None:
        proto.write(json.dumps(obj, ensure_ascii=False) + "\n")
        proto.flush()

    model = _load_model(attn)
    reply({"ready": True})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            words, meta = transcribe_one(model, Path(req["wav"]), use_vad=use_vad)
            reply({"words": words, "meta": meta})
        except Exception as e:                                    # noqa: BLE001 — see docstring
            reply({"error": f"{type(e).__name__}: {e}"})
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true",
                    help="line-protocol mode for the pipeline (see serve())")
    ap.add_argument("--root", type=Path, default=ROOT / "work",
                    help="corpus root: every <root>/<id>/source.wav is transcribed")
    ap.add_argument("--out", type=Path, default=ROOT / "work-exp" / "parakeet" / "out")
    ap.add_argument("--ids", help="comma-separated subset of ids")
    ap.add_argument("--limit", type=int, help="stop after N videos (shortest first)")
    ap.add_argument("--attn", choices=("local", "full"), default="local")
    ap.add_argument("--no-vad", action="store_true",
                    help="decode raw audio with no speech gate (what the 2026-08-06 baseline did)")
    ap.add_argument("--force", action="store_true", help="re-decode videos that already have output")
    args = ap.parse_args()

    if args.serve:
        return serve(args.attn, not args.no_vad)

    wavs = sorted(args.root.glob("*/source.wav"), key=lambda p: p.stat().st_size)
    if args.ids:
        wanted = {s.strip() for s in args.ids.split(",") if s.strip()}
        wavs = [p for p in wavs if p.parent.name in wanted]
    if not args.force:
        wavs = [p for p in wavs if not (args.out / p.parent.name / "words.json").exists()]
    if args.limit:
        wavs = wavs[:args.limit]
    if not wavs:
        print("nothing to do", file=sys.stderr)
        return 0

    total_audio = sum(p.stat().st_size for p in wavs) / 32000.0    # 16k mono s16 => 32000 B/s
    print(f"[parakeet] {len(wavs)} videos, ~{total_audio / 3600:.1f} h of audio", file=sys.stderr)

    model = _load_model(args.attn)
    ok = failed = 0
    t_batch = time.perf_counter()
    for i, wav in enumerate(wavs, 1):
        vid = wav.parent.name
        dest = args.out / vid
        dest.mkdir(parents=True, exist_ok=True)
        try:
            words, meta = transcribe_one(model, wav, use_vad=not args.no_vad)
        except Exception as e:                                     # noqa: BLE001
            # One video must not kill a 48-hour batch: OOM on a 4-hour file is an expected
            # outcome here, and it is a RESULT (this config cannot do that length), not a crash.
            failed += 1
            (dest / "meta.json").write_text(
                json.dumps({"error": f"{type(e).__name__}: {e}", "attn": args.attn},
                           ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [{i}/{len(wavs)}] {vid}  FAILED  {type(e).__name__}: {e}", file=sys.stderr)
            continue
        # Chunk geometry is stamped, not assumed: it moved once already (2026-08-06, 20 -> 10 min)
        # and a words.json carries no trace of how many seams are in it. Without this a later run
        # cannot tell a re-decoded video from one left over from the previous geometry.
        meta.update(model=MODEL_ID, attn=args.attn, att_context=ATT_CONTEXT,
                    chunk_sec=CHUNK_SEC, chunk_threshold_sec=CHUNK_THRESHOLD_SEC)
        (dest / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
        ok += 1
        print(f"  [{i}/{len(wavs)}] {vid}  {meta['audio_sec'] / 60:5.1f} min  "
              f"{meta['wall_sec']:6.1f}s  RTF {meta['rtf']}  {meta['n_words']} words  "
              f"{meta['chunks']} chunk(s)  VRAM {meta['vram_peak_mb']} MB  "
              f"vad {meta['vad']} {meta['vad_speech_sec'] / 60:.1f}min/{meta['vad_blocks']}blk"
              + (f"  HOLES {len(meta['holes'])} ({meta['hole_sec']:.0f}s) "
                 f"+{meta['hole_words_recovered']}w" if meta["holes"] else ""),
              file=sys.stderr)

    print(f"[parakeet] {ok} ok, {failed} failed, {time.perf_counter() - t_batch:.0f}s total",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
