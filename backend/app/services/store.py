"""Converts between ItemResult and its database row, and (re)builds a
session's report (risk + summaries)."""

import json
import secrets
from dataclasses import asdict
from datetime import datetime, timezone

from sqlmodel import Session, select

from ..db import Child, ItemResultRow, ReadingSession, Report
from . import bank
from .analyse import ItemResult, awaiting_verification
from .classify_rules import ErrorLabel, WordPair
from .confidence import Confidence
from .llm import NOT_FINAL, generate_summaries, label_residual_errors, template_summaries
from .risk import RiskReport, compute_risk
from .timing import Timing
from .transcribe import Transcript

LEVEL_LABELS_HI = {
    "low_risk": "पढ़ाई ठीक चल रही है",
    "english_exposure_gap": "अंग्रेज़ी का अभ्यास कम है, अंग्रेज़ी में मदद चाहिए",
    "reading_support": "पढ़ने में थोड़ी मदद की ज़रूरत है",
    "hindi_support": "हिंदी पढ़ने में मदद की ज़रूरत है",
    "specialist_check": "विशेषज्ञ से जाँच करवाने की सलाह",
    "provisional": "जाँच अभी पूरी हो रही है",
    "pending": "जाँच अभी पूरी हो रही है",
}


def _dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False)


def fill_row(row: ItemResultRow, r: ItemResult, transcript: Transcript | None = None) -> ItemResultRow:
    row.item_id, row.lang, row.section = r.item_id, r.lang, r.section
    row.transcript = r.transcript
    if transcript is not None:
        row.words_json = _dumps([asdict(w) for w in transcript.words])
    row.correct, row.suggested_correct, row.skipped = r.correct, r.suggested_correct, r.skipped
    row.errors_json = _dumps([asdict(e) for e in r.errors])
    row.status, row.verified, row.live_tap = r.status, r.verified, r.live_tap
    row.avg_logprob, row.no_speech_prob = r.confidence.avg_logprob, r.confidence.no_speech_prob
    row.confidence_reasons_json = _dumps(r.confidence.reasons)
    row.start_latency_ms = None if r.timing.start_latency_s is None else round(r.timing.start_latency_s * 1000)
    row.duration_ms = None if r.timing.duration_s is None else round(r.timing.duration_s * 1000)
    row.hesitation = r.timing.hesitation
    row.timing_json = _dumps(asdict(r.timing))
    row.words_correct, row.words_total = r.words_correct, r.words_total
    row.pairs_json = _dumps([asdict(p) for p in r.pairs])
    row.updated_at = datetime.now(timezone.utc)
    return row


def row_to_result(row: ItemResultRow) -> ItemResult:
    return ItemResult(
        item_id=row.item_id,
        lang=row.lang,
        section=row.section,
        status=row.status,
        transcript=row.transcript,
        correct=row.correct,
        suggested_correct=row.suggested_correct,
        skipped=row.skipped,
        errors=[ErrorLabel(**e) for e in json.loads(row.errors_json)],
        timing=Timing(**json.loads(row.timing_json)),
        confidence=Confidence(
            avg_logprob=row.avg_logprob,
            no_speech_prob=row.no_speech_prob,
            low=row.status == "teacher_verify",
            reasons=json.loads(row.confidence_reasons_json),
        ),
        words_total=row.words_total,
        words_correct=row.words_correct,
        pairs=[WordPair(**p) for p in json.loads(row.pairs_json)],
        live_tap=row.live_tap,
        verified=row.verified,
    )


def session_rows(db: Session, session_id: int) -> list[ItemResultRow]:
    return list(db.exec(select(ItemResultRow).where(ItemResultRow.session_id == session_id).order_by(ItemResultRow.id)))


