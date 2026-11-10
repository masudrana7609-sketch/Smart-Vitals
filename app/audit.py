"""The audit log (R5): who logged in, viewed, changed or was refused what, and when. Written in the same
transaction as the action where there is one, so the log and the data cannot disagree.

Views (lists, histories, thresholds) are recorded at most once per VIEW_REPEAT_MINUTES for the same person,
action and patient: the dashboard refreshes every few seconds, and logging every refresh would bury the
events that matter. Logins, changes and refusals are always recorded.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.tables import AuditEvent

VIEW_REPEAT_MINUTES = 5


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def record(
    session, actor: str, action: str, patient_id: str | None = None, outcome: str = "ok", detail: str = ""
) -> None:
    session.add(
        AuditEvent(
            at=_now(), actor=actor[:32], action=action, patient_id=patient_id, outcome=outcome, detail=detail[:300]
        )
    )


def record_view(session, actor: str, action: str, patient_id: str | None = None, detail: str = "") -> None:
    since = _now() - timedelta(minutes=VIEW_REPEAT_MINUTES)
    recent = session.scalar(
        select(AuditEvent.id)
        .where(
            AuditEvent.actor == actor,
            AuditEvent.action == action,
            AuditEvent.patient_id.is_(None) if patient_id is None else AuditEvent.patient_id == patient_id,
            AuditEvent.outcome == "ok",
            AuditEvent.at >= since,
        )
        .limit(1)
    )
    if recent is None:
        record(session, actor, action, patient_id, detail=detail)
