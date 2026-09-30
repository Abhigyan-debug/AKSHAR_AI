"""Practice games: content checked with the rule engine's own Devanagari
knowledge, no overlap with the screening test, and per-child recommendations."""

import unicodedata

from fastapi.testclient import TestClient

from app.config import load_test
from app.services.akshara import split_aksharas, units
from app.services.classify_rules import ASPIRATION_PAIRS_HI, VISUAL_PAIRS_HI
from app.services.normalize import compact
from app.services.practice import GAME_IDS, content, recommend
from tests.test_api import client, llm, new_child, new_session, read_everything_correctly, upload  # noqa: F401  (client/llm are fixtures)

GAMES = content()["games"]


def all_practice_words() -> list[str]:
    words = [w for pair in GAMES["matra"]["pairs"] + GAMES["breath"]["pairs"] for w in pair]
    words += [w["word"] for w in GAMES["builder"]["words"]]
    words += GAMES["mirror"]["words"]
    return words


def test_everything_is_nfc():
    for w in all_practice_words():
        assert unicodedata.normalize("NFC", w) == w, w
    for s in GAMES["readalong"]["stories"]:
        for line in s["lines"]:
            assert unicodedata.normalize("NFC", line) == line


def test_matra_pairs_differ_only_in_one_vowel_sign():
    for a, b in GAMES["matra"]["pairs"]:
        ua, ub = units(a), units(b)
        assert len(ua) == len(ub), (a, b)
        diff = [(x, y) for x, y in zip(ua, ub) if x.sound != y.sound]
        assert len(diff) == 1, (a, b)
        x, y = diff[0]
        assert x.consonant == y.consonant and x.vowel != y.vowel, (a, b)


def test_breath_pairs_differ_only_in_aspiration():
    for a, b in GAMES["breath"]["pairs"]:
        ua, ub = units(a), units(b)
        diff = [(x, y) for x, y in zip(ua, ub) if x.sound != y.sound]
        assert len(ua) == len(ub) and len(diff) == 1, (a, b)
        x, y = diff[0]
        assert x.vowel == y.vowel and frozenset((x.consonant, y.consonant)) in ASPIRATION_PAIRS_HI, (a, b)


def test_twins_are_look_alike_pairs():
    for pair in GAMES["twins"]["pairs"]:
        assert frozenset(pair) in VISUAL_PAIRS_HI, pair


def test_builder_tiles_spell_the_word():
    for w in GAMES["builder"]["words"]:
        assert split_aksharas(w["word"]) == w["tiles"], w["word"]
        for d in w["distractors"]:
            assert len(split_aksharas(d)) == 1 and d not in w["tiles"], (w["word"], d)


def test_mirror_words_start_with_a_mirror_letter():
    for w in GAMES["mirror"]["words"]:
        assert w.isalpha() and w.islower() and w[0] in "bdpq", w


def test_practice_never_reuses_test_items():
    """Practising test items at home would spoil a re-screen (PRODUCT.md)."""
    test_words, passage_lines = set(), []
    for lang in ("hi", "en"):
        for item in load_test(lang)["items"]:
            if item["section"] == "D":
                passage_lines += [compact(x) for x in item["text"].replace("।", ".").split(".") if x.strip()]
                continue
            if item["section"] == "A":
                continue  # single letters are the alphabet itself
            for w in [item["text"], item.get("near_real") or "", *item.get("accepted_variants", [])]:
                if w:
                    test_words.add(compact(w))
            for w in (item.get("prompt") or "").replace("'", " ").split():
                test_words.add(compact(w))
    reused = [w for w in all_practice_words() if compact(w) in test_words]
    assert reused == [], reused
    for s in GAMES["readalong"]["stories"]:
        for line in s["lines"]:
            assert compact(line) not in passage_lines, line


def test_recommendations_follow_the_childs_errors():
    metrics = {
        "hi": {"error_counts": {"matra_confusion": 5, "aspiration_error": 2, "lexicalization": 1}, "wcpm": 60, "wcpm_min": 50},
        "en": {"error_counts": {"letter_reversal": 3}, "wcpm": 60, "wcpm_min": 50},
    }
    assert recommend(metrics, "specialist_check") == ["matra", "mirror", "breath", "builder"]


def test_slow_reading_and_english_gap_recommendations():
    slow = {"hi": {"error_counts": {}, "wcpm": 20, "wcpm_min": 50}, "en": {"error_counts": {}}}
    assert recommend(slow, "reading_support") == ["readalong"]
    gap = {"hi": {"error_counts": {}}, "en": {"error_counts": {}}}
    assert recommend(gap, "english_exposure_gap") == ["mirror", "readalong"]
    assert recommend(gap, "low_risk") == []
    assert set(GAME_IDS) == set(GAMES)


def test_practice_endpoints(client):  # noqa: F811
    public = TestClient(client.app)
    assert public.get("/api/practice").status_code == 200  # no token needed
    child = new_child(client)
    sid = new_session(client, child["id"])
    read_everything_correctly(client, sid)
    upload(client, sid, "hi_B_02", "पिला")  # a matra slip
    token = client.post(f"/api/sessions/{sid}/finish").json()["report"]["parent_token"]
    view = public.get(f"/api/parent/{token}").json()
    assert view["ready"] is False and view["practice"] == []  # provisional: English not confirmed yet
    report = client.get(f"/api/children/{child['id']}/report").json()
    for item in report["items"]:
        if item["awaiting_verification"]:
            client.patch(f"/api/results/{item['id']}", json={"decision": "correct"})
    view = public.get(f"/api/parent/{token}").json()
    assert view["ready"] and view["practice"][0] == "matra"
