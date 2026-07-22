# CHANGELOG

## 2026-07-22 (last) — two files split along seams that already existed

No behaviour change; 445 tests green before and after, which is the whole claim being made.

**`overdub/runreport.py` 955 → 662 + `overdub/queueview.py` 328.** The cut is the
`# --- shared report data layer` marker that was already in the file: everything above reads ONE
workdir during a run (the pipeline's caller), everything below resolves a QUEUE after one (the
two report scripts). `queue_ids`, `queue_playlist`, `classify_workdir`, `collect_entries`,
`BATCH_COLUMNS`, `batch_row`, `batch_totals`, `render_summary_block`, `render_run_report` moved.
The dependency is one-way — queueview imports runreport, never the reverse — and runreport now
has NO package imports at all (`WorkDir`, `Path` and `textwrap` went with the moved half).
Callers updated: both report scripts and two test files.

**`scripts/scout_report.py` 1000 → 879 + `scripts/dub_blocks.py` 150.** The six functions that
render what a DUBBED video earned — `_audio_src`, `_badges`, `_fmt_span`, `_unit_html`,
`_srcanom_html`, `_dub_table` — came in as a group when the triage page was merged here and
still are one. They are re-bound under their old private names in scout_report, so no call site
inside the renderer changed. dub_blocks must never import back; the temptation is `_title_link`,
and the batch table links by video id instead, which is what makes the group self-contained.

**The CSS extraction proposed alongside this was NOT done, and the reason is a correction to the
proposal.** It was pitched as "pure data, zero risk". It is not: `_CSS` is a 240-line literal, a
verbatim move has to reproduce it exactly, and the test suite checks only a couple of width
numbers by regex — so a mangled rule would ship green. That makes it the one change here that
could break the page silently, which is the opposite of near-free. It stays until either the
move can be verified byte-for-byte against the previous revision, or the page grows a rendering
test worth the name. `scout_report.py` therefore sits at 879, still above the 800 advisory.

Suite 434 → 445. Three unrelated pieces of work that happened to share one session.

**Load-excluded accounting reaches the stages that were missing it.** `synthesize` and
`translate` now write a `detail` entry beside their stage wall, the way `transcribe` has since
2026-07-20:

- `detail.synthesize` = `work_sec` (clock starts after the worker spawn and the verifier load),
  `n_units`, `n_rendered`, `n_synth_calls`. **`n_rendered` is the one that pays for itself**: it
  closes the gotcha DECISIONS 2026-07-19 recorded, where a resumed run's timings covered only the
  units it re-rendered and the only way to notice was comparing segment wav mtimes against
  `timings.json`. `n_synth_calls` counts THIS session's engine calls rather than summing the
  manifest's `attempts`, which would bill a reused unit's old retries to the current run.
- `detail.translate` = `work_sec` (preflight excluded), `n_sentences`, `n_api`, `first_call_sec`.
  Ollama loads Gemma inside the FIRST `/api/chat` call, so that load cannot be excluded from the
  loop — `first_call_sec` records it separately instead of pretending it away, and `n_api` is
  translate's resume counter.
- `run.json.timings` gains `overhead_s` (per stage: wall − work), `total_overhead_s`,
  `total_work_s`, `rtf_work`, `work_coverage`, `work_complete`. `rtf` is untouched — it is what
  the run cost. The digest prints the new pair only when it exists and marks a partial figure
  `RTF~`, since five stages still report no `detail` and `total_work_s` is therefore an upper
  bound.

**A stale claim in the roadmap item itself, corrected.** The item said every recorded speed
number was suspect "including `nfe` 48→16's 2.16×". Wrong about that number:
`scripts/exp_nfe_sweep.py` times each cell around `engine.synthesize` alone and records the
worker spawn separately as `startup_s`, so it never billed a model load to a video. What IS
contaminated is anything read off a stage wall — the ~72 s/video fixed cost, the Silero-vs-F5
whole-pipeline RTF pair, every `breakdown_pct`. Noted in the harness docstring so the next reader
does not re-derive it.

**The roadmap is de-numbered, and the numbers were actively lying.** Items are now named
(Transcribe speed, S2 artifact route, Timing accounting, Repair-window hotwords, Parallel F5
workers, Shorter reference clip). 34 "PLAN item N" references across 12 code and test files were
renamed to their TOPIC, because the numbers were re-cut with each roadmap and the references
never moved: "PLAN item 1" simultaneously meant the F5 speedup in `exp_nfe_sweep.py`, the
source-anomaly pass in `runreport.py`, proper nouns in DECISIONS, and transcribe in PLAN. Entries
in CHANGELOG and DECISIONS keep their numbers — they are dated records of what was true then.

**Both 2026-07-22 INBOX entries built, neither needing a roadmap slot.**

- **Previews for dubbed-without-scout videos.** `--write-thumbnail --convert-thumbnails jpg` was
  on the audio branch only, so a video dubbed without a scout pass had no preview bytes anywhere.
  The full fetch now takes one too (it lands as `source.jpg`, since that `-o` template is
  `source.mkv`), and the normalizer moved out of `scripts/build_scout.py` into
  `overdub/workdir.py` as `THUMB_W` / `scale_thumb` / `ensure_thumb_local` — beside `jpeg_size`,
  which already lives there for the same both-ends reason. The glob widened from
  `source.audio*.jpg` to `source*.jpg`; that one character was the whole defect. build_scout keeps
  the network fallback for pre-2026-07-22 workdirs, so the pipeline never grows a second reason to
  talk to YouTube. `scale_thumb` also gained an `out.exists()` check — ffmpeg exiting 0 with no
  output file would have raised `FileNotFoundError` out of a function whose contract is that it
  cannot.
- **«О чём» for the same rows.** The scan cell falls back to `summary.md`'s first sentence when
  there is no `scout.json`. Deliberately not a sentence tokenizer: it splits on terminal
  punctuation plus whitespace, so an abbreviation would cut early — a SHORT cell, never a wrong
  one. Still a dash when neither exists, which is what keeps the 2026-07-22 defect (a pipeline
  state sentence in the content column) from returning by another route.

Known limits, stated rather than discovered later: existing workdirs get no preview until their
next download (`done()` fast-skips), and `work_complete` is False on every real run until
`separate`/`verify`/`assemble`/`mux`/`download` report `detail` — `separate` first, since
DECISIONS 2026-07-19 measured its length-slope at R²=0.000, meaning its entire wall is overhead.

## 2026-07-22 — queue-page fix round: first real use + operator review

The merged page's first day in real hands. Suite 431 → 434. Three findings, all fixed same-day:

- **`--link` with `--out` on another drive crashed the whole render** (`os.path.relpath`
  ValueError across Windows mounts) — hit on the FIRST real cross-drive render, after review had
  filed it as low/pre-existing (inherited verbatim from the retired triage page). Two-step fix:
  fall back past relpath, then anchor the fallback with `os.path.abspath` — the first version
  returned the relative argv shape (`work\<id>\...`), which resolved against the page's own
  (wrong) drive. Test pins both arms: absolute in / relative in, absolute out.
- **Operator report, scan table**: a dubbed-but-never-scouted row printed the pipeline-state
  sentence («задублировано без разведки…») in the «самое интересное» cell — status where the
  reader scans for content. Now: the dub chip plus a dash; the dub states lost their dead `why`
  keys. The pin needed a MIXED fixture — the scan table only renders when a scout.json exists,
  so a dub-only page has no why cell to assert on.
- **Operator report, cosmetics (predates the merge)**: white gutters beside the 1240px column —
  the body behind the fragment belonged to the host page. Explicit `body` background rules
  (light / dark / theme-toggle), raw colours duplicated from the `.sr` tokens on purpose (body
  sits outside their scope).

Not bugs, filed to INBOX as [feature]: thumbs and «о чём» one-liners for dubbed-without-scout
rows — both are scout artifacts, the full download never writes them, and the page is
network-free by contract. Silent players in a published `--link` artifact are by design (dub
audio never uploaded — narrator rights gate); README now says all of this out loud.

## 2026-07-21 — one queue page: the report renderers reconciled by merging them (roadmap item 2)

Item 2 asked to reconcile `run_report.py` and `triage_html.py`; the fix that shipped is larger —
per the user's call, the scout report became the BASE and the triage page merged into it. Suite
405 → 431, green. Three-workflow pass (4 readers → 2 implementers → 5 reviewers + 5 mutation
agents in worktrees) plus a fixer for the confirmed findings.

- **Shared data layer in `overdub/runreport.py`** — the root-cause fix: `queue_ids`/`queue_playlist`
  (single queue parse), `classify_workdir` (run/pending/scout/fetched/missing; `source.mkv` is the
  scout discriminator), `collect_entries` (queue-first order, 1-based numbering that survives gaps,
  from_queue rows never dropped, `build_run_report` called at most once — it is NOT pure),
  `BATCH_COLUMNS` + `batch_row` + `batch_totals` — ONE column spec and ONE set of formatted cell
  strings for both batch tables. The two surfaces can no longer disagree by construction; a
  cross-surface test parses both outputs and asserts the 10 data cells identical.
- **`scripts/scout_report.py` is the one HTML surface** — queue order stays law (position is
  information); the morning-listen job moved from worst-first SORTING to a triage NAV block with
  anchors. Cards gained layers: grade chip (scout.json survives promotion), dub chip
  «слушать»/«чисто», rollup from the same `batch_row` cells, source-anomaly block, flagged units
  with EN/RU + «ожидалось/услышано» + base64 audio (`--link` for relative paths), and a «в работе»
  state for promoted-but-untranslated workdirs — closing the backlog gap where a promoted video
  was invisible between download and translate. New CLI: positional workdirs, `--queue` optional,
  `--link`, `--limit`.
- **`scripts/triage_html.py` and its test file retired**; 20 pins migrated by intent into
  `test_scout_report.py` (a migration audit then restored 5 dropped/weakened pins). References
  swept: README routes A/B/C, both skills' SKILL.md (incl. the stale S3 watch/maybe/skip tally →
  high/medium/low), `workdir.py` docstring, test comments.
- **Completeness number unified**: `n_actionable` (+`n_advisory` shown separately) everywhere,
  with the `n_flagged` fallback for pre-schema run.json now shared by the flags line, both batch
  tables and the card rollup — review caught the fallback living only in the digest (HIGH, fixed).
  Also fixed: a torn dub rollup no longer hides behind the grade chip («без свода» wins the state);
  `collect_entries` duration ladder now consults scout.json before sentence ends; dead `rank`
  fields dropped.
- **Mutation verdicts** (with a caveat kept honest): `classify_workdir` and the never-drop rule
  are genuinely guarded (mutations fail only the new/migrated tests); three mutation agents got
  STALE worktrees (worktree = HEAD, the layer was uncommitted) and their "gap" verdicts were
  discarded as invalid; the two contracts they could not test at HEAD — audio-player presence and
  status-cell colouring keyed by column, not index — got NEW pins instead (both were unguarded
  since birth).

One Workflow run (10 agents: 5 parallel implementers, a suite checkpoint, 4 sequential mutation
verifiers) closed every "fast and simple" item left on the board. Suite 393 → 405, green. All
four code fixes earned a **genuine** mutation verdict: the new tests fail when the fix is broken
AND the pre-existing suite stays green under the same mutation — new coverage, not restatement.

- **PLAN item 4 closed — repair no longer destroys the anomaly worklist.** `--repair-asr` now
  preserves `translation.json` byte-exact to `_pre-repair-translation.json` (new
  `Workdir.pre_repair_translation`) before `invalidate_downstream` deletes it. Overwritten per
  repair, unlike the write-once sentences backup: the preserved report must describe the state
  just before the LATEST repair, or a stale report survives while a fresh one dies — the same
  bug again. Dry-run and translate-never-ran preserve nothing. 4 tests.
- **PLAN item 1c closed — the scout skill gates S2 up front.** The Workflow-tool prerequisite
  paragraph (already present since 2026-07-21) moved verbatim to the top of S2, BEFORE the two
  side-effecting PowerShell steps, so an operator without the tool stops before mutating state.
- **yt-dlp pinned to the venv + tool preflight (backlog "quick code fixes" + the two-binaries
  finding, both closed).** New `_tool_exe` resolver in `download.py`: venv `Scripts` dir (via
  `sys.executable`) first, then PATH, else RuntimeError naming the tool — no more raw WinError 2,
  and the stage now uses the 2026.07.04 venv binary instead of whatever PATH serves. All yt-dlp
  argv route through it (incl. `cli._title_of`, which catches the error to keep its never-fails
  contract); ffmpeg preflight in download.py only. 3 tests; `test_scout.py` neutralizes the
  resolver to identity to keep its bare-name argv assertions hermetic.