def build_report(db: Session, sess: ReadingSession, *, with_summaries: bool, llm_client=None) -> tuple[Report, RiskReport]:
    """Recompute risk for a session.

    with_summaries=True (finish button): label residual errors and write the
    summaries (LLM when the result is final, else a template). Otherwise the AI
    summary is written automatically the first time the result is final with an
    empty verify queue; before that a template is refreshed; after it, a change
    only marks the summary stale."""
    child = db.get(Child, sess.child_id)
    rows = session_rows(db, sess.id)
    results = [row_to_result(r) for r in rows]
    risk = compute_risk(results, child.grade, bank_counts=bank.section_counts())
    report = db.get(Report, sess.id)
    if report is None:
        report = Report(session_id=sess.id, parent_token=secrets.token_urlsafe(16))
    has_ai_summary = report.summary_source == "llm"
    # The result is final and nothing is left to verify: write the real summary now, once.
    if not with_summaries and not has_ai_summary and risk.level not in NOT_FINAL and risk.pending_verify == 0:
        with_summaries = True

    if with_summaries:
        if label_residual_errors(results, bank.items(), client=llm_client):
            for row, r in zip(rows, results):
                row.errors_json = _dumps([asdict(e) for e in r.errors])
                db.add(row)

        # LLM labels can change the error pattern, so recompute risk with them.
        risk = compute_risk(results, child.grade, bank_counts=bank.section_counts())
    changed = report.risk_level != risk.level or report.reasons_json != _dumps(risk.reasons)

    report.metrics_json = _dumps({lang: asdict(m) for lang, m in risk.languages.items()})
    report.scoring_breakdown_json = _dumps(risk.scoring_breakdown)
    report.risk_level = risk.level
    report.reasons_json = _dumps(risk.reasons)
    if with_summaries or not has_ai_summary:
        # Without an AI summary yet, the template is refreshed on every change (no LLM call).
        s = generate_summaries(risk, child.grade, client=llm_client) if with_summaries else template_summaries(risk)
        report.teacher_summary, report.next_step = s.teacher_summary, s.next_step
        report.parent_summary_hi, report.home_tips_json = s.parent_summary_hi, _dumps(s.home_tips_hi)
        report.summary_source, report.summary_stale = s.source, False
    elif changed:
        report.summary_stale = True
    report.updated_at = datetime.now(timezone.utc)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report, risk


def result_view(row: ItemResultRow) -> dict:
    """An item result as the teacher UI sees it."""
    item = bank.items().get(row.item_id, {})
    r = row_to_result(row)
    return {
        "id": row.id,
        "item_id": row.item_id,
        "lang": row.lang,
        "section": row.section,
        "text": item.get("text"),
        "prompt": item.get("prompt"),
        "is_nonword": bool(item.get("is_nonword")),
        "status": row.status,
        "verified": row.verified,
        "live_tap": row.live_tap,
        "awaiting_verification": awaiting_verification(r),
        "transcript": row.transcript,
        "correct": row.correct,
        "suggested_correct": row.suggested_correct,
        "skipped": row.skipped,
        "errors": json.loads(row.errors_json),
        "pairs": json.loads(row.pairs_json),
        "words_correct": row.words_correct,
        "words_total": row.words_total,
        "confidence": {
            "avg_logprob": row.avg_logprob,
            "no_speech_prob": row.no_speech_prob,
            "reasons": json.loads(row.confidence_reasons_json),
        },
        "timing": json.loads(row.timing_json),
        "audio_url": f"/api/audio/{row.id}" if row.audio_path else None,
    }


def report_view(report: Report | None) -> dict | None:
    if report is None:
        return None
    from .risk import LEVELS

    emoji, label = LEVELS[report.risk_level]
    return {
        "risk_level": report.risk_level,
        "emoji": emoji,
        "label": label,
        "reasons": json.loads(report.reasons_json),
        "metrics": json.loads(report.metrics_json),
        "scoring_breakdown": json.loads(report.scoring_breakdown_json),
        "teacher_summary": report.teacher_summary,
        "next_step": report.next_step,
        "summary_source": report.summary_source,
        "summary_stale": report.summary_stale,
        "parent_token": report.parent_token,
        "updated_at": report.updated_at.isoformat(),
    }
