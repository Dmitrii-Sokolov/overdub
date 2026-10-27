# A silent dub never reaches an export

## Goal + AC

No resume can ship a silent `dub_ru.wav` over a good MKV. AC: not frozen — fix at pickup.

## Plan

- [x] (iii, outranks the rest) Assert the LEVEL of the finished `dub_ru.wav` at the `mux` gate
  and refuse to mux a silent one — a DEGRADED-style loud stamp rather than a raise (a missing
  dub degrades, DECISIONS 2026-07-28; a silent dub is the same class of loss). Per-unit check in
  `assemble`, where the wav is already in memory; track-level check at `mux`, the last point
  where refusing still protects an existing export. Built as a RAISE — see Findings.
- [x] (i) `SynthesizeStage.done()` verifies the wavs the manifest names exist, not just the
  manifest. Built in `assemble` instead — see Findings.
- [x] (ii) A 100%-flagged `assemble` gets its own loud report line instead of an offenders list.
  Dropped — both causes now fail the video outright, which is louder than any report line.

## State

Done 2026-10-27: `mux.dub_peak_dbfs` + `_SILENT_PEAK_DBFS` gate in `MuxStage.run`, a missing
voiced-wav gate in `AssembleStage.run`, both pinned by `tests/test_silent_dub.py`.

## Findings

**Why both gates RAISE instead of degrading** (2026-10-27). Degrading at mux would re-mux a
dub-less container over an `output.mkv` that may carry the good dub, i.e. it would destroy the
very export the check exists to protect; and `mux.done()` would then see the silent dub as a
track present but unstamped and re-mux on every resume. A silent dub, and a manifest naming wavs
that are not there, are artifacts that DISAGREE — the case the 2026-07-28 rule already sends to
a raise. Both raise before writing anything, so the previous `dub_ru.wav` and `output.mkv`
survive and the batch reports the video as failed with the cause in the message.

**Why the wav check sits in `assemble`, not in `SynthesizeStage.done()`.** In `done()` it would
re-synthesize every finished workdir whose segment wavs were cleaned off disk, on every resume,
even when nothing downstream needs them (assemble's own gate skips a dub whose keys match) —
pure Silero time, and the planned post-mux cleanup (tasks/clean-workdir-after-mux.md) would
make it the common case. In `assemble` it fires only when a dub is actually about to be built
from the missing wavs. The cost: the fix is an operator act (`--force --only synthesize`, named
in the message) rather than a self-heal.

**The bar has 60 dB of margin on both sides:** the 2026-08-04 silence peaked at -91.0 dBFS; the
six most recent real dubs in `work/` peak at -0.0 dBFS (measured 2026-10-27).

**Measured 2026-08-04** on `54BdUqMQUMI` / `dcmPV-Fa3GA` / `16zrEPOsIcI`: per-segment wavs gone
(manifest the only survivor), `synthesize` fast-skipped, `assemble` hit `FileNotFoundError` per
unit and set `assemble_error` + `placed_sec: 0.0` on 100% of 472 units, then wrote a full-length
`dub_ru.wav` of digital silence (`max_volume: -91.0 dB`, ffmpeg `volumedetect`). `MuxStage.done()`
is make-style freshness on `dub_audio` mtime, so the fresh silence (01:24) was NEWER than
`output.mkv` (2026-07-25) and the next plain `--batch` would have re-muxed silence over three good
exports. Caught only because the run was halted before step 3. 2 of the 3 videos still read
`[clean]` in the report.

The level check is the only one of the three that is a detector rather than a patch: it fires
for every silent-dub cause (all-empty `text_tts`, a broken mix, a wrong-path regression), and it
settled both the breakage and the repair in one second each (`-91.0 dB` broken; mean -21.9 /
-22.7 / -22.0 dB on the re-synthesized batch).

Fixture: the three `report.json` + `segments/manifest.json` pairs were copied to
`work/_silent-dub-2026-08-04/` before the re-synthesis — that state is not reproducible
afterwards, and those six files are the whole evidence base.