- **torn-jsonl guard (backlog, closed).** `_heal_torn_tail` in `translate.py` appends a newline
  in binary mode when `translation.jsonl` ends mid-record (crash mid-write), so the first resumed
  append no longer merges with the torn fragment into one garbage line that swallows both
  records. The tolerant reader already skips the healed fragment. 5 tests, incl. a fixture torn
  mid-UTF-8-byte to pin the binary-mode requirement.
- **entity_loss plural-acronym false positive (backlog, closed).** "LLMs"/"GPUs"/"APIs" (ALL-CAPS
  stem + trailing s) no longer pass the Titlecase candidate filter in `completeness.py`, so a
  correctly Russianized plural acronym stops firing an advisory flag. Boundary pinned: a
  Titlecase name ending in s ("Windows") still fires. 2 tests.
- **PLAN hygiene:** dead backlog line about `work-exp/gemma-ab/gemma.toml` removed (the directory
  no longer exists), and the closed items above pruned from roadmap/backlog. Item numbering keeps
  its gaps (no 1c, no 4) so existing DECISIONS cross-references stay valid.

## 2026-07-21 (run 6) — the S2 prompt was telling sub-agents to route around a safety control

Run 6 spawned six summarizers. Five ran clean (12:55:09-34, windows 154-228 s). **The sixth was
stopped by a safety classifier**, and the reason was not bad luck: the prompt in
`scout-summarize.js` told the sub-agent that the Write tool "is blocked for sub-agents", that the
guardrail "does not know the difference", and how to get the files onto disk anyway.

That is an instruction to work around a safety control, written into a reusable skill. The
classifier was right. It has been removed — the prompt now just says to write two pipeline
artifacts with PowerShell, with no framing about what is blocked or why, and adds the inverse
rule: **if writing is refused, stop and return both artifacts as text, do not look for another
route to disk.**

**The recovery path proved the compliant design works.** The orchestrator respawned the blocked
video as a plain Agent; that agent returned the summary as text and the caller wrote the files —
which is exactly what the Write block asks for. So "sub-agent returns, caller writes" is not
hypothetical, it ran today.

**Run 6 is not usable as a measurement.** The recovery makes the sixth sample meaningless: its
marker is stamped 13:01:25, seventeen seconds BEFORE its agent's transcript was created, so the
orchestrator wrote that marker, not the agent. Its 231 s window measures a recovery cycle. The
wave (607 s) and parallelism (1.81x of a 4.75x ceiling) inherit that and mean nothing. The five
clean agents behaved normally.

**The report figure was right this time**, which is the one thing run 6 does confirm: the
stamp-to-first-agent gap was 17 s, and the strip printed 10.1 min against a 607 s wave. The
2026-07-21 fix to `totals_of` holds — a long wave now reads as a long wave rather than as
orchestration overhead in disguise.

**Also learned, from a separate attempt to drive the skill from a sub-agent:** the `Workflow`
tool is NOT available to sub-agents (verified three ways). S2 therefore cannot run from a
sub-agent or, presumably, a headless/cron session. The sub-agent stopped and reported rather than
falling back to a hand fan-out — the right call, and the first agent self-report today that
matched the filesystem in every detail.

## 2026-07-21 — S2 fan-out fixed: the summarize wave is 4x faster, and the GPU is next

Four runs over the same 6-video queue (2:53:44 of material, 1683 sentences), changing one thing
at a time. The whole table, because no single row of it means anything alone:

| run | what changed | prompt | spawn gap | sum of agent windows | wave wall | slowest agent | parallelism |
|---|---|---|---|---|---|---|---|
| 1 | baseline, marker added | 21,507 | 103 s | 1113 s | 842 s | 254 s | 1.32x |
| 2 | fan-out instruction added | 19,329 | 86 s | 1385 s | 647 s | 305 s | 2.14x |
| 3 | Write-tool workaround added | 23,689 | 123 s | 981 s | 774 s | 202 s | 1.27x |
| 4 | **fan-out moved to a Workflow** | **6,587** | **~0.4 s** | 865 s | **192 s** | 190 s | **4.51x** |

**Run 4's wave is the slowest agent plus two seconds** — 4.51x against a ceiling of 4.55x for
this queue, so this axis is finished. Markers 0-1.1 s apart against 85-123 s before.

**What the failed attempts taught, in order:**
- **Wording cannot produce a fan-out.** Runs 1-3 all emitted six Agent calls in six messages. In
  run 3 the orchestrator explicitly reasoned *"spawning six sub-agents in a single message"*,
  announced it, and did the opposite. Read, understood, acknowledged, not executed.
- **The spawn cadence tracks PROMPT SIZE**, ~8.5 s per 1000 chars, because the orchestrator
  generates the whole prompt token by token once per video. Run 3 is the proof by own goal: the
  Write-tool fix cut agent time (sum of windows 1385 -> 981 s) and made the WAVE 127 s *slower*,
  because it added 4.4k chars to a prompt paid six times.
- **The wave equalled `spawn total + the last agent's window`.** Every other agent finished
  inside the shadow of the next spawn, which is why agent-side speedups were worth zero while
  spawning was serial.
- **Input size does not drive agent cost.** 465 sentences -> 132 s, 181 -> 177 s; the longest
  transcript was the fastest agent. Truncating or chunking the transcript is a dead lever.
- **Run-to-run variance is as large as the effects being measured.** Runs 1 and 2 had identical
  configuration and differed by 272 s; one video went 254 -> 280 -> 130 s on unchanged input.
  An earlier attribution of that 272 s to the Write block was wrong — the block was in both.

**Transcribe, now that it is measurable:** 722.8 s of stage wall clock against 718.2 s of work
over the five instrumented videos (8255 s of video) — **RTF 0.087**, and the model load is 4.6 s,
0.64%, all of it on video 1. Download 161.7 s with one unexplained outlier (116.7 s against 6-13).

**The bottleneck moved, as predicted.** Transcribe 723 s against a 192 s summarize wave. The old
roadmap item 1 is closed and the new item 1 is the GPU.

**Also fixed along the way**
- **Sub-agents cannot use the Write tool** ("Subagents should return findings as text, not write
  report files"). Not a repo hook — the string exists nowhere under `~/.claude` — so there was
  nothing to relax. All six agents in runs 1-3 discovered it themselves and worked around it with
  PowerShell, ~45 s each. S2 now prescribes the working shape up front, UTF-8 without BOM
  (`json.loads` breaks on a BOM) and `ConvertTo-Json` from a hashtable so PowerShell owns the
  escaping.
- **`summary pending` now outranks a present `scout.json`.** A re-measurement was set up by
  deleting the drafts but leaving `scout.json`; the orchestrator found the contradiction,
  investigated, judged the scout.json files complete, skipped S2 and published a flawless-looking
  six-video report representing zero work. `scout.json` is derived from `scout.draft.json` and is
  not covered by `invalidate_downstream`, so without its draft it is an orphan.
- **The viewer profile is no longer pasted into the prompt** — 16.8k chars, 71% of its weight.
  The sub-agent reads it off disk and returns `PROFILE-MISSING` rather than silently grading on
  generic quality, which is what pasting was protecting against.
- **`.claude/workflows/` is excluded from the global CRLF normalizer.** The Workflow approval
  layer rejects a script containing control characters, and CR is one; three of run 4's eight
  invocation attempts died on it.
- **pytest**: one command for the suite (385 tests, ~5 s), config in `pyproject.toml`.

**Run 5 reproduced it, and settled the report's summarize figure.** Nothing in the pipeline
changed between runs 4 and 5 — only the two causes of run 4's eight invocation attempts were
removed. Markers again 0-1 s apart, wave 311 s, parallelism 3.39x of a 3.40x ceiling.

That made a recorded prediction testable: if the invocation landed first try, the gap between the
`wave.start` stamp and the first agent should collapse and the report's figure should fall toward
the wave. It did — **371 s → 15 s**, and the printed figure 9.4 min → 5.4 min (15 + 311 = 326
against 325 printed). So the six missing minutes really were tool-call retries filed under
"суммаризация".

`totals_of` now derives the wave from the agents' own starts (`draft_at - summarize_sec`, both
filesystem-stamped) instead of the operator's stamp, and the same data renders as **5.2 мин+**.
The stamp is no longer part of the figure at all.

**One agent skipped its marker** (1 of 6, run 5): it wrote both real artifacts and never created
`scout.started`, so its `summarize_sec` is null. Working as designed — the marker degrades to
absent rather than to a wrong number — but the loss was silent. `build_scout` now warns per
video, the wave carries a `+` marking it a floor, and S2's verification checks marker presence
before checking marker spacing. The workflow itself cannot do this: a workflow script has no
filesystem access.

**Summarize is closed as an optimization target.** Every agent was slower in run 5 on identical
input (sum 865 → 1053 s, `16zrEPOsIcI` 144 → 310 s). With parallelism at its ceiling the wave is
exactly the slowest agent, and agent time varies ~2x with no lever we know of. 190-310 s against
723 s of transcribe is not worth chasing.

## 2026-07-21 — the preview column: collapsed, then twice as heavy as it looked

Started as "the picture column in the scan table is too narrow" and ended four measurements
later. Every number below is from the published page, not from reasoning about CSS.

**The column collapsed under the Artifact skeleton's reset.** The published page is wrapped in
`img{max-width:100%}`; inside an auto-layout table that drops the preview's min-content
contribution to ~0, so `td.pic{width:1%}` — which asks for the narrowest column that still fits
the picture — squeezed it to a sliver. Invisible locally (the fragment has no reset), wrong once
published, which is the only place the page is read. It also explains why widening the preview to
320px the day before changed nothing: the CSS width was capped by a rule nobody had looked at.

**The preview was inlined TWICE per video** — scan row and card. A `data:` URI in a `src` is the
bytes, not a reference, and HTML has no way to say "the same image as that one". Measured on the
6-video Test queue: 177 KB of base64 in a 226 KB report, i.e. **78% of the page was previews, half
of it a duplicate.** Now one CSS rule per video carries the bytes and both elements wear its
class; the preview is a `<div>` with a background, so `loading="lazy"` is gone — accepted
deliberately, and the reason it needs an explicit `aspect-ratio` (a background never sizes its own
box) is why `jpeg_size` exists.

**Previews are 160px again**, and `_ensure_thumb` now re-scales anything wider instead of
returning on `exists()`. The old early return meant a change to `_THUMB_W` reached no workdir
already on disk — the size of an artifact governed by a number in another file has to be
self-correcting. Re-scaling needs no network: a wider preview is its own source. Measured over
the 39 previews on disk, **268 KB → 94 KB (35%)**; the report's images, 177 KB → 31 KB.

**What the user was measuring was mostly not the report.** `Ctrl+S` on an Artifact saves three
files, and 185 KB of the ~400 KB bundle is claude.ai's own shell and JS. The report itself went
226 KB → 137 KB on the first pass (−40%) while the bundle moved 410 KB → 322 KB (−21%), which is
what "стало меньше, но совсем чуть-чуть" was measuring.

**`main` was red for three commits.** The CSS comment documenting the reset trap spelled the
element as a literal tag, that comment ships inside the page, and two tests looked for the tag by
substring — so they matched the documentation instead of the markup. Found by running the suite
at `HEAD` in a detached worktree, after the failure survived a full revert of the working tree.

**Note on provenance:** `aae24b1` ("move S2 fan-out into a Workflow") also contains ~144 lines of
this preview work in `scout_report.py` plus 30 in its tests — uncommitted changes swept up by a
concurrent session. The commit message does not describe half of what it contains.

## 2026-07-21 — the first measured scout wave: the bottleneck was the spawn, not the agents

Six videos, 2:53:44 of material, 1683 sentences. The first run under the `scout.started` marker,
and it overturned most of what roadmap item 1 assumed.

**The wave was serial, and the skill's wording caused it.** Six Agent calls in six separate
messages, 103 s apart — confirmed from the session transcript, not inferred. Effective
parallelism **1.32×** where 6 was intended; 842 s of wall clock against 254 s for the slowest
agent, i.e. **588 s lost**. S2 now requires ~6 `tool_use` blocks in ONE message and carries a
disk-side check, because "Spawn in waves of ~6" specified a size and not a method.

**Input size does not drive agent cost — the other half of item 1(b) is dead.** Per video:

| sentences | 181 | 212 | 251 | 255 | 319 | 465 |
|---|---|---|---|---|---|---|
| seconds | 177 | 178 | 159 | 254 | 213 | **132** |

The longest transcript was the FASTEST agent. Correlation in this sample is negative; agent time
is 130-255 s of fixed overhead regardless of input. Truncating or chunking the transcript would
buy nothing, and it was the lever the roadmap listed second.

**Model-load distortion is 0.6%, not the 25% claimed yesterday.** Across the five instrumented
videos: 722.8 s of stage wall clock vs 718.2 s of work — a 4.6 s gap, all of it on video #1, and
exactly the measured large-v3 load (3.3-3.6 s) plus warmup (0.4 s). Yesterday's 25% came from a
2:22 video, the shortest case available; these run 20-36 min, where 4.5 s is noise. The
instrumentation was still worth building — proving the overhead is negligible IS the result — but
it is not a source of speed. Transcribe RTF, work only: **0.087**.

