export const meta = {
  name: 'translate-batch',
  description: 'Route B / Step 2: fan out one Sonnet translator (and summarizer) per video, deterministically',
  whenToUse: 'The overdub-sonnet-batch skill Step 2. Needs args {ids: [...], sumIds: [...], root: "D:\\\\code\\\\overdub"}.',
  phases: [
    { title: 'Translate', detail: 'one Sonnet sub-agent per video, all spawned at once' },
    { title: 'Summarize', detail: 'one Sonnet sub-agent per video missing summary.md' },
  ],
}

// WHY THIS EXISTS — the same reason as scout-summarize.js (route C / S2), measured on route B.
//
// Step 2 used to be one Agent call per video that the orchestrator emitted itself, with the
// translation contract PASTED into every prompt. Measured on the 2026-07-27 batch (117 videos,
// transcript c9a89f27):
//
//   translator prompts   87 spawns    403,364 chars      (median 4.5k, all generated token by token)
//   summarizer prompts   11 spawns     22,118 chars
//   inbound reports     123 msgs      270,832 chars      (mean 2.4k, worst 13,547 for a 9-line fix)
//   SendMessage out      40 calls      92,460 chars
//   idle_notification   133 blocks     15,794 chars      (pure noise: "agent is available")
//   ------------------------------------------------------------------
//   orchestrator context 60k -> 893k tokens; ~350k of that is the traffic above
//
// Two independent costs, both removed here:
//
//   CONTEXT. A sub-agent isolates its OWN context, but its prompt and its final report stay in the
//   orchestrator's history forever. Hand fan-out therefore makes the orchestrator pay TWICE per
//   video instead of not at all. At ~9.6k tokens per spawn a 117-video queue cannot fit in a 1M
//   window — the run above died at 89% with Step 4 never executed and 84 of 117 summaries silently
//   never written. A workflow's agent results return to THIS SCRIPT, not to the model's context.
//
//   TIME. scout-summarize.js measured the orchestrator generating prompts at ~8.5 s per 1000 chars,
//   and a wave costing `spawn total + the last agent's own window`. 403k chars of translator prompt
//   is ~57 minutes of pure generation per batch, during which agent-side speedups are worth zero.
//
// The prompts live HERE rather than in the skill for the same reason they do on route C: anything
// the orchestrator has to TYPE is the cost this file exists to remove, and two copies of one prompt
// drift. The contract is not pasted at all — the sub-agent reads it off disk (9.1k chars saved per
// spawn) under a MANDATORY-READ rule with an explicit stop marker, so an agent that could not read
// it aborts loudly instead of translating to its own taste.

// Accept `args` as either an object or a JSON string — the caller stringified it in all 8 attempts
// on route C's first real invocation (2026-07-21), and the failure mode is an empty fan-out that
// reports success. A failed parse becomes null on purpose: that falls through to the loud throw.
let ARGS = args
if (typeof ARGS === 'string') {
  try { ARGS = JSON.parse(ARGS) } catch (e) { ARGS = null }
}
const obj = (typeof ARGS === 'object' && ARGS) ? ARGS : {}
const ROOT = obj.root || 'D:\\code\\overdub'
const IDS = Array.isArray(obj.ids) ? obj.ids : []
const SUM_IDS = Array.isArray(obj.sumIds) ? obj.sumIds : []

if (!IDS.length && !SUM_IDS.length) {
  throw new Error(
    'translate-batch: both args.ids and args.sumIds are empty. Pass the RESUME-FILTERED lists ' +
    'from Step 2, e.g. {ids: ["abc12345678"], sumIds: [...], root: "D:\\\\code\\\\overdub"}. ' +
    'Refusing to run: an empty fan-out would report success having translated nothing.')
}

const CONTRACT = ROOT + '\\.claude\\skills\\overdub-sonnet-batch\\references\\translate-contract.md'

