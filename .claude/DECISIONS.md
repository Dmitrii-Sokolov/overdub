# DECISIONS

## 2026-07-19 — `no_repeat_ngram_size` REJECTED; and the guard threshold's separation is gone

**Measured, not argued: 60 ASR runs** (3 videos × n in 0/4/5/6 × 5 repeats), scoring floor ratio,
adjacent duplicate sentences, and word count vs the n=0 baseline.

**No consistent direction, so it is not adopted.**
- Severe (`4szRHy_CT7s`) — the only win: floor 11.07% → 8.2%, dups 2 → 0 at n=6; words −1.1/−1.3%.
- Borderline (`RyvXxApfHkk`) — WORSE on every axis: floor 6.13% → 13.51%, dups 0 → 2, words +11.5%.
  More words *with* more duplicates means the ban did not suppress the loop, it pushed the decoder
  into a different repeating shape.
- Healthy control (`Y0KidGr9Z2Y`) — n=4 damages a clean video: 0.13% → 4.44%.

A knob that helps one source, harms another and destabilises a third is not a fix.

**The third axis was badly designed, and that is worth recording.** "Word count drops ⇒ the ban ate
real speech" is ambiguous exactly where it matters: removing a duplicated sentence ALSO drops the
count, and that is a win. So the −1.3% on the severe video is unreadable — it could be the deleted
duplicate or eaten text, and this metric cannot tell them apart. Settling this properly needs a
CONTENT comparison against a reference transcript, not a word tally.

**Bigger finding — the guard threshold's "clean separation" does not survive more data.** The
n=0 cells are a second, independent 5-run sample of the same three videos. `RyvXxApfHkk` reached
**15.82%**, above the severe video's whole range (9.3-11.9%) and more than double its own maximum
in the earlier session (7.52%). The 7.52 → 9.33 pp gap that `transcribe_floor_run_max = 0.085`
was calibrated into does not exist at n=60. The threshold stays PROVISIONAL and its comment
understates the problem: this is not a narrow gap, it is overlapping populations. The guard
remains justified as catastrophe insurance (the severe video is above threshold in every sample
ever taken) and is confirmed unreliable for borderline cases. Recalibration must come from the
`asr.floor_ratio` series now accumulating in run.json, not from another hand-run probe.

## 2026-07-19 — Triage signal: narrow `refusal`, and stop advisory flags from deciding it

**`translate:refusal` was matching ordinary prose.** The pattern `как (?:ии|модель|языковая)`
was written for the Gemma route, where refusals are real. But "как ИИ" is also plain "how AI",
and on AI-subject content that is everywhere: ALL SIX refusal flags in the 12-video AI-Fluency
batch were false — e.g. "по мере того, как ИИ продолжает развиваться". Narrowed to require the
first-person clause a real refusal carries (`как ИИ, я …`). "языковая модель" alone is likewise
not a marker in this domain ("работает как языковая модель" is a normal sentence). Validated: 0
false positives on all 6 real cases plus 2 constructed traps, 0 misses on 8 genuine refusals in
both languages. All 12 translations rebuilt; refusal flags went 6 → 0.

**The deeper problem was not the regex — it was pooling.** `needs_triage` was
`any flag at all > 0`, so `speed ×8.79` (unintelligible audio) and `entity_loss` on the surname
Дейкин (cosmetic) carried identical weight. The batch reported **11 of 12 videos needing a
look**, which conveys exactly as much as reporting none. Fixing the regex alone would only have
made it 10 of 12.

**Completeness flags are now split by what a human can act on.** `entity_loss` and
`length_short` are ADVISORY: still counted, still printed, but they no longer decide
`needs_triage`. This is not a workaround — completeness.py's own docstring names personal-name
Russification as `entity_loss`'s dominant IRREDUCIBLE false positive (no cheap brand-vs-person
discriminator exists) and calls `length_short` the deliberately coarse weak signal. Narrowing
the detectors instead would trade a real loss class (a dropped brand name) for quieter output.
`num_loss` and `neg_loss` stay actionable — an inverted negation is the most dangerous silent
loss there is, and one false positive per batch is a fair price for never missing one.

**Result: 11 → 2 videos needing triage** on the same run data, and the two left are real
(a `neg_loss`, and an `english_echo` that would send Latin script into the synthesizer).
`run.json` now carries `flags_actionable` / `flags_advisory` alongside `flags_total`, so the
advisory stream stays available for trends without polluting the decision.

## 2026-07-19 — Silero v5 audition: v4 was tested BY MISTAKE; v5 is the fast fallback

**The 2026-07-15 bake-off tested the wrong release.** `v4_ru` was already superseded when it was
adopted; the adapter then hardcoded it, so every Silero verdict in this file up to now describes
an outdated model. `v5_5_ru` is audibly better and is now the default. v4 stays reachable only to
reproduce pre-2026-07-19 runs.

**Ear ranking (user, 5 videos × 5 voices, one voice per video, v5_5_ru):**
- **kseniya, eugene — best.** These are the two to use.
- **xenia** — good voice, slightly unpleasant.
- **aidar, baya** — off-standard accent, sounds harder to follow; phonemes drift from ordinary
  Russian. Avoid.

**Verdict: quality is below F5/ESpeech and the user accepts that trade for speed, for now.**

**Speed is the headline: synthesis is 12-19× faster and CPU-only.** Measured on the same
translations as the F5 run (5 videos): synth 11-14 s vs F5's 128-250 s; whole-pipeline RTF
0.14-0.17 vs 0.70-0.92. Synthesis stops being the bottleneck (verify and separate now dominate)
and the GPU is left free. Objective quality is near parity — mean round-trip similarity
0.979-0.992 vs F5's 0.985-0.991, zero verify flags, zero segments over ×1.8, `xenia` fully clean.
The old worry that Silero would trip the 0.9 gate did NOT reproduce: sample min was 0.920. That
worry was measured on v4 — another consequence of the wrong-release mistake.

**Metrics did not predict the ear here, again.** 0.99 similarity means "the words are present",
not "it sounds good" — the id101 precedent (sim 1.0, judged bad by ear, 2026-07-16) holds. The
three defects below are all invisible to every metric the pipeline computes.

**Three defects found by ear, none of them caught by verify:**
1. **Noise / hiss, "cheap microphone", voices do not ring** like a trained announcer. Candidate
   fix is post-processing — denoise, compression, EQ — not an engine change.
2. **No expressiveness.** Tone never varies; sentence after sentence lands on the same contour and
   the result is soporific. v5_5 is reported to support varied intonation; unexplored.
3. **Dub lags the subtitles and the English speech.** MEASURED asymmetry against the F5 baseline:
   clip-duration/source-span median 0.93 and 0.87 (Silero) vs 0.98 and 0.98 (F5), with more units
   overflowing the slot (7 vs 4, and 7 vs 0). Mechanism: Silero declares `supports_target=False`,
   so nothing asks the engine to hit the source span — F5 receives `target_sec` = the span and
   lands on it natively, while Silero renders at its own pace and only assemble's `atempo`
   intervenes, and only once a clip exceeds the SLOT (span + following pause), never the span
   itself. Inside a grouped unit the per-sentence offsets then drift both ways. The user's own
   proposed remedy — tempo-fit the already-rendered chunk — points at exactly this: fit to the
   SPAN, not only to the slot, for engines without native targeting. NOT yet fixed.

**Migration cost was small, and the code stays.** Two changes: `cfg.silero_model` (release id
passed to `torch.hub`, replacing the hardcoded `MODEL_ID`) and — load-bearing — that id added to
`synth_key`. Without the second, v5 would have silently reused v4 wavs under the same voice name:
the exact silent-staleness class the `synth_key` INVARIANT exists to prevent. The v5 Cyrillic-only
caveat needed no filter: `text_tts` is Cyrillic by contract and measured clean (0 Latin characters
across all 12 batch videos), because the pronounce chain transliterates kept-Latin names before
synthesis. Full suite green.

**Production default stays F5.** This audition changes the fallback's identity and quality, not
the primary engine.

## 2026-07-19 — Collapsed ASR alignment: guard the cause, not the harm

**The defect.** `4szRHy_CT7s` dubbed one slot at 294 char/s (atempo ×8.79, unintelligible).
Root cause sat two stages upstream of the symptom: `condition_on_previous_text=True` fed
whisper's decoder into a repetition loop, which took the word alignment down with it. Whisper
returned unusable word timings, `flatten`'s monotone clamp + `MIN_WORD_DUR` floor manufactured
plausible-looking ones (0.02 s per word, 44 in a row), and every stage below trusted them. The
floor is correct — a zero-length word divides by zero in atempo — but it converted "no timing"
into "false timing" and recorded nothing.

**Timings are an input to SYNTHESIS, not just to assembly.** F5 receives each unit's span as a
native-speed target (`supports_target`), so a collapsed stretch makes the engine compress until
it DROPS words — `unit_sim_threshold` exists precisely because compression ≥~1.3 loses words
while ASR similarity still scrapes past the base gate. So bad timings cost lost speech, not
fast speech, and verify can miss it. That is why the guard must sit at transcribe.

**Guard the cause.** Downstream harm cannot be predicted at transcribe time: it depends on the
Russian text (which does not exist until translate) and on unit grouping absorbing free gaps —
measured, a sentence at 178 char/s still finished at ×1.37 because the following gap swallowed
the spill. So `floor_run_ratio` scores the DATA defect (chained floor-stamped words) and
`_guard` re-runs once with context feedback off, keeping the retry only if it at least halves
the ratio (the flag earns its keep on punctuation — see 2026-07-17 — and a marginal win does
not justify losing it).

**Whisper is not deterministic here, and that reframes the threshold.** `temperature` is a
fallback LIST, so the decoder samples and the same audio yields different transcripts per run.
Measured over 5 repeat runs each of 3 videos: severe 9.33–11.38% (fired 5/5), mid 3.82–7.52%,
"clean" 0.00–7.46%. The control video — 0.0% on its original run — hit 7.46% with a 30-word
chain on run 3. There is no such thing as a sick VIDEO, only a sick RUN. The first threshold
(0.06) would therefore have fired on a healthy source and traded away punctuation for nothing;
it is now 0.085, inside a separating gap only 1.8 pp wide on n=5 and marked PROVISIONAL.

**Consequence accepted:** the guard is reliable insurance against a CATASTROPHE (severe case
caught 5/5) and unreliable as a borderline detector (mid case 2/5). Claiming otherwise would be
false. `run.json` now carries `asr.floor_ratio` on EVERY run so the threshold can be recalibrated
from a real distribution instead of single samples.

**Still open:** `no_repeat_ngram_size` / `repetition_penalty` are at library defaults (0 and 1 —
i.e. off). They attack the repetition loop that FEEDS the temperature fallback, so they are the
only lever that could narrow the run-to-run spread rather than catch its tail. Not adopted
blind: a too-small n mangles legitimate repetition silently, which is the forbidden class.

## 2026-07-15 — Founding decisions

**Local-only pipeline.** Target volume is hundreds of hours; cloud TTS pricing
(ElevenLabs ≈ dollars per 20 min) makes remote synthesis economically absurd at
this scale. Local compute is a sunk cost. Trade-off accepted: local Russian TTS
quality is below ElevenLabs.