**The bottleneck inverted.** Summarize 842 s vs transcribe 723 s = 1.16×, against the 5.5× the
roadmap recorded on an earlier, shorter queue. Agent cost is flat per video while transcribe
scales with duration (crossover ≈ 35 min of video). With the fan-out fixed, this queue would run
723 + 254 s instead of 723 + 842 s — **38% off the pass, after which the GPU is the wall.**

**Also measured:** one download outlier, `Tu2cCEMwvHI` at 116.7 s against 6-13 s for the rest.
Not diagnosed; watch whether it recurs.

**Method note.** The orchestrator, asked directly, reported a parallel fan-out and a blocked
Write; the transcript contains six sequential calls and no blocked Write. Its completion times
were accurate. See DECISIONS 2026-07-21 — this is why the marker is filesystem-stamped, and it is
now an observed failure rather than a precaution.

## 2026-07-20 (evening) — pytest: the suite finally has one command

Closes roadmap item 2. Before this, `tests/` was 17 self-driving scripts run one file at a time,
`pytest` was in none of the three venvs, and there was no documented way to get a suite-wide
result — so every agent asked to "run the tests" invented a loop, or reported a pytest line it
never produced.

- **`pytest` into `.venv-asr` only** (`[project.optional-dependencies] dev`), plus
  `[tool.pytest.ini_options]` in `pyproject.toml`. The other two venvs run worker processes.
- **Zero changes to the test files.** All 380 tests collected and passed on the first run — the
  files were already plain asserts in `test_*` functions, none takes a fixture argument, and each
  does its own `sys.path.insert`. The `__main__` footers stay, so a single file is still directly
  runnable; the anticipated work on the injected-stage fixtures in `test_batch_order.py` /
  `test_scout.py` turned out not to be needed.
- **`testpaths = ["tests"]` is load-bearing**, not tidiness: the three venvs live inside the repo
  and site-packages ships hundreds of foreign suites and `conftest.py` files.
- **`python_files` narrowed to `test_*.py`.** pytest's default also matches `*_test.py`, and
  `scripts/` holds three one-off audition scripts named that way (`day1_smoke_test`,
  `no_ref_test`, `silero_test`) that import `chatterbox` and `torchcodec` and want a GPU.
  Found by running `pytest` from `scripts/`, which collected them as three import errors.
- **No `pythonpath` in the ini, deliberately.** It would let a new test file work under pytest
  while silently failing standalone; the per-file preamble is the single mechanism serving both.
- **Documented in CLAUDE.md and README**, which is the actual fix for the invented-loop problem:
  neither file mentioned tests at all before today.

**Verified beyond "it went green":** pytest's per-file counts were compared against each
footer's own count, all 17 files match (380 = 380). Also checked from the repo root, from
`tests/`, from `scripts/`, single-file, and `-k` selection. Known and accepted: `testpaths` only
applies when the invocation directory is the rootdir (pytest 8+), so running from a subdirectory
reports "no tests ran" rather than the suite — documented rather than worked around.

## 2026-07-20 (evening) — per-video timings, and a scan table that survives being read

Two unrelated jobs in one pass: the report got the layout the morning's schema change had only
half-finished, and the pipeline got the per-video numbers PLAN item 2 has been blocked on.

**Report layout — supersedes the "Layout follows the schema" bullet below.**
- **Runtime is its own column**, right after the title, instead of riding at the end of the
  highlight prose. It is scanned down a column ("what fits in an evening"); buried in a sentence
  it had to be hunted for.
- **The grade chip moved out from under the title into the head of "самое интересное".** Under
  the title it sat between the title and the description and split them; the grade and the
  reason it earned read as one thought.
- **The row's colour stripe is gone.** The chip already states the grade in words AND colour;
  tinting the row said the same thing a third time, before the reader had read anything.
- **Previews are 320px, not 160.** `build_scout._THUMB_W` and the renderer's CSS width are now
  the same number, held together by a test — rendering wider than the file on disk is what made
  the column soft. All 33 existing `thumb.jpg` were re-fetched. Cost, measured rather than
  guessed: 4.2-8.3 KB each, ~0.8 MB for a 100-video queue. The old comment's claim that 320px
  "triples" the page was never measured and was wrong.
  *(Superseded the same week — back to 160px, and the cost figure here undercounted by half
  because the preview was inlined twice per video. See "the preview column" below.)*
- **Page widened 1080 → 1240px** (six columns needed it) and the read cards capped at 62rem, so
  a card is no longer a full-width box wrapped around a 66ch paragraph.
- The card number is no longer a link back to the table: it duplicated the browser's own back
  gesture and competed with the title.

**Per-video timings — closes the measurement half of PLAN item 2.**
- **`timings.json` grew a `detail` section.** `stages[x]` stays the pipeline's wall clock (load
  included — what the run cost); `detail[x]` is what the stage measured about itself.
  `scout.json` surfaces both as `transcribe_sec` / `transcribe_work_sec`, plus
  `transcribe_asr_passes` (2 = the alignment guard re-ran ASR, so that video cost roughly
  double and the outlier has an explanation six months from now).
- **Measured on a real video: 23.0 s stage wall clock vs 17.3 s of work.** A 25% distortion,
  and all of it model load — which lands on whichever video the sweep starts with.
- **`load_whisper` now warms the model** with one throwaway decode, shaped like the real call so
  the same kernels get tuned. Honest scoring: this buys ~0.17 s (large-v3 first decode 0.472 s
  vs 0.30 s steady) and costs ~0.4 s per load. Roughly break-even; it makes video #1 comparable,
  but the real win was excluding the 3.3-3.6 s load, which `work_sec` gets for free.
- **Per-agent summarize time, from a marker file.** The sub-agent's first action is to touch
  `work/<id>/scout.started`; `summarize_sec` is mtime(draft) − mtime(marker). Filesystem-stamped,
  never self-reported. Better than the wave start, which is shared by the whole spawn and bills
  an agent for time it sat behind the concurrency cap.
- **The report's summarize figure no longer spans multiple waves.** It grouped by nothing and took
  `max(draft) − min(start)` across the queue, so a resumed queue (the NORMAL case — the skill
  re-summarizes only what needs it) charged the hours BETWEEN waves to summarization: two 20-min
  waves five hours apart read as 5 h 25 m. Now one window per wave, windows summed.
- **Fixed on the way past: `record_stage_timing` wrote `{"stages": …}` over the whole file**,
  discarding every other top-level key. Invisible while `stages` was the only section; it would
  have eaten `detail` on every stage write.

**Verified:** 49 scout tests, full suite (17 files) green, one live `--scout --force` run end to
end, warmup A/B measured on both large-v3 and small. **Not verified:** no sub-agent has yet run
under the marker instruction, so every `summarize_sec` on disk is still `null`, and no workdir
except one carries `transcribe_work_sec` — the baseline for any optimization comparison does not
exist until the next full queue pass.

## 2026-07-20 — scout grades the MATERIAL, not the reader (supersedes the axes below)

The first real scout queue came back **0 watch · 1 maybe · 9 skip**, and 28 of 30 videos took
the same `attention` value. Both axes shipped that morning; both were replaced the same day, on
that evidence.

- **`verdict` (watch/maybe/skip) → `quality` (high/medium/low), scored on the MATERIAL:**
  substance, currency, delivery. A personal verdict is a decision taken FOR the reader, it
  collapses toward "no", and nothing can check it. Whether a video is well made can be argued
  with — which is what makes the grade worth publishing. The prompt now forbids factoring in
  whether this particular person needs the topic.
- **The viewer profile is demoted to context.** It steers what gets named as the interesting
  part and what counts as already-known; it does not move the grade. The S0 preflight still
  requires it.
- **`attention` (focus/background) deleted.** A field that took one value on 28 of 30 videos is
  a column that teaches the reader to ignore it. "Требует концентрации" is now a clause the
  summarizer writes into the highlight, so it appears only when true.
- **`reason` → `highlight`**: not "why this verdict" but *what is most interesting or useful in
  the video*. The decision goes back to the reader; the report supplies material for it.
- **Layout follows the schema.** The verdict/cost/runtime column is gone: the grade is a stripe
  on the row plus a chip under the title, the runtime rides at the end of the highlight, the
  preview gets its own column, and the jump into the write-up moved onto the description — the
  cell the reader is already reading when they want more. Paragraph splits finally show: the
  summarizer had been splitting by meaning since the morning and the CSS gave it no gap.
- **Cost of the change:** every `scout.json` already on disk carries `verdict` and renders as
  "не отсканировано" until its video is summarized again. The drafts are stale too, so this is
  a real re-run of S2, not a rebuild.
- Verified: 41 tests, full suite green. **Not verified:** no live sub-agent has written a draft
  under the new contract, so whether the model actually separates "quality of the material"
  from "useful to me" is untested — that is exactly the confusion that produced 0/1/9.

## 2026-07-20 — the scout REPORT: rated queue, two lists, published as an Artifact (route C)

**Superseded in part by the entry above** — the `verdict` and `attention` axes described here
were replaced the same day. The rest (the helper split, the wave timing, the three unfinished
states, previews, the playlist header) still stands.

Built on the same day as `--scout` below, after the mode itself was exercised end to end. Scout
answered "what is in this queue"; this layer answers "what of it earns my time".

- **`.claude/viewer-profile.md` — the criterion, and it is personal.** Verdicts are judged against
  one person's stacks, what they already KNOW (the section that stops the system recommending
  beginner courses), and what makes a video useless to them regardless of topic. Without it a
  summarizer can only rate generic quality, which is not the question being asked. **Gitignored**;
  the prompt that builds it from the owner's own chat history is committed at
  `.claude/skills/overdub-scout/references/viewer-profile-prompt.md`, because Claude Code has no
  access to conversation history, profile or memory and cannot produce it here. The skill's S0
  preflight refuses to scout without it — before S1, since S1 is the expensive half.
- **Two orthogonal axes, not one scale.** `verdict` (`watch`/`maybe`/`skip`) is what a video is
  worth; `attention` (`focus`/`background`) is what it COSTS to consume. A deep dive needing
  practice alongside and a survey you can run in the background compete for different budgets, so
  `background` is not a worse grade. `attention` is REQUIRED for the same reason the verdict is: an
  optional cost label goes missing exactly when the summarizer was least sure. An optional `author`
  axis stays absent while the profile's trusted list is empty — a column of one repeated value is
  noise, and filling that list lights it up with no code change.
- **`scripts/build_scout.py` owns everything deterministic**, the same division of labour
  `build_translation.py` enforces on route B: the sub-agent writes six judgement fields into
  `scout.draft.json`, the helper adds title, duration, sentence count and stage timings FROM
  ARTIFACTS, and validates. An unknown `verdict`/`attention` is fatal (they are what the page sorts
  and colours on); a bad optional `author` is clamped; empty prose is fatal; over-length is truncated
  with a `[warn]`.
- **Per-video summarize time is taken from the FILESYSTEM**, not from the model. Sub-agents run
  outside the process and in parallel, so `timings.json` cannot see them; the alternative — the agent
  stamping its own start/finish — is unverifiable self-measurement. `mtime(scout.draft.json) −
  wave_start` is honest about what it measures: TIME-UNTIL-DONE FROM THE WAVE START, which for a
  queued agent includes waiting for a slot. Per-video values therefore do not sum to the wave's wall
  clock, and the page says so. A draft older than the wave start is a carry-over, recorded as
  UNKNOWN rather than as an instant zero.
- **`scripts/scout_report.py` → `work/scout-report.html`.** A scan table (verdict/attention/runtime
  block · preview · title · what it is · why that verdict) and read cards in the SAME order, cross
  linked both ways. **Order is the queue's, never sorted** — the report is read beside the playlist
  it came from, so position is information; this is the deliberate opposite of `triage_html.py`,
  which sorts the worst first because it answers "what is broken". Numbers survive gaps for the same
  reason. Body-fragment HTML (inline `<style>`, no doctype/`<html>`) so it publishes as a Claude
  Artifact unchanged and still opens locally.
- **`one_liner` and `reason` are separate fields** because the scan table asks two questions at once
  and one field answers neither well: "разбор оркестрации агентов" does not say whether to watch it,
  "тема в активной работе" does not say what it is. The full write-up splits into paragraphs on blank
  lines — **the split is the summarizer's**, since only it knows where the meaning turns; the
  renderer honours blank lines and never invents its own.
- **Three unfinished states, not one.** `не скачано` / `не расшифровано` / `не отсканировано`, told
  apart by which artifact is missing, because each needs a different fix. Probed transcript-first: a
  transcript proves the download happened whatever the media looks like now, and probing the wav
  first would order a re-fetch of something already transcribed. A queued video never vanishes from
  the report.
