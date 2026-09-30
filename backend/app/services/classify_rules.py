"""Rule-based error classifier (see docs/scoring.md). Deterministic and explainable; the
LLM only sees what these rules leave as `unclassified`.

Input is the item (from data/tests/{lang}.json) and Whisper's transcript.
Confidence gating and timing are handled elsewhere (confidence.py, timing.py).
"""

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import product

from .akshara import HALANT, INHERENT, Unit, aksharas, units, vowel_display
from .align import DEL, INS, MATCH, SUB, align
from .normalize import compact, is_single_word, matches, normalize

VISUAL_PAIRS_HI = {frozenset(p) for p in [("ब", "व"), ("भ", "म"), ("घ", "ध"), ("प", "ष"), ("ड", "ङ"), ("थ", "य")]}
ASPIRATION_PAIRS_HI = {
    frozenset(p)
    for p in [("क", "ख"), ("ग", "घ"), ("च", "छ"), ("ज", "झ"), ("ट", "ठ"),
              ("ड", "ढ"), ("त", "थ"), ("द", "ध"), ("प", "फ"), ("ब", "भ")]
}
REVERSAL_PAIRS_EN = {frozenset(p) for p in [("b", "d"), ("p", "q"), ("u", "n"), ("m", "w")]}
VOWELS_EN = set("aeiou")

# A heard word this different from the target is a guess, not a set of
# individual slips: label it once instead of listing every difference.
GUESS_SIMILARITY = 0.5


@dataclass
class ErrorLabel:
    type: str
    target: str | None = None
    heard: str | None = None
    detail: str = ""
    low_confidence: bool = False  # conjunct errors
    source: str = "rules"         # "rules", or "llm" for residual labels


@dataclass
class WordPair:
    """One aligned target/heard word, for highlighting in the report."""
    kind: str  # match | sub | del | ins
    target: str | None
    heard: str | None


@dataclass
class Classification:
    correct: bool
    skipped: bool
    errors: list[ErrorLabel] = field(default_factory=list)
    words_total: int = 1
    words_correct: int = 0
    pairs: list[WordPair] = field(default_factory=list)


def _dedupe(errors: list[ErrorLabel]) -> list[ErrorLabel]:
    seen, out = set(), []
    for e in errors:
        key = (e.type, e.target, e.heard, e.detail)
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def _is_adjacent_swap(a: list, b: list) -> bool:
    if len(a) != len(b) or len(a) < 2:
        return False
    diff = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]


# --- Hindi -------------------------------------------------------------------

def _kha_rava_swap(t: str, h: str) -> bool:
    """ख and रव look alike but have different akshara counts, so check directly."""
    for a, b in ((t, h), (h, t)):
        for i, ch in enumerate(a):
            if ch == "ख" and a[:i] + "रव" + a[i + 1:] == b:
                return True
    return False


def _conjunct_variants(us: list[Unit]):
    """Sound sequences a reader produces by splitting or simplifying the conjuncts in `us`."""
    groups: list[list[Unit]] = []
    for u in us:
        if groups and groups[-1][0].akshara_index == u.akshara_index:
            groups[-1].append(u)
        else:
            groups.append([u])
    if not any(len(g) > 1 for g in groups):
        return
    # split: स्कूल read as स-कूल (a vowel inserted inside the cluster)
    yield "split", [(u.consonant, INHERENT if u.vowel == HALANT and u.in_cluster else u.vowel, u.nasal) for u in us]
    # simplified: प्यास read as पास (one consonant of the cluster kept)
    for combo in product(*[range(len(g)) if len(g) > 1 else [None] for g in groups]):
        out = []
        for g, keep in zip(groups, combo):
            if keep is None:
                out.extend(u.sound for u in g)
            else:
                out.append((g[keep].consonant, g[-1].vowel, g[-1].nasal))
        yield "simplified", out


def _unit_sub_cost(x: Unit, y: Unit) -> float:
    if x.consonant == y.consonant or x.vowel == y.vowel:
        return 0.5
    return 1.0


def _unit_sub_labels(tu: Unit, hu: Unit, target: str, heard: str) -> list[ErrorLabel]:
    out = []
    if tu.consonant != hu.consonant:
        detail = f"{tu.consonant or tu.text}→{hu.consonant or hu.text}"
        pair = frozenset((tu.consonant, hu.consonant))
        if tu.consonant is None or hu.consonant is None:
            out.append(ErrorLabel("unclassified", target, heard, detail))
        elif pair in VISUAL_PAIRS_HI:
            out.append(ErrorLabel("visual_akshara_swap", target, heard, detail))
        elif pair in ASPIRATION_PAIRS_HI:
            out.append(ErrorLabel("aspiration_error", target, heard, detail))
        else:
            out.append(ErrorLabel("unclassified", target, heard, detail))
    if tu.vowel != hu.vowel or tu.nasal != hu.nasal:
        if {tu.vowel, hu.vowel} == {HALANT, INHERENT}:
            out.append(ErrorLabel("conjunct_error", target, heard, "split" if tu.vowel == HALANT else "added", True))
        elif tu.vowel == hu.vowel:
            out.append(ErrorLabel("matra_confusion", target, heard, "ं dropped" if tu.nasal else "ं added"))
        else:
            detail = f"{vowel_display(tu.vowel, tu.nasal)}→{vowel_display(hu.vowel, hu.nasal)}"
            out.append(ErrorLabel("matra_confusion", target, heard, detail))
    return out


