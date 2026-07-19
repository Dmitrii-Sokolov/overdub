# Session 2026-07-19 — Sonnet route-B infra + 4-way translate bake-off

## TL;DR
Two threads closed:
1. **Route B (Sonnet semi-auto translate) turned into shippable infrastructure** — a skill
   (`overdub-sonnet-batch`) that fixes the transcribe→sub-agent-draft→resume order, plus
   `scripts/build_translation.py` which owns the fragile part of the translate contract so it
   never rides on the LLM. Committed.
2. **4-way translator bake-off on x7DfiXqSEdM (427 sentences) → two ideas falsified.** User
   read-through verdict: the Gemma completeness prompt-bundle is not worth it (parity, clumsier,
   ×10 tempo cost), and Sonnet agent-isolation buys no quality. Both dropped. Sonnet remains the
   clear winner and the primary route.

## What happened, in order
- Started from "how do I run a batch with Sonnet as translator?" → read README route B, verified it
  against the code (`--only`, `TranslateStage.done()`, the translate contract in `translate.py`).
- Built the route-B infrastructure: `overdub-sonnet-batch` skill + `build_translation.py` helper
  (sub-agent writes only `{id,text_ru}`; helper fills src_en/timings, `text_tts` via
  `normalize_for_tts`, `_is_bad` gate, id-contiguity). Smoke-tested the helper (happy path, echo
  flag, missing-id fail).
- Discussed sub-agent context isolation → built a custom isolated `overdub-translator` agent type
  (Read/Write only) to test "narrow agent ⇒ cleaner translation".
- Ran a 4-way bake-off on a fresh transcribe of x7DfiXqSEdM (427 sentences, ~39 min vlog):
  gemma-base, gemma-impr (the 4-change bundle from `.claude/gemma-translate-ab-brief.md`, run on a
  fresh workdir off a throwaway branch), sonnet-v1 (general-purpose), sonnet-iso (isolated).
- Produced objective metrics + three word-diff HTML tables (base↔impr, v1↔iso, v1↔gemma-base).
- **User verdict:** Gemma bundle = text parity but clumsier sentences → DROP; Sonnet iso ≈ v1
  (v1 slightly more natural) → DROP; Sonnet ≫ Gemma → confirmed primary.
- Cleanup: restored `translate.py`, deleted branch `gemma-completeness-ab`, deleted the
  `overdub-translator` agent, wrote DECISIONS + CHANGELOG, committed skill+helper (feat) and docs.

## State of the tree
- **Commits (main):** `b5b29fe` feat (skill + build_translation.py), `12afa68` docs (DECISIONS +
  CHANGELOG). `translate.py` unchanged — the bundle was discarded, not merged.
- **Deleted:** branch `gemma-completeness-ab`, `.claude/agents/overdub-translator.md`.
- **Kept in tree:** `.claude/skills/overdub-sonnet-batch/{SKILL.md,references/translate-contract.md}`,
  `scripts/build_translation.py`.
- **Artifacts on disk (gitignored):** `work/x7DfiXqSEdM/` holds `sentences.json`,
  `translation.gemma.json` (baseline), `translation.json` (= baseline copy), the three
  `translation_compare*.html` tables. Sonnet drafts + gemma-impr output live in the session scratchpad.

## Open threads (→ PLAN)
1. **Translation completeness check** (still PLAN roadmap 1, the top verify blind spot). This session
   FALSIFIED the prompt-bundle as the fix — the completeness reframe inflated length without recovering
   meaning. The lever remains verify-side (measure completeness), not a Gemma prompt change.
2. **Multi-content-type A/B** — this bake-off was n=1 lifestyle vlog. Sonnet's edge is wider on
   science-pop (prior read-through). If a Gemma-quality decision ever matters again, use 2–3 content types.

## Loose ends
- `.claude/gemma-translate-ab-brief.md` — the user's handoff brief, left **untracked/uncommitted**.
  Decide: delete (task done) or keep as a reference doc.
- Session scratchpad holds the throwaway tooling (`compare.py`, `gen_html.py`, `gen_pair.py`,
  `run_translate.py`) and the Sonnet drafts — not in the repo, discard at will.
- The `overdub-sonnet-batch` skill duplicates the translate rules from `SYSTEM` in prose
  (references/translate-contract.md) — documented drift risk; a `python -c "print(SYSTEM)"` inject
  would remove it if the skill is used a lot.
