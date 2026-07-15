# DECISIONS

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
