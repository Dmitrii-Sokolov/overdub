# Session handoff — 2026-07-17: batch+stop, proper nouns, segmentation cluster, whisper-context root fix

Compact conspectus; full detail lives in the four artifacts (DECISIONS: five new 2026-07-17
entries; CHANGELOG: four new entries; PLAN: roadmap now item 0 + item 1; INBOX: triaged).
Supersedes the "Next steps" of `2026-07-17-session-deadair-close.md`. Long day — four features
shipped, all via ultracode workflows (Measure→Design→Implement→Review→Verify→Fix→Smoke).

## What this session shipped (commits, newest last)

- `977a129` feat: **batch queue + stop switch**. `--batch FILE` (one URL/line, `#` comments,
  BOM-safe, dedupe by video id); failed video prints traceback and batch CONTINUES; exit codes
  0/1/2/3 (ok/fail/usage/stop-halt). Stop switch = `work_root/STOP` checked before every stage
  boundary, consumed at honor time, stale-swept at startup. Titled export: hardlink (copy
  fallback) of output.mkv → `output_dir` (new key, default `out/`) as `"<title> [<id>].mkv"`.
- `812318b` docs for the above.
- `8e1b8d3` feat: **proper-noun pronunciation chain** — new `overdub/pronounce.py` (PHRASES →
  WORDS ~50 → plural → case-gated acronyms → letter names → ~74-rule practical-transcription
  scanner replacing the naive per-letter translit; sky→скай, vowel-less output letter-spelled).
  Wired into normalize as pass 0a (phrases) + 1b (PS5→пи-эс пять seam) + rewritten pass 6.
  Audit-only `pronounce_audit.json` (never a resolution input — purity). `tools/renorm_workdir.py`
  A/B tool (re-derive text_tts from stored text_ru, no LLM).
- `921791a` docs for pronounce.
- `75e9543` fix: **renorm tool** writes copied manifest with `complete:false` — a complete
  manifest made synthesize skip over stale wavs (found live in the pronounce A/B).
- `13bec6a` docs: proper nouns CLOSED by ear (pronunciation correct on all 5 target ids).
- `9ca7751` fix: **segmentation cluster** — MIN_PAUSE_SEC=0.20 gate + `_ok_cut` veto (all 3
  branches) + `_CONJ`→`_CUT_BEFORE` (drop ambiguous subordinators) + item E ('.'+seg_end before
  lowercase = boundary). translate prompt: names stay Latin. assemble: display-only cue split.
  Items C (tolerance band) and D (Capital-after-lowercase) REJECTED on corpus evidence.
- `a5be5dc` docs for the cluster.
- **THIS commit** feat+docs: **whisper punctuation context** — the segmentation ROOT fix.

## Ear verdicts (user, binding)

- Proper nouns: pronunciation CORRECT on all 5 target ids → CLOSED.
- Segmentation cluster ear-check surfaced the deeper bug: "period mid-sentence" is FREQUENT
  (181/314 sentences open mid-thought). The cluster fixed the *choice* of cut point but not the
  *need* to cut. User pushed: "is it whisper or Qwen?" — correctly.
- Within-word pause at 23:08 is an F5 prosody artifact (speed=1.0), not the fix's fault.

## The root fix (this commit) — read DECISIONS 2026-07-17 whisper entry for the full trace

- Layered trace of id148 (condition=False): whisper EN text ends `...you have` (no period);
  Qwen RU ends `...у вас есть.` (period). The full stop is QWEN's, the BREAK is
  `_split_overlong`'s, forced by whisper's 60-206 s terminator-free blocks. Qwen is 1:1, only
  inherits the break.
- Single-variable experiment (flipped ONLY `condition_on_previous_text` False→True, re-ran ASR):
  max raw range 206→27 s; 314→427 real sentences; both ear cases whole in one sentence. Proves
  root = whisper punctuation, not Qwen.
