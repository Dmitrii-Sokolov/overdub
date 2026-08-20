# PLAN

Forward-looking only. Measurements and rationale retire to DECISIONS; if an item here
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
`stats-batch/` and the translator A/B cells NO LONGER EXIST (only the 2026-07-2x cells remain):
those workdirs are gone, the published A/B report artifact (508 sentences) is the only surviving
record of that comparison, and the stats-batch URL list is unrecoverable. The route-C baselines under `work-exp/wave-*-2026-07-21/`
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

### Pipeline the batch instead of running it stage by stage *(added and re-scoped 2026-08-06)*

**The objective is a LATENCY, not a stage speed-up** (user, 2026-08-06): shorten the time until the
FIRST video reaches its post-translate tail, so that tail overlaps the translation of the next
video. No stage on this list is being optimized — translate is the longest and is deliberately out
of scope, and the rest are near their practical ceilings.

**WHAT IS LEFT, in order:**

1. **`mux` — the next lever, and nobody has ever looked at it.** 19.3% of machine time on the
   baseline, more than download and transcribe together, pure ffmpeg and disk. Now that the
   overlap is taken it is what binds. Profile before optimising: nothing is known about where its
   time goes.
2. **A clean end-to-end batch figure.** Every phase has been measured on its own; the batch total
   has not, because transcribe's wall varies 35× on identical work (see "Also open") and pollutes
   any total it appears in. That item gates this one.
3. **Acceptance — the artifacts must not move.** Never run, and its original phrasing is now
   broken: it assumed Parakeet was deterministic, and it is not (INBOX 2026-08-07). Re-phrase
   before running it. Bit-stability has to be established per artifact first — `source_bed.wav`
   has never been shown to be stable either — or the comparison reads noise as a regression.
4. **Per-video dispatch of the TRANSLATORS** — the trigger's other half, deliberately not built.
   The wave ends on its slowest agent, which starts when ITS transcript exists either way, so the
   win is bounded by the spread of the transcribe phase (151.4 s over 10 videos) and not by the
   wave. It also cannot use `Workflow` as it stands: the whole queue goes in one call by contract
   (queue-contract §6). Do the arithmetic on a real batch before building it.
5. **A GPU mutex and LONGEST-first ordering — PARTS of a future scheduler, not steps toward one.**
   No two GPU stages can meet inside one process today, so a mutex would guard nothing; the live
   hazard is two PROCESSES, which an in-process lock cannot see. Ordering is inert for the same
   structural reason: every sweep stage is a full barrier. When a scheduler does arrive, the
   ordering argument is transcribe at RTF 0.0103 against a tail at 0.0777 — **7.5× apart** — so
   the long pole goes first. Check rather than assume that the tail scales with duration per
   video, and that a long video's CHUNKED translation is not itself the slowest agent.

**Standing constraints for any work above.** Two stages hold the card — `transcribe` (the Parakeet
worker) and `separate` — and they DO co-reside (9930 MiB of 12282, no OOM, DECISIONS 2026-08-06),
so nothing forces a phase barrier; 19% headroom on one pair of videos is not a licence for
arbitrary lengths. Silero is CPU, assemble and mux are ffmpeg, download is network. If
`verify_roundtrip` is ever turned back on it is a THIRD GPU consumer and the queue must cover it by
construction. The `separate` sweep must finish before `build_translation.py`: both read-modify-write
`timings.json` and a real overlap drops one stage entry silently — if that becomes awkward to hold
by hand, the fix is a lock in `overdub/timings.py`, not a rule in a fifth place.

**Two rules about the numbers, both learned the hard way.** Never sum an overlapping stage: the
translate spans are sub-agent wall clocks and summing them read 4.41× on 6 videos and 6.20× on 10,
growing with fan-out width — report a union or an elapsed window. And tail-to-wave is a property
of the QUEUE, not of the pipeline, so no single ×N generalises; quote the phase and the queue with
it, and keep machine time apart from the attended session span (2438.6 s against 5700.6 s on the
baseline — the difference is the orchestrator thinking).

**What shipped** (git history + DECISIONS 2026-08-06/07 carry the numbers). The instrument (`spans[<stage>]`, `work/runs.jsonl`), the baseline, the concurrent download
pre-pass, `separate` moved into the translate wave, and `scripts/drain.py` — the per-video trigger,
which needed no pipeline change at all. All confirmed on real media; the drain measured ×1.40 on
the wave+tail phase (10 videos, 2026-08-07) with 10 drained, 0 failed, 0 pending. **The ~1.7×
projection this item opened with is withdrawn** — it came off a batch where the tail fitted inside
the wave, and on the 10-video baseline the inequality runs the other way.

### Name list at ASR — the proper-noun class

`model.transcribe` passes neither `initial_prompt` nor `hotwords` today. The SOURCE pass is
`stages/transcribe.transcribe_words`; `asr.py` calls the same API for the verify round-trip, and a
name list must NOT reach that one — a judge handed the answer stops being one, and the similarity
score would rise on exactly the words it is there to check. Measured 2026-07-26: `vLIDHi-1PVU`
("Designing Claude Code") came back with **16 × "Cloud" and 0 × "Claude"** at large-v3/fp16/beam 5
— so DECISIONS 2026-07-20's proper-noun class is not a beam-1-only artifact. Fixing it at the translate seam is possible but
partial and expensive: it needs a `src` flag on every normalised record, it makes 27 of 28
`entity_loss` offenders false, and it cannot reach `en.srt` at all (not re-timed by design — the
rule and its reason are in `assemble._ru_cue_rows`'s docstring, beside the RU path that IS
re-timed — one MKV shipped with 15 × "Cloud" in EN subs against 35 × "Claude" in RU). A
name list closes all three surfaces at once. **First here because it is the only known defect that
survives into a finished MKV and cannot be reached from any later stage.**

