import pytest

from app.services.classify_rules import classify_item, classify_word_en, classify_word_hi


def types(errors):
    return [e.type for e in errors]


# --- Hindi word rules ---------------------------------------------

@pytest.mark.parametrize(
    "target, heard, expected_type, detail",
    [
        ("मीठा", "मिठा", "matra_confusion", "ी→ि"),
        ("दिन", "दीन", "matra_confusion", "ि→ी"),
        ("कमल", "कमला", "matra_confusion", "(no matra)→ा"),
        ("हंस", "हस", "matra_confusion", "ं dropped"),
        ("वजन", "बजन", "visual_akshara_swap", "व→ब"),
        ("भालू", "मालू", "visual_akshara_swap", "भ→म"),
        ("खाना", "रवाना", "visual_akshara_swap", "ख↔रव"),
        ("खाना", "काना", "aspiration_error", "ख→क"),
        ("धीमक", "दीमक", "aspiration_error", "ध→द"),
        ("कमल", "मकल", "transposition", "कम→मक"),
        ("बकरी", "बगीचा", "first_letter_guess", "starts with ब"),
    ],
)
def test_hindi_word_errors(target, heard, expected_type, detail):
    errors = classify_word_hi(target, heard)
    assert types(errors) == [expected_type]
    assert errors[0].detail == detail


@pytest.mark.parametrize(
    "target, heard, detail",
    [
        ("स्कूल", "सकूल", "split"),
        ("प्यास", "पास", "simplified"),
        ("सकूल", "स्कूल", "added"),
    ],
)
def test_conjunct_errors_are_low_confidence(target, heard, detail):
    errors = classify_word_hi(target, heard)
    assert types(errors) == ["conjunct_error"]
    assert errors[0].detail == detail
    assert errors[0].low_confidence


def test_gemination_is_normalized_away():
    assert classify_word_hi("बिल्ली", "बिली") == []


def test_whole_word_swap_is_one_label():
    assert types(classify_word_hi("है", "था")) == ["unclassified"]


def test_akshara_omission_and_addition():
    assert types(classify_word_hi("कमल", "कल")) == ["omission"]
    assert types(classify_word_hi("कमल", "कमलम")) == ["addition"]


# --- English word rules --------------------------------------------------------

@pytest.mark.parametrize(
    "target, heard, expected_type",
    [
        ("bed", "ded", "letter_reversal"),
        ("dig", "big", "letter_reversal"),
        ("was", "saw", "word_reversal"),
        ("from", "form", "transposition"),
        ("cat", "cot", "vowel_error"),
        ("frog", "fog", "omission"),
        ("cat", "cats", "addition"),
        ("jump", "jelly", "first_letter_guess"),
        ("was", "song", "unclassified"),
    ],
)
def test_english_word_errors(target, heard, expected_type):
    assert types(classify_word_en(target, heard)) == [expected_type]


# --- Items ---------------------------------------------------------------------

PAMIR = {"id": "hi_C_01", "section": "C", "text": "पमीर", "is_nonword": True, "near_real": "पनीर", "accepted_variants": []}
NAPKIM = {"id": "en_C_01", "section": "C", "text": "napkim", "is_nonword": True, "near_real": "napkin", "accepted_variants": []}


def test_correct_reading():
    c = classify_item(PAMIR, "पमीर।", "hi")
    assert c.correct and not c.errors and c.words_correct == 1


def test_lexicalization_near_real():
    c = classify_item(PAMIR, "पनीर", "hi")
    assert not c.correct
    assert types(c.errors) == ["lexicalization"]
    assert types(classify_item(NAPKIM, "Napkin,", "en").errors) == ["lexicalization"]


def test_lexicalization_known_words():
    item = {**PAMIR, "near_real": None}
    assert types(classify_item(item, "कमल", "hi", known_words=["कमल"]).errors) == ["lexicalization"]
    assert types(classify_item(item, "कमल", "hi").errors) != ["lexicalization"]


def test_accepted_variant_is_correct():
    item = {"id": "hi_A_08", "section": "A", "text": "ष", "accepted_variants": ["श"]}
    assert classify_item(item, "श", "hi").correct


def test_split_nonword_is_correct():
    item = {"id": "en_C_08", "section": "C", "text": "mistop", "is_nonword": True, "accepted_variants": []}
    assert classify_item(item, "Mis top.", "en").correct


def test_self_correction_on_single_word():
    c = classify_item(PAMIR, "पन पमीर", "hi")
    assert c.correct
    assert types(c.errors) == ["self_correction"]
    c = classify_item(PAMIR, "पम पनीर", "hi")
    assert not c.correct
    assert types(c.errors) == ["lexicalization", "self_correction"]


def test_empty_transcript_is_skipped():
    c = classify_item(PAMIR, "", "hi")
    assert c.skipped and not c.correct and c.errors == []


def test_sound_game_is_right_or_wrong_only():
    item = {"id": "hi_E_01", "section": "E", "text": "मल", "accepted_variants": []}
    assert classify_item(item, "मल", "hi").correct
    c = classify_item(item, "कमल", "hi")
    assert not c.correct and c.errors == []


def test_passage_skip_repeat_and_substitution():
    item = {"id": "hi_D_x", "section": "D", "text": "सोनू हर सुबह स्कूल जाता है"}
    c = classify_item(item, "सोनू सोनू हर स सुबह स्कूल जाता था", "hi")
    assert not c.correct
    assert c.words_total == 6 and c.words_correct == 5
    assert types(c.errors) == ["self_correction", "self_correction", "unclassified"]

    c = classify_item(item, "सोनू हर स्कूल जाता है", "hi")
    assert types(c.errors) == ["omission"] and c.errors[0].target == "सुबह"
    assert c.words_correct == 5


def test_passage_with_only_self_corrections_is_correct():
    item = {"id": "en_D_x", "section": "D", "text": "the cat sat"}
    c = classify_item(item, "the the cat sat", "en")
    assert c.correct and c.words_correct == 3


def test_split_transcript_is_one_reading_not_a_self_correction():
    # Real v3 output on TTS: "drumpet" -> "Drum Pit", "mistop" -> "Missed stop."
    item = {"id": "en_C_04", "section": "C", "text": "drumpet", "is_nonword": True, "near_real": "trumpet", "accepted_variants": []}
    c = classify_item(item, "Drum Pit", "en")
    assert "self_correction" not in types(c.errors)
    assert types(c.errors) == ["vowel_error"]
    item = {"id": "en_C_08", "section": "C", "text": "mistop", "is_nonword": True, "accepted_variants": []}
    assert "self_correction" not in types(classify_item(item, "Missed stop.", "en").errors)


def test_false_start_on_a_different_akshara_is_still_a_retry():
    c = classify_item(PAMIR, "पन पनीर", "hi")
    assert types(c.errors) == ["lexicalization", "self_correction"]
