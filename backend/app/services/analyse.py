"""One item: transcript -> result, plus teacher decisions and the report's
scoring breakdown (see docs/scoring.md).

Status is set once by the pipeline and never changes:
  auto            rules decide; Hindi counts at once, English only once verified
  teacher_verify  low confidence; counts only once a teacher verifies it
  manual          scored by the teacher's live tap; never reaches the verify queue
A teacher's confirmation sets `verified` instead of changing the status, so the
breakdown can still say how many items were auto-scored vs sent to verify.
"""

from dataclasses import dataclass, field

from ..config import thresholds
from .classify_rules import ErrorLabel, WordPair, classify_item
from .confidence import AUTO, MANUAL, TEACHER_VERIFY, Confidence, assess_confidence, item_status
from .normalize import is_single_word
from .timing import Timing, analyse_timing
from .transcribe import Transcript

TAPS = ("correct", "incorrect", "skipped")
TIMING_TYPES = ("hesitation", "slow_start", "slow_decoding")


@dataclass
class ItemResult:
    item_id: str
    lang: str
    section: str
    status: str
    transcript: str
    correct: bool | None            # None until the teacher taps / verifies, when that is needed
    suggested_correct: bool         # what the rules say (shown in the verify queue)
    skipped: bool
    errors: list[ErrorLabel]
    timing: Timing
    confidence: Confidence
    words_total: int
    words_correct: int
    pairs: list[WordPair] = field(default_factory=list)
    live_tap: str | None = None
    verified: bool = False


def _apply_tap(result: ItemResult, tap: str) -> None:
    if tap not in TAPS:
        raise ValueError(f"tap must be one of {TAPS}, got {tap!r}")
    result.correct = tap == "correct"
    result.skipped = tap == "skipped"


def analyse_item(
    item: dict,
    lang: str,
    transcript: Transcript,
    *,
    live_tap: str | None = None,
    known_words=(),
    cfg: dict | None = None,
) -> ItemResult:
    cfg = cfg or thresholds()
    conf = assess_confidence(transcript.segments, transcript.text, cfg, lang)
    status = item_status(item.get("scoring", AUTO), conf)
    timing = analyse_timing(transcript.words, item.get("section"), cfg, multi_word=not is_single_word(item["text"]))
    cls = classify_item(item, transcript.text, lang, known_words)
    # Timing counts whatever the status: it doesn't depend on the transcript being right.
    timing_errors = [ErrorLabel(kind, item["text"], None, detail) for kind, detail in timing.flags()]

    result = ItemResult(
        item_id=item["id"],
        lang=lang,
        section=item.get("section", ""),
        status=status,
        transcript=transcript.text,
        correct=cls.correct if status == AUTO else None,
        suggested_correct=cls.correct,
        skipped=cls.skipped,
        # Manual items: the transcript is evidence only; the teacher's tap is the result.
        errors=timing_errors if status == MANUAL else cls.errors + timing_errors,
        timing=timing,
        confidence=conf,
        words_total=cls.words_total,
        words_correct=cls.words_correct,
        pairs=cls.pairs,
    )
    if status == MANUAL and live_tap is not None:
        record_live_tap(result, live_tap)
    return result


def record_live_tap(result: ItemResult, tap: str) -> None:
    """Teacher's correct / incorrect / skipped tap during reading (manual items)."""
    if result.status != MANUAL:
        raise ValueError("live tap is only for manual items")
    result.live_tap = tap
    _apply_tap(result, tap)


def record_verification(result: ItemResult, tap: str, words_correct: int | None = None) -> None:
    """Teacher's decision from the verify queue (teacher_verify items, English auto
    items) or a manual override of an auto item.

    Single items: the tap is the child's reading (correct / incorrect / skipped).
    Passage (section D): "correct" = the AI heard it right, keep its word-level
    scoring; "incorrect" = the AI heard it wrong, and `words_correct` is the
    teacher's own count; "skipped" = the child didn't read it.
    """
    if result.status == MANUAL:
        raise ValueError("manual items are live-tapped, not verified")
    if tap not in TAPS:
        raise ValueError(f"tap must be one of {TAPS}, got {tap!r}")
    timing_only = [e for e in result.errors if e.type in TIMING_TYPES]

    if result.section == "D":
        if tap == "incorrect":
            if words_correct is None or not 0 <= words_correct <= result.words_total:
                raise ValueError(f"words_correct (0-{result.words_total}) is required when the AI heard the passage wrong")
            result.words_correct = words_correct
            result.correct = words_correct == result.words_total
            result.errors = timing_only  # word-level errors came from a wrong transcript
            result.skipped = False
        elif tap == "correct":
            result.correct = result.suggested_correct
            result.skipped = False
        else:
            result.correct, result.skipped = False, True
        result.verified = True
        return

    result.verified = True
    _apply_tap(result, tap)
    if tap == "correct":
        # The teacher heard a correct reading, so rule errors came from a mis-hearing.
        result.errors = timing_only


def is_counted(result: ItemResult) -> bool:
    """Whether the item counts toward risk."""
    if result.status == MANUAL:
        return result.live_tap is not None
    if result.status == TEACHER_VERIFY:
        return result.verified
    return result.lang == "hi" or result.verified


def awaiting_verification(result: ItemResult) -> bool:
    """In the verify queue and not yet decided."""
    if result.verified or result.status == MANUAL:
        return False
    return result.status == TEACHER_VERIFY or result.lang == "en"


def _breakdown(results: list[ItemResult]) -> dict:
    n = len(results)

    def pct(k: int) -> float:
        return round(100 * k / n, 1) if n else 0.0

    auto = sum(r.status == AUTO for r in results)
    verify = sum(r.status == TEACHER_VERIFY for r in results)
    manual = sum(r.status == MANUAL for r in results)
    return {
        "items": n,
        "auto_pct": pct(auto),
        "teacher_verify_pct": pct(verify),
        "live_tap_pct": pct(manual),
        "pending_verify": sum(awaiting_verification(r) for r in results),
    }


def scoring_breakdown(results: list[ItemResult]) -> dict:
    """% auto-scored vs sent to teacher verify vs live-tapped, per language and overall."""
    out = {lang: _breakdown([r for r in results if r.lang == lang]) for lang in sorted({r.lang for r in results})}
    out["overall"] = _breakdown(results)
    return out
