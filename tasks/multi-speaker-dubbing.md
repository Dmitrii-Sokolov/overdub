# Multi-speaker dubbing

## Goal + AC

A video with several speakers is dubbed with a distinct Russian voice per speaker, and turns of
different speakers are never read as one sentence. A single-speaker video comes out exactly as it
does today. This lifts the founding "single-speaker, no diarization" constraint (DECISIONS,
founding entry) — the lift itself is a `/triage` decision, not this task's.

Why: there is no `speaker` field anywhere in the pipeline. Sentence and unit merges ignore who is
talking, so on the panel `GDN3mPqJdvo` turns of different speakers are glued into one thought
(see `multi-speaker-detector.md`, Findings), one voice voices everyone, and the translator guesses
the grammatical gender of every first-person past verb.

## Frozen Spec

### Acceptance criteria

- **Single-speaker identity:** on the golden fixture videos plus 5 corpus videos,
  `sentences.json`, `translation.json` and the dub are byte-identical with diarization on and off.
  The diarization wall on those runs is reported (expected negligible, user 2026-10-27).
- **False-split rate measured:** over the single-speaker corpus (filtered at selection, so it is a
  pure negative set), the share of videos where diarization finds >1 speaker before and after the
  Q8 merge rule. Budget: ≤ 1 h of GPU, `host_guard` first.
- **No cross-speaker unit:** on the five test videos (Plan) no sentence and no synthesis unit spans
  a speaker change; boundary accuracy against the corrected labels of the fixture video is a number.
- **Per-unit speaker everywhere:** `sentences.json`, `translation.json`, manifest
  units and `run.json` flagged-unit rows carry `speaker`; manifest units carry `voice` (the palette
  variant); `run.json` carries `speakers: N` and every Q8 merge.
- **Translator sees the speaker:** route-B input carries `speaker` and `gender`
  (`feminine|masculine|unknown`); the contract no longer says "single-narrator".
- **Subtitles mark turns:** a speaker change opens the cue with "— " in `ru.srt` and "- " in `en.srt`.
- **Nothing drops the field:** `--repair-asr`, `tools/renorm_workdir.py` and the degraded assemble
  path preserve `speaker`.
- **Resume is honest:** a workdir without `diar.json` is diarized on the next run without
  re-decoding; a re-cut retires everything downstream of `sentences.json`; changing a unit's voice
  variant invalidates only that unit's wav. `words.json` is never written by diarization (it is the
  raw ASR record, DECISIONS 2026-07-19) — a word's speaker is derived from it and `diar.json`.

### Constraints

- Diarization runs in the Parakeet worker (`.venv-parakeet`, NeMo already installed — Sortformer
  first, MSDD if quality falls short; other engines only after both). No new dependency without
  asking.
- Always on (`diarize = true`); 1 speaker found → today's pipeline unchanged.
- Engine specifics stay in the TTS adapter; voice post-processing does not change duration, so the
  `voice_rate` / slot model stays valid.
- Every accepted palette voice has a measured `voice_rate` — an unmeasured one silently disables
  `target_chars`.

### Non-Goals

- Voice cloning or matching the source speaker's timbre beyond gender.
- Overlapped speech rendered as overlap — the dub stays sequential.
- More than 4 distinct voices (Sortformer v1 cap); speakers 5+ share their gender's last voice.
- Repairing any individual video.

## Plan

- [x] **Spike — voice palette (before any pipeline code).** Closed 2026-10-27: palette and
  assignment rule under "Decisions", measurements under Findings. Candidates: the 5 stock voices;
  `eugene`/`kseniya` × SSML `<prosody pitch>` levels; `eugene`/`kseniya` × rubberband formant
  shift (two passes: `pitch=X:formant=shifted`, then `pitch=1/X:formant=preserved`) ± EQ;
  `apply_tts(voice_path=…)` / `speaker="random"` probe (the v5_5_ru signature exposes
  `voice_path`, `intensity`, `type_str` — semantics unknown). Filter by TitaNet cosine between
  variants (NeMo `label_models`, already installed), then the user's ear, including `aidar` vs
  `prosody pitch` head to head. Output: an ordered palette per gender + `voice_rate` per accepted
  variant.
- [x] **Diarization stage** (2026-10-27): `scripts/parakeet_worker.py --serve --model diar` (its
  own process), `ParakeetWorker.diarize`, `Session.diarizer`, `overdub/stages/diarize.py` between
  transcribe and translate (and in `transcribe_only_stages`), `cfg.diarize`. Word → speaker by
  overlap, `smooth_islands`, re-cut + `invalidate_downstream` only when the cut changes.
- [ ] **F0 per speaker → gender** (absorbs `narrator-gender-f0.md`: measured once, used for both
  voice and translator) + ΔF for the timbre metric.
- [x] **Fixture:** auto labels of `z7cNbsr3b5s` and `i-o5YbNfmh0` judged fully correct by ear
  (user, 2026-10-27) — `work-exp/diar-probe/<id>/labels.txt` stand as the reference, uncorrected.
