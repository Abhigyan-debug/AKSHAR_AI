from app.services.timing import analyse_timing
from app.services.transcribe import Word
from tests.conftest import load_fixture


def test_v3_folds_pause_into_next_word(cfg):
    # Real v3 output: "jump" spans 1.62-6.34 s because the 3 s pause is folded in.
    t = analyse_timing(load_fixture("en_06_long_pause").words, "D", cfg)
    assert t.hesitation
    assert t.long_word == "jump" and t.max_word_s == 4.72
    assert t.gap_after is None


def test_hindi_pause_detected(cfg):
    t = analyse_timing(load_fixture("hi_09_long_pause").words, "D", cfg)
    assert t.hesitation and t.max_word_s > 4


def test_exactly_0_8s_is_not_longer_than_0_8(cfg):
    # Real v3 output: final word "mat." is 0.80 s (0.8000000000000007 before rounding).
    t = analyse_timing(load_fixture("en_05_skip_word").words, "D", cfg)
    assert t.max_word_s == 0.8
    assert not t.hesitation


def test_gap_counts_as_hesitation(cfg):
    words = [Word("tom", 0.5, 0.8), Word("can", 0.8, 1.1), Word("jump", 2.2, 2.6)]
    t = analyse_timing(words, "D", cfg)
    assert t.hesitation and t.gap_after == "can" and t.max_gap_s == 1.1


def test_slow_start_and_start_latency(cfg):
    t = analyse_timing([Word("पमीर", 3.4, 3.9)], "C", cfg)
    assert t.start_latency_s == 3.4 and t.slow_start
    assert not analyse_timing([Word("पमीर", 1.0, 1.5)], "C", cfg).slow_start


def test_slow_decoding_per_section(cfg):
    words = [Word("पमीर", 0.5, 0.9), Word("पमीर", 5.0, 5.8)]
    assert analyse_timing(words, "C", cfg).slow_decoding       # 5.3 s > 5.0
    assert not analyse_timing(words, "D", cfg).slow_decoding   # no limit for passages


def test_no_words():
    t = analyse_timing([], "C")
    assert t.start_latency_s is None and not t.hesitation and t.flags() == []


def test_flags_have_details(cfg):
    t = analyse_timing(load_fixture("en_06_long_pause").words, "D", cfg)
    kinds = dict(t.flags())
    assert "jump" in kinds["hesitation"]


def test_single_word_items_have_no_hesitation_rule(cfg):
    # e2e 2026-09-30: correct TTS readings of 3-4 akshara words took 0.82-0.88 s.
    words = [Word("लोकुस", 0.02, 0.90)]
    t = analyse_timing(words, "C", cfg, multi_word=False)
    assert not t.hesitation and t.flags() == []
    # a repeated attempt with a pause is still not "hesitation" for a single item...
    t = analyse_timing([Word("पम", 0.5, 0.8), Word("पमीर", 2.5, 3.1)], "C", cfg, multi_word=False)
    assert not t.hesitation
    # ...but a slow start still counts
    assert analyse_timing([Word("पमीर", 3.2, 3.8)], "C", cfg, multi_word=False).slow_start
