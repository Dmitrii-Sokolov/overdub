# Voice post-processing

## Goal + AC

Compression/EQ for a brighter, more attractive timbre on the dub track. `assemble` has only
`lowpass` today (Silero vocoder hiss), no dynamics.
AC: not frozen — task imported from PLAN.md (2026-08-24), fix AC at pickup. Judge by ear —
metrics do not adjudicate this.

## Plan

- [ ] Candidates: `acompressor`, `adynamicequalizer` (2-4 kHz presence lift), `speechnorm`,
  `loudnorm` by LUFS at the end instead of peak normalization. Same chain, after verify.

## State

Not started. Imported from PLAN.md at the 2026-08-24 agent-docs migration. Deliberately ranked
below tasks/input-prosody.md: the TTS guide puts the input first, and an EQ chain applied to
flat delivery is polish on the wrong layer.
