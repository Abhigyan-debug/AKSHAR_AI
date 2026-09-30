"""Public parent page data. The random token in the link is the only
key; the response carries no child code or name."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import Child, ReadingSession, Report
from ..services import practice
from ..services.store import LEVEL_LABELS_HI
from .deps import get_db

router = APIRouter()

HELP_HI = [
    "स्कूल के काउंसलर या कक्षा शिक्षक से बात करें।",
    "नज़दीकी सरकारी अस्पताल के बच्चों के विभाग में जाँच करवाएँ।",
    "RCI (भारतीय पुनर्वास परिषद) से पंजीकृत विशेष शिक्षक से मिलें।",
]
DISCLAIMER_HI = "यह केवल एक स्क्रीनिंग है, कोई निदान नहीं। इसकी सीमाएँ डेमो के लिए हैं और चिकित्सकीय रूप से प्रमाणित नहीं हैं।"


@router.get("/parent/{token}")
def parent_view(token: str, db: Session = Depends(get_db)):
    """What the parent page shows. No child code or name: the link is shareable."""
    report = db.exec(select(Report).where(Report.parent_token == token)).first()
    if not report:
        raise HTTPException(404, "report not found")
    sess = db.get(ReadingSession, report.session_id)
    child = db.get(Child, sess.child_id)
    ready = report.risk_level not in ("pending", "provisional")
    return {
        "ready": ready,
        "grade": child.grade,
        "risk_level": report.risk_level,
        "label_hi": LEVEL_LABELS_HI[report.risk_level],
        "summary_hi": report.parent_summary_hi,
        "tips_hi": json.loads(report.home_tips_json),
        "help_hi": HELP_HI,
        "show_help": report.risk_level in ("specialist_check", "reading_support", "hindi_support"),
        "disclaimer_hi": DISCLAIMER_HI,
        # Game ids ordered by the child's own error pattern; empty until the result is final.
        "practice": practice.recommend(json.loads(report.metrics_json), report.risk_level) if ready else [],
    }


@router.get("/practice")
def practice_content():
    """Practice game content (public: it holds no child data)."""
    return practice.content()
