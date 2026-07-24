"""Unit tests for the ASR decode-config plumbing (roles, beam, provenance) — 2026-07-22.

Run: .venv-asr/Scripts/python.exe -X utf8 tests/test_asr_config.py   (or via pytest)
No GPU, no whisper, no media, no network: every model is a fake that records the kwargs it
was called with, and load_whisper itself is monkeypatched out.

Guards the failure classes the "Transcribe speed" experiment can only fail SILENTLY:

  * THE INSTRUMENT MOVES WITH THE THING IT MEASURES. Flipping the transcriber to int8_float16
    used to drag whisper-small along (one cfg key fed both roles), so every round-trip
    similarity score and every flag count moved too and the experiment would read its own
    measurement error as a result.
  * TWO ROLES SHARE ONE LOADED MODEL WHEN THEY MUST NOT. The session cache used to key on
    (model, device) alone; two roles differing only in compute type — or one instance warmed at
    beam 5 handed to a beam-1 decode — would be one build wearing two labels, i.e. an A/B that
    compared a thing to itself.
  * THE TWO CONSUMERS OF transcribe_words DRIFT. The stage and --repair-asr share one body on
    purpose; a beam that moved in one and not the other splices a sentence of a different KIND
    into the transcript, and no test that stops at the stage would ever see it.
  * A DECODE-CONFIG CHANGE LANDS AS A NO-OP. Transcribe has no invalidation machinery, so a
    changed beam on an existing workdir prints [skip] and the operator believes a beam-1 run
    happened; forced, it pairs a NEW transcript with the OLD translation.json and nothing
    downstream can detect that. Both paths are covered: done() guards the unforced one, and
    --force skips done() entirely, so TranscribeStage._refuse_mixed_rewrite guards the other.
    --repair-asr runs no stage at all, so it checks the key itself before spending GPU time.
  * THE STAMP RECORDS AN INTENT INSTEAD OF WHAT DECODED. _guard re-runs at cond=False and keeps
    the retry when it halves the floor ratio, so a key built from the config alone would let two
    workdirs share one string over materially different transcripts — corroding the sweep the
    key exists to protect. Recording (asr_key) and refusing (asr_key_core) are separate jobs.
  * THE SHIPPED overdub.toml QUIETLY STOPS MEANING TODAY'S DEFAULTS. Every number the corpus
    was measured at is conditional on that file resolving to large-v3/float16/beam 5/cond True.
"""

from __future__ import annotations

import contextlib
import inspect
import io
import json
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from overdub import asr, repair, runreport  # noqa: E402
from overdub.asr import (VERIFY_BEAM_SIZE, asr_key, asr_key_core,  # noqa: E402
                         load_whisper, roundtrip_similarity)
from overdub.config import Config  # noqa: E402
from overdub.pipeline import Context, Session  # noqa: E402
from overdub.stages.synthesize import SynthesizeStage  # noqa: E402
from overdub.stages.transcribe import MIN_WORD_DUR, TranscribeStage, transcribe_words  # noqa: E402
from overdub.stages.verify import VerifyStage  # noqa: E402
from overdub.workdir import WorkDir  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]
VID = "vid00000001"                              # 11 chars, like a real youtube id
URL = f"https://youtu.be/{VID}"


# --- fakes ---------------------------------------------------------------------------
class FakeModel:
    """Stands in for a WhisperModel: records every transcribe() kwarg, decodes nothing."""

    def __init__(self, tag: str = "m") -> None:
        self.tag = tag
        self.calls: list[dict] = []

    def transcribe(self, *args, **kw):
        self.calls.append(kw)
        return ([], None)


