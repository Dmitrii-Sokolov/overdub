"""Silero RU TTS engine — native Russian, fixed voice, CPU, deterministic.

Loaded via torch.hub (snakers4/silero-models, cached in ~/.cache/torch/hub). Model release
is a config knob (`silero_model`): "v4_ru" (~38 MB, the long-standing default) or "v5_5_ru"
(~139 MB). Both expose the same five speakers — aidar, baya, kseniya, eugene, xenia — so a
release swap keeps every voice name valid.

v5 REJECTS Latin script (its symbol table is Cyrillic-only; Latin is silently stripped by the
model's own regex). That is safe here only because `text_tts` is Cyrillic-by-contract — the
pronounce chain transliterates every kept-Latin name before synthesis. Verified across the
12-video AI-Fluency batch: zero Latin characters in any `text_tts`. If that contract ever
loosens, v5 needs an out-of-alphabet filter; v4 tolerates the same input.

Output is written with soundfile, not torchaudio.save — torchaudio 2.11 routes save
through TorchCodec, so we sidestep that shifting backend entirely.
"""

from __future__ import annotations

import re
from pathlib import Path

import soundfile as sf
import torch

# Silero rounds break times itself; anything under this reads as no pause at all, and anything
# over it is a hole the ear hears as a dropout rather than a beat. The floor also keeps the
# markup out of units whose members were already adjacent.
MIN_BREAK_MS = 120
MAX_BREAK_MS = 2000
_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+")


def _esc(s: str) -> str:
    """XML-escape. text_tts is Cyrillic-by-contract, but a stray & or < would make the whole
    SSML string unparseable and take the unit down with it."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_ssml(text: str, gaps: list[float] | None) -> str | None:
    """`<speak>` with the unit's ORIGINAL inter-sentence pauses restored, or None to fall back
    to plain text.

    Pure and deterministic — the interesting part is when it declines. Returns None unless the
    sentence count the text splits into matches len(gaps) + 1: the joined text is rebuilt from
    the same members the gaps came from, so a mismatch means the split disagreed with the unit
    boundaries (an abbreviation ate a full stop, a member had no terminal punctuation), and
    guessing where the pause goes is worse than not placing one. Gaps below MIN_BREAK_MS are
    dropped rather than emitted as a token pause."""
    if not gaps or not text.strip():
        return None
    parts = [p for p in _SENT_SPLIT.split(text.strip()) if p]
    if len(parts) != len(gaps) + 1:
        return None
    out = [_esc(parts[0])]
    for gap, part in zip(gaps, parts[1:]):
        ms = int(round(max(0.0, gap) * 1000))
        if ms >= MIN_BREAK_MS:
            out.append(f'<break time="{min(ms, MAX_BREAK_MS)}ms"/>')
        out.append(_esc(part))
    return "<speak>" + " ".join(out) + "</speak>"


class SileroEngine:
    LANGUAGE = "ru"
    MODEL_ID = "v4_ru"               # default release; overridden per-run by cfg.silero_model
    supports_seed = False            # deterministic: same text → same audio, reseed is a no-op
    supports_target = False          # no native speed — atempo does all timing fit
    supports_breaks = True           # SSML <break>: v5 only, gated per-instance below

    def __init__(self, voice: str = "eugene", sample_rate: int = 48000, device: str = "cpu",
                 model_id: str | None = None, breaks: bool = True) -> None:
        self.voice = voice
        self.sample_rate = sample_rate
        self.model_id = model_id or self.MODEL_ID
        # v4 predates SSML in this repo's usage and was never probed with it; restricting the
        # feature to v5 keeps "reproduce an old run with v4_ru" byte-identical to what it was.
        self.breaks = breaks and self.model_id.startswith("v5")
        model, _ = torch.hub.load(
            "snakers4/silero-models", "silero_tts",
            language=self.LANGUAGE, speaker=self.model_id, trust_repo=True,
        )
        model.to(torch.device(device))
        self._model = model

    def synthesize(self, text: str, out_path: Path, *, seed: int | None = None,
                   target_sec: float | None = None, max_sec: float | None = None,
                   gaps: list[float] | None = None) -> None:
        kw = {"text": text}
        ssml = build_ssml(text, gaps) if self.breaks else None
        if ssml is not None:
            kw = {"ssml_text": ssml}
        audio = self._model.apply_tts(
            **kw,
            speaker=self.voice,
            sample_rate=self.sample_rate,
            put_accent=True,
            put_yo=True,
        )
        # explicit format="WAV": callers pass atomic temp paths (…/00007.wav.tmp) whose
        # extension soundfile cannot infer a container from, so never rely on the suffix.
        sf.write(str(out_path), audio.cpu().numpy(), self.sample_rate, format="WAV", subtype="PCM_16")

    def begin_video(self) -> None:
        pass                     # no per-video failure state to reset (no worker, no seed)

    def close(self) -> None:
        pass