**Chatterbox Multilingual as the first TTS engine.** MIT license, actively
developed (Resemble AI), voice cloning + emotion control, strongest English
results in blind tests. Known risk: Russian is 6–7/10 with slight accent
artifacts. Silero (native Russian, flat but bulletproof) and XTTS-v2 (best
Russian among cloners, but dead project) come later behind a common interface.
If Chatterbox Russian fails the ear test — switch, don't polish (see PLAN kill
criteria).

**Timing strategy: per-segment TTS + atempo up to x2.** Russian runs 15–25%
longer than English; an x2 compression budget covers ~99% of segments. The user
validated by ear that x2 is acceptable. No smarter time-borrowing logic in v1.

**Local translation (Qwen3-14B via Ollama).** Operationally simpler than cloud
(no keys, no billing, offline), free at any volume. Quality loss vs frontier
models is acceptable for a dubbed track; upgrade path is a URL swap since
Ollama speaks the OpenAI protocol.

**ASR round-trip verification for every TTS segment.** Neural TTS hallucinates
(skips, repeats, mumbles). At hundreds of hours nobody will listen for defects
— the pipeline must catch them itself. Whisper-small transcribes each generated
segment; text mismatch → regenerate with a new seed.

**MKV container with dual subtitles.** Transcript (EN) and translation (RU)
already exist as pipeline artifacts — embedding both as subtitle tracks is
free. MKV over MP4: native SRT support, multiple audio tracks without
container quirks.

**Single-speaker assumption for v1.** Covers ~95% of target content.
Diarization (whisperX + pyannote) would multiply complexity by 2–3x — deferred
until actually needed.

**Rejected: Microsoft local voices.** Windows Narrator natural voices have no
ru-RU voice at all (verified 2026-07); legacy SAPI5 "Irina" is unusable.
Neural Dmitry/Svetlana are cloud-only (edge-tts) — violates local-only.

**Name: overdub.** Real audio-engineering term — laying a new track over an
existing recording, which is literally the final pipeline step.

**Voice cloning first, fixed voice as rollback.** Phase 1 clones the original
speaker (Chatterbox, short reference clip from source audio). This is the
riskiest quality axis — accent artifacts are strongest when cloning from an
English reference — but the payoff (preserved speaker identity) is highest, and
the rollback is trivial: one fixed Russian voice for everything. Decide by ear
after Phase 1; per kill criteria, don't tune reference clips endlessly.

