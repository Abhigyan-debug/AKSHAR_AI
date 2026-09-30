"""Groq Whisper transcription.

Settings decided in the spike (see docs/scoring.md): whisper-large-v3, verbose_json with word
and segment timestamps, language set per test, temperature 0, and NO prompt -
passing the target text would bias Whisper toward the correct reading.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_STT_MODEL = "whisper-large-v3"


@dataclass(frozen=True)
class Word:
    word: str
    start: float
    end: float


@dataclass(frozen=True)
class Segment:
    text: str
    start: float
    end: float
    avg_logprob: float
    no_speech_prob: float


@dataclass
class Transcript:
    text: str
    words: list[Word]
    segments: list[Segment]
    model: str = ""
    language: str = ""
    raw: dict = field(default_factory=dict, repr=False)


def parse_verbose_json(data: dict, model: str = "", language: str = "") -> Transcript:
    words = [
        Word(word=str(w.get("word", "")).strip(), start=float(w["start"]), end=float(w["end"]))
        for w in data.get("words") or []
    ]
    segments = [
        Segment(
            text=str(s.get("text", "")).strip(),
            start=float(s.get("start", 0.0)),
            end=float(s.get("end", 0.0)),
            avg_logprob=float(s.get("avg_logprob", 0.0)),
            no_speech_prob=float(s.get("no_speech_prob", 0.0)),
        )
        for s in data.get("segments") or []
    ]
    return Transcript(
        text=str(data.get("text") or "").strip(),
        words=words,
        segments=segments,
        model=model,
        language=language or str(data.get("language") or ""),
        raw=data,
    )


def _as_dict(resp) -> dict:
    if isinstance(resp, dict):
        return resp
    if hasattr(resp, "to_dict"):
        return resp.to_dict()
    if hasattr(resp, "model_dump"):
        return resp.model_dump()
    return dict(resp)


def transcribe(audio: bytes, filename: str, lang: str, *, model: str | None = None, client=None) -> Transcript:
    """Transcribe one item's clip. `lang` is "hi" or "en"."""
    model = model or os.getenv("GROQ_STT_MODEL") or DEFAULT_STT_MODEL
    if client is None:
        from groq import Groq

        client = Groq(max_retries=5)
    resp = client.audio.transcriptions.create(
        file=(filename, audio),
        model=model,
        response_format="verbose_json",
        timestamp_granularities=["word", "segment"],
        language=lang,
        temperature=0.0,
    )
    return parse_verbose_json(_as_dict(resp), model=model, language=lang)


def cached_transcribe(audio: bytes, filename: str, lang: str, *, model: str | None = None, client=None) -> Transcript:
    """transcribe(), served from the DEMO_MODE cache when possible."""
    from . import cache

    model = model or os.getenv("GROQ_STT_MODEL") or DEFAULT_STT_MODEL
    key = cache.key_for(model, lang, audio)
    hit = cache.get("stt", key)
    if hit is not None:
        return parse_verbose_json(hit, model=model, language=lang)
    tr = transcribe(audio, filename, lang, model=model, client=client)
    cache.put("stt", key, tr.raw)
    return tr


def transcribe_file(path: str | Path, lang: str, **kwargs) -> Transcript:
    path = Path(path)
    return transcribe(path.read_bytes(), path.name, lang, **kwargs)