- **Previews are inlined as data-URIs.** A remote `src` is blocked outright by the Artifact CSP —
  invisible in the one place this page is meant to be read. yt-dlp fetches the thumbnail during the
  scout download; older workdirs self-heal over the network from the URL `info.json` already carries.
  One normalizing function, three possible inputs, one output, never fatal — ~3.5 KB per video after
  an ffmpeg downscale to 160 px.
- **The queue's provenance travels with the queue**: a `# playlist: <title> | <url>` header comment
  names and links the source at the top of the report. A comment, so every queue written before this
  keeps working and the line stays valid pipeline input.
- **Transient download failures retry in-process.** A 12-video scout batch lost two videos to
  `HTTP Error 403` and `Video unavailable`; both downloaded on a plain re-run of the same command,
  same binary, same URLs, and their audio-only formats were verified present afterwards — transient,
  and stage-major hoisting every download into the first minutes is the burst shape that provokes it.
  yt-dlp's own knobs (`--retries`/`--extractor-retries`/`--retry-sleep exp=2:60`) now spend seconds
  inside the run instead of costing a human-initiated re-run. **NOT a bug fix** — the resume contract
  already covered it. No full-video fallback was added: paying ~20× the bytes to route around a
  transient is the wrong trade, and the no-audio-only case already fails loud.
- **Own skill, `overdub-scout`** (S0 preflight → S1 scout → S2 rate+summarize → S3 report+publish),
  split out of `overdub-sonnet-batch` so the router cannot pick the dubbing skill for a scouting
  request. The summarizer prompt is shared between the two and marked as such in both files.
- Verified: 41 tests in `tests/test_scout_report.py`, full suite green (17 files). **Not verified:**
  no live sub-agent has ever written a `scout.draft.json` — every draft in testing was hand-authored,
  so `reason`, the paragraph split and the previews are unexercised against a real wave.

## 2026-07-20 — scout mode: `--scout` = download (audio only) → transcribe → stop (roadmap item 1)

- **A cheap triage pass over an unread queue.** `--scout` truncates the pipeline to two stages and
  fetches AUDIO ONLY (`yt-dlp -f bestaudio` → `source.wav`, 16 kHz mono — exactly what whisper eats).
  `source.mkv` is never written, so a 100-video queue costs a few GB instead of ~100 GB in hour 0,
  which is the constraint that motivated the mode (81 GB free on D:, measured 2026-07-20). Works with
  a single URL and with `--batch`, in both batch orders.
- **`DownloadStage.done()` splits into two gates** — audio-ready (`source.wav`) for scout, video-ready
  (`source.mkv` AND `source.wav`) unchanged for everything else. A promoted video therefore fails the
  video gate and re-downloads, while `transcribe` fast-skips on the scout's `sentences.json` so the
  large-v3 pass is not repeated. The `~5%` this wastes, and the three rejected ways of avoiding it,
  are in DECISIONS 2026-07-20.
- **`-f bestaudio` with no `/best` tail**, unlike the full branch's `/b`. The fallback would pull a
  progressive VIDEO stream on a source with no audio-only format — scout silently doing the exact
  thing it exists to prevent, at ~20× the bytes. A hard FAIL for that one video is the correct and
  loud outcome. The audio container is deleted after extraction; the wav is the artifact.
- **`--write-info-json` lands as `source.audio.<ext>.info.json`, a name nothing reads**, so the fetch
  renames it to `source.info.json`. Left alone it costs a 30 s networked `yt-dlp --print title` per
  scouted workdir at report time (~50 min across a 100-video queue) AND silently downgrades a promoted
  video's `video_sec_source` from `info_json` to `ffprobe`/`sentences`. The rename is unconditional:
  the only other writer for a scout workdir is `_title_of`'s title-only backfill, a strict subset.
- **No summarize stage, deliberately** — the pipeline stops after transcribe and `summary.md` keeps
  being written by a Sonnet sub-agent at the seam, exactly as route B already does. `read_summary`
  and `run.json`'s schema needed no change (predicted in the 2026-07-20 summary entry, confirmed).
- **`--scout` is a mode, not an `--only` composition.** `scout_stages()` builds the truncated list and
  the audio-only `DownloadStage` in ONE expression, so the two facts cannot desynchronize into
  "truncated list + full download" (100 GB for a triage pass) or "full list + audio-only download"
  (mux fails eight hours in). `--scout --only` and `--scout --repair-asr` are usage errors, refused
  before any side effect.
- **The scout page.** `scripts/triage_html.py` skipped every run.json-less workdir, so the whole mode
  was invisible there — a pure-scout batch printed "nothing to render" and wrote no file. Scouted
  workdirs now render as a **card** (`SCOUT` tag, duration, sentence count, summary): no audio player,
  no RTF, no triage verdict, and counted separately from videos so "0 need triage" cannot cover 100
  never-dubbed videos. The discriminator is `sentences.json` AND NO `source.mkv` — `sentences.json`
  alone is also the shape of route B's step 1, a workdir between `--repair-asr` and its re-run, and
  any batch killed mid-translate. At zero scouted videos both the page meta and the CLI line are
  byte-identical to the pre-scout strings.
- **New CLI status line** `scouted · 12:34 · 210 sentences · summary pending|ok`, not
  `(no output.mkv)` — the latter is what a broken full run prints, so a clean scout batch would have
  read as a wall of defects. Re-running the identical `--scout` command is therefore the operator's
  completion check for the whole pass: both stages fast-skip, and the line re-reads disk.
- **Pre-existing hazard closed on the way past:** WAV extraction now writes `source.wav.tmp` +
  `replace_retry` on BOTH download paths. Both `done()` gates are bare existence checks, so a run
  killed mid-extraction previously left a truncated `source.wav` that every later resume accepted as
  complete. The atomic tmp then needed an explicit `-f wav` — ffmpeg picks its muxer from the
  extension and `.tmp` matches none, which took both branches down with exit 127 (reproduced against
  the repo's ffmpeg 7.1.1, and the same hazard `mux.py`'s `-f matroska` already guards).
- **Verified in tests only.** 44 new tests — 32 in the new `tests/test_scout.py`, 12 appended to
  `tests/test_triage_html.py`; all 16 test files green (`test_batch_order.py` needed no edits, as
  predicted). A mutation harness killed 8/8 mutants, and in doing so caught two errors in the code
  review: one proposed fix was unpinned by the test that supposedly covered it, and `read_summary`
  does NOT strip a heading to empty (it strips the marker, keeps the text). **No real-media run:**
  no scout pass has been executed against YouTube, so bytes saved, wall per video and the promotion
  round-trip on disk are all unmeasured. See PLAN.

## 2026-07-20 — source-anomaly reporting at the translate seam (roadmap item 1)

- **The translate sub-agent now REPORTS source damage instead of smoothing it.** The prompt gains a
  closed six-kind anomaly vocabulary plus the rule "translate it as-is AND report the id". Rationale
  is in DECISIONS 2026-07-19: a good translator is a defect BLEACHER by default — `RyvXxApfHkk` id11's
  garbage was silently repaired into plausible Russian on the first pass, hiding it from every
  downstream stage. This is compensation for an observability regression the primary translate route
  itself introduced, not a bonus detector.
- **No new artifact.** `src` / `src_note` ride on `translation.draft.json` into `translation.json`.
  `src` is REQUIRED on every record — `"ok"` is a positive claim, so a silent omission cannot pass as
  a clean sentence. `run.json` gains a `source` block with a first-class `scanned` boolean, so route A
  (Gemma) reads "not scanned" and never "clean".
- **Advisory only, by design.** `flags_total += n_src`; `flags_actionable` and `needs_triage` are
  untouched, and every source defect is a `[warn]`, never an exit. Promoting it to actionable is
  gated on measuring the detector's fire rate first (INBOX) — it has zero measured precision, and
  `entity_loss` firing on 11 of 12 videos is the standing cautionary precedent.
- **Latent bug caught by the new column:** `triage_html._batch_table` hard-coded the triage cell as
  `i == 9`. The added `src` column shifts it to 10, which would have silently mis-coloured the status
  cell. Now `len(cells) - 1`. The 2026-07-19 review had flagged this index as a landmine; it took one
  column to step on it.
- Prompt/contract edits in `.claude/skills/overdub-sonnet-batch/SKILL.md` and
  `references/translate-contract.md`. 24 new assertions across three existing test files.

## 2026-07-20 — video summary from the full transcript (roadmap item 3)

- **`work/<id>/summary.md`** — a ~200-word Russian triage summary written by a second Sonnet
  sub-agent at the translate seam, answering "is this worth watching" and "what to look for". Zero
  GPU, one extra agent per video. **Gates nothing** and skips nothing: a model silently dropping a
  video contradicts the project's own no-silent-failures rule, so the skip decision belongs to the
  human (roadmap scout mode).
- **No `build_summary.py`, deliberately.** `build_translation.py` earned its place as an ASSEMBLER of
  machine-consumed fields; a prose blob has nothing to assemble, and a validator would have delivered
  two non-blocking `print`s to a human already reading the prose. All validation moved to the READ
  boundary — `runreport.read_summary()` strips heading markers (they would collide with the digest's
  own `### <vid>` structure), truncates runaway text at 4000 chars with a visible marker, and returns
  `None` for empty/unreadable. Both renderers go through it, so it cannot be bypassed.
- **`run.json` schema UNCHANGED** — the summary is a sidecar. `_build_run_report` unlinks `run.json`
  when report.json and translation.json are both absent, which is exactly scout mode's shape, so
  routing the summary through the rollup would have made it invisible in the mode it exists for.
- Smoke-confirmed: a summary-only workdir already surfaces its summary in the text digest, so scout
  mode needs no change to `read_summary`. Triage HTML still skips such a workdir by design.

## 2026-07-20 — `--repair-asr id,id|auto`: isolated-window ASR repair (roadmap item 2)

- **NEW `overdub/repair.py`** — window derivation, the agreement gate, merge-and-renumber, splice.
  `--repair-asr auto` seeds windows from `rate_implausible` / `dup_adjacent`; `--repair-asr 23,24,25`
  takes explicit ids (single video only). `--repair-dry-run` decides and reports without writing.
  Repair is an operator action, not a Stage: it touches no `all_stages`, runs no downstream stage.
- **A defect's own span is unusable**, so the audio window widens using neighbours' real timings to
  `repair_window_min_sec` (8.0). Whatever run of sentences the widened window covers is what gets
  replaced — the audio window and the replaced id range must be co-extensive, or a reading overwrites
  sentences it only partially heard.
- **Downstream invalidation** (`WorkDir.invalidate_downstream`): an explicit named list, never a
  blanket wipe. `words.json` is deliberately preserved — it is the raw record of what the ASR actually
  did, and `asr.floor_ratio` should keep reporting the collapse. `summary.md` was added to the delete
  set: it is derived from `sentences.json` and nothing in Python ever refreshed it.
- **Measured on the golden fixture — real audio, real large-v3 — and the numbers matter more than the
  feature** (full record: DECISIONS 2026-07-20). `auto` reached **5 of 12** human-repaired regions;
  both known detector-blind videos derived zero windows and printed as clean. One accepted repair
  **REGRESSED** `Claude` → `Cloud` on a sentence that had no flag and was pulled in only by widening,
  with both readings agreeing. Timestamps came out sound (monotone, zero overlaps, max delta 0.71 s);
  the feared silent mis-rebasing does not exist. Cost is ~2.6 s per reading — 20× under the
  2026-07-19 estimate, which predates batch-level model reuse.
- **`WindowResult.collateral` + a `[warn] collateral edit on unflagged id(s)` line** so a
  net-negative substring can no longer report as a bare "1 accepted, 0 rejected". Makes it visible;
  does not make it safe.
- **`repair_window_max_sec` was born dead and is gone.** Its only use was an early return that could
  never change a window for any `max_sec >= min_sec` — verified over 20 000 randomized cases — while
  config.py documented it as load-bearing and the test pinning it passed identically with the guard
  deleted. Deleted rather than made real: merging must be allowed to exceed any cap.

## 2026-07-19 — stage-major batch execution (each model loads once per BATCH)
- **`--batch` now runs stages outer / videos inner.** `_run_batch_stage_major` replaces
  `_run_batch` as the default driver; the old order stays reachable as **`--video-major`**
  (`--batch` only — it errors on a single-video run, which has nothing to amortise). Both orders
  go through the same `run_pipeline`, `_export_output` and `_summarize`, so a bug in the stage
  contract shows up in both and only an ordering bug shows up in one.
- **NEW `pipeline.Session`** — a model cache whose lifetime is exactly ONE stage sweep, so peak
  VRAM stays the MAX over models instead of their sum (that is what keeps the Gemma route safe
  with no parking or eviction policy). Get-or-create at the USE SITE, never eagerly: an
  all-reusable synthesize batch still spawns no F5 worker. `run_pipeline(owns_session=True)`
  clears after every stage, which for a single video reproduces the old per-stage teardown
  exactly; the stage-major driver passes `False` and clears after its own sweep.