**Conditions, non-negotiable:** it changes source text, so it goes into `asr_key`; and it is
adopted only off a measurement on the six fixtures, never because it reads well — biasing an ASR
toward a word list also changes decoding elsewhere in the transcript, which is what the probe
measures. Open sub-question before any code: where the names come from (video title + channel are
free and on disk; a per-queue list is an operator step). Rationale: DECISIONS 2026-07-26.

**The engine changed under this item on 2026-08-06 and the defect did not.** Parakeet produced
6 × `Cloud` against 30 × `Claude` in `2YCaBqP8muw`, where whisper had 0 — but in `RyvXxApfHkk` it
was the only source of the three (whisper, the human transcript, itself) to write `Claude`
correctly all four times. So neither engine owns this class and the fix is still a name list, not
an engine choice. What DID change is the mechanism: `initial_prompt` / `hotwords` are
faster-whisper arguments and do not exist here. NeMo carries its own context biasing (a
`biasing_cfg` rides on every `Hypothesis`) — unmeasured on this corpus, and the first thing to look
at before designing anything. The verify round-trip still runs on whisper, so the old warning holds
unchanged: a name list must never reach it.

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

### Slot fit — size the translation to the slot *(was item 1(a))*

**The fit is TWO-SIDED** (re-framed 2026-07-25, user call). The original framing ("Silero
under-fills, translate longer") did not survive reading the corpus: on 3 of the 5 videos in
`work-silero-v5` Silero **over**-runs its slots (raw/slot medians 1.023, 1.145, 1.017; 16/30,
19/31, 21/37 units under atempo), on 2 it under-fills (0.791, 0.816), and 0.73 was one video's
SOURCE pace, not an engine property. What is missing is a duration model in either direction. The
engine side is a usable constant because Silero's rate is stable (CV 5.5%), but it is **per VOICE,
not per engine**: eugene runs ~1.4× baya, and the shipped per-voice rates live in
`overdub/tts/__init__.py` `_VOICE_RATE` (with their provenance) rather than being restated here —
so the knob keys on `tts_voice`.

**Two thirds of this item already shipped** — ru.srt follows the dub and underfill is measurable
(2026-07-25; the numbers live in "Numbers to re-measure" (A)), and `atempo_floor` = 0.75
cut slot silence 283 → 84 s on `8zJlKmgMT44` in assembly alone. What is left is the polish that
removes the 84 s residue and the audible stretch on the 42-of-69 units pinned at the floor. Ranked
below the three above because the ear has now passed twice without it.

**Sized from the TEXT side 2026-07-28** (translation-layer audit, 9 files): median 18-22 ch/s against
the slot, p90 25-31, 631 of 988 segments over 20 ch/s in the worst file — and ru/en length ratio
**0.97**, so the pressure is the SOURCE speaker's pace, not RU expansion, which is the same
conclusion the 0.73 above reached from the audio side. Two cautions before any of it is quoted: the
audit's "comfortable Russian TTS is 14-16 ch/s" is not our number and sits against a measured eugene
rate of 19.85 ru ch/s; and at that rate a 22 ch/s slot needs cf ≈ 1.11, inside the 1.22 the
shipped-config batches already reached and the ear already passed twice. The figures SIZE this item;
they do not reopen it as a defect.

Target chars = slot ÷ the voice's rate (`tts.target_chars`, shipped); `atempo` trims the remainder.
Obstacles, all confirmed in code: (i) ~~`atempo` <1 does not exist~~ **BUILT**
(`assemble._tempo_for`); (ii) **the `runaway` gate fights the target** — `_is_bad` caps `text_ru`
at `translate_max_len_ratio=3.0 × len(src_en)`, so for any source slower than ~6.3 en ch/s the
CORRECT length is flagged, costing up to 4 reseeds and in the limit shipping `src_en`, i.e. English
into the dub; re-anchor it on the target, not on the source length; (iii) **the length rule lives
in 5 hand-synced copies, and the inventory is worth re-deriving before touching any of them** —
this list was wrong in both directions until 2026-08-03, naming a file that no longer had a copy
while missing the one that actually reaches the translator:

| where | what it is |
|---|---|
| `translate.py` `SYSTEM` | the stated source of truth — and NOT imported by anything: `build_translation.py` imports `_is_bad` from this module, never `SYSTEM`, so nothing enforces the other four against it |
| `skills/overdub-sonnet-batch/references/translate-contract.md` rule 2 | what the route-B sub-agent reads off disk |
| **`.claude/workflows/translate-batch.js`** | the route-B prompt itself — **the copy that decides the output**, and the one the old inventory missed |
| `README.md` (pipeline description + route B) | prose |
| `CLAUDE.md` (Design rules) | prose |

Route B's prompt is a STATIC template in that script, not assembled by an agent at runtime (it was,
before 2026-07-28) — which helps: the script can carry a rule change without a model in the loop.
What it cannot carry is the target itself, since that is per-sentence (slot ÷ voice rate) and has to
travel with the data. So: compute it in a shared helper that `translate.py` and
`scripts/build_translation.py` both call, and enforce/report it in the latter or route-B compliance
is unverifiable; (iv) ~~the resume key ignores timings, so after `--repair-asr` a translation sized
for a slot that no longer exists is silently kept~~ **GONE with route A**: the resume key is now
`translation.json` existing (`stages/translate.py` `done()`), and `invalidate_downstream` deletes
that file plus `translation.jsonl` and `translation.draft.json` on every repair — a repaired
transcript has no translation left to be stale against.

