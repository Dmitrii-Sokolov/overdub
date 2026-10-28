# Multi-speaker dubbing

## Goal + AC

A video with several speakers is dubbed with a distinct Russian voice per speaker, and turns of
different speakers are never read as one sentence. A single-speaker video is voiced by its pool's
first palette voice: a male narrator comes out exactly as today, a female one in a female voice. This lifts the founding "single-speaker, no diarization" constraint (DECISIONS,
founding entry) — the lift itself is a `/triage` decision, not this task's.

Why: there is no `speaker` field anywhere in the pipeline. Sentence and unit merges ignore who is
talking, so on the panel `GDN3mPqJdvo` turns of different speakers are glued into one thought
(see `multi-speaker-detector.md`, Findings), one voice voices everyone, and the translator guesses
the grammatical gender of every first-person past verb.

## Frozen Spec

### Acceptance criteria

- **Single-speaker identity (male pool):** on the golden fixture videos plus 5 corpus videos
  with a male-pool narrator, `sentences.json`, `translation.json` and the dub are byte-identical
  with diarization on and off. The diarization wall on those runs is reported (expected
  negligible, user 2026-10-27).
- **Single female narrator:** a single-speaker video whose speaker lands in the female pool is
  voiced by the first female palette voice; with diarization off (or no `speakers_info`) every
  video keeps `tts_voice`.
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
- [x] **F0 + ΔF per speaker** (2026-10-27): `overdub/timbre.py` (pure numpy), written by the
  diarize stage into `diar.json` → `speakers_info` (words, f0_hz, delta_f_hz, pool, gender) for
  every video, single-speaker included. Absorbs `narrator-gender-f0.md`'s measurement; feeding
  `gender` to the translator is the contract item below.
- [x] **Fixture:** auto labels of `z7cNbsr3b5s` and `i-o5YbNfmh0` judged fully correct by ear
  (user, 2026-10-27) — `work-exp/diar-probe/<id>/labels.txt` stand as the reference, uncorrected.
- [x] **False-split run** over the corpus (2026-10-27, read-only) — see Findings; it replaced the
  Q8 threshold with identity linking.
- [x] **Windowed diarization + identity linking:** diarize fixed windows (bounded VRAM), link
  speakers across windows and merge same-identity labels by TitaNet embedding cosine; calibrate
  the threshold on the interview channels (two-person episodes must come out as 2).
- [x] **Speaker change = hard boundary** in resegment and `_merge_short` (`_split_overlong` runs
  inside a same-speaker range by construction).
- [x] **Same boundary in `build_units`** — `speaker` in `translation.json` is copied from
  `sentences.json` by `scripts/build_translation.py`.
- [x] **Per-unit voice:** `voice=` per `synthesize()` call (`overdub/tts/silero.py`
  `shift_formants`); palettes `voice_palette_male` / `voice_palette_female` in config, timbre
  table `VOICE_TIMBRE` in `overdub/tts/__init__.py`; assignment `overdub/voices.py`
  (`assign_voices`, Q22 inserts); `speaker` + `voice` per manifest unit, reuse and `done()`
  compare the voice per unit.
- [x] **Translator contract:** `speaker` comes in on `sentences.json` records, `gender` from the
  head of `diar.json` (`speakers_info` above `segments`, kept there by
  `test_speakers_info_sits_above_the_segments`); contract rule 1 lost "single-narrator", rule 9
  sets the grammar of a speaker's gender (`unknown` → wording that marks none, else the text,
  else masculine); same in both workflow prompts, `SYSTEM` and the `.agents/` mirror.
- [x] **Subtitles + reporting:** `assemble.turn_marked` opens a sentence that changes speaker
  with "— " (`text_ru`) / "- " (English) on every srt path, degraded ones included — display
  only, the artifacts keep their text; `run.json` → `diarize: {speakers, merges}` (None when not
  diarized), `speaker` on the `flagged_units` and `summarize_offenders` rows.