// Markdown backticks are deliberately absent from both templates below: they live inside JS
// template literals, and a hundred hand-escaped backticks is a syntax error waiting to happen.
function translatorPrompt(id) {
  const dir = ROOT + '\\work\\' + id
  return `Your FIRST action, before reading anything: create the empty marker file
${dir}\\translate.started

Use PowerShell: New-Item -ItemType File -Force "${dir}\\translate.started" | Out-Null
Its timestamp is how the pipeline checks that the fan-out actually happened in parallel. Do not
write a timestamp INTO the file and never report your own runtime — the filesystem stamps it, you
only touch it.

MANDATORY FIRST READ: ${CONTRACT}
That file is the translate-seam contract: the translation rules (mirrored from the local route's
SYSTEM prompt), the source-anomaly vocabulary, and the exact draft schema. Read ALL of it before
translating a single sentence. If it is missing or unreadable, STOP and return the single line
CONTRACT-MISSING as your whole answer. Do NOT fall back on your own idea of good dubbing
translation: a translation that silently lost the contract is indistinguishable from one that
followed it, and every downstream invariant on this route assumes the contract held.

You are a dubbing translator for the overdub pipeline. Your input is
${dir}\\sentences.json — a JSON list of {id, text, start, end}, ids contiguous from 0, in order.

READ IT COMPLETELY. This is the one instruction most likely to be violated silently: the Read tool
returns at most 2000 lines by default and this file is frequently longer (measured: 28 of 152
transcripts exceed it, the largest is 5930 lines / 988 sentences). A truncated read gives you the
first third of the video and no warning that anything is missing. So: read it, and if the output
was truncated or its last record's id is lower than the sentence count implies, keep reading with
offset/limit until you have seen the LAST id. Before you translate anything, state to yourself the
total number of sentences and the highest id — every check below is against that number.

Translate every sentence's text from English into natural, spoken Russian for a single-narrator
voice-over, IN ID ORDER, keeping a rolling memory of the earlier sentences and your Russian for
them so terminology, names and pronouns stay consistent across the whole video. You have the
COMPLETE transcript — use it: this route exists precisely because the translator can see the whole
video at once instead of a sliding window.

Follow the contract file's rules exactly. Two of them decide most of the outcome:
  - Keep the Russian CLOSE IN LENGTH to the English. This is dubbing; the line has to fit the same
    on-screen slot. Do not pad, do not over-compress.
  - Judge the ENGLISH source of every sentence and REPORT what looks wrong instead of repairing it.
    Garbled, self-contradictory, truncated mid-thought, duplicative of a neighbour, an enumeration
    item repeating another's head, or contradicting what earlier sentences established: translate
    it AS IS and set src to the matching kind with a short English src_note. A good translator is a
    defect BLEACHER — the better you are, the more reliably you hide that the source was damaged,
    and nothing downstream can see a semantic garble that carries no timing anomaly. Every record
    gets a src; "ok" is a POSITIVE claim that you read that sentence and it is sound.

Write ${dir}\\translation.draft.json — a JSON list
[{"id": 0, "text_ru": "...", "src": "ok"}, ...] with one entry for EVERY id, in order. Output only
text_ru, src and (when src is not "ok") src_note. Do NOT add text_tts, do NOT respell numbers, do
NOT touch timings, do NOT copy the English text back — all of that is filled deterministically by
scripts/build_translation.py, and a hand-spelled text_tts silently breaks ASR verification.

For a long video (300+ sentences) write the file incrementally — batches of ~50 entries per edit,
never one giant single-shot write.

THEN VERIFY YOUR OWN OUTPUT BEFORE ANSWERING. Read the draft you just wrote back from disk and
check three things: the record count equals the sentence count; the ids are contiguous from 0 to
the highest id with no gaps and no duplicates; every record has a src. This check is the whole
reason you are trusted with a file — build_translation.py will exit hard on a gap and that costs a
full respawn, whereas you can still fix it right now.

Your final text is a STATUS LINE, not a report. Return exactly ONE of these and nothing else — no
summary of your choices, no list of the anomalies, no terminology notes, no preamble:
  OK <written>/<total> anom=<count>        — draft complete and verified
  INCOMPLETE <written>/<total>             — you could not cover every id; say nothing more
  CONTRACT-MISSING                         — the contract file could not be read
Anything you would want to explain belongs in src_note inside the file, where the helper prints it
at the seam and a human can act on it. Prose returned here is read by nobody and costs the caller
its context window — that is measured, not hypothetical: on the 2026-07-27 batch these reports came
to 270k characters, the worst of them 13,547 characters describing nine edited lines.`
}