### Input prosody — punctuation and SSML *(promoted from Backlog 2026-07-27)*

The cheapest unpulled lever in the file, and the one that answers "the dub is fine but it reads
flat". The guide attributes ~70% of prosody quality to the INPUT and names flat ASR+MT punctuation
as the main cause of monotony — exactly our input shape. Silero accepts SSML
(`<speak> <p> <s> <prosody> <break>`) while the adapter sends plain `text=`; `<p>`/`<s>` alone give
pauses and a contour reset.

**`<break>` is NOT part of this item — it was built, measured and REJECTED by ear (DECISIONS
2026-07-25), and it stays in the code at `silero_ssml_breaks = False`.** Recorded here because the
mechanism is still wired and reads as available: it was the right mechanism on the wrong problem,
the holes being made by ASSEMBLY rather than by swallowed pauses. The forensics that killed it are
the comment at that config key; do not re-derive them here. It comes back onto this list only if
units with genuinely long INTERNAL pauses start appearing — the condition it was the right
mechanism for and never met. The unpulled half is `<p>`/`<s>`/`<prosody>` and the
punctuation-quality lever, which is the bigger of the two per the guide and is not a markup
question at all — it is what the translator writes.

Two cautions before any code: `text_tts` is Cyrillic-by-contract because Silero DELETES Latin
script, so markup has to be proven not to trip that; and verify compares against `text_tts`, so
tags must be stripped on the comparison side exactly as stress marks already are. Judged by ear,
like everything else in this half of the list.

### Phoneme transliteration from CMUdict *(was item 2)* — blocks the stress audit

The letter rules guess from spelling what the dictionary knows phonetically: `buy → буи` vs
`B AY1`, `fields → фиелдс` vs `F IY1 L D Z`, `update → упдейт` vs `AH0 P D EY1 T`, `execute →
эксекют` vs `EH1 K S AH0 K Y UW2 T`. An ARPAbet→Cyrillic table is ~39 phonemes against ~55 letter
rules — smaller AND more accurate. Coverage over the corpus's invented tokens: 79% of types, 77% of
occurrences; the absent tail is brands and neologisms (`mcp`, `anthropic`, `vercel`, `shadcn`,
`tmux`), so the letter rules STAY as the out-of-dictionary fallback. **The 2026-07-28
translation-layer audit measured the same class from the other end and named its frequency peak:
`alignment → алигнмент`, 91 occurrences.** `data/cmudict.dict` has it (`AH0 L AY1 N M AH0 N T`) and 6
of the audit's other 7 examples — `deceptive D IH0 S EH1 P T IH0 V`, `language L AE1 NG G W AH0 JH`,
`research R IY0 S ER1 CH`, plus `reduce`/`hero`/`models` — each giving roughly the pronunciation the
audit asked for; only `OpenAI` sits in the brand tail. So the dictionary route already reaches the
top offender, and the audit's own proposal (a hand-built 50-100 entry transliteration list) is the
same fix at more maintenance for less coverage. This is also what closes the
open-class residue the ~55-rule ceiling made awkward: `execute → эксекют` (18 hits), `adventures →
адвентурс`, `fields → фиелдс`, `open → опен`, `waters → вейтерс`, `buy → буи`. A rule on
`ex-`/`ie`/`-ute` is ambiguous in English ("exit" wants экс, "execute" wants эгз) — hence the
dictionary, not another rule. Needs an ear check either way.

**Confirmed from a third angle 2026-08-11, and partly DEFUSED the same day.** Four more spelling
failures off `L0nBN6ME7VQ`: `button → буттон`, `changes → чанджс`, `breaking → брикинг`, and
`alchemy → алчеми` where the `ch` is /k/ — the last one being the clean argument that no rule over
letters can reach this class. Compounds are the sharper case: `AlchemySerializeField` came out
as one glued «алчемисериалайзфиелд». What defuses it is the dual-form markup shipped that day
(DECISIONS `08-11`): the translator now supplies the reading, so the fallback saw 2 tokens on that
video instead of 90. This item is therefore no longer about the DUB being wrong — it is about how
much the translator has to mark, i.e. about the seam's cost. Fixing it makes the markup optional
for ordinary words. **Do not reach for espeak-ng for this** (it was proposed on 08-11 and is the
worse option): `data/cmudict.dict` is already in-repo and covers the measured class, while espeak
would be a third external binary against the two the stack rule allows, and it answers only the
brand/neologism tail the letter rules already own.

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

"Synthesize dominates" describes a configuration this pipeline no longer runs — see "Numbers to
re-measure" (B). Do it after the slot-fit item lands, or the numbers describe a pipeline that is
about to change.

## Also open — independent, none of them ordered against the list above

