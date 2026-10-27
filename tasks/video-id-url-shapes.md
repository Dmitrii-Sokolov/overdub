# `video_id` recognises every YouTube URL shape in use

## Goal + AC

`video_id` (`overdub/workdir.py`, `_YT_ID`) derives the YouTube id from every URL form YouTube
emits today, and the set is pinned by a test. AC: not frozen — fix at pickup.

## Plan

- [ ] Enumerate the URL shapes YouTube emits today (`/live/`, `/watch/`, share links with extra
  path segments, ...), add them, pin the lot with a test instead of one branch per surprise.

## State

Not started. Routed from INBOX at triage 2026-10-27.

## Findings

`_YT_ID` matches `v=`, `/shorts/`, `youtu.be/` and `/embed/` only. Observed 2026-08-14 on
`https://www.youtube.com/live/OAu3jkX8dK4`, which produced `work/6b38c4b89df/`. Consequences, in
ascending order of cost: reports and exports name the video by a hash a human cannot look up;
`_read_queue` dedupes by `video_id`, so the same video as `/live/…` and `watch?v=…` passes the
`-Unique` guard and is processed twice into two workdirs; every skill's `$ids` block derives ids
from `queue.txt` by the same rule and then addresses artifacts that are correct but unfindable by
id. yt-dlp resolves all of these fine; only the local id derivation is blind.