- [ ] **False-split run** over the single-speaker corpus → the Q8 threshold. Must be READ-ONLY on
  `work/` (the bridge + `assign_speakers` + `smooth_islands`, never the stage): on a corpus
  workdir the stage would retire a real translation on every false split.
- [x] **Speaker change = hard boundary** in resegment and `_merge_short` (`_split_overlong` runs
  inside a same-speaker range by construction).
- [ ] **Same boundary in `build_units`** — rides with per-unit voice (needs `speaker` in
  `translation.json` first).
- [ ] **Per-unit voice:** `voice=` per `synthesize()` call; palette variants as config; cache keys
  and manifest per unit.
- [ ] **Translator contract** (route B contract, both workflow prompts, the `.agents/` mirror,
  `build_translation.py` copying the field).
- [ ] **Subtitles + reporting.**

Test videos (user, 2026-10-27): 2 speakers — `i-o5YbNfmh0`, `N6FkmdL0Lg0`, `9GtcbnmldcY`;
3 speakers — `z7cNbsr3b5s`; 4 speakers — `hm8NzEd5io0`.

## Decisions taken at drafting (user, 2026-10-27)

- No corpus measurement of the multi-speaker share: the corpus was filtered single-speaker at
  selection, so any share off it is a selection artifact; the feature is justified as is.
- How many videos have >2 speakers is unanswerable off this corpus — answered by design instead
  (4-voice palette, Non-Goals).
- ~~Voice assignment: dominant speaker gets the best voice of their gender~~ — superseded the
  same day by the timbre-matching rule below.
- **Palette (user ear, 2026-10-27), ordered per gender:**
  male — `eugene`, `aidar`, `eugene+formant=1.12`, `aidar+formant=1.12`, `eugene+formant=0.88`,
  `aidar+formant=0.88`; female — `xenia`, `kseniya`, then the same four formant variants of
  `xenia`/`kseniya`. Rejected: prosody pitch x-low/x-high (worse voice, small difference),
  the stacked bigger/smaller combos, `baya`. This reverses the 2026-07-25 ear ranking on two
  points: `aidar` comes back as the second male voice, and `xenia` becomes the primary female.
- **Voice assignment = timbre matching (user, 2026-10-27).** Split speakers by gender; for k
  speakers of a gender take the first k voices of that gender's palette; assign them one-to-one
  so that the sum of squared timbre differences speaker ↔ dub voice is minimal (an assignment
  problem). Same for the female pool. The dominant speaker is no longer guaranteed the primary
  voice.
- **Timbre = (log median F0, log formant spacing ΔF)**, both standardized, equal weights; the
  same feature function runs on a speaker's spans of `source.wav` and on each palette voice
  (the palette side is a constant of the adapter). TitaNet is not used for matching (Findings).
  If assignments disagree with the ear on the test videos, re-weight first, keep the metric.
- **Plain sum of squares, NO speech-time weighting** (user): the assignment then depends only on
  the speaker's voice, so the same person recurring across videos of a series gets the same dub
  voice.
- **Gender for the voice pool: hard threshold at 165 Hz median F0, never `unknown`.** The
  translator's field keeps the `unknown` band (~155-185 Hz → impersonal constructions): the
  voice pool and the grammatical gender are two decisions over the same measurement.
- False split: a "speaker" under X% of speech time or N turns merges into the nearest by
  embedding; X and N come from the false-split run, every merge is reported.
- Palette lives in config as an ordered list of named variants (base voice + pitch + formant +
  EQ); the adapter applies them.
- Short backchannels stay their own unit in their own voice; overlap goes to the dominant word
  owner.

## Code map (2026-10-27)

- `overdub/stages/transcribe.py` — `resegment` (sentence records `{id,text,start,end}`),
  `_ends_sentence`, `_split_overlong`, `_merge_short` (`ok_prev`/`ok_next`), `class W`, words.json
  writers on both engine paths.
- `overdub/parakeet.py` — the worker; `overdub/asr.py` — `asr_key`.
- `overdub/repair.py` — its sentences loader keeps only `{id,text,start,end}`.
- `overdub/stages/synthesize.py` — `build_units` join condition; unit reuse keyed by `tuple(ids)`;
  manifest `units` and the single `"voice"`; `_legacy_key`.
- `overdub/tts/__init__.py` — `build_engine` (one voice per engine), `_VOICE_RATE` (all 5 stock
  voices, eugene the only well-measured one), `voice_rate`, `target_chars`, `synth_key`; `overdub/tts/base.py` — `synthesize()` has no
  voice parameter; `overdub/tts/silero.py` — `speaker=self.voice`.
- `overdub/pipeline.py` — engine cached per session by `_tts_key(cfg)`.
- `scripts/build_translation.py` — `build()` record shape, id validation;
  `.claude/skills/overdub-sonnet-batch/references/translate-contract.md` (rule 1
  "single-narrator"), `.claude/workflows/translate-batch.js`, `translate-chunks.js`, `.agents/`
  mirror; `overdub/stages/translate.py` `SYSTEM` (unimported).
- `overdub/stages/assemble.py` — `_write_srt`, `_ru_cue_rows`, `_degraded`.
- `overdub/runreport.py` — `flagged_units` row dict; `overdub/report.py` — `upsert`.
- `tools/renorm_workdir.py` — rewrites translation records.
- Host ffmpeg is built with `--enable-librubberband` and LADSPA (checked 2026-10-27).