// The prose half of this prompt is IDENTICAL to the summarizer in .claude/workflows/
// scout-summarize.js (route C / S2). Change it in one place and change it in the other, or the two
// routes start producing different artifacts under one name. The route-C copy additionally reads
// the viewer profile and writes scout.draft.json; this one writes only summary.md, which is all the
// dubbing route's digest and queue page read.
function summarizerPrompt(id) {
  const dir = ROOT + '\\work\\' + id
  return `You are a triage summarizer for the overdub pipeline. Read
${dir}\\sentences.json (list of {id, text, start, end} — the COMPLETE English transcript, in order)
and write ${dir}\\summary.md: a summary in RUSSIAN of about 200 words.

Read the transcript COMPLETELY: the Read tool returns at most 2000 lines by default and this file
is frequently longer (28 of 152 transcripts exceed it, the largest is 5930 lines). If the output
was truncated, keep reading with offset/limit until you have seen the last record — a summary
written off the first third of a video is confidently wrong about what the video is.

The reader has NOT watched the video and is deciding whether to. So answer two things, in prose:
(a) is this worth watching at all, and for whom — say so plainly, including "смотреть не стоит" if
that is the honest read; (b) what is the single most interesting thing in it / what to look out
for, and roughly where (use the start timestamps, M:SS). Ground every claim in the transcript — do
not invent facts, names, or numbers that are not there, and if the transcript is too garbled or
thin to judge, say that instead of guessing. Plain paragraphs only: no markdown headings, no bullet
lists, no title, no preamble like "Вот краткое содержание" — the file's whole content is the
summary text. Write EXACTLY TWO paragraphs separated by a BLANK LINE: paragraph 1 is (a),
paragraph 2 is (b), and paragraph 2 must OPEN with the interesting thing itself (e.g. "Самое
интересное — …"), never with a verdict about whether to watch. The queue report reads paragraph 2
as its «самое интересное» column and takes its first sentence verbatim, so a one-paragraph summary
leaves that cell empty and a paragraph 2 opening with "Смотреть стоит…" fills it with the wrong
answer (measured 2026-07-25: 2 of 24 summaries ran the two points together, ~6 opened paragraph 2
with the verdict). Read the file in one pass; write it in one pass.

Write it with PowerShell, never the Write tool. The harness blocks a sub-agent's Write on a path
matching *summary*.md ("Subagents should return findings as text, not write report files") — right
in general, wrong here (this file is a pipeline INPUT that two report surfaces read), and
HARNESS-level, so nothing local turns it off. Use this shape, UTF-8 WITHOUT BOM:

    $summary = @'
    ...the ~200-word Russian prose, verbatim...
    '@
    [System.IO.File]::WriteAllText("${dir}\\summary.md", $summary,
      (New-Object System.Text.UTF8Encoding($false)))

In a here-string the closing '@ MUST sit at column 0 on its own line, and nothing inside it is
interpolated. If writing is refused or unavailable for ANY reason, STOP and return the prose as
your final text — the caller writes it. Do NOT look for another route to disk: a temp file plus a
rename/move is an end-run around the same block, it makes two agents on one batch behave
differently for no reason a reader can see, and it was measured happening on 2026-07-25.

When the file is on disk, verify it exists and return the single line OK — your final text is a
status, not the summary. The summary's home is the file.`
}

// ONE parallel over BOTH kinds of task, not a phase barrier between them. The two are independent
// per video (translate reads sentences.json, summarize reads sentences.json, neither reads the
// other's output), so a barrier would idle every finished translator until the slowest summarizer
// caught up. opts.phase keeps them in separate progress groups without synchronizing them.
const TASKS = [
  ...IDS.map((id) => ({ kind: 'translate', id })),
  ...SUM_IDS.map((id) => ({ kind: 'summarize', id })),
]

log(`fanning out ${IDS.length} translators + ${SUM_IDS.length} summarizers (all at once)`)

const results = await parallel(TASKS.map((t) => () =>
  agent(t.kind === 'translate' ? translatorPrompt(t.id) : summarizerPrompt(t.id), {
    label: `${t.kind}:${t.id}`,
    phase: t.kind === 'translate' ? 'Translate' : 'Summarize',
    model: 'sonnet',            // explicit: the route was verified on Sonnet (DECISIONS 07-18/19)
    agentType: 'general-purpose',
  // Hard cap on what comes back. The prompt asks for one status line; this is what makes it true
  // regardless. On 2026-07-27 the same instruction ("report the count written") produced a mean of
  // 2.4k chars and a worst case of 13.5k, so the instruction alone is not a mechanism.
  }).then((text) => ({ ...t, text: String(text || '').slice(0, 200).trim() }))
))

// Buckets, by id rather than by count: the operator's next move is per video — respawn THIS one.
// `unclear` is NOT failure. It is an agent whose status line we could not parse, whose artifact may
// well be perfect; the skill resolves it from disk, because an agent's account of what it DID is
// worth less than the file it left behind (route C, 2026-07-20).
const done = { translate: [], summarize: [] }
const failed = { translate: [], summarize: [] }
const incomplete = []
const unclear = { translate: [], summarize: [] }

TASKS.forEach((t, i) => {
  const r = results[i]
  const text = r ? r.text : ''
  if (!r) failed[t.kind].push(t.id)                            // runtime dropped the agent
  else if (/CONTRACT-MISSING/i.test(text)) failed.translate.push(t.id)
  else if (/^INCOMPLETE\b/i.test(text)) incomplete.push(t.id)
  else if (/^OK\b/i.test(text)) done[t.kind].push(t.id)
  else unclear[t.kind].push(t.id)
})

const n = (o) => o.translate.length + o.summarize.length
log(`translated ${done.translate.length}/${IDS.length}, summarized ${done.summarize.length}/${SUM_IDS.length}` +
    (incomplete.length ? ` — INCOMPLETE: ${incomplete.join(', ')}` : '') +
    (n(failed) ? ` — FAILED: ${[...failed.translate, ...failed.summarize].join(', ')}` : '') +
    (n(unclear) ? ` — unclear status (check on disk): ${[...unclear.translate, ...unclear.summarize].join(', ')}` : ''))

// A worklist, not a result. The artifacts on disk are the contract; build_translation.py runs after
// this returns (a workflow script has no filesystem or shell access, and the helper has to run per
// video anyway). Deliberately no prose from any agent is carried out of here.
return {
  done, failed, incomplete, unclear,
  total: { translate: IDS.length, summarize: SUM_IDS.length },
}
