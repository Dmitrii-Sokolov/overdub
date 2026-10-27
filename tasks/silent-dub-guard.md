# A silent dub never reaches an export

## Goal + AC

No resume can ship a silent `dub_ru.wav` over a good MKV. AC: not frozen — fix at pickup.

## Plan

- [ ] (iii, outranks the rest) Assert the LEVEL of the finished `dub_ru.wav` at the `mux` gate
  and refuse to mux a silent one — a DEGRADED-style loud stamp rather than a raise (a missing
  dub degrades, DECISIONS 2026-07-28; a silent dub is the same class of loss). Per-unit check in
  `assemble`, where the wav is already in memory; track-level check at `mux`, the last point
  where refusing still protects an existing export.
- [ ] (i) `SynthesizeStage.done()` verifies the wavs the manifest names exist, not just the
  manifest.
- [ ] (ii) A 100%-flagged `assemble` gets its own loud report line instead of an offenders list.

## State

Not started. Routed from INBOX at triage 2026-10-27.

## Findings

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
