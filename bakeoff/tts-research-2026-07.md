# TTS Engine Bake-off — Synthesis Verdict (overdub, EN→RU dubbing)

**Date:** 2026-07-16 · **Baseline to beat:** Silero v4_ru `eugene` (flat, slightly muffled) · **Quality gate:** Russian naturalness + clarity, correct ударения, no foreign accent, no hallucinations.

## Preliminary note: the candidate list contained duplicates

Three of the six "verified candidates" (entries 2, 5, 6) are the **same engine** — the ESpeech-TTS-1 family — verified by different passes. They were merged into one entry. Real distinct candidates: **ESpeech-TTS-1, Misha24-10 F5-RU, CosyVoice3, Silero v5.** Four engines, three slots — CosyVoice3 is cut (see Rejected).

A second structural fact drives the whole plan: **ranks 1 and 2 are checkpoints on the identical F5-TTS runtime.** One venv, two checkpoint downloads, one ear-test session covers both.

## Ranking

| # | Engine | RU quality evidence | Windows/12GB | Liveness | License |
|---|--------|--------------------|--------------|----------|---------|
| 1 | **ESpeech-TTS-1_RL-V2** (F5 arch, RU-native) | Raft 4.5/5 naturalness, stress correct out of the box; UTMOS 3.265 vs Silero v4's 1.76–2.14; **zero negative RU reports found** | pip, torch≥2.0, ~2–4 GB VRAM, no flash-attn | Org active 2026; TTS-1 ckpts frozen Aug 2025 | **Apache-2.0** (provenance caveat) |
| 2 | **Misha24-10/F5-TTS_RUSSIAN v2** | Raft 4.5/5 + **5/5 expressiveness** (highest tested); dominant lineage (93.7k dl/mo); BUT one independent dubbing-pipeline rejection + short-phrase truncation is the top community complaint | Same venv as #1 — checkpoint swap | Repo active (v4_winter Jan 2026) | **CC-BY-NC-4.0** — no commercial path |
| 3 | **Silero v5 (v5_5_ru, eugene)** | Raft 4/4; diffnotes #1 free RU (above CosyVoice3); direct fix for v4 stability/stress complaints — but **same timbres as v4** | Perfect — runs in existing torch 2.11 main venv, CPU-capable | Active (pip 0.5.5 Feb 2026, SAPI5 Jun 2026) | CC BY-NC — same as today |

### Why ESpeech over Misha at #1
Near-identical headline scores (both 4.5/5 naturalness; Misha +1 on expressiveness), but every tiebreaker points one way:
- **License:** Apache vs hard NC. The profile says flag-not-reject, but with equal quality the clean license wins.
- **Failure record:** targeted counter-evidence hunts found *nothing* negative on ESpeech; Misha has an on-the-record rejection by an independent film-dubbing pipeline (intermittent RU gibberish, habr 974080) — our exact use case — plus a documented short-phrase truncation habit that dubbing sentence streams will hit.
- **Stress (the stated quality gate):** ESpeech is by the RUAccent author, trained with stress markup, and the Raft review confirms correct ударения without manual effort.

Misha stays a serious contender — its 5/5 expressiveness and bigger user base are real, and the marginal cost of A/B-ing it is one 1.35 GB download into the same venv. The ear test settles it.

### Why Silero v5 at #3 (and not dropped)
It will almost certainly *not* beat the F5 finetunes on naturalness — Raft scores it below both. It's on the list because it costs ~15 minutes, needs **no new venv**, keeps determinism, and directly patches v4's stability/prosody/stress issues. It becomes the **new comparison bar** and the fallback if F5 flakiness (seed retries, truncation flags) proves too annoying across 300-sentence batches.

## Install plans (Windows 11, PowerShell)

### Shared F5 venv (serves ranks 1 AND 2)
```powershell
py -3.12 -m venv D:\code\overdub\.venv-f5tts
D:\code\overdub\.venv-f5tts\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
pip install f5-tts ruaccent soundfile huggingface_hub
ffmpeg -version   # MUST be a 7.x *shared* build on PATH — f5-tts pulls torchcodec; FFmpeg 8 breaks it (F5-TTS #1234/#1257)
```
Main venv (torch ~2.11) stays untouched. Reported pins: f5-tts wants torch≥2.0, no hard upper pin; 2.8.0+cu128 is the community-recommended combo. Python 3.12 is fine (the numpy≤1.26.4 pin only applies to py≤3.10).

### Rank 1 — ESpeech RL-V2
```powershell
hf download ESpeech/ESpeech-TTS-1_RL-V2 --local-dir D:\models\espeech-rlv2   # ~1.4 GB: .pt + vocab.txt
```
```python
import soundfile as sf
from ruaccent import RUAccent
from f5_tts.api import F5TTS

accent = RUAccent(); accent.load(omograph_model_size='turbo3.1', use_dictionary=True)
tts = F5TTS(model='F5TTS_v1_Base',
            ckpt_file=r'D:\models\espeech-rlv2\espeech_tts_rlv2.pt',
            vocab_file=r'D:\models\espeech-rlv2\vocab.txt')
text = accent.process_all('Проверка синтеза: тридцать первое декабря, замок на старой двери.')
wav, sr, _ = tts.infer(ref_file=r'D:\models\ru_ref.wav',
                       ref_text='точная расшифровка референс-клипа',
                       gen_text=text, seed=42)
sf.write('out_espeech.wav', wav, sr)   # 24 kHz; soundfile, NOT torchaudio.save (TorchCodec landmine)
```
Requires one clean 5–12 s RU narrator clip + its **exact** transcript — this clip *is* the narrator voice; budget an iteration cycle picking it.

