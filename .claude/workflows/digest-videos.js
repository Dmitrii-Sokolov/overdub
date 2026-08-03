export const meta = {
  name: 'digest-videos',
  description: 'Route D / D2: digest each transcribed video with Opus, then compress it to budget',
  whenToUse: 'The overdub-digest skill D2 step. Needs args {ids: [...], compressOnly: [...], root: "D:\\\\code\\\\overdub"}.',
  phases: [
    { title: 'Digest', detail: 'one Opus sub-agent per video — complete coverage, length unconstrained' },
    { title: 'Compress', detail: 'one Opus sub-agent per video — fit the budget by cutting, not shaving' },
  ],
}

// WHY TWO PASSES, and it is a measured decision rather than a design preference.
//
// A single pass cannot be talked into a length. Same video (fGKNUvivvnc, 59 min, 691 sentences),
// same transcript, one variable — how the prompt asked for brevity:
//
//   sentence counts ("1-3 sentences")   11,266 chars   7 points   10 cap truncations
//   character budgets ("~450 chars")    11,591 chars   9 points   12 cap truncations
//
// Zero reduction (+3%) against a predicted 3,500. The reason is mechanical: a model cannot count
// characters while composing, and the budget line competes with a concrete, actionable instruction
// in the same prompt ("put the mechanism, the number, the example, the counter-argument in each
// point"). The actionable one wins, every time.
//
// The caps in build_digest then did the damage the length fight was supposed to prevent: on that
// second run a truncation deleted the «plan A / plan B» framing out of the tail of one point — the
// ONE finding of the reference digest that the first run had missed entirely. A cap is not a style
// guard, it deletes content, and it deletes the marginal finding first.
//
// Compression is a different task from composition: the editor HOLDS the text, so "cut this to a
// third" is countable arithmetic instead of a guess about output it has not produced yet. Pass 1
// therefore optimises coverage with no length pressure at all, and pass 2 owns the fit. Cost is
// ~2x per video, accepted deliberately (DECISIONS 2026-07-30).
//
// The other half of why this is a workflow at all: hand fan-out costs ~8.5 s per 1000 prompt chars
// per video and the orchestrator emits one message per agent no matter how the skill is worded
// (three runs, same queue, measured on route C). parallel()/pipeline() do not depend on a model
// choosing to emit N tool_use blocks.

// Accept `args` as either an object or a JSON string. The tool's docs are explicit that the CALLER
// must pass real JSON values, and the runtime hands over whatever it was given — but on the first
// real invocation of the sibling workflow the caller stringified it in all 8 attempts (2026-07-21),
// so parse defensively and keep passing an object from the skill anyway.
let ARGS = args
if (typeof ARGS === 'string') {
  try { ARGS = JSON.parse(ARGS) } catch (e) { ARGS = null }
}
const OBJ = (typeof ARGS === 'object' && ARGS) ? ARGS : {}
const ROOT = OBJ.root || 'D:\\code\\overdub'
// ids            → both passes (no usable digest.long.json on disk)
// compressOnly   → pass 2 only (a fresh long digest exists; its compression is missing or stale)
// The split is the cache: a change to the COMPRESSOR must never re-pay the expensive read pass.
// The orchestrator computes both lists from disk — a workflow script has no filesystem access, so
// it cannot decide this itself, and guessing would silently re-run the expensive half.
const IDS = Array.isArray(OBJ.ids) ? OBJ.ids : []
const COMPRESS_ONLY = Array.isArray(OBJ.compressOnly) ? OBJ.compressOnly : []

if (!IDS.length && !COMPRESS_ONLY.length) {
  throw new Error(
    'digest-videos: both args.ids and args.compressOnly are empty. Pass the RESUME-FILTERED lists ' +
    'from D2, e.g. {ids: ["abc12345678"], compressOnly: [], root: "D:\\\\code\\\\overdub"}. ' +
    'Refusing to run: an empty fan-out would report success having digested nothing.')
}

