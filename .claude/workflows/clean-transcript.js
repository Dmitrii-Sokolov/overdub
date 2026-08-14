export const meta = {
  name: 'clean-transcript',
  description: 'Route E / E3: clean each transcript chunk with Sonnet, one sub-agent per chunk',
  whenToUse: 'The overdub-clean skill E3 step. Needs args {jobs: [{video, from, to, lang}], root: "D:\\\\code\\\\overdub"}; lang is "en" or "ru" and comes from build_clean.py --plan.',
  phases: [
    { title: 'Clean', detail: 'one Sonnet sub-agent per chunk — filler out, wording untouched' },
  ],
}

// WHY ONE AGENT PER CHUNK RATHER THAN PER VIDEO, and it follows from what this route produces.
//
// Routes C and D are output-tiny: an agent reads a 60k-character transcript and writes 3k. This one
// is output-heavy — a cleaned transcript is roughly as long as its source — so a per-video agent
// would have to emit tens of thousands of characters in one answer. That fails in a specific and
// silent way: the model cleans the opening faithfully and compresses harder the further it goes,
// so the tail arrives as a summary. Nothing in the artifact says which half you are reading.
//
// Chunking removes the failure instead of detecting it. ~80 sentences is ~7k characters of output,
// well inside the range where the task stays mechanical, and the id contract makes a lost line
// impossible to hide: build_clean.py demands every id in the range back and exits on a gap.
//
// The chunk BOUNDARIES are not decided here. scripts/build_clean.py --plan cuts on the longest
// pause near the target, the orchestrator passes that cut through, and the same function re-derives
// it at join time — so the plan and the assembler cannot disagree about what a chunk was.
//
// Sonnet, not Opus, and set explicitly: this is a mechanical edit with an exact contract, not a
// judgement task. An inherited session model would also make two runs of one queue incomparable.

let ARGS = args
if (typeof ARGS === 'string') {
  try { ARGS = JSON.parse(ARGS) } catch (e) { ARGS = null }
}
const OBJ = (typeof ARGS === 'object' && ARGS) ? ARGS : {}
const ROOT = OBJ.root || 'D:\\code\\overdub'
const LANGS = ['en', 'ru']
// Flat list across the WHOLE queue: [{video, from, to, lang}, ...]. Flat rather than grouped per
// video because the concurrency cap is global anyway, and a flat list lets a single failed chunk be
// re-run on its own without rebuilding a nested structure.
const RAW = Array.isArray(OBJ.jobs) ? OBJ.jobs : []
const JOBS = RAW.filter(
  (j) => j && typeof j.video === 'string' && Number.isInteger(j.from) && Number.isInteger(j.to) &&
    LANGS.indexOf(j.lang) !== -1)

// Named rather than silently dropped: `lang` became required when route E stopped being
// English-only, and a caller still passing the old three-field shape would otherwise see its whole
// fan-out filtered away and be told only that the list was "empty" — the wrong thing to go fix.
if (JOBS.length !== RAW.length) {
  throw new Error(
    'clean-transcript: ' + (RAW.length - JOBS.length) + ' of ' + RAW.length + ' job(s) are ' +
    'malformed. Each needs {video, from, to, lang} with lang one of ' + LANGS.join('/') + '; take ' +
    'lang from `build_clean.py --plan`, which detects it per video — never guess it here.')
}
if (!JOBS.length) {
  throw new Error(
    'clean-transcript: args.jobs is empty. Pass the RESUME-FILTERED chunk list from E3, e.g. ' +
    '{jobs: [{video: "abc12345678", from: 0, to: 79, lang: "en"}], root: "D:\\\\code\\\\overdub"}. ' +
    'Refusing to run: an empty fan-out would report success having cleaned nothing.')
}

// WHAT IS LANGUAGE-SPECIFIC HERE, AND WHY IT IS ONLY THIS. Route E was English-only until
// 2026-08-14; extending it to Russian was measured before it was written (OAu3jkX8dK4, 1832
// sentences, Parakeet on both sides), and almost nothing on the Python side had to move: sentence
// length lands at 79 chars against an English median of 80, so the 80-sentence chunk still holds;
// dotted abbreviations appear once in 1832 lines; and the Latin-only entity detector performs
// BETTER on Russian technical speech than a Cyrillic one would. What is genuinely language-bound is
// this prompt — a filler list is a fact about a language, and the English one names nothing a
// Russian speaker actually says.
const LANG = {
  en: {
    name: 'English',
    remove: `  - filler and hesitation: um, uh, ah, er, "you know", "I mean", "sort of"/"kind of" when they carry
    no meaning, "like" used as a verbal tic, "right?" and "okay?" used as punctuation.`,
    fix: '',
    empty: '"So. Yeah.", "Um, right."',
    sample: `      @{ id = 0; text = "We tested it twice and it failed twice." },
      @{ id = 1; text = "" },
      @{ id = 2; text = "The second run took forty minutes." }`,
  },
  ru: {
    name: 'Russian',
    // Frequencies measured on OAu3jkX8dK4 (3 h of Russian technical speech): вот 685, то есть 206,
    // ну 199, типа 110, просто 105, короче 103, да 96, как бы 46, на самом деле 28. The second
    // paragraph exists because that list is NOT a delete-list — several of those words are ordinary
    // vocabulary most of the time, and an agent given only the counts would strip meaning.
    remove: `  - filler and hesitation: «э-э», «а-а», «ну», «вот», «типа», «как бы», «короче», «в общем»,
    «так сказать», «собственно», and tag questions used as punctuation: «да?», «понимаешь?», «знаешь?».
  - CAREFUL — these are filler only SOMETIMES and are ordinary words the rest of the time. Read the
    sentence before touching one: «то есть» often introduces a real clarification, «просто» can mean
    "merely", «значит» can mean "so/therefore", «да» can be an answer, and «вот» can be a
    demonstrative («вот этот метод»). When in doubt, keep it. Keeping a filler costs a reader one
    word; deleting a real one costs them the meaning.`,
    fix: `  - English technical terms the speaker pronounced in Russian and the ASR wrote in Cyrillic. Restore
    the form the industry writes: «Джейсон» -> JSON, «ЕЦС» -> ECS, «Адресаблс» -> Addressables,
    «Юай» -> UI, «гарбадж коллектор» -> garbage collector.
    THE LIMIT, and it matters more than the rule: restore NAMES only — APIs, products, acronyms,
    class and library names. Do NOT latinise ordinary Russian words that happen to be borrowings:
    «компонент», «шейдер», «рендеринг», «кэш», «профайлер» stay Cyrillic. Restore only what the
    surrounding text makes unambiguous; a mangled term you cannot identify stays exactly as the ASR
    wrote it. This is the one place in your task where you rewrite rather than delete, so it is also
    the one place where you can invent — do not.`,
    empty: '«Ну вот.», «Так, ага.»',
    sample: `      @{ id = 0; text = "Мы протестировали это дважды, и оба раза упало." },
      @{ id = 1; text = "" },
      @{ id = 2; text = "Второй прогон занял сорок минут." }`,
  },
}