class _Loader:
    """Recorder for overdub.asr.load_whisper. Hands back a DISTINCT object per call so a test
    can tell a cache hit from a second load by identity alone."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, model, device="cuda", compute_type="float16", *, beam_size=5,
                 num_workers=1):
        self.calls.append((model, device, compute_type, beam_size, num_workers))
        return FakeModel(f"{model}/{compute_type}/beam{beam_size}")


@contextlib.contextmanager
def _patched_loader():
    """asr.load_whisper is imported INSIDE Session.whisper, so the module attribute is what the
    call site resolves — patching it here is what makes the session testable without a GPU."""
    rec = _Loader()
    original = asr.load_whisper
    asr.load_whisper = rec
    try:
        yield rec
    finally:
        asr.load_whisper = original


def _quiet(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


def _work(tmp: Path) -> WorkDir:
    work = WorkDir(root=tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    return work


def _ctx(work: WorkDir, cfg: Config | None = None) -> Context:
    cfg = Config() if cfg is None else cfg
    cfg.work_root = work.root.parent
    return Context(url=URL, cfg=cfg, work=work)


# --- 1. defaults ----------------------------------------------------------------------

def test_defaults_resolve_both_roles_to_todays_values() -> None:
    # The split must be a NO-OP at defaults, or every measured number in the corpus (RTF 0.087,
    # the repair-fixture baseline, the similarity distribution) silently describes another build.
    cfg = Config()
    assert cfg.whisper_beam_size == 5, cfg.whisper_beam_size
    assert cfg.whisper_compute_type == "float16", cfg.whisper_compute_type
    assert cfg.verify_compute_type == "float16", cfg.verify_compute_type
    assert cfg.compute_type_for("transcribe") == "float16"
    assert cfg.compute_type_for("verify") == "float16"


def test_verify_beam_is_a_constant_not_a_config_key() -> None:
    # Verify decides WHICH units get flagged. If it took cfg.whisper_beam_size it would move
    # under the very experiment it is supposed to measure.
    assert VERIFY_BEAM_SIZE == 5
    assert not hasattr(Config(), "verify_beam_size")
    assert not hasattr(Config(), "repair_beam_size")


# --- 2. the decoupling ----------------------------------------------------------------

def test_verify_compute_type_survives_a_transcribe_only_override() -> None:
    # THE point of the split: this assertion is what fails if verify_compute_type is ever turned
    # into an inherit-sentinel, which would leave problem (a) exactly where it was.
    cfg = Config()
    cfg.whisper_compute_type = "int8_float16"
    assert cfg.compute_type_for("transcribe") == "int8_float16"
    assert cfg.compute_type_for("verify") == "float16", cfg.compute_type_for("verify")


def test_transcribe_compute_type_survives_a_verify_only_override() -> None:
    # Symmetric direction: moving the instrument on purpose must not move the transcriber.
    cfg = Config()
    cfg.verify_compute_type = "int8_float16"
    assert cfg.compute_type_for("transcribe") == "float16"
    assert cfg.compute_type_for("verify") == "int8_float16"


# --- 3. unknown role ------------------------------------------------------------------

def test_unknown_role_raises() -> None:
    # A closed 2-element enum: a typo'd role that fell back to a default would silently hand one
    # instrument's compute type to the other.
    try:
        Config().compute_type_for("nonsense")
    except ValueError as e:
        assert "nonsense" in str(e), str(e)
    else:
        raise AssertionError("compute_type_for accepted an unknown role")


# --- 4. asr_key -----------------------------------------------------------------------

def test_asr_key_is_stable_and_names_the_config() -> None:
    # A string, not a hash: the refusal message has to be actionable.
    assert asr_key(Config()) == "large-v3|float16|beam=5|cond=True", asr_key(Config())
    assert asr_key(Config()) == asr_key(Config())


def test_asr_key_moves_with_every_source_text_knob() -> None:
    base = asr_key(Config())
    for field, value in (("whisper_model", "distil-large-v3"),
                         ("whisper_compute_type", "int8_float16"),
                         ("whisper_beam_size", 1),
                         ("whisper_condition_on_previous", False)):
        cfg = Config()
        setattr(cfg, field, value)
        assert asr_key(cfg) != base, field


def test_asr_key_ignores_knobs_that_cannot_change_source_text() -> None:
    # Not a hash of the whole Config: a key that moved on tts_seed would refuse every workdir
    # after an unrelated TTS experiment, and operators would learn to delete the stamp.
    base = asr_key(Config())
    for field, value in (("tts_seed", 7), ("verify_compute_type", "int8_float16"),
                         ("f5_nfe", 32), ("repair_window_min_sec", 12.0)):
        cfg = Config()
        setattr(cfg, field, value)
        assert asr_key(cfg) == base, field


# --- 5. the session cache key ---------------------------------------------------------

def test_session_key_is_the_five_tuple_and_roles_do_not_cross() -> None:
    cfg = Config()
    with _patched_loader() as rec:
        session = Session()
        t = session.whisper(cfg, cfg.whisper_model, role="transcribe")
        v = session.whisper(cfg, cfg.verify_model, role="verify")
        assert set(session._cache) == {("whisper", "large-v3", "cuda", "float16", 5),
                                       ("whisper", "small", "cuda", "float16", 5)}, session._cache
        assert rec.calls == [("large-v3", "cuda", "float16", 5, 1),
                             ("small", "cuda", "float16", 5, 1)], rec.calls
        # synthesize's reseed verifier asks for the same role+model as verify — one instance
        assert session.whisper(cfg, cfg.verify_model, role="verify") is v
        assert session.whisper(cfg, cfg.whisper_model, role="transcribe") is t
        assert len(rec.calls) == 2, rec.calls


def test_session_key_separates_two_roles_that_differ_only_in_compute_type() -> None:
    # The trap: point verify_model at the transcribe model (or flip only the compute type) and a
    # (model, device) key hands BOTH roles the same build — an in-process A/B comparing a thing
    # to itself, invisible in every report.
    cfg = Config()
    cfg.whisper_model = "small"
    cfg.verify_model = "small"
    cfg.whisper_compute_type = "int8_float16"
    with _patched_loader() as rec:
        session = Session()
        t = session.whisper(cfg, cfg.whisper_model, role="transcribe")
        v = session.whisper(cfg, cfg.verify_model, role="verify")
        assert t is not v
        assert [c[2] for c in rec.calls] == ["int8_float16", "float16"], rec.calls
        assert set(session._cache) == {("whisper", "small", "cuda", "int8_float16", 5),
                                       ("whisper", "small", "cuda", "float16", 5)}, session._cache


def test_session_key_separates_two_roles_that_differ_only_in_beam() -> None:
    # asr._warm tunes kernels FOR a beam, so an instance warmed at 5 is not interchangeable with
    # one warmed at 1. A key without the beam would silently share one build across the A/B —
    # and would also drag the verifier down to beam 1 with the transcriber.
    cfg = Config()
    cfg.whisper_model = "small"
    cfg.verify_model = "small"
    cfg.whisper_beam_size = 1
    with _patched_loader() as rec:
        session = Session()
        t = session.whisper(cfg, cfg.whisper_model, role="transcribe")
        v = session.whisper(cfg, cfg.verify_model, role="verify")
        assert t is not v
        assert [c[3] for c in rec.calls] == [1, VERIFY_BEAM_SIZE], rec.calls
        assert set(session._cache) == {("whisper", "small", "cuda", "float16", 1),
                                       ("whisper", "small", "cuda", "float16", 5)}, session._cache


def test_session_role_is_required() -> None:
    # Not defaulted, so a new call site must STATE which instrument it wants instead of
    # inheriting whichever one happened to be written first.
    params = inspect.signature(Session.whisper).parameters
    assert params["role"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["role"].default is inspect.Parameter.empty


# --- 6. signature pins ----------------------------------------------------------------

def test_transcribe_words_beam_is_required_keyword_only() -> None:
    # A DEFAULT here is the whole failure: one of the two consumers would keep beam 5 while the
    # other moved, and the suite would stay green against the wrong media.
    p = inspect.signature(transcribe_words).parameters["beam_size"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY
    assert p.default is inspect.Parameter.empty


def test_load_whisper_exposes_beam_and_num_workers_as_keywords() -> None:
    # num_workers exists ONLY so the sweep can measure the threading ceiling through the one
    # loader that registers the CUDA DLL dirs and warms the model; it must never be positional.
    params = inspect.signature(load_whisper).parameters
    for name, default in (("beam_size", 5), ("num_workers", 1)):
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY, name
        assert params[name].default == default, name
    assert inspect.signature(asr._warm).parameters["beam_size"].default is inspect.Parameter.empty


# --- 7. the beam actually reaches the decoder, on BOTH consumers ----------------------

def test_transcribe_stage_decodes_at_the_config_beam() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        work = _work(tmp)
        work.source_audio.write_bytes(b"RIFF")
        cfg = Config()
        cfg.whisper_beam_size = 1
        ctx = _ctx(work, cfg)
        model, roles = FakeModel(), []
        ctx.session.whisper = lambda c, m, *, role: (roles.append(role) or model)  # type: ignore[method-assign]
        _quiet(TranscribeStage().run, ctx)
        assert roles == ["transcribe"], roles
        assert [c["beam_size"] for c in model.calls] == [1], model.calls
        assert model.calls[0]["word_timestamps"] is True and model.calls[0]["vad_filter"] is True


def test_repair_window_decodes_at_the_same_config_beam() -> None:
    # The trap a stage-only test cannot see: --repair-asr shares transcribe_words on purpose, so
    # a window decoded at another width splices in a sentence of a different KIND — a defect that
    # shows up only on real media, long after the suite went green.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        work = _work(tmp)
        work.source_audio.write_bytes(b"RIFF")
        cfg = Config()
        cfg.whisper_beam_size = 1
        ctx = _ctx(work, cfg)
        model, roles = FakeModel(), []
        ctx.session.whisper = lambda c, m, *, role: (roles.append(role) or model)  # type: ignore[method-assign]
        which, run = repair.shutil.which, repair.subprocess.run
        repair.shutil.which = lambda name: "ffmpeg.exe"
        repair.subprocess.run = lambda *a, **kw: None
        try:
            repair.make_window_asr(ctx)(0.0, 5.0, False)
        finally:
            repair.shutil.which, repair.subprocess.run = which, run
        assert roles == ["transcribe"], roles
        assert [c["beam_size"] for c in model.calls] == [cfg.whisper_beam_size], model.calls
        assert model.calls[0]["condition_on_previous_text"] is False


def test_roundtrip_verifier_holds_its_beam_while_the_transcriber_moves() -> None:
    # roundtrip_similarity takes no cfg at all, by design. Pinned anyway: wiring it to
    # cfg.whisper_beam_size later would shift every similarity score under a speed experiment.
    model = FakeModel()
    ratio, hyp, hyp_n = roundtrip_similarity(model, Path("x.wav"), "anything", "ru")
    assert model.calls[0]["beam_size"] == VERIFY_BEAM_SIZE, model.calls
    assert model.calls[0]["condition_on_previous_text"] is False
    assert (ratio, hyp, hyp_n) == (0.0, "", "")


# --- 8. the provenance guard ----------------------------------------------------------

def _stamped_ctx(tmp: Path, stamp: str | None, cfg: Config | None = None) -> Context:
    work = _work(tmp)
    work.sentences.write_text("[]", encoding="utf-8")
    if stamp is not None:
        runreport.record_stage_detail(work, "transcribe", work_sec=1.0, asr_passes=1,
                                      asr_key=stamp)
    return _ctx(work, cfg)


def test_done_is_false_without_the_artifact() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        tmp.mkdir(parents=True)
        assert TranscribeStage().done(_ctx(_work(tmp))) is False


def test_done_accepts_a_pre_stamp_workdir() -> None:
    # The existing corpus predates asr_key. Invalidating it would be a data loss, not a guard.
    with tempfile.TemporaryDirectory() as d:
        assert TranscribeStage().done(_stamped_ctx(Path(d) / VID, None)) is True


def test_done_accepts_a_matching_stamp() -> None:
    with tempfile.TemporaryDirectory() as d:
        ctx = _stamped_ctx(Path(d) / VID, asr_key(Config()))
        assert TranscribeStage().done(ctx) is True


def test_done_warns_on_a_mixed_provenance_workdir_and_names_both_configs() -> None:
    # WARNS, does not refuse (2026-07-22). Refusal was inert on all 72 existing workdirs — none
    # carries a stamp — while breaking `--batch --force`, which rebuilds translation.json two
    # stages later and was never wrong. The workdir must stay usable; the operator must be told.
    with tempfile.TemporaryDirectory() as d:
        cfg = Config()
        cfg.whisper_beam_size = 1
        ctx = _stamped_ctx(Path(d) / VID, "large-v3|float16|beam=5|cond=True", cfg)
        ok, out = _quiet(TranscribeStage().done, ctx)
        assert ok is True
        assert "[warn]" in out, out
        assert "beam=5" in out and "beam=1" in out, out
        assert "SKIPS" in out, out                     # names the consequence, not just the drift


def test_run_stamps_the_key_that_done_reads_back() -> None:
    # The round trip, so the writer and the reader cannot drift into two spellings of the key.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        work = _work(tmp)
        work.source_audio.write_bytes(b"RIFF")
        cfg = Config()
        cfg.whisper_beam_size = 1
        ctx = _ctx(work, cfg)
        ctx.session.whisper = lambda c, m, *, role: FakeModel()  # type: ignore[method-assign]
        _quiet(TranscribeStage().run, ctx)
        doc = json.loads((tmp / "timings.json").read_text(encoding="utf-8"))
        assert doc["detail"]["transcribe"]["asr_key"] == asr_key(cfg), doc
        assert TranscribeStage().done(ctx) is True
        ctx.cfg.whisper_beam_size = 5                     # the operator "tries beam 5 next"
        ok, out = _quiet(TranscribeStage().done, ctx)
        assert ok is True                                 # usable — but the drift is announced
        assert "[warn]" in out and "beam=1" in out and "beam=5" in out, out


# --- 9. the shipped overdub.toml ------------------------------------------------------

def test_shipped_toml_resolves_to_todays_effective_asr_settings() -> None:
    # Every measured number in this repo — RTF 0.087, the repair-fixture baseline, the corpus
    # similarity distribution — is conditional on this file resolving to exactly this config. An
    # accidentally uncommented key would rebase all of them without a single failing test.
    toml = _ROOT / "overdub.toml"
    assert toml.exists(), toml
    cfg = Config.load(toml)
    assert cfg.whisper_model == "large-v3", cfg.whisper_model
    assert cfg.whisper_device == "cuda", cfg.whisper_device
    assert cfg.whisper_beam_size == 5, cfg.whisper_beam_size
    assert cfg.whisper_condition_on_previous is True
    assert cfg.verify_model == "small", cfg.verify_model
    assert cfg.compute_type_for("transcribe") == "float16"
    assert cfg.compute_type_for("verify") == "float16"
    assert asr_key(cfg) == asr_key(Config()) == "large-v3|float16|beam=5|cond=True"


# --- 10. the loader actually forwards what it was asked for ---------------------------

class _FakeWhisperModel:
    """Stands in for faster_whisper.WhisperModel: records the CONSTRUCTION kwargs (where
    num_workers lands) and every transcribe kwarg (where the warmup beam lands)."""

    def __init__(self, model, device=None, compute_type=None, num_workers=None) -> None:
        self.ctor = {"model": model, "device": device, "compute_type": compute_type,
                     "num_workers": num_workers}
        self.calls: list[dict] = []

    def transcribe(self, *args, **kw):
        self.calls.append(kw)
        return ([], None)


@contextlib.contextmanager
def _stub_faster_whisper():
    """load_whisper imports faster_whisper INSIDE the function, so a sys.modules stub is what
    makes it callable without CUDA, cuDNN or a 3 GB download."""
    mod = types.ModuleType("faster_whisper")
    mod.WhisperModel = _FakeWhisperModel
    prior = sys.modules.get("faster_whisper")
    sys.modules["faster_whisper"] = mod
    try:
        yield
    finally:
        if prior is None:
            del sys.modules["faster_whisper"]
        else:
            sys.modules["faster_whisper"] = prior


def test_the_warmup_decodes_at_the_beam_the_run_will_use() -> None:
    """asr._warm exists so the first video does not absorb cuDNN/cuBLAS autotuning — but the
    beam is one of the things that SELECTS the kernels being tuned. Warming at 5 for a run that
    decodes at 1 tunes the wrong ones, and the mis-tune lands entirely on the first video of the
    sweep, i.e. on exactly the number the optimization measurement is trying to read."""
    with _stub_faster_whisper():
        m, _out = _quiet(load_whisper, "small", "cuda", "float16", beam_size=1, num_workers=3)
    assert m.calls, "the model was never warmed"
    assert m.calls[0]["beam_size"] == 1, m.calls
    assert m.calls[0]["word_timestamps"] is True and m.calls[0]["vad_filter"] is False


def test_num_workers_reaches_the_constructor() -> None:
    # ctranslate2 inter_threads is a CONSTRUCTION argument — it exists only so the sweep can
    # measure the cross-video-threading ceiling through the one loader that registers the CUDA
    # DLL dirs and warms the model. Dropped there, the variant would measure nothing.
    with _stub_faster_whisper():
        m, _out = _quiet(load_whisper, "small", "cuda", "int8_float16", beam_size=5,
                         num_workers=3)
    assert m.ctor == {"model": "small", "device": "cuda", "compute_type": "int8_float16",
                      "num_workers": 3}, m.ctor


# --- 11. the two verify-role call sites -----------------------------------------------

def _role_recorder():
    seen: list[tuple] = []

    def rec(cfg, model, *, role):
        seen.append((model, role, cfg.compute_type_for(role)))
        return FakeModel()

    return seen, rec


def test_verify_asks_for_the_verify_role_while_the_transcriber_is_moved() -> None:
    """The instrument must not move with the thing it measures: flipping the transcriber to
    int8_float16 must leave whisper-small at float16, or every similarity score and every flag
    count moves too and the experiment reads its own measurement error as a result."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        work = _work(tmp)
        (tmp / "segments").mkdir(parents=True, exist_ok=True)
        work.translation.write_text("[]", encoding="utf-8")
        work.seg_manifest.write_text(json.dumps({"units": [], "synth_key": "k",
                                                 "units_key": "u"}), encoding="utf-8")
        cfg = Config()
        cfg.whisper_compute_type = "int8_float16"
        ctx = _ctx(work, cfg)
        seen, rec = _role_recorder()
        ctx.session.whisper = rec                       # type: ignore[method-assign]
        _quiet(VerifyStage().run, ctx)
        assert seen == [("small", "verify", "float16")], seen


