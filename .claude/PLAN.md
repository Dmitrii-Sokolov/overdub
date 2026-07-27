# PLAN

Forward-looking only. Measurements retire to CHANGELOG, rationale to DECISIONS; if an item here
carries more than the evidence needed to decide it, cut it.

**Admission rule: an item must change the TOOL.** Repairing one video is never an item — the
deliverable is the pipeline and a broken shipped MKV is a signal about it, not a ticket
(DECISIONS 2026-07-25). A finished video is touched only for a measurement that generalizes, and
then the improved artifact is a by-product. If a proposed item makes exactly one video better and
returns no number, no flag distribution, no ear verdict and no fixture, it does not belong here.

Items are NAMED, not numbered — the
numbering was re-cut with every roadmap while code references stayed put, so "PLAN item 1" meant
four different things by 2026-07-22 (DECISIONS 2026-07-22). Do not reintroduce it.

## Where the project stands

Route C (scout) is in daily use and works end to end. Route B (Sonnet dub) is the primary dubbing
route; a 24-video batch shipped 2026-07-25 with zero crashes and the seven fixes it earned are in.
**A 7-video route-B batch shipped 2026-07-26 — the first corpus at the SHIPPED engine and
grouping** (Silero v5_5_ru, 1.2/20/600, `atempo_floor` active): 7 of 7 muxed, 2 need a listen
(1 actionable flag each), batch max combined factor **1.22** — no unit anywhere near the 1.8 bar —
per-video fill medians 0.79-0.95 over 6 videos, and 97.1 s of slot silence against 3349 s of dub.
It closes the corpus precondition under "Numbers to re-measure" (D). One of the seven was an
instrumental with no speech and it went through untouched (route-B skill, step 1). **A second
route-B batch (5 videos, "Test 2") followed the same day** on the corrected skills: the queue rule
and the no-speech rule both held, and `work/queue-prev.txt` shows the overwrite ran instead of a
question. `NGOAUJtdk-4` fills only 0.71 of its slots with 48.5 s of silence in a 447 s dub. Eleven
unique videos now exist at the shipped config; that is a sample, not a baseline (see (D)).
**Both batches were listened to end to end and are fine** (user, 2026-07-26 and 2026-07-27) — the
ear is the instrument that adjudicates quality here, and it has now passed the shipped config
twice. That verdict is also what demoted `neg_loss` (DECISIONS 2026-07-27): re-scored, the two
batches need **0 of 7 and 1 of 5** listens, not 2 and 4, and the single survivor is a real verify
defect rather than a detector artefact.
Silero v5_5_ru is the ONLY engine since 2026-07-25 — **ear-confirmed on finished videos, quality
sufficient** (DECISIONS 2026-07-25 later). What the switch cost is timing: Silero has no
`supports_target`, so fitting speech to its slot is now the pipeline's job — half done since
2026-07-25 (`atempo_floor`), and no longer a blocker: see Open.

**Before the next dubbing batch** — one standing caveat, not a bug: `_title_of` is a networked
`yt-dlp --print title` (30 s timeout) for pre-2026-07-20 workdirs; in the finish sweep those queue
back-to-back — an offline resume of 12 videos can sit ~6 min in one block at the very end.
(The unconfirmed C→B promotion moved out of this block into Open on 2026-07-27 — it is work, not a
caveat.)

**`work-exp/` is not an archive and has already lost data once.** `context-earcheck/`,
`stats-batch/` and `gemma-ab/` NO LONGER EXIST (only `nfe-sweep/`, `nfe16/`, and the 2026-07-2x
cells remain): the Qwen-vs-Gemma A/B set and the 8/23 stats-batch workdirs are gone, the published
A/B report artifact (508 sentences) is the only surviving record of that comparison, and the
stats-batch URL list is unrecoverable. The route-C baselines under `work-exp/wave-*-2026-07-21/`
are live — **a re-run of that 6-video queue overwrites the artifacts, so copy the six `scout.json`
before repeating it.** Decide what in `work-exp/` is a consumable and what is an archive before the
next disk cleanup makes that call for you.