- [x] **Nothing drops the field:** `repair.repair_window` gives the window's new sentences the
  speaker of the run they replace and rejects a window across a speaker change before decoding
  ("spans a speaker change": its reading is resegmented with no turn boundary);
  `tools/renorm_workdir.py` copies `diar.json`, translation records were already copied whole.
  The degraded assemble path reads records that carry `speaker` (`turn_marked`).

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
- ~~Gender for the voice pool: hard threshold at 165 Hz median F0~~ — superseded the same day
  (user, after a man measured 176 Hz): **outside 150-200 Hz F0 decides; inside it ΔF does**
  (pool split at 1075 Hz, never `unknown`; the translator's gender is `unknown` between 1040 and
  1110 Hz). Voice pool and grammatical gender stay two decisions over the same measurement.
- **`diarize` stays on by default** (user, 2026-10-27), with the false-split finding known: a
  re-run of an old workdir re-cuts its transcript when speakers are found.
- **Short inserts get a voice too** (user, 2026-10-27): a speaker under 3% of the words is not a
  participant but is another person — it takes a palette voice after the main participants, and
  when its gender's palette is exhausted it speaks in the voice of the main participant closest
  in timbre.
- **A single speaker goes through the same assignment** (user, 2026-10-27, Q23): a female-pool
  narrator gets the first female palette voice; the old "single-speaker byte-identical" AC holds
  for the male pool only, whose first voice is `tts_voice`. `tts_voice` stays the voice of a
  workdir with no `speakers_info` and of a unit whose sentence has no `speaker`.
- **Timbre standardization** (user, Q24): each feature divided by its spread over that pool's
  palette voices — a constant, so a speaker's voice depends on their own timbre only.
- **Unmeasurable speaker** (user, Q25; no voiced frames, `pool: None`): male pool, takes the next
  free voice after the measured speakers, no timbre cost.
- **Where synthesize reads the speaker** (user, Q26): `translation.json`, into which
  `build_translation.py` copies it from `sentences.json` by id; the translator never writes it.
- **Q8 replaced:** no word-share merge threshold; speakers are linked by identity (TitaNet
  embeddings) across fixed windows, which also bounds VRAM on long audio (user agreed).
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

Every plan item built. Open against the AC: the single-speaker identity run (golden fixture + 5
male-pool corpus videos, diarize on vs off), boundary accuracy on the fixture video as a number,
and a route-B run on the five test videos (rule 9 and the full dub by ear). The
five test videos sit in `work/` transcribed and diarized with `speakers_info`, untranslated — a
route-B run on them is the first check of rule 9 and of the full dub by ear.
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

**Timbre measurement, 2026-10-27** (`overdub/timbre.py`; scripts `work-exp/voice-palette/
timbre_*.py`, `work-exp/diar-probe/timbre_videos.py`):

- **Validated on an exact scaling** (the same audio read at ×0.88 / ×1.12 its sample rate): F0
  within 1%; ΔF within 1-5% male, 2-3% female once the LPC ceiling follows the pool (5000 / 5500
  Hz). A single 5000 Hz ceiling read kseniya's ×1.12 as ×1.027. The first F0 version read
  eugene at x-low pitch (76 Hz) as 156 Hz — an octave error fixed by the window-autocorrelation
  correction and a 3-period frame.
- **rubberband's formant shift is about half its name** on this scale: eugene ×0.990 / ×1.059,
  kseniya ×0.968 / ×1.052, and for aidar / xenia the ×0.88 variant even measures ABOVE its base
  (×1.033 / ×1.032). Within one voice family ΔF differences sit inside the estimator's error, so
  matching among a base and its formant variants is effectively arbitrary (deterministic). Across
  bases ΔF carries signal: xenia 1085 vs kseniya 1252 Hz.
- **Palette** (F0 / ΔF Hz): eugene 95 / 953, aidar 129 / 943, xenia 203 / 1085, kseniya 254 / 1252.
- **Test videos:** every speaker lands in a pool; `9GtcbnmldcY` speaker 0 reads 176 Hz — female
  pool, `unknown` grammatical gender (inside the 155-185 band). `hm8NzEd5io0` is four male
  speakers (110-142 Hz), i.e. it needs four voices of the male palette.
- **F0 alone misplaces a high male voice.** User, 2026-10-27: `9GtcbnmldcY` speaker 0 is a man;
  he measures 176 Hz (autocorrelation) and 172 Hz (cepstrum, independent) — real, not an octave
  error — while his ΔF, 922 Hz, is the most male of all. Male ΔF over the test videos 922-1037,
  the one real female 1169, palette female 1085-1312: ΔF separates where F0 overlaps.

