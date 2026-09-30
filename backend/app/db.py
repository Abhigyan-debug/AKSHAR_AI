"""SQLite tables (see docs/architecture.md)."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Session, SQLModel, create_engine


def now() -> datetime:
    return datetime.now(timezone.utc)


class Child(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    grade: int
    home_lang: str
    created_at: datetime = Field(default_factory=now)


class ReadingSession(SQLModel, table=True):
    __tablename__ = "session"
    id: Optional[int] = Field(default=None, primary_key=True)
    child_id: int = Field(foreign_key="child.id", index=True)
    status: str = "in_progress"            # in_progress | finished
    include_sound_game: bool = True
    created_at: datetime = Field(default_factory=now)


class ItemResultRow(SQLModel, table=True):
    __tablename__ = "item_result"
    __table_args__ = (UniqueConstraint("session_id", "item_id"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session.id", index=True)
    item_id: str
    lang: str
    section: str
    transcript: str = ""
    words_json: str = "[]"                 # Whisper word timestamps
    correct: Optional[bool] = None
    suggested_correct: bool = False
    skipped: bool = False
    errors_json: str = "[]"
    status: str = "auto"                   # auto | teacher_verify | manual (never changes)
    verified: bool = False
    live_tap: Optional[str] = None
    avg_logprob: Optional[float] = None
    no_speech_prob: Optional[float] = None
    confidence_reasons_json: str = "[]"
    start_latency_ms: Optional[int] = None
    hesitation: bool = False
    duration_ms: Optional[int] = None
    timing_json: str = "{}"
    words_correct: int = 0
    words_total: int = 1
    pairs_json: str = "[]"
    audio_path: Optional[str] = None
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Report(SQLModel, table=True):
    session_id: int = Field(foreign_key="session.id", primary_key=True)
    metrics_json: str = "{}"
    scoring_breakdown_json: str = "{}"
    risk_level: str = "pending"
    reasons_json: str = "[]"
    teacher_summary: str = ""
    next_step: str = ""
    parent_summary_hi: str = ""
    home_tips_json: str = "[]"
    summary_source: str = ""               # llm | template
    summary_stale: bool = False            # risk changed after the summary was written
    parent_token: str = Field(index=True, unique=True)
    updated_at: datetime = Field(default_factory=now)


def make_engine(url: str):
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def session_factory(engine):
    def get_db():
        with Session(engine) as db:
            yield db

    return get_db