def classify_word_hi(target: str, heard: str) -> list[ErrorLabel]:
    t, h = normalize(target), normalize(heard)
    if t == h:
        return []
    if _kha_rava_swap(t, h):
        return [ErrorLabel("visual_akshara_swap", target, heard, "ख↔रव")]

    ta, ha = [a.text for a in aksharas(t)], [a.text for a in aksharas(h)]
    if _is_adjacent_swap(ta, ha):
        i = next(k for k, (x, y) in enumerate(zip(ta, ha)) if x != y)
        return [ErrorLabel("transposition", target, heard, f"{ta[i]}{ta[i + 1]}→{ha[i]}{ha[i + 1]}")]

    tu, hu = units(t), units(h)
    t_sounds, h_sounds = [u.sound for u in tu], [u.sound for u in hu]
    for kind, variant in _conjunct_variants(tu):
        if variant == h_sounds:
            return [ErrorLabel("conjunct_error", target, heard, kind, True)]
    for _, variant in _conjunct_variants(hu):
        if variant == t_sounds:
            return [ErrorLabel("conjunct_error", target, heard, "added", True)]

    ops = align(tu, hu, eq=lambda x, y: x.sound == y.sound, sub_cost=_unit_sub_cost)
    mismatches = [op for op in ops if op.kind != MATCH]
    # A unit with both consonant and vowel wrong counts as two differences (है -> था).
    n_diff = sum(
        2 if op.kind == SUB and tu[op.a].consonant != hu[op.b].consonant and tu[op.a].vowel != hu[op.b].vowel else 1
        for op in mismatches
    )
    if n_diff >= 2 and SequenceMatcher(None, t_sounds, h_sounds).ratio() < GUESS_SIMILARITY:
        if ta and ha and ta[0] == ha[0]:
            return [ErrorLabel("first_letter_guess", target, heard, f"starts with {ta[0]}")]
        return [ErrorLabel("unclassified", target, heard, "whole word differs")]

    errors: list[ErrorLabel] = []
    for op in mismatches:
        if op.kind == SUB:
            errors += _unit_sub_labels(tu[op.a], hu[op.b], target, heard)
        elif op.kind == DEL:
            u = tu[op.a]
            if u.in_cluster:
                errors.append(ErrorLabel("conjunct_error", target, heard, "simplified", True))
            else:
                errors.append(ErrorLabel("omission", target, heard, f"{u.text} dropped"))
        else:
            u = hu[op.b]
            if u.in_cluster:
                errors.append(ErrorLabel("conjunct_error", target, heard, "added", True))
            else:
                errors.append(ErrorLabel("addition", target, heard, f"{u.text} added"))
    return _dedupe(errors)


# --- English -----------------------------------------------------------------

def classify_word_en(target: str, heard: str) -> list[ErrorLabel]:
    t, h = compact(target), compact(heard)
    if t == h:
        return []
    if len(t) >= 2 and h == t[::-1]:
        return [ErrorLabel("word_reversal", target, heard, f"{t}→{h}")]
    if _is_adjacent_swap(list(t), list(h)):
        return [ErrorLabel("transposition", target, heard, f"{t}→{h}")]

    ops = align(t, h)
    mismatches = [op for op in ops if op.kind != MATCH]
    if len(mismatches) >= 2 and SequenceMatcher(None, t, h).ratio() < GUESS_SIMILARITY:
        if t and h and t[0] == h[0]:
            return [ErrorLabel("first_letter_guess", target, heard, f"starts with '{t[0]}'")]
        return [ErrorLabel("unclassified", target, heard, "whole word differs")]

    errors: list[ErrorLabel] = []
    for op in mismatches:
        if op.kind == SUB:
            x, y = t[op.a], h[op.b]
            if frozenset((x, y)) in REVERSAL_PAIRS_EN:
                errors.append(ErrorLabel("letter_reversal", target, heard, f"{x}→{y}"))
            elif x in VOWELS_EN and y in VOWELS_EN:
                errors.append(ErrorLabel("vowel_error", target, heard, f"{x}→{y}"))
            else:
                errors.append(ErrorLabel("unclassified", target, heard, f"{x}→{y}"))
        elif op.kind == DEL:
            errors.append(ErrorLabel("omission", target, heard, f"'{t[op.a]}' dropped"))
        else:
            errors.append(ErrorLabel("addition", target, heard, f"'{h[op.b]}' added"))
    return _dedupe(errors)


