"""Groq LLM (see docs/scoring.md): labels for residual `unclassified` errors, and the
teacher (English) + parent (Hindi) summaries.

The LLM never decides risk. It rephrases facts that risk.py computed and a
next step chosen per risk level (NEXT_STEPS). Every response is strict JSON,
validated with Pydantic, retried once; after that a hand-written template is
used, so a report always has a summary. Principle 1: no "dyslexic" wording.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ValidationError, field_validator

from . import cache
from .analyse import ItemResult
from .risk import LANG_NAMES, RiskReport

DEFAULT_LLM_MODEL = "openai/gpt-oss-120b"
FORBIDDEN = re.compile(r"dyslexi|डिस्लेक्स|डिसलेक्स", re.IGNORECASE)

NEXT_STEPS = {
    "specialist_check": "Refer for a specialist check (school counsellor, government hospital, or an RCI-registered special educator); meanwhile give 10 minutes of daily one-to-one reading practice.",
    "reading_support": "Give 10 minutes of daily reading support in both languages and re-screen in 8-10 weeks.",
    "english_exposure_gap": "Increase English exposure (read-alouds, phonics games); this pattern points to less English practice, not a reading difficulty.",
    "hindi_support": "Check the child's home language and give daily Hindi reading support; re-screen in 8-10 weeks.",
    "low_risk": "No action needed now; re-screen next year as usual.",
    "provisional": "Finish verifying the English items in the verify queue to get the final result.",
    "pending": "Finish the teacher checks for the Hindi items before reading this result.",
}


# --- Validation models ---------------------------------------------------------

def _devanagari_share(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha() or "ऀ" <= ch <= "ॿ"]
    if not letters:
        return 0.0
    return sum("ऀ" <= ch <= "ॿ" for ch in letters) / len(letters)


def _no_diagnosis(text: str) -> str:
    if FORBIDDEN.search(text):
        raise ValueError("diagnostic wording is not allowed (screener, not diagnosis)")
    return text


class SummaryOut(BaseModel):
    teacher_summary: str
    next_step: str
    parent_summary_hi: str
    home_tips_hi: list[str]

    @field_validator("teacher_summary", "next_step")
    @classmethod
    def _english(cls, v: str) -> str:
        v = _no_diagnosis(v.strip())
        if not 20 <= len(v) <= 1200:
            raise ValueError("teacher text length out of range")
        return v

    @field_validator("parent_summary_hi")
    @classmethod
    def _hindi(cls, v: str) -> str:
        v = _no_diagnosis(v.strip())
        if not 40 <= len(v) <= 1200:
            raise ValueError("parent summary length out of range")
        if _devanagari_share(v) < 0.8:
            raise ValueError("parent summary must be in Hindi (Devanagari)")
        return v

    @field_validator("home_tips_hi")
    @classmethod
    def _tips(cls, v: list[str]) -> list[str]:
        v = [_no_diagnosis(t.strip()) for t in v]
        if len(v) != 3:
            raise ValueError("exactly 3 home tips are required")
        if any(_devanagari_share(t) < 0.8 or not 5 <= len(t) <= 300 for t in v):
            raise ValueError("home tips must be short Hindi sentences")
        return v


HI_TYPES = ("matra_confusion", "visual_akshara_swap", "aspiration_error", "conjunct_error", "transposition",
            "omission", "addition", "lexicalization", "first_letter_guess", "unclassified")
EN_TYPES = ("letter_reversal", "word_reversal", "vowel_error", "transposition", "omission", "addition",
            "lexicalization", "first_letter_guess", "unclassified")


class ResidualLabel(BaseModel):
    index: int
    type: Literal[
        "matra_confusion", "visual_akshara_swap", "aspiration_error", "conjunct_error", "transposition",
        "omission", "addition", "lexicalization", "first_letter_guess", "unclassified",
        "letter_reversal", "word_reversal", "vowel_error",
    ]


class ResidualOut(BaseModel):
    labels: list[ResidualLabel]


# --- Groq call ------------------------------------------------------------------

def llm_model() -> str:
    return os.getenv("GROQ_LLM_MODEL") or DEFAULT_LLM_MODEL


def _client():
    from groq import Groq

    return Groq(max_retries=2)


def _chat_json(messages: list[dict], schema: type[BaseModel], *, client=None, model: str | None = None, attempts: int = 2):
    """Call the LLM in JSON mode and validate; retry once. Returns (parsed, None) or (None, error)."""
    model = model or llm_model()
    key = cache.key_for(model, json.dumps(messages, ensure_ascii=False, sort_keys=True))
    cached = cache.get("llm", key)
    if cached is not None:
        try:
            return schema.model_validate(cached), None
        except ValidationError:
            pass
    if client is None:
        if not os.getenv("GROQ_API_KEY"):
            return None, "GROQ_API_KEY not set"
        client = _client()

    last_error = None
    convo = list(messages)
    for _ in range(attempts):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=convo,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            content = resp.choices[0].message.content or ""
            data = json.loads(content)
            parsed = schema.model_validate(data)
            cache.put("llm", key, parsed.model_dump())
            return parsed, None
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = f"invalid response: {exc}"
            convo = messages + [
                {"role": "user", "content": f"Your last reply was rejected: {str(exc)[:400]}. Reply again with valid JSON only, following every rule."}
            ]
        except Exception as exc:  # network / API errors: fall back rather than fail the report
            last_error = f"API error: {exc}"
            break
    return None, last_error


# --- Summaries -------------------------------------------------------------------

@dataclass
class Summaries:
    teacher_summary: str
    next_step: str
    parent_summary_hi: str
    home_tips_hi: list[str]
    source: str                      # "llm" or "template"
    error: str | None = None


SUMMARY_SYSTEM = """You write short reports for Akshar, a reading-aloud SCREENER (not a diagnosis) used in Indian schools. A child read letters, words, made-up words (nonwords) and a short story aloud in Hindi and in English.