- **Does `effort: 'low'` cut a translator's turn chain, and what does it cost the Russian?**
  `translate-batch.js` sets `model` and `agentType` but not `effort`, so sub-agents inherit the
  session's. Measured 2026-08-20 (DECISIONS): of a translator's median 11 turns only ~6 carried a
  tool call, so ~5 were pure reasoning — yet output is just 2.5% of the agent's tokens against 78%
  for cache traffic, so the direct saving looks small. The reason to measure anyway is INDIRECT:
  fewer reasoning turns is a shorter chain, and the chain is what the cost tracks. Do it as an A/B
  on a handful of videos with the ear on the Russian, not as a blind switch — translation quality is
  the product, and this route exists because Sonnet translates better than the local model did.
- **Uncovered speech is now reported and triaged — what is left is a POPULATION.** The worker
  stamps `holes` / `hole_words_recovered` / `holes_unrecovered`, `run.json` carries them, the batch
  digest has a `gap` column and an unrecovered span sets `needs_triage` (2026-08-06). What no one
  has yet is a rate: every hole measured on the 165-video corpus was recovered on the second read,
  so `holes_unrecovered > 0` has **never actually fired on real media** and its precision is
  unknown. Watch the column across the next few batches before treating it as calibrated — and if
  it stays at zero, that is the answer, not a reason to loosen it.
- **`--repair-asr` has no equivalent on the shipped engine.** It refuses on Parakeet (its accept
  gate is vacuous on a deterministic decoder, DECISIONS 2026-08-06), and the coverage repair inside
  the worker replaces only its uncovered-speech half. The detector-driven half — `completeness`
  seeding a re-read of a garbled or duplicated sentence — has no home now. Whether it needs one is
  open: those detectors were tuned against whisper's failure modes, and whether Parakeet even
  produces that class at a rate worth machinery is unmeasured.
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
- **Sonnet cost per batch is unrecorded — an observability gap, NOT a ceiling** *(demoted from
  Open and re-framed 2026-08-06)*. Route B spends 2 sub-agents per video (translator +
  summarizer), route C one, route E one per CHUNK, and the price appears nowhere: not in
  `run.json`, not in the digest, not in the report. It used to be ranked in Open as **"the scarce
  resource now that disk is not"** — that framing is retracted. The user's own operating estimate
  (2026-08-06) is ~1% of the weekly limit per 2-5 h of translated audio, i.e. tens of hours run
  without approaching a limit, so nothing is gated on this and a 100-video queue is not the
  surprise the old text feared. Treat that as an ESTIMATE with a named source, not a measurement —
  it is exactly the kind of figure this file requires a date and a provenance for, and it does not
  become a measurement by being quoted again. What survives unchanged is the gap itself: no route
  has a recorded per-video token figure, and nothing in the pipeline WRITES one. The only route
  that ever had one (route D, ~200k per video, 2026-07-30) came from reading task notifications by
  hand and was deleted with the route on 2026-08-03, so that number describes nothing that still
  exists. Cheap to close if a batch ever wants it; nothing waits on it.
- **`host_guard` decides on the wrong instrument — move it to the SM CLOCK** *(2026-08-07,
  DECISIONS)*. It gates on `utilization.gpu` (bar 40) and memory (bar 2500 MiB), and
  `utilization.gpu` measures the fraction of sample windows containing any kernel at all, not load
  — desktop compositing keeps it in the tens of percent on a card sitting at its idle clock. It
  printed `35% util, 815 MiB, 57 C, 210 MHz — idle` and that ONE line misled in both directions
  at once: the verdict said idle, the percentage said busy, and only the 210 MHz was true. Measured
  the same session: **210 MHz / 13.5 W at rest vs 2445 MHz / 45 W under load** — an order of
  magnitude, against a utilisation figure that cannot separate the two. The fix is to gate on the
  clock (idle-clocked is idle whatever the percentage), keep memory as the second signal, and
  demote utilisation to something printed rather than decided on. Do NOT just lower
  `BUSY_UTIL_PCT`: that keeps the wrong instrument and would start refusing to run on a normally
  composited desktop, which is the hardware this project targets.
- **Transcribe's wall varies 35× on IDENTICAL work, and nothing explains it** *(2026-08-07)*.
  `IOMCDpzpNaQ` (617 s of audio) recorded `work_sec` of **6.8 s** (as the 10th video of a warm
  10-video sweep), then **238.2 s**, **32.7 s** and **22.4 s** on three later decodes of the same
  file. At batch level the same day: transcribe summed 151.2 s on the baseline and 539.3 s on a
  re-run of the same ten videos. Ruled OUT: a busy card (clocks and power measured healthy under
  load, DECISIONS 2026-08-07) and a changed input (`vad_speech_sec` identical to 0.1 s on all ten,
  so the VAD saw the same audio). Partial candidate: first-use CUDA kernel compilation, which a
  warm sweep amortises and an isolated run pays in full — but it does not explain the FIRST video
  of the re-run being slow too. This is 5-6% of machine time so it changes no decision, but it
  makes any transcribe figure unquotable until understood, and it is why the 2026-08-07
  end-to-end comparison was scoped to the wave and the tail. **Do not re-measure transcribe speed
  against the closed 2026-07-24 axis until this is resolved** — that closure assumed a stable wall.
  Note the spans for these videos are themselves contaminated by the two diagnostic `--force`
  re-runs, so a clean series has to start from a fresh workdir.
