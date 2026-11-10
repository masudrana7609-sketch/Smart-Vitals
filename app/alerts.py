"""The alert rule (R4, ADR 5, A6).

- A Critical reading raises an alert to the patient's assigned clinician, with the patient ID, the vitals and
  the time, unless the patient already has an open alert.
- While an alert is open, a reading that is WORSE (a NEWS2-inspired score at least 2 points higher, or a vital
  newly in the red band) raises an escalation at once; the old alert is marked superseded, so there is
  still one open alert.
  In the first escalation_settle_minutes after an alert the same event is still unfolding (the median is
  catching up), so a worse reading only updates the open alert's details, without another message.
- An open alert that nobody has acknowledged is re-sent as a reminder every alert_reminder_minutes, while the
  patient is not back to Normal (the alert still stays open until a clinician reviews it).
- After an acknowledgement, the patient gets no new alert for alert_reminder_minutes unless they get worse.
- A reading that arrives more than late_alert_max_minutes after it was measured is stored but raises no
  new alert: the clinician should act on the patient's current state, not an old one.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tables import Alert, Notification, Patient, Reading

UNITS = {
    "heart_rate": "bpm",
    "spo2": "%",
    "systolic_bp": "mmHg",
    "diastolic_bp": "mmHg",
    "temperature": "C",
    "glucose": "mmol/L",
}
SHORT = {
    "heart_rate": "HR",
    "spo2": "SpO2",
    "systolic_bp": "SBP",
    "diastolic_bp": "DBP",
    "temperature": "Temp",
    "glucose": "Glucose",
}


def message(kind: str, alert: Alert) -> str:
    vitals = ", ".join(f"{SHORT[k]} {v:g}{UNITS[k]}" for k, v in alert.vitals.items() if v is not None)
    red = f"; red: {', '.join(alert.red_vitals)}" if alert.red_vitals else ""
    head = {"new": "CRITICAL", "escalation": "CRITICAL - WORSE", "reminder": "REMINDER - CRITICAL"}[kind]
    return (
        f"{head}: patient {alert.patient_id} at {alert.raised_at:%Y-%m-%d %H:%M} UTC. {vitals} "
        f"(score {alert.news_score}{red}; decided by {alert.decided_by})"
    )[:500]


WORSE_BY = 2  # points: a rise of 1 happens every minute while a median climbs, and is not news


def _worse(result, than: Alert) -> bool:
    """Meaningfully worse: the score rose by WORSE_BY or more, or a vital is newly in the red band."""
    return result.news_score >= than.news_score + WORSE_BY or bool(set(result.red_vitals) - set(than.red_vitals))


def _refresh(alert: Alert, reading: Reading, result) -> None:
    alert.reading_id = reading.id
    alert.vitals = {k: getattr(reading, k) for k in UNITS}
    alert.news_score = result.news_score
    alert.red_vitals = result.red_vitals
    alert.p_critical = result.p_critical


def _notify(session: Session, alert: Alert, kind: str, now: datetime) -> Notification:
    note = Notification(
        alert_id=alert.id, clinician_id=alert.clinician_id, kind=kind, sent_at=now, message=message(kind, alert)
    )
    session.add(note)
    return note


def on_reading(
    session: Session, patient: Patient, reading: Reading, result, late: bool, now: datetime, settings
) -> list[Notification]:
    """Decide whether this classified reading raises an alert. Returns the notifications to send."""
    if result.status != "Critical":
        return []
    if late and now - reading.measured_at > timedelta(minutes=settings.late_alert_max_minutes):
        return []
    open_alert = session.scalar(select(Alert).where(Alert.patient_id == patient.id, Alert.state == "open"))
    if open_alert is not None:
        if not _worse(result, open_alert):
            return []
        if now - open_alert.raised_at < timedelta(minutes=settings.escalation_settle_minutes):
            _refresh(open_alert, reading, result)  # the same event still unfolding: update it quietly
            return []
        open_alert.state = "superseded"
        kind = "escalation"
    else:
        last_ack = session.scalar(
            select(Alert)
            .where(Alert.patient_id == patient.id, Alert.state == "acknowledged")
            .order_by(Alert.acknowledged_at.desc())
            .limit(1)
        )
        quiet = timedelta(minutes=settings.alert_reminder_minutes)
        if last_ack is not None and now - last_ack.acknowledged_at < quiet and not _worse(result, last_ack):
            return []
        kind = "new"
    alert = Alert(
        patient_id=patient.id,
        clinician_id=patient.clinician_id,
        reading_id=reading.id,
        kind=kind,
        state="open",
        raised_at=reading.measured_at,
        vitals={k: getattr(reading, k) for k in UNITS},
        news_score=result.news_score,
        red_vitals=result.red_vitals,
        p_critical=result.p_critical,
        decided_by=result.decided_by,
        reminders=0,
        last_notified_at=now,
    )
    session.add(alert)
    session.flush()
    return [_notify(session, alert, kind, now)]


def _latest_status(session: Session, patient_id: str) -> str | None:
    return session.scalar(select(Reading.status).where(Reading.patient_id == patient_id)
                          .order_by(Reading.measured_at.desc()).limit(1))


def due_reminders(session: Session, now: datetime, settings) -> list[Notification]:
    """Re-send every open alert that has waited alert_reminder_minutes since its last message, unless the
    patient's latest reading is Normal again: the alert stays open for review, but stops reminding."""
    due = now - timedelta(minutes=settings.alert_reminder_minutes)
    notes = []
    for alert in session.scalars(select(Alert).where(Alert.state == "open", Alert.last_notified_at <= due)):
        if _latest_status(session, alert.patient_id) == "Normal":
            continue
        alert.reminders += 1
        alert.last_notified_at = now
        notes.append(_notify(session, alert, "reminder", now))
    return notes


def acknowledge(session: Session, alert: Alert, clinician_id: str, now: datetime) -> None:
    alert.state = "acknowledged"
    alert.acknowledged_at = now
    alert.acknowledged_by = clinician_id
