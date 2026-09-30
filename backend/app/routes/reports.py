import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import Child, ItemResultRow, ReadingSession, Report
from ..services.analyse import TAPS, awaiting_verification, record_live_tap, record_verification
from ..services.risk import DISCLAIMER
from ..services.store import (
    build_report,
    fill_row,
    report_view,
    result_view,
    row_to_result,
    session_rows,
)
from .children import child_view
from .deps import get_db, llm_client
from .sessions import session_view

router = APIRouter()

MEDIA_TYPES = {".webm": "audio/webm", ".ogg": "audio/ogg", ".wav": "audio/wav", ".m4a": "audio/mp4",
               ".mp3": "audio/mpeg", ".mp4": "audio/mp4", ".flac": "audio/flac"}


def _latest_session(db: Session, child_id: int) -> ReadingSession | None:
    return db.exec(
        select(ReadingSession).where(ReadingSession.child_id == child_id).order_by(ReadingSession.id.desc())
    ).first()


@router.get("/children/{child_id}/report")
def child_report(child_id: int, db: Session = Depends(get_db)):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "child not found")
    sess = _latest_session(db, child_id)
    if not sess:
        return {"child": child_view(child), "session": None, "report": None, "items": [], "disclaimer": DISCLAIMER}
    rows = session_rows(db, sess.id)
    return {
        "child": child_view(child),
        "session": session_view(sess),
        "report": report_view(db.get(Report, sess.id)),
        "items": [result_view(r) for r in rows],
        "disclaimer": DISCLAIMER,
    }


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(correct|incorrect|skipped)$")
    words_correct: int | None = Field(default=None, ge=0)


@router.patch("/results/{result_id}")
def decide(result_id: int, body: DecisionIn, db: Session = Depends(get_db), client=Depends(llm_client)):
    """Teacher verify / override. Manual items: corrects the live tap."""
    row = db.get(ItemResultRow, result_id)
    if not row:
        raise HTTPException(404, "result not found")
    result = row_to_result(row)
    try:
        if result.status == "manual":
            record_live_tap(result, body.decision)
        else:
            record_verification(result, body.decision, body.words_correct)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    fill_row(row, result)
    db.add(row)
    db.commit()
    db.refresh(row)

    sess = db.get(ReadingSession, row.session_id)
    report = None
    if sess.status == "finished":
        report, _ = build_report(db, sess, with_summaries=False, llm_client=client)
    return {"result": result_view(row), "report": report_view(report)}


@router.get("/class/summary")
def class_summary(db: Session = Depends(get_db)):
    out = []
    for child in db.exec(select(Child).order_by(Child.code)):
        sess = _latest_session(db, child.id)
        report = db.get(Report, sess.id) if sess else None
        rows = session_rows(db, sess.id) if sess else []
        pending = sum(awaiting_verification(row_to_result(r)) for r in rows)
        view = report_view(report)
        out.append({
            **child_view(child),
            "session_id": sess.id if sess else None,
            "session_status": sess.status if sess else None,
            "tested_at": sess.created_at.isoformat() if sess else None,
            "items_recorded": len(rows),
            "pending_verify": pending,
            "risk_level": view["risk_level"] if view else None,
            "emoji": view["emoji"] if view else None,
            "label": view["label"] if view else None,
            "summary_stale": view["summary_stale"] if view else False,
        })
    return out


def _audio_row(db: Session, clip_id: int) -> ItemResultRow:
    row = db.get(ItemResultRow, clip_id)
    if not row or not row.audio_path or not Path(row.audio_path).exists():
        raise HTTPException(404, "clip not found")
    return row


@router.get("/audio/{clip_id}")
def get_audio(clip_id: int, db: Session = Depends(get_db)):
    row = _audio_row(db, clip_id)
    path = Path(row.audio_path)
    return FileResponse(path, media_type=MEDIA_TYPES.get(path.suffix, "application/octet-stream"))


@router.delete("/audio/{clip_id}", status_code=204)
def delete_audio(clip_id: int, db: Session = Depends(get_db)):
    """Privacy: the teacher can delete any clip. The scored result stays."""
    row = _audio_row(db, clip_id)
    Path(row.audio_path).unlink(missing_ok=True)
    row.audio_path = None
    db.add(row)
    db.commit()


@router.delete("/children/{child_id}/audio", status_code=204)
def delete_child_audio(child_id: int, db: Session = Depends(get_db)):
    if not db.get(Child, child_id):
        raise HTTPException(404, "child not found")
    sessions = db.exec(select(ReadingSession).where(ReadingSession.child_id == child_id)).all()
    for sess in sessions:
        for row in session_rows(db, sess.id):
            if row.audio_path:
                Path(row.audio_path).unlink(missing_ok=True)
                row.audio_path = None
                db.add(row)
    db.commit()


@router.delete("/children/{child_id}", status_code=204)
def delete_child(child_id: int, db: Session = Depends(get_db)):
    """Privacy: remove a child and everything recorded for them."""
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "child not found")
    for sess in db.exec(select(ReadingSession).where(ReadingSession.child_id == child_id)).all():
        for row in session_rows(db, sess.id):
            if row.audio_path:
                Path(row.audio_path).unlink(missing_ok=True)
            db.delete(row)
        report = db.get(Report, sess.id)
        if report:
            db.delete(report)
        db.delete(sess)
    db.delete(child)
    db.commit()


@router.post("/sessions/{session_id}/parent-link")
def new_parent_link(session_id: int, db: Session = Depends(get_db)):
    """Make a new parent link; the old one stops working."""
    report = db.get(Report, session_id)
    if not report:
        raise HTTPException(404, "no report for this session yet")
    report.parent_token = secrets.token_urlsafe(16)
    db.add(report)
    db.commit()
    return {"parent_token": report.parent_token}
