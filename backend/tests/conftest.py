"""Fixtures are real whisper-large-v3 verbose_json responses from the
2026-09-30 spike (TTS clips), copied from spike/results/."""

import json
from pathlib import Path

import pytest

from app.config import thresholds
from app.services.transcribe import Segment, Transcript, Word, parse_verbose_json

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Transcript:
    with open(FIXTURES / f"{name}.json", encoding="utf-8") as f:
        return parse_verbose_json(json.load(f), model="whisper-large-v3")


def make_transcript(text: str, words=(), avg_logprob: float = -0.2, no_speech_prob: float = 0.05) -> Transcript:
    """A synthetic transcript; `words` is a list of (word, start, end)."""
    return Transcript(
        text=text,
        words=[Word(w, s, e) for w, s, e in words],
        segments=[Segment(text, 0.0, 2.0, avg_logprob, no_speech_prob)],
    )


@pytest.fixture
def cfg() -> dict:
    return thresholds()