- Hallucination risk (why it was off) measured on the MUSIC video: longest repeat run = 3
  ordinary words, zero loops. Safe on both poles (N=2: clean monologue + music).
- Shipped as Config flag `whisper_condition_on_previous` (default True), NOT hardcoded. The
  segmentation cluster is now second-order (splitter rarely fires) but KEPT as the fallback.

## Config state after this session

New keys: `output_dir=Path("out")`, `whisper_condition_on_previous=True`. Unchanged from prior
session: `tts_engine="f5"`, `dub_mix="bed"`, `f5_speed_ceil=1.1`, `similarity_threshold=0.9`,
`similarity_threshold_compressed=0.9`. pronounce.py, MIN_PAUSE_SEC=0.20 and the cue-split
constants (MAX_CUE_SEC=6.0/MAX_CUE_CHARS=84/MIN_CUE_SEC=1.2) are module constants, not config.

## NEXT TASK — PLAN item 0 (do this first)

Ear-check the whisper-context fix: full `--force` pass (~46 min) on a FRESH workdir with the
flag on (now default). Recipe that works (used this session):
1. Seed a fresh workdir with source artifacts only (avoid re-download/re-separate): hardlink
   `source.mkv`, `source.wav`, `source.info.json`, `source_bed.wav` from an existing workdir
   into a new `work-exp/<name>/<vid>/`. (scratch script `seed_segfix.py` did this.)
2. A one-line toml with `work_root = "work-exp/<name>"`, defaults elsewhere.
3. `.venv-asr\Scripts\python.exe -X utf8 -m overdub <url> --config <toml>`.
4. Compare against `work-exp/segfix/x7DfiXqSEdM/output.mkv` (condition=False, the STALE segfix
   run) and `work-exp/f5-control/x7DfiXqSEdM/output.mkv` (pre-cluster). Listen for the
   "period mid-sentence" class on the survival/exploration and Xbox-Live passages.
Note the id shift: with context on there are ~427 sentences vs 314; the ear-case ids move
again — REASON FROM TEXT ("met through Xbox Live", "survival exploration"), not from numbers.

## Landmines / decided positions (don't re-litigate)

- **synthesize.done() never compares text_tts vs translation.json** (INBOX bug). A complete
  manifest skips the stage over stale wavs. `renorm_workdir.py` writes `complete:false` to work
  around it; `--force --only translate` + plain rerun hits the same class. Consider a done()-side
  congruence gate before trusting a resumed synth.
- **Out-of-dict game/company names self-agree through verify UNFLAGGED** (silent-loss class,
  INBOX). Bungie→бунджи etc. The only detector is promoting `pronounce_audit.json` to a
  pre-batch operator gate. Do NOT trust a low verify flag count as "pronunciation is fine".
- Items C/D (tolerance band, run-on recovery) are REJECTED on measured corpus evidence, not
  deferred — don't resurrect without a ≥10-video corpus.
- The corpus is 3 UNIQUE videos (x7DfiXqSEdM appears in `work/` and `work-exp/f5-control/`
  byte-identical). Every precision figure this session has that denominator.
- Priority lesson (DECISIONS): a one-line flag beat the 31-agent segmentation cluster. Measure
  surfaced the 206 s blocks; they were filed to backlog instead of tested first. Test the root
  before polishing the symptom.

## Operational map

- Venvs: `.venv-asr` (pipeline) / `.venv-f5tts` (F5 worker) / `.venv-demucs` (separate). Never
  merge. Run: `.venv-asr\Scripts\python.exe -X utf8 -m overdub <url> --config <toml>`.
- Corpus workdirs are READ-ONLY reference. `work/*` = Silero baselines. `work-exp/f5-control`,
  `work-exp/bed-music`, `work-exp/segfix` = F5 runs; segfix is condition=False and now STALE.
- Roadmap after the ear-check: item 1 = babble duration heuristic (~1 d, activates at batch
  scale — first overnight batch supplies calibration data). Then backlog.
