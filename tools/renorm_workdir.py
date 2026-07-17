"""Renormalize a copied workdir with the CURRENT normalizer (A/B tool for pronunciation work).

Copies SRC -> DST (REFUSES if DST exists; SRC is opened read-only) and rewrites
translation.json with text_tts = normalize_for_tts(text_ru). Only the source.* artifacts
are hardlinked — their stages are done()-gated and never rewrite an existing file.
segments/*.wav are COPIED, never hardlinked: synthesize has in-place error/empty-unit
writes (sf.write straight to the final wav path, bypassing .tmp + os.replace) that would
truncate a shared inode and corrupt the READ-ONLY source corpus. Downstream artifacts
(report.json, translation.jsonl, dub_ru.wav, srt, output*.mkv) are NOT carried over —
their done() gates fail and the next pipeline run self-heals verify -> assemble -> mux,
while synthesize re-renders exactly the units whose text_tts changed (the manifest reuse
gate compares text_tts).

Run: .venv-asr/Scripts/python.exe -X utf8 tools/renorm_workdir.py SRC_WORKDIR DST_WORKDIR
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import pronounce  # noqa: E402
from overdub.normalize import normalize_for_tts  # noqa: E402

_BIG = ["source.mkv", "source.wav", "source_bed.wav"]
# both yt-dlp sidecar name variants (mkv merge path vs single-format /b fallback)
_SMALL = ["source.info.json", "source.mkv.info.json", "words.json", "sentences.json"]


def _link(src: Path, dst: Path) -> None:
    try:
        os.link(src, dst)                      # same-volume: free
    except OSError:
        shutil.copy2(src, dst)                 # cross-volume / FS without hardlinks


def _write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    if not (src / "translation.json").exists():
        print(f"error: {src} is not a workdir (no translation.json)", file=sys.stderr)
        return 2
    if dst.exists():
        print(f"error: {dst} already exists — refusing to touch it", file=sys.stderr)
        return 2

    (dst / "segments").mkdir(parents=True)
    for name in _BIG:
        if (src / name).exists():
            _link(src / name, dst / name)
    for wav in sorted((src / "segments").glob("*.wav")):
        shutil.copy2(wav, dst / "segments" / wav.name)   # NEVER _link: see docstring
    for name in _SMALL:
        if (src / name).exists():
            shutil.copy2(src / name, dst / name)
    if (src / "segments" / "manifest.json").exists():
        shutil.copy2(src / "segments" / "manifest.json", dst / "segments" / "manifest.json")

    records = json.loads((src / "translation.json").read_text(encoding="utf-8"))
    out, changed = [], []
    for r in records:
        new_tts = normalize_for_tts(r["text_ru"])
        if new_tts != r.get("text_tts"):
            changed.append(r["id"])
        out.append({**r, "text_tts": new_tts})
    _write_json(dst / "translation.json", out)
    _write_json(dst / "pronounce_audit.json", pronounce.audit_summary(dst.name, out))

    print(f"{len(out)} records → {dst / 'translation.json'} ({len(changed)} text_tts changed)")
    if changed:
        print("changed ids:", " ".join(str(i) for i in changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