- **Persist the batch capacity measurement — it currently survives only in a chat message.**
  Step 4 computes audio ÷ machine time from the per-step stamps (route-B skill, "Capacity",
  added 2026-08-02: 2 videos, digest said ×4.13, the machine did ×2.56), but nothing writes it
  down. `run.json` carries no timestamp and `timings.json` has no batch level, so the ratio
  cannot be recomputed once the session ends and every night is planned off a single sample.
  Cheapest shape: append-only `work/capacity.jsonl` written by step 4 — queue ids, `audio_s`,
  the four step seconds, and a config fingerprint. The fingerprint is load-bearing: the point is
  comparing nights, and a series that silently spans an engine or grouping change is exactly the
  trap `run.json` is already in (no engine field in any of them — 193 checked 2026-08-02 — so its
  own provenance is only recoverable from git history). Do NOT fold it into `run.json` — that file is
  per-video and this quantity is per-batch.
- **Clean `work/<id>/` after a successful mux — hygiene, NOT a queue-size lever.** Delete BINARIES
  only (`source.mkv`, `source.wav`, `source_bed.wav`, `dub_ru.wav`, `segments/`); json/md are
  pennies. Transcript, translation and summary survive; the cost is re-synthesis of everything
  downstream. `out/` holds a second hardlink so the result survives on its own. **Blocker inside
  it:** mux's input must move `source.mkv` → `output.mkv`, or a re-mux needs a re-download.
- **Recalibrate the floor CHAIN, not the ratio.** `floor_ratio ≥ 0.085` fired on nothing (batch max
  0.070) while two videos had visible collapses; `floor_longest_run ≥ 40` separates exactly those
  two and nothing else, and now drives a digest hint (2026-07-25). `config.py`'s own comment admits
  the ratio is "knowingly unreliable" for borderline detection. `transcribe._guard` still gates on
  the ratio — recalibrate off the accumulated series, as that comment asks.
- **Timing detail for the four remaining stages.** `download`, `verify`, `assemble` and `mux` report
  no `detail`, so `work_complete` stays False on a real run and `total_work_s` is an UPPER bound.
  The mechanism shipped 2026-07-22 (+ `separate` 2026-07-24); this is one measurement pass, not
  code design. Add it when a real batch makes the calls worth it.
- **`translate-batch` — one run in, and the mechanism held; two paths still unexercised.** First
  real use 2026-07-28 (5-video queue: 4 translated + 4 summarized, the fifth carried by the resume
  filter). All three predictions confirmed — markers **3.5 s apart** across the wave, the 4694-line /
  782-sentence transcript came back **782/782**, `src` on 100% of records in all four drafts with
  zero forbidden fields and zero `_is_bad` flags. Step 2 cost the orchestrator **1428 chars** (0.7%
  of the session, against 62% for hand fan-out). Two defects found and fixed the same day
  (2026-07-28): a narrated status line, and the args-as-string call that the ported guard
  caught on the first try. **What this run did NOT test:** (i) the projected ~5.6k tokens/video — at
  4 videos steps 1/3/4 and manual debugging dominate the session, so the figure stays a projection
  and must not be quoted as measured; (ii) the `failed` / `incomplete` / second-wave branches —
  nothing failed, so that code has never executed; (iii) the 5930-line `9eXV64O2Xp8` transcript,
  the true worst case, which is 20% longer than what did run. Fold (i) and (ii) into the next
  ordinary batch rather than staging a run for them.
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
  **First sample outside route C, 2026-07-28: route B's four summarizers wrote `summary.md` via the
  PowerShell path 4/4 with no refusal and no end-run** — the caller-writes fallback (a) was not
  needed once, which is weak evidence that stating the mechanism is enough and the ~200 s/6 videos
  in (a) may never have to be paid. Four agents is a sample, not a rate; the question stays open.