**False-split run over the corpus, 2026-10-27** (122 videos with words, 163.9 h, read-only;
`work-exp/diar-probe/false-split-2026-10-27.jsonl` + raw segments beside it):

- **91 of 122 "single-speaker" videos come out multi-speaker after smoothing**, 72 of them with a
  minority of ≥10% of the words. By length: 0-15 min 26/45 (17 ≥10%), 15-60 min 10/14 (2),
  60-120 min 24/30 (23), 120-240 min 24/26 (23), >240 min 7/7 (7). A word-share threshold cannot
  be the merge rule: false and real minorities both reach 25-45%.
- **The corpus is NOT single-speaker — it holds two interview channels.** Lex Fridman 27 of 27
  multi-speaker, Dwarkesh Patel 36 of 39: 63 of the 91. The single-voice channels are the real
  negative set and stay low: GOG Classics Vault 0/6, Claude 1/8, Steve (Builder.io) 3/12.
- **Similar timbre does not mean one person** (retracted the same day). Near-identical F0/ΔF
  across a split was read as "one voice split after an intro"; the user's ear put a real second
  speaker at every one of the four places checked — `9TU0XjJqpOg` @1:27, `1fmcdz2EO_c` @0:44 (a
  short line over the first speaker's monologue), `NNr6gPelJ3E` @0:54, `frYSOKvNiiE` @0:06 (an
  inserted news clip). Two men at 108 and 110 Hz are two men.
- **The real false split is over-counting in long interviews.** A two-person interview comes out
  with 3-4 speakers — 4 on 14 of the 27 Lex Fridman videos — i.e. streaming Sortformer loses a
  voice's identity over hours and opens a new label for it. Identity linking (TitaNet across
  windows) is the fix, not a size threshold.
- **Calibration set** (`work-exp/diar-probe/calibration.tsv`, built by `calibration_template.py`):
  the interview and single-voice channels with an expected count — host + guests named in the
  title, solo essays 1 — every prefilled value confirmed by the user, the unreadable ones settled
  by ear; 3 videos have no single right count (a crowd, distorted voices, inserted clips) and are
  not scored. **Raw diarization on the 85 first scored: exact 40, over 45, under 0** — the error
  runs one way, so an identity merge, which can only lower a count, aims straight at it.
- **Identity merge, whole-file segments, 2026-10-27** (`identity_embed.py` on CPU → 
  `identity_sweep.py`; per smoothed speaker up to 12 × 3 s TitaNet chunks spread over the whole
  video, agglomerative merge on centroid cosine): of 89 scored videos, **exact 41 → 73**. Plateau
  at 0.45-0.55 (73 exact, 13-14 over, 2-3 under); recall drops on both sides (0.30: 64 exact, 16
  under; 0.85: 62 exact, 26 over). **0.45 chosen**: same score as 0.50, and the costs are not
  symmetric — an over-split changes one person's voice mid-video, an under-merge gives two people
  one voice, which is what the pipeline did before.
- **Counting only main voices (user: inserts are short) moves it to 85 of 89.** The table counts
  participants; a news clip or a quoted guest is a real voice but not one. Counting a merged
  group only at ≥3% of the video's words: thr 0.55-0.70 → **85 exact, 2 over, 2 under** — a wider
  plateau than without the share, so **0.60 / 3% supersedes 0.45**.