// ---------------------------------------------------------------- shared prompt fragments
// Kept as constants rather than repeated: the two prompts must agree about the artifact mechanics
// and about what a point IS, and two hand-maintained copies drift.

function writeRules(dir, file, extra) {
  return `HOW TO WRITE THE FILE. PowerShell writes it — build a hashtable and let ConvertTo-Json own
the escaping. Never hand-assemble JSON: the text is multi-paragraph Russian prose with quotes and
dashes in it, and one unescaped newline costs the whole video a re-run. UTF-8 WITHOUT BOM, because
build_digest.py reads it with json.loads and a BOM breaks that.

Assign each long text to its own here-string variable FIRST, then reference it in the array — a
here-string terminator must sit at column 0 on its own line, and nesting one inside an array literal
is where this goes wrong:

    $headline = 'Запись воркшопа, ~40 мин: два инженера разбирают миграцию, сорвавшуюся дважды.'
    $thesis = @'
...one paragraph, verbatim...
'@
    $t1 = @'
...the text of point 1...
'@
    $t2 = @'
...the text of point 2...
'@
    $points = @(
      @{ title = "Откат первой попытки"; at = "6:12"; text = $t1 },
      @{ title = "Чем мерили простой"; text = $t2 }
    )
    $context = @'
...one paragraph...
'@
    $notCovered = 'Нужен разбор конфигов на экране — в пересказ он не вошёл …'
    $obj = @{ headline = $headline; thesis = $thesis; points = $points;
              context = $context; not_covered = $notCovered }
    [System.IO.File]::WriteAllText("${dir}\\${file}",
      ($obj | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))

points must stay an ARRAY (the @( ) is not decoration) and -Depth must be at least 6, or the nested
objects serialize as type names instead of content. Nothing inside a single-quoted here-string is
interpolated, which is why the prose goes in one.

Every example above describes an invented video, and none of them may ever be replaced by an example
taken from a real video in this corpus: the reference digest this format was built against covers a
video that IS in the corpus, and the first draft of this prompt used its headline and two of its
bullet titles as examples — handing the agent two of the answers on exactly the video used to judge
the prompt. Keep the examples fictional.

${extra}
If writing is refused or unavailable for any reason, STOP and return all five fields as your final
text instead, each under a clear header, and say plainly that you could not write the file. Do NOT
look for another route to disk — a temp file plus a rename is an end-run, not an alternative (it was
measured happening on the sibling route on 2026-07-25), and the caller can write the file from your
answer only if you hand the content back instead of retrying.

When the file is on disk, verify it exists and return the single line OK — your final text is a
status, not the digest. The digest's home is the file.`
}

const FIELDS = `- headline — ONE line, no markup, saying what this thing IS: format, runtime, who is speaking, and
  the subject. It goes in a table cell, so keep it under ~200 characters. Do not restate the title
  and do not open with a verdict. Shape (the register, not a template):
  "Recorded workshop, ~40 min: two database engineers walking through a migration that failed twice."

- thesis — ONE paragraph: the central claim or framing the whole video hangs off. Not a summary of
  the summary — the thing that, if the reader took away only one idea, would be that idea. Name the
  position, not the topic: "they argue X, against Y" beats "they discuss X and Y".

- points — the list of what is actually COVERED. This is the field the whole page exists for. Each
  item is an object:
    title  — 2-6 words naming the thing covered, no terminal punctuation (the renderer adds it).
    text   — the CONCRETE content: the mechanism, the number, the example, the counter-argument.
             "They discuss planning" is a wasted bullet; "in a rhyming couplet the model picks the
             final rhyme before starting the second line, and swapping the internal concept rebuilds
             the whole line" is a bullet that saved the reader an hour.
    at     — OPTIONAL "M:SS" (or "H:MM:SS" past an hour) where this starts, read off the start field
             of the sentence where it begins. It is navigation, so it must be real: a marker you
             estimated rather than read is worse than none, and one past the end of the video is
             dropped by the build script as fabricated.

- context — ONE paragraph: why this material exists / what it is for, PLUS the honest caveats. The
  caveats are the load-bearing half: what the speakers themselves admit does not work, how narrow
  the evidence is, what is dated. If the video makes a claim without support, say that here.

- not_covered — the field a reader trusts the page for. Begin with the condition ("нужны детали
  экспериментов и живая дискуссия…"), and name what a digest CANNOT carry: the argument between two
  positions, a demo you have to watch, code on screen, tone, the quality of a Q&A. This is not a
  recommendation to watch — it is the honest inventory of what stayed in the video, i.e. what the
  reader loses by reading you instead of watching it.`