- Stages stop owning teardown: `transcribe`/`verify`/`synthesize` lost their `try/finally`
  (`del model` + `gc.collect()` + `torch.cuda.empty_cache()`) in favour of the session. Expected
  amortisation on a 12-video batch: whisper-large 12 loads → 1, F5 worker 12 spawns → 1,
  whisper-small 24 loads → 2 (synthesize and verify are different sweeps), Gemma 12 → 1.
- **NEW `TtsEngine.begin_video()`** (no-op on Silero, resets `_crashes` on F5). A batch-scoped
  engine would otherwise leak its crash budget across videos: `_MAX_CRASHES` counts CONSECUTIVE
  failures within ONE video, so a video that merely flagged 2 synth_errors would hand the next one
  a budget of 1 and kill it with `TtsFatalError` over a perfectly healthy worker. `_rid` is
  deliberately NOT reset — it is the live protocol id matched against worker replies.
- **Ollama unload moved to the end of the translate SWEEP** (`_Unloader` registered in the session
  instead of a per-video `finally`), or stage-major would evict and reload Gemma between every pair
  of videos. Single-video and `--video-major`: the sweep is one video, i.e. the old behavior.
- **Behavior change, deliberate: `build_run_report` now runs for FAILED and STOPPED videos too.**
  Previously a video that failed never reached the rollup, so the batch sweep picked up its
  PREVIOUS `run.json` and counted it in totals/triage — the morning operator saw a green video that
  did not actually render last night. Strictly more honest; guarded by a test.
- `--only` stage names are now validated against the real stage list in `main`. Stage-major would
  otherwise turn a typo into 8 sweeps of no-ops and report "12 ok" — exactly the silent-success
  class this restructure could amplify.
- Summary/sweep reporting: the batch-sweep header stamps the order it ran (`(stage-major)` /
  `(video-major)`) because per-video RTF is not comparable across orders — under stage-major a
  model's load time lands on whichever video went first in that stage. The count word "not run"
  became "unfinished" (under stage-major a video that never finished was still partly processed).
- NEW `tests/test_batch_order.py` — 17 tests, fakes injected into the driver, no GPU/network:
  traversal order both ways, per-video failure isolation, first-error-wins, STOP breaking BOTH
  loops (consume-on-honor means exactly one pair observes it, so continuing would leave the stop
  un-honored for the rest of the batch), the finish sweep, session lifetime, and the engine cache
  key covering both `synth_key` and `f5_python`.

## 2026-07-19 — `f5_nfe` 48 → 16 (2.16× on synthesis, ear-checked); VRAM rule relaxed
- **`cfg.f5_nfe` default 48 → 16.** Ear-checked by the user on a full 5.7-minute video rendered
  both ways: the only defects heard (noise, flat intonation) are in the nfe=48 render too, so they
  belong to the engine and the input, not the step count. Rationale + the EPSS finding that made
  16 the pick over the planned 32: DECISIONS.
- Measured on 40 real production units × nfe {48,32,16,12}: 1.0× / 1.43× / **2.16×** / 2.29×.
  Whole-video check: synthesize 102.6 s against ~174 s predicted for nfe=48, cost model off by
  3.6%. Timing math provably untouched — max combined compression 1.292 both ways, dub track
  identical in length.
- NEW `scripts/exp_nfe_sweep.py` — the measurement harness + blind A/B page generator. Real units
  at their real `target_sec`/`max_sec` (so `plan_speed` reproduces the shipped speed), 7 disjoint
  strata assigned rarest-first, per-cell wall/duration/samples/sha256/round-trip-sim, and
  `--recheck` which re-renders a stratified subset to FALSIFY the determinism premise that
  licenses one render per cell (12/12 byte-identical, on both the naive and EPSS schedule paths).
  `--pages-only` regenerates the blind pages with no GPU.
- Harness design was adversarially reviewed before any GPU time was spent — five findings fixed
  first, the load-bearing two being a `translit` stratum that ranked by text LENGTH and so selected
  against its own property (measured density 0.022 vs the pool's 0.056; the corpus's 41%-Latin unit
  was excluded), and a missing per-cell timestamp without which the block-order/thermal confound
  would have been unrecoverable after the fact.
- **CLAUDE.md VRAM constraint rewritten** from "never load two heavy models at once" to a budget
  with measured numbers. All four models resident is ~7.4 GB of 12; only Gemma-3-12B (~8-9 GB)
  makes it tight. The old rule generalised one model's size into a law and was blocking model
  reuse across a batch for no VRAM reason — measured cost ~72 s per video, ~13 min per 12-video
  batch. See DECISIONS for why stage-major batching, not residency, is the preferred way to
  collect that.

## 2026-07-19 — Item 0 closed: 8 ASR defects repaired, 2 new detectors, batch re-shipped
- **The batch carried 8 defects across 6 of 12 videos, not the 2 PLAN recorded**, and triage
  pointed at none of them. All 8 are now repaired and all 12 MKVs rebuilt.
- NEW `completeness.implausible_rate(texts, durations)` → flag `rate_implausible`: chars/sec above
  40 on the EN source span, the signature of a whisper alignment collapse. Threshold sits on a
  PHYSICAL bound (speech tops out at 25-30 ch/s; corpus median 16.75, p99 34.26) rather than on
  corpus separation. **7 fires / 1100 sentences, 7 true positives, 0 false** — best precision in
  the module, and it found real defects in two videos every text-based signal called `[clean]`.
- NEW containment signal inside `duplicate_adjacent` (`lcs / len(shorter) > 0.85`, OR-ed with the
  existing ratio): catches the whisper RESTART class, where a re-spoken line is swallowed by its
  neighbour and the symmetric ratio is dragged down by the new tail. Ratio alone found 1 of the
  corpus's 3 repetition defects; with containment, 3 of 3.
- FIXED `_RU_NEG_RE` twice. First cut widened it to a bare `бе[зс][а-я]*`, which made
  positive-polarity stems (безопасн-, бесплатн-) count as surviving negation and went blind to
  real inversions ("not safe" → "безопасно"); a test had even been added pinning that miss as
  acceptable. Shipped form subtracts `_NEG_POSITIVE_STEMS` — re-measured identical on the corpus
  (2 fires, target FP `W4Ua6XFfX9w#32` still removed, zero new FPs) while closing the hole.
- Repair method: **isolated-window re-ASR, not full-file re-transcription.** Re-running whole
  files fixed 1 defect of 4 and created new ones; re-transcribing just the defect window (no
  prior context for the loop to feed on) returned a clean reading for 7 of 7, identical under
  `condition_on_previous_text` True and False — that agreement was the acceptance criterion.
  Originals at `work/<id>/_pre-repair*-sentences.json`; `words.json` deliberately untouched.