class _FakeEngine:
    """Minimal seed-capable TTS engine: writes a real (silent) wav so the stage's own sr and
    frame checks pass, and reports supports_seed so the reseed VERIFIER is requested."""

    supports_seed = True

    def __init__(self, sample_rate: int) -> None:
        self.sample_rate = sample_rate

    def begin_video(self) -> None:
        return None

    def synthesize(self, text, path, seed=None, **kw) -> float:
        sf.write(str(path), np.zeros(self.sample_rate // 10, dtype="float32"), self.sample_rate)
        return 1.0


def test_the_reseed_verifier_asks_for_the_verify_role_too() -> None:
    # The second call site, and the one a stage-only test of verify cannot see: synthesize's
    # reseed loop shares roundtrip_similarity with verify on purpose, so it must share the
    # instrument's build as well.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        work = _work(tmp)
        (tmp / "segments").mkdir(parents=True, exist_ok=True)
        work.translation.write_text(json.dumps(
            [{"id": 0, "start": 0.0, "end": 2.0, "src_en": "hello",
              "text_ru": "привет", "text_tts": "привет", "status": "ok"}],
            ensure_ascii=False), encoding="utf-8")
        cfg = Config()
        cfg.tts_engine = "silero"                       # synth_key must not need F5 assets here
        cfg.whisper_compute_type = "int8_float16"
        cfg.tts_max_retries = 1
        ctx = _ctx(work, cfg)
        seen, rec = _role_recorder()
        ctx.session.whisper = rec                       # type: ignore[method-assign]
        ctx.session.tts_engine = lambda c: _FakeEngine(c.tts_sample_rate)  # type: ignore
        _quiet(SynthesizeStage().run, ctx)
        assert seen == [("small", "verify", "float16")], seen


# --- 12. asr_key records, asr_key_core refuses ----------------------------------------

def test_asr_key_core_drops_cond_and_keeps_the_other_three() -> None:
    """cond is the ONE element the pipeline changes by itself at runtime (_guard) and the one
    documented as a per-source escape hatch, so refusing on it poisoned the workdir the hatch
    existed to produce. The other three are global config facts the sweep moves and the operator
    must not be able to land as a no-op."""
    base = asr_key(Config())
    assert asr_key_core(base) == "large-v3|float16|beam=5"
    assert asr_key_core(asr_key(Config(), cond=False)) == asr_key_core(base)
    assert asr_key_core(asr_key(Config(), cond="mixed")) == asr_key_core(base)
    for field, value in (("whisper_model", "distil-large-v3"),
                         ("whisper_compute_type", "int8_float16"),
                         ("whisper_beam_size", 1)):
        cfg = Config()
        setattr(cfg, field, value)
        assert asr_key_core(asr_key(cfg)) != asr_key_core(base), field


def test_asr_key_records_the_cond_it_is_given() -> None:
    assert asr_key(Config(), cond=False).endswith("|cond=False")
    assert asr_key(Config(), cond="mixed").endswith("|cond=mixed")
    assert asr_key(Config()).endswith("|cond=True")            # default: the config's value


def test_done_keeps_a_workdir_whose_cond_alone_differs() -> None:
    # The hatch (overdub.toml's 4szRHy_CT7s NOTE) is used, then the toml is restored. Refusing
    # here left that workdir raising forever, with the printed remedy ("delete sentences.json")
    # destroying the transcript the hatch existed to produce.
    with tempfile.TemporaryDirectory() as d:
        ctx = _stamped_ctx(Path(d) / VID, "large-v3|float16|beam=5|cond=False")
        ok, out = _quiet(TranscribeStage().done, ctx)
        assert ok is True
        assert "cond=False" in out and "cond=True" in out, out


# --- 13. the stamp is what DECODED, not what was configured ---------------------------

def _seg(words):
    return SimpleNamespace(words=words, text=" ".join(w.word for w in words),
                           start=words[0].start, end=words[-1].end)


def _word(tok, start, end):
    return SimpleNamespace(word=tok, start=start, end=end)


class _GuardModel:
    """Returns a COLLAPSED alignment on the first decode and a clean one on the retry — the
    exact shape TranscribeStage._guard reacts to (chained MIN_WORD_DUR words that flatten had
    to manufacture)."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def transcribe(self, *args, **kw):
        self.calls.append(kw)
        clean = [_word(f"w{i}", i * 0.5, i * 0.5 + 0.4) for i in range(5)]
        if len(self.calls) > 1:
            return ([_seg(clean)], None)
        # start == end and <= the previous end: flatten clamps monotone and floors the duration
        collapsed = [_word(f"d{i}", 0.0, 0.0) for i in range(40)]
        return ([_seg(clean + collapsed)], None)


def test_run_stamps_the_cond_the_guard_actually_decoded_at() -> None:
    """_guard hands back its cond=False retry whenever that retry halves the floor ratio. A
    stamp of the config's INTENT would let two workdirs carry one identical key over materially
    different transcripts — and the workdir must stay usable afterwards, since nothing about the
    config changed."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        work = _work(tmp)
        work.source_audio.write_bytes(b"RIFF")
        ctx = _ctx(work)
        model = _GuardModel()
        ctx.session.whisper = lambda c, m, *, role: model   # type: ignore[method-assign]
        _quiet(TranscribeStage().run, ctx)
        detail = json.loads((tmp / "timings.json").read_text(encoding="utf-8"))["detail"]
        assert detail["transcribe"]["asr_passes"] == 2, detail
        assert detail["transcribe"]["asr_key"].endswith("|cond=False"), detail
        assert detail["transcribe"]["asr_key"] != asr_key(ctx.cfg)
        # ...and the guard's own correct output must not poison the workdir it produced
        ok, _out = _quiet(TranscribeStage().done, ctx)
        assert ok is True
        assert [c["condition_on_previous_text"] for c in model.calls] == [True, False], model.calls


def test_run_stamps_the_config_when_the_guard_does_not_fire() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        work = _work(tmp)
        work.source_audio.write_bytes(b"RIFF")
        ctx = _ctx(work)
        ctx.session.whisper = lambda c, m, *, role: FakeModel()  # type: ignore[method-assign]
        _quiet(TranscribeStage().run, ctx)
        detail = json.loads((tmp / "timings.json").read_text(encoding="utf-8"))["detail"]
        assert detail["transcribe"]["asr_key"] == asr_key(ctx.cfg), detail
        assert detail["transcribe"]["asr_passes"] == 1
        assert MIN_WORD_DUR > 0                                  # the guard's unit, unchanged


# --- 14. --force skips done(), so the rewrite guard is its own check ------------------

def test_a_forced_rewrite_over_a_live_translation_warns_loudly() -> None:
    """run_pipeline consults done() only on the unforced path, and `--force --only transcribe`
    is precisely the command an adoption run uses to re-time a beam. --only filters translate
    out, TranslateStage.done() is bare existence, and nothing downstream compares the two files
    — so a beam-1 transcript paired with a beam-5 translation is invisible for the rest of the
    run. The rewrite proceeds (refusing also caught plain `--batch --force`, which rebuilds
    translation.json two stages later); the operator gets the one line that makes it visible."""
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        cfg = Config()
        cfg.whisper_beam_size = 1
        ctx = _stamped_ctx(tmp, "large-v3|float16|beam=5|cond=True", cfg)
        ctx.work.source_audio.write_bytes(b"RIFF")
        ctx.work.translation.write_text("[]", encoding="utf-8")
        ctx.session.whisper = lambda c, m, *, role: FakeModel()  # type: ignore[method-assign]
        _out, printed = _quiet(TranscribeStage().run, ctx)
        assert "[warn]" in printed, printed
        assert "translation.json" in printed and "beam=1" in printed, printed
        detail = json.loads((tmp / "timings.json").read_text(encoding="utf-8"))["detail"]
        assert detail["transcribe"]["asr_key"] == asr_key(cfg), detail   # and it really rewrote


def test_a_forced_rewrite_with_no_translation_stays_free() -> None:
    # The sweep's own legitimate move. Scoped to the artifact that makes the failure silent.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        cfg = Config()
        cfg.whisper_beam_size = 1
        ctx = _stamped_ctx(tmp, "large-v3|float16|beam=5|cond=True", cfg)
        ctx.work.source_audio.write_bytes(b"RIFF")
        ctx.session.whisper = lambda c, m, *, role: FakeModel()  # type: ignore[method-assign]
        _quiet(TranscribeStage().run, ctx)
        detail = json.loads((tmp / "timings.json").read_text(encoding="utf-8"))["detail"]
        assert detail["transcribe"]["asr_key"] == asr_key(cfg), detail


def test_a_cond_only_difference_does_not_block_a_forced_rewrite() -> None:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / VID
        ctx = _stamped_ctx(tmp, "large-v3|float16|beam=5|cond=False")
        ctx.work.source_audio.write_bytes(b"RIFF")
        ctx.work.translation.write_text("[]", encoding="utf-8")
        ctx.session.whisper = lambda c, m, *, role: FakeModel()  # type: ignore[method-assign]
        _quiet(TranscribeStage().run, ctx)                  # must not raise


# --- 15. --repair-asr runs no stage, so it checks the key itself ----------------------

def test_repair_warns_about_a_window_at_another_beam() -> None:
    """cli.py branches to _run_repair before the pipeline, so TranscribeStage.done() never
    executes on this path. A window decoded at another model/compute type/beam splices in a
    sentence of a different KIND from its neighbours — the drift transcribe_words' shared body
    exists to prevent. Warns rather than refuses: the refusing version ran ahead of the
    no-defect-windows early return, so a repair that would change nothing still exited 1."""
    with tempfile.TemporaryDirectory() as d:
        cfg = Config()
        cfg.whisper_beam_size = 1
        ctx = _stamped_ctx(Path(d) / VID, "large-v3|float16|beam=5|cond=True", cfg)
        stamped, out = _quiet(repair.check_decode_config, ctx)
        assert stamped == "large-v3|float16|beam=5|cond=True"
        assert "[warn]" in out and "beam=5" in out and "beam=1" in out, out


def test_repair_accepts_a_cond_difference_and_a_pre_stamp_workdir() -> None:
    # The emitted repair reading is always the clipped cond=False one, so refusing on cond would
    # break the mode by design; and the preserved corpus predates the stamp entirely.
    with tempfile.TemporaryDirectory() as d:
        ctx = _stamped_ctx(Path(d) / VID, "large-v3|float16|beam=5|cond=False")
        assert repair.check_decode_config(ctx) == "large-v3|float16|beam=5|cond=False"
    with tempfile.TemporaryDirectory() as d:
        assert repair.check_decode_config(_stamped_ctx(Path(d) / VID, None)) is None


def test_a_repaired_transcript_stamps_cond_mixed_and_counts_its_windows() -> None:
    """A repaired transcript is the full-file reading with n clipped windows spliced in, so the
    pure cond value is no longer true. invalidate_downstream deliberately PRESERVES timings.json,
    so nothing else could record this."""
    with tempfile.TemporaryDirectory() as d:
        ctx = _stamped_ctx(Path(d) / VID, asr_key(Config()))
        repair.stamp_repaired(ctx, asr_key(Config()), 2)
        repair.stamp_repaired(ctx, asr_key(Config()), 1)
        detail = json.loads((ctx.work.root / "timings.json").read_text(
            encoding="utf-8"))["detail"]["transcribe"]
        assert detail["asr_key"] == asr_key(Config(), cond="mixed")
        assert detail["asr_repair_windows"] == 3            # cumulative across passes
        assert asr_key_core(detail["asr_key"]) == asr_key_core(asr_key(Config()))


def test_a_pre_stamp_workdir_gets_the_count_but_no_invented_key() -> None:
    # Its base decode is genuinely unknown, and an invented stamp is a worse record than none.
    with tempfile.TemporaryDirectory() as d:
        ctx = _stamped_ctx(Path(d) / VID, None)
        repair.stamp_repaired(ctx, None, 1)
        detail = json.loads((ctx.work.root / "timings.json").read_text(
            encoding="utf-8"))["detail"]["transcribe"]
        assert detail["asr_repair_windows"] == 1
        assert "asr_key" not in detail, detail


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all asr-config tests passed")