You receive facts computed by a rule engine. Use ONLY these facts. Do not invent scores, names, places, organisations or phone numbers.

Rules:
- Never use the words "dyslexia", "dyslexic" or any Hindi form of them, and never say the child "has" a condition. This is a screening result, not a diagnosis.
- Refer to the child only as "the child" / "आपका बच्चा" (never by code or name).
- teacher_summary: English, 3-5 plain sentences for a class teacher. State the result, then the key evidence (cite the numbers and examples given). Mention that the thresholds are illustrative.
- next_step: English, one or two sentences, a clear rephrasing of recommended_next_step. Do not add other actions.
- parent_summary_hi: simple, warm, non-blaming Hindi in Devanagari script (5th-grade reading level, 3-5 short sentences). No English words, no percentages or technical terms. Only if result_key is not "low_risk": reassure the parent that the child is not lazy and that the right help makes a big difference. For "low_risk", do not mention laziness or problems; simply encourage. Say what the school suggests next, in simple words.
- home_tips_hi: a JSON array of exactly 3 separate strings (not one string, no numbering). Each is one short, practical Hindi tip a parent can do at home in 5-10 minutes a day, matched to the difficulties in the facts (e.g. matra practice, reading together aloud, sound games). Devanagari only.
- Never quote the test's items (its letters, words or made-up words such as the examples in the facts) in parent_summary_hi or home_tips_hi, and never suggest practising them: practising test items would spoil a later re-screening. Tips use everyday material (story books, signboards, sound games).
- Write correct, natural Hindi with correct spelling and grammar (e.g. "आपका बच्चा अच्छा पढ़ रहा है", not "आपका बच्चा ... किया है").

