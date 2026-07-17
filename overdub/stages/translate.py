"""Translate stage (Phase 1): Qwen3-14B via Ollama, context-aware per sentence.

Design: the translate-stage-design workflow (3-approach panel + lens judges + synthesis),
see DECISIONS. One LLM call per sentence, in id order — NO batching (batching risks a silent
sentence merge/drop, the one failure this pipeline forbids). The LLM returns ONLY natural
spoken Russian (text_ru); text_tts is derived by the deterministic Python normalizer that the
verify stage also imports, so the round-trip comparison is exact by construction.

Endpoint: the NATIVE Ollama /api/chat with `think: false` — NOT the OpenAI /v1 path. Empirically,
qwen3:14b ignores an in-prompt `/no_think` on many samples and its reasoning is truncated by
num_predict, leaving message.content EMPTY; the native `think: false` toggle reliably disables
thinking (~3x faster, no wasted reasoning tokens). See DECISIONS.

Robustness: validate every output -> reseed-retry with a temperature bump -> flagged English
fallback, never a dropped or blanked slot. Progress is appended per sentence to translation.jsonl
(flush+fsync) so an overnight run resumes after a crash; translation.json is written atomically
once every id is present. Only status=="ok" pairs feed the rolling context (a failed English
fallback never poisons the next sentence).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

from .. import pronounce
from ..normalize import normalize_for_tts
from ..pipeline import Context

SYSTEM = (
    "You are a professional dubbing translator. You translate English speech into natural, "
    "spoken Russian for a single-narrator voice-over dub.\n\n"
    "Rules:\n"
    "- Translate ONLY the one English sentence marked SENTENCE into Russian.\n"
    "- This is dubbing. The Russian must sound natural said aloud and stay CLOSE IN LENGTH to "
    "the English so it fits the same on-screen time slot. Do not pad and do not over-compress.\n"
    "- Use the CONTEXT block (earlier sentences and their Russian translations) only to keep "
    "terminology, names and pronouns consistent. Never translate the CONTEXT. Never continue "
    "past SENTENCE.\n"
    "- Preserve meaning, tone and register. Write common acronyms the way they are normally "
    "written in Russian.\n"
    "- Keep every proper NAME of a game, brand, platform or company in LATIN script, "
    "capitalised the standard way, even when the English source is lowercase "
    "(runescape -> RuneScape, minecraft -> Minecraft). Never respell such a name in Cyrillic — "
    "pronunciation is handled later by a dedicated step. Personal names may be written the "
    "usual Russian way.\n"
    '- Keep numbers as digits (e.g. "4080", "50%", "24/7"). Do NOT spell numbers out in words '
    "— that is handled later.\n"
    "- Output ONLY the Russian translation of SENTENCE — a single line. No quotes, no English, "
    "no labels, no notes, no explanations.\n"
    "/no_think"          # weak fallback; the load-bearing switch is native think:false in _chat
)

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_LABEL = re.compile(r"^\s*(\[RU\]|RU:|Russian:|Перевод:)\s*", re.IGNORECASE)
_CYR = re.compile(r"[А-Яа-яЁё]")
_ALPHA = re.compile(r"[A-Za-zА-Яа-яЁё]")
_LATIN_RUN = re.compile(r"[A-Za-z]+")
_REFUSAL = re.compile(
    r"(?i)\b(i cannot|i can'?t|as an ai|i'?m sorry|i am sorry|"
    r"не могу перевести|как (?:ии|модель|языковая))\b"
)


def _parse(raw: str | None) -> str:
    """Response content -> single clean Russian line (defensive: strip think-tags, quotes, labels)."""
    text = _THINK.sub("", raw or "").strip().strip('"“”«»`').strip()
    text = _LABEL.sub("", text)
    return text.splitlines()[0].strip() if text.strip() else ""


def _is_bad(text_ru: str, src_en: str, cfg) -> str | None:
    """Return a reason string if the translation is unusable, else None.

    english_echo counts only ALL-LOWERCASE Latin runs: ALL-CAPS (GPU, RTX) are acronyms and
    Capitalised runs (Minecraft, RuneScape) are proper names the prompt deliberately keeps in
    Latin so pronounce.py owns them — neither is an untranslated echo. A genuine echo is
    running lowercase English and still scores >0.84 against a 0.30 limit.

    no_cyrillic is gated the same way: under the Latin-name mandate a names-only line
    ("Minecraft, Valheim, No Man's Sky") carries no Cyrillic yet is a valid translation the
    pronounce chain voices — accept it when normalize_for_tts yields Cyrillic. A lowercase
    English echo also transliterates to Cyrillic here but is caught by english_echo below; only
    pure punctuation/garbage stays Cyrillic-free after normalization.
    """
    if not text_ru:
        return "empty"
    if not _CYR.search(text_ru) and not _CYR.search(normalize_for_tts(text_ru)):
        return "no_cyrillic"
    alpha = len(_ALPHA.findall(text_ru))
    echo = sum(len(w) for w in _LATIN_RUN.findall(text_ru) if w.islower())
    if alpha and echo / alpha > cfg.latin_ratio_max:
        return "english_echo"
    if len(text_ru) > cfg.translate_max_len_ratio * max(len(src_en), 1):
        return "runaway"
    if _REFUSAL.search(text_ru):
        return "refusal"
    return None


def _build_user(target_en: str, pairs: list[tuple[str, str]], char_cap: int) -> str:
    """Inlined CONTEXT block (oldest pairs dropped past char_cap) + the target SENTENCE."""
    def block(ps: list[tuple[str, str]]) -> str:
        if not ps:
            return ""
        lines = ["CONTEXT (do not translate; most recent last):"]
        for en, ru in ps:
            lines += [f"[EN] {en}", f"[RU] {ru}"]
        return "\n".join(lines) + "\n\n"

    ps = list(pairs)
    while ps and len(block(ps)) > char_cap:
        ps.pop(0)
    return block(ps) + f"SENTENCE:\n{target_en}"


def _chat(root: str, cfg, user: str, temperature: float, seed: int) -> str:
    """One native Ollama /api/chat turn with thinking disabled. Returns message.content (may raise)."""
    body = json.dumps({
        "model": cfg.ollama_model,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": user}],
        "think": False,                      # load-bearing: reliably suppresses qwen3 reasoning
        "stream": False,
        "options": {
            "num_ctx": cfg.num_ctx,          # Ollama preallocates KV for the FULL num_ctx
            "temperature": temperature,
            "top_p": cfg.translate_top_p,
            "seed": seed,
            "num_predict": cfg.translate_max_tokens,
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        root + "/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=cfg.ollama_timeout_s) as r:
        data = json.loads(r.read().decode("utf-8"))
    return (data.get("message") or {}).get("content", "")


def _translate_one(root: str, cfg, user: str, src_en: str) -> tuple[str, str, int, str | None]:
    """(text_ru, status, attempts, flag). Retries reseed + bump temperature; never raises."""
    best, flag, attempts = "", None, 0
    for attempt in range(cfg.translate_max_retries + 1):
        attempts = attempt + 1
        try:
            content = _chat(root, cfg, user,
                            temperature=min(0.6, cfg.translate_temperature + 0.1 * attempt),
                            seed=cfg.translate_seed + attempt)
            text_ru = _parse(content)
        except Exception as e:                       # timeout / connection drop = a failed attempt
            flag = "api_error"
            print(f"       [warn] api error (attempt {attempts}): {e}", file=sys.stderr)
            continue
        if text_ru and _CYR.search(text_ru):
            best = text_ru                           # keep the most recent Russian-ish candidate
        reason = _is_bad(text_ru, src_en, cfg)
        if reason is None:
            return text_ru, "ok", attempts, None
        flag = reason
    return (best or src_en), "failed", attempts, (flag or "unknown")


def _root(base_url: str) -> str:
    """Native Ollama root (tolerates a legacy '/v1' suffix in the configured base_url)."""
    return base_url.rsplit("/v1", 1)[0].rstrip("/")


def _preflight(root: str, model: str) -> None:
    try:
        with urllib.request.urlopen(root + "/api/tags", timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(
            f"Ollama not reachable at {root} — start the daemon (ollama serve). ({e})"
        ) from e
    names = {m.get("name", "") for m in data.get("models", [])}
    if not any(n == model or n.startswith(model + ":") or n.split(":")[0] == model for n in names):
        raise RuntimeError(
            f"Ollama model '{model}' not found. Available: {sorted(names)}. "
            f"Pull it first: ollama pull {model}"
        )


def _unload(root: str, model: str) -> None:
    """Best-effort keep_alive:0 so Qwen frees VRAM before the whisper-large-contending stages."""
    try:
        body = json.dumps({"model": model, "messages": [], "keep_alive": 0}).encode("utf-8")
        req = urllib.request.Request(
            root + "/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=15).read()
    except Exception:
        pass


class TranslateStage:
    name = "translate"

    def done(self, ctx: Context) -> bool:
        return ctx.work.translation.exists()

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        sentences = json.loads(ctx.work.sentences.read_text(encoding="utf-8"))
        root = _root(cfg.ollama_base_url)
        _preflight(root, cfg.ollama_model)

        # resume: reload any already-finished sentences from the append-only trail
        partial = ctx.work.translation_partial
        done: dict[int, dict] = {}
        if partial.exists():
            for line in partial.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    done[obj["id"]] = obj
                except (json.JSONDecodeError, KeyError):
                    continue  # tolerate a torn last line from a crash mid-write

        window: list[tuple[str, str]] = []      # rolling context of ok (en, ru) pairs
        try:
            with partial.open("a", encoding="utf-8") as pf:
                for s in sentences:
                    sid = s["id"]
                    if sid in done and done[sid].get("src_en") == s["text"]:  # done for THIS source
                        # timings follow the CURRENT sentence: a re-transcribe (e.g. the ultra-short
                        # merge) can shift start/end at an id whose text happens to match
                        done[sid] = obj = {**done[sid], "start": s["start"], "end": s["end"]}
                        if obj.get("status") == "ok":                 # resume: skip, keep context
                            window = (window + [(s["text"], obj["text_ru"])])[-cfg.context_window:]
                        continue                                      # source changed -> re-translate
                    user = _build_user(s["text"], window[-cfg.context_window:],
                                       cfg.translate_context_char_cap)
                    text_ru, status, attempts, flag = _translate_one(root, cfg, user, s["text"])
                    obj = {
                        "id": sid, "start": s["start"], "end": s["end"], "src_en": s["text"],
                        "text_ru": text_ru, "text_tts": normalize_for_tts(text_ru),
                        "status": status, "attempts": attempts,
                    }
                    if flag:
                        obj["flag"] = flag
                    pf.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    pf.flush()
                    os.fsync(pf.fileno())
                    done[sid] = obj
                    if status == "ok":
                        window = (window + [(s["text"], text_ru)])[-cfg.context_window:]
                    else:
                        print(f"       [flag] id{sid}: {flag}", file=sys.stderr)
        finally:
            if cfg.translate_unload:
                _unload(root, cfg.ollama_model)

        # finalize: enforce the contract (raise, not assert — a never-drop invariant must not be
        # stripped under `python -O`), then atomic write
        out = [done[s["id"]] for s in sentences]
        ids = [o["id"] for o in out]
        if ids != list(range(len(sentences))):
            raise RuntimeError(f"translation ids not contiguous (never-drop invariant): {ids}")
        tmp = ctx.work.translation.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, ctx.work.translation)

        # pronounce audit (AUDIT-ONLY artifact — written, never read back: resolution must
        # stay pure/deterministic or verify's two sides desync): what the pipeline invented
        # for Latin tokens — operator triage + weekly dictionary-seeding material
        audit = pronounce.audit_summary(ctx.work.root.name, out)
        atmp = ctx.work.pronounce_audit.with_suffix(".json.tmp")
        atmp.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(atmp, ctx.work.pronounce_audit)

        n_fail = sum(1 for o in out if o.get("status") != "ok")
        print(f"       {len(out)} sentences → translation.json ({n_fail} flagged)")
