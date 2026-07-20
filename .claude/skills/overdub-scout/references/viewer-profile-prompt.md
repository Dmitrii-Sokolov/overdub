# Building `.claude/viewer-profile.md`

The scout verdicts (`watch` / `maybe` / `skip`) are only as good as the viewer profile behind
them. Without one, a summarizer can only rate generic video quality — which is not the question
the scout report exists to answer.

The profile is **personal and gitignored**. This prompt, which builds it, is committed: it is a
tool, not a person's data.

**How to use it:** paste everything below the separator into a fresh chat on claude.ai — a
surface with access to the person's conversation history, profile and memory. Claude Code cannot
do this itself; it has no access to any of the three. Save the result as
`.claude/viewer-profile.md` in this repo.

The prompt is written in the FIRST PERSON, addressed to the assistant by the profile's owner —
paste it as is; do not rewrite it into the third person.

---

I need a viewer profile. It will be fed to sub-agents that rate YouTube videos from my queue and
return one of three verdicts: definitely watch / questionable / definitely skip. The profile is
the only thing that turns "is this a good video" into "is this useful to *me*", so its quality
determines the quality of every verdict downstream.

Build it from evidence, not from what I claim about myself.

## What to analyze

1. **My conversation history.** Search it yourself; do not ask me for a list.
2. **My profile and preferences** — working style, stated settings, anything stored about me.
3. **Your memory of me** across sessions.

## How to weight the conversations — this part matters

Do not rank chats by last-updated time alone. Use both dimensions:

- **Size.** A long, multi-turn conversation means real engagement. A short chat I touched
  yesterday is often a one-off question and says less about me than a hundred-turn deep dive from
  three months ago.
- **Recency.** A thread alive in the last month outranks one closed half a year ago.
- **Recurrence.** A topic surfacing across a dozen separate chats is a durable interest; a single
  huge chat may be one emergency, not a direction.

Weight highest: large AND recent AND recurring. Separately, call out topics that were once large
and then went quiet — those usually belong in "already know" or "no longer relevant", not in
"actively working on".

## What I do not want

- A list of everything I have ever touched. A profile that lists everything rates everything
  "watch" and is worthless. Cut hard.
- Generalities like "interested in programming" or "likes new technology". They do not separate
  one video from another.
- Guesses presented as facts. Where an inference is thin, mark it as thin.

## What is worth the most to me

The **"what I already know — do NOT recommend an introduction to it"** section. It is the hardest
to build and it saves the most time: without it the system recommends me beginner courses on
things I have done for years. Derive it from what I do without asking, from the level of the
questions I ask, and from the topics where I correct you rather than the reverse.

Second most valuable: **"what makes something useless to me regardless of topic"**. Derive it
from what I reacted to with irritation, what I called empty or padded, and from how I phrase
requests in the first place.

## Output format

Return a ready-to-save Markdown file in exactly this structure, no preamble:

```
# viewer profile — what makes a video worth MY time

<one or two sentences: how this file is used, and that it is meant to be hand-edited>

## Stacks I actually work in
## What I already know — do NOT recommend an introduction to it
## What I am actively chewing on right now
## What makes something USELESS to me regardless of topic
## Staleness — what counts as out of date
```

Short, specific bullets inside each section. In the staleness section, separate the areas that go
stale in months from the ones where age barely matters.

Write the file in whichever language I use with you — the sub-agents read it verbatim and are
fine either way.

## After the file

Separately, outside the file, tell me:

1. **What each non-obvious conclusion rests on** — which conversation or memory led there. I need
   to be able to contest a single bullet, not the whole profile.
2. **Where the evidence ran out**, and what you would ask if I answered three questions.
3. **What surprised you** — any gap between what I say about myself and where my time actually
   goes. That is the most useful part; do not soften it.