**Custom orchestrator instead of pyVideoTrans / VideoLingo / Pandrator.**
Ready-made dubbing tools cover the happy path but not this project's core
requirements: ASR verification loop, resumable hundred-hour batches, dual
subtitle embedding, local-only pluggable TTS. They stay useful as reference
implementations for stage wiring and edge cases:
[pyVideoTrans](https://github.com/jianchang512/pyvideotrans),
[Pandrator](https://github.com/lukaszliniewicz/Pandrator).

## 2026-07-15 — PoC reframe and timing simplification

**Project stage: research / proof of concept.** Goal is a turn-key pipeline
(URL in → MKV out) proving feasibility; speed and quality must be acceptable,
not production-grade. Kill criteria removed from PLAN — nothing gates; results
are evaluated by ear at the end of Phase 1.

**No tempo cap (supersedes founding x2 decision).** Segments are sped up as
much as their slot requires, at assembly. The translation-shortening feedback
loop is dropped entirely — a few audibly broken segments per video are
acceptable losses for a PoC. Verification runs on raw audio before atempo, so
speed-up never pollutes the verify loop. Per-segment speed factor is logged in
the run report for triage (factor > ~1.8 ≈ candidate for "broken"). The
keep-length prompt instruction stays — it keeps typical factors near 1.0–1.4
for free.

**Context-aware sentence translation.** Whisper segments are not translation
units — they cut mid-thought and lose coreference. Word timestamps → sentence
re-segmentation → sentences translated in order with a rolling context window
(previous EN sentences + their RU translations). Rejected alternative:
whole-transcript translation — better prose, but re-aligning free-form RU text
to timestamps is a hard problem; 1:1 sentence mapping keeps sync trivial.

**Two text fields per sentence.** `text_ru` (raw translation → subtitles) and
`text_tts` (normalized: numbers/acronyms/Latin → Russian words → TTS input).
ASR verification compares against `text_tts` with the same normalizer applied
to both sides — comparing whisper output against raw text would loop forever
on every normalized token ("джи-пи-ю" vs "GPU").

**Per-video loop for PoC.** The stage runner processes one video through all
stages (≈3 model load/unloads per video — minutes of overhead, noise next to
synthesis time). Per-stage batching (one model load per stage per batch) is
deferred to Phase 2; artifact-driven resumable stages make the switch a loop
reorder, not a rewrite.

**VRAM constraint amended.** whisper-small (~0.5 GB) is co-resident with the
TTS engine during synthesis + verification; the one-heavy-model-at-a-time rule
applies to whisper large-v3 / Qwen3-14B / TTS.

**EN→RU fixed.** Source is always English, output always Russian. No language
detection or multi-language handling anywhere in the pipeline.

## 2026-07-15 — Stack verification (pre-code multi-agent research pass)

Verified the whole stack against primary sources before writing pipeline code
(5 researchers + adversarial refutation of risky claims + synthesis, ~960k
tokens). Full reference: STACK.md, SETUP.md. Decision-relevant outcomes:

**Chatterbox EN-ref → RU: CONDITIONAL GO, not settled.** Mechanics verified —
Russian is officially supported, `ChatterboxMultilingualTTS` + `generate()`
signature confirmed, V3 checkpoint loads, 0.5B fits 12 GB. But the core value
proposition — an English reference producing natural Russian — is REFUTED in
its strong form: Resemble AI's own docs state a language-mismatched reference
inherits its accent *by default*, and `cfg_weight=0.0` only *minimizes*, never
eliminates, the bleed. Issue #360: even a native RU reference drifts to an
English accent + broken stress after ~5 generations. No ear-test / round-trip
evidence for EN-ref→RU exists. Day-1 is therefore a load-bearing A/B ear test
(EN-ref vs RU-ref × cfg_weight 0.0/0.5), not a formality. Fallback if EN-ref
fails: fixed RU reference (loses same-voice) or Silero/XTTS behind the adapter.
The per-segment ASR round-trip is exactly the safety net for this — it's why
CONDITIONAL and not NO-GO.

**Corrections that change implementation:**
- Chatterbox 0.1.7 `from_pretrained` takes only `device` — the researched
  `t3_model="v3"` arg does NOT exist in this version (verified live via
  inspect.signature; the research over-inferred it). Corrected in code + STACK.
- Chatterbox hard-pins `torch==2.6.0` / `transformers==5.2.0` → isolated TTS
  venv (`.venv-tts`); ASR stack in `.venv-asr`. Forced by Chatterbox's pins,
  not by whisper (faster-whisper + torch can share one venv).
- Qwen3-14B Q4_K_M in 12 GB is knife-edge: pin `num_ctx` ≤ 8K (4K per segment).
  Ollama preallocates KV for the *full* num_ctx, and Windows sysmem fallback
  turns overflow into a silent 5–30× slowdown, not a clean OOM.
- faster-whisper does NOT "never OOM" — batching can hit 19 GB; keep batch/beam
  conservative. Windows CTranslate2 needs `os.add_dll_directory` for cuDNN 9.

**Refuted worries (safe to rely on):** Ollama `/v1` honors `seed`; `qwen3:14b`
carries the think toggle (thinking goes to `message.thinking`, not `content`) —
keep the regex strip only as a fallback; atempo equal-split keeps exact duration.

**RTF is unmeasured** on the RTX 4080 Mobile for every GPU stage (only
third-party / different-GPU numbers exist) — measure on host before trusting
the x5 throughput budget.

## 2026-07-15 — Day-1 engine bake-off: Chatterbox rejected, Silero adopted

Ran the day-1 ear test on real audio before writing pipeline code. Outcome
overturns two founding decisions.

**Chatterbox REJECTED.** Cloning from an English reference produced unusable
Russian (heavy accent + artifacts), as the vendor docs warned. Critically, even
WITHOUT a reference (built-in voice, `audio_prompt_path=None`) the Russian was
still bad — so it's the engine's ceiling, not just cross-lingual cloning. No
point tuning it. RTF was fine (~0.76–0.83 on the 4080M), but quality gates, not
speed. Incidental findings: the researched `t3_model="v3"` arg does not exist in
chatterbox-tts 0.1.7 (from_pretrained takes only `device`); `russian_text_stresser`
was unavailable so stress was skipped; several segments hit repetition/EOS-forcing.

**Silero v4_ru ADOPTED (voice `eugene`, `xenia` backup).** Native Russian, clean
and intelligible, deterministic, ~38 MB, runs on CPU at RTF ~0.02–0.3 (zero VRAM).
Host ear test of all 5 voices: eugene best, xenia acceptable; aidar/kseniya poor,
baya has sibilant hiss. Loaded via torch.hub (snakers4/silero-models), `apply_tts`
with built-in stress (put_accent/put_yo).

**Consequences (supersede founding decisions):**
- **"Voice cloning first, fixed voice as rollback" is DEAD.** Cross-lingual
  cloning on local models doesn't deliver clean Russian (Chatterbox failed; XTTS
  is the same category and would fail the same way). Same-voice premise dropped:
  every video gets one fixed narrator voice.
- **"Chatterbox Multilingual as first TTS engine" is superseded** by Silero.
- **XTTS rejected** without testing: dead project (Coqui folded), non-commercial
  license, same cross-lingual accent risk. The modern cloner, if expressiveness
  is ever needed, is F5-TTS — not XTTS.
- **The two-venv split collapses.** `.venv-tts` existed only for Chatterbox's
  torch==2.6.0 / transformers==5.2.0 pins. Silero needs only torch+torchaudio, so
  it can share the ASR venv; `.venv-tts` can be retired.
- **Verify-loop retry changes.** Silero is deterministic — a failed round-trip
  can't be fixed by reseeding. Failed segments are flagged, not regenerated.
- **VRAM budget eases.** With TTS on CPU, the only heavy-model contention is
  whisper-large ↔ Qwen; Stage 3 (Silero + whisper-small) barely touches VRAM.

## 2026-07-15 — Transcribe: word-level sentence resegmentation (BUILD, stdlib)

The sentence is the unit of translation/synthesis/timing. Chose a hand-rolled,
stdlib-only word-level resegmenter over buying pysbd: pysbd returns char spans
(forcing a fragile char→word remapping — the actually-hard part), is frozen since
2021, and the input (whisper large-v3 on English speech) is well-punctuated, so the
accuracy gap is small and a wrong boundary is bounded + recoverable (the overlong
splitter caps length; Phase-2 ASR verify catches garbage). Whisper segment ends are
demoted to a *pause prior*, used only to choose a good overlong-split cut point.

Adversarial review (multi-agent) fixed three real defects: zero-duration slots
(would divide-by-zero in atempo), 2–3× whisper stutters leaking into translation
('and and', 'situations. situations.'), and overlong-split cuts stranding bare
function words. Deferred as cosmetic: sub-word spacing ('decision -making') — Qwen
and TTS are robust to it and no timing/id contract is touched.

**Contract for the future assemble stage (surfaced by the review):** sentences.json
timings are monotone and NON-OVERLAPPING, but NOT gap-free — inter-sentence gaps are
legitimate pause headroom for the RU dub. assemble must anchor each RU clip at its
own `start`, NEVER butt-join clips, or it destroys sync and the pause budget.

## 2026-07-15 — Translate stage: design panel + review (BUILD)

Design settled by a 3-approach multi-agent panel (simplicity vs quality vs
robustness biases) + lens judges + synthesis, then an adversarial review pass.

**F1/F2 — LLM returns `text_ru` only; `text_tts = normalize_for_tts(text_ru)` in
deterministic Python.** Rejected design B (LLM emits `text_tts` too, JSON/delimited):
qwen's seed is not bit-exact, so an LLM-spelled `text_tts` would diverge from the
Python normalizer the verify stage applies to the ASR hypothesis, silently depressing
similarity on correct numeric dubs — the one silent-failure class the project forbids.
The normalizer must exist as a pure Python function for verify regardless; reusing it
as the sole `text_tts` source makes the round-trip exact *by construction*.

**F3 — inlined CONTEXT block in a single user message, only `status=="ok"` pairs**
(a failed English fallback never poisons the next sentence's context). Ollama `/v1`
is stateless per request, so multi-turn buys no server cache for a sliding window;
inlining gives exact, snapshot-testable control. One call per sentence, id order —
NO batching (batching risks a silent sentence merge/drop).

**F4 — validate → reseed+temp-bump retry → flagged English fallback, never drop.**
Append-only `translation.jsonl` (flush+fsync) for crash resume; contiguity enforced
(`raise`, not `assert` — a never-drop invariant must survive `python -O`); atomic
`os.replace`. Each record carries `src_en` so a re-tuned `sentences.json` (same id,
changed text) forces re-translation instead of reusing the stale RU.

**Endpoint correction — native Ollama `/api/chat` with `think: false`, NOT OpenAI
`/v1` + `/no_think`.** Empirically on the host: qwen3:14b ignores an in-prompt
`/no_think` on many samples, and its reasoning (routed to a `reasoning` field) is
truncated by `num_predict`, leaving `message.content` EMPTY (finish_reason=length).
The native `think: false` toggle reliably disables thinking — ~3× faster (5s vs 16s
per sentence, no wasted reasoning tokens) and cleaner output. This drops the `openai`
dependency; the stage is now stdlib-only (urllib). STACK.md's `/v1` sketch is
superseded for this stage.

**Normalization is SAFETY-CRITICAL, not incidental.** Because verify normalizes both
sides with the same code, a magnitude bug (a number voiced with the wrong value) is
architecturally invisible to the round-trip — it self-agrees and passes unflagged. So
the normalizer gets its own direct ground-truth tests, not only round-trip coverage.
The review caught three real magnitude/mangling bugs, now fixed + regression-tested:
grouped thousands read as decimals (`$1,999` → 1.999, ~1000× low; `10 000` → "десять
ноль"), decimal ranges shredded (`3.5-4.5` → "три.от пять…"), and Cyrillic `х`/`с` in
the multiplier/Celsius classes mangling ordinary Russian ("ось х 5", "90° севернее").

**num2words (ru locale) approved as a dependency** for Russian cardinal/ordinal
spelling (fiddly to hand-roll correctly); a stdlib 0..10⁹ speller stays as the
import-fallback. Accepted PoC loss: num2words yields nominative case, so oblique
numerals are occasionally voiced in the wrong case — self-consistent for verify, so
never false-flagged; audibly-rough-but-not-silent.

**Contract for downstream stages (synthesize / verify — for whoever builds them next):**
`translation.json` is a list of `{id, start, end, src_en, text_ru, text_tts,
status ("ok"|"failed"), attempts, flag?}`, id-contiguous with `sentences.json`.
- **synthesize** feeds `text_tts` (NEVER `text_ru`) to Silero — one wav per id, on RAW
  audio before any atempo. `en.srt`/`ru.srt` come from `src_en`/`text_ru`.
- **verify** MUST `from ..normalize import normalize_for_compare` and compare it applied to
  `text_tts` vs the whisper-small RU hypothesis — the SAME function on both sides, or numeric
  dubs false-flag. Silero is deterministic, so a failed round-trip is flagged, not reseeded.
- `status:"failed"` records are already flagged by translate (bad/echoed translation, EN
  fallback in `text_ru`); verify adds its own low-similarity flag on top, never overwrites.
- The 245 s/50-sentence throughput (~0.8× realtime, translate alone) is the batch-scale
  bottleneck created by the deliberate one-call-per-sentence (no-batching) safety choice —
  revisit batching FIRST if overnight runs get time-bound, not the normalizer or context scheme.

## 2026-07-15 — Pipeline tail (synthesize / verify / assemble / mux): design panel + review

Settled by a 3-bias design panel (minimalist / robust / timing-correctness) + synthesis, then a
4-lens adversarial review with per-finding refutation. The six load-bearing decisions:

**atempo slot = `[start_i, start_{i+1})`, not `[start_i, end_i]`.** Every clip is anchored at its
own absolute start, so consuming the following inter-sentence gap only delays the start of
*silence*, never the next sentence (independently anchored). `[start, next.start)` therefore
strictly dominates: it spends free pause before pitch-warping ("no tempo cap" ≠ "no effort").
Last segment: unbounded, factor 1.0 (nothing follows to protect; the dub may outlast the video —
MKV tolerates it). Shorter-than-slot clip → factor 1.0, place raw, remainder stays silent.

**Timeline = pre-allocated int16 buffer, absolute-offset disjoint blit, single per-segment
atempo.** Each clip written at `round(start*sr)` truncated to its slot → zero cumulative drift;
disjoint slots make direct assignment lossless (Silero writes PCM_16). ffmpeg 7.1.1 atempo range
is 0.5–100 as a *single* filter — no chaining ever. Rejected: streaming SoundFile writer (its
"100 h = 69 GB" is a per-*batch* strawman; one video ≤ ~700 MB int16 and streaming reintroduces
cursor-drift + butt-join complexity that absolute placement eliminates by construction);
float32 buffer (2× memory, no gain — disjoint, no summing).

**report.json is co-owned via `overdub/report.py` (merge-by-id), and `verify.done()` checks the
`"verify"` marker key — NOT `report.exists()`.** The marker fix is the highest-value guard in the
whole tail: with an existence gate, an `--only assemble` run (which creates report.json first)
would make `verify.done()` True forever → verification silently never runs, the one forbidden
failure. A single `upsert` preserving foreign keys stops verify/assemble clobbering each other;
`prune` drops phantom records after a re-tune shrinks the sentence count.

**verify similarity = char-level `SequenceMatcher(autojunk=False).ratio()`** on the two normalized
strings. Char-level tolerates Russian inflectional endings (`фреймворк` vs `фреймворка` → 0.947,
where a word-token metric gives 0.0 and false-flags every short segment), while gross skips still
move enough chars to trip 0.8. `autojunk=False` is mandatory — the default treats common Cyrillic
letters as junk on ≥200-char strings (sentences reach MAX_CHARS=240) and silently skews the score.

**synthesize uses the existing `build_engine(cfg)`** (the factory already existed — the minimalist
"hardcode Silero" was wrong); resume reuses a wav iff `text_tts` unchanged AND the prior flag is
not `synth_error` (transient errors always retry; mirrors translate's src_en-unchanged guard).

**mux dub codec = native `aac 128k` mono, RU dub as the DEFAULT track.** aac ships in every ffmpeg
build; the "external binaries not guaranteed" contract forbids gambling on optional `libopus`
(a one-flag post-PoC upgrade). Video is `-c:v copy`, non-negotiable. Atomic `.mkv.tmp` + os.replace
so a killed ffmpeg can't leave a partial output that satisfies `done()`.

**Review outcome:** 13 findings → 11 kept (ALL verified down to PLAUSIBLE/low, 0 CONFIRMED,
0 critical), 2 refuted (one misread `.strip()`; one invented a non-monotone-timing scenario the
transcribe contract provably forbids). 8 cheap robustness fixes applied — the seg_manifest guard
in verify, `sf.info` wrapped so a corrupt wav flags instead of crashing the stage (never block on
a bad segment), a loud RuntimeError on a zero-segment (speech-free) source, uncapped speed-factor
logging (the ≤100 clamp applies only to the ffmpeg arg), resume flag-carry, report.prune, a
report.load corruption warning, and a `missing_audio` flag. Deferred: download.py has no
`shutil.which` preflight (pre-existing, out of scope) → INBOX.

**Real bug found by *running* it, not by review:** `sf.write` cannot infer WAV format from an
atomic `…/NNNNN.wav.tmp` path → every segment failed `synth_error` on the first run. Fixed by
making SileroEngine write with explicit `format="WAV"`. Lesson: soundfile format inference keys on
the file extension, so any caller passing a temp/suffixless path must pass `format=` explicitly.

## 2026-07-16 — TTS bake-off #2: ESpeech (F5-TTS RU) wins by ear; voice cloning explored, EN-clone dropped

**Ear verdict (user, real pipeline output on 4szRHy_CT7s):** ESpeech-TTS-1_RL-V2 with the
author's demo reference is the unambiguous leader over Silero v4 (current), Silero v5, Misha
F5-RU v2 and every cloning variant. Objective metrics agree: mean sim 0.992, 0 verify flags,
mean atempo ×1.03, 0 segments over ×1.8 — timing at Silero-v4 level with far better voice.
Research trail: bakeoff/tts-research-2026-07.md (multi-agent sweep of ~20 engines + adversarial
verification; only Silero/ESpeech/Misha credibly speak Russian — "supports Russian" in a language
list is marketing, the Chatterbox lesson generalizes). Engine switch is finalized by the F5Engine
adapter integration + a full-length control run (PLAN Phase 3).

**Russian voice cloning WORKS and becomes the narrator mechanism.** F5 is a zero-shot cloner:
the fixed narrator is now a config-level reference-clip choice, decoupled from the engine. A
9.7 s phone-video clip of the user's own voice scored best-of-day similarity (0.994, 0 flags);
timbre close but not identity-level — the expected zero-shot ceiling from a compressed 10 s
reference. Reference recipe: fast, clear, neutral-prosody diction in a quiet room — the
reference's pace transfers to the synthesis, so a brisk speaker buys free atempo headroom
(this is exactly why the fast-talking ESpeech demo reference got mean ×1.03).

**EN-reference cloning (the founding "same-voice" premise): possible, fixable — DROPPED by goal.**
- Round-1 failure was NOT accent. F5 sizes its generation canvas by UTF-8 *byte* ratio
  (`utils_infer.py`: `len(text.encode("utf-8"))`); a Latin reference (1 B/char) against Cyrillic
  gen text (2 B/char) doubles the canvas and the model fills the surplus with babble that
  whisper ignores (a verify blind spot) while atempo compresses ×2.11 (36/50 segments broken).
- Both predicted fixes verified on the full video: exact Latin transcript + `speed≈1.7`
  (byte-rate ratio) → mean sim 0.980, ×1.28, 1/50 over threshold; Cyrillic phonetic ref
  transcript → 0.950 (hand-written phonetics add alignment noise — the speed fix is better).
  Formula if ever revived: exact Latin ref transcript + `speed = ref_byte_rate / 0.045 s/B`
  (measured RU rate), or per-segment `fix_duration`.
- Residual defects by ear: end-of-sentence babble ("эр" at nearly every period — per-sentence
  canvas slack lands at the tail), one mid-sentence artifact on a long sentence, and a
  "1930s-recording" character: degraded-mic timbre + slightly off Russian pronunciation
  inherited from the EN reference.
- **Decision (user): the approach is workable and could be polished further, but the project
  goal is a quality Russian dub, not speaker identity — the direction is dropped.**

**Engine-integration note regardless of cloning:** ultra-short sentences garble/echo the
reference tail (id43 "Решениям.", 0.6 s → "Together"); known F5 short-text class. Mitigate by
merging ultra-short sentences upstream or reseed-retry when the F5Engine lands.

## 2026-07-16 — Narrator voice: ESpeech demo reference adopted; voice experiments closed

**Decision (user, ear, full-video runs):** the fixed narrator is the ESpeech author's demo
reference (HF Space `Den4ikAI/ESpeech-TTS`, `ref/example.mp3`) — best across every audition round:
mean sim 0.992, 0 flags, mean atempo ×1.03 on the sample video. Rights unclarified (a real
person's voice, unknown provenance) → the clip is NOT committed; fetched from the Space at setup;
outputs stay personal-use only (README "Voices, cloning and the law").

**PD fallbacks, re-creatable with `scripts/lv_pick_refs.py` (refs deleted from disk, sources
recorded here):** LibriVox readers, all Public Domain Mark — tovarisch
(`obyknovennayaistorya_1912_librivox`; best PD result: 0.985 / 0 flags), Kazbek
(`vekhi_2011_librivox`; bass ~109 Hz), Mark Chulsky (`carousel_2511_librivox`; 826 sections
available via librivox.org/reader/8086).

**Speed calibration validated as a config mechanism.** Slow narrators (Chulsky ×1.8 natural pace)
compensated via F5 `speed` to mean atempo ×1.03–1.08 at ≤0.022 sim cost — reference pace is no
longer a disqualifier; `speed` goes into the F5Engine config.

**Celebrity-voice references (personal-use experiment) closed by the user — "сложно добиться
качества".** Round-1 YouTube interview refs → artifacts/stutter across ALL ten voices: noise,
room reverb, conversational fillers and garbled whisper transcripts of noisy speech all clone
straight into the synthesis. Round-2 studio narrations improved but still under the bar.
Repo policy unchanged: PD samples only, person-agnostic docs.

**id43 confirmed a third time** (ultra-short "Решениям.", 0.6 s → hallucinated round-trips in 2 of
4 narrator runs) — merge-ultra-short-sentences upstream + reseed-retry are REQUIRED F5Engine
integration items, not nice-to-haves.

## 2026-07-16 — F5Engine integration: design panel + adversarial review (BUILD)

Settled by a 3-bias design panel (minimalist / operability / quality) + 3 lens judges
(contracts / windows-ops / scope), synthesis by the main session; then a 4-lens adversarial
review with per-finding refutation (16 findings kept, 0 refuted, all fixed). Load-bearing calls:

**Worker process in `.venv-f5tts`, never f5-tts into `.venv-asr` (unanimous).** pip dry-run
evidence: resolver keeps torch 2.11 but downgrades numpy 2.5.1→2.4.6 under working
ctranslate2/onnxruntime, adds ~110 packages (gradio, wandb, datasets), and pulls torchcodec
0.15 built against torch 2.8 — an ABI gamble inside the venv every stage depends on.
Worker mechanics: JSONL over stdio; the worker's FIRST act is fd-level
`os.dup(1)` + `os.dup2(2,1)` BEFORE heavy imports (Python-level sys.stdout rebinding does not
survive native fd-1 writers); stderr inherited (live progress, no pipe deadlock class); config
via argv (Task-Manager-visible); reader-thread + Queue timeouts (the only sane Windows pipe
timeout; constants in f5.py, not config); per-request id echo (protocol corruption == crash);
respawn+resend once per request; EVERY consecutive failure — transport, respawn handshake, or
an ok:false reply (sticky CUDA context dies per-request while the process lives — review
finding) — counts toward a 3-strike TtsFatalError that escapes the per-segment catch. Startup
~30 s measured (imports 17 s + RUAccent 6 s + model 3 s); warm synth ~×1.1 of audio duration;
0.7 GiB VRAM.

**Reseed-retry lives in SYNTHESIZE, not verify (2 of 3 judges, over the scope judge's
objection).** Deciding invariant: segments/manifest.json stays single-writer — assemble derives
atempo factors from manifest `samples`, so a verify-side wav replacement with a stale manifest
is silent timing desync, the forbidden class; ordering discipline can only narrow that window,
single-writer eliminates it. Every fresh F5 segment gets an in-stage whisper-small round-trip
via `asr.roundtrip_similarity` (ONE function shared with verify — same-transform-both-sides,
the normalize.py precedent); < threshold → seeds tts_seed+1..+3, keep-best by similarity.
Accepted costs: double ASR round-trip (~+90 s / 39-min video), whisper-small coupled into
synthesize (loud failure, co-residency pre-blessed). Verify stays a pure judge — sole
similarity-flagging authority, byte-identical Silero path. Proven mechanics (micro-test,
threshold 0.9 / seed 7): id43 retried 4 attempts, best 0.875 kept (seed 9), honestly flagged.

**synth_key gates all wav reuse.** Everything that changes rendered audio enters one canonical
string: engine | ref-stem:content-sha1[:8] (the narrator ref is fetched-at-setup and mutable at
a stable path — stems lie) | ckpt+vocab name:size (review catch: a checkpoint swap must not
serve stale wavs) | sr | nfe | speed | base seed. Legacy Silero manifests reconstruct their key
read-side (zero migration). Manifest v2 adds per-segment seed/attempts/synth_sim and a
"complete" marker: the manifest is downgraded to complete:false BEFORE any wav mutates and
flushed every 25 fresh segments (review catch: a crash mid-resynthesis must not leave a
complete:true manifest over divergent wavs; F5 makes the stage ~20× longer than Silero, so
mid-stage interruption is now a real overnight event).

**Ultra-short mitigation = merge upstream in transcribe (char-criterion) + reseed as the net.**
MIN_SENT_CHARS=15 on EN chars — the failure mechanism is F5's UTF-8-byte duration canvas, so
chars, not seconds, are causal; MERGE_GAP_MAX=0.6 s; cumulative absorption of a merge chain
capped at 1.5 s (review catch); merged range must pass the existing _too_long. Pure pass
between _split_overlong and id assignment; unit-tested with synthetic word lists. Existing
workdirs keep their segmentation (done() gates on sentences.json); a --force transcribe on an
old workdir shifts ids after the first merge → src_en mismatches cascade into near-full Qwen
re-translation (~23 min on a 39-min video) — correct (stale RU must die) but expensive, don't
--force transcribe casually.

**Config surface minimal.** Engine-agnostic tts_seed/tts_max_retries + 7 f5_* keys; no
device/timeout knobs; the retry gate reuses similarity_threshold (no second threshold to
drift). `tts_engine` default stays "silero" until the Phase-3 control run + user ear check
pass; the flip is its own commit.

**Control-run gates fixed by the judges' fact-check (all three designers were wrong twice).**
The ultra-short "Решениям." is id43 of the SAMPLE video (4szRHy_CT7s), not the control video
(its ultra-short is id101 "Хорошо.", 0.22 s); and the Silero baseline's single flag is id189 —
a proper-noun-class failure whose text_tts is identical under F5, so it will likely flag again
regardless of engine. Gates are therefore ABSOLUTE (flag rate ≤ 2% of 315 after retries, id189
pre-registered as expected-to-flag; baseline comparison advisory), plus mean sim ≥ 0.985,
mean atempo ≤ 1.10, synth+verify RTF ≤ 0.5×, and the binding user ear check.

## 2026-07-16 — Dead-air ear verdict (user): noticeably better overall; mix modes iterate

**Overall: ощутимо лучше** — the dead-air mechanism (slot-fill + units) is validated by ear.
id101 ("Хорошо.", the ultra-short that failed as a lone segment) is now PERFECT inside its
group — L2 grouping confirmed as the structural fix for the ultra-short class.

**Defect found (17:02, unit [135,136,137]):** three short sentences in a 2.76 s EN span,
RU needed ~4 s → native compression ×1.327 → mid-word cutoff (first phrase truncated, next
begins). synth_sim 0.8361 scraped past the 0.8 threshold — no retry, no flag. LESSON:
post-hoc atempo compresses uniformly and never drops words; F5 NATIVE compression at
≥~1.3 does drop them, and char-similarity on long joined strings under-penalizes the loss.
Fix direction: native speed stays for STRETCHING only (safe direction, ear-validated);
compression returns to atempo (f5_speed_ceil → ~1.0–1.15), plus a stricter sim gate for
any compressed unit. The ×1.6-at-≤0.022-sim bake-off number measured ASR similarity, not
word survival — it over-promised for compression.

**Duck: mechanism right, depth wrong** — −15 dB leaves the EN original too audible. Retest
at −22..−25 dB (module constant). **Bed: content-dependent, inapplicable here** — this
video is nearly music-free, so the no-vocals stem is near-silence and the dead-air feel
returns. Re-check on a music-heavy source before judging the mechanism; a bed-RMS census
with automatic duck-fallback is the likely production shape. dub_mix default stays
"replace" until the duck depth retest.

## 2026-07-16 — Dead-air elimination: design panel + review (BUILD)

Panel (minimalist/contracts/audio + 3 judges) + 4-lens adversarial review (20 findings,
1 refuted, all fixed). Three composable layers against the measured 607-s underfill:

**L1 slot-fill native speed — parent-side pure `plan_speed()` (2/3 judges).** F5's duration
canvas is deterministic (`out ≈ ref_sec·gen_bytes/ref_bytes/speed`, raw pre-accent bytes both
sides — stress-mark inflation cancels; bench: |err| ≤ 1.5% even on group-shaped 300-char
texts). Three branches: stretch to the SPAN (never the slot — real pauses stay pauses),
neutral when the free gap absorbs the spill (the DECISIONS gap-headroom principle), native
compress ≤ ceil before atempo tops up. Caps are MULTIPLIERS of f5_speed (narrator-pace
recalibration shifts the window); floor 0.75 by the pre-registered bench rule (0.7 passed
sims down to 0.95+, ship +0.05 margin). Retries reuse the same speed — keep-best compares
identical canvases. Worker reports EFFECTIVE speed (F5 forces 0.3 under 10 UTF-8 bytes).

**L2 render units — group at SYNTHESIS, not transcribe (unanimous rejection of widening the
transcribe merge: per-sentence subtitles are binding, and re-segmentation would cascade into
full re-translation).** build_units: gap ≤ 0.4 s, span ≤ 12 s (F5 trained regime, judges'
correction of the 18–24 s drafts), joined ≤ 300 chars; empty-text singletons break chains.
Manifest v3 "units" as the single structural truth; verify/assemble read units, never
recompute. Non-negotiable correction from the contracts judge: verify's reference text joins
from CURRENT translation.json — referencing the manifest would kill the stale-translation
net. Per-sentence report records with group_id keep translation-id contiguity verbatim.

**L3 dub_mix knob (replace/duck/bed), mixing in MUX.** Duck = explicit sample-exact numpy
envelope (−15 dB, ramps 50/300 ms, intervals merged < 1 s) — beats sidechaincompress on
determinism (no program-dependent pumping, no compressor keyed by F5 breaths); the
cmdline-length argument against envelopes was factually void (-filter_complex_script), the
decision is purely perceptual. Duck intervals = unit spans EXTENDED to placed audio (review:
the slot-fill neutral branch deliberately spills RU past the span — that tail must not ride
over full-level EN). Bed = htdemucs no-vocals at −6 dB, own .venv-demucs, CLI subprocess,
44.1 k stereo extract (the 16 k mono STT wav is unusable). ALL modes RMS-align the dub to
the original's speech loudness (±6 dB cap) — otherwise the A/B measures loudness, not
mechanism. Empty/failed units are deliberately NOT ducked: full-level EN there is the
honest fallback (on the ear checklist).

**Self-healing done() chain (review-driven).** verify/assemble gate on synth_key AND
units_key (content fingerprint — same-key --force resynthesis is otherwise invisible);
mux gates on dub_mix/synth_key stamps plus make-style mtime deps (re-assembled dub → re-mux).
Ordering discipline: the ARTIFACT flips before the stamp, everywhere — review confirmed
stamp-first turns a failed os.replace (the documented AV hold) into permanently-served
stale audio. Ear-loop consequence: flipping dub_mix in the TOML re-runs exactly mux.

**Known accepted losses (named, not hidden):** group-level similarity dilutes per-sentence
sensitivity at the same 0.8 threshold (re-tune queued — PLAN open question); subtitle cues
keep source timings while grouped audio renders continuously (drift bounded by the 12 s
span cap; on the ear checklist); --repair granularity becomes the unit, not the sentence.

## 2026-07-16 — Phase 3 closed by ear; roadmap reprioritized: dead air first

**Ear verdict (user, 39-min F5 control run):** id26/id136/id200 fine, id150 almost fine
("Minecraft, Valheim" good, "No Man's Sky" bad), id189 acceptable, id101 (ultra-short "Okay.")
bad. Overall approved → default `tts_engine` flipped to "f5"; Silero stays the fallback.

**id101 is a load-bearing data point:** its round-trip sim was 1.0 yet the ear says bad — the
ASR-blindness of verify is now CONFIRMED on real content, not just on synthetic babble. The
ultra-short class needs structural fixes (merge/grouping), not retry luck; and the babble
detector (duration heuristic) moves up in relevance.

**Dead-air decomposition (measured, control run):** 665 s of silence in a 2333 s dub =
607 s RU-underfill (the fast ESpeech narrator finishes each sentence well before the EN span
ends; the dub buffer is digital zero there) + 68 s inherited inter-sentence gaps (median
0.14 s) + 6 s spill. The problem is NOT bad timings — it is systematic underfill plus a
zero-noise-floor track. Consequence: the fix is three composable layers (slot-fill native F5
speed incl. stretch, sentence grouping gap≤0.4 s, overlay mix duck/bed), not timing surgery.

**Priority reorder (user):** dead-air first (simpler, bigger payoff), proper nouns second
(harder, smaller payoff — F5 already softened it: id189 0.95 vs Silero's 0.661), everything
else after those two. Cloud-translate note: after F5, translate is ~45% of wall-clock
(co-bottleneck with synth), not 80% — the founding premise of roadmap item "cloud translate"
weakened but the item stays.

**Translate quality nit (ear):** ids 134–137 voice «причина» three times in a row — the
rolling context window keeps terminology consistent but has no repetition-avoidance. INBOX.

## 2026-07-16 — Local-only constraint amended: optional cloud-translate mode approved

**User decision:** an explicitly opt-in cloud translation mode (Anthropic API, Sonnet-class) is
a permitted exception to the founding local-only constraint. Rationale: translate is 80% of
wall-clock (RTF 0.60, the only real bottleneck) and the likeliest quality ceiling; a cloud pass
would give the largest single speed win while keeping quality. Boundaries: OFF by default, a
deliberate flag (no silent fallback to cloud), local Qwen path remains the default and must keep
working; STT/TTS stay local unconditionally. CLAUDE.md hard-constraints section amended to match.

## 2026-07-17 — Compression back to atempo; bed at original level is THE mix mode (ear)

**f5_speed_ceil 1.6 → 1.1 + stricter gate for compressed units.** The 17:02 defect (unit
[135-137], native ×1.327, mid-word cutoff at synth_sim 0.836) confirmed the bake-off blind
spot: ASR similarity measures character overlap, not word survival — F5 native compression
≥~1.3 drops words outright, while atempo compresses uniformly and never drops any. Native
compression is now capped at 1.1×base (mild pace-up, safely under the observed word-drop
regime); everything above tops up via atempo at assembly. Any unit rendered above base pace
must clear `similarity_threshold_compressed = 0.9` — ONE shared `unit_sim_threshold()` used
by both synthesize's reseed loop and verify (same one-function discipline as
`roundtrip_similarity`, so the two gates can never drift).

**Mix mode (user ear, binding): bed WITHOUT attenuation; duck and replace are worse.**
`_BED_GAIN` −6 dB → 0 dB; `dub_mix` default flips to "bed". The planned duck-depth retest
(−22..−25 dB) and the bed-RMS-census/auto-duck-fallback idea are cancelled. Named accepted
residual: on near-music-free sources the no-vocals stem is ≈silence, so bed degrades to
replace and the remaining in-span silence (204 s on the control) stays silent — accepted,
L1+L2 already removed two thirds. A sanity-check on a music-heavy video stays on the plan.

**L1 "measure instead of predict" (user question, answered — rejected):** cutoffs leave no
silence to measure — a compressed canvas is fully voiced with words missing; only content
verification catches it (and did: 0.836, gate was just too lax). Measurement already sits
where it can: atempo derives from actual wav samples, in_span_silence is reported, every
unit round-trips through ASR. The canvas prediction (err ≤1.5%) only picks the speed knob
BEFORE synthesis; a synth-measure-resynth loop would ~double GPU time (242/256 units
stretched) to correct a ≤1.5% error.

## 2026-07-17 — Dead-air closed by ear (final verdict)

**User verdict:** L3 bed on the music-heavy check (tJP6SKfo49c) works perfectly; the 17:02
cutoff fix is acceptable; the remaining artifacts roughly correspond to the source's own
unusual intonations and stutters — i.e. they mirror the original delivery, they are not
pipeline defects. The dead-air problem group is CLOSED. Accepted residuals, named: 203.8 s
in-span silence on the speech-only control (bed ≈ replace there — no stem to carry) and
delivery-correlated artifacts. Roadmap top is now proper nouns (PLAN item 1).

## 2026-07-17 — Priorities set; base sim gate → 0.9; UTMOS and four items demoted

**Near-term roadmap (user):** proper nouns → batch queue → stop switch → babble duration
heuristic. New batch-queue requirement: output files named by original video title + video id
(yt-dlp metadata).

**Base similarity_threshold 0.8 → 0.9 (user).** Units are long joined strings that dilute
local defects — the 17:02 word-drop scored 0.836 and passed the per-sentence-calibrated 0.8;
both current runs sit comfortably above 0.9 (unit min 0.926 / 0.9415). Further tuning
deferred entirely until production flags misbehave. Known side effect, accepted: Silero
fallback runs will flag more (its per-sentence sample min was 0.875) — flags are warnings,
the pipeline never blocks.

**UTMOS (4b) judged high-cost/low-effect for now:** the duration heuristic covers the cheap
majority of the babble class; MOS adds a model integration plus calibration data that only
batch runs will produce. Revisit only if the heuristic provably misses defects.

**Demoted to PLAN Deferred (not near-term, user):** cloud translate, gender-matched narrator,
multi-speaker violation detector, sim-threshold re-tune analysis, Arc B390 path (Phase 4
section removed from PLAN; Silero-on-CPU remains the safe TTS there, F5-on-XPU is an
unproven spike). Phase 2 section dissolved into roadmap items 2-4 — PLAN now holds one
roadmap, one backlog, one deferred list.

## 2026-07-17 — Batch queue + stop switch (BUILD)

Settled by a 2-bias design panel (minimal-diff / overnight-operability) + judge, then 4-lens
adversarial review with 2-skeptic per-finding verification (13 findings, 11 confirmed, all
fixed). Load-bearing calls:

**Exit codes are the batch API: 0 ok / 1 any fail / 2 usage / 3 stop-halt.** An overnight
wrapper must distinguish "stopped" from "broke" without parsing stdout; fail wins over halt.
KeyboardInterrupt is deliberately caught nowhere — the operator pressing Ctrl+C is at the
console; a partial-summary handler is 4 lines for near-zero value.

**STOP is consumed at honor time, not at catch site.** `check_stop(work_root, where)` in
pipeline.py unlinks then raises — a plain re-run always resumes. The startup sweep in cli.main
reuses the same helper (a stale file can never silently no-op the run); if the unlink fails
persistently (AV hold / open handle), startup aborts loudly instead of re-halting at the first
boundary with a misleading message. Checkpoint sits BEFORE the only/done filters — a stop
halts at the next stage boundary even through a run of [skip] lines. The between-videos
checkpoint was removed by review: run_pipeline's "before stage 'download'" check fires first
thing for every video and covers the same gap (accepted observable change: a between-videos
stop prints the next video's header and reports as its "stop" row).

**Export = hardlink with copy fallback; persisted title is never refreshed.** Same-volume
hardlink is free at MKV sizes; .tmp + replace_retry keeps the flip atomic in both paths.
Naming stability beats freshness for an archive dir; stale exports of the same video id are
glob-cleaned (the offline-fallback→online-backfill rename case). Named accepted residual:
an export left open in a player without FILE_SHARE_DELETE can block a later re-mux's
os.replace of output.mkv (loud FAIL, batch continues) — documented in the code, not worked
around with always-copy.

**Review catches worth remembering:** yt-dlp encodes piped stdout in the locale ANSI codepage,
not UTF-8 — the title backfill runs with PYTHONUTF8=1 in the child env or Cyrillic titles
mangle on stock Windows (this host works only because ACP=65001); with `-o source.mkv` the
info-json sidecar is `source.info.json` on the mkv merge path but `source.mkv.info.json` on
the single-format `/b` fallback — both probed; UnicodeDecodeError from a torn info.json is a
ValueError, NOT an OSError/JSONDecodeError — the guard catches (OSError, ValueError) or a
torn file blocks the backfill forever; queue files from PowerShell 5.1 carry a BOM that
str.strip() does not remove — read with utf-8-sig.

**Config surface: exactly one new key (`output_dir`, default `out/`).** Stop-file name,
120-char title cap and 30 s backfill timeout are constants — knobs without a demonstrated
tuner are dead config surface. Per-stage batching (one model load per stage per batch)
explicitly NOT built — revisit only if per-video model reload overhead is measured to matter.

## 2026-07-17 — Proper nouns: pronunciation chain (BUILD)

**Chain: PHRASES → WORDS → plural tail → case-gated acronyms → letter names → rule
transliteration (`overdub/pronounce.py`), wired into normalize as passes 0a/0b + the pass-6
resolver.** Phrases run FIRST on raw text (keys may contain digits/apostrophes, so they must
precede every numeric pass); a phrase earns a slot only when word-by-word composition cannot
produce the target ("no man's sky" — the id150 ear case). The fallback replaced the naive
per-letter translit with an ordered left-to-right practical-transcription scanner (~74 rules),
killing the sky→скй class structurally: every corpus output word ≥3 chars must contain a vowel
(tested). Committed contested readings: хейло, энвидиа, пайтон, твитч, uh→э-э (EN hesitation
as RU filler keeps slot timing). The roadmap's "per-run cache" is reinterpreted as the
AUDIT-ONLY artifact `pronounce_audit.json` (written by translate, read by nobody):
normalize_for_tts must stay pure/deterministic — a run-scoped resolution cache would desync
verify's two sides, the forbidden silent class. A/B on a renormed copy of the f5-control run
(tools/renorm_workdir.py; 31/315 records changed) is the acceptance path; expect verify flag
counts to RISE — the old low count was the masking bug (broken translit self-agreed in the
round-trip at sim 0.93–0.97, only id189 ever flagged).

## 2026-07-17 — Segmentation cluster (BUILD): the seg_end "pause" was a whisper VAD artifact

**Root cause, measured not guessed.** The user ear-reported two mid-phrase splits; the
Measure phase (running resegment() on the persisted words.json — the offline re-tune lever the
stage was built for) disproved the obvious "it's the 15 s cap" reading: both emitted spans were
recursion LEAVES with `_too_long`=False. The real defect: `_split_overlong` branch 1 treated
`W.seg_end` (last word of a whisper segment) as a speaker pause, but 73% of corpus seg_ends
carry a 0.000 s gap to the next word — whisper ends segments mid-phrase on a VAD/window
boundary. Both bugs cut at gap 0.000, the point chosen purely by time-midpoint proximity
('survival' beat 'games' by 0.030 s, severing "survival | exploration crafting games"). Branch 1
made ~90% of all cuts and 95% were fake pauses.

**Fix = a real-silence gate, not a bigger dictionary.** `MIN_PAUSE_SEC=0.20` on branch 1
(measured plateau: any value 0.10–0.50 fixes both bugs, total spread one span — a plateau, not
a fit); `_ok_cut` veto (no cut ends on a bare function word, none inside a hyphen-split
compound) applied to ALL THREE branches — a filter in 1/2, a sort *preference* in 3 so branch 3
always cuts and termination is preserved. `_CONJ`→`_CUT_BEFORE` drops the ambiguous
subordinators (that/which/who/as/if/when/where/…): once branch 1 is gated, the next-word test
jumps ~11→~110 cuts and cutting before "that" severs verb-from-object — the id150 cascade class
(review finding, critical). Item E shipped ('.'+seg_end before a lowercase word is a boundary;
11/11 genuine on corpus, decimals can't reach it).

**C and D rejected on evidence, not deferred lightly.** Tolerance band (C): does not fix bug A
(the cut is at depth 1 on a 70 s parent, far above any 16.5 s band), and it breaches F5's 12 s
unit cap while letting `_merge_short` rebuild long sentences (it calls `_too_long`). Run-on
recovery (D, Capital-after-lowercase): ~5% precision, cuts inside «Call of|Duty»; the only safe
variant (seg_end AND gap≥0.2) fires once in 7,483 words — N=1 cannot calibrate a rule whose
dangerous variants sit one predicate away. The ear reported A/B/F/G; C/D were our ideas.

**Item F (names stay Latin) — accepted silent-loss class, named.** The translate prompt now
mandates Latin script + canonical casing for game/brand/platform/company names so pronounce.py
owns them; personal names stay Russian (Qwen renders Джонсон/Миямото well, the rule
transliterator mangles them). ACCEPTED COST: an out-of-dict game/company name (Bungie→бунджи,
Bethesda→бетесда) now hits the rule fallback and — per pronounce.py's own docstring — self-agrees
through verify unflagged. The 3-video corpus (the dict was fit to it) cannot exercise this; the
only detector is promoting `pronounce_audit.json` to a pre-batch operator gate (INBOX). This is
the deliberate trade for making Qwen's previously-unrecoverable Cyrillic transliteration
(«Ранескэпом») recoverable and auditable.

**Item F residual (dangling verbs) accepted, not fixed.** `_ok_cut` still vetoes only the
16-word `_STOP` set, so a cut can end on a bare verb/pronoun ("you have" / "i think"; ~9 corpus
cuts). Accepted: a dangling verb → a dangling verb is strictly better than the fake-pause cut it
replaced, and widening _STOP is a large unmeasured change that risks more midpoint fallbacks.

**Upstream cause bigger than the whole cluster (both designs flagged it).** x7 has 6
terminator-free ranges >60 s (worst 206 s / 2968 chars → ~19 bisected sentences) because the
whisper call sets `condition_on_previous_text=False`. The gap-gate makes those bisections
defensible, not correct; re-enabling context or a punctuation-restore pass would retire the
class. → PLAN backlog + INBOX (measure the hallucination risk that turned it off).

**Cascade cost restated (DP10).** Both transcribe id-shift and the prompt change invalidate all
four corpus workdirs' translations (~23 min re-translate/video). assemble's cue split is
display-only — it never touches sentences.json/ids/timings. After a fresh --force transcribe the
ear-session ids shift by −2 past id102 (id149→147, id150→148, id188→186, id189→187): reason from
text, not the old numbers.

## 2026-07-17 — Whisper punctuation context: the segmentation ROOT fix (ear-driven, measured)

**The cluster fix was damage control; this is the cause.** Ear check of the segfix run: the
"period mid-sentence" defect the user heard was frequent (fragment-opening sentences 181/314).
Layered trace of a single case (id148, condition=False): whisper's EN `sentences.json` text ends
`...and then you have` — last char `e`, NO period; Qwen's `text_ru` ends `...у вас есть.` — with a
period. So the FULL STOP is written by Qwen, but the BOUNDARY (where the phrase is severed) is
`_split_overlong`'s, firing because whisper returned a 60-206 s terminator-free block. Qwen
translates 1:1 and cannot merge across units — it inherits the break, it does not create it.

**Root proven by a single-variable experiment.** Changed ONLY the whisper flag
`condition_on_previous_text` False→True (Qwen and the splitter untouched) and re-ran ASR on the
ear video: max terminator-free raw range 206.1 s → 27.2 s, sentences 314 → 427 (real
boundaries), sents >15 s = 0, and both ear cases became whole in ONE sentence ("...met through
Xbox Live or through... a forum or YouTube"; "...you have so many of these like survival
exploration crafting... Minecraft, Valheim, No Man's Sky"). Since only whisper changed, the
break was whisper's punctuation gap, not Qwen — a Qwen fix (e.g. "don't end a fragment with a
period") would not help: the thought is still split into two synth units with a pause between.

**Hallucination risk (why the flag was off) measured, not assumed.** condition=True is known to
loop on low-signal audio; that is why it was False. A/B on the music video (the worst case for
looping): longest identical-token run = 3 (ordinary words), zero nonsense loops, max sentence
9.3 s. Safe on both poles measured (clean monologue + music, N=2). Shipped as a Config flag
`whisper_condition_on_previous` (default True), NOT hardcoded — a future source that loops can
set it False without a code change; the gap-gate/`_CUT_BEFORE` cluster stays as the fallback
splitter for genuinely long single sentences.

**Consequence for the cluster.** With context on, `_split_overlong` rarely fires (max sentence
14.2 s on the ear video), so the 31-agent cluster is now second-order. It is NOT reverted (fake
VAD-pause cuts were objectively worse and other videos will have real >15 s sentences), but the
priority lesson stands: Measure surfaced the 206 s blocks and they were filed to backlog instead
of tested first — the one-line flag outperformed the whole cluster. Test the root before
polishing the symptom.

## 2026-07-18 — Gemma-3-12B replaces Qwen3-14B as the translation model

**Decision: Gemma-3-12B is the default translator; Qwen3-14B is removed entirely — not kept even
as an option.** The user's standing observation ("Qwen местами сыпется") was confirmed and fixed.

**Evidence: an 8-video A/B on identical segmentation.** Both models were fed the SAME
`sentences.json` (the 8 videos the Qwen stats batch had finished), so the only variable is the
translator — the demucs bed and everything downstream are byte-identical. 508 sentences. Objective:
RU/EN length ratio (dubbing fit) median 1.062 vs 1.086 (Gemma tighter → less atempo stretch);
translate flags 4 vs 6; verify round-trip sim ~0.991 vs ~0.988 (≈); lower mean max speed-factor.
Qualitative (user read ~100 phrases, all better on Gemma; + a divergence scan): Qwen's real
defects were absent in Gemma — "эффективное/эффективное" duplicated on "effectively, efficiently"
(twice), an untranslated "fluent" left in Latin, "Интеллектуальная грамотность" for "AI fluency".

**Cost accepted: ~16% slower.** Same 508 sentences: 5.30 vs 4.58 s/sentence (1.08–1.21× per
video). translate is the pipeline bottleneck, so end-to-end ≈ +8–10%. At 100-hour batch scale that
is real (+~1–1.5 h/overnight) but the quality jump dominates. (Counter-intuitive for 12B<14B;
thinking is not the cause — Qwen ran think:false, Gemma has none — it is Gemma-3 arch/tokenisation.)

**Gemma-3 API differences forced a code change, not a config swap.** Gemma 3 has no thinking mode
(Ollama HTTP-400s if a "think" key reaches it) and its chat template rejects a system role. The
translate stage now folds SYSTEM into the single user turn and sends no "think" key — replacing
Qwen's native `think:false` + separate system message. It was built first as two config flags
(`ollama_system_role`/`ollama_send_think`) for a clean A/B that kept the Qwen wire-request
byte-identical (proven); once Gemma won, the flags AND the Qwen branch were removed (YAGNI). Default
`ollama_model` qwen3:14b → gemma3:12b (~7.5 GB VRAM loaded, was ~8.6 GB).

## 2026-07-18 — Silero v5 acknowledged: the good no-sample TTS option

**User verdict:** Silero v5 is also good as TTS — quality slightly below F5/ESpeech, but it
needs NO narrator reference clip: zero voice-sample setup, zero rights questions (the F5
narrator carries the README rights caveat). Recorded as a first-class alternative, not just
a legacy fallback; the engine choice is now: F5/ESpeech = best quality + needs a reference,
Silero = slightly lower quality + no sample. The in-code adapter still loads v4_ru — bumping
to v5 (`v5_5_ru` via torch.hub) is a small change with one caveat: v5 rejects Latin script
(text_tts is Cyrillic-only by the normalize contract already; add an out-of-alphabet filter
per the bake-off note). → INBOX chore. Bake-off history unchanged: ESpeech led v5 by ear
(2026-07-16); this verdict upgrades v5's standing as the no-sample option.

## 2026-07-18 — Sonnet verdict (user read-through): both translation routes stay; Sonnet semi-automatic is the PRIMARY route

**User verdict on the 508-sentence A/B read-through:** Sonnet's quality is noticeably
better and its speed significantly higher (~3× serial, order-of-magnitude in parallel) —
and, notably, it replaces the pipeline's heaviest, longest stage (translate is the local
bottleneck). Both routes are declared good and both stay:
- **Gemma-3-12B (local)** — good quality, free, offline, slow; remains the in-pipeline
  default. The local path must keep working (hard constraint unchanged).
- **Claude Sonnet (cloud)** — requires a subscription; better quality, much faster.

**Primary route: Sonnet in SEMI-AUTOMATIC mode** — the sub-agent workflow proven by the
A/B spike (transcribe in-pipeline → Sonnet sub-agents write translation.json under the
translate contract → pipeline resumes from synthesize), NOT an in-pipeline API
integration. The approved opt-in Anthropic API path (2026-07-16) stays approved but is no
longer the next step — build it only if the semi-automatic seam's manual step becomes the
bottleneck. Cloud translation remains explicit and per-run, never a silent fallback.
Runbook for both routes: README "Running".

**Top blind spot after this: translation COMPLETENESS is unmeasured.** verify's ASR round-trip
checks TTS fidelity to `text_ru`, not that `text_ru` is a complete translation of the English.
Gemma's tightness occasionally drops a word (measured: 1 of 3 adverbs on Dmgujo id1) and nothing
flags it — same silent-loss class as the out-of-dict pronunciation echo. A completeness check is now
the highest-value verify upgrade (PLAN roadmap 1).

## 2026-07-19 — 4-way translate bake-off on x7DfiXqSEdM: Gemma prompt-bundle dropped, Sonnet isolation dropped

Single-video A/B/C/D on one frozen `sentences.json` (x7DfiXqSEdM, 427 sentences, ~39 min,
first-person vlog monologue on social gaming), same input, four translators:
1. **gemma-base** — current SYSTEM prompt (shipping local default).
2. **gemma-impr** — the four-change bundle from `.claude/gemma-translate-ab-brief.md`:
   completeness-first reframe (#1) + forward lookahead of the next 1-2 EN sentences (#2) +
   1-2 few-shot examples inside SYSTEM (#3) + anti-repetition rule (#4). Ran on a FRESH workdir
   (the brief's stale-`src_en`-reuse trap) via a branch build of `translate.py`.
3. **sonnet-v1** — Sonnet sub-agent, `general-purpose` type (Tools:*), whole document in context.
4. **sonnet-iso** — Sonnet sub-agent, a custom isolated `overdub-translator` type (Read/Write only),
   built to test whether a narrow agent translates cleaner than the broad one.

**Objective metrics** (all four: 427 sentences, 0 `_is_bad` flags):

| variant | len ratio med | >1.5× slots | name_loss* | digit_loss* |
|---|---|---|---|---|
| gemma-base | 0.98 | 2 | 29 | 6 |
| gemma-impr | 1.06 | **20** | 27 | 5 |
| sonnet-v1  | 0.93 | 1 | 21 | **0** |
| sonnet-iso | 0.95 | 1 | 21 | 0 |

\* noisy heuristic (EN names/digits absent from RU); valid for cross-variant comparison, not absolute.
Pairwise differ-counts: base↔impr 345/427, v1↔iso 344/427 (81%), v1↔gemma-base 411/427 (96%) —
engine choice moves the translation far more than any prompt/agent tweak.

**User read-through verdict:**
- **Gemma base vs impr → PARITY on text, base wins for the video.** impr makes no outright errors
  (base occasionally mistranslates), but builds clumsier, harder-to-parse sentences. Net: the bundle
  is not worth it. The mechanical cause is change #1 (completeness reframe): it inflated length
  (+7% median, **×10 more >1.5× slots: 2→20**) without recovering meaning in the target spots (the
  `[46]` "medium of a game" drop it was meant to fix survived) — it just added filler and register
  stiffness. **DROPPED; branch `gemma-completeness-ab` discarded, `translate.py` unchanged.**
- **Sonnet v1 vs iso → difference small, v1 slightly more natural** (iso calques the English a touch
  more often). Isolation does NOT improve translation quality; its only value is operational
  (narrow tool-set, determinism, tokens). Not worth a second agent type. **iso agent DROPPED; the
  `overdub-sonnet-batch` skill stays on `general-purpose`.**
- **Sonnet vs Gemma → Sonnet is the clear winner** — more accurate and more natural speech. On this
  lifestyle vlog the gap is clear; on the earlier science-pop read-through it was even wider
  (content-dependent). Confirms Sonnet = PRIMARY route (DECISIONS 2026-07-18).

**Kept:** the semi-automatic Sonnet-route infrastructure — `.claude/skills/overdub-sonnet-batch/`
(fixed transcribe → sub-agent draft → resume order) + `scripts/build_translation.py` (sub-agent
writes only `{id, text_ru}`; the helper fills src_en/timings, derives `text_tts` via the pipeline's
own `normalize_for_tts`, gates each line through `_is_bad`, enforces id-contiguity — so the translate
contract never rides on an LLM's discipline). Validated on this 427-sentence run.

**Completeness stays the top blind spot but the prompt-bundle is NOT the fix** (this experiment
falsified it). The verify-side completeness check (PLAN roadmap 1) remains the right lever.
Caveat: n=1 video, lifestyle content — indicative, not a multi-content-type A/B.

## 2026-07-19 — Completeness check (verify-side, deterministic A+B) — shipped, all 4 detectors kept

After rejecting the LLM-judge / embedding semantic check as PoC over-engineering (the analysis
earlier this day), built the cheap deterministic A+B insurance via an ultracode workflow (8 agents:
understand → build → adversarial verify → synthesize). New pure module `overdub/completeness.py` —
four NON-BLOCKING per-sentence detectors written to `report.json` at verify:
- **num_loss** — a digit run in src_en absent from text_ru (leans on the keep-digits rule;
  `normalize._n2w` suppresses legitimately spelled-out numbers).
- **neg_loss** — an EN negation marker with no RU не/ни/без in text_ru (guards meaning INVERSION,
  the worst silent loss).
- **entity_loss** — a Titlecase Latin name in src_en absent from text_ru (leans on keep-Latin-names).
- **length_short** — len(text_ru)/len(src_en) < `completeness_len_ratio_min` (0.45) with a 30-char
  src guard (catches a catastrophic clause drop the precise signals miss).
- **dup_adjacent** — *(added later the same day, PLAN item 0c — listed here so this enumeration
  stays complete)* two ADJACENT **src_en** sentences with char-level
  `SequenceMatcher(autojunk=False).ratio() > 0.80`, first member > 25 chars. The only
  CROSS-SENTENCE detector, so it lives in a module-level `duplicate_adjacent(texts)` rather than
  in `check()` (whose `(src_en, text_ru, cfg)` signature cannot express it); `verify.py` appends
  the flag and writes `completeness_duplicate_of`. Catches an **ASR** defect, not a translation
  one — whisper's repetition loop emits a line twice and the dub says it twice.
Integrated as a separate segs loop in `verify.run()` (after the whisper model frees, before
`report.save`); rollup `rep["completeness"]`. 21 tests, no regression.

**Real-data validation (x7DfiXqSEdM, 854 sentence-checks across Gemma + Sonnet): 31 fires, 0 true
losses, all FP.** But the two precise signals stayed SILENT on the clean data — num_loss Sonnet
0/427, length_short 0/854 — which is exactly the intended "silent until a real loss happens"
insurance (they fire on a genuinely dropped number/clause; this content simply has none).
entity_loss is ~100% FP (Russified personal names — Jimmy Carter, Bruce Lee — which the naming rule
PERMITS; translated titles; Capitalized common words) with ~0 recall on EN→RU: structurally noisy,
no cheap person-vs-brand discriminator exists. neg_loss is 100% FP here too (lexical negation:
`not good`→`плохо`) but guards the meaning-inverting class at 0.5%.

**User decision: KEEP ALL FOUR as-is** (triage-only, non-blocking). entity's noise (~3% of
sentences) is accepted for the chance of catching a genuinely dropped brand. This is the FIRST
data source for the run-report / observability item (PLAN 1). The heavy semantic check stays
rejected.

### Addendum (same day, PLAN item 0c) — 5th detector + a negation-regex fix

**`dup_adjacent` is ACTIONABLE, not advisory — justified by PRECISION, not hit rate.** PLAN
argued actionable from "found real defects in 2 of 12 videos"; that figure belongs to the
session's ad-hoc audit, not to this rule. Measured over all 13 workdirs (1101 sentences, 1028
eligible pairs): **exactly 1 fire, a true positive** (`ytEN_iAk09c` 7/8 — byte-identical lines,
the second spanning 0.32 s), i.e. 1 of 13 videos, precision 1.0. Unlike `entity_loss`, whose
dominant FP the docstring calls IRREDUCIBLE, this one's FPs are *decidable* — a human reading both
members can always tell an echo from two distinct sentences. That difference, not frequency, is
what splits the two across `_ADVISORY_COMPLETENESS` (deliberately left untouched: any name absent
from it is actionable by set difference).

**Correction to a first draft of this entry**, which called the FP mode "deliberate verbatim
repetition, rare and instantly recognised". That is the *rarest* mode, not the dominant one. At
0.80 a pair may differ in ~12% of its characters, so the reachable FP is single-token substitution
across a shared frame: enumerations (0.89), before/after and free/paid contrasts (0.92-0.93),
CPU/GPU swaps (0.98). Worst shape — a polarity flip in an identical frame, "You should use this…"
/ "You should not use this…" = 0.96 — is emphatically NOT instantly recognised, and a triager who
"resolves" it by deleting one member inverts the meaning. Measured zero times in this batch's 1028
pairs, so it is genre exposure (explainer prose) rather than an observed defect; a conversational
or instructional corpus would fire far more. The docstring now names this as the dominant FP with
the read-both-members warning, and a test pins the firing boundary so the near-miss control test
is not misread as "parallelism is safe". Actionable status stands — decidable-on-inspection is
still the right bar — but it rests on a correct account of what the flag will show a human.

**Second signal added the same day: CONTAINMENT, because ratio alone was worth a third of what
PLAN assumed.** PLAN justified the actionable status with "found real defects in 2 of 12 videos",
but that figure belonged to an ad-hoc script doing PARTIAL substring matching, while the method
PLAN actually recorded was `ratio > 0.80`. The formula in PLAN was a lossy transcription of what
had worked — and the ratio rule finds **1** of this corpus's 3 repetition defects, not 2. Worth
recording as a process failure, not just a metric one: the finding survived into PLAN, the method
that produced it did not.
Containment (`longest common substring / len(shorter)`) targets the RESTART shape, where whisper
re-speaks part of the previous line and continues — the shared span is large but the new tail
drags the symmetric ratio down. Measured over all 13 workdirs / 1028 eligible pairs: **3 fires,
all true positives** (ytEN_iAk09c 7/8 containment 1.0000; x7DfiXqSEdM 298/299 0.9677;
2YCaBqP8muw 16/17 0.9167), loudest benign pair 0.7188 — a 0.20-wide empty band. `_DUP_RATIO_MIN`
is kept rather than replaced: it is the better-grounded of the two, and the signals are OR-ed.
**0.85 is labelled a HYPOTHESIS in the code, not a measured constant** — it rests on 3 positives,
and the surrounding comments deliberately do NOT read like `_DUP_RATIO_MIN`'s, which earns the
stronger claim. Re-validate as the corpus grows.
Still missed by construction: NON-adjacent loops (the scan is pairwise; a duration/wps check is
the orthogonal answer — INBOX) and semantic garbles that repeat no span (the four-Ds recap,
containment 0.44).

## 2026-07-19 — Repairing a whisper hallucination: isolated-window re-ASR, not a full re-run

**Full-file re-transcription is not a repair method for this class.** All four known-defective
videos were re-run with `--force --only transcribe` on the theory (PLAN 0a) that whisper's
non-determinism would shake the defect loose. It fixed **1 of 4**. The other three reproduced the
same defect on the same audio, one came back worse (a new 0.28 s collapsed segment), and a fourth
gained a fresh garble containing CJK characters. These are not decoder noise — they are stable
responses to specific passages, and re-rolling the dice costs a full ASR pass to mostly lose.

**What works: re-transcribe the WINDOW, not the file.** The repetition loop is fed by
`condition_on_previous_text`; a clipped 8-18 s window has no prior context to loop on. Applied to
all 7 defect regions across 6 videos, every window returned a clean reading, **identical under
both `condition_on_previous_text=True` and `False`** — the stability check that says the reading
is the audio and not another sampling artifact. Cost is ~1 minute per window against ~50 s for a
full file, and it repairs instead of re-rolling.

**Repair discipline — delete, do not invent.** Every replacement text is the isolated window's
OWN output; the defect is always that whisper emitted extra sentences where the window shows one,
so each repair MERGES a run into the single verified sentence and renumbers to keep ids
contiguous (the invariant `duplicate_adjacent` and `implausible_rate` both rely on). Exactly one
correction overrode ASR rather than deleting: `Anthropics Cloud Models` → `Anthropic's Claude
models`, flagged in the repair script, on the grounds that this is Anthropic's own course about
Claude and a wrong brand name would reach both the dub and `pronounce`.

**Result: 7 repairs, and both ASR detectors go silent on the batch.** `rate_implausible` max fell
from 246 to 39.36 ch/s (under the 40 threshold — zero fires); `dup_adjacent` fires zero times
across the 12 queue videos. Originals preserved at `work/<id>/_pre-repair-sentences.json`;
`words.json` is deliberately NOT rewritten — it is the raw record of what the ASR actually did,
and `asr.floor_ratio` should keep reporting that these files had a collapse.

**A THIRD defect class, found by a translator sub-agent reading the text — not by any detector.**
`W4Ua6XFfX9w` ids 19/20 read "Description goes beyond distinction." / "just writing prompts."
The isolated window says it is one sentence: "Description goes beyond just writing prompts." A
hallucinated word (`distinction` for `just`) split one sentence in two. **Both detectors are blind
to this shape by construction**: each half sits at a plausible ~26 ch/s (well under the 40 bound)
and the two are not similar to each other, so neither `rate_implausible` nor `dup_adjacent` can
see it. Only reading the text finds it.
**This settles the "Tier 2" question the 0d audit raised.** The translate seam is not a nice-to-
have extra detector — it is the ONLY thing that catches semantic garbles carrying no timing
anomaly and no repeated span. Both classes that survived every deterministic detector in this
batch (this one, and the `RyvXxApfHkk` self-referential nonsense) were caught by an LLM reading
the source, and in the same pass the agents also flagged `CLAWD`/`anthropics` ASR mis-spellings
nobody had logged. The deterministic detectors remain worth having — they are cheap, they
localise precisely, and they run before any model — but the honest architecture is
deterministic detectors PLUS a reading pass, not one or the other.
**Counter-note against over-trusting it:** the same property makes the translator dangerous.
`RyvXxApfHkk` id11's garbage was silently REPAIRED into plausible Russian by Sonnet on the first
pass (PLAN 0e), hiding it from everything downstream. A reading pass helps only when it is asked
to REPORT anomalies rather than to smooth them over — that is a prompt requirement, not a
property of the model.

**Caveat worth keeping honest:** this is hand-editing ASR output. It is defensible here because
every edit is grounded in a second, cleaner ASR reading of the same audio rather than in judgement
about what was probably said — but it is a semi-automatic operator action, not something the
pipeline does for itself. Automating it (detect → re-ASR the window → merge) is the obvious next
step and is NOT built.

## 2026-07-19 — `dup_adjacent` + `rate_implausible` (continued)

**Third signal, and the best one in the file: `rate_implausible` (signal D).** A source sentence
whose chars/second exceeds `_RATE_MAX_CPS = 40` cannot have been spoken in its own span — the
signature of a whisper alignment collapse. Unlike every other threshold here, this one is sited on
a PHYSICAL bound rather than corpus separation: human speech tops out near 25-30 ch/s, and the
corpus agrees (1100 sentences, median 16.75, p95 23.97, p99 34.26, fastest benign 39.4). The
defects sit at 70-246 ch/s — an order of magnitude clear.
**7 fires / 1100 sentences, 7 true positives, 0 false.** Highest precision of anything in this
module, and it is the only detector that reads TIMING instead of text.

**What it found that nothing else could.** Two videos that every text-based signal reported
`[clean]` carry real collapsed segments: `DmgujoZ1mmk#32` (93 chars in 0.88 s) and
`W5cga7xipRI#23` (66 chars in 0.94 s). Batch triage went 2 → 4 videos, and the two additions are
real. It also catches garble that repeats NOTHING (`RyvXxApfHkk#11`, "The LLM is used to analyze
and categorize data, like the LLM, or LLM." in 0.28 s) — invisible to every similarity metric —
and, structurally, repetition loops that are NON-ADJACENT, which `dup_adjacent` cannot see by
construction. The two detectors are complementary; neither subsumes the other, and the tests pin
that claim.

**The strategic lesson, worth more than the detector.** Three text-similarity detectors were built
before anyone measured duration, and duration beat all of them on precision, recall, and grounding
— with less code. `_dehallucinate` in `transcribe.py` had been using near-zero duration as an
artifact signal at the WORD level since the beginning; nobody lifted it to the sentence level.
When the next detector is proposed, ask what physical invariant the defect violates before
reaching for a text comparison.

**Threshold 0.80 is a module constant, NOT a Config knob.** Every threshold in 0.70..0.95 yields
the identical single fire; the true positive (1.0000) sits in a 0.30-wide empty band above the
loudest benign pair (0.6977). A knob would advertise a tuning problem that does not exist. The
25-char guard is INERT on this batch (identical fire set at guard 0..40) — kept as a structural
guard for conversational corpora, explicitly not presented as validated.

**KNOWN MISS, documented on purpose:** this catches the verbatim-ECHO class only. Whisper
RESTARTS (a truncated line re-spoken differently) score 0.35–0.70 — `x7DfiXqSEdM` 298/299 is
0.6977, sitting between two benign pairs at 0.6667 — so no usable threshold separates them. The
`W4Ua6XFfX9w` four-Ds garble (0.5882) is a duplicated HEAD TOKEN across an enumeration, a
different defect. A clean `dup_adjacent` does not mean "no repetition defects here".

**Deliberate PLAN deviation, named rather than hidden:** PLAN says the check "must run on
sentences.json". It reads `src_en` from the already-in-memory translation.json instead. Same
bytes — both translate routes copy `src_en` verbatim (`translate.py:252`, `build_translation.py:87`)
and `translate.py:241` uses that equality as its resume key, so verbatimness is an enforced
invariant, not an assumption. Buys zero new I/O and zero new failure modes (missing/torn
sentences.json, id desync).

**`_RU_NEG_RE`: `без(?![а-я])` → `бе[зс](?!опасн|платн|условн|обидн|конечн|ед)[а-я]*`.** The real
bug was ASYMMETRY, broader than PLAN's framing ("scans for без with a з"): не/ни matched as
prefixes while без matched only as a standalone word, hiding **voiced** bound prefixes too. без/бес
is ONE marker split by voicing assimilation.

**A first cut widened it to a bare `бе[зс][а-я]*` and that was wrong — recorded because the error
is instructive, not because the numbers were bad.** On the corpus it looked free (neg_loss 3 → 2,
removing exactly the target FP `W4Ua6XFfX9w#32`, zero additions). Its justification was that
"non-negative бе[зс]- lexis (беседа, бешеный) has ZERO occurrences", but those two words are
absent from the corpus while the бе[зс]- lexis that IS present is безопасн-×18. The predicate was
ETYMOLOGICAL (privative origin) where the detector needs SEMANTIC (polarity): безопасный means
*safe*, so counting it as surviving negation makes "it is not safe" → "это безопасно" — a textbook
inversion — read as a kept negation and pass silently. Eight such constructions were caught by the
old regex and missed by the bare widening. A test was even added pinning one ("I don't like this
conversation." → "Мне нравится эта беседа.", negation genuinely dropped) as an *accepted miss*,
telling future maintainers that an inversion miss is fine for the one detector that exists to
catch inversions.

**The general lesson, which outlives this regex:** the module-wide "over-matching only ever causes
a MISS, the safe direction" rule does NOT apply to `neg_loss`. `completeness.py` anchors
prefer-miss to "the weak length signal most of all", and DECISIONS 2026-07-19 carves neg_loss out
by name — *"an inverted negation is the most dangerous silent loss there is, and one false positive
per batch is a fair price for never missing one."* For this detector a MISS is the failure mode the
detector exists to prevent. Citing the module docstring to justify lowering its sensitivity was
circular: the regex, the docstring sentence licensing it, and the pinning test all landed together.

**Shipped form subtracts positive-polarity stems** (`_NEG_POSITIVE_STEMS`). Re-measured over the
same 1101 sentences: **identical to the bare widening — 2 fires, the same two**, target FP still
removed, **zero new false positives**. So the correction is free on observed data and closes a
LATENT hole; the accepted cost is a flagged correct translation ("not dangerous" → "безопасно"),
which is the trade DECISIONS already priced. Both directions are now pinned by tests, including
one asserting the inversion IS caught.

**Rejected in the same pass:** adding `"i don't know"` to `_NEG_IDIOMS` (it would convert one FP
into a systemic miss over real negation — `_NEG_IDIOMS` is excised unconditionally before the
scan); an enumeration-head detector and a timing/chars-per-second detector (both real, both with
their own FP surface and tests — INBOX, not this commit).

**Artifacts do not self-heal:** `work/W4Ua6XFfX9w/report.json` keeps its stale neg_loss and
`ytEN_iAk09c` gains its dup flag only after a re-run of verify. No resynthesis needed — the
completeness loop never touches audio.

## 2026-07-19 — Run report (observability): two non-obvious choices in run.json

Built the per-run rollup (`overdub/runreport.py` → `work/<id>/run.json`, PLAN item 1). Two calls
worth recording; the rest is mechanical aggregation of already-persisted artifacts.

**RTF denominator source priority: info_json > ffprobe > sentences.** RTF (wall / video duration)
needs a duration, and the pipeline never stored one as a first-class field. Priority: (1)
yt-dlp's `source.info.json` "duration" — authoritative, already on disk, zero cost; (2) a
best-effort `ffprobe` on the source media — recovers the metadata-backfill path (info.json holds
only a title) at the cost of one guarded subprocess, the ONLY external call runreport is allowed;
(3) the last `sentences.json` "end" — always present once transcribe ran, but it UNDERSHOOTS
(trailing silence/music after the final sentence isn't counted), so it slightly inflates RTF —
acceptable as a last resort, and `video_sec_source` is stamped in run.json so the number is never
read blind. No duration at all → RTF null, never a fabricated denominator.

**Speed distribution metric = `combined_factor`, not raw `tts_speed`.** The distribution
(median/p95/max, count ≥ 1.8) is over `combined_factor` = native F5 compression × atempo top-up,
the REAL compression a listener hears — matching assemble's own `n_over_1_8_combined` triage bar
(DECISIONS 2026-07-17: native ≥~1.3 drops words, atempo tops up the rest; the combined figure is
the one that means "candidate broken"). Raw `tts_speed` alone misses the atempo half and
`speed_factor` (atempo demand) alone misses the native half — neither is the number the 1.8 bar
was calibrated against. Aggregated over UNIT leaders (report records fan out per sentence sharing
a `group_id`; dedup first-seen), so the count is units, not member sentences.