// ---------------------------------------------------------------- pass 1: digest
function digesterPrompt(id) {
  const dir = ROOT + '\\work\\' + id
  return `Your FIRST action, before reading anything: create the empty marker file
${dir}\\digest.started

Its timestamp is how the pipeline measures how long this video's whole chain took. Do not write a
timestamp INTO the file and do not report your own runtime anywhere: the filesystem stamps it, you
only touch it. If you skip this, the video simply has no per-video timing — never invent one.

You are a DIGESTER for the overdub pipeline. You do not grade videos and you do not recommend
anything: a separate route already does that. Your one job is to say WHAT IS IN THIS VIDEO, well
enough that a reader can either (a) check they missed nothing while watching, or (b) know what to
expect before they start.

INPUT, and it is the only ground truth you have:

  ${dir}\\sentences.json — the COMPLETE English transcript as a list of {id, text, start, end}, in
  order. Read ALL of it, in one pass, start to finish. If this file is missing or unreadable, STOP
  and return the single line NO-TRANSCRIPT as your whole answer.

  ${dir}\\source.info.json — the yt-dlp metadata sidecar: title, channel, upload_date (YYYYMMDD),
  duration, description. Take the format, the speakers' names and the date from here, never from
  guesswork. Treat description as the author's own framing, i.e. promotional: useful for what the
  video CLAIMS to be, never as evidence it delivers. If the file is absent, say so in one clause and
  do not infer an age — an invented upload date is worse than an acknowledged gap.

WRITE IN RUSSIAN. Every field below is Russian prose for a Russian reader; this instruction is in
English only because the pipeline's contracts are.

GROUND EVERY CLAIM IN THE TRANSCRIPT. No fact, name, number or example that is not in it. The
transcript came out of ASR, so names and numbers may already be mangled — where a term is clearly
garbled, write what was evidently meant and do not silently upgrade a guess into a fact. If the
transcript is too thin or too garbled to digest (a music video, a wordless demo, whisper
hallucinating a handful of repeated lines over music), say exactly that in thesis and context, keep
the points to what is really there, and still write the file. A video with no verdict is a hole in
the page; a video with an honest "there is nothing here to retell" is a finished row.

COVER THE WHOLE RUNTIME. The commonest failure of this task is a digest of the first fifteen
minutes: check the LAST sentences of the transcript and make sure your points reach the end. If the
tail is genuinely repetition, an outro or a sponsor read, say so in one clause rather than padding.

DO NOT FIGHT FOR BREVITY IN THIS PASS. A second pass compresses your draft to the page's budget, and
it can only cut what you give it — so completeness is your job and length is not. Two consequences,
and they are the point of splitting the passes:
  - Put the concrete anchor IN the text of every point (the mechanism, the number, the example, the
    name). The compressor is allowed to drop a whole point but not to invent detail, so an anchor you
    leave out is gone for good.
  - Do NOT pad. A sentence that adds no fact survives compression no better than it deserves, and it
    costs the compressor the budget it needs for a real one.
How many points: one per thing genuinely covered — roughly 3-4 for a short video, 5-6 for an hour,
6-9 for a long panel. Splitting one topic into three is padding; merging two real topics is a loss.

THE OUTPUT, five fields:

${FIELDS}

${writeRules(dir, 'digest.long.json', `Write ONLY digest.long.json. Do not write digest.draft.json, digest.json or digest.md: the next
pass produces the draft from yours, and build_digest.py derives the rest. A draft written here would
skip the compression pass silently.
`)}`
}

