"""Verify stage: whisper-small round-trip of every render unit on raw (unsped) audio.

Units come FROM THE MANIFEST (the record of what was actually rendered; legacy per-sentence
manifests adapt as singleton units), but the reference text is joined from the CURRENT
translation.json member sentences — never from the manifest — so a stale unit wav rendered
from an older translation self-flags as low_similarity instead of silently passing against
the artifact under test (the stale-translation safety net).

One ASR round-trip per unit (asr.roundtrip_similarity — shared with synthesize's reseed
loop), fanned out to a report record per SENTENCE id (never-drop): members carry group_id
(= the unit's first id) and the unit's similarity/flag; the hypothesis lands on the leader
only. verify never re-synthesizes — it is the pure, independent judge.

done(): the report marker must exist AND its stamped synth_key must match the manifest's —
a resynthesis under a new key auto-invalidates verification (self-healing re-verify) instead
of silently shipping a stale report over new wavs.
"""

from __future__ import annotations

import json
import sys

import soundfile as sf

from .. import completeness, report
from ..asr import roundtrip_similarity
from ..normalize import normalize_for_compare
from ..pipeline import Context
from .synthesize import unit_sim_threshold, units_of


def _frames(wav) -> int:
    try:
        return sf.info(str(wav)).frames
    except Exception:
        return 0