# --- Items -------------------------------------------------------------------

def classify_word(target: str, heard: str, lang: str) -> list[ErrorLabel]:
    return classify_word_hi(target, heard) if lang == "hi" else classify_word_en(target, heard)


def _is_lexicalization(attempt: str, item: dict, known_words) -> bool:
    if not item.get("is_nonword"):
        return False
    near_real = item.get("near_real")
    if near_real and matches(attempt, near_real):
        return True
    known = {compact(w) for w in known_words}
    return compact(attempt) in known and compact(attempt) != compact(item["text"])


def _classify_single(item: dict, heard: str, lang: str, known_words) -> Classification:
    target = item["text"]
    variants = item.get("accepted_variants") or []
    errors: list[ErrorLabel] = []
    attempt = heard
    heard_words = normalize(heard).split()
    last = heard_words[-1] if heard_words else ""
    # Repeated attempts restart the same word ("पम पमीर", "पन पनीर"): every earlier
    # word starts like the last one and isn't longer. Anything else is one reading
    # that Whisper split into words ("drumpet" -> "drum pit"), judged as a whole.
    retries = len(heard_words) > 1 and all(w[:1] == last[:1] and len(w) <= len(last) for w in heard_words[:-1])
    if retries:
        errors.append(ErrorLabel("self_correction", target, heard, f"{len(heard_words)} attempts"))
        attempt = last
        if matches(attempt, target, variants):
            return Classification(True, False, errors, 1, 1, [WordPair(MATCH, target, attempt)])
    elif len(heard_words) > 1:
        attempt = compact(heard)
    if _is_lexicalization(attempt, item, known_words):
        errors.insert(0, ErrorLabel("lexicalization", target, normalize(attempt), f"{target}→{normalize(attempt)}"))
    else:
        errors = classify_word(target, attempt, lang) + errors
    return Classification(False, False, errors, 1, 0, [WordPair(SUB, target, normalize(attempt))])


def _word_sub_cost(x: str, y: str) -> float:
    return 1.0 - 0.5 * SequenceMatcher(None, x, y).ratio()


def _is_repeat(word: str, j: int, heard_words: list[str]) -> bool:
    """An inserted word that repeats, or starts, a neighbouring word is a self-correction."""
    nxt = heard_words[j + 1] if j + 1 < len(heard_words) else None
    prev = heard_words[j - 1] if j > 0 else None
    return (nxt is not None and nxt.startswith(word)) or prev == word


def _classify_passage(item: dict, heard: str, lang: str) -> Classification:
    tw, hw = normalize(item["text"]).split(), normalize(heard).split()
    errors: list[ErrorLabel] = []
    pairs: list[WordPair] = []
    correct_words = 0
    for op in align(tw, hw, sub_cost=_word_sub_cost):
        if op.kind == MATCH:
            correct_words += 1
            pairs.append(WordPair(MATCH, tw[op.a], hw[op.b]))
        elif op.kind == DEL:
            errors.append(ErrorLabel("omission", tw[op.a], None, "word skipped"))
            pairs.append(WordPair(DEL, tw[op.a], None))
        elif op.kind == INS:
            kind = "self_correction" if _is_repeat(hw[op.b], op.b, hw) else "addition"
            errors.append(ErrorLabel(kind, None, hw[op.b], "word repeated" if kind == "self_correction" else "word added"))
            pairs.append(WordPair(INS, None, hw[op.b]))
        else:
            errors += classify_word(tw[op.a], hw[op.b], lang)
            pairs.append(WordPair(SUB, tw[op.a], hw[op.b]))
    correct = all(e.type == "self_correction" for e in errors)
    return Classification(correct, False, errors, len(tw), correct_words, pairs)


def classify_item(item: dict, heard: str, lang: str, known_words=()) -> Classification:
    """Classify one item's transcript against its target.

    `known_words`: real words (e.g. every real word in the test plus the
    near_real list); a nonword read as one of them is a lexicalization.
    """
    target = item["text"]
    variants = item.get("accepted_variants") or []
    n_words = len(normalize(target).split())
    if not normalize(heard):
        return Classification(False, True, [], n_words, 0, [])
    if matches(heard, target, variants):
        words = normalize(target).split()
        return Classification(True, False, [], n_words, n_words, [WordPair(MATCH, w, w) for w in words])
    if item.get("section") == "E":
        # Sound game: right or wrong answer; no reading-error pattern to extract.
        return Classification(False, False, [], 1, 0, [WordPair(SUB, target, normalize(heard))])
    if is_single_word(target):
        return _classify_single(item, heard, lang, known_words)
    return _classify_passage(item, heard, lang)