Reply with one JSON object with exactly these keys:
{"teacher_summary": "<string>", "next_step": "<string>", "parent_summary_hi": "<string>", "home_tips_hi": ["<tip 1>", "<tip 2>", "<tip 3>"]}"""


def _facts(report: RiskReport, grade: int) -> dict:
    langs = {}
    for lang, m in report.languages.items():
        langs[LANG_NAMES[lang]] = {
            "letters_accuracy_pct": None if m.acc_letters is None else round(100 * m.acc_letters),
            "words_accuracy_pct": None if m.acc_words is None else round(100 * m.acc_words),
            "nonwords_accuracy_pct": None if m.acc_nonwords is None else round(100 * m.acc_nonwords),
            "passage_words_correct_per_minute": m.wcpm,
            "grade_guide_words_correct_per_minute": m.wcpm_min,
            "error_counts": m.error_counts,
            "nonwords_read_as_real_words": m.lexicalization_examples,
            "still_being_checked_by_teacher": m.pending,
        }
    return {
        "grade": grade,
        "result": report.label,
        "result_key": report.level,
        "evidence": report.reasons,
        "languages": langs,
        "recommended_next_step": NEXT_STEPS[report.level],
        "note": report.disclaimer,
    }


NOT_FINAL = ("pending", "provisional")


def generate_summaries(report: RiskReport, grade: int, *, client=None, model: str | None = None) -> Summaries:
    if report.level in NOT_FINAL:
        # Partial data must not be summarised as if it were a result.
        return template_summaries(report, "result not final yet")
    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM},
        {"role": "user", "content": json.dumps(_facts(report, grade), ensure_ascii=False)},
    ]
    parsed, error = _chat_json(messages, SummaryOut, client=client, model=model)
    if parsed is None:
        return template_summaries(report, error)
    return Summaries(**parsed.model_dump(), source="llm")


PARENT_TEMPLATES = {
    "low_risk": "आपका बच्चा हिंदी और अंग्रेज़ी दोनों में अपनी कक्षा के हिसाब से अच्छा पढ़ रहा है। घर पर रोज़ साथ बैठकर पढ़ने की आदत बनाए रखें।",
    "english_exposure_gap": "आपका बच्चा हिंदी अच्छी तरह पढ़ रहा है। अंग्रेज़ी में उसे अभी कम अभ्यास मिला है, इसलिए वहाँ थोड़ी कठिनाई है। यह पढ़ने की कमज़ोरी नहीं है, बस अंग्रेज़ी सुनने और पढ़ने का ज़्यादा मौका चाहिए।",
    "reading_support": "आपके बच्चे को पढ़ने में अभी थोड़ी मदद की ज़रूरत है। आपका बच्चा आलसी नहीं है। स्कूल रोज़ थोड़ा अतिरिक्त अभ्यास कराएगा, और घर पर आपका साथ बहुत फ़र्क लाएगा।",
    "hindi_support": "आपके बच्चे को हिंदी पढ़ने में थोड़ी मदद की ज़रूरत है। स्कूल यह भी देखेगा कि घर पर कौन-सी भाषा ज़्यादा बोली जाती है। रोज़ थोड़ा हिंदी पढ़ने का अभ्यास मदद करेगा।",
    "specialist_check": "पढ़ते समय आपके बच्चे की कुछ गलतियाँ ऐसी हैं जिन्हें किसी विशेषज्ञ से जाँच करवाना अच्छा रहेगा। आपका बच्चा आलसी नहीं है। सही समय पर सही मदद मिलने से बच्चे बहुत अच्छा सीखते हैं।",
    "provisional": "आपके बच्चे की जाँच अभी पूरी हो रही है। शिक्षक जल्द ही पूरा परिणाम साझा करेंगे।",
    "pending": "आपके बच्चे की जाँच अभी पूरी हो रही है। शिक्षक जल्द ही पूरा परिणाम साझा करेंगे।",
}
TIPS_DEFAULT = [
    "रोज़ 10 मिनट बच्चे के साथ बैठकर कोई छोटी कहानी ज़ोर से पढ़ें।",
    "पढ़ते समय बच्चे को धीरे-धीरे पढ़ने दें और हर कोशिश पर उसकी तारीफ़ करें।",
    "आवाज़ों के खेल खेलें, जैसे 'कमल' से 'क' हटाओ तो क्या बचेगा।",
]


def template_summaries(report: RiskReport, error: str | None = None) -> Summaries:
    if report.level in NOT_FINAL:
        teacher = (
            f"{report.label}. {report.pending_verify} item(s) are waiting in the verify queue; "
            "the summary is written once the result is final."
        )
    else:
        evidence = "; ".join(report.reasons[:4])
        teacher = (
            f"Result: {report.label}. Evidence: {evidence}. "
            "This is a screening result, not a diagnosis; thresholds are illustrative."
        )
    return Summaries(
        teacher_summary=teacher,
        next_step=NEXT_STEPS[report.level],
        parent_summary_hi=PARENT_TEMPLATES[report.level],
        home_tips_hi=list(TIPS_DEFAULT),
        source="template",
        error=error,
    )


# --- Residual error labels ---------------------------------------------------------

RESIDUAL_SYSTEM = """You label children's reading errors for Akshar, a reading screener. Each case has the language, the target the child was shown, what the speech recogniser heard, and whether the target is a made-up word (nonword).

