---
name: video-digest
description: "One or more videos, YouTube URLs or local files → one Russian digest judged as of today: facts and ideas, what to do about them, and a check of errors, outdated claims and forecasts against the current date. Several videos make one aggregated report, not a digest each. Runs the transcript pass, applies the digest prompt, saves digests/<date>-<id>.md or digests/<date>-<slug>.md. Trigger on '/video-digest <URL or file> ...', 'сделай выжимку видео', 'выжимка по ссылке', 'общий отчёт по этим видео', 'что нового в этом видео', 'digest this video'. For the bare transcript use transcript; for a dub use overdub-sonnet-batch."
---

# video-digest — videos → one digest

Arguments: one or more inputs, each a YouTube URL or a path to a local media file.

## Steps

1. **Resolve each input.** The same id given twice counts once.
   - A URL becomes `https://www.youtube.com/watch?v=<id>`, the id taken with the regex of
     `docs/queue-contract.md` §1, so no `&list=`, timestamp or tracking tail reaches the queue file.
     A URL the regex does not match is dropped and named in the final report.
   - A local file with a YouTube id in its name (`Title [<11 chars>].mkv`, the name yt-dlp and overdub
     give) becomes `https://www.youtube.com/watch?v=<id>`. An existing `work/<id>/` is reused: its
     `sentences.json` spares the ASR pass, but only its `source.wav` spares the network — a workdir
     whose `source.wav` a `work/` cleanup took fetches the audio from YouTube again. Without a
     workdir, the audio comes from YouTube.
   - A local file with no id goes to step 3.
2. **Transcripts for everything with an id**, in one pass, so the models load once. From the repo
   root, with the URLs in a queue file in the scratchpad:

   ```powershell
   .venv-asr\Scripts\python.exe -X utf8 -m overdub --batch <queue file> --transcribe-only
   ```

   Each video gets `work/<id>/transcript.md`. A finished dub stays intact: the run adds
   `transcript_view.json` beside it and leaves the translation and the MKV alone. Do not add
   `--force`: a dubbed video refuses it and fails. Collect every
   `[warn]`. If a local file's video is gone from YouTube, treat that file as having no id. Any
   other failure goes into the final report and the rest carry on.
3. **Transcripts for files with no id**, one command per file. First, any video whose download
   failed in step 2 but whose `work/<id>/transcript.md` is on disk from an earlier run keeps that
   transcript, URL or file alike: use it as it is and name the failed download in the final report.
   Only a file without one comes here.

   ```powershell
   .venv-asr\Scripts\python.exe -X utf8 -m overdub --transcribe-file "<path>" --out "<scratchpad>\<n>-<stem>.transcript.md"
   ```

   `<n>` is the input's position in the arguments, so two files with one name from different
   folders do not overwrite each other.

   This route reads the first audio track and gives no metadata and no speaker labels. For a file
   whose id has a workdir, take the title, channel and date from `work/<id>/source.info.json` or
   `work/<id>/source.mkv.info.json`, whichever exists. A date the user stated counts; the date the
   file has on disk does not, it says nothing about publication.
4. **Read** every transcript in full, paging with `offset`/`limit` where needed. The header gives
   the title, duration, speakers, channel, publication date, popularity and link; the description
   and chapters follow it. A transcript that says `_No speech detected._` drops out and is named in
   the final report; if none remain, write no digest. When the transcripts together will not fit
   in the session, give each to its own `Agent` to return the material for Parts 1-2 and the claims
   and forecasts to check, then write the report and run the searches of step 6 here, once.
5. **Apply the prompt** in `prompt.md` beside this file, treating the transcripts as the attached
   text. Read `prompt.md` fresh each run: it is the one place the wording lives. Today's date comes
   from the session environment. Speaker labels and timecodes are navigation, not content; do not
   carry them into the digest.
6. **Part 3 uses WebSearch** for the errors worth verifying, for what may have changed since
   publication, and for every forecast whose date has passed. The digest marks which items were searched and
   which come from memory, as the prompt requires. Do not mark an item as searched unless a search
   was actually run for it.
7. **Save** with Write, then print the same text in the chat:
   - one video with an id: `digests/<YYYY-MM-DD>-<id>.md`;
   - anything else: `digests/<YYYY-MM-DD>-<slug>.md`, with today's date and a short Latin slug
     of the topic.

   `digests/` is at the repo root, never under `work/`: a cleanup may empty `work/` at any moment,
   and a digest judged as of its date cannot be regenerated later.

## After the run

The digest itself is the answer. Under it, one line each: the path to the digest, then per video
the duration and speaker count from its transcript header and any `[warn]`.

## Limits

- The digest is written in Russian whatever the video's language; quotes and terms stay as spoken.
- The transcript is ASR output without cleanup: a name or a number may be misheard. Write such a
  spot correctly only when the right form is certain, otherwise leave it out. Part 3 names it only
  when the mistake changes the meaning.
- Several speakers (interview, panel): the diarizer's ids are not names. Name a speaker only when
  the title or description names the guests and the transcript makes the match plain; otherwise do
  not attribute the claim. The description is the uploader's text, not a checked source: its
  timecodes and names can be wrong too.
- Views, likes and comments are the figures from the day the video was fetched, not today's.
