# Multi-speaker violation detector

## Goal + AC

A report flag when a video breaks the single-speaker assumption (ECAPA embeddings vs the
dominant-voice centroid); full diarization stays out of scope. AC: not frozen — fix at pickup.

## Plan

- [ ] Not planned — deferred in BACKLOG.

## State

Not started. Created at triage 2026-10-27 only to hold the evidence below.

## Findings

**Source-anomaly rate on a multi-speaker panel, 2026-09-19:** `GDN3mPqJdvo` ("joining an AI doom
panel discussion oh boy"), 392 of 3171 sentences (12.4%), all 3171 scanned. By kind: garbled
211, truncated 121, dup_neighbour 53, context_contradiction 7. The missing diarization shows in
the last kind: id 136 "No" against the same speaker's "Now, yes" in id 134, id 239 "300 feet"
against "300 miles" in id 210 — turns of different speakers read as one. No corpus baseline was
computed, so 12.4% is not yet comparable to a single-voice video; `--repair-asr` is unavailable
on Parakeet, so the digest's suggested action does not exist for this engine.
