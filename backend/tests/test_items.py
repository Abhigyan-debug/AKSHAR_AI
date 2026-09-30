"""The item bank follows the rules in docs/test-content.md."""

import re
import unicodedata
from collections import Counter

import pytest

from app.config import load_test
from app.services.classify_rules import classify_item
from app.services.normalize import compact, normalize

LANGS = ("hi", "en")


@pytest.fixture(params=LANGS)
def bank(request):
    return request.param, load_test(request.param)["items"]


def test_sections_and_ids(bank):
    lang, items = bank
    assert Counter(i["section"] for i in items) == {"A": 10, "B": 10, "C": 10, "D": 1, "E": 5}
    ids = [i["id"] for i in items]
    assert len(ids) == len(set(ids))
    for i in items:
        assert i["id"].startswith(f"{lang}_{i['section']}_")
        assert unicodedata.normalize("NFC", i["text"]) == i["text"]
        assert i["scoring"] in ("auto", "manual")


def test_letters_are_live_tapped_in_both_languages(bank):
    _, items = bank
    assert all(i["scoring"] == "manual" for i in items if i["section"] == "A")


def test_english_scoring_rules():
    items = load_test("en")["items"]
    assert all(i["scoring"] == "manual" for i in items if i["section"] == "E")
    for i in items:
        if i["section"] == "C":
            assert len(re.findall(r"[aeiouy]+", i["text"])) == 2, f"{i['text']} is not two-syllable"
            assert i["scoring"] == "auto"
        if i["section"] == "B":
            assert i["scoring"] == "auto"  # short real words stay auto, behind the confidence gate


def test_nonwords(bank):
    lang, items = bank
    for i in items:
        if i["section"] == "C":
            assert i["is_nonword"]
        near = i.get("near_real")
        if near:
            assert normalize(near) != normalize(i["text"])
            assert compact(near) not in {compact(v) for v in i["accepted_variants"]}


def test_sound_game_has_prompts(bank):
    _, items = bank
    assert all(i.get("prompt") for i in items if i["section"] == "E")


def test_passage_word_count(bank):
    _, items = bank
    (passage,) = [i for i in items if i["section"] == "D"]
    assert len(passage["text"].split()) == passage["word_count"]
    assert 35 <= passage["word_count"] <= 45


def test_every_item_read_correctly_is_scored_correct(bank):
    lang, items = bank
    for i in items:
        assert classify_item(i, i["text"], lang).correct, i["id"]
        for v in i["accepted_variants"]:
            assert classify_item(i, v, lang).correct, (i["id"], v)


def test_every_near_real_reading_is_a_lexicalization(bank):
    lang, items = bank
    for i in items:
        if i.get("near_real"):
            errors = classify_item(i, i["near_real"], lang).errors
            assert [e.type for e in errors] == ["lexicalization"], i["id"]


def test_sound_game_is_live_tapped_in_both_languages(bank):
    _, items = bank
    assert all(i["scoring"] == "manual" for i in items if i["section"] == "E")