- 6 videos re-translated through the Sonnet seam. Two defects were found by translator agents
  READING the source, not by any detector — a hallucinated word splitting one sentence in two
  (`W4Ua6XFfX9w` 19/20, both halves at a plausible ~26 ch/s and not similar to each other) and
  self-referential garble. Also fixed `chain-of-thought` → «цепочка рассуждений`, which the
  normalizer had been voicing as "чейн-оф-таугхт".
- Also fixed 0g: `report.json` was structurally stale against `translation.json` across all 12
  (verify/assemble gate on text-derived keys, so flag-only changes never invalidated them),
  leaving 6 phantom `translate:refusal` in the digest that DECISIONS had declared cleared.
- **Result: both ASR detectors fire ZERO times across the batch** (`rate_implausible` max 246 →
  39.36 ch/s; `dup_adjacent` 3 → 0). Digest: 2 of 12 need triage, and both are documented false
  positives — a lexical negation with no не/ни/без token, and an accepted `few-shot prompting`
  Latin run. Full suite (11 files) green.
- Sub-item index (the 0a-0j labels INBOX/DECISIONS still reference; the detail lived in PLAN item 0,
  removed on close): 0a `ytEN_iAk09c` 7/8 duplicated pair · 0b `W4Ua6XFfX9w` four-Ds recap garble ·
  0c the no-duplicate-detector blind spot (→ `dup_adjacent`) · 0d morning-report re-audit (triage
  was wrong about both videos it named) · 0e `RyvXxApfHkk` 10/11 garbled ASR masked by Sonnet's
  repair · 0f `2YCaBqP8muw` 16/17 repetition loop · 0g `report.json` flag-staleness (cleared via
  `--force --only verify assemble`) · 0h `entity_loss` acronym+s bug (left open → PLAN backlog) ·
  0i four-Ds mnemonic destroyed in RU (left open → PLAN backlog) · 0j collapsed spans in videos
  reported `[clean]` (found by the rate detector).

## 2026-07-19 — `no_repeat_ngram_size` measured and REJECTED; guard threshold downgraded
- 60-run sweep (3 videos × n in 0/4/5/6 × 5 repeats, read-only probe, no workdir writes): the knob
  is NOT adopted. Severe source improved (floor 11.07% → 8.2%, dups 2 → 0 at n=6), borderline got
  worse on every axis (floor 6.13% → 13.51%, dups 0 → 2, words +11.5% — more words WITH more
  duplicates = the loop changed shape, not stopped), healthy control degraded at n=4
  (0.13% → 4.44%). No code change; PLAN item 3 struck through with the reason.
- The sweep's third axis is recorded as MISDESIGNED: "word count drops ⇒ real speech eaten" cannot
  distinguish that from "a duplicate was correctly removed", which is exactly the case it had to
  judge. A future attempt needs a content comparison against a reference transcript.
- `cfg.transcribe_floor_run_max` comment corrected: the n=0 cells form a second independent sample
  and put the MID video at 15.82% — above the severe video's entire range, and 2× its own maximum
  from the earlier session. The 1.8 pp "separating gap" does not exist; the populations overlap.
  0.085 is kept only because the severe case has never fallen below it. Catastrophe insurance
  holds; borderline detection is knowingly unreliable.

## 2026-07-19 — Triage that means something: `refusal` narrowed, advisory flags demoted
- FIXED `translate._REFUSAL`: `как (?:ии|модель|языковая)` matched ordinary "как ИИ" = "how AI",
  so all 6 refusal flags in the 12-video batch were false. Now requires the first-person clause a
  real refusal carries (`как ИИ, я …`). Validated 0 false positives / 0 misses over 8 benign + 8
  genuine refusals. All 12 translations rebuilt: refusal 6 → 0.
- NEW `_ADVISORY_COMPLETENESS = {entity_loss, length_short}` in runreport: these are counted and
  printed but no longer decide `needs_triage`. Both are documented false-positive-prone by
  completeness.py itself (personal-name Russification; the deliberately coarse length signal).
  `num_loss` / `neg_loss` stay actionable — an inverted negation is the worst silent loss.
- `run.json` gains `flags_actionable` + `flags_advisory` (`flags_total` unchanged);
  `completeness` gains `n_actionable` + `n_advisory`. Digest block shows
  `completeness N (+M advisory)`; batch table splits `cp` / `adv`.
- EFFECT on the AI-Fluency batch, same run data: **11 of 12 videos needing triage → 2**, and both
  survivors are real (a `neg_loss`; an `english_echo` that would feed Latin script to the TTS).
- Full suite (11 files) green.

## 2026-07-19 — Silero release is a config knob; v5_5_ru becomes the fallback default
- NEW `cfg.silero_model` (default `"v5_5_ru"`, was a hardcoded `MODEL_ID = "v4_ru"` in the
  adapter): the torch.hub release id. v4 was the bake-off entrant BY MISTAKE — already superseded
  at the time — so every pre-2026-07-19 Silero verdict describes an outdated model. v4 stays
  selectable to reproduce old runs.
- `synth_key` now includes the release id (`silero|<model>|<voice>|sr=…`). Load-bearing: without
  it v5 silently reuses v4 wavs under the same voice name, the exact silent-staleness class the
  key's INVARIANT exists to prevent. Legacy manifests re-render once, which is correct.
- `SileroEngine(model_id=…)` + docstring: both releases expose the same five speakers; v5 is
  Cyrillic-only, which is safe only because `text_tts` is Cyrillic by contract (measured: 0 Latin
  characters across all 12 batch videos) — noted with the condition under which a filter is needed.
- AUDITION (5 videos × 5 voices, same translations as the F5 run): synth 11-14 s vs F5's
  128-250 s (12-19× faster, CPU-only, GPU idle); pipeline RTF 0.14-0.17 vs 0.70-0.92; mean
  round-trip similarity 0.979-0.992 vs 0.985-0.991; 0 verify flags, 0 segments over ×1.8.
  Ear: eugene + kseniya best, xenia good-but-slightly-unpleasant, aidar/baya off-standard accent.
  Three ear-only defects (hiss/no ring, no expressiveness, dub lags picture) → DECISIONS + PLAN.
- Production default unchanged: `tts_engine = "f5"`. Full suite (11 files) green.

## 2026-07-19 — Transcribe guard: auto-retry on a collapsed word alignment + `asr` rollup
- NEW `transcribe.floor_run_ratio(flat) -> (ratio, longest_run)`: share of words sitting on the
  `MIN_WORD_DUR` floor IN A CHAIN (start == previous end), the signature of a whisper alignment
  collapse. Only chained hits count — whisper stamps on a 20 ms grid, so an isolated short word
  is ordinary output, not evidence.
- NEW `TranscribeStage._guard`: when the ratio exceeds `cfg.transcribe_floor_run_max` it re-runs
  ASR ONCE with `condition_on_previous_text=False` (the model stays loaded — no reload cost) and
  keeps the retry only if it at least HALVES the ratio; otherwise it keeps the original and says
  loudly that the timings are still suspect. Never silent either way.
- NEW `cfg.transcribe_floor_run_max = 0.085` (0.0 disables), marked PROVISIONAL with its sample.
- `run.json` gains an `asr` block (`n_words`, `floor_ratio`, `floor_longest_run`), recomputed from
  the already-persisted `words.json` — no new artifact, no schema break, and the SAME function the
  guard gates on, so report and guard cannot drift. Reported every run, not only when the guard
  fires: the threshold can only be calibrated from a distribution.
- `scripts/run_report.py`: `floor` column in the batch table, `- asr:` line per video block, and a
  new `--rebuild` flag (recompute run.json from artifacts) so older runs gain new rollup fields.
  Import of `floor_run_ratio` is function-local — a module-level one cycles
  `pipeline → runreport → stages.transcribe → pipeline`.
- NEW `tests/test_transcribe_guard.py` (12 tests: detector shape + every `_guard` branch on a stub
  ASR). Full suite 11 files green.
- FIXED in the AI-Fluency batch: `4szRHy_CT7s` (repetition loop → 2 duplicate sentence pairs, one
  slot at 294 char/s) re-transcribed with the flag off — 170 floor-stamped words → 0, max density
  294 → 24 char/s, atempo ×8.79 → ×1.03, no overlong terminator-free blocks came back.
  `RyvXxApfHkk` likewise re-run: max ×1.81 → ×1.57, 63.6 → 35.9 char/s.
- MEASURED (5 repeat runs × 3 videos): whisper's temperature fallback samples, so the metric scores
  the RUN, not the video — a "clean" control video hit 7.46% on one run of five. See DECISIONS.

## 2026-07-19 — Morning-triage HTML: flagged units with inline audio (closes PLAN item 1)
- NEW `scripts/triage_html.py [work/<id> ...] [--queue FILE] [--out PATH] [--link]`: renders one
  self-contained HTML page for a batch — a triage table (which videos need a listen) + per FLAGGED
  render unit its reason badges, EN/RU text, the ASR similarity + what whisper HEARD back vs the
  EXPECTED `text_tts` (the verify-triage payload), and an `<audio>` player for the unit's raw
  `segments/<lead>.wav`. Audio is base64-EMBEDDED by default (every player works under file://, page
  is portable); `--link` references wavs by relative path (tiny page, must stay next to work/).
  Read-only, best-effort, no model/GPU/network; a missing wav degrades to a note, a missing run.json
  to a skipped video. Videos needing triage sort first.
- NEW `runreport.flagged_units(report, translation)` (pure, tested): UNIT-level triage rows (deduped
  by `group_id`) — reasons unioned across a unit's members (verify/speed/assemble from the leader,
  completeness/translate from any member), leader id (= the wav key), similarity + hypothesis, joined
  EN/RU/tts text, span, speed. +3 tests; full suite (10 files) green. HTML validated well-formed in
  both audio modes on a synthetic workdir (embed base64 + link relative + ASR expected/heard block).
- README morning-triage bullets + skill Step 4 now point at the HTML page alongside the text digest.
  Closes PLAN item 1 (observability) in full.

## 2026-07-19 — Observability: per-run run.json + timings.json + digest + skill Step 4 (PLAN item 1)
- NEW `overdub/runreport.py` (pure stdlib, no model/GPU/network; one best-effort ffprobe): rolls
  up the ALREADY-PERSISTED artifacts into `work/<id>/run.json` — timings + RTF + stage breakdown,
  flag counts by type (translate/verify/completeness), speed distribution (median/p95/max of
  `combined_factor`, count ≥ 1.8), completeness aggregates, retry/repair, flags_total +
  needs_triage. Unit-level fields deduped by `group_id` (report records fan out per sentence) so
  speed/verify by_type count UNITS not member sentences.
- NEW `work/<id>/timings.json`: `run_pipeline` now persists each stage's wall-clock as it runs
  (`record_stage_timing`, atomic upsert) — a resumed/`--only` run rewrites only the stages it
  actually ran; skipped stages keep their last real timing. Never raises into the runner.
- CLI: `_run_one` refreshes run.json after the pipeline (one-line RTF/flags/triage headline);
  `_run_batch` prints a BATCH SWEEP (total wall, aggregate throughput, which video_ids need
  triage) after the existing summary. Both best-effort — a missing/None run.json never crashes.
- NEW `scripts/run_report.py [work\<id> ...] [--queue FILE]`: deterministic ENGLISH digest
  (per-video block + batch table + totals) built from run.json (or rebuilt on the fly). This is
  the DATA the overdub-sonnet-batch skill reads to write its Russian triage narrative.
- Skill: new **Step 4 — Human-readable report** (runs the digest, agent narrates in Russian);
  front-matter description now notes the route ends with a human-readable report.
- 21 tests (`tests/test_runreport.py`), no regression (completeness suite green, all 10 test
  files pass, imports resolve, no import cycle — runreport is stdlib-only). run.json validated on
  a synthetic workdir + the digest smoke. PLAN item 1 now down to its last open sub-part: the
  morning-triage HTML.
- Post-build adversarial review (ultracode, 4 lenses + verify): 9 confirmed minor/nit findings,
  all applied — verify by_type gained an `unknown` catch-all (silent-loss symmetry with translate);
  speed emits null (not a fabricated 1.0) when verify ran but assemble did not; `n_over_1_8` trusts
  assemble's raw-float rollup over the rounded recompute; a reset workdir clears its stale run.json;
  torn timings.json now warns before rebuilding; +6 regression-guard tests.

## 2026-07-19 — Route-B skill audit round 2: 5 gaps closed (SKILL.md only)
- Re-audit vs code after the round-1 hardening: commands/contract/flag table/stage order all
  hold; helper contract tests green. 5 residual gaps, all in SKILL.md orchestration prose:
  (1) `$ids` snippet now fails loud when a queue line doesn't match the id regex — an
  unmatched URL (e.g. `/live/`) is still processed by the pipeline via the `video_id()`
  hash fallback but was invisible to every gate → silent Gemma substitution at step 3;
  (2) `$ids` deduped with `-Unique` (CLI dedupes by video_id; two spellings of one video =
  two sub-agents racing on one draft file); (3) step-2 resume filter `$todo` — skip videos
  with a helper-validated translation.json, mtime clause re-queues drafts stale from a
  re-transcribe; (4) step-3 synth preflight now lists exact paths (config.py defaults incl.
  the not-in-repo ref clip) instead of "models/ exists"; (5) step-2 parallelism capped at
  waves of ~6 sub-agents. All three snippets verified live on a sandbox (dedupe/throw/
  single-URL scalar/todo filter/preflight)

## 2026-07-19 — Completeness A+B: deterministic verify-side loss flags (ultracode)
- NEW `overdub/completeness.py` — 4 non-blocking per-sentence detectors (num_loss/neg_loss/
  entity_loss/length_short) written to `report.json` at verify; rollup `rep["completeness"]`.
  Pure, no LLM/VRAM. 21 tests, no regression. Built via an 8-agent ultracode workflow
  (understand → build → adversarial verify → synthesize).
- Validation (x7DfiXqSEdM, 854 checks): num_loss+length_short = silent precise insurance (0 FP on
  clean data, fire only on a real number/clause drop); entity_loss ~100% FP structurally (naming
  rule permits Russifying personal names); neg_loss guards meaning inversion. User: keep all four
  as-is, triage-only, non-blocking. DECISIONS 2026-07-19
- PLAN: observability / run-report added as item 1 (persist stage timings, per-run rollup, flag
  counts by type, speed distribution, completeness aggregates, batch sweep) — completeness is its
  first data source

## 2026-07-19 — Route-B hardening: skill audit closed 8 defects (skill + helper)
- Skill audit (minimal-context-agent lens) vs code: commands/contract/flag table all held;
  8 gaps fixed. SKILL.md: ids from queue.txt (regex, never a `work/` listing — stale/baseline
  workdirs would be re-translated and their translation.json overwritten), gate before step 2
  (every sentences.json exists), MANDATORY gate before step 3 (every translation.json exists —
  a missing one silently falls back to Gemma with Ollama up, or fails with a misleading
  "start the daemon"), explicit `model: "sonnet"` for sub-agents (else session model silently
  substitutes), incremental draft writes for 300+ sentences, synth-prereq preflight before the
  overnight resume
- build_translation.py: writes pronounce_audit.json (parity with the local route — route B was
  silently losing the only detector for the out-of-dict Latin-name silent-loss class,
  DECISIONS 2026-07-17 item F); rejects non-string text_ru (JSON null coerced to "None" passed
  every _is_bad gate and would be voiced as «нон»). Both verified live on a synthetic workdir
- translate-contract.md: helper's outputs now include pronounce_audit.json
- A/B/C/D on x7DfiXqSEdM (427 sentences): gemma-base vs gemma-impr (completeness+lookahead+few-shot+
  anti-repeat bundle) vs sonnet-v1 (general-purpose) vs sonnet-iso (isolated agent). User read-through:
  Gemma bundle = parity but clumsier → dropped (×10 more >1.5× slots, no completeness win); Sonnet iso
  ≈ v1, no quality gain → dropped; Sonnet >> Gemma, confirmed primary. DECISIONS 2026-07-19
- Kept + committed: `.claude/skills/overdub-sonnet-batch/` (fixed route-B order: transcribe → Sonnet
  sub-agent writes `{id,text_ru}` draft → resume) + `scripts/build_translation.py` (helper fills the
  contract: src_en/timings, `text_tts` via normalize_for_tts, `_is_bad` gate, id-contiguity)
- Discarded: branch `gemma-completeness-ab` (translate.py prompt bundle) and the isolated
  `overdub-translator` agent type — neither earned its keep

## 2026-07-18 — Silero v5 recorded as the good no-sample TTS option
- User verdict: quality slightly below F5/ESpeech, but no narrator reference clip needed —
  zero voice-sample setup and zero rights questions. Documented in README (pipeline, stack
  table, Voices), STACK Stage 3, CLAUDE.md. Adapter still loads v4_ru → INBOX chore to bump
  (`v5_5_ru`; v5 rejects Latin script — needs an out-of-alphabet filter). DECISIONS 2026-07-18

## 2026-07-18 — Sonnet verdict: semi-automatic cloud translate is the primary route
- User read-through verdict on the A/B: Sonnet noticeably better and much faster; both routes
  declared good — Gemma = good quality, local, slow (in-pipeline default); Sonnet = subscription,
  better quality, cloud, replaces the heaviest stage. PRIMARY route = Sonnet in semi-automatic
  mode (sub-agent workflow at the translate seam). In-pipeline Anthropic API flag stays approved
  but deferred. DECISIONS 2026-07-18
- Runbook added to README ("Running"): route A — turn-key local batch (Gemma); route B —
  transcribe-only batch → Sonnet sub-agents write translation.json under the translate contract
  (text_tts via normalize_for_tts in Python, _is_bad gates) → plain rerun resumes from
  synthesize. CLAUDE.md hard-constraint note updated to match

## 2026-07-18 — fix: synthesize.done() congruence gate (stale-wav skip closed)
- done() now compares the manifest's own units against the CURRENT translation.json text_tts
  (same join as verify's reference); mismatch or uncovered ids → stage re-runs and re-renders
  exactly the changed units via the existing reusable() path. Closes the INBOX 2026-07-17 bug:
  `--force --only translate` + plain rerun silently skipped synthesize over stale wavs (bit the
  renorm A/B). Grouping changes stay WARN-only (no surprise regroup); unreadable translation
  keeps legacy behavior. New tests/test_synthesize_done.py (8 cases); all 7 suites green

## 2026-07-18 — Docs audit: README/STACK/SETUP caught up with the code
- README pipeline/stack/status still described the Silero era (contradicting its own "Voices"
  section); STACK's header pipeline line still said Chatterbox and Stage 3 had no section for
  the actual production engine. Both now document F5/ESpeech production + Silero fallback,
  the separate stage + bed mix, and Gemma/F5 VRAM figures
- SETUP: added the missing `.venv-demucs` section — separate.py's error message said "create
  .venv-demucs per SETUP.md" but SETUP never covered it (verified combo from the live venv:
  py 3.12, torch 2.11 cu128, demucs 4.1.0)
- INBOX: purged resolved (struck-through) entries; deleted the 3 superseded session conspectus
  from .claude-tasks/ (each declared superseded by the next; the 2026-07-18 handoff kept).
  Audit also confirmed: all 6 test suites green, no TODO/stub code in the package

## 2026-07-18 — Sonnet cloud-translate A/B spike (sub-agents, not yet in pipeline)
- Ran Claude Sonnet on the SAME 8 videos / 508 sentences / segmentation as the Gemma A/B, via 8
  parallel Sonnet sub-agents (one per video, same prompt rules) — a research spike, NOT the pipeline
  path. Reused Gemma's sentences.json so only the translator varied; built translation.json through
  the same normalize/_is_bad; published a Gemma-vs-Sonnet artifact
- Findings: Sonnet holds length near 1:1 (median 1.00 vs Gemma 1.06 — best dubbing-fit of the three
  models), more natural, and corrects ASR errors both local models translated literally (CLAWD→
  Claude, entropic→Anthropic, «дообучение» for fine-tuning). Flag counts (Sonnet 7 vs Gemma 4) are
  noise — all the «как ИИ/модель» refusal-regex false positive (INBOX); real flags 0/0
- Speed: ~3× faster than Gemma without parallelism (988s cumulative vs 2691s), order-of-magnitude
  faster in parallel (~4 min wall for 8 agents vs ~45 min). Cost: ~$3 per hour of source video (cloud)
- No adoption decision yet — awaiting the user's read-through; if adopted, the in-pipeline opt-in
  Anthropic path still has to be built. completeness-check + babble heuristic returned to the backlog
  tail (triggers: model errors on short sentences / a narrator-voice or TTS-engine change)

## 2026-07-18 — Gemma-3-12B replaces Qwen3-14B (translation model swap)
- 8-video A/B on identical `sentences.json` (the Qwen stats batch's finished 8; only the translator
  varied — bed + downstream byte-identical). 508 sentences: Gemma tighter (len ratio median 1.062
  vs 1.086), fewer flags (4 vs 6), ≈ verify sim. User read ~100 phrases — all better on Gemma;
  Qwen's defects (эффективное×2 for effectively/efficiently, "fluent" left Latin, "Интеллектуальная
  грамотность" for AI fluency) absent. DECISIONS 2026-07-18
- Cost: ~16% slower translate (5.30 vs 4.58 s/sentence), ≈ +8–10% end-to-end. Accepted for the quality
- Code: translate stage folds SYSTEM into the user turn + sends no "think" key (Gemma 3 has no
  thinking mode and rejects a system role). The A/B's two config flags AND the Qwen branch removed
  (Qwen not kept even as an option); `ollama_model` default qwen3:14b → gemma3:12b. Live smoke green
- Built via an ultracode workflow (7 agents) that kept the Qwen wire-request byte-identical during
  the A/B, then collapsed to the single Gemma path. Reference docs updated (Qwen findings in STACK
  retained as history)

## 2026-07-18 — Whisper-context fix ear-validated: roadmap item 0 CLOSED
- Full --force pass on a fresh workdir with `whisper_condition_on_previous=True` (x7DfiXqSEdM,
  work-exp/context-earcheck). Objective: 427 sentences (matched the predicted 314→427), 0 verify
  flags, max speed 1.288, 0 units >1.8. User ear verdict: all found problems gone, no sudden
  pauses, "sounds better than ever"
- One accepted roughness: speech slightly slow (inter-word gaps a touch large) = the slot-fill
  stretch (f5_speed_floor). Compressing instead would open inter-phrase gaps (worse). Root lever is
  the "keep length" prompt pressure (PLAN Open questions), not a post-hoc squeeze. NB the ear-check
  dub used Qwen — the segmentation verdict is translator-independent

## 2026-07-17 — Whisper punctuation context: segmentation root fix (config flag)
- Ear check of the segfix run found the "period mid-sentence" defect frequent (181/314
  sentences open mid-thought). Layered trace: the full stop is Qwen's, but the BREAK is
  `_split_overlong`'s, forced by whisper returning 60-206 s terminator-free blocks under
  `condition_on_previous_text=False`. Qwen is 1:1 and only inherits the break
- Single-variable experiment (flipped ONLY the whisper flag, re-ran ASR): max terminator-free
  range 206→27 s, 314→427 real sentences, both ear cases whole in one sentence. Proves the
  root is whisper punctuation, not Qwen
- Hallucination risk (why the flag was off) measured on the music video: longest repeat run =
  3 ordinary words, zero loops — safe. Shipped as Config `whisper_condition_on_previous`
  (default True, not hardcoded — a looping source can flip it off without code)
- The segmentation cluster (9ca7751) is now second-order (with context on, `_split_overlong`
  rarely fires) but kept as the fallback splitter. Priority lesson in DECISIONS: test the root
  before polishing the symptom
- NOT yet re-run to MKV with the flag on — a full --force pass (~46 min) is the ear-check

## 2026-07-17 — Segmentation cluster: the "pause" that wasn't (transcribe/translate/assemble)
- Root cause (measured on stored words.json, not guessed): `_split_overlong` branch 1 treated
  whisper `seg_end` as a speaker pause, but 73% of seg_ends carry a 0.000 s gap (VAD/window
  artifact). Both ear-reported splits (id149/150 "survival | exploration", id188/189
  "met through | Xbox Live") were cut at gap 0.000, chosen purely by time-midpoint proximity
  ('survival' beat 'games' by 0.030 s). NOT the MAX_SEC cap — the emitted spans were recursion
  leaves with _too_long=False
- Fix: MIN_PAUSE_SEC=0.20 gate on branch 1 + `_ok_cut` veto applied to all three branches
  (filter in 1/2, sort-preference in 3 so it always cuts); `_CONJ`→`_CUT_BEFORE` drops
  ambiguous subordinators (that/which/who/as/if…) that severed verb-object pairs; item E
  ('.'+seg_end before a lowercase word is a boundary, 11/11 genuine on corpus)
- Item F (translate prompt): proper NAMES of games/brands stay Latin with canonical casing
  (runescape→RuneScape) so pronounce.py owns them; `_is_bad` echo gate keys on `islower()`
  and accepts a names-only line whose normalize_for_tts yields Cyrillic (retired id150 false
  english_echo). Item G (assemble): display-only cue split at clause punctuation, ≤6 s/84 ch,
  flash-guarded — sentences.json/ids/timings untouched
- Items C (tolerance band) and D (Capital-after-lowercase run-on) REJECTED on corpus evidence:
  C breaks F5's 12 s unit cap and lets merges rebuild long sentences; D ~5% precision (cuts
  inside "Call of|Duty"). The ear reported A/B/F/G, not C/D
- Process: ultracode workflow, 31 agents; Measure phase first (empirical, disproved my own
  "it's the 15 s cap" diagnosis); 10 review findings all confirmed and fixed (incl. a critical:
  clause branch cutting before "that"). Fix/Smoke re-run after a mid-flight 529. Smoke: 6 test
  suites green, corpus A/B invariants hold, both ear bugs at defensible boundaries, corpus
  SHA-identical (untouched). NOT yet ear-validated post --force re-transcribe

## 2026-07-17 — Proper nouns (roadmap 1, code): pronunciation chain replaces naive translit
- New `overdub/pronounce.py`: PHRASES (multiword names, raw-text pass before numerics) →
  WORDS (~50 established RU spellings: ютуб, иксбокс, хейло, майнкрафт…) → plural tails →
  case-gated acronyms (It/Ok no longer misread; GPUs via singular) → letter names →
  ~74-rule left-to-right practical transcription (sky→скай; the vowel-less скй class is
  structurally excluded — rule output without a vowel letter-spells instead)
- normalize.py passes 0a (phrases) + 1b (PS5→пи-эс пять seam split; after pass 1 so
  1920x1080 is not "в раз") + rewritten pass 6; purity/idempotency/Cyrillic-only intact,
  verify inherits identical resolution via normalize_for_compare
- "Per-run cache" reinterpreted (DECISIONS): audit-only `pronounce_audit.json` from
  translate — dictionary-seeding material, never a resolution input
- `tools/renorm_workdir.py` SRC DST: A/B copy with re-derived text_tts, no LLM re-run,
  SRC untouched; downstream self-heals, only changed units re-render
- Process: ultracode workflow, 43 agents / ~2.9M tok: corpus mine (55 tokens, 60 goldens)
  → 2 designs → judge → impl → 4-lens review (16 findings, all confirmed incl. 2 majors:
  hardlinked wavs could corrupt read-only corpus; acronym-plural bypass) → fixes → smoke:
  4 suites green, 710-sentence sweep 0 violations, 72/710 text_tts improved
- Ear verdict (user, same day, A/B on renormed f5-control — 31 units re-rendered, verify
  0 flags): pronunciation CORRECT on all five target ids — item CLOSED. The A/B also
  surfaced upstream findings (transcribe mid-phrase splits, Qwen self-transliteration,
  long subtitle cues) — reclassified to their own stages, INBOX 2026-07-17
- Found live by the A/B: renorm tool bug — copied complete:true manifest made synthesize
  skip over stale wavs (done() never compares text_tts); fixed same day, tool now writes
  complete:false

## 2026-07-17 — Batch queue + stop switch (roadmap 2-3): overnight runs are turn-key
- `--batch FILE`: one URL per line, `#` comments/blank lines skipped, BOM-safe (utf-8-sig),
  dedupe by video id first-wins; sequential turn-key runs. A failed video prints the full
  traceback and the batch CONTINUES; summary rows [ok/FAIL/stop/not run] + counts; exit codes
  0 ok / 1 any fail / 2 usage / 3 stop-halt. `--force`/`--only` pass through per video
