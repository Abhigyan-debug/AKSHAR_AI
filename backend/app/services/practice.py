"""Practice games (see docs/practice.md): content and per-child recommendations.

Recommendations come from the child's report: each game targets one error
pattern, and games whose pattern showed up most come first. No child data
leaves this function except the ordered list of game ids.
"""

import json
from functools import lru_cache

from ..config import BACKEND_DIR

PRACTICE_PATH = BACKEND_DIR / "data" / "practice.json"
GAME_IDS = ("matra", "breath", "twins", "builder", "mirror", "readalong")

# Which error types each game practises (names from docs/scoring.md).
TARGETS = {
    "matra": {"hi": ("matra_confusion",)},
    "breath": {"hi": ("aspiration_error",)},
    "twins": {"hi": ("visual_akshara_swap",)},
    "builder": {"hi": ("lexicalization", "first_letter_guess", "conjunct_error", "omission", "addition"), "en": ("lexicalization",)},
    "mirror": {"en": ("letter_reversal", "word_reversal")},
    "readalong": {"hi": ("hesitation", "slow_start", "slow_decoding"), "en": ("hesitation", "slow_start", "slow_decoding")},
}


@lru_cache(maxsize=1)
def content() -> dict:
    with open(PRACTICE_PATH, encoding="utf-8") as f:
        return json.load(f)


def recommend(metrics: dict, risk_level: str) -> list[str]:
    """Game ids ordered by how often the child made the error each game targets.
    Games with no matching errors are left out; an English exposure gap adds
    the English games; a slow passage adds the read-along."""
    scores: dict[str, float] = {}
    for game, by_lang in TARGETS.items():
        n = 0
        for lang, types in by_lang.items():
            counts = (metrics.get(lang) or {}).get("error_counts") or {}
            n += sum(counts.get(t, 0) for t in types)
        if n:
            scores[game] = n
    for lang in ("hi", "en"):
        m = metrics.get(lang) or {}
        if m.get("wcpm") is not None and m.get("wcpm_min") and m["wcpm"] < m["wcpm_min"]:
            scores["readalong"] = scores.get("readalong", 0) + 2
    if risk_level == "english_exposure_gap":
        scores["mirror"] = scores.get("mirror", 0) + 1
        scores["readalong"] = scores.get("readalong", 0) + 1
    return sorted(scores, key=lambda g: (-scores[g], GAME_IDS.index(g)))