### Rank 2 — Misha24-10 v2 (checkpoint swap in the same venv)
```powershell
hf download Misha24-10/F5-TTS_RUSSIAN "F5TTS_v1_Base_v2/model_last_inference.safetensors" "vocab.txt" --local-dir D:\models\misha-f5-ru
# NEVER mirror the repo — it is 48.5 GB total. Verify exact tree paths first.
```
Same Python call with `ckpt_file=...model_last_inference.safetensors`. RUAccent pre-pass is **mandatory** (v2/v4 trained with full stress markup — unaccented input underuses the model). Optionally grab `F5TTS_v1_Base_v4_winter/model_58000.pt` for the contested v2-vs-v4 A/B (default v2).

### Rank 3 — Silero v5 (main venv, 15 min)
```powershell
pip install silero omegaconf   # pip 0.5.5 may predate v5_5_ru — torch.hub from master is the reliable path
```
```python
import torch, soundfile as sf
model, _ = torch.hub.load('snakers4/silero-models', 'silero_tts',
                          language='ru', speaker='v5_5_ru', trust_repo=True)
audio = model.apply_tts(text='Проверка синтеза: тридцать первое декабря, замок на старой двери.',
                        speaker='eugene', sample_rate=48000, put_accent=True, put_yo=True)
sf.write('out_silero_v5.wav', audio.numpy(), 48000)
```
v5 RU models **reject Latin script** — text_tts must stay Cyrillic-only, and the adapter should filter out-of-alphabet chars (#317 crash class).

## Pipeline integration deltas (both F5 engines)
- **Normalizer:** strip `+` stress marks in the ASR-verification normalizer on **both** sides (RUAccent inserts them into text_tts).
- **Sentence length:** merge very short (1–4 word) sentences upstream — F5-architecture truncation is the documented failure class; expect elevated ASR-verify flag rates there and treat them as the known loss class.
- **Sample rate:** F5 outputs 24 kHz (Vocos) — resample at assembly; Silero stays 48 kHz.
- **Seed:** `infer(seed=N)` is real reseed-retry material for F5 (unlike Silero, where retries stay a no-op).
- **VRAM:** 2–4 GB engine + 0.5 GB whisper-small — nowhere near the 12 GB ceiling.

## What ONLY the ear test can decide
1. **ESpeech checkpoint choice** — RL-V2 vs RL-V1 vs SFT-95K: reviewers are genuinely split.
2. **ESpeech vs Misha head-to-head** with the same reference clip — no published comparison exists anywhere.
3. **Misha v2 vs v4_winter** — author lukewarm, heavy user says v4 is significantly worse, Raft liked v4.
4. **Whether the habr-974080 gibberish rejection reproduces** on a proper setup (RUAccent + v2 + fixed narrator) — a hard gate, not a formality.
5. **Reference-clip selection** — narrator timbre and much of the output quality ride on it.
6. **Silero v5: is the problem v4's artifacts or eugene's timbre?** Same voices — only ears answer this.
7. **Real per-segment failure/retry rates** on a genuine ~300-sentence batch — reviews measure clips, not batches; the pipeline's ASR gate is the only instrument that measures this.

Zero-install pre-screen: HF Spaces `Den4ikAI/ESpeech-TTS` (live) lets you A/B ESpeech against the current baseline before building anything.

## First install: **ESpeech-TTS-1_RL-V2** (via the shared `.venv-f5tts`)
One venv build covers ranks 1 and 2. Sequence: (1) build `.venv-f5tts` + ESpeech RL-V2, (2) add Misha v2 checkpoint, (3) bump Silero to v5 in the main venv (15-min side-quest, no venv work), (4) run one ear-test session: same 10–15 sentences (include homographs like за́мок/замо́к, several 2–3-word phrases, one long sentence) across ESpeech RL-V2/RL-V1/SFT-95K, Misha v2, Silero v5, and the current v4 baseline.

## Rejected at synthesis: CosyVoice3
Fourth viable candidate, cut on all four weighting axes relative to the shortlist: unresolved multi-user RU→Chinese failure (issue #1790, 'user error' framing refuted on verify — systematic per environment, reseed-retry can't recover it); worst Windows install story (1 native success vs 2 abandonments; all RTF numbers measured under WSL); a July 2026 RU roundup rates its Russian below Silero v5; license disclaimer contradicts its Apache tag. It solves nothing the F5 finetunes don't solve better here. Sweep rejects stand as recorded (Fish/OpenAudio, Higgs, IndexTTS2, CosyVoice2, XTTS, ZONOS2, Kokoro, etc. — no credible RU or direct negative RU ear tests). **Piper irina** remains the 30-minute deterministic CPU fallback of last resort; recheck Sber/big-vendor open RU TTS in ~6 months.