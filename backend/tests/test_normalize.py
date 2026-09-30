import pytest

from app.services.normalize import compact, is_single_word, matches, normalize


@pytest.mark.parametrize(
    "a, b",
    [
        ("गुब्बारा", "गुबारा"),      # gemination
        ("हिन्दी", "हिंदी"),         # nasal consonant + virama -> anusvara
        ("हँस", "हंस"),              # chandrabindu -> anusvara
        ("ज़मीन", "जमीन"),           # nukta dropped
        ("सोनू है।", "सोनू है"),     # danda
        ("Blink.", "blink"),
        ("क्‍ष", "क्ष"),        # zero-width joiner dropped, word not split
    ],
)
def test_spelling_variants_compare_equal(a, b):
    assert normalize(a) == normalize(b)


@pytest.mark.parametrize(
    "a, b",
    [
        ("मीठा", "मिठा"),   # matra error
        ("स्कूल", "सकूल"),  # conjunct error
        ("खाना", "काना"),   # aspiration error
        ("पढ़ना", "पढना"),  # ड़/ढ़ keep their nukta
        ("बड़ा", "बडा"),
    ],
)
def test_real_errors_stay_distinct(a, b):
    assert normalize(a) != normalize(b)


def test_matches_uses_accepted_variants():
    assert matches("श", "ष", ["श"])
    assert not matches("श", "ष")


def test_single_word_items_ignore_spaces():
    assert matches("mis top", "mistop")
    assert compact("mis top") == "mistop"
    assert is_single_word("पमीर") and not is_single_word("सोनू हर")


def test_multi_word_items_keep_spaces():
    assert matches("The cat sat.", "the cat sat")
    assert not matches("thecat sat", "the cat sat")


def test_empty_transcript_never_matches():
    assert not matches("", "पमीर")
    assert not matches("।", "पमीर")
