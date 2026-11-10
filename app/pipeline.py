"""What happens to every reading, whichever way it arrives (MQTT or HTTP):

duplicate? -> known patient and device? -> quality checks -> classify with recent history -> store
-> alert rule -> reminders -> commit -> send notifications (only after the data is safely stored)
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import alerts, quality
from app.schemas import IngestResult, ReadingIn, to_utc_naive
from app.tables import Patient, Reading
from src.vitals import VITALS

log = logging.getLogger("smartvitals.pipeline")


@dataclass
class Outcome:
    result: IngestResult
    notifications: list = field(default_factory=list)


def received_time(msg: ReadingIn, clock: str) -> datetime:
    """The arrival time: the simulator's clock (A20) or the server's own."""
    if clock == "feed":
        return to_utc_naive(msg.sent_at or msg.measured_at)
    return datetime.now(UTC).replace(tzinfo=None)


def _previous(session: Session, patient_id: str, before: datetime, limit: int) -> tuple[list[dict], list[dict]]:
    """The patient's earlier readings, most recent first: (values after quality checks, values as received)."""
    rows = session.scalars(
        select(Reading)
        .where(Reading.patient_id == patient_id, Reading.measured_at < before)
        .order_by(Reading.measured_at.desc())
        .limit(limit)
    ).all()
    return [{v: getattr(r, v) for v in VITALS} for r in rows], [{v: r.raw.get(v) for v in VITALS} for r in rows]


def process(session: Session, msg: ReadingIn, classifier, settings, notifier) -> Outcome:
    if session.scalar(select(Reading.id).where(Reading.msg_id == msg.msg_id)) is not None:
        return Outcome(IngestResult(result="duplicate", msg_id=msg.msg_id))
    patient = session.get(Patient, msg.patient_id)
    if patient is None:
        return Outcome(IngestResult(result="rejected", msg_id=msg.msg_id, reason="unknown patient"))
    if patient.device_id != msg.device_id:
        return Outcome(IngestResult(result="rejected", msg_id=msg.msg_id, reason="device not registered to patient"))

    measured = to_utc_naive(msg.measured_at)
    received = received_time(msg, settings.clock)
    checked = quality.check(msg.values(), measured, received, patient.diabetes, settings.late_after_minutes)
    previous, previous_raw = _previous(
        session, patient.id, measured, max(classifier.window, settings.stuck_readings) - 1
    )
    # compare with the values as received: a stuck value is blanked when stored, but the sensor is still stuck
    for vital in quality.stuck_vitals(checked.values, previous_raw, settings.stuck_readings):
        checked.values[vital] = None
        checked.flags.append(f"stuck:{vital}")
    result = classifier.classify(patient, checked.values, previous)

    reading = Reading(
        msg_id=msg.msg_id,
        patient_id=patient.id,
        device_id=msg.device_id,
        measured_at=measured,
        received_at=received,
        raw=msg.model_dump(mode="json"),
        flags=checked.flags,
        status=result.status,
        p_critical=result.p_critical,
        decided_by=result.decided_by,
        news_score=result.news_score,
        score_parts=result.parts,
        model_version=classifier.version,
        **checked.values,
    )
    session.add(reading)
    try:
        session.flush()
    except IntegrityError:  # the same message arrived twice at the same moment
        session.rollback()
        return Outcome(IngestResult(result="duplicate", msg_id=msg.msg_id))

    notes = alerts.on_reading(session, patient, reading, result, checked.late, received, settings)
    notes += alerts.due_reminders(session, received, settings)
    session.commit()
    for note in notes:
        try:
            notifier.send(note)
        except Exception:  # a failed message must not lose the stored reading; it stays in the database
            log.exception("could not send notification %s", note.id)
    raised = sum(n.kind in ("new", "escalation") for n in notes)
    return Outcome(
        IngestResult(
            result="stored", msg_id=msg.msg_id, status=result.status, flags=checked.flags, alerts_raised=raised
        ),
        notes,
    )