## State

Diarization stage built; next is the read-only false-split run, then F0/ΔF. The five test videos
sit in `work/` transcribed and diarized, untranslated.
Voice-palette spike closed (ear pass done: all 12 palette voices accepted). Artifacts and scripts in
`work-exp/voice-palette/` (archive): `synth_palette.py` → `diff_check.py` → `make_listen.py` →
`embed_palette.py`, outputs under `2026-10-27/`.

## Findings

**Voice-palette spike, 2026-10-27** (30 `text_tts` sentences of `aVwxzDHniEw`, Silero v5_5_ru,
TitaNet-large cosine; every figure compares DIFFERENT-text pairs — same-text pairing inflates the
cross cosine and was discarded):

- **Silero levers.** `<prosody pitch>` works and keeps the duration sample-exact (eugene F0
  97 Hz → 76/79/115/128 Hz at x-low/low/high/x-high; kseniya 245 → 183/207/279/300 Hz).
  `intensity` 1/5 renders byte-identical to the default — no lever. `speaker="random"` is
  rejected by v5_5_ru. rubberband formant shift keeps F0 and duration. Consequence: every variant
  of a base voice inherits its `_VOICE_RATE` entry — no new rate measurement per variant.
- **Distance to the model.** Same-variant baseline 0.82-0.89. Two different stock voices:
  0.18-0.28 — strangers. Variants of one base, distance from the base: prosody pitch alone
  0.76-0.83, formant ±12% alone 0.67-0.72, pitch + formant stacked ("bigger"/"smaller")
  0.60-0.66. Post-processing makes a RELATIVE of the base voice, never a stranger: the strongest
  combo covers about a third of the gap to a different stock voice.
- **Palette consequence.** Two female speakers are covered by stock voices already (`kseniya` +
  `xenia`, both inside the ear ranking's acceptable set). Two male speakers is the real choice:
  `aidar` (a stranger, ear-rejected for accent) vs a eugene variant (a relative). kseniya's
  formant-shifted variants drift toward `baya` (0.37-0.40 vs 0.28 unshifted).
- **TitaNet is not a perceptual distance.** The user hears `baya` and `kseniya` as one voice;
  TitaNet puts them at 0.28, as far apart as eugene and aidar. It separates IDENTITIES, it does
  not rank how alike two voices sound — so it must not be the timbre metric of the assignment.

**Diarization probe, 2026-10-27** (`nvidia/diar_streaming_sortformer_4spk-v2.1`, the model card's
highest-latency streaming setting, the 5 test videos at 16 kHz mono, idle GPU; scripts and
outputs in `work-exp/diar-probe/`):

- **Speaker counts match the user's on all five** (2/2/2/3/4) once one artifact is merged:
  `N6FkmdL0Lg0` grows a third "speaker" of 0 s / 1 turn — the false-split case the merge rule
  exists for, met on the first multi-speaker video. `i-o5YbNfmh0`'s second speaker holds 7 s over
  6 turns: a real short-line speaker or a split, unresolved until the ear pass.
- **Cost:** 3.9-17.7 s wall per video (3.6-34.7 min of audio, model already loaded), peak
  allocated VRAM 0.90-2.07 GiB, growing with length. The 2 GiB matters: `transcribe` and
  `separate` already co-reside at 9930 of 12282 MiB (DECISIONS 2026-08-06), so diarization in the
  Parakeet worker must be measured in that co-residence, not alone.
- Audacity label tracks (`<id>/labels.txt`) are the fixture's starting point; the densest
  5-minute window of `z7cNbsr3b5s` (20 speaker changes) starts at 2:18.

**Pipeline run on the five test videos, 2026-10-27** (`--transcribe-only`, then `--only diarize
--force` after the island rule):

- **A re-download changes what the diarizer sees.** The pipeline's `source.wav` of `z7cNbsr3b5s` is
  not byte-identical to the probe's, and on it Sortformer grew a 4th label: 0 s, one segment, one
  word ("minis."). Same wav twice through the bridge reproduced the probe exactly (2 videos), so
  this is input drift, not nondeterminism.
- **Raw word assignment fragments sentences at overlaps.** Before the island rule: ≤2-word
  sentences 16 (`z7cNbsr3b5s`) and 57 (`hm8NzEd5io0`), most of them the speaker's own word handed
  to the listener whose "right" overlapped it ("correct all the | time.", "Mac | minis.",
  "does not look | like the"). Every false island started inside an UNFINISHED sentence; every
  real backchannel followed a finished one — the asymmetry `smooth_islands` keys on.
- **After the rule:** speaker counts 2/2/2/3/4 — all five match the user's; ≤2-word sentences
  0/0/2/6/11, and the 11 of `hm8NzEd5io0` read as real reactions ("Nice.", "Yeah.", "I see.",
  "Likewise.", "Thank you."). Diarize stage wall 2.4-10.4 s per video, worker load included on the
  first.

## Open questions

None outstanding — all clarified during planning.
