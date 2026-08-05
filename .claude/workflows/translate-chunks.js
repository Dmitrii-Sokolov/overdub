export const meta = {
  name: 'translate-chunks',
  description: 'Route B / Step 2 (long videos): translate one transcript CHUNK per Sonnet sub-agent',
  whenToUse: 'The overdub-sonnet-batch skill Step 2, when a transcript defeats the per-video translator. Needs args {jobs: [{video, from, to, prev?}], root: "D:\\\\code\\\\overdub"}.',
  phases: [
    { title: 'Translate', detail: 'one Sonnet sub-agent per chunk, chained per video' },
  ],
}

// WHY THIS EXISTS, beside translate-batch.js rather than replacing it.
//
// translate-batch.js spawns ONE translator per video, and that is the right shape for almost every
// video: the agent sees the whole transcript at once, which is the stated advantage of this route.
// It has a ceiling. Measured 2026-08-05 on 7xTGNNLPyMI (Karpathy, 3.5 h, 2259 sentences): two
// independent attempts returned 1200/2258 and 1500/2259 records. Not a flaky spawn — the agent
// reads a 411 KB transcript and then has to emit ~250 KB of JSON, and it runs out of window about
// two thirds through. Retrying is not a fix; the third attempt fails the same way.
//
// So the per-video agent stays the default and this is the escape hatch for what defeats it. The
// contract at the seam does not move: each agent writes the ORDINARY draft record shape into
// work/<id>/translate/<from>-<to>.json, and scripts/build_translation.py --join concatenates them
// into translation.draft.json before building translation.json exactly as before. Everything
// downstream of the seam is byte-identical either way.
//
// THE MARKER IS NOT FOR VERIFICATION HERE, IT IS THE WAVE'S START CLOCK. Verification needs none
// on this path — the chunk files ARE per-agent evidence, six files with six mtimes say more than
// one marker would, and --join names the missing one (the reasoning queue-contract §7 gives
// route E). But build_translation.py times the seam as `last agent write - translate.started`,
// and without a start stamp a chunked video contributes NOTHING to the one measurement that says
// what the translate seam costs. So the FIRST chunk touches it and the rest do not: one marker
// per video, same name and same meaning as the per-video route, and the chain guarantees the
// first chunk really is first. Re-running a middle chunk alone therefore leaves the marker
// pointing at the original wave — that video's recorded wall is then a floor, not its cost.
//
// THE CHUNK BOUNDARIES ARE NOT DECIDED HERE. build_translation.py --plan cuts on the longest pause
// near the target and the same function re-derives the cut at --join time, so the planner and the
// assembler cannot disagree about what a chunk was.
//
// Sonnet, set explicitly: the route was verified on Sonnet (DECISIONS 07-18/19), and an inherited
// session model would make two runs of one queue incomparable.

let ARGS = args
if (typeof ARGS === 'string') {
  try { ARGS = JSON.parse(ARGS) } catch (e) { ARGS = null }
}
const OBJ = (typeof ARGS === 'object' && ARGS) ? ARGS : {}
const ROOT = OBJ.root || 'D:\\code\\overdub'
// Flat across the whole queue, like route E: [{video, from, to, prev?}, ...]. `prev` is the file
// name of the chunk immediately before this one in the PLAN — supplied by the orchestrator, which
// is the only side that has the full plan. It may name a chunk translated in an earlier run, which
// is exactly why it is passed rather than inferred from this run's job list.
const JOBS = Array.isArray(OBJ.jobs) ? OBJ.jobs.filter(
  (j) => j && typeof j.video === 'string' && Number.isInteger(j.from) && Number.isInteger(j.to)) : []

if (!JOBS.length) {
  throw new Error(
    'translate-chunks: args.jobs is empty or malformed. Pass the RESUME-FILTERED chunk list, e.g. ' +
    '{jobs: [{video: "abc12345678", from: 0, to: 399}], root: "D:\\\\code\\\\overdub"}. ' +
    'Refusing to run: an empty fan-out would report success having translated nothing.')
}

const CONTRACT = ROOT + '\\.claude\\skills\\overdub-sonnet-batch\\references\\translate-contract.md'

