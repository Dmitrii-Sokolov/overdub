"""Which palette voice speaks for which speaker of a video.

Per voice pool, the main participants of a video take the first k voices of that pool's palette,
one-to-one, so that the sum of squared timbre differences speaker ↔ voice is minimal. Timbre is
(log median F0, log formant spacing ΔF), each divided by its spread over the pool's palette
voices: a constant, so a speaker's voice depends on their own timbre and on nothing else in the
video — the same person recurring across a series keeps the same voice. Nothing is weighted by
speech time for the same reason.

Inserts (speakers under MAIN_SHARE of the words: a news clip, a quoted guest) are other people
too: they take the voices after the participants', matched the same way, and once the palette is
exhausted each speaks in the voice of the main participant closest to them in timbre. A speaker
with no measurable timbre goes to the male pool and takes the next free voice.
"""

from __future__ import annotations

import itertools
import math


def _features(f0: float, df: float) -> tuple[float, float]:
    return math.log(f0), math.log(df)


def _scale(points: list[tuple[float, float]]) -> tuple[float, float]:
    out = []
    for axis in zip(*points):
        mean = sum(axis) / len(axis)
        sd = math.sqrt(sum((x - mean) ** 2 for x in axis) / len(axis))
        out.append(sd if sd > 0 else 1.0)
    return out[0], out[1]


def _dist2(a, b, scale) -> float:
    return sum(((x - y) / s) ** 2 for x, y, s in zip(a, b, scale))


def _match(people: list[dict], voices: list[str], feat: dict, timbre: dict, scale) -> dict:
    """One-to-one, len(people) == len(voices), minimal sum of squared distances; ties keep the
    first permutation in palette order, so the result is deterministic."""
    best, best_cost = None, math.inf
    for perm in itertools.permutations(voices):
        cost = sum(_dist2(feat[p["speaker"]], timbre[v], scale) for p, v in zip(people, perm))
        if cost < best_cost - 1e-12:
            best, best_cost = perm, cost
    return {p["speaker"]: v for p, v in zip(people, best or ())}


def assign_voices(speakers: list[dict], palettes: dict[str, list[str]],
                  timbre: dict[str, tuple[float, float]]) -> dict[int, str]:
    """{speaker: voice} for every entry of a diar.json `speakers_info`."""
    out: dict[int, str] = {}
    for pool, names in palettes.items():
        members = [s for s in speakers if (s.get("pool") or "male") == pool]
        measured = [s for s in members if s.get("f0_hz") and s.get("delta_f_hz")]
        voice_feat = {v: _features(*timbre[v]) for v in names}
        scale = _scale(list(voice_feat.values()))
        feat = {s["speaker"]: _features(s["f0_hz"], s["delta_f_hz"]) for s in measured}
        free = list(names)
        for group in ([s for s in measured if s.get("main", True)],
                      [s for s in measured if not s.get("main", True)]):
            # more people than voices left: the most-spoken get a voice of their own
            fit = sorted(group, key=lambda s: (-s["words"], s["speaker"]))[:len(free)]
            out.update(_match(fit, free[:len(fit)], feat, voice_feat, scale))
            free = free[len(fit):]
        mains = [s for s in measured if s.get("main", True) and s["speaker"] in out]
        for s in measured:
            if s["speaker"] not in out:              # the palette ran out
                ref = mains or [m for m in measured if m["speaker"] in out]
                near = min(ref, key=lambda m: (_dist2(feat[s["speaker"]], feat[m["speaker"]],
                                                      scale), m["speaker"]))
                out[s["speaker"]] = out[near["speaker"]]
        for s in sorted((s for s in members if s not in measured), key=lambda s: s["speaker"]):
            out[s["speaker"]] = free.pop(0) if free else names[0]
    return out