// ---------------------------------------------------------------- pass 2: compress
function compressorPrompt(id) {
  const dir = ROOT + '\\work\\' + id
  return `You are the COMPRESSION pass of the overdub digest route. A previous agent read the whole
transcript and wrote a complete but over-long digest. Your job is to make it fit the page, by
EDITING what it wrote — you are not writing a digest and you are not reading the video.

MANDATORY FIRST READ: ${dir}\\digest.long.json — the long digest, five fields
{headline, thesis, points, context, not_covered}. If it is missing or unreadable, STOP and return the
single line NO-LONG-DIGEST as your whole answer. Do NOT fall back to reading the transcript: the
passes are split so that this one cannot introduce anything, and an agent that quietly re-derives the
digest from source defeats that.

Then read ${dir}\\source.info.json for the video's duration — it sets how many points may survive.

THE POINT CEILING IS THE REAL BUDGET, and the length target is secondary — that order is measured,
not stylistic. Across five videos this task lands at about ONE THIRD of its input whatever divisor it
is given (asked for a fifth on a 19.6k input, produced 2.99x), while the point ceiling is obeyed
exactly, every time. So the number of points you keep is what actually decides how long the page is.

    Aim for ONE THIRD of what you were given, and never below a quarter.

Count the characters of the long version's five fields to know where you are. Per field, as an
aspiration you should push toward rather than a line you must hit:

    point text     ~450 characters            thesis        ~600
    context        ~700                       not_covered   ~350
    headline       leave it alone unless it is over ~200 — it was written to fit

If your fields come out well over those numbers, the fix is to KEEP FEWER POINTS, not to shave a few
sentences off each survivor. Shaving is the "cut the tails" failure the order below exists to prevent:
it costs the concrete anchors, which is the whole content of a point.

HOW MANY POINTS SURVIVE — by runtime, and this is a ceiling, not a target:
    up to ~25 min → 4        up to ~2 h → 6        longer → 8
Over that, DROP whole points: the weakest first, then any that restate another from a different
angle. Two points about one interview are one point.

HOW TO CUT, in this order, and the order is the whole instruction:
  1. Whole points that overlap or add nothing.
  2. Framing, hedging, restatement, "важно отметить, что", anything that describes the video instead
     of reporting what is in it.
  3. Only then, prose inside a surviving point.
THE CONCRETE ANCHOR IS THE LAST THING TO GO — the mechanism, the number, the example, the name. That
is what makes a point worth reading, and it is usually at the END of a sentence, which is exactly
where a careless cut lands. Measured on 2026-07-30: a blind character cap on this same route deleted
the «plan A / plan B» framing out of the tail of one point, and that was the one finding of the whole
digest that the earlier run had missed. A compressor that shaves tails is that same defect with
better manners.

RULES YOU MAY NOT BREAK:
  - Add NO fact, name, number, example or claim that is not already in the long digest. You have no
    transcript, on purpose. If you cannot support a sentence from what you were given, drop it —
    never paraphrase it into a new claim.
  - Keep every surviving point's "at" marker EXACTLY as it was. Never re-time, never invent one,
    never carry a dropped point's marker over to its neighbour.
  - Keep the field structure and the language (Russian). Same five fields, same shape.
  - Keep the caveats in context. They are the half a reader checks the digest against; cutting them
    to fit is how a digest turns into a press release.
  - Keep not_covered honest about what stayed in the video — compress it, do not soften it.

THE OUTPUT is the same five fields, for reference:

${FIELDS}

${writeRules(dir, 'digest.draft.json', `Write ONLY digest.draft.json, and leave digest.long.json exactly as you found it — it is the record
of what the read pass produced, and comparing the two is the only way anyone can ever check what
compression cost. Do not write digest.json or digest.md: build_digest.py derives those.
`)}`
}

