import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select

from ..db import Child, ItemResultRow, ReadingSession
from ..services import bank
from ..services.analyse import TAPS, analyse_item
from ..services.store import build_report, fill_row, report_view, result_view
from ..services.transcribe import Transcript
from ..security import sniff_audio
from .deps import get_db, llm_client, storage_dir, transcriber

log = logging.getLogger(__name__)
router = APIRouter()

MAX_AUDIO_BYTES = 10 * 1024 * 1024


class SessionIn(BaseModel):
    child_id: int
    include_sound_game: bool = True


def session_view(s: ReadingSession) -> dict:
    return {"id": s.id, "child_id": s.child_id, "status": s.status, "include_sound_game": s.include_sound_game,
            "created_at": s.created_at.isoformat()}


def _get_session(db: Session, session_id: int) -> ReadingSession:
    sess = db.get(ReadingSession, session_id)
    if not sess:
        raise HTTPException(404, "session not found")
    return sess


@router.post("/sessions", status_code=201)
def create_session(body: SessionIn, db: Session = Depends(get_db)):
    if not db.get(Child, body.child_id):
        raise HTTPException(404, "child not found")
    sess = ReadingSession(child_id=body.child_id, include_sound_game=body.include_sound_game)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return session_view(sess)


@router.post("/sessions/{session_id}/items/{item_id}/audio")
async def upload_audio(
    session_id: int,
    item_id: str,
    file: UploadFile = File(...),
    live_tap: str | None = Form(None),
    db: Session = Depends(get_db),
    stt=Depends(transcriber),
    storage: Path = Depends(storage_dir),
):
    sess = _get_session(db, session_id)
    if sess.status != "in_progress":
        raise HTTPException(409, "session is finished")
    item = bank.items().get(item_id)
    if not item:
        raise HTTPException(404, "unknown item")
    manual = item.get("scoring") == "manual"
    if manual and live_tap not in TAPS:
        raise HTTPException(422, "manual items need the teacher's live tap: correct, incorrect or skipped")
    if not manual and live_tap is not None:
        raise HTTPException(422, "live tap is only for manual items")

    audio = await file.read(MAX_AUDIO_BYTES + 1)  # never read more than the limit
    if not audio:
        raise HTTPException(422, "empty audio")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "audio too large")
    # Trust the bytes, not the file name or content type the client sent.
    ext = sniff_audio(audio)
    if ext is None:
        raise HTTPException(415, "not a supported audio file (webm, ogg, wav, m4a, mp3, flac)")

    folder = storage / "audio" / str(session_id)
    folder.mkdir(parents=True, exist_ok=True)
    row = db.exec(select(ItemResultRow).where(ItemResultRow.session_id == session_id, ItemResultRow.item_id == item_id)).first()
    if row and row.audio_path:
        Path(row.audio_path).unlink(missing_ok=True)
    path = folder / f"{item_id}{ext}"
    path.write_bytes(audio)

    lang = item["lang"]
    stt_failed = None
    try:
        transcript = stt(audio, path.name, lang)
    except Exception as exc:  # keep the clip; the teacher verifies it by listening
        log.warning("transcription failed for %s/%s: %s", session_id, item_id, exc)
        transcript, stt_failed = Transcript(text="", words=[], segments=[]), str(exc)[:200]

    result = analyse_item(item, lang, transcript, live_tap=live_tap, known_words=bank.known_words(lang))
    if stt_failed:
        result.confidence.reasons.append("transcription failed")

    row = fill_row(row or ItemResultRow(session_id=session_id, item_id=item_id, lang=lang, section=item["section"]), result, transcript)
    row.audio_path = str(path)
    db.add(row)
    db.commit()
    db.refresh(row)
    return result_view(row)


@router.post("/sessions/{session_id}/finish")
def finish_session(session_id: int, db: Session = Depends(get_db), client=Depends(llm_client)):
    """Compute risk and write the summaries. Can be called again to refresh stale summaries."""
    sess = _get_session(db, session_id)
    sess.status = "finished"
    db.add(sess)
    db.commit()
    db.refresh(sess)
    report, _ = build_report(db, sess, with_summaries=True, llm_client=client)
    return {"session": session_view(sess), "report": report_view(report)}