- Stop switch: `work_root/STOP` checked before EVERY stage boundary (hence also between
  videos), consumed at honor time; stale file swept at startup (unremovable → loud abort).
  Halt prints where it stopped; a plain re-run resumes (artifact-driven skip)
- Export: final MKV hardlinked (copy fallback) into `output_dir` (new key, default `out/`)
  as `"<title> [<video id>].mkv"` — atomic .tmp flip, mtime-based refresh on re-mux,
  stale-export cleanup; `work/<id>/output.mkv` never moves. Title persisted at download
  (`--write-info-json`) with a one-shot metadata-only backfill for pre-change workdirs;
  offline → loud id-only fallback. `safe_filename()` in workdir.py (Windows reserved names,
  forbidden chars, 120-char cap, Cyrillic preserved)
- Process: ultracode workflow, 34 agents / ~2.0M tok: 2 design biases → judge spec → impl →
  4-lens adversarial review (13 findings → 11 confirmed by 2-skeptic verify, all fixed) →
  smoke 52/52 (stubbed batch/stop/export/sanitizer, no network). Not yet run on real videos

## 2026-07-17 — Dead-air CLOSED by ear: ceil→atempo fix + bed@0dB is the production mix
- Final ear verdict (user): L3 bed on a music-heavy source works perfectly; the 17:02
  mid-word cutoff is fixed acceptably; remaining artifacts roughly mirror the source's own
  unusual intonations/stutters — the dead-air problem group is closed
- Closing changes: f5_speed_ceil 1.6 → 1.1 (native F5 compression ≥~1.3 drops words; atempo
  never does — it takes the top-up), stricter gate 0.9 for compressed units (ONE shared
  unit_sim_threshold in synthesize + verify); _BED_GAIN −6 → 0 dB; dub_mix default → "bed".
  Duck-depth retest and bed-RMS census/auto-fallback cancelled by the verdict
- Control resynth (39-min): ex-defect unit [135-137] now native 1.1 + atempo ×1.20
  (combined ×1.32) with roundtrip sim 1.0 verbatim; 0 flags, 0 retries, 9 compressed units
  all ≥0.985; residual in-span silence 203.8 s accepted (speech-only source → bed ≈ replace)
- Music-video check (tJP6SKfo49c, 3.6 min, bed stem −29 dBFS RMS / active 99%): full
  turn-key on the flipped defaults incl. auto separate stage; 0 flags, atempo max ×1.18,
  in-span silence 2.9 s — L3 validated on real music
- Commits: 053b29a (fix ceil+gate), 87c31d9 (feat bed@0dB + default), 58831e3 + this (docs)

## 2026-07-16 — Dead-air elimination: slot-fill speed + render units + duck/bed mix
- Measured root cause first: 665 s silence on the 39-min F5 dub = 607 s RU-underfill (fast
  narrator ends before the EN span) + only 68 s real gaps (median 0.14 s) — not a timing bug
- L1 slot-fill: per-unit native F5 speed from the span budget (plan_speed, pure, 16 tests);
  stretch floor 0.75 fixed by a pre-registered bench rule (canvas formula err ≤1.5% incl.
  group-shaped texts, sims stable to 0.7); compress ceil 1.6 before atempo. Caps are
  multipliers of the narrator base pace and enter synth_key
