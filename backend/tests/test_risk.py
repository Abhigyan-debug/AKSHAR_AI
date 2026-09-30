"""Risk decision table (docs/scoring.md) and its edge cases."""

import pytest

from app.services.analyse import ItemResult, record_verification
from app.services.classify_rules import ErrorLabel
from app.services.confidence import Confidence
from app.services.risk import compute_risk
from app.services.timing import Timing

BANK = {"hi": {"A": 10, "B": 10, "C": 10, "D": 1, "E": 5}, "en": {"A": 10, "B": 10, "C": 10, "D": 1, "E": 5}}
HI_ERROR = "matra_confusion"
EN_ERROR = "letter_reversal"


def result(lang, section, i, correct, *, status="auto", verified=False, live_tap=None, errors=(), hesitation=False,
           words_total=1, words_correct=None, duration=0.6, start=1.0):
    timing = Timing(start_latency_s=start, duration_s=duration, hesitation=hesitation, slow_start=start >= 3.0)
    errs = [ErrorLabel(t, "x", "y") for t in errors]
    if hesitation:
        errs.append(ErrorLabel("hesitation", "x", None))
    if start >= 3.0:
        errs.append(ErrorLabel("slow_start", "x", None))
    return ItemResult(
        item_id=f"{lang}_{section}_{i:02d}", lang=lang, section=section, status=status, transcript="",
        correct=correct if (status == "auto" or verified or live_tap) else None, suggested_correct=bool(correct),
        skipped=False, errors=errs, timing=timing, confidence=Confidence(-0.2, 0.05, False),
        words_total=words_total, words_correct=words_correct if words_correct is not None else int(bool(correct)),
        live_tap=live_tap, verified=verified,
    )


def language(lang, *, letters_ok=10, words_ok=10, nonwords_ok=10, wcpm=80.0, lex=0, error_type=None,
             hesitate=0, verified=True, include_c=True, status="auto"):
    error_type = error_type or (HI_ERROR if lang == "hi" else EN_ERROR)
    v = verified if lang == "en" else False
    out = []
    for i in range(10):
        ok = i < letters_ok
        out.append(result(lang, "A", i, ok, status="manual", live_tap="correct" if ok else "incorrect"))
    n = 0
    for i in range(10):
        ok = i < words_ok
        out.append(result(lang, "B", i, ok, status=status, verified=v, errors=() if ok else (error_type,), hesitation=n < hesitate))
        n += 1
    if include_c:
        for i in range(10):
            ok = i < nonwords_ok
            wrong_index = i - nonwords_ok
            errs = () if ok else (("lexicalization",) if wrong_index < lex else (error_type,))
            out.append(result(lang, "C", i, ok, status=status, verified=v, errors=errs, hesitation=n < hesitate))
            n += 1
    duration = 40 / wcpm * 60
    out.append(result(lang, "D", 1, False, status=status, verified=v, words_total=42, words_correct=40, duration=duration))
    return out


def risk(results, grade=3):
    return compute_risk(results, grade, bank_counts=BANK)


def test_both_languages_ok_is_low_risk():
    r = risk(language("hi") + language("en"))
    assert r.level == "low_risk" and r.emoji == "🟢"
    assert r.languages["hi"].wcpm == 80.0


def test_weak_only_in_english_is_exposure_gap():
    r = risk(language("hi") + language("en", words_ok=3, nonwords_ok=4))
    assert r.level == "english_exposure_gap" and r.emoji == "🔵"
    assert any("English word accuracy 30%" in x for x in r.reasons)


def test_weak_in_both_with_pattern_needs_specialist():
    hi = language("hi", words_ok=6, nonwords_ok=3, lex=2, hesitate=10)
    en = language("en", words_ok=5, nonwords_ok=4, lex=1)
    r = risk(hi + en)
    assert r.level == "specialist_check" and r.emoji == "🔴"
    assert r.specific_pattern
    assert r.languages["hi"].lexicalizations == 2
    assert any("made-up words read as real words" in x for x in r.reasons)
    assert any("Read the made-up word" in x for x in r.reasons)


def test_weak_in_both_without_pattern_needs_reading_support():
    # weak only through slow passage reading, no error pattern
    r = risk(language("hi", wcpm=20) + language("en", wcpm=20))
    assert r.level == "reading_support" and r.emoji == "🟡"
    assert not r.specific_pattern


def test_weak_only_in_hindi_needs_hindi_support():
    r = risk(language("hi", words_ok=4) + language("en"))
    assert r.level == "hindi_support"


def test_unverified_english_is_provisional():
    r = risk(language("hi") + language("en", verified=False))
    assert r.level == "provisional"
    assert r.pending_verify == 21  # 10 words + 10 nonwords + passage
    assert r.languages["en"].pending
    assert any("verify 21 English items" in x for x in r.reasons)


def test_missing_hindi_nonwords_is_pending():
    r = risk(language("hi", include_c=False) + language("en"))
    assert r.level == "pending"
    assert r.languages["hi"].pending_sections == ["C"]


def test_teacher_verify_items_count_only_once_verified():
    hi = language("hi")
    for x in hi:
        if x.section == "C":
            x.status, x.correct = "teacher_verify", None
    r = risk(hi + language("en"))
    assert r.level == "pending"  # Hindi nonwords all waiting for the teacher
    for x in hi:
        if x.section == "C":
            record_verification(x, "correct")
    assert risk(hi + language("en")).level == "low_risk"


def test_conjunct_errors_alone_do_not_make_a_pattern():
    hi = language("hi", words_ok=5, nonwords_ok=5, error_type="conjunct_error")
    en = language("en", words_ok=5, nonwords_ok=5)
    r = risk(hi + en)
    assert r.languages["hi"].weighted_error_score < 0.5
    assert r.level == "reading_support"


def test_timing_counts_whatever_the_status():
    hi = language("hi", hesitate=20)
    for x in hi:
        if x.section in "BC":
            x.status, x.correct = "teacher_verify", None
    m = risk(hi + language("en")).languages["hi"]
    assert m.timing_rate == pytest.approx(20 / 30, abs=0.01)
    assert m.error_counts["hesitation"] == 20


def test_passage_errors_and_sound_game_timing_stay_out_of_pattern_score():
    hi = language("hi")
    hi.append(result("hi", "E", 1, False, start=5.0))
    hi[-2].errors += [ErrorLabel("omission", "x", None)] * 10  # passage
    m = risk(hi + language("en")).languages["hi"]
    assert m.weighted_error_score == 0.0 and "slow_start" not in m.error_counts


def test_grade_is_clamped_to_the_table():
    assert risk(language("hi") + language("en"), grade=9).languages["hi"].wcpm_min == 80
    assert risk(language("hi") + language("en"), grade=0).languages["hi"].wcpm_min == 20


def test_scoring_breakdown_is_on_the_report():
    r = risk(language("hi") + language("en"))
    assert r.scoring_breakdown["hi"]["live_tap_pct"] == pytest.approx(10 / 31 * 100, abs=0.1)
    assert "not clinically validated" in r.disclaimer


def test_reason_wording():
    hi = language("hi", words_ok=9, nonwords_ok=9, lex=1)
    for x in hi:
        for e in x.errors:
            if e.type == "lexicalization":
                e.target, e.heard = "पमीर", "पनीर"
    reasons = risk(hi + language("en")).reasons
    assert "1 matra confusion in Hindi" in reasons
    assert "Read the made-up word पमीर as पनीर" in reasons