**Carried into the next ordinary batch** — look at these when they pass by, they are not gates:
`--repair-asr auto`'s fixture recall (5/12) and the `RyvXxApfHkk#11` 246-vs-35.9 ch/s discrepancy are
unreconciled (DECISIONS 2026-07-20, provenance); listen to a repaired unit in a finished MKV once —
repair moves a TTS unit boundary, so `atempo` on that unit moves too, and that is a property of the
step, not of the video; the `Tu2cCEMwvHI` 116.7 s download outlier is
undiagnosed (6-13 s for the rest of that queue); on a route-B run check `needs_triage` — after the
2026-07-27 demotion the two shipped-config batches re-score to 0/7 and 1/5, so the next batch is the
first one whose rate is measured rather than re-scored; if it drifts back toward N/N, look at what
is padding it before adding a detector — and the `- pronounce:` line (ranged 9..248 per video; a video near 200 names the tokens the
dictionary still lacks).

## Open — ordered by value, re-cut 2026-07-27

**There is no blocker.** The previous ordering opened with "the first is the blocker"; the stretch
branch shipped 2026-07-25 and the ear then passed the shipped config on both 2026-07-26 batches, so
nothing below gates a batch. Document order IS the priority order, it is a VALUE order, and the
next measurement is allowed to overturn it.

**Slugs, not numbers** (DECISIONS 2026-07-22 — the numbering had crept back in and is removed
again). Retired aliases are noted once per item so an old reference resolves; do not reuse them.

### Name list at ASR — the proper-noun class

`model.transcribe` passes neither `initial_prompt` nor `hotwords` today
(`stages/transcribe.py:385`). Measured 2026-07-26: `vLIDHi-1PVU` ("Designing Claude Code") came
back with **16 × "Cloud" and 0 × "Claude"** at large-v3/fp16/beam 5 — so DECISIONS 2026-07-20's
proper-noun class is not a beam-1-only artifact. Fixing it at the translate seam is possible but
partial and expensive: it needs a `src` flag on every normalised record, it makes 27 of 28
`entity_loss` offenders false, and it cannot reach `en.srt` at all (not re-timed by design,
`assemble.py:199` — one MKV shipped with 15 × "Cloud" in EN subs against 35 × "Claude" in RU). A
name list closes all three surfaces at once. **First here because it is the only known defect that
survives into a finished MKV and cannot be reached from any later stage.**

**Conditions, non-negotiable:** it changes source text, so it goes into `asr_key` beside the beam;
and it is adopted only off `asr_probe.py --variant` on the six fixtures, never because it reads
well — an `initial_prompt` also biases decoding elsewhere in the transcript, which is exactly what
the probe measures. Open sub-question before any code: where the names come from (video title +
channel are free and on disk; a per-queue list is an operator step). Rationale: DECISIONS 2026-07-26.

### Promotion C→B, confirmed once *(was a pre-batch caveat)*

**One promotion end to end is still unconfirmed on real media.** Promotion = the SAME videos going
through route C and then route B: scout writes `sentences.json` and only `source.wav`, the human
trims the queue, the dub run then has to (i) fast-skip `transcribe` — the whole economic point, or
scouting pays for large-v3 twice — and (ii) re-run `download`, because the final MKV needs
`source.mkv` and scout never wrote one. Every run so far has been route C **or** route B, never
C-then-B on one video, so neither half is observed. Confirming it costs one small queue: scout 2
videos, dub the same 2, then read their `run.json` — `timings.stages.transcribe` near zero and
`download` clearly non-zero is the pass. It is this high because both daily routes already depend
on it working and nobody has looked.

### Sonnet budget per batch

Route B spends 2 sub-agents per video (translator + summarizer), route C one, and the price is
visible NOWHERE — not in `run.json`, not in the digest, not in the report. **This is the scarce
resource now that disk is not**: machine time is not the bound either (3 h 16 m of work for 24
videos), and the 2026-07-27 disk re-measurement removed the only other stated ceiling. An estimate
per video (agents × tokens) and a share of the weekly limit per batch would make "does a 100-video
queue fit in a week" arithmetic instead of a surprise at #60.

### Slot fit — size the translation to the slot *(was item 1(a))*

