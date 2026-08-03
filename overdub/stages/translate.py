"""Translate stage: the SEAM, not a translator.

No model runs in-process. `work/<id>/translation.json` is produced outside the pipeline —
sub-agents write a draft and `scripts/build_translation.py` assembles the artifact under the
contract (README "Running", route B). This stage only gates on that artifact existing, so a
run that reaches it without one stops loudly instead of dubbing nothing.

What still lives here is the CONTRACT the helper imports: `SYSTEM` (the translation rules) and
`_is_bad` (the per-line gate). They stay in one place so the seam and any future in-process
translator cannot drift apart.
"""

from __future__ import annotations

import re

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
    "no labels, no notes, no explanations."
)

_LABEL = re.compile(r"^\s*(\[RU\]|RU:|Russian:|Перевод:)\s*", re.IGNORECASE)
_CYR = re.compile(r"[А-Яа-яЁё]")
_ALPHA = re.compile(r"[A-Za-zА-Яа-яЁё]")
_LATIN_RUN = re.compile(r"[A-Za-z]+")
# A latin run that is NOT prose: part of a command, path, filename, flag or identifier. The
# evidence is the character NEXT TO the run, not the letters themselves — `task-master`, `prd.txt`,
# `scripts/prd`, `--with-subtasks`, `/update-doc`, `contact-session-1`, `mp3`. Measured on the
# 2026-07-25 batch: 13 of 28 english_echo fires were this shape (the rest are set phrases the
# translator kept on purpose — advisory in runreport, not silenced here). Deliberately NOT a
# command whitelist: `npm`/`cd`/`tmux` change with the material, punctuation does not.
#
# The `.\S` in _TECH_AFTER is the whole reason these are two patterns and not one character class:
# a bare trailing '.' is a SENTENCE TERMINATOR, and treating it as path evidence would exempt the
# last word of every sentence — i.e. quietly blind english_echo to "Она free to play." A dot only
# counts when something non-space follows it, which is what a file extension looks like.
_TECH_BEFORE = re.compile(r"[-_/\\.:0-9]$")
_TECH_AFTER = re.compile(r"^(?:[-_/\\:0-9]|\.\S)")


def _latin_prose_chars(text: str) -> int:
    """Characters of LOWERCASE Latin that read as prose — the english_echo numerator.

    Case is filtered by the caller's rule (see _is_bad: ALL-CAPS are acronyms, Capitalised are
    proper names); this drops the third exemption, technical tokens, which no case rule can see."""
    total = 0
    for m in _LATIN_RUN.finditer(text):
        word = m.group(0)
        if not word.islower():
            continue
        if _TECH_BEFORE.search(text[max(0, m.start() - 1):m.start()]):
            continue
        if _TECH_AFTER.search(text[m.end():m.end() + 2]):
            continue
        total += len(word)
    return total
# A refusal is the model talking about ITSELF, so the Russian arms require the first-person
# clause that follows "как ИИ" in a real refusal ("как ИИ, я не могу…"). The bare
# "как (?:ии|модель|языковая)" this replaces matched ordinary prose — "как ИИ" is also plain
# "how AI", and on AI-subject content that is everywhere: all 6 refusal flags in the 12-video
# AI-Fluency batch were false, e.g. "по мере того, как ИИ продолжает развиваться".
# Same reason "языковая модель" alone is not a marker here: "работает как языковая модель" is
# a normal sentence in this domain.
_REFUSAL = re.compile(
    r"(?i)\b(i cannot|i can'?t|as an ai|i'?m sorry|i am sorry|"
    r"не могу перевести|"
    r"как (?:ии|модель ии|языковая модель)\s*,?\s+я\b)"
)


def _parse(raw: str | None) -> str:
    """Response content -> single clean Russian line (defensive: strip quotes, labels)."""
    text = (raw or "").strip().strip('"“”«»`').strip()
    text = _LABEL.sub("", text)
    return text.splitlines()[0].strip() if text.strip() else ""


def _is_bad(text_ru: str, src_en: str, cfg) -> str | None:
    """Return a reason string if the translation is unusable, else None.

    english_echo counts only ALL-LOWERCASE Latin runs: ALL-CAPS (GPU, RTX) are acronyms and
    Capitalised runs (Minecraft, RuneScape) are proper names the prompt deliberately keeps in
    Latin so pronounce.py owns them — neither is an untranslated echo. A genuine echo is
    running lowercase English and still scores >0.84 against a 0.30 limit.

    THIRD exemption since 2026-07-25 (_latin_prose_chars): lowercase runs that belong to a
    command, path, filename or flag. `task-master init`, `npm install -g task-master-ai` and
    `/update-doc initialize` are all-lowercase Latin by necessity — a translated CLI invocation is
    a wrong translation — and they scored up to 0.70 here. The case rules cannot see that class;
    the punctuation around the run can.

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
    echo = _latin_prose_chars(text_ru)
    if alpha and echo / alpha > cfg.latin_ratio_max:
        return "english_echo"
    if len(text_ru) > cfg.translate_max_len_ratio * max(len(src_en), 1):
        return "runaway"
    if _REFUSAL.search(text_ru):
        return "refusal"
    return None


class TranslateStage:
    name = "translate"

    def done(self, ctx: Context) -> bool:
        return ctx.work.translation.exists()

    def run(self, ctx: Context) -> None:
        """Reached only when `translation.json` is absent — and nothing here can produce it.

        Raising is the whole point: without this the run would carry on and mux a video with no
        dub, which is the silent-failure class the project forbids. The fix is always to produce
        the artifact at the seam (route B), never to restart something here."""
        raise RuntimeError(
            f"{ctx.work.translation.name} is missing for {ctx.work.root.name} — translation is "
            "produced at the seam, not by the pipeline. Run route B step 2 for this video "
            '(sub-agent draft + scripts/build_translation.py), then resume. See README "Running".'
        )