- **Repair-window `hotwords` / `initial_prompt` — last on purpose.** Fixes the one confirmed
  regression from the 2026-07-20 ear check (DECISIONS 2026-07-20 explains why this does not reopen
  the repetition loop); available in faster-whisper 1.2.1, verified; word-list sources cheapest
  first (the video's own out-of-window sentences, then `pronounce_audit.json`); measure on the
  golden fixture. `--repair-asr` shipped at 5/12 recall with a proper-noun regression, so the open
  question is whether the feature earns more investment at all — that ranks below every item serving
  a route in daily use.

## Numbers to re-measure

Three groups, three different reasons. **Do not quote across a group boundary.**

**(F2) The dual-form seam is ON TRIAL — measure its cost, and roll back if it is too high.**
Shipped 2026-08-11 (DECISIONS): the translator writes `[[written|spoken]]`, so it emits both forms
and the seam's output volume grows. The only reading so far is one 164-sentence video —
**translate 7.8 min of a 10.5 min run, 154 marked spans, 469 s wave** — which is not a baseline
for anything: no full batch has run under the rule. Take the seam's wall and its char volume on
the first real batch and compare against the pre-08-11 runs.

**The decision rule is set in advance, so the measurement cannot be argued with after the fact:
if translate is noticeably more expensive or slower, try something else, and the FIRST thing to
try is a rollback.** Reverting is cheap by construction — the markup lives only in the draft and
`translation.json` never changed shape, so it is one revert of the contract + prompts + the
resolver, and nothing downstream knows the difference. The other direction is the CMUdict item
above, which would let the translator mark far less instead of not at all.

Two things this measurement must not conflate. Output VOLUME is what binds the chunked
translator, not sentence count — so the 2000-sentence chunking threshold is also stale until this
is read. And the 08-11 seam figures were taken with `translate.started` present; a video whose
wave was not timed reports the OLD meaning of `total_wall_s` and is not comparable.

**(A) `8zJlKmgMT44` — the current reading.** Shipped grouping 1.2/20/600, measured 2026-07-25 with
the new metric: **fill median 0.7104, slot silence 283.1 s** of a 1058.8 s dub (`in_span_silence`
reads 241.8 s on the same run and understates by 41 s — it excludes the inter-unit gap). **Quote
these; every earlier pair on this video was measured at grouping 0.4/12/300 and is history, not a
comparison arm.**
**Retired, do not re-quote: "17 units at cf ≥ 1.8, up to ×12.5".** Recomputed over all of `work/`
2026-07-25: **7 units of 3575, worst 2.63** (12 SENTENCE rows — the two counts were being mixed,
and the ×12.5 was one sentence's pre-repair `speed_factor`).

**(D) Everything measured on `work/` BEFORE 2026-07-26 is F5 at grouping 0.4.** Those 36 manifests
report `engine=f5`, `group_gap_max=0.4` — that pair is how you IDENTIFY them on disk, and the engine
left the code, not the manifests. So every compression, slot and unit-count figure derived from that
corpus describes a configuration this pipeline no longer runs, and the boundary is now a DATE, not
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
and are not comparable), and none of it is quotable beside a pre-2026-07-26 number.

**(B) F5-era batch stage-shares are void.** synthesize 47.6% · transcribe
21.3% · download 9.8% · verify 8.3% · mux 7.9% · separate 4.9%; batch RTF 0.451 (7.26 h → 3.27 h);
the 2026-07-24 36-run split (synthesize 52.6 + verify 7.6 + mux 7.4 + separate 4.8 = 72.7%); and the
"3.3 h → ~1.9 h, RTF → ~0.26" projection, which extrapolates one video to a batch. Closed by
"Re-time the batch on Silero".

**(C) Wall-clock contaminated — anything derived from `timings.json` stage walls before
2026-07-22.** The ~72 s/video fixed cost, the whole-pipeline RTF pair from the 2026-07-19 audition
(Silero 0.14-0.17 vs F5 0.70-0.92 — unlabelled, that pair is two unquotable numbers), and every
`breakdown_pct`. Re-derive from `rtf_work` on the next pass.

**(E) The chunked-translate threshold is measured on the WRONG GRAIN (2026-08-05).** The route-B
skill sends a video straight to the chunked translator above ~2000 SENTENCES, off a count over 227
drafts: one partial in the corpus (`477qF6QNSvc`, 1550/2514), zero partial at or below 2004, two
failures among the four videos above it. What binds the per-video agent is not the sentence count
but the OUTPUT VOLUME it has to emit — so a transcript of long sentences hits the wall sooner than
one of clipped speech at the same count, and the threshold as written cannot see the difference.

Re-site it on characters: sum `len(text)` over `sentences.json` per video, split by the same
outcome, and quote whichever separates the two classes better. What must NOT be carried over is the
2-in-4 rate — it is a FLOOR, because a video that failed once and passed on a retry leaves a
complete draft behind and reads as a clean success. Recovering the real rate needs a record the
pipeline does not keep today (the draft is overwritten), so either accept the floor and say so, or
persist the `INCOMPLETE` fraction somewhere first.

**And 2000 is not a failure threshold** — the outcomes interleave (2259 failed, 2379 passed, 2514
failed, 2829 passed) and the largest transcript in the corpus is a single-agent success. It is a
"stop paying for the attempt" line resting on the clean lower half. Anything quoting it as "videos
over 2000 sentences fail" is wrong.

**(F) `total_wall_s` CHANGED SCOPE on 2026-08-05 — it now includes the translate seam.** Not a
contamination like (C): the number was always missing a real cost and now is not.
`build_translation.py` records the Sonnet wave into `stages["translate"]`, so from that date a run's
`total_wall_s`, `rtf`, `breakdown_pct` and the batch stage split all count the seam. **Before it,
`translate` was absent from the `stages` map of all 252 timings.json on disk** — so every published
throughput figure from before excludes it and the two are not comparable. Measured on
`7xTGNNLPyMI` the same day: stage walls alone imply ×3.73 over the corpus, the real end-to-end
figure was ×1.31.

Three things to know before quoting the new number. It is only as good as `translate.started`, so a
video whose agent skipped the marker records NO wave and its total silently reverts to the old
meaning — the helper prints a `[warn]` and that warning is the only signal. A chunked video whose
middle chunk was re-run alone measures from the ORIGINAL wave's marker, so its wall is a floor. And
the seam wall is orchestrator time, not machine time: it includes the sub-agents' own latency and
queueing behind the concurrency cap, which is exactly what makes it the right input for the
overlap question and the wrong input for a GPU-utilisation one.

**The barrier it was collected to size is now MEASURED and this sub-item is spent** (2026-08-06).
The batch is stage-major (`for st in stages: for j in jobs`, `cli.py`), so the translate wave is a
full barrier during which the GPU idles; the baseline puts that idle at 811.6 s of an 2438.6 s run
and the first video's own wait at 313 s inside step 1 alone. Numbers and method: DECISIONS
2026-08-06. `total_wall_s` remains what this entry says it is — a per-video SUM — and the batch
window now lives in `work/runs.jsonl` instead of nowhere, so the two must not be mixed.
Note the stage-major rationale (DECISIONS 2026-07-19) is partly EXPIRED: its core argument
was that a model's lifetime is one stage sweep so peak VRAM is the max over models rather than
their sum, and it was sized around the local ~8-9 GB Gemma translator that no longer exists.

## Backlog

**Throughput / weaker hardware.** With TTS fast on CPU and the GPU idle during synthesis, the
remaining GPU load is whisper-large (transcribe) + whisper-small (verify) — a low-VRAM or GPU-less
host becomes plausible, and the Arc B390 path gets a realistic TTS story (Silero runs on the CPU, so
the XPU question never comes up for TTS). Re-time first ("Re-time the batch on Silero").

**From [`docs/russian-tts-guide.md`](../docs/russian-tts-guide.md)** — levers we have not pulled.
The input/SSML pair moved into Open 2026-07-27 ("Input prosody"); what stays here: per-chunk
silence trimming + crossfade at joins (our "seams"); a versioned stress dictionary (`terms.tsv`)
for domain terms — the class `pronounce_audit.json` surfaces and nothing consumes. The guide was
cut down 2026-08-03, so **nothing shipped is left in it as an OPEN item**: what remains is either
Open (punctuation and SSML), this Backlog entry, or the listening checklist. Anything the code
already does (including the `sample_rate` 48000 recommendation we already follow) was deleted
rather than left to read as an open item. The one exception is deliberate: the guide's opening
divergence block records where our ear ranking overrules its voice advice, which is shipped state
and belongs there precisely so a reader of the guide meets it before the advice.

**Re-validate `MIN_SENT_CHARS` on Silero.** The ultra-short-sentence merge threshold
(`stages/transcribe.py`, 15 EN chars) was calibrated on the retired F5 engine, which sized its
duration canvas by text length and made tiny texts echo the reference tail. Silero has no such
failure mode, so the threshold is currently an unexamined inheritance: it may be too high (merging
sentences that needed no merging, and absorbing their pauses) or harmless. Cheap to answer — synth a
handful of sub-15-char units alone versus merged and listen. Do it before any further merge tuning,
because every other merge knob is calibrated against this one.

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

**Translation-layer audit — 9 `translation.json`, ~2090 segments, read 2026-07-28.** Semantic
translation quality and ASR-repair metadata came back clean; every finding is in the TTS
normalization layer or in cross-segment consistency. **Provenance caveat: the audit read files named
`translation__N_.json` and no video ids, so not one of its counts is traceable to a workdir — get the
id mapping before quoting any number from it, and note that a `translation.json` is engine-neutral
EXCEPT where a figure is measured against the slot (there the date boundary of (D) applies).**
Four of its seven findings were already open and are deliberately NOT duplicated here — the numbers
went to the existing items instead: letter-by-letter anglicisms → "Phoneme transliteration from
CMUdict" (Open, `алигнмент` 91× recorded there); chars/sec over the slot → "Slot fit" (Open, sized
there, and it does not survive as a defect); a detector that fires while nothing acts → the
`src != ok` seed item (Also open, which also carries the ordering constraint the audit missed:
seeds are read BEFORE translation); numeral case → the accepted PoC loss recorded in
`normalize.py`'s module docstring ("Known PoC loss"), whose proposed fix ("delegate numeral spelling to the LLM") is design B, **rejected by DECISIONS
2026-07-17 F1/F2** — an LLM-spelled `text_tts` diverges from the Python normalizer verify applies to
the ASR hypothesis and silently depresses similarity on correct numeric dubs. If case-aware numerals
are wanted, they are a `num2words` + syntactic-context pass inside `normalize.py`, never an LLM
field. What is new:
- **URL / domain branch in the normalizer.** `claude.ai` → "клод.ей": the dot SURVIVES, so Silero
  reads it as a sentence end (spurious pause + falling contour mid-phrase), and `.ai` voices as "ей"
  instead of "эй-ай"; want "клод точка эй-ай". Also `anthropic.com` → "антропик.ком",
  `importai.substack.com`. `pronounce.py` carries `URL`/`HTTP`/`HTTPS` as acronyms and no domain
  rule at all, so nothing owns this shape today. Cheap and self-contained; the ear-audible half is
  the dot, not the TLD.
- **Terminology drifts INSIDE one file, not only across a series.** One file renders "alignment"
  three ways — 93× left in Latin, 23× "согласова-", 9× "выравнива-", sometimes in adjacent
  segments — and produced "фейковать выравнивание". Different grain from the per-SERIES glossary
  below: the fix is a file-scoped glossary carried across segments instead of re-derived per
  sentence, i.e. a route-B prompt/`build_translation` change, not a `terms.tsv`.
- **`english_echo` marks deliberately preserved terms as `failed`** — 7 segments, all on "alignment
  faking", translations correct. Not a new class: the comment above
  `translate._latin_prose_chars` records that 13 of 28 fires on the 2026-07-25 batch were the
  technical-token shape and the remaining 15 were set phrases the translator kept on purpose
  (`runreport`'s `_ADVISORY_TRANSLATE` comment scores all 28 as correct Sonnet behaviour), and the
  call then was advisory-in-runreport rather than silenced. But the STATUS written into `translation.json` is
  still `failed`, which is what the audit read — so decide whether the term-preservation exemption
  belongs in `_is_bad` beside the three that are there, or whether the status is simply the wrong
  field for an advisory.

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
  guard is the `$ids` check in `docs/queue-contract.md` §1, i.e. instruction, not code
- enumeration-head detector (in a run of ≥3 adjacent sentences matching `^(and )?X to …` the
  captured head must be unique — 1 fire / 1101 sentences, the true positive, 0 FP, ~15 LOC)
- `--repair id,id --seed N` (point re-synth + remux; grain = the GROUP after units)
- normalize polish pass (range+unit "3.5-4.5 GHz" voices the unit as "гхз"; "90х" →
  "девяностох"; "10-20%" keeps a literal dash)
- reuse the scout audio on promotion instead of re-fetching (~5% waste, accepted 2026-07-20). **The
  provenance question is no longer open in the "believed benign" direction: a re-fetch CHANGED the
  transcript** — `uFYLIdYXntk` read 2057 words / 149 sentences, and 2055 / 150 after its
  `source.mkv` was deleted and re-downloaded (2026-08-06, DECISIONS). Isolated: a second decode of
  the same file reproduced 2055 / 150 exactly, so the decoder is deterministic and the INPUT moved.
  Small, but it means `sentences.json` read off the old audio and `--repair-asr` clipping windows
  from the new one are describing different files. WHY the audio moved is unmeasured — the two
  downloads were never compared for format or bytes, so "yt-dlp picked a different format" is a
  hypothesis. Answer that before designing the reuse, because it decides whether reuse is a saving
  or the actual fix
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
  Latin-punctuation-shaped resegmentation `TERMINATORS`/`_ABBREV`. Two of those are now MEASURED
  rather than suspected, on the Russian side at least: route E went EN-or-RU on 2026-08-14 and
  `resegment` needed nothing — dotted abbreviations appear once in 1832 sentences and Russian
  sentence length matches English, so `TERMINATORS`/`_ABBREV` are not the obstacle this line
  assumes for RU. Says nothing about a language that does not end sentences with `.!?`)