function cleanerPrompt(job) {
  const dir = ROOT + '\\work\\' + job.video
  const name = `${job.from}-${job.to}.json`
  const L = LANG[job.lang]
  return `You are a TRANSCRIPT CLEANER for the overdub pipeline. You are not a summariser, not a
translator and not an editor of substance: a separate route does each of those. Your one job is to
turn raw ASR output into text a human can read, changing as little as possible.

INPUT, and it is the only ground truth you have:

  ${dir}\\sentences.json — the COMPLETE ${L.name} transcript as a list of {id, text, start, end}, in
  order. If this file is missing or unreadable, STOP and return the single line NO-TRANSCRIPT as
  your whole answer.

The transcript is in ${L.name} and your output is in ${L.name}. That was DETECTED from the file, not
assumed: if what you read is plainly some other language, stop and say so rather than cleaning it.

YOUR RANGE IS ids ${job.from} TO ${job.to}, INCLUSIVE. Those are the ids you return — every one of
them, no others. Read a few sentences either side for context if you like, but never write them:
another agent owns them and is working right now.

WHAT TO REMOVE:
${L.remove}
  - false starts and self-interruptions: "we should — we really should test this" -> "we really
    should test this".
  - stutters and immediate word repetitions the speaker did not intend ("the the", "and and").
  - ASR debris: a stray repeated line, a fragment that is clearly the tail of the previous sentence
    duplicated.

WHAT TO FIX:
  - punctuation and capitalisation, so the sentence reads as written ${L.name}.
  - obvious ASR mishearings of terms the surrounding text makes unambiguous. Fix the SPELLING of
    something you can identify; never upgrade a guess into a fact. If you cannot tell what was
    meant, leave the text exactly as it is — a visible oddity is honest, an invented term is not.${L.fix ? '\n' + L.fix : ''}

WHAT YOU MAY NOT DO, and these are the rules the pipeline checks:
  - Do NOT paraphrase. Keep the speaker's own words, register and word order. If a sentence is
    already clean, return it byte-identical. Most sentences should come back nearly unchanged —
    that is success, not laziness.
  - Do NOT shorten, summarise or "tighten" anything. Removing filler is the only compression
    allowed. A chunk that comes back much shorter than its source is rejected by the build script.
  - Do NOT merge or split sentences, and do NOT move text between ids. Each id keeps its own
    content because each id is anchored to a timestamp in the audio. Paragraphs are assembled later
    from the pauses, so a run-on pair of ids will read fine without your help.
  - Do NOT translate. The output is ${L.name}, exactly like the input. The build script compares the
    script of your text against its source and flags a chunk that changed one, because a translation
    passes every other check here: it is complete, correctly numbered and about the right length.
  - Do NOT add anything: no headings, no commentary, no bridging phrases, no "[inaudible]".
  - Keep every number, name, product and acronym. The build script checks for these and warns when
    one disappears.

AN EMPTY STRING IS ALLOWED AND IS SOMETIMES CORRECT. If a line is nothing but filler (${L.empty}),
return it as "" — the renderer drops it and its id stays accounted for. What you may
never do is omit the id: a missing id fails the build, because an emptied line and a lost line look
identical in a text file afterwards.

HOW TO WRITE THE FILE. PowerShell writes it — build the array and let ConvertTo-Json own the
escaping. Never hand-assemble JSON: the text carries quotes, apostrophes and dashes, and one
unescaped character costs the whole chunk a re-run. UTF-8 WITHOUT BOM, because build_clean.py reads
it with json.loads and a BOM breaks that.

    New-Item -ItemType Directory -Force "${dir}\\clean" | Out-Null
    $rows = @(
${L.sample}
    )
    [System.IO.File]::WriteAllText("${dir}\\clean\\${name}",
      ($rows | ConvertTo-Json -Depth 4), (New-Object System.Text.UTF8Encoding($false)))

The ids above are an illustration of the SHAPE — yours are ${job.from}..${job.to}. Keep the @( ) so
a single-record chunk still serializes as an array, and keep -Depth at 4 or more.

For a long chunk, assign the awkward strings to variables first, or write the file in one go from a
here-string only if you are certain of the escaping — ConvertTo-Json is the safe path and is why it
is specified here.

If writing is refused or unavailable for any reason, STOP and return the JSON array as your final
text instead, and say plainly that you could not write the file. Do NOT look for another route to
disk — a temp file plus a rename is an end-run, not an alternative — and the caller can write the
file from your answer only if you hand the content back.

When the file is on disk, verify it exists and that it holds exactly ${job.to - job.from + 1}
records, then return the single line OK. Your final text is a status, not the transcript.`
}

function cleanAgent(job) {
  const label = `clean:${job.video}:${job.from}-${job.to}`
  return agent(cleanerPrompt(job), {
    label,
    phase: 'Clean',
    model: 'sonnet',
    agentType: 'general-purpose',
  }).then((text) => (text == null ? null : { job, text: String(text).slice(0, 200) }))
}

const videos = new Set(JOBS.map((j) => j.video))
const langs = Array.from(new Set(JOBS.map((j) => j.lang))).sort()
log(`${JOBS.length} chunk(s) across ${videos.size} video(s) · ${langs.join('+')}`)

// parallel(), not pipeline(): chunks are independent single-stage work, so there is nothing to
// chain. The cap keeps ~10 in flight and the rest queue.
const results = await parallel(JOBS.map((j) => () => cleanAgent(j)))

const done = []
const failed = []
results.forEach((r) => {
  if (!r) return
  const id = `${r.job.video}:${r.job.from}-${r.job.to}`
  if (/NO-TRANSCRIPT/i.test(r.text)) failed.push(id)
  else done.push(id)
})
// A null slot is an agent that produced nothing — the runtime dropped it, or agent() returned null
// on an operator skip or a terminal API error. Indistinguishable from success in the array, so it
// is recovered by difference rather than counted.
const seen = new Set(results.filter(Boolean).map((r) => `${r.job.video}:${r.job.from}-${r.job.to}`))
const dropped = JOBS.map((j) => `${j.video}:${j.from}-${j.to}`).filter((k) => !seen.has(k))

log(`cleaned ${done.length}/${JOBS.length}` +
  (failed.length ? ` — FAILED: ${failed.join(', ')}` : '') +
  (dropped.length ? ` — DROPPED BY RUNTIME: ${dropped.join(', ')}` : ''))

// The workflow does NOT run build_clean.py: a script has no filesystem or shell access, and the
// join has to run per video after this returns anyway. Artifacts on disk are the contract here;
// this return value is a worklist, and a chunk it calls done can still be missing from disk.
return { done, failed, dropped, total: JOBS.length }
