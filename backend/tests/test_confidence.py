from app.services.confidence import AUTO, MANUAL, TEACHER_VERIFY, assess_confidence, item_status
from app.services.transcribe import Segment
from tests.conftest import load_fixture


def seg(logprob, no_speech=0.05, text="x"):
    return Segment(text, 0.0, 1.0, logprob, no_speech)


def test_real_mishearing_goes_to_teacher_verify(cfg):
    # Real v3 output: "was" read as "saw", heard as "song" at avg_logprob -0.93.
    tr = load_fixture("en_02_was_saw")
    conf = assess_confidence(tr.segments, tr.text, cfg)
    assert conf.low and "avg_logprob" in conf.reasons[0]
    assert item_status("auto", conf) == TEACHER_VERIFY


def test_real_confident_transcript_is_auto(cfg):
    tr = load_fixture("hi_05_lexicalization")
    conf = assess_confidence(tr.segments, tr.text, cfg)
    assert not conf.low
    assert item_status("auto", conf) == AUTO


def test_thresholds(cfg):
    assert not assess_confidence([seg(-0.6)], "x", cfg).low          # boundary is strict
    assert assess_confidence([seg(-0.61)], "x", cfg).low
    assert assess_confidence([seg(-0.2, no_speech=0.61)], "x", cfg).low
    # worst segment decides
    assert assess_confidence([seg(-0.1), seg(-0.9)], "x", cfg).avg_logprob == -0.9


def test_empty_transcript_is_low_confidence(cfg):
    conf = assess_confidence([], "।", cfg)
    assert conf.low and conf.reasons == ["empty transcript"]


def test_manual_items_stay_manual_whatever_the_confidence(cfg):
    low = assess_confidence([seg(-1.5)], "x", cfg)
    high = assess_confidence([seg(-0.1)], "x", cfg)
    assert item_status("manual", low) == MANUAL
    assert item_status("manual", high) == MANUAL


def test_wrong_script_goes_to_teacher_verify(cfg):
    # Real v3 output on TTS: Hindi मोर transcribed as "more".
    assert "transcribed in the wrong script" in assess_confidence([seg(-0.2)], "more", cfg, "hi").reasons
    assert "transcribed in the wrong script" in assess_confidence([seg(-0.2)], "पमीर", cfg, "en").reasons
    assert not assess_confidence([seg(-0.2)], "मोर।", cfg, "hi").low
    assert not assess_confidence([seg(-0.2)], "Ship", cfg, "en").low
