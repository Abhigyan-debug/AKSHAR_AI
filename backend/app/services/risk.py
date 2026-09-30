"""Risk logic (see docs/scoring.md): deterministic and explainable.

Input: every ItemResult of one session, the child's grade and the item bank.
Only items that count (analyse.is_counted) feed accuracies and rule errors;
timing flags count for every item that has timestamps.

Scope decisions (also in docs/scoring.md):
  - Rule errors and timing feed the pattern score from the single-item
    sections A, B, C only. The passage (D) is measured by WCPM, so its
    word-level errors aren't counted twice; the sound game (E) involves
    thinking time, so its timing isn't a reading signal.
  - WCPM = passage words correct / (last word end - first word start).

Thresholds are PROVISIONAL and illustrative - see config/thresholds.json.
"""

from dataclasses import asdict, dataclass, field

from ..config import load_test, thresholds
from .analyse import TIMING_TYPES, ItemResult, awaiting_verification, is_counted, scoring_breakdown

SINGLE_ITEM_SECTIONS = ("A", "B", "C")
SECTION_NAMES = {"A": "letters", "B": "words", "C": "nonwords", "D": "passage", "E": "sound game"}
LANG_NAMES = {"hi": "Hindi", "en": "English"}

LEVELS = {
    "low_risk": ("🟢", "Low risk"),
    "english_exposure_gap": ("🔵", "English exposure gap → English support"),
    "specialist_check": ("🔴", "Needs specialist check"),
    "reading_support": ("🟡", "Needs reading support"),
    "hindi_support": ("🟡", "Needs Hindi reading support (check home language)"),
    "provisional": ("⏳", "Provisional: verify English items to finish"),
    "pending": ("⏳", "Pending teacher check"),
}
DISCLAIMER = "Screener, not a diagnosis. Thresholds are illustrative and not clinically validated - for demo."


@dataclass
class LanguageMetrics:
    lang: str
    accuracy: dict[str, float | None]      # section -> share correct among counted items
    coverage: dict[str, float]             # section -> counted / items in the test
    wcpm: float | None
    wcpm_min: int
    lexicalizations: int
    lexicalization_examples: list[str]
    timing_rate: float
    weighted_error_score: float
    error_counts: dict[str, int]
    pending_sections: list[str]
    pending: bool
    weak: bool
    weak_reasons: list[str] = field(default_factory=list)

    @property
    def acc_letters(self):
        return self.accuracy.get("A")

    @property
    def acc_words(self):
        return self.accuracy.get("B")

    @property
    def acc_nonwords(self):
        return self.accuracy.get("C")


@dataclass
class RiskReport:
    level: str
    emoji: str
    label: str
    languages: dict[str, LanguageMetrics]
    specific_pattern: bool
    reasons: list[str]
    scoring_breakdown: dict
    pending_verify: int
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict:
        return asdict(self)


def _weight(error_type: str, lang: str, cfg: dict) -> float:
    weights = cfg["error_weights"]
    lang_weights = weights.get(lang, {})
    if error_type in lang_weights:
        return float(lang_weights[error_type])
    return float(weights["default"].get(error_type, 0.0))


def _grade_min(grade: int, cfg: dict) -> int:
    table = {int(k): v for k, v in cfg["risk"]["wcpm_min_by_grade"].items()}
    g = min(max(grade, min(table)), max(table))
    return int(table[g])


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{round(100 * x)}%"


def language_metrics(results: list[ItemResult], lang: str, grade: int, bank_counts: dict[str, int], cfg: dict) -> LanguageMetrics:
    r = cfg["risk"]
    mine = [x for x in results if x.lang == lang]
    counted = [x for x in mine if is_counted(x)]

    accuracy: dict[str, float | None] = {}
    coverage: dict[str, float] = {}
    for section in ("A", "B", "C", "E"):
        in_section = [x for x in counted if x.section == section]
        accuracy[section] = (sum(bool(x.correct) for x in in_section) / len(in_section)) if in_section else None
        total = bank_counts.get(section, 0)
        coverage[section] = len(in_section) / total if total else 0.0

    wcpm = None
    passage = next((x for x in counted if x.section == "D" and not x.skipped), None)
    if passage and passage.timing.duration_s:
        wcpm = round(passage.words_correct / (passage.timing.duration_s / 60), 1)

    single_counted = [x for x in counted if x.section in SINGLE_ITEM_SECTIONS]
    single_timed = [x for x in mine if x.section in SINGLE_ITEM_SECTIONS and x.timing.start_latency_s is not None]

    error_counts: dict[str, int] = {}
    score = 0.0
    lex_examples = []
    for x in single_counted:
        for e in x.errors:
            if e.type in TIMING_TYPES:
                continue
            error_counts[e.type] = error_counts.get(e.type, 0) + 1
            score += _weight(e.type, lang, cfg)
            if e.type == "lexicalization" and len(lex_examples) < 3:
                lex_examples.append(f"{e.target} → {e.heard}")
    timed_flagged = 0
    for x in single_timed:
        flags = [e.type for e in x.errors if e.type in TIMING_TYPES]
        if "hesitation" in flags or "slow_start" in flags:
            timed_flagged += 1
        for t in flags:
            error_counts[t] = error_counts.get(t, 0) + 1
            score += _weight(t, lang, cfg)

    pending_sections = [s for s in ("B", "C") if coverage[s] < r["section_min_coverage"]]
    wcpm_min = _grade_min(grade, cfg)

    weak_reasons = []
    if accuracy["B"] is not None and accuracy["B"] < r["weak_acc_words"]:
        weak_reasons.append(f"{LANG_NAMES[lang]} word accuracy {_pct(accuracy['B'])} (below {_pct(r['weak_acc_words'])})")
    if accuracy["C"] is not None and accuracy["C"] < r["weak_acc_nonwords"]:
        weak_reasons.append(f"{LANG_NAMES[lang]} nonword accuracy {_pct(accuracy['C'])} (below {_pct(r['weak_acc_nonwords'])})")
    if wcpm is not None and wcpm < wcpm_min:
        weak_reasons.append(f"{LANG_NAMES[lang]} passage {wcpm:g} words correct per minute (grade guide {wcpm_min})")

    return LanguageMetrics(
        lang=lang,
        accuracy=accuracy,
        coverage=coverage,
        wcpm=wcpm,
        wcpm_min=wcpm_min,
        lexicalizations=error_counts.get("lexicalization", 0),
        lexicalization_examples=lex_examples,
        timing_rate=round(timed_flagged / len(single_timed), 3) if single_timed else 0.0,
        weighted_error_score=round(score / len(single_counted), 3) if single_counted else 0.0,
        error_counts=error_counts,
        pending_sections=pending_sections,
        pending=bool(pending_sections),
        weak=bool(weak_reasons),
        weak_reasons=weak_reasons,
    )