// ---------------------------------------------------------------- run
// null stays null in both wrappers: a wrapper object is truthy even around a null, and the `!prev`
// guard on the compress stage below is what keeps a dead read pass from spawning a compressor.
function digestAgent(id) {
  return agent(digesterPrompt(id), {
    label: `digest:${id}`,
    phase: 'Digest',
    model: 'opus',              // explicit: the route was verified on Opus, and an inherited
    agentType: 'general-purpose',//          session model makes two runs incomparable
  }).then((text) => (text == null ? null : { id, text: String(text).slice(0, 200) }))
}

function compressAgent(id) {
  return agent(compressorPrompt(id), {
    label: `compress:${id}`,
    phase: 'Compress',
    model: 'opus',
    agentType: 'general-purpose',
  }).then((text) => (text == null ? null : { id, text: String(text).slice(0, 200) }))
}

log(`${IDS.length} video(s) through both passes, ${COMPRESS_ONLY.length} through compression only`)

// pipeline(), not parallel() + a barrier: each video compresses the moment ITS read pass returns,
// so a 90-minute video still waiting on pass 1 never holds up an 8-minute one's pass 2. The two
// groups run concurrently for the same reason — they share the concurrency cap, not a barrier.
const [chained, only] = await Promise.all([
  pipeline(
    IDS,
    (id) => digestAgent(id),
    (prev, id) => {
      // A dead or aborted read pass must NOT spawn a compressor: it would read a stale
      // digest.long.json from an earlier run, or none, and either way report work it did not do.
      if (!prev || /NO-TRANSCRIPT/i.test(prev.text)) {
        return { id, text: prev ? prev.text : 'DIGEST-DROPPED', pass: 'digest' }
      }
      return compressAgent(id).then((r) => ({ ...r, pass: 'compress' }))
    },
  ),
  parallel(COMPRESS_ONLY.map((id) => () => compressAgent(id).then((r) => ({ ...r, pass: 'compress' })))),
])

// Reported by id rather than counted, because the operator's next move is per video — and the pass
// matters: a failure in `digest` re-runs both, a failure in `compress` re-runs only the cheap half.
const done = []
const failedDigest = []
const failedCompress = []
const all = [...chained, ...only]
all.forEach((r) => {
  if (!r) return
  if (r.pass === 'digest' || /NO-TRANSCRIPT|DIGEST-DROPPED/i.test(r.text)) failedDigest.push(r.id)
  else if (/NO-LONG-DIGEST/i.test(r.text)) failedCompress.push(r.id)
  else done.push(r.id)
})
// A null slot is an agent that produced nothing: pipeline() nulls the whole item, parallel() nulls
// one, and agent() itself returns null on an operator skip or a terminal API error.
const seen = new Set(all.filter(Boolean).map((r) => r.id))
const dropped = [...IDS, ...COMPRESS_ONLY].filter((id) => !seen.has(id))

log(`digested+compressed ${done.length}/${IDS.length + COMPRESS_ONLY.length}` +
  (failedDigest.length ? ` — DIGEST FAILED: ${failedDigest.join(', ')}` : '') +
  (failedCompress.length ? ` — COMPRESS FAILED: ${failedCompress.join(', ')}` : '') +
  (dropped.length ? ` — DROPPED BY RUNTIME: ${dropped.join(', ')}` : ''))

// The workflow does NOT run build_digest.py: a script has no filesystem or shell access, and the
// helper has to run per video after this returns anyway. Artifacts on disk are the contract here;
// this return value is a worklist, not a result.
return {
  done,
  failed: [...failedDigest, ...failedCompress, ...dropped],
  failedDigest,
  failedCompress,
  dropped,
  total: IDS.length + COMPRESS_ONLY.length,
}
