import json

from app.services.transcribe import parse_verbose_json, transcribe
from tests.conftest import FIXTURES


class FakeTranscriptions:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class FakeClient:
    def __init__(self, response):
        self.audio = type("Audio", (), {})()
        self.audio.transcriptions = FakeTranscriptions(response)


def raw(name):
    with open(FIXTURES / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def test_request_settings_from_spike(monkeypatch):
    monkeypatch.delenv("GROQ_STT_MODEL", raising=False)
    client = FakeClient(raw("hi_05_lexicalization"))
    transcribe(b"audio", "clip.webm", "hi", client=client)
    kw = client.audio.transcriptions.kwargs
    assert kw["model"] == "whisper-large-v3"
    assert kw["response_format"] == "verbose_json"
    assert kw["timestamp_granularities"] == ["word", "segment"]
    assert kw["language"] == "hi"
    assert kw["temperature"] == 0.0
    assert kw["file"] == ("clip.webm", b"audio")
    assert "prompt" not in kw  # the target text must never bias Whisper


def test_model_from_env(monkeypatch):
    monkeypatch.setenv("GROQ_STT_MODEL", "some-other-model")
    client = FakeClient(raw("hi_05_lexicalization"))
    assert transcribe(b"a", "c.wav", "hi", client=client).model == "some-other-model"


def test_parse_real_response():
    tr = parse_verbose_json(raw("en_06_long_pause"))
    assert tr.text == "Tom can jump over the big log."
    assert [w.word for w in tr.words] == ["Tom", "can", "jump", "over", "the", "big", "log."]
    assert tr.words[2].start == 1.62 and tr.words[2].end == 6.34
    assert len(tr.segments) == 1 and tr.segments[0].avg_logprob < 0


def test_parse_missing_fields():
    tr = parse_verbose_json({"text": " hi "})
    assert tr.text == "hi" and tr.words == [] and tr.segments == []