- tail: translation completeness check (EN↔RU content-word ratio / back-translation on outliers —
  evidence: Gemma dropped 1 of 3 adverbs in `DmgujoZ1mmk` id1, unflagged — DECISIONS 2026-07-18,
  i.e. measured on the retired local translator: the failure CLASS carries to any route, the rate
  does not); babble
  duration heuristic
  (expected-vs-actual unit duration → flag garbled synth the ASR round-trip misses) — **add it
  BEFORE any narrator-voice or engine change**; whisper anti-repetition decoder params (REJECTED
  2026-07-19 on a 60-run sweep — retry ONLY with a content comparison against a reference
  transcript, since the word-count axis cannot tell "removed a duplicate" from "ate real speech";
  extend `scratchpad/floor_variance.py` rather than starting over)

## Deferred — not near-term

- Promoting `n_src` from advisory into `flags_actionable` — **blocked on measuring the
  source-anomaly detector's fire rate and precision on a real Sonnet batch first.** Zero measured
  precision today, and `entity_loss` on 11 of 12 videos is the standing precedent.
- In-pipeline Anthropic API translate flag (approved in principle, DECISIONS 2026-07-18; build ONLY
  if the manual sub-agent seam becomes the bottleneck — it is not, and that seam is where translate,
  summary and scout sub-agents all hang).
- Gender-matched narrator — **no longer blocked on sourcing a voice (2026-07-27).** The female
  voices ship with the model (kseniya = backup, xenia, baya), so matching is `tts_voice` per video,
  not a hunt for a clip. What is left is
  a design question and an ear pass: whether the narrator's voice should follow the speaker's median
  F0 at all, and whether kseniya holds up over a full video. Shares the F0 pass with the
  grammatical-gender item above — measure once, use twice.
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
- **Publication rights — HARD gate before ANY publication of dubs (not re-checked since
  2026-07-25).** There is no reference clip anywhere in the pipeline, so what governs is the
  MODEL's own licence: Silero v5 is recorded as **CC BY-NC**, i.e. the project sits on the
  non-commercial side, and nothing in the docs re-examined the gate afterwards.
  **NC accepted for personal use (user, 2026-07-27)**,
  so this is not a gate on the current use — it is a gate on publication and on "other users".
  Unverified against the current model card; verify before any distribution.
  **Known escape hatch if NC ever binds:** Silero's `v5_cis_base` with the ~30 `ru_*` voices under
  **MIT**, at the cost of setting stresses yourself — which this pipeline is already building
  toward (CMUdict + the stress audit). Same engine family, so the adapter would not change; the
  voice and the stress preprocessor would. Both licences are recorded in README, "Voices, cloning
  and the law" (moved there 2026-08-03 — they used to live only in the TTS guide).

## Open questions

- **"Keep length" is being replaced, not tuned.** The SYSTEM prompt asks the LLM to keep RU close in
  length to the EN; "Slot fit" replaces that with an explicit target character count, and the
  engine-side slot-fill stretch — the other half of the old trade — no longer exists. The measured
  translator-tightness comparison from that era (508 segs) is evidence about a knob that is going
  away. Do not tune the old prompt; land "Slot fit".

## Closed

Phases and shipped work: **git history**. Rationale: **DECISIONS**. Three axes are closed with a
standing "do not reopen" — transcribe speed (2026-07-24: four levers measured, none adopted; reopen
only on different hardware or distil cleared by ear, not another probe on this host), summarize
throughput (at its 4.5× parallel ceiling, 2026-07-21), and the `condition_on_previous` claim
(2026-07-24: falsification criterion did not fire, `_guard`/hatch/demotion all upheld, no code
change). `word_timestamps=True` stays load-bearing — sentence resegmentation, timing sync and
`--repair-asr` are all built on it.

Stack pins, host findings and setup: STACK.md + SETUP.md. Translation: Sonnet semi-automatic at the
seam (runbook README "Running"). TTS: Silero v5_5_ru (`eugene`) since 2026-07-25.
