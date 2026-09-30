"""Loads backend/config/thresholds.json.

All values there are PROVISIONAL (calibrated on synthetic speech) - see the
file's _note. Re-tune on real recordings before trusting any result.
"""

import json
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
THRESHOLDS_PATH = BACKEND_DIR / "config" / "thresholds.json"
TESTS_DIR = BACKEND_DIR / "data" / "tests"


@lru_cache(maxsize=1)
def thresholds() -> dict:
    with open(THRESHOLDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_test(lang: str) -> dict:
    with open(TESTS_DIR / f"{lang}.json", encoding="utf-8") as f:
        return json.load(f)
