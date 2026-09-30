"""LLM layer with a fake Groq client: validation, retry, template fallback,
residual labels and the DEMO_MODE cache. No network calls."""

import json

import pytest

from app.services import cache, llm
from app.services.analyse import ItemResult
from app.services.classify_rules import ErrorLabel
from app.services.confidence import Confidence
from app.services.timing import Timing
from tests.test_risk import language, risk

GOOD = {
    "teacher_summary": "The child needs a specialist check. Nonword accuracy was 30% in Hindi and 40% in English.",
    "next_step": "Refer for a specialist check and give daily reading practice.",
    "parent_summary_hi": "आपके बच्चे को पढ़ने में थोड़ी मदद चाहिए। आपका बच्चा आलसी नहीं है। सही मदद से वह अच्छा सीखेगा।",
    "home_tips_hi": ["रोज़ 10 मिनट साथ में कहानी पढ़ें।", "आवाज़ों के खेल खेलें।", "हर कोशिश पर तारीफ़ करें।"],
}


class FakeClient:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        content = reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)
        msg = type("M", (), {"content": content})
        return type("R", (), {"choices": [type("C", (), {"message": msg})]})


@pytest.fixture(autouse=True)
def no_demo_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path / "cache")


@pytest.fixture
def report():
    return risk(language("hi", words_ok=6, nonwords_ok=3, lex=2, hesitate=10) + language("en", words_ok=5, nonwords_ok=4, lex=1))


def test_valid_reply(report):
    client = FakeClient([GOOD])
    s = llm.generate_summaries(report, 3, client=client, model="m")
    assert s.source == "llm" and s.home_tips_hi == GOOD["home_tips_hi"]
    call = client.calls[0]
    assert call["response_format"] == {"type": "json_object"} and call["model"] == "m"
    facts = json.loads(call["messages"][1]["content"])
    assert facts["result_key"] == "specialist_check"
    assert facts["recommended_next_step"] == llm.NEXT_STEPS["specialist_check"]


def test_retry_once_on_invalid_json(report):
    client = FakeClient(["not json", GOOD])
    s = llm.generate_summaries(report, 3, client=client, model="m")
    assert s.source == "llm" and len(client.calls) == 2
    assert "rejected" in client.calls[1]["messages"][-1]["content"]


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD, "home_tips_hi": "1. कहानी पढ़ें 2. खेल खेलें 3. तारीफ़ करें"},        # tips as one string
        {**GOOD, "home_tips_hi": GOOD["home_tips_hi"][:2]},                          # two tips
        {**GOOD, "parent_summary_hi": "Your child needs some help with reading at school."},  # not Hindi
        {**GOOD, "teacher_summary": "The child shows signs of dyslexia in both languages."},  # diagnosis word
        {**GOOD, "parent_summary_hi": "आपके बच्चे को डिस्लेक्सिया हो सकता है, कृपया डॉक्टर को दिखाएँ और मदद लें।"},
    ],
)
def test_invalid_twice_falls_back_to_template(report, bad):
    client = FakeClient([bad, bad])
    s = llm.generate_summaries(report, 3, client=client, model="m")
    assert s.source == "template" and len(client.calls) == 2
    assert s.parent_summary_hi == llm.PARENT_TEMPLATES["specialist_check"]
    assert s.next_step == llm.NEXT_STEPS["specialist_check"]
    assert len(s.home_tips_hi) == 3


def test_api_error_falls_back_without_retry(report):
    client = FakeClient([RuntimeError("503")])
    s = llm.generate_summaries(report, 3, client=client, model="m")
    assert s.source == "template" and "API error" in s.error and len(client.calls) == 1


def test_no_api_key_uses_template(report, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    s = llm.generate_summaries(report, 3)
    assert s.source == "template" and s.error == "GROQ_API_KEY not set"


def test_templates_follow_the_rules():
    for level, text in llm.PARENT_TEMPLATES.items():
        assert level in llm.NEXT_STEPS
        assert llm._devanagari_share(text) >= 0.8 and not llm.FORBIDDEN.search(text)
    llm.SummaryOut(teacher_summary="x" * 30, next_step="y" * 30,
                   parent_summary_hi=llm.PARENT_TEMPLATES["low_risk"], home_tips_hi=llm.TIPS_DEFAULT)


def test_demo_mode_serves_cached_reply(report, monkeypatch):
    FakeClient([GOOD])  # unused
    first = FakeClient([GOOD])
    llm.generate_summaries(report, 3, client=first, model="m")
    monkeypatch.setenv("DEMO_MODE", "true")
    second = FakeClient([])
    s = llm.generate_summaries(report, 3, client=second, model="m")
    assert s.source == "llm" and second.calls == []


def _wrong(item_id, lang, section, target, heard, status="auto", verified=False):
    return ItemResult(
        item_id=item_id, lang=lang, section=section, status=status, transcript=heard, correct=False,
        suggested_correct=False, skipped=False, errors=[ErrorLabel("unclassified", target, heard, "whole word differs")],
        timing=Timing(), confidence=Confidence(-0.2, 0.05, False), words_total=1, words_correct=0, verified=verified,
    )


def test_residual_labels():
    results = [
        _wrong("hi_C_02", "hi", "C", "लोकुस", "लोटस"),
        _wrong("hi_B_01", "hi", "B", "कमल", "कलम"),
        _wrong("en_B_03", "en", "B", "was", "song", status="teacher_verify"),  # unverified: skipped
    ]
    lookup = {"hi_C_02": {"text": "लोकुस", "is_nonword": True}, "hi_B_01": {"text": "कमल", "is_nonword": False}}
    reply = {"labels": [{"index": 0, "type": "lexicalization"}, {"index": 1, "type": "lexicalization"}, {"index": 7, "type": "omission"}]}
    client = FakeClient([reply])
    changed = llm.label_residual_errors(results, lookup, client=client, model="m")
    assert changed == 1
    assert results[0].errors[0].type == "lexicalization" and results[0].errors[0].source == "llm"
    assert results[1].errors[0].type == "unclassified"  # lexicalization only for nonwords
    assert results[2].errors[0].type == "unclassified"
    sent = json.loads(client.calls[0]["messages"][1]["content"])["cases"]
    assert [c["target"] for c in sent] == ["लोकुस", "कमल"]


def test_residual_labels_invalid_reply_changes_nothing():
    results = [_wrong("hi_C_02", "hi", "C", "लोकुस", "लोटस")]
    client = FakeClient([{"labels": [{"index": 0, "type": "made_up_type"}]}] * 2)
    assert llm.label_residual_errors(results, {"hi_C_02": {"is_nonword": True}}, client=client, model="m") == 0
    assert results[0].errors[0].type == "unclassified"


def test_residual_labels_without_cases_makes_no_call():
    client = FakeClient([])
    assert llm.label_residual_errors([], {}, client=client) == 0 and client.calls == []


def test_not_final_results_never_reach_the_llm():
    client = FakeClient([])
    s = llm.generate_summaries(risk(language("hi") + language("en", verified=False)), 3, client=client, model="m")
    assert s.source == "template" and client.calls == []
    assert "waiting in the verify queue" in s.teacher_summary
    assert s.parent_summary_hi == llm.PARENT_TEMPLATES["provisional"]