- **Two of those four misses were the table's** (user, by ear: `8-boBsWcr5A` 3, `ctsHqR2vtWQ`
  2). Rescored: **87 of 89 exact, 0 over, 2 under** at 0.55-0.70 / 3%; the setting does not move.
  The over-split class — the costly one — is gone on this set. What is left is under-merging in
  the two longest panels (~5 h, the user's counts are lower bounds): `_1f-o0nqpEI` 83/17%
  (≥3 expected), `ugvHCXCOmm4` 52/24/24% (≥4). No threshold buys them back for free — 0.80
  recovers one and reopens two over-splits.
- **Cost: 12.4 s of diarizer per audio hour** (33.8 min over 163.9 h) — negligible beside
  transcribe, which answers the Q3 cost question.
- **VRAM grows ~5 GB per audio hour and has no ceiling**: peak 1.2 GB (<15 min), 6.2 GB (<2 h),
  10.8 GB (<4 h), **20.2 GB on a >4 h video — past the 12 GB card**, i.e. the WDDM spill-to-RAM
  regime the Parakeet worker documents (no OOM, a twentieth of the throughput). Long audio needs
  chunking before this stage can run unattended on the corpus.

**Windowed diarization + identity linking in the worker, 2026-10-27** (`scripts/parakeet_worker.py`:
equal windows of ≤1200 s, labels `w<k>:<spk>`, TitaNet linking at 0.60; then the stage's own
assign → smooth → renumber and `MAIN_SHARE` 3%; `work-exp/diar-probe/calibrate_windowed.py`, output
`calibrate-windowed-2026-10-27.jsonl`, idle GPU):

- **88 of 89 exact, 0 over, 1 under** (with the table fix below) — the whole-file + merge baseline
  was 87 / 0 / 2. Both
  long-panel under-merges (`_1f-o0nqpEI`, `ugvHCXCOmm4`) now come out right at the same 0.60 / 3%;
  why was not isolated.
- **The one miss was the table's, and turned into an under-count.** `9V6tWC4CdFQ` (table 2) gets a
  third main voice at 7.7% of the words, 12 runs between 1:52:01 and 2:09:04, the first opening
  "Hey Lex, my name is Andrew. I lead the Google Beam team". User, by ear: 4 or more participants,
  a 4th from 2:02 — table corrected to 4. The 2:02-2:09 runs sit in the same group as Andrew's, so
  rescored the set is **88 exact, 0 over, 1 under**: two guests sharing one voice, the cheap error
  direction.
- **Re-run on the five test videos** (`--only diarize --force`): speaker counts still 2/2/2/3/4;
  `z7cNbsr3b5s` and `hm8NzEd5io0` were re-cut (untranslated, nothing lost).
- **VRAM is bounded: peak 1.6 GB** over the set (whole-file: 20.2 GB). **Cost 14.1 s per audio
  hour** (whole-file 12.4 s; the difference is the TitaNet pass and per-window model state).

**Per-unit voice, 2026-10-27:**

- **A real Silero render keeps duration sample-exact through the formant shift** (one sentence,
  v5_5_ru, 48 kHz): eugene and eugene+formant=1.12 both 250200 samples, F0 95.6 / 95.9 Hz, ΔF
  931 → 995 Hz; xenia and xenia+formant=0.88 both 291600 samples, ΔF 1055 → 1175 Hz — the 0.88
  variant reads ABOVE its base again, as in the spike.
- **Assignment on the five test videos** (F0/ΔF Hz, word share → voice):
  `i-o5YbNfmh0` 108/951 97% → eugene, 130/979 insert → aidar;
  `N6FkmdL0Lg0` 103/989 84% → eugene, 120/1000 16% → aidar;
  `9GtcbnmldcY` 176/923 81% → aidar (the high male voice), 108/1037 19% → eugene;
  `z7cNbsr3b5s` 191/1170 16% → xenia, 105/943 57% → aidar, 101/944 27% → eugene — the two men
  are 4 Hz apart, so which of them gets eugene is decided by noise;
  `hm8NzEd5io0` 110/967 → eugene, 136/936 → aidar, 142/1043 → eugene+formant=1.12,
  124/944 → aidar+formant=1.12.

**Boundary accuracy, 2026-10-28** (pipeline `sentences.json` speakers vs the ear-approved
`work-exp/diar-probe/<id>/labels.txt`, a sentence scored by the reference speaker covering most
of it, labels mapped one-to-one; the two wavs differ by 0.04 s in length):

- `z7cNbsr3b5s` (394 sentences, 3 speakers): **98.5% of words** (384 sentences) carry the right
  speaker; 1 sentence holds a second reference speaker for ≥ 1 s; of 56 reference turns
  (segments ≥ 1 s) 50 have a pipeline speaker change within 0.5 s. `i-o5YbNfmh0`: 100%, 2 of 2
  turns.
- **The miss is the windowed diarizer, not the cut:** 6 of the 10 wrong sentences are one
  stretch, 386-408 s, where window 0 labels the second man as the first (`w0:speaker_1`) and
  switches to him only at 408 s; the whole-file probe has him from 386.6 s. The two men are 4 Hz
  apart (Findings above).

**Turn dashes, 2026-10-28:** on `z7cNbsr3b5s` (394 sentences) the English degraded track gets
65 dashes for 65 speaker changes.

## Open questions

None outstanding — all clarified during planning.
