import pytest

from app.config import load_test
from app.services.analyse import (
    analyse_item,
    awaiting_verification,
    is_counted,
    record_live_tap,
    record_verification,
    scoring_breakdown,
)
from tests.conftest import load_fixture, make_transcript

HI = {i["id"]: i for i in load_test("hi")["items"]}
EN = {i["id"]: i for i in load_test("en")["items"]}


def test_real_lexicalization_is_auto_scored(cfg):
    # Real v3 output for पमीर read as पनीर.
    r = analyse_item(HI["hi_C_01"], "hi", load_fixture("hi_05_lexicalization"), cfg=cfg)
    assert r.status == "auto"
    assert r.correct is False and r.suggested_correct is False
    assert [e.type for e in r.errors] == ["lexicalization"]
    assert is_counted(r) and not awaiting_verification(r)


def test_real_mishearing_waits_for_teacher(cfg):
    # Real v3 output: "saw" heard as "song" with low confidence.
    r = analyse_item(EN["en_B_03"], "en", load_fixture("en_02_was_saw"), cfg=cfg)
    assert r.status == "teacher_verify"
    assert r.correct is None and r.suggested_correct is False
    assert not is_counted(r) and awaiting_verification(r)
    record_verification(r, "incorrect")
    assert r.verified and r.correct is False
    assert is_counted(r) and not awaiting_verification(r)


def test_real_conjunct_error_is_low_confidence(cfg):
    r = analyse_item(HI["hi_B_09"], "hi", load_fixture("hi_07_conjunct"), cfg=cfg)
    assert [e.type for e in r.errors] == ["conjunct_error"]
    assert r.errors[0].low_confidence


def test_english_auto_counts_only_once_verified(cfg):
    r = analyse_item(EN["en_B_01"], "en", make_transcript("cat", [("cat", 1.0, 1.4)]), cfg=cfg)
    assert r.status == "auto" and r.correct is True
    assert not is_counted(r) and awaiting_verification(r)
    record_verification(r, "correct")
    assert is_counted(r)


def test_manual_item_is_live_tapped_and_never_queued(cfg):
    tr = make_transcript("बाद", [("बाद", 0.9, 1.3)], avg_logprob=-0.7)
    r = analyse_item(HI["hi_A_01"], "hi", tr, cfg=cfg)
    assert r.status == "manual"
    assert r.correct is None and r.errors == []  # transcript is evidence only
    assert not awaiting_verification(r) and not is_counted(r)
    record_live_tap(r, "correct")
    assert r.correct is True and r.live_tap == "correct" and is_counted(r)
    assert not awaiting_verification(r)
    with pytest.raises(ValueError):
        record_verification(r, "incorrect")


def test_live_tap_can_come_with_the_clip(cfg):
    r = analyse_item(EN["en_A_01"], "en", make_transcript("d", [("d", 1.0, 1.2)]), live_tap="skipped", cfg=cfg)
    assert r.correct is False and r.skipped and is_counted(r)


def test_live_tap_rejected_for_auto_items_and_bad_values(cfg):
    r = analyse_item(HI["hi_B_01"], "hi", make_transcript("कमल", [("कमल", 1.0, 1.4)]), cfg=cfg)
    with pytest.raises(ValueError):
        record_live_tap(r, "correct")
    m = analyse_item(HI["hi_A_01"], "hi", make_transcript("ब"), cfg=cfg)
    with pytest.raises(ValueError):
        record_live_tap(m, "maybe")


def test_timing_errors_are_kept_for_manual_items(cfg):
    tr = make_transcript("ब", [("ब", 3.5, 3.8)])
    r = analyse_item(HI["hi_A_01"], "hi", tr, cfg=cfg)
    assert [e.type for e in r.errors] == ["slow_start"]


def test_scoring_breakdown(cfg):
    results = [
        analyse_item(HI["hi_B_01"], "hi", make_transcript("कमल"), cfg=cfg),                       # auto
        analyse_item(HI["hi_B_02"], "hi", make_transcript("पीला", avg_logprob=-0.9), cfg=cfg),    # verify
        analyse_item(HI["hi_A_01"], "hi", make_transcript("ब"), live_tap="correct", cfg=cfg),     # live tap
        analyse_item(HI["hi_A_02"], "hi", make_transcript("व"), live_tap="correct", cfg=cfg),     # live tap
        analyse_item(EN["en_B_01"], "en", make_transcript("cat"), cfg=cfg),                        # auto, awaits confirm
    ]
    record_verification(results[1], "correct")
    b = scoring_breakdown(results)
    assert b["hi"] == {"items": 4, "auto_pct": 25.0, "teacher_verify_pct": 25.0, "live_tap_pct": 50.0, "pending_verify": 0}
    assert b["en"] == {"items": 1, "auto_pct": 100.0, "teacher_verify_pct": 0.0, "live_tap_pct": 0.0, "pending_verify": 1}
    assert b["overall"]["items"] == 5 and b["overall"]["auto_pct"] == 40.0


def _passage(cfg):
    words = [(w, 1.0 + i * 0.5, 1.4 + i * 0.5) for i, w in enumerate("the cat sat".split())]
    item = {"id": "en_D_x", "section": "D", "text": "the cat sat on the mat", "scoring": "auto"}
    return analyse_item(item, "en", make_transcript("the cat sat", words), cfg=cfg)


def test_passage_verification_correct_keeps_ai_scoring(cfg):
    r = _passage(cfg)
    assert r.words_correct == 3 and r.suggested_correct is False
    record_verification(r, "correct")
    assert r.verified and r.words_correct == 3 and r.correct is False
    assert [e.type for e in r.errors].count("omission") == 3


def test_passage_verification_incorrect_needs_teacher_count(cfg):
    r = _passage(cfg)
    with pytest.raises(ValueError):
        record_verification(r, "incorrect")
    with pytest.raises(ValueError):
        record_verification(r, "incorrect", words_correct=99)
    record_verification(r, "incorrect", words_correct=5)
    assert r.words_correct == 5 and r.correct is False and not r.skipped
    assert all(e.type in ("hesitation", "slow_start", "slow_decoding") for e in r.errors)


def test_verifying_a_word_correct_clears_rule_errors(cfg):
    tr = make_transcript("song", [("song", 3.5, 3.9)], avg_logprob=-0.9)
    r = analyse_item(EN["en_B_03"], "en", tr, cfg=cfg)
    assert {e.type for e in r.errors} == {"unclassified", "slow_start"}
    record_verification(r, "correct")
    assert r.correct is True and [e.type for e in r.errors] == ["slow_start"]


def test_single_word_item_read_at_normal_pace_has_no_hesitation(cfg):
    tr = make_transcript("लोकुस", [("लोकुस", 0.02, 0.88)])
    r = analyse_item(HI["hi_C_02"], "hi", tr, cfg=cfg)
    assert r.correct is True and r.errors == []
