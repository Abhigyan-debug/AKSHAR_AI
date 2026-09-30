import pytest

from app.services.akshara import HALANT, INHERENT, aksharas, split_aksharas, units


@pytest.mark.parametrize(
    "word, expected",
    [
        ("कमल", ["क", "म", "ल"]),
        ("बिल्ली", ["बि", "ल्ली"]),
        ("स्कूल", ["स्कू", "ल"]),
        ("क्षत्रिय", ["क्ष", "त्रि", "य"]),
        ("हिंदी", ["हिं", "दी"]),
        ("आम", ["आ", "म"]),
        ("पढ़ना", ["प", "ढ़", "ना"]),
        ("हँसना", ["हँ", "स", "ना"]),
        ("दुःख", ["दुः", "ख"]),
    ],
)
def test_split(word, expected):
    assert split_aksharas(word) == expected


def test_split_skips_spaces_and_punctuation_is_its_own_chunk():
    assert split_aksharas("राम है।") == ["रा", "म", "है", "।"]


def test_akshara_parts():
    ak = aksharas("स्कूल")[0]
    assert ak.consonants == ("स", "क")
    assert ak.vowel == "uu"
    assert ak.is_conjunct
    assert aksharas("हिं")[0].nasal
    assert aksharas("आ")[0].consonants == () and aksharas("आ")[0].vowel == "aa"
    assert aksharas("ज़")[0].consonants == ("ज़",)


def test_units_flatten_conjuncts():
    us = units("स्कूल")
    assert [u.sound for u in us] == [("स", HALANT, False), ("क", "uu", False), ("ल", INHERENT, False)]
    assert [u.in_cluster for u in us] == [True, True, False]


def test_word_final_virama_is_dead_consonant():
    assert units("जगत्")[-1].vowel == HALANT
