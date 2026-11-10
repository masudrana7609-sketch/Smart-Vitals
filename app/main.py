"""The Smart Vitals API. Start it with:

    uvicorn app.main:create_app --factory --reload

Sprint 2: readings in (HTTP; MQTT goes through app/mqtt_ingest.py and the same pipeline), patient history,
alerts and acknowledgement. Sprint 3 adds logins: every endpoint below will then check that the clinician
may see the patient (R5). Until then this API must only run on a private network with simulated data.
"""

from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import alerts, pipeline
from app.classifier import Classifier
from app.config import Settings, get_settings
from app.db import init_db, make_engine, make_session_factory
from app.notify import LogNotifier
from app.schemas import AcknowledgeIn, AlertOut, HistoryOut, IngestResult, PatientOut, ReadingIn, ReadingOut
from app.tables import Alert, Clinician, Patient, Reading


def create_app(settings: Settings | None = None, classifier=None, notifier=None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    app = FastAPI(
        title="Smart Vitals API", version="0.2.0", description="Prototype. Simulated data only. Not a medical device."
    )
    app.state.settings = settings
    app.state.sessions = make_session_factory(engine)
    app.state.classifier = classifier or Classifier(settings.model_path, settings.rule_safety_net)
    app.state.notifier = notifier or LogNotifier()

    def db(request: Request):
        with request.app.state.sessions() as session:
            yield session

    def now(session: Session) -> datetime:
        """The current time: the newest arrival in the feed's clock (A20), or the server's clock."""
        if settings.clock == "feed":
            latest = session.scalar(select(func.max(Reading.received_at)))
            if latest is not None:
                return latest
        return datetime.now(UTC).replace(tzinfo=None)

    @app.get("/health")
    def health(session: Session = Depends(db)):
        return {
            "status": "ok",
            "model": app.state.classifier.version,
            "readings": session.scalar(select(func.count(Reading.id))),
        }

    @app.post("/readings", response_model=IngestResult)
    def post_reading(msg: ReadingIn, request: Request, session: Session = Depends(db)):
        outcome = pipeline.process(session, msg, request.app.state.classifier, settings, request.app.state.notifier)
        if outcome.result.result == "rejected":
            raise HTTPException(status_code=422, detail=outcome.result.reason)
        return outcome.result

    @app.get("/patients", response_model=list[PatientOut])
    def list_patients(clinician_id: str | None = None, session: Session = Depends(db)):
        query = select(Patient).order_by(Patient.id)
        if clinician_id:
            query = query.where(Patient.clinician_id == clinician_id)
        return session.scalars(query).all()

    def get_patient(session: Session, patient_id: str) -> Patient:
        patient = session.get(Patient, patient_id)
        if patient is None:
            raise HTTPException(status_code=404, detail="patient not found")
        return patient

    @app.get("/patients/{patient_id}", response_model=PatientOut)
    def read_patient(patient_id: str, session: Session = Depends(db)):
        return get_patient(session, patient_id)

    @app.get("/patients/{patient_id}/history", response_model=HistoryOut)
    def history(
        patient_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = Query(1440, ge=1, le=20000),
        session: Session = Depends(db),
    ):
        """Readings and alerts for one patient, oldest first, in measured-time order (R6, T5)."""
        patient = get_patient(session, patient_id)
        readings = select(Reading).where(Reading.patient_id == patient_id)
        found = select(Alert).where(Alert.patient_id == patient_id)
        if since:
            readings = readings.where(Reading.measured_at >= since.replace(tzinfo=None))
            found = found.where(Alert.raised_at >= since.replace(tzinfo=None))
        if until:
            readings = readings.where(Reading.measured_at <= until.replace(tzinfo=None))
            found = found.where(Alert.raised_at <= until.replace(tzinfo=None))
        newest = session.scalars(readings.order_by(Reading.measured_at.desc()).limit(limit)).all()
        return HistoryOut(
            patient=PatientOut.model_validate(patient),
            readings=[ReadingOut.model_validate(r) for r in reversed(newest)],
            alerts=[AlertOut.model_validate(a) for a in session.scalars(found.order_by(Alert.raised_at))],
        )

    @app.get("/alerts", response_model=list[AlertOut])
    def list_alerts(state: str | None = None, clinician_id: str | None = None, session: Session = Depends(db)):
        query = select(Alert).order_by(Alert.raised_at.desc())
        if state:
            query = query.where(Alert.state == state)
        if clinician_id:
            query = query.where(Alert.clinician_id == clinician_id)
        return session.scalars(query).all()

    @app.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
    def acknowledge(alert_id: int, body: AcknowledgeIn, session: Session = Depends(db)):
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="alert not found")
        if session.get(Clinician, body.clinician_id) is None or body.clinician_id != alert.clinician_id:
            raise HTTPException(status_code=403, detail="only the assigned clinician can acknowledge this alert")
        if alert.state != "open":
            raise HTTPException(status_code=409, detail=f"alert is {alert.state}")
        alerts.acknowledge(session, alert, body.clinician_id, now(session))
        session.commit()
        return alert

    return app
