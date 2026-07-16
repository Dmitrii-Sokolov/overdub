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

## 2026-07-16 — Local-only constraint amended: optional cloud-translate mode approved

**User decision:** an explicitly opt-in cloud translation mode (Anthropic API, Sonnet-class) is
a permitted exception to the founding local-only constraint. Rationale: translate is 80% of
wall-clock (RTF 0.60, the only real bottleneck) and the likeliest quality ceiling; a cloud pass
would give the largest single speed win while keeping quality. Boundaries: OFF by default, a
deliberate flag (no silent fallback to cloud), local Qwen path remains the default and must keep
working; STT/TTS stay local unconditionally. CLAUDE.md hard-constraints section amended to match.
