"""Timing flags from word timestamps (see docs/scoring.md).

whisper-large-v3 usually folds a pause into the *next* word's timestamp span
instead of leaving a gap, so in multi-word reading hesitation = a long gap OR
a long word. Single-word items have no next word, and a 3-4 akshara word
simply takes ~0.9 s to say (e2e, 2026-09-30), so for them hesitation is off:
slow_start and slow_decoding cover their timing.
Timestamps are rounded to Whisper's 10 ms resolution so 0.80 s isn't
"longer than 0.8". Thresholds are PROVISIONAL - see config/thresholds.json.
"""

from dataclasses import dataclass

from ..config import thresholds
from .transcribe import Word


@dataclass
class Timing:
    start_latency_s: float | None = None
    duration_s: float | None = None
    max_gap_s: float = 0.0
    gap_after: str | None = None
    max_word_s: float = 0.0
    long_word: str | None = None
    hesitation: bool = False
    slow_start: bool = False
    slow_decoding: bool = False

    def flags(self) -> list[tuple[str, str]]:
        """(error_type, detail) for each timing flag that fired."""
        out = []
        if self.hesitation:
            parts = []
            if self.gap_after is not None and self.max_gap_s:
                parts.append(f"{self.max_gap_s:.2f}s gap after '{self.gap_after}'")
            if self.long_word is not None:
                parts.append(f"'{self.long_word}' took {self.max_word_s:.2f}s")
            out.append(("hesitation", "; ".join(parts)))
        if self.slow_start:
            out.append(("slow_start", f"started after {self.start_latency_s:.2f}s"))
        if self.slow_decoding:
            out.append(("slow_decoding", f"took {self.duration_s:.2f}s"))
        return out


def analyse_timing(words: list[Word], section: str | None = None, cfg: dict | None = None, *, multi_word: bool = True) -> Timing:
    t = (cfg or thresholds())["timing"]
    if not words:
        return Timing()
    latency = round(words[0].start, 2)
    duration = round(words[-1].end - words[0].start, 2)

    max_gap, gap_after = 0.0, None
    for prev, cur in zip(words, words[1:]):
        gap = round(cur.start - prev.end, 2)
        if gap > max_gap:
            max_gap, gap_after = gap, prev.word
    longest = max(words, key=lambda w: w.end - w.start)
    max_word = round(longest.end - longest.start, 2)

    long_gap = multi_word and max_gap >= t["hesitation_gap_s"]
    long_word = multi_word and max_word > t["long_word_s"]
    slow_limit = t.get("slow_decoding_s", {}).get(section) if section else None
    return Timing(
        start_latency_s=latency,
        duration_s=duration,
        max_gap_s=max_gap,
        gap_after=gap_after if long_gap else None,
        max_word_s=max_word,
        long_word=longest.word if long_word else None,
        hesitation=long_gap or long_word,
        slow_start=latency >= t["slow_start_s"],
        slow_decoding=slow_limit is not None and duration > slow_limit,
    )
