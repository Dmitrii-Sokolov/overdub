---
name: video-digest
description: "YouTube URL → Russian digest of the video: runs the transcript skill, then applies the digest prompt (what I did not know / what to do / fact-check) to work/<id>/transcript.md and saves work/<id>/digest.md. Trigger on '/video-digest <URL>', 'сделай выжимку видео', 'выжимка по ссылке', 'что нового в этом видео', 'digest this video'. For the bare transcript use transcript; for a dub use overdub-sonnet-batch."
---

# video-digest — URL → `work/<id>/digest.md`

Argument: one YouTube URL. Several URLs: run the whole procedure once per URL.

## Steps

1. **Transcript.** Invoke the `transcript` skill with the URL and follow it as written. Take the
   path of `work/<id>/transcript.md` from its output. A `[warn]` about uncovered speech spans goes
   into the final report; it does not stop the run.
2. **Read** `transcript.md` in full (page through it with `offset`/`limit` if it exceeds one read).
   A transcript that says `_No speech detected._` ends the run: report that, write no digest.
3. **Apply the prompt** in `prompt.md` beside this file, treating the transcript as the attached
   text. Read `prompt.md` fresh each run — it is the one place the wording lives. Speaker labels
   and timecodes are navigation, not content; do not carry them into the digest.
4. **Part 3 (the check) uses WebSearch** for the claims worth verifying, and the digest marks which
   items were searched and which come from memory — as the prompt requires. Do not mark an item as
   searched unless a search was actually run for it.
5. **Save** the result to `work/<id>/digest.md` (Write), then print the same text in the chat.

## After the run

The digest itself is the answer. Under it, one line each: the path to `digest.md`, the video
duration and speaker count (from the transcript header), any `[warn]`.

## Limits

- The digest is written in Russian whatever the video's language; quotes and terms stay as spoken.
- The transcript is ASR output without cleanup: a name or a number may be misheard. Part 3 is where
  that is supposed to surface, so do not silently correct such a spot in Parts 1-2.
- Several speakers (interview, panel): the diarizer's ids are not names. Name a speaker only when
  the description lists the guests and the transcript makes the match plain; otherwise do not
  attribute the claim. The description is the uploader's text, not a checked source: its timecodes
  and names can be wrong too.