class VerifyStage:
    name = "verify"

    def done(self, ctx: Context) -> bool:
        p = ctx.work.report
        if not p.exists():
            return False
        try:
            rep = json.loads(p.read_text(encoding="utf-8"))
            marker = rep.get("verify")
            if not marker:
                return False
            man = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
            # absent stamp counts as mismatch: a legacy report must re-verify ONCE (writing
            # the stamp), or the transition itself becomes the silent-staleness hole.
            # units_key catches SAME-synth_key resynthesis (--force) — content, not config.
            if (marker.get("synth_key") != man.get("synth_key")
                    or marker.get("units_key") != man.get("units_key")):
                print("       [info] verify: manifest synth/units key changed — re-verifying",
                      file=sys.stderr)
                return False
            return True
        except Exception:
            return False                                   # torn report/manifest → re-run

    def run(self, ctx: Context) -> None:
        cfg = ctx.cfg
        segs = json.loads(ctx.work.translation.read_text(encoding="utf-8"))
        if [s["id"] for s in segs] != list(range(len(segs))):
            raise RuntimeError("translation ids not contiguous (verify never-drop)")
        if not ctx.work.seg_manifest.exists():
            raise RuntimeError("segments/manifest.json missing — run synthesize before verify")
        man = json.loads(ctx.work.seg_manifest.read_text(encoding="utf-8"))
        units = units_of(man)
        if sorted(i for u in units for i in u["ids"]) != list(range(len(segs))):
            raise RuntimeError("manifest units do not cover translation ids (verify never-drop)")

        # session-owned: one whisper-small load per stage SWEEP. Inside a stage the session
        # also dedupes it against synthesize's reseed verifier when both run in the same
        # sweep — across stages it is loaded once per sweep, released at each sweep's end.
        model = ctx.session.whisper(cfg, cfg.verify_model, role="verify")
        rep = report.load(ctx.work.report)                 # preserve any assemble fields
        n_flag = n_retried = n_repaired = 0
        for u in units:
            lead = u["ids"][0]
            wav = ctx.work.seg_wav(lead)
            # reference from CURRENT translation — the stale-translation net
            ref = normalize_for_compare(" ".join(
                (segs[i].get("text_tts") or "").strip() for i in u["ids"]).strip())
            sim: float | None = None
            vflag: str | None = None
            hyp = ""

            if not ref:
                vflag = "empty_ref"
            elif not wav.exists() or _frames(wav) == 0:
                vflag = "missing_wav"
            else:
                try:
                    sim, hyp, hyp_n = roundtrip_similarity(model, wav, ref, cfg.target_lang)
                except Exception as e:
                    vflag = "unreadable_wav"
                    print(f"       [flag] u{lead}: unreadable_wav {e}", file=sys.stderr)
                else:
                    if not hyp_n:
                        vflag = "empty_hyp"
                    else:                                  # compressed units → stricter gate
                        need_sim = unit_sim_threshold(cfg, u.get("speed"))
                        vflag = None if sim >= need_sim else "low_similarity"

            attempts = u.get("attempts") or 0
            if attempts > 1:
                n_retried += 1
                if vflag is None:
                    n_repaired += 1
            for sid in u["ids"]:
                report.upsert(
                    rep, sid, status=segs[sid]["status"], translate_flag=segs[sid].get("flag"),
                    group_id=lead,
                    similarity=(round(sim, 4) if sim is not None else None),
                    verify_flag=vflag, hypothesis=(hyp if sid == lead else None),
                    tts_seed=u.get("seed"), tts_attempts=(attempts or None),
                    tts_speed=u.get("speed"), synth_sim=u.get("synth_sim"),
                )
            if vflag:
                n_flag += 1
                tail = "" if sim is None else f" ({sim:.2f})"
                print(f"       [flag] u{lead} (ids {u['ids']}): {vflag}{tail}", file=sys.stderr)

        report.prune(rep, {s["id"] for s in segs})
        rep["video_id"] = ctx.work.root.name
        rep["similarity_threshold"] = cfg.similarity_threshold
        rep["similarity_threshold_compressed"] = cfg.similarity_threshold_compressed
        rep["verify"] = {"model": cfg.verify_model, "synth_key": man.get("synth_key"),
                         "units_key": man.get("units_key"),
                         "n_units": len(units), "n_segments": len(segs), "n_flagged": n_flag,
                         "n_retried": n_retried, "n_repaired": n_repaired}

        # Completeness: a pure src_en<->text_ru text comparison (no audio, no model, no unit
        # grouping) — a SEPARATE loop over sentences, run here on the CPU; the whisper model
        # is released by the session at the end of the stage sweep, not here. One
        # cross-sentence pass (duplicate_adjacent) runs before the loop on
        # the EN source: src_en is copied verbatim from sentences.json by both translate routes
        # (translate.py / build_translation.py, which also key their resume on that equality),
        # so the ASR-defect check reads the source text without a second file read.
        # Non-blocking triage flags only; never gates the pipeline. Written
        # UNCONDITIONALLY per sentence (None/[] when clean) so a re-run after a translation fix
        # overwrites stale flags — the same stale-clearing discipline the unit loop uses above.
        n_num = n_neg = n_ent = n_len = n_dup = n_rate = n_comp_flag = 0
        src_texts = [s.get("src_en") or "" for s in segs]
        dups = completeness.duplicate_adjacent(src_texts)
        rates = completeness.implausible_rate(
            src_texts, [(s.get("end") or 0) - (s.get("start") or 0) for s in segs])
        for s in segs:
            c = completeness.check(s.get("src_en") or "", s.get("text_ru") or "", cfg)
            fl = c["flags"]
            twin = dups.get(s["id"])
            if twin is not None:
                fl.append("dup_adjacent")
            cps = rates.get(s["id"])
            if cps is not None:
                fl.append("rate_implausible")
            report.upsert(
                rep, s["id"],
                completeness_flags=fl,
                completeness_len_ratio=c["length_ratio"],
                completeness_missing_numbers=(c["missing_numbers"] or None),
                completeness_missing_entities=(c["missing_entities"] or None),
                completeness_negation_lost=(True if c["negation_lost"] else None),
                completeness_duplicate_of=twin,
                completeness_chars_per_sec=cps,
            )
            if fl:
                n_comp_flag += 1
            n_num += "num_loss" in fl
            n_neg += "neg_loss" in fl
            n_ent += "entity_loss" in fl
            n_len += "length_short" in fl
            n_dup += "dup_adjacent" in fl
            n_rate += "rate_implausible" in fl
        rep["completeness"] = {"len_ratio_min": cfg.completeness_len_ratio_min,
                               "n_sentences": len(segs), "n_flagged": n_comp_flag,
                               "n_num_loss": n_num, "n_neg_loss": n_neg,
                               "n_entity_loss": n_ent, "n_length": n_len,
                               "n_dup_adjacent": n_dup, "n_rate_implausible": n_rate}

        report.save(ctx.work.report, rep)
        print(f"       {len(units)} units / {len(segs)} sentences verified "
              f"({n_flag} flagged, {n_retried} retried, {n_repaired} repaired)")
        print(f"       {len(segs)} sentences completeness-checked "
              f"({n_comp_flag} flagged: num {n_num}, neg {n_neg}, ent {n_ent}, len {n_len}, "
              f"dup {n_dup}, rate {n_rate})")
