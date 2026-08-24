# overdub/ — module facts

Measured facts and standing constraints local to the pipeline package. Tasks live in
`../BACKLOG.md`; rationale in `../DECISIONS.md`. **Do not quote a number across a fence below.**

## Corpus provenance — work/ and timings

- **Everything measured on `work/` BEFORE 2026-07-26 is F5 at grouping 0.4.** Those 36 manifests
  report `engine=f5`, `group_gap_max=0.4` — that pair is how you IDENTIFY them on disk, and the
  engine left the code, not the manifests. Every compression, slot and unit-count figure derived
  from that corpus describes a configuration this pipeline no longer runs; the boundary is a
  DATE, not a directory. `run.json` carries NO engine field (193 checked 2026-08-02), so these
  documents are the corpus's only provenance.
- The post-boundary corpus (eleven unique videos over the two 2026-07-26 batches) is a SAMPLE,
  not a baseline: fill medians are PER VIDEO and cannot be averaged across videos, and none of it
  is quotable beside a pre-2026-07-26 number. Triage rates from those batches are re-scored
  under the shipped classifier to **0 of 7 and 1 of 5** (DECISIONS 2026-07-27) — do not quote
  the older pair.
- **`total_wall_s` CHANGED SCOPE on 2026-08-05 — it now includes the translate seam.**
  `build_translation.py` records the Sonnet wave into `stages["translate"]`, so from that date a
  run's `total_wall_s`, `rtf`, `breakdown_pct` and the batch stage split all count the seam.
  Before it, `translate` was absent from the `stages` map of all 252 timings.json on disk — the
  two eras are not comparable (measured on `7xTGNNLPyMI` the same day: stage walls alone imply
  ×3.73, the real end-to-end figure was ×1.31). Three traps reading the new number: it is only
  as good as `translate.started`, so a video whose agent skipped the marker silently reverts to
  the old meaning (the helper prints a `[warn]` and that warning is the only signal); a chunked
  video whose middle chunk was re-run alone measures from the ORIGINAL wave's marker, so its
  wall is a floor; and the seam wall is orchestrator time, not machine time — right for the
  overlap question, wrong for a GPU-utilisation one. `total_wall_s` is a per-video SUM; the
  batch window lives in `work/runs.jsonl` — the two must not be mixed.
- Transcribe's wall varies 35× on identical work and no transcribe figure is quotable until
  `../tasks/transcribe-wall-variance.md` resolves.
- Retired figures (F5-era stage shares, pre-2026-07-22 wall-clock derivatives): DECISIONS
  2026-08-24 lists them; do not re-quote.

## Standing pipeline constraints

- Two stages hold the GPU — `transcribe` (the Parakeet worker) and `separate` — and they DO
  co-reside (9930 MiB of 12282, no OOM, DECISIONS 2026-08-06), so nothing forces a phase
  barrier; 19% headroom on one pair of videos is not a licence for arbitrary lengths. Silero is
  CPU, assemble and mux are ffmpeg, download is network. If `verify_roundtrip` is ever turned
  back on it is a THIRD GPU consumer and the queue must cover it by construction.
- The `separate` sweep must finish before `build_translation.py`: both read-modify-write
  `timings.json` and a real overlap drops one stage entry silently. If that becomes awkward to
  hold by hand, the fix is a lock in `overdub/timings.py`, not a rule in a fifth place.
- **Two rules about batch numbers, both learned the hard way.** Never sum an overlapping stage:
  the translate spans are sub-agent wall clocks and summing them read 4.41× on 6 videos and
  6.20× on 10, growing with fan-out width — report a union or an elapsed window. And
  tail-to-wave is a property of the QUEUE, not of the pipeline, so no single ×N generalises;
  quote the phase and the queue with it, and keep machine time apart from the attended session
  span (2438.6 s against 5700.6 s on the 2026-08-06 baseline — the difference is the
  orchestrator thinking).

## Smaller standing facts

- `_title_of` is a networked `yt-dlp --print title` (30 s timeout) for pre-2026-07-20 workdirs;
  in the finish sweep those queue back-to-back — an offline resume of 12 videos can sit ~6 min
  in one block at the very end. A caveat, not a bug.
- `word_timestamps=True` stays load-bearing: sentence resegmentation, timing sync and
  `--repair-asr` are all built on it.
