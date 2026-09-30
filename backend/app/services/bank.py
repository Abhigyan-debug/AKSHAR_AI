"""The item bank (data/tests/{hi,en}.json), loaded once."""

from functools import lru_cache

from ..config import load_test

LANGS = ("hi", "en")


@lru_cache(maxsize=1)
def items() -> dict[str, dict]:
    out = {}
    for lang in LANGS:
        for item in load_test(lang)["items"]:
            out[item["id"]] = {**item, "lang": lang}
    return out


def lang_of(item_id: str) -> str | None:
    item = items().get(item_id)
    return item["lang"] if item else None


@lru_cache(maxsize=2)
def known_words(lang: str) -> tuple[str, ...]:
    """Real words a nonword could be read as: the test's real words plus every near_real."""
    words = set()
    for item in items().values():
        if item["lang"] != lang:
            continue
        if item["section"] == "B":
            words.add(item["text"])
        if item.get("near_real"):
            words.add(item["near_real"])
    return tuple(sorted(words))


def section_counts() -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {lang: {} for lang in LANGS}
    for item in items().values():
        c = counts[item["lang"]]
        c[item["section"]] = c.get(item["section"], 0) + 1
    return counts