**The fit is TWO-SIDED** (re-framed 2026-07-25, user call). The original framing ("Silero
under-fills, translate longer") did not survive reading the corpus: on 3 of the 5 videos in
`work-silero-v5` Silero **over**-runs its slots (raw/slot medians 1.023, 1.145, 1.017; 16/30,
19/31, 21/37 units under atempo), on 2 it under-fills (0.791, 0.816), and 0.73 was one video's
SOURCE pace, not an engine property. What is missing is a duration model in either direction. The
engine side is a usable constant because Silero's rate is stable (CV 5.5%), but it is **per VOICE,
not per engine**: eugene 18.8-19.5 ru ch/s against baya 14.4, aidar 14.9, kseniya 15.5, xenia 17.8,
so the knob keys on `tts_voice`.

**Two thirds of this item already shipped** — ru.srt follows the dub and underfill is measurable
(2026-07-25, CHANGELOG; the numbers live in "Numbers to re-measure" (A)), and `atempo_floor` = 0.75
cut slot silence 283 → 84 s on `8zJlKmgMT44` in assembly alone. What is left is the polish that
removes the 84 s residue and the audible stretch on the 42-of-69 units pinned at the floor. Ranked
below the three above because the ear has now passed twice without it.

Target chars = slot ÷ the voice's rate (`tts.target_chars`, shipped); `atempo` trims the remainder.
Obstacles, all confirmed in code: (i) ~~`atempo` <1 does not exist~~ **BUILT**
(`assemble._tempo_for`); (ii) **the `runaway` gate fights the target** — `_is_bad` caps `text_ru`
at `translate_max_len_ratio=3.0 × len(src_en)`, so for any source slower than ~6.3 en ch/s the
CORRECT length is flagged, costing up to 4 reseeds and in the limit shipping `src_en`, i.e. English
into the dub; re-anchor it on the target, not on the source length; (iii) **the length rule lives
in 4 hand-synced copies** (`translate.py:SYSTEM`,
`skills/overdub-sonnet-batch/references/translate-contract.md`, that skill's `SKILL.md`,
`README.md`) and route B's prompt is assembled by an agent at runtime — a target has to reach BOTH
routes, so compute it in a shared helper that `translate.py` and `scripts/build_translation.py`
both call, and enforce/report it in the latter or route-B compliance is unverifiable; (iv) **the
route-A resume key ignores timings** (skip is `done[sid]['src_en'] == s['text']`), so after
`--repair-asr` a translation sized for a slot that no longer exists is silently kept.

### Input prosody — punctuation and SSML *(promoted from Backlog 2026-07-27)*

The cheapest unpulled lever in the file, and the one that answers "the dub is fine but it reads
flat". `docs/russian-tts-guide.md` attributes ~70% of prosody quality to the INPUT and names flat
ASR+MT punctuation as the main cause of monotony — exactly our input shape. Silero accepts SSML
(`<speak> <p> <s> <prosody> <break>`) while the adapter sends plain `text=`; `<p>`/`<s>` alone give
pauses and a contour reset. Two cautions before any code: `text_tts` is Cyrillic-by-contract
because Silero DELETES Latin script, so markup has to be proven not to trip that; and verify
compares against `text_tts`, so tags must be stripped on the comparison side exactly as stress
marks already are. Judged by ear, like everything else in this half of the list.

### Phoneme transliteration from CMUdict *(was item 2)* — blocks the stress audit

The letter rules guess from spelling what the dictionary knows phonetically: `buy → буи` vs
`B AY1`, `fields → фиелдс` vs `F IY1 L D Z`, `update → упдейт` vs `AH0 P D EY1 T`, `execute →
эксекют` vs `EH1 K S AH0 K Y UW2 T`. An ARPAbet→Cyrillic table is ~39 phonemes against ~55 letter
rules — smaller AND more accurate. Coverage over the corpus's invented tokens: 79% of types, 77% of
occurrences; the absent tail is brands and neologisms (`mcp`, `anthropic`, `vercel`, `shadcn`,
`tmux`), so the letter rules STAY as the out-of-dictionary fallback. This is also what closes the
open-class residue the ~55-rule ceiling made awkward: `execute → эксекют` (18 hits), `adventures →
адвентурс`, `fields → фиелдс`, `open → опен`, `waters → вейтерс`, `buy → буи`. A rule on
`ex-`/`ie`/`-ute` is ambiguous in English ("exit" wants экс, "execute" wants эгз) — hence the
dictionary, not another rule. Needs an ear check either way.

### Stress audit of the dictionary *(was item 4)* — gated on the item above

Using `stress_index`/`apply_stress`; English stress wins on disagreement (user call). Of the top 60
invented tokens only 10 disagree with Silero's own stress and half of those would mark an
already-broken transliteration (`execute → +эксекют`), so accenting first entrenches the defect.
Needs an EAR pass — 34 of 60 automatic stresses were already correct, where a mark is pure noise in
the data. The mechanism shipped 2026-07-25 (marks honoured, verify strips them, CMUdict in-repo);
this is the content pass.

### Voice post-processing *(was item 3)*

Compression/EQ for a brighter, more attractive timbre. `assemble` has only `lowpass` today (Silero
vocoder hiss), no dynamics. Candidates: `acompressor`, `adynamicequalizer` (2-4 kHz presence lift),
`speechnorm`, `loudnorm` by LUFS at the end instead of peak normalization. Same chain, after
verify. Judge by ear — metrics do not adjudicate this. Below the input lever on purpose: the guide
puts the input first, and an EQ chain applied to flat delivery is polish on the wrong layer.

### Re-time the batch on Silero *(was item 5)*

"Synthesize dominates" is F5's shape, not Silero's — see "Numbers to re-measure" (B). Do it after
the slot-fit item lands, or the numbers describe a pipeline that is about to change.

## Also open — independent, none of them ordered against the list above

- **Feed `src != ok` from `translation.json` into `repair.seed_ids_from_detectors`** (user-selected
  as the next step, 2026-07-25). The one defect class NO detector sees by construction: a clause
  repeated INSIDE one sentence. Measured on `8zJlKmgMT44` (audible repeats at 3:22 and 9:53): `#44`
  repeats "and the subtle ways that they can affect our behavior" at a normal 18 ch/s, `#105`
  repeats "we had to move stuff around…" plus a stump in a 1.50 s slot. `dup_adjacent` compares
  NEIGHBOURS, `rate_implausible` needs a timing anomaly — both blind. Only the translator's reading
  pass caught them (`src=garbled`), and that signal is printed and dies. Constraint: seeds are read
  BEFORE translation (`auto --batch` on a fresh transcript is the normal case), so src-seeds can
  only ever be an ADDITIONAL source when `translation.json` already exists.
- **Sentence rebuild loses endings — ours, not whisper's.** 166 of 388 source anomalies are
  `truncated`, clustered in live Q&A where whisper emits no terminal punctuation (`2qrzI8YCVgI`,
  `Tu2cCEMwvHI`). Same root, second symptom: `aVwxzDHniEw#67` = "is the derivative of a Bezier
  curve?" in a 1.06 s slot — one sentence cut in half by the rebuild, and `rate_implausible` does
  not fire (36 ch/s against a 40 bound). Repair cannot help either by construction; only re-joining
  at rebuild can. Distinct from the 143 `garbled` / 60 `dup_neighbour`, which really are whisper's.
- **Clean `work/<id>/` after a successful mux — hygiene, NOT a queue-size lever.** Delete BINARIES
  only (`source.mkv`, `source.wav`, `source_bed.wav`, `dub_ru.wav`, `segments/`); json/md are
  pennies. Transcript, translation and summary survive; the cost is re-synthesis of everything
  downstream. `out/` holds a second hardlink so the result survives on its own. **Blocker inside
  it:** mux's input must move `source.mkv` → `output.mkv`, or a re-mux needs a re-download.
  **The disk argument this item used to carry is dead (2026-07-27):** it cited 81 GB free from
  2026-07-20; D: now has 418 GB free against a 30 GB `work/`, so nothing about queue size is
  bounded by disk today. Re-measure free space before ever reviving that claim.
- **Recalibrate the floor CHAIN, not the ratio.** `floor_ratio ≥ 0.085` fired on nothing (batch max
  0.070) while two videos had visible collapses; `floor_longest_run ≥ 40` separates exactly those
  two and nothing else, and now drives a digest hint (2026-07-25). `config.py`'s own comment admits
  the ratio is "knowingly unreliable" for borderline detection. `transcribe._guard` still gates on
  the ratio — recalibrate off the accumulated series, as that comment asks.
- **Timing detail for the four remaining stages.** `download`, `verify`, `assemble` and `mux` report
  no `detail`, so `work_complete` stays False on a real run and `total_work_s` is an UPPER bound.
  The mechanism shipped 2026-07-22 (+ `separate` 2026-07-24); this is one measurement pass, not
  code design. Add it when a real batch makes the calls worth it.
- **S2 artifact route — workable but not settled.** Sub-agents are blocked from the Write tool; the
  prompt now plainly instructs writing the two artifacts with PowerShell and handing content back if
  refused. (a) The fully compliant shape is "sub-agent returns, caller writes" — run 6's recovery
  ran it end to end; its cost is that the caller GENERATES ~3-4k chars per video at ~8.5 s/1000
  chars, so six videos add ~200 s to a 200-600 s wave. Worth measuring against
  `work-exp/wave-run{4,5}-2026-07-21/` rather than assuming. (b) Structured return via a schema has
  a known failure mode — long string fields abort the run after data is on disk
  (`~/.claude/knowledge/claude-code/agent-orchestration.md`) and `paragraph` runs to 1500 chars. Do
  not reach for it without re-reading that note. Until decided, an occasional classifier stop is a
  respawn, not a reason to reinstate any instruction about what is blocked.
- **Repair-window `hotwords` / `initial_prompt` — last on purpose.** Fixes the one confirmed
  regression from the 2026-07-20 ear check (DECISIONS 2026-07-20 explains why this does not reopen
  the repetition loop); available in faster-whisper 1.2.1, verified; word-list sources cheapest
  first (the video's own out-of-window sentences, then `pronounce_audit.json`); measure on the
  golden fixture. `--repair-asr` shipped at 5/12 recall with a proper-noun regression, so the open
  question is whether the feature earns more investment at all — that ranks below every item serving
  a route in daily use.

## Numbers to re-measure

Three groups, three different reasons. **Do not quote across a group boundary.**

**(A) `8zJlKmgMT44` — re-measured on Silero; the F5 half is RETIRED, not owed.** Silero at the
shipped 1.2/20/600, measured 2026-07-25 with the new metric: **fill median 0.7104, slot silence
283.1 s** of a 1058.8 s dub (`in_span_silence` reads 241.8 s on the same run and understates by
41 s — it excludes the inter-unit gap). **Quote these, not the old pair.** The F5 side (0.90 /
124 s at grouping 0.4/12/300, and the older cross-engine 136 units / 224 s vs 47 s) is **dead
weight, dropped 2026-07-26 (user call)**: this file used to carry "needs an F5 arm at 1.2/20/600
or it stays uncited" as an open debt, but the only question that comparison could answer — which
engine ships — was decided on 2026-07-25, so nobody will ever run that arm. F5-era figures are
HISTORY: cite them as F5's if a revival ever needs them (see "Deferred — the F5 path"), never
beside a Silero number, and never as something still to be measured.
**Retired, do not re-quote: "17 units at cf ≥ 1.8, up to ×12.5".** Recomputed over all of `work/`
2026-07-25: **7 units of 3575, worst 2.63** (12 SENTENCE rows — the two counts were being mixed,
and the ×12.5 was one sentence's pre-repair `speed_factor`).

**(D) Everything measured on `work/` BEFORE 2026-07-26 is F5 at grouping 0.4.** Those 36 manifests
report `engine=f5`, `group_gap_max=0.4` — so every compression, slot and unit-count figure derived
from that corpus describes the OLD engine at the OLD grouping, and the boundary is now a DATE, not
the directory. **The gap is closed on the corpus side:** the 7-video batch of 2026-07-26
(`sHImlfVM9r4`, `Yiy0cU6ChSw`, `NfoFdsc2ODQ`, `VHRhSDawKVA`, `CeotyuztIkg`, `FpOAn6Dh44k`,
`kSl2mxseXkM`) is Silero at the shipped 1.2/20/600 with the floor active — first reading: max
combined factor 1.22, per-video fill medians 0.79-0.95 (6 videos; the instrumental has none),
slot silence 97.1 s over 3349 s of dub. **The second batch the same day
(`02nFRuEo0bc`, `vLIDHi-1PVU`, `NGOAUJtdk-4`, `005JLRt3gXI` + a repeat of `NfoFdsc2ODQ`) already
moved every one of those figures:** fill medians 0.71-0.95, max cf 1.20. Eleven unique videos total.

**Triage rates from these two batches are RE-SCORED and the old pair is retired (2026-07-27).**
"2 of 7 and 4 of 5" were measured with `neg_loss` still actionable; under the shipped classifier
they are **0 of 7 and 1 of 5** (DECISIONS 2026-07-27). Do not quote the old pair, and do not treat
either as a rate — a 12-video sample cannot carry one.

**This is a sample and not a baseline, and the rule that follows from it:**
do not derive a threshold, a population share or a "typical" value from it. The fill medians are
PER VIDEO and cannot
be averaged across videos (a 5 s instrumental and a 35 min talk carry one slot each in that list
and are not comparable), and none of it is quotable beside an F5-era number.

**(B) F5-era batch shares are void on the Silero path.** synthesize 47.6% · transcribe 21.3% ·
download 9.8% · verify 8.3% · mux 7.9% · separate 4.9%; batch RTF 0.451 (7.26 h → 3.27 h); the
2026-07-24 36-run split (synthesize 52.6 + verify 7.6 + mux 7.4 + separate 4.8 = 72.7%); and the
"3.3 h → ~1.9 h, RTF → ~0.26" projection, which extrapolates one video to a batch. Closed by
"Re-time the batch on Silero".

**(C) Wall-clock contaminated — anything derived from `timings.json` stage walls before
2026-07-22.** The ~72 s/video fixed cost, the Silero-vs-F5 whole-pipeline RTF pair (0.14-0.17 vs
0.70-0.92 from the 2026-07-19 audition), and every `breakdown_pct`. Re-derive from `rtf_work` on the
next pass. **NOT contaminated, contrary to an earlier claim in this file:** `nfe` 48→16 = 2.16× —
`scripts/exp_nfe_sweep.py` times each cell around `engine.synthesize` alone and records worker spawn
separately as `startup_s`.

## Backlog

**Throughput / weaker hardware.** With TTS fast on CPU and the GPU idle during synthesis, the
remaining GPU load is whisper-large (transcribe) + whisper-small (verify) — a low-VRAM or GPU-less
host becomes plausible, and the Arc B390 path gets a realistic TTS story (Silero-on-CPU sidesteps
the unproven F5-on-XPU spike). Re-time first ("Re-time the batch on Silero").

**From [`docs/russian-tts-guide.md`](../docs/russian-tts-guide.md)** (user-supplied, July 2026) —
levers we have not pulled. The input/SSML pair moved into Open 2026-07-27 ("Input prosody"); what
stays here: per-chunk silence trimming + crossfade at joins (our "seams"); a versioned stress
dictionary
(`terms.tsv`) for domain terms — the class `pronounce_audit.json` surfaces and nothing consumes.
`sample_rate` 24000 is called "plastic" and 48000 recommended: we already run 48000.

**Narrator's grammatical gender → the translate prompt** (user 2026-07-25). Russian marks gender on
1st-person PAST verbs, English does not, and the transcript carries no name — so every first-person
past clause is a silent coin flip. Measured on `aVwxzDHniEw` (Freya Holmér): the sub-agent used
impersonal constructions where they read naturally and defaulted to masculine in 7 places (ids
178/181/190-192/195-196). Not a translator defect — the information was not in its input. Mechanics:
median F0 over voiced frames of `source.wav` (one cheap pass, no model; single-speaker is already
assumed), written beside the transcript and threaded into BOTH routes (the route-B sub-agent prompt
and `SYSTEM` in `stages/translate.py`). Three rules keep it honest: F0 measures VOCAL TYPE, not a
person's gender, so the field is about the grammatical gender of self-reference and takes
`feminine|masculine|unknown`; a middle band (~155-185 Hz) resolves to `unknown`, never to a guess;
`unknown` means "prefer impersonal constructions", which is a real instruction, not a default to
masculine. An operator override belongs next to it (per-channel data). Getting it wrong is audible
immediately and costs only a re-synth of the affected units — which is also why it never blocks a
batch.

**Smaller, roughly by value:**
- per-SERIES terminology glossary (`terms.tsv` per playlist into every translate prompt, checked
  after — drift measured across the 12-video course, ИИ-грамотность vs владение ИИ; per-video
  isolation makes it invisible to every stage, only a batch-level check sees it)
- name-safety pass (out-of-dict Latin names self-agree through verify UNFLAGGED — Bungie → бунджи;
  promote `pronounce_audit.json` to a pre-batch operator gate + a per-run known-names check on
  `src_en` for ASR misspellings like CLAWD→Claude)
- `--no-playlist` on both yt-dlp fetches (`_fetch_video` + `_fetch_audio`, one flag each + test): a
  queue line carrying `&list=` passes the id regex and yt-dlp then FOLLOWS the playlist into the
  fixed `-o source.*` path — dozens of videos over one workdir, verified 2026-07-24. Today's only
  guard is a check in both skills, i.e. instruction, not code
- Ollama circuit-breaker (abort translate after ~3 consecutive api_error instead of burning
  4×timeout per sentence overnight; failed records are not retried on resume)
- enumeration-head detector (in a run of ≥3 adjacent sentences matching `^(and )?X to …` the
  captured head must be unique — 1 fire / 1101 sentences, the true positive, 0 FP, ~15 LOC)
- `--repair id,id --seed N` (point re-synth + remux; grain = the GROUP after units)
- normalize polish pass (range+unit "3.5-4.5 GHz" voices the unit as "гхз"; "90х" →
  "девяностох"; "10-20%" keeps a literal dash)
- reuse the scout audio on promotion instead of re-fetching (~5% waste, accepted 2026-07-20 — but
  answer the provenance question first: a promoted run OVERWRITES `source.wav` with a
  differently-decoded file, ba[ext=m4a] vs the scout's opus, while `sentences.json` was read off the
  old one and `--repair-asr` clips windows from the new one; same master and timeline, believed
  benign, never checked)
- `libopus` for the dub track (one-flag quality upgrade over aac); loudnorm/EQ on the dub;
  singing/music detection → keep original (no robot singing); `--subs-only` fast path
- fix the `out/` export name collision (identical `<title> [<id>].mkv` across models overwrites —
  namespace per run/model or per work_root)
- cross-video stage pipelining (translate GPU ∥ synth/verify) if nights get tight
- RU analogue for the "four Ds" mnemonic (Д/Ф/К/Д does not spell "4D" — prompt unpacking or a RU
  mnemonic; translation-quality class)
- any-language source → Russian (shelved 2026-07-19 until the EN queue runs dry; biggest effort here
  and it breaks the EN→RU hard constraint. whisper large-v3 is already multilingual: drop the
  hardcoded `language="en"` and detect; the translator is prompt-driven, so source language is a
  prompt variable. Quality degradation on rare languages ACCEPTED — coverage, not parity. Touches
  `cfg.source_lang`, the transcribe call, both routes' prompts, the `en.srt` label, and the
  Latin-punctuation-shaped resegmentation `TERMINATORS`/`_ABBREV`)
- tail: translation completeness check (EN↔RU content-word ratio / back-translation on outliers —
  evidence: Gemma dropped 3 of 4 adverbs in `DmgujoZ1mmk` id1, unflagged); babble duration heuristic
  (expected-vs-actual unit duration → flag garbled synth the ASR round-trip misses) — **add it
  BEFORE any narrator-voice or engine change**; whisper anti-repetition decoder params (REJECTED
  2026-07-19 on a 60-run sweep — retry ONLY with a content comparison against a reference
  transcript, since the word-count axis cannot tell "removed a duplicate" from "ate real speech";
  extend `scratchpad/floor_variance.py` rather than starting over)

## Deferred — the F5 path (only if the Silero switch fails)

F5/ESpeech is out of the pipeline (DECISIONS 2026-07-25) and comes back out of git history if
Silero does not work out. Everything below was live roadmap work for F5 and is parked WITH its
measurements, so a revival does not re-derive them — but none of it is work today, and none of it
is a reason to keep per-engine knobs around.

- **Parallel F5 workers — occupancy gate PASSED 2026-07-24, build never started.** `nvidia-smi dmon`
  at nfe=16 over 40 real units: median SM 5%, mean 26.6%, 60% of the active window below 10%
  occupancy — F5 is confirmed launch-bound, so the lever is real. Three things the number does NOT
  promise: the 60% idle includes the verify round-trip and the one-off 66 s worker spawn (only the
  F5-synth slice is fillable); Windows has no MPS, so N processes get WDDM time-slicing and
  threading already showed N=3 DEGRADES; VRAM is tight (~2×1.3 GB + whisper-small + desktop ≈ 9+ GB
  of 12). Raw: `work-exp/f5-occupancy/` + `scratchpad/dmon_f5.txt`.
- **Shorter reference clip — measured, unexercised, and it moves the voice.** F5 denoises
  `ref + gen` and throws the ref away (`utils_infer.py:508`); the reference is 9.164 s against a
  ~7 s mean unit, so over half of every unit's compute is discarded. Worth ~158 s/batch after
  nfe=16 — larger than the workers item. The cost is not compute but quality: shortening the
  reference changes speaker conditioning. It owes the same ear session as the rights-clear narrator
  replacement; do them together or pay it twice.

## Deferred — not near-term

- **Improving the GRADE's quality** (closed as a roadmap item 2026-07-20): grades read as reasonable
  against real material, which was the bar. Making them BETTER is undefined — no reference set, no
  disagreement log, no measurement, so any prompt change would be judged by vibe. Decide what a
  wrong grade looks like first. Cheap diagnostic if a queue ever comes back wrong: the profile's
  four "калибровочные примеры" are videos its owner will certainly watch — scout them, they should
  come back `high`. Run it on suspicion, not as routine.
- Promoting `n_src` from advisory into `flags_actionable` — **blocked on measuring the
  source-anomaly detector's fire rate and precision on a real Sonnet batch first.** Zero measured
  precision today, and `entity_loss` on 11 of 12 videos is the standing precedent.
- In-pipeline Anthropic API translate flag (approved in principle, DECISIONS 2026-07-18; build ONLY
  if the manual sub-agent seam becomes the bottleneck — it is not, and that seam is where translate,
  summary and scout sub-agents all hang).
- Gender-matched narrator (median-F0 → M/F reference; blocked on a female PD reference — search the
  HF Space Den4ikAI/ESpeech-TTS discussions and the author's channels first; fallback re-scan
  LibriVox female readers — xenium5 rejected on mic, chekhov01 on timbre).
- Multi-speaker violation detector (ECAPA vs dominant-voice centroid → report flag; full diarization
  stays out of scope); UTMOS/MOS verification (high cost, low effect until batch stats prove the
  duration heuristic insufficient); unit sim threshold re-tune (base 0.9 — only if production flags
  misbehave); Arc B390 path (whisper.cpp/llama.cpp SYCL); streamed mixing in mux (trigger:
  multi-hour sources — the numpy mix holds a ~2-3 GB transient even after chunked RMS/peak).
- **A pre-synthesis bar on the compression factor — parked 2026-07-27, do not build on this file's
  numbers.** There is nothing to catch: the two shipped-config batches top out at cf 1.22 and
  `work-silero-v5` at 1.790, i.e. ZERO units at or over the 1.8 bar. Two further findings stand
  whenever it is revisited — merging cannot fix an offender anyway (every candidate needed a merged
  span of 20.1-36.6 s against `group_span_max` 20.0, so the lever is the CAP), and a constant-rate
  predictor is too coarse to gate on (worst-case predicted/actual 0.715 forces a 1.29 threshold →
  ~8.4 flags per 24-video batch against ~0.65 real ones, i.e. the bar mostly flags its own error).
  Build constraints kept so a revival does not re-derive them: dropping a unit is forbidden by four
  never-drop invariants, merging self-heals (units keyed by id-tuple), and `done()` compares the
  manifest's own units rather than a fresh partition, so a regroup returns True and never applies
  without a partition check. Trigger to reopen: a batch that actually produces units over the bar.
- **Publication rights — HARD gate before ANY publication of dubs, and the engine switch CHANGED
  its shape (not re-checked since 2026-07-25).** The old wording covered F5's demo-clip narrator
  (personal-use only) and ESpeech's Apache provenance caveat; on the Silero path there is no
  reference clip at all, so what governs is the MODEL's own licence. Our own bakeoff
  (`bakeoff/tts-research-2026-07.md`) records Silero v5 as **CC BY-NC** and explicitly weighed
  "Apache vs hard NC" as an argument for the engine that is no longer in the pipeline — i.e. the
  2026-07-25 switch moved the project ONTO the non-commercial side of that comparison, and nothing
  in the docs re-examined the gate afterwards. Unverified against the current model card; verify
  before any distribution of dubs, and before any plan that ends in "other users".

## Open questions

- **"Keep length" is being replaced, not tuned.** The SYSTEM prompt asks the LLM to keep RU close in
  length to the EN; "Slot fit" replaces that with an explicit target character count, and F5's
  slot-fill stretch — the other half of the old trade — no longer exists on the Silero path. The
  measured Gemma-vs-Qwen tightness comparison (508 segs: Gemma ~2% shorter, stretched on 46% of
  segments vs 39%, leftover silence 1.2% vs 0.8%) is F5-era evidence about a knob that is going
  away. Do not tune the old prompt; land "Slot fit".

## Closed

Phases and shipped work: **CHANGELOG**. Rationale: **DECISIONS**. Three axes are closed with a
standing "do not reopen" — transcribe speed (2026-07-24: four levers measured, none adopted; reopen
only on different hardware or distil cleared by ear, not another probe on this host), summarize
throughput (at its 4.5× parallel ceiling, 2026-07-21), and the `condition_on_previous` claim
(2026-07-24: falsification criterion did not fire, `_guard`/hatch/demotion all upheld, no code
change). `word_timestamps=True` stays load-bearing — sentence resegmentation, timing sync and
`--repair-asr` are all built on it.

Stack pins, host findings and setup: STACK.md + SETUP.md. Translation: Gemma-3-12B (Ollama,
`gemma3:12b`) is the local in-pipeline default; PRIMARY route = Sonnet semi-automatic (DECISIONS
2026-07-18, runbook README "Running"). TTS: Silero v5_5_ru (`eugene`) since 2026-07-25.