def _nonwords_weakest(m: LanguageMetrics) -> bool:
    nw = m.acc_nonwords
    if nw is None or nw >= 1:
        return False
    others = [a for a in (m.acc_letters, m.acc_words) if a is not None]
    return all(nw <= a for a in others)


def specific_pattern(hi: LanguageMetrics, en: LanguageMetrics, cfg: dict) -> tuple[bool, list[str]]:
    r = cfg["risk"]
    why = []
    if hi.weighted_error_score < r["pattern_min_weighted_error_score"]:
        return False, why
    if _nonwords_weakest(hi):
        why.append(f"nonwords are the weakest Hindi section ({_pct(hi.acc_nonwords)})")
    lex = hi.lexicalizations + en.lexicalizations
    if lex >= r["pattern_min_lexicalizations"]:
        why.append(f"{lex} made-up words read as real words")
    if hi.timing_rate >= r["pattern_min_timing_rate"]:
        why.append(f"hesitated on {_pct(hi.timing_rate)} of Hindi letters/words/nonwords")
    return bool(why), why


def _summary_line(m: LanguageMetrics) -> str:
    parts = [
        f"letters {_pct(m.acc_letters)}",
        f"words {_pct(m.acc_words)}",
        f"nonwords {_pct(m.acc_nonwords)}",
        f"passage {m.wcpm:g} WCPM" if m.wcpm is not None else "passage n/a",
    ]
    return f"{LANG_NAMES[m.lang]}: " + ", ".join(parts)


def _pattern_lines(m: LanguageMetrics) -> list[str]:
    lines = []
    name = LANG_NAMES[m.lang]
    labels = {  # (singular, plural)
        "matra_confusion": ("matra confusion", "matra confusions"),
        "aspiration_error": ("aspiration error", "aspiration errors"),
        "visual_akshara_swap": ("look-alike letter swap", "look-alike letter swaps"),
        "letter_reversal": ("letter reversal (b/d, p/q)", "letter reversals (b/d, p/q)"),
        "word_reversal": ("word reversal (was/saw)", "word reversals (was/saw)"),
        "transposition": ("case of letters in the wrong order", "cases of letters in the wrong order"),
    }
    for key, (one, many) in labels.items():
        n = m.error_counts.get(key, 0)
        if n:
            lines.append(f"{n} {one if n == 1 else many} in {name}")
    for ex in m.lexicalization_examples:
        lines.append("Read the made-up word " + ex.replace(" → ", " as "))
    return lines


def compute_risk(results: list[ItemResult], grade: int, cfg: dict | None = None, bank_counts: dict | None = None) -> RiskReport:
    cfg = cfg or thresholds()
    if bank_counts is None:
        bank_counts = {}
        for lang in ("hi", "en"):
            counts: dict[str, int] = {}
            for item in load_test(lang)["items"]:
                counts[item["section"]] = counts.get(item["section"], 0) + 1
            bank_counts[lang] = counts
    hi = language_metrics(results, "hi", grade, bank_counts["hi"], cfg)
    en = language_metrics(results, "en", grade, bank_counts["en"], cfg)
    pattern, pattern_why = specific_pattern(hi, en, cfg)
    pending_verify = sum(awaiting_verification(x) for x in results)

    reasons = [_summary_line(hi), _summary_line(en)]
    if hi.pending:
        level = "pending"
        reasons.append("Hindi words/nonwords need more scored items before a result can be shown")
    elif en.pending:
        level = "provisional"
        n_en = sum(awaiting_verification(x) for x in results if x.lang == "en")
        reasons.append(f"Hindi looks {'weak' if hi.weak else 'on track'}; verify {n_en} English items to finish")
    elif not hi.weak and not en.weak:
        level = "low_risk"
    elif not hi.weak and en.weak:
        level = "english_exposure_gap"
    elif hi.weak and en.weak:
        level = "specialist_check" if pattern else "reading_support"
    else:
        level = "hindi_support"

    if level not in ("pending",):
        reasons += hi.weak_reasons + (en.weak_reasons if not en.pending else [])
        if level == "specialist_check":
            reasons += [w[0].upper() + w[1:] for w in pattern_why]
        reasons += _pattern_lines(hi) + (_pattern_lines(en) if not en.pending else [])

    emoji, label = LEVELS[level]
    return RiskReport(
        level=level,
        emoji=emoji,
        label=label,
        languages={"hi": hi, "en": en},
        specific_pattern=pattern,
        reasons=reasons,
        scoring_breakdown=scoring_breakdown(results),
        pending_verify=pending_verify,
    )