Choose exactly one type per case from the allowed list for its language:
Hindi: matra_confusion (vowel sign swapped/dropped/added), visual_akshara_swap (look-alike letters: ब/व, भ/म, घ/ध, प/ष, थ/य, ख/रव), aspiration_error (क/ख, ग/घ, ब/भ, द/ध ...), conjunct_error, transposition (aksharas reordered), omission, addition, lexicalization (a NONWORD read as a real Hindi word), first_letter_guess (first letter right, rest a different real word), unclassified.
English: letter_reversal (b/d, p/q, u/n, m/w), word_reversal (was/saw), vowel_error, transposition, omission, addition, lexicalization (a NONWORD read as a real English word), first_letter_guess, unclassified.

Use lexicalization only when is_nonword is true AND the heard word is a real, common word. If unsure, use unclassified.
Reply with JSON: {"labels": [{"index": <case index>, "type": "<type>"}, ...]} covering every case."""


def label_residual_errors(results: list[ItemResult], item_lookup: dict[str, dict], *, client=None, model: str | None = None) -> int:
    """Relabel `unclassified` word errors on reliable items (auto or teacher-verified,
    sections B/C). Returns how many labels changed. Rule labels are never overwritten."""
    cases = []
    for r in results:
        if r.section not in ("B", "C") or r.correct is not False:
            continue
        if not (r.status == "auto" or r.verified):
            continue
        item = item_lookup.get(r.item_id, {})
        for e in r.errors:
            if e.type == "unclassified" and e.source == "rules" and e.heard:
                cases.append((r, e, item))
    if not cases:
        return 0
    payload = [
        {"index": i, "language": LANG_NAMES[r.lang], "target": item.get("text", e.target), "heard": e.heard,
         "is_nonword": bool(item.get("is_nonword"))}
        for i, (r, e, item) in enumerate(cases)
    ]
    messages = [
        {"role": "system", "content": RESIDUAL_SYSTEM},
        {"role": "user", "content": json.dumps({"cases": payload}, ensure_ascii=False)},
    ]
    parsed, _ = _chat_json(messages, ResidualOut, client=client, model=model)
    if parsed is None:
        return 0
    changed = 0
    for label in parsed.labels:
        if not 0 <= label.index < len(cases) or label.type == "unclassified":
            continue
        r, e, item = cases[label.index]
        allowed = HI_TYPES if r.lang == "hi" else EN_TYPES
        if label.type not in allowed:
            continue
        if label.type == "lexicalization" and not item.get("is_nonword"):
            continue
        e.type, e.source = label.type, "llm"
        e.detail = (e.detail + " · AI label").strip(" ·")
        changed += 1
    return changed