function translatorPrompt(job) {
  const dir = ROOT + '\\work\\' + job.video
  const name = `${job.from}-${job.to}.json`
  const count = job.to - job.from + 1
  // Terminology carryover. Chunking's one real cost is that the whole-video rolling context the
  // per-video translator relies on is gone, and the seam between two chunks is where it shows:
  // a term renamed, a speaker's «вы» turning into «ты». Reading the previous chunk's tail is the
  // cheap fix and the reason the chain runs in order instead of all at once.
  const carry = job.prev ? `
CONTINUITY — READ THIS BEFORE YOU TRANSLATE. The chunk before yours has already been translated to
${dir}\\translate\\${job.prev}
Read its LAST ~30 records and treat them as binding: keep the same Russian for every recurring term,
product, person and acronym, keep the same register and the same form of address, and make your
first sentence read as a continuation of its last one. Where your own instinct and that file differ
on a term, the file wins — a video that renames a concept halfway through is worse than a video
that names it slightly awkwardly throughout. Do not translate any id from that file.` : `
CONTINUITY. Yours is the FIRST chunk of this video, so there is nothing before it to match. Choose
Russian for the recurring terms, products and names carefully and stay consistent with yourself:
the agents translating the later chunks read your output and are told to follow it.`

  // Only the first chunk of a video stamps the wave's start. Later ones must not: the marker is
  // one per video, and a chunk re-touching it would move the start forward and report the wave as
  // shorter than it was.
  const marker = job.prev ? '' : `Your FIRST action, before reading anything: create the empty marker file
${dir}\\translate.started

Use PowerShell: New-Item -ItemType File -Force "${dir}\\translate.started" | Out-Null
Its timestamp is where this video's translate wall is measured FROM. Do not write a timestamp INTO
the file and never report your own runtime — the filesystem stamps it, you only touch it.

`

  return `${marker}MANDATORY FIRST READ: ${CONTRACT}
That file is the translate-seam contract: the translation rules (mirrored from the local route's
SYSTEM prompt), the source-anomaly vocabulary, and the exact draft schema. Read ALL of it before
translating a single sentence. If it is missing or unreadable, STOP and return the single line
CONTRACT-MISSING as your whole answer. Do NOT fall back on your own idea of good dubbing
translation: a translation that silently lost the contract is indistinguishable from one that
followed it, and every downstream invariant on this route assumes the contract held.

You are a dubbing translator for the overdub pipeline. Your input is
${dir}\\sentences.json — a JSON list of {id, text, start, end}, ids contiguous from 0, in order.

YOUR RANGE IS ids ${job.from} TO ${job.to}, INCLUSIVE — ${count} sentences. Those are the ids you
return: every one of them, and no others. Another agent owns the rest and is working right now, so
an id outside your range is not a bonus, it is two agents writing one sentence and the build script
rejects the chunk. Read a few sentences either side for context if you like; never write them.

READ YOUR WHOLE RANGE. The Read tool returns at most 2000 lines by default and this transcript is
much longer, so use offset/limit and keep reading until you have seen id ${job.to}. Before you
translate anything, confirm to yourself that you have the text of both id ${job.from} and id
${job.to}. This is the instruction most likely to be violated silently: a short read gives you the
opening of your range with no warning that the rest is missing.
${carry}

Translate every sentence in your range from English into natural, spoken Russian for a single
narrator, IN ID ORDER, keeping a rolling memory of your own earlier sentences so terminology, names
and pronouns stay consistent.

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

Write ${dir}\\translate\\${name} — a JSON list
[{"id": ${job.from}, "text_ru": "...", "src": "ok"}, ...] with one entry for EVERY id in your range,
in order. Output only text_ru, src and (when src is not "ok") src_note. Do NOT add text_tts, do NOT
respell numbers, do NOT touch timings, do NOT copy the English text back — all of that is filled
deterministically by scripts/build_translation.py, and a hand-spelled text_tts silently breaks ASR
verification. Create the directory first if it does not exist.

Write the file incrementally — batches of ~50 entries per edit, never one giant single-shot write.
UTF-8 without a BOM: the helper reads it with json.loads and a BOM breaks that.

THEN VERIFY YOUR OWN OUTPUT BEFORE ANSWERING. Read the file you just wrote back from disk and check
three things: it holds exactly ${count} records; the ids run from ${job.from} to ${job.to} with no
gaps and no duplicates; every record has a src. This check is the whole reason you are trusted with
a file — build_translation.py --join exits hard on a gap and that costs this chunk a respawn,
whereas you can still fix it right now.

Your final text is a STATUS LINE, not a report. Return exactly ONE of these and nothing else — no
summary of your choices, no list of the anomalies, no terminology notes, no preamble, and above all
no account of the verification you just did:
  OK <written>/${count} anom=<count>       — chunk complete and verified
  INCOMPLETE <written>/${count}            — you could not cover every id; say nothing more
  CONTRACT-MISSING                         — the contract file could not be read
The status must be the LAST line of your answer with nothing after it. Anything you would want to
explain belongs in src_note inside the file, where the helper prints it at the seam and a human can
act on it. Prose returned here is read by nobody and costs the caller its context window — that is
measured, not hypothetical: on the 2026-07-27 batch these reports came to 270k characters, the
worst of them 13,547 characters describing nine edited lines.`
}