- L2 render units: sentences grouped at synthesis (gap ≤0.4 s, span ≤12 s, ≤300 chars) —
  natural prosody, ultra-shorts dissolve; manifest v3 "units" + units_key fingerprint;
  per-sentence report records with group_id; verify refs CURRENT translation
- L3 dub_mix: replace | duck (sample-exact −15 dB envelope over spans extended to placed
  audio, merged <1 s) | bed (htdemucs no-vocals −6 dB, new separate stage in .venv-demucs,
  45 s for a 39-min video); all modes RMS-align dub loudness to the original (+4.0 dB here)
- Self-healing done() chain: synth/units key stamps in verify/assemble, dub_mix/mtime deps
  in mux — flipping dub_mix re-runs exactly mux (the 3-output A/B costs seconds per mode);
  artifact-flips-before-stamp discipline everywhere (review catch: stamp-first + failed
  replace = silently served stale audio)
- Process: design panel (3+3, 651k tok) → impl → 4-lens adversarial review (25 agents,
  1.51M tok): 20 findings, 1 refuted, all fixed. Control result: in-span silence 204 s
  (−66%), 0 flags, 0 atempo, unit sim mean 0.9939, synth 996 s (was 1409 — fewer calls);
  three outputs produced for the ear verdict, dub_mix default flip pending it

## Phase 3 — TTS engine upgrade ✅ (closed 2026-07-16)
- [x] Research sweep + adversarial verify of the July-2026 local RU TTS landscape →
      bakeoff/tts-research-2026-07.md (~20 engines; only Silero/ESpeech/Misha speak Russian)
- [x] Bake-off #2: ESpeech-TTS-1_RL-V2 unambiguous winner by ear; RU-voice cloning works,
      EN-cloning dropped by goal (DECISIONS 2026-07-16)
- [x] F5Engine behind the adapter — worker in .venv-f5tts, synth_key resume guard, manifest v2
- [x] Reseed-retry in synthesize (keep-best), proven on id43
- [x] Ultra-short merge in transcribe, unit-tested
- [x] Narrator: ESpeech demo reference (rights caveat; PD fallbacks in DECISIONS)
- [x] Control run 39-min vs Silero baseline: flags 0 vs 1, sim 0.9943 vs 0.986, 0 retries;
      RTF gate missed (×0.65 vs ≤0.5, thermal) — x5 budget still cleared ~3.8×
- [x] User ear check passed (id101 ultra-short noted bad → feeds roadmap item 1); default
      tts_engine flipped to "f5", Silero stays the fallback

## 2026-07-16 — F5Engine integrated: worker adapter, reseed-retry, ultra-short merge, control run
- ESpeech (F5-TTS) is now a first-class engine behind the adapter: overdub/tts/f5.py drives a
  persistent worker (overdub/tts/f5_worker.py) in .venv-f5tts over JSONL stdio — venv merge was
  killed by measured evidence (torch 2.11 vs 2.8, numpy downgrade, ~110 packages, torchcodec ABI).
  fd-level stdout isolation, reader-thread timeouts, id-echo, respawn-once + 3-strike TtsFatalError
  (ok:false counts too — sticky CUDA context). Startup ~30 s, warm synth ~×1.1 audio, 0.7 GiB VRAM
- Reseed-retry in SYNTHESIZE (manifest single-writer; verify stays the pure judge): in-stage
  whisper-small round-trip via shared asr.roundtrip_similarity, seeds base+1..+3, keep-best.
  Proven on id43: 4 attempts, best kept, honestly flagged when still low
- synth_key resume guard: engine|ref-content-hash|ckpt|nfe|speed|seed gates ALL wav reuse (engine
  switch / ref swap / knob change → full resynth, loud [info]); manifest v2 with complete-marker,
  downgraded before wavs mutate, flushed every 25 fresh segments (overnight interrupt-resume)
- Ultra-short sentence merge in transcribe (chars<15 → merge into neighbor, gap ≤0.6 s, chain
  absorption ≤1.5 s) + 8 unit tests — kills the id43 class at the source for fresh videos
- Process: design panel (3 biases + 3 lens judges, 610k tok) → implementation → adversarial review
  (4 lenses, per-finding refutation, 1.25M tok): 16 findings, 0 refuted, ALL fixed — incl. 5 major
  (poisoned-CUDA grind cap, sf.info wav/manifest divergence, stale complete:true during resynth,
  ckpt identity missing from synth_key, first-round-trip failure destroying good audio). Judges
  also caught two factual errors by all designers (id43 is in the SAMPLE video; baseline's only
  flag id189 is engine-independent) → control gates made absolute, not baseline-relative
- Control run (39-min x7DfiXqSEdM, frozen transcript/translation, baseline untouched): F5 beats
  Silero on every quality metric — flags 0 vs 1 (id189 proper-noun: F5 0.95 unflagged vs Silero
  0.661), sim mean 0.9943 vs 0.986, min 0.837 vs 0.661, atempo ×1.014/max 1.87 vs ×1.018/max 2.08,
  0 retries. RTF gate missed: synth+verify ×0.65 vs ≤0.5 target (thermal-loaded vs cold 0.39);
  full pipeline ~×1.33 realtime, x5 budget cleared ~3.8×. Default engine flip awaits the user ear
  check (Phase 3 stays open on that one item)

## 2026-07-16 — TTS bake-off #2: ESpeech adopted, narrator selected, cloning explored
- RTF gate PASSED: 39-min real video end-to-end ×0.75 realtime (translate = 80% of wall-clock),
  x5 budget cleared 6.7×. Real-content triage surfaced the proper-noun transliteration defect
  ("но ман'с скй", english_echo false flag) → queued as work item 2 in PLAN
- Multi-agent engine research (~20 engines, adversarial verify, ~940k tokens) →
  bakeoff/tts-research-2026-07.md; only Silero/ESpeech/Misha credibly speak Russian. Bake-off #2
  by ear (bakeoff/listen.html, 8 phrases × 5 engines incl. Silero v5): **ESpeech-TTS-1_RL-V2 wins**
  — .venv-f5tts + ESpeech/Misha checkpoints installed, RTF 0.39 @ 0.8 GiB VRAM measured on host
- Voice cloning explored on full-video runs: RU-ref WORKS (user's voice: 0.994 / 0 flags);
  EN-ref (original-speaker premise) diagnosed — F5 sizes duration by UTF-8 *byte* ratio, Latin ref
  → ×2 canvas → babble filler; two fixes verified (speed≈1.7 → 0.980), then DROPPED by project
  goal. Famous-voice refs (personal-use) failed the quality bar (noisy refs clone their noise)
- Narrator adopted: ESpeech demo reference (0.992 / 0 flags / ×1.03); rights caveat documented in
  README ("Voices, cloning and the law" section); PD fallbacks (LibriVox: tovarisch/Kazbek/Chulsky)
  recorded in DECISIONS; speed-calibration for slow narrators validated (×1.03–1.08 @ ≤0.022 sim)
- New scripts: bakeoff2_silero/bakeoff2_f5/bakeoff3_narrators (auditions), lv_pick_refs
  (PD reference cutting), exp_clone_synth (full-video F5 synth — the F5Engine prototype)
- Intermediate voice artifacts pruned; kept work-exp/espeechvoice (chosen-voice run) + the ref clip

## 2026-07-16 — Phase 1 validated (user ear-test)
- User inspected the assembled output on a real video: RU dub audio present, positioned at the
  correct timestamps, translation correct. This is the Phase-1 quality gate — the pipeline is
  proven turn-key (URL→MKV) on real content, not just mechanically on the sample. Phase 1 closed;
  next up is Phase 2 (batch mode) after broader real-content passes + full-length RTF measurement

## 2026-07-15 — Pipeline tail: synthesize + verify + assemble + mux (Phase 1 complete, turn-key)
- Filled the last 4 stub stages → the pipeline now runs URL→MKV end-to-end. Design panel
  (3-bias) + adversarial review (4-lens + per-finding verify) workflows, per the project rhythm
- synthesize: build_engine (Silero eugene) renders text_tts → segments/NNNNN.wav + manifest.json;
  atomic per-wav (tmp+os.replace), staleness-guarded resume (text_tts + flag), 0-frame honest
  empty slot, sr-drift guard, never-drop contiguity
- verify: whisper-small round-trip on RAW wavs; char-level SequenceMatcher(autojunk=False) of
  normalize_for_compare(text_tts) vs RU hypothesis @ 0.8; deterministic → flag not reseed;
  done() checks the "verify" marker key (NOT report.exists()) so an out-of-order run can't
  silently disable verification; loud guard if run before synthesize
- assemble: place each clip at absolute round(start*sr) in an int16 buffer, slot = [start,
  next.start) (gap = pause headroom), atempo uncapped (ffmpeg single-filter 0.5–100), speed
  factor logged UNCAPPED; dub_ru.wav + en.srt/ru.srt; atomic dub written last
- mux: MKV = av1 video copy + orig aac + RU dub (aac 128k, DEFAULT track) + EN/RU SRT with
  language metadata; explicit per-stream maps; atomic .mkv.tmp
- new overdub/report.py: co-owned report.json (load/upsert/save/prune, merge-by-id) so verify
  and assemble never clobber each other's fields; + workdir.seg_wav; silero.py explicit format="WAV"
- Verified on the 50-sentence sample (each stage via --only): synth 50/0-flagged, verify mean
  sim 0.988 / 0 flagged, assemble 3 sped max ×1.23, mux → 5-stream MKV (video not re-encoded).
  Review: 13 findings → 11 kept (all PLAUSIBLE/low), 2 refuted; 8 cheap fixes applied, 1 → INBOX

## 2026-07-15 — Project founded
- Repository initialized, documentation written (README, CLAUDE.md, artifact files)
- Stack and constraints fixed: see DECISIONS.md founding entry

## 2026-07-15 — Stack installed + day-1 TTS bake-off
- Installed local stack on the RTX 4080 Mobile: Ollama 0.31.2 + qwen3:14b,
  faster-whisper (.venv-asr), verified CUDA in both venvs
- Multi-agent stack-verification pass → STACK.md + SETUP.md (verified APIs, VRAM)
- Day-1 ear test on a real video: Chatterbox RU rejected (unusable even without
  cloning); Silero v4_ru adopted — voice eugene, xenia backup. Cross-lingual
  cloning dropped (same-voice premise abandoned). See DECISIONS engine bake-off.
- Experiment scripts: scripts/{day1_smoke_test,no_ref_test,silero_test}.py

## 2026-07-15 — Phase 0 skeleton
- overdub package: CLI, flat-TOML config, per-video workdir, resumable stage
  runner (skip-if-exists, --only/--force); 7 stages (download real, rest stubs)
- TTS engine adapter + SileroEngine (torch.hub v4_ru/eugene, soundfile output)
- Consolidated to one venv (.venv-asr); .venv-tts retired; `pip install -e .`
- Verified end-to-end: `overdub <url> --only download` → source.mkv + source.wav

## 2026-07-15 — Transcribe stage (Phase 1)
- faster-whisper large-v3 → word timestamps → word-level sentence resegmentation
  → sentences.json (+ words.json for re-tuning). Design + adversarial review via
  two workflows (3-approach design panel; 4-lens review + verify)
- Shared asr.py: Windows cuDNN DLL discovery + whisper loader; cuDNN verified on host
- 885 words → 50 sentences in 32s (RTF ~0.08); contract validated (ids contiguous,
  no zero-duration slots, monotone non-overlapping, no stutter/dangling artifacts)

## 2026-07-15 — Translate stage (Phase 1)
- sentences.json → Qwen3-14B (Ollama) → translation.json: per-sentence, id order,
  rolling ok-only context window; text_ru (subtitles) + text_tts (normalized for TTS).
  Design + adversarial review via two workflows (3-approach panel; 4-lens review+verify)
- New overdub/normalize.py: deterministic digits/units/acronyms/Latin/symbols → spoken
  Russian; idempotent, Cyrillic-only output; normalize_for_compare reused by verify.
  num2words (ru) added; stdlib speller fallback. 9 unit tests (magnitude/range/collision)
- Native Ollama /api/chat + think:false (not /v1 — /no_think left content empty on
  truncated reasoning); ~5s/sentence, openai dependency dropped, stage now stdlib-only
- Robustness: validate→reseed-retry→flagged EN fallback (never drop); append-only
  translation.jsonl (fsync) resume keyed on src_en; contiguity enforced; atomic write
- Verified on the 50-sentence sample: 50/50 ok, 0 flagged, RU/EN length ratios ≤1.67
  (atempo-friendly), resume confirmed (47→50 in 19s). Review fixed 3 silent magnitude
  bugs in the normalizer (grouped thousands, decimal ranges, Cyrillic х/с collisions)
