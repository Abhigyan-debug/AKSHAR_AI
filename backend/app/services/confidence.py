"""Confidence gate (see docs/scoring.md): decides whether an item is auto-scored, sent to
teacher verify, or scored by the teacher's live tap.

Thresholds are PROVISIONAL - see config/thresholds.json.
"""

from dataclasses import dataclass, field

from ..config import thresholds
from .normalize import normalize
from .transcribe import Segment

AUTO = "auto"
TEACHER_VERIFY = "teacher_verify"
MANUAL = "manual"


@dataclass
class Confidence:
    avg_logprob: float | None
    no_speech_prob: float | None
    low: bool
    reasons: list[str] = field(default_factory=list)


def _wrong_script(text: str, lang: str | None) -> bool:
    """A Hindi item heard in Latin letters (मोर -> "more"), or an English item
    heard in Devanagari: Whisper switched language, so the transcript can't be scored."""
    letters = [ch for ch in text if ch.isalpha() or "ऀ" <= ch <= "ॿ"]
    if not letters or lang not in ("hi", "en"):
        return False
    devanagari = sum("ऀ" <= ch <= "ॿ" for ch in letters)
    return devanagari == 0 if lang == "hi" else devanagari == len(letters)


def assess_confidence(segments: list[Segment], text: str, cfg: dict | None = None, lang: str | None = None) -> Confidence:
    c = (cfg or thresholds())["confidence"]
    logprob = min((s.avg_logprob for s in segments), default=None)
    no_speech = max((s.no_speech_prob for s in segments), default=None)
    reasons = []
    if not normalize(text):
        reasons.append("empty transcript")
    elif _wrong_script(text, lang):
        reasons.append("transcribed in the wrong script")
    if logprob is not None and logprob < c["min_avg_logprob"]:
        reasons.append(f"avg_logprob {logprob:.2f}")
    if no_speech is not None and no_speech > c["max_no_speech_prob"]:
        reasons.append(f"no_speech_prob {no_speech:.2f}")
    return Confidence(avg_logprob=logprob, no_speech_prob=no_speech, low=bool(reasons), reasons=reasons)


def item_status(scoring: str, confidence: Confidence) -> str:
    """manual items are live-tapped by the teacher and never reach the verify queue."""
    if scoring == MANUAL:
        return MANUAL
    return TEACHER_VERIFY if confidence.low else AUTO