// Same parser as translate-batch.js, and case-SENSITIVE for the same reason: a case-insensitive
// "ok" matches the word in ordinary prose ("the file looks ok") and scores a failure as a success.
// Status is parsed from the FULL answer and only then truncated — a narrated status would push the
// real line past a 200-char cut.
const STATUS_RE = /(CONTRACT-MISSING|INCOMPLETE\s+\d+\s*\/\s*\d+|OK(?:\s+\d+\s*\/\s*\d+)?)/g

function parseStatus(full) {
  const hits = String(full || '').match(STATUS_RE)
  if (!hits) return null                                   // -> unclear; the disk decides
  const counted = hits.filter((h) => /\d/.test(h))
  const pick = (counted.length ? counted : hits).pop()
  if (pick.startsWith('CONTRACT-MISSING')) return 'contract'
  if (pick.startsWith('INCOMPLETE')) return 'incomplete'
  return 'ok'
}

function key(j) { return `${j.video}:${j.from}-${j.to}` }

// Group by video, then chain each video's chunks in id order. The chain is what makes the
// carryover above real: chunk N's agent cannot read chunk N-1's file until it exists. Different
// VIDEOS have nothing to say to each other, so they run concurrently — a one-video queue is simply
// a chain of one, which is the case this route was built for.
const byVideo = new Map()
for (const j of JOBS) {
  if (!byVideo.has(j.video)) byVideo.set(j.video, [])
  byVideo.get(j.video).push(j)
}
for (const chunks of byVideo.values()) chunks.sort((a, b) => a.from - b.from)

log(`${JOBS.length} chunk(s) across ${byVideo.size} video(s) — chunks chained per video, videos in parallel`)

const waves = await parallel([...byVideo.values()].map((chunks) => async () => {
  const out = []
  for (const j of chunks) {
    const text = await agent(translatorPrompt(j), {
      label: `translate:${j.video}:${j.from}-${j.to}`,
      phase: 'Translate',
      model: 'sonnet',
      agentType: 'general-purpose',
    })
    // A dropped agent must not abort its video's chain: the later chunks do not depend on this
    // one's CONTENT, only on its file for terminology, and losing five chunks because the second
    // one died would turn one respawn into six.
    out.push(text == null ? { job: j, status: null, dropped: true }
                          : { job: j, status: parseStatus(String(text)) })
  }
  return out
}))

const done = []
const failed = []
const incomplete = []
const unclear = []
const dropped = []
for (const wave of waves) {
  if (!wave) continue
  for (const r of wave) {
    if (r.dropped) dropped.push(key(r.job))
    else if (r.status === 'contract') failed.push(key(r.job))
    else if (r.status === 'incomplete') incomplete.push(key(r.job))
    else if (r.status === 'ok') done.push(key(r.job))
    else unclear.push(key(r.job))
  }
}
// A whole chain can vanish if parallel() drops the wave itself, which no per-chunk bucket above
// would show. Recovered by difference, like route E does for a dropped chunk.
const seen = new Set([...done, ...failed, ...incomplete, ...unclear, ...dropped])
const lost = JOBS.map(key).filter((k) => !seen.has(k))

log(`translated ${done.length}/${JOBS.length}` +
  (incomplete.length ? ` — INCOMPLETE: ${incomplete.join(', ')}` : '') +
  (failed.length ? ` — FAILED: ${failed.join(', ')}` : '') +
  (unclear.length ? ` — unclear status (check on disk): ${unclear.join(', ')}` : '') +
  (dropped.length || lost.length ? ` — DROPPED BY RUNTIME: ${[...dropped, ...lost].join(', ')}` : ''))

// A worklist, not a result. The artifacts on disk are the contract: build_translation.py --join
// runs after this returns (a workflow script has no filesystem or shell access) and it is what
// decides whether the video can be dubbed.
return { done, failed, incomplete, unclear, dropped: [...dropped, ...lost], total: JOBS.length }
