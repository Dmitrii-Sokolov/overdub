---
name: transcript
description: "Download a YouTube video and produce a plain-text transcript with paragraphs, rough timecodes and speaker labels: work/<id>/transcript.md. One command, no LLM: download (audio only) → Parakeet transcribe → diarize → render. The text stays in the video's own language and is not cleaned or translated. Trigger on '/transcript <URL>', 'расшифруй видео', 'скачай и сделай транскрипцию', 'транскрипт со спикерами', 'transcribe this video'. For filler-free readable text use overdub-clean (route E); for a dub use overdub-sonnet-batch."
---

# transcript — URL → `work/<id>/transcript.md`

Argument: a YouTube URL (several URLs: run once per URL, or put them in a queue file and use
`--batch FILE` instead of the URL).

```powershell
.venv-asr\Scripts\python.exe -X utf8 -m overdub <URL> --transcribe-only
```

Run it from the repo root. The tool is resumable: finished stages print `[skip]`, so re-running
only re-renders the file. `--force` redoes the transcribe as well.

## What comes out

`work/<id>/transcript.md`: title, a line `Duration: H:MM:SS · N speakers`, a line `channel (N subscribers) · date ·
views · likes` (each part only if the video has it), then the uploader's description verbatim
under `## Description` (it usually carries chapter timecodes and the speaker list; absent when the
video has none), then `## Transcript` with the paragraphs. The video's chapters, when it has them,
are `### title [t]` headings inside the transcript. A paragraph breaks on a
pause of 1 s or more, on 900 characters, and always on a change of speaker. With several speakers
each change opens with `**Speaker N** [t]`; with one speaker there are no labels and a `**[t]**`
timecode appears every two minutes. `N` is the diarization id (from 0), not a name.

Next to it: `sentences.json` (every sentence with `speaker`, `start`, `end`), `diar.json` (raw
speaker segments) and `source.wav`.

## After the run

Report in Russian, briefly: the path to `transcript.md`, duration, number of speakers, and any
`[warn]` the run printed (for example uncovered speech spans). Do not paste the transcript into the
chat.

## Limits

- Speaker labels are whatever the diarizer returned; nothing here checks them against the audio.
  Say so if the user relies on them.
- A video without speech gets a document that says `_No speech detected._`.
- Not a dubbing route: the language is not forced to English, and nothing is translated.
