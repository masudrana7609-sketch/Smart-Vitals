"""The Smart Vitals API. Start it with:

    uvicorn app.main:create_app --factory --reload

Access control (R5): every endpoint except /health and /auth/login needs a clinician's token. A clinician
sees only their own patients and alerts (403 otherwise, T4); an admin can see every patient, manage
thresholds and read the audit log. Devices post readings with the ingest key, not a clinician login.
Every view, change, login and refused access is written to the audit log.
"""

import secrets
from datetime import UTC, datetime

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import alerts, audit, auth, pipeline
from app.classifier import Classifier
from app.config import Settings, get_settings
from app.db import init_db, make_engine, make_session_factory
from app.notify import LogNotifier
from app.schemas import (
    AlertOut,
    AuditOut,
    HistoryOut,
    IngestResult,
    LoginIn,
    PatientOut,
    PatientSummary,
    ReadingIn,
    ReadingOut,
    ThresholdIn,
    ThresholdOut,
    ThresholdsOut,
    TokenOut,
)
from app.tables import Alert, AuditEvent, Clinician, Patient, PatientThreshold, Reading
from src.labelling import BANDS
from src.vitals import PLAUSIBLE_RANGE, VITALS

bearer = HTTPBearer(auto_error=False)


def _limits_text(low: float | None, high: float | None) -> str:
    """Readable limits for the audit log, e.g. "low none, high 110"."""
    return f"low {'none' if low is None else f'{low:g}'}, high {'none' if high is None else f'{high:g}'}"


def create_app(settings: Settings | None = None, classifier=None, notifier=None) -> FastAPI:
    settings = settings or get_settings()
    auth.check_secret(settings.secret_key)
    engine = make_engine(settings.database_url)
    init_db(engine)
    app = FastAPI(
        title="Smart Vitals API", version="0.3.0", description="Prototype. Simulated data only. Not a medical device."
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.state.settings = settings
    app.state.sessions = make_session_factory(engine)
    app.state.classifier = classifier or Classifier(settings.model_path, settings.rule_safety_net)
    app.state.notifier = notifier or LogNotifier()
    throttle = auth.LoginThrottle(settings.login_max_failures, settings.login_lock_minutes)

    # --- dependencies ------------------------------------------------------------------------------

    def db(request: Request):
        with request.app.state.sessions() as session:
            yield session

    def current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer), session: Session = Depends(db)
    ) -> Clinician:
        if credentials is None:
            raise HTTPException(status_code=401, detail="log in first", headers={"WWW-Authenticate": "Bearer"})
        try:
            claims = auth.read_token(credentials.credentials, settings.secret_key)
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=401, detail="invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
            ) from None
        user = session.get(Clinician, claims["sub"])
        if user is None or user.password_hash is None:
            raise HTTPException(status_code=401, detail="unknown user", headers={"WWW-Authenticate": "Bearer"})
        return user

    def admin_only(user: Clinician = Depends(current_user), session: Session = Depends(db)) -> Clinician:
        if user.role != "admin":
            audit.record(session, user.id, "admin.denied", outcome="denied")
            session.commit()
            raise HTTPException(status_code=403, detail="admins only")
        return user

    def allowed_patient(session: Session, user: Clinician, patient_id: str, action: str) -> Patient:
        """The patient, if this user may see them. Refusals are audited (R5, T4)."""
        patient = session.get(Patient, patient_id)
        if patient is None:
            raise HTTPException(status_code=404, detail="patient not found")
        if user.role != "admin" and patient.clinician_id != user.id:
            audit.record(session, user.id, action, patient_id, outcome="denied")
            session.commit()
            raise HTTPException(status_code=403, detail="not your patient")
        return patient

    def now(session: Session) -> datetime:
        """The current time: the newest arrival in the feed's clock (A20), or the server's clock."""
        if settings.clock == "feed":
            latest = session.scalar(select(func.max(Reading.received_at)))
            if latest is not None:
                return latest
        return datetime.now(UTC).replace(tzinfo=None)

    # --- public ------------------------------------------------------------------------------------

    @app.get("/health")
    def health(session: Session = Depends(db)):
        return {"status": "ok", "model": app.state.classifier.version}

    @app.post("/auth/login", response_model=TokenOut)
    def login(body: LoginIn, session: Session = Depends(db)):
        if throttle.locked(body.username):
            audit.record(session, body.username, "login", outcome="denied", detail="too many failures")
            session.commit()
            raise HTTPException(status_code=429, detail="too many failed logins; try again later")
        user = session.get(Clinician, body.username)
        if not auth.verify_password(body.password, user.password_hash if user else None):
            throttle.failed(body.username)
            audit.record(session, body.username, "login", outcome="failed")
            session.commit()
            raise HTTPException(status_code=401, detail="wrong name or password")
        throttle.succeeded(body.username)
        audit.record(session, user.id, "login")
        session.commit()
        token = auth.make_token(user.id, user.role, settings.secret_key, settings.access_token_minutes)
        return TokenOut(
            access_token=token,
            expires_in=settings.access_token_minutes * 60,
            clinician_id=user.id,
            name=user.name,
            role=user.role,
        )

    # --- devices -----------------------------------------------------------------------------------

    @app.post("/readings", response_model=IngestResult)
    def post_reading(
        msg: ReadingIn,
        request: Request,
        session: Session = Depends(db),
        x_ingest_key: str | None = Header(default=None),
    ):
        if not settings.ingest_key:
            raise HTTPException(status_code=503, detail="HTTP ingest is off: set INGEST_KEY")
        if x_ingest_key is None or not secrets.compare_digest(x_ingest_key, settings.ingest_key):
            raise HTTPException(status_code=401, detail="device not authorised")
        outcome = pipeline.process(session, msg, request.app.state.classifier, settings, request.app.state.notifier)
        if outcome.result.result == "rejected":
            raise HTTPException(status_code=422, detail=outcome.result.reason)
        return outcome.result

    # --- clinicians --------------------------------------------------------------------------------

    @app.get("/me")
    def me(user: Clinician = Depends(current_user)):
        return {"clinician_id": user.id, "name": user.name, "role": user.role}

    @app.get("/patients", response_model=list[PatientSummary])
    def list_patients(user: Clinician = Depends(current_user), session: Session = Depends(db)):
        query = select(Patient).order_by(Patient.id)
        if user.role != "admin":
            query = query.where(Patient.clinician_id == user.id)
        out = []
        for patient in session.scalars(query):
            latest = session.scalars(
                select(Reading).where(Reading.patient_id == patient.id).order_by(Reading.measured_at.desc()).limit(1)
            ).first()
            open_alert = session.scalar(
                select(func.count(Alert.id)).where(Alert.patient_id == patient.id, Alert.state == "open")
            )
            out.append(
                PatientSummary(
                    **PatientOut.model_validate(patient).model_dump(),
                    latest_status=latest.status if latest else None,
                    latest_at=latest.measured_at if latest else None,
                    open_alert=bool(open_alert),
                )
            )
        audit.record_view(session, user.id, "patients.list", detail=f"{len(out)} patients")
        session.commit()
        return out

    @app.get("/patients/{patient_id}", response_model=PatientOut)
    def read_patient(patient_id: str, user: Clinician = Depends(current_user), session: Session = Depends(db)):
        patient = allowed_patient(session, user, patient_id, "patient.view")
        audit.record_view(session, user.id, "patient.view", patient_id)
        session.commit()
        return patient

    @app.get("/patients/{patient_id}/history", response_model=HistoryOut)
    def history(
        patient_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = Query(1440, ge=1, le=20000),
        user: Clinician = Depends(current_user),
        session: Session = Depends(db),
    ):
        """Readings and alerts for one patient, oldest first, in measured-time order (R6, T5)."""
        patient = allowed_patient(session, user, patient_id, "history.view")
        readings = select(Reading).where(Reading.patient_id == patient_id)
        found = select(Alert).where(Alert.patient_id == patient_id)
        if since:
            readings = readings.where(Reading.measured_at >= since.replace(tzinfo=None))
            found = found.where(Alert.raised_at >= since.replace(tzinfo=None))
        if until:
            readings = readings.where(Reading.measured_at <= until.replace(tzinfo=None))
            found = found.where(Alert.raised_at <= until.replace(tzinfo=None))
        newest = session.scalars(readings.order_by(Reading.measured_at.desc()).limit(limit)).all()
        result = HistoryOut(
            patient=PatientOut.model_validate(patient),
            readings=[ReadingOut.model_validate(r) for r in reversed(newest)],
            alerts=[AlertOut.model_validate(a) for a in session.scalars(found.order_by(Alert.raised_at))],
        )
        audit.record_view(session, user.id, "history.view", patient_id, detail=f"{len(newest)} readings")
        session.commit()
        return result

    @app.get("/alerts", response_model=list[AlertOut])
    def list_alerts(state: str | None = None, user: Clinician = Depends(current_user), session: Session = Depends(db)):
        query = select(Alert).order_by(Alert.raised_at.desc()).limit(500)
        if state:
            query = query.where(Alert.state == state)
        if user.role != "admin":
            query = query.where(Alert.clinician_id == user.id)
        found = session.scalars(query).all()
        audit.record_view(session, user.id, "alerts.list", detail=f"{len(found)} alerts")
        session.commit()
        return found

    @app.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
    def acknowledge(alert_id: int, user: Clinician = Depends(current_user), session: Session = Depends(db)):
        alert = session.get(Alert, alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="alert not found")
        if alert.clinician_id != user.id:
            audit.record(session, user.id, "alert.acknowledge", alert.patient_id, "denied", f"alert {alert_id}")
            session.commit()
            raise HTTPException(status_code=403, detail="only the assigned clinician can acknowledge this alert")
        if alert.state != "open":
            raise HTTPException(status_code=409, detail=f"alert is {alert.state}")
        alerts.acknowledge(session, alert, user.id, now(session))
        audit.record(session, user.id, "alert.acknowledge", alert.patient_id, detail=f"alert {alert_id}")
        session.commit()
        return alert

    # --- per-patient thresholds (R10) ----------------------------------------------------------------

    def thresholds_out(session: Session, patient: Patient) -> ThresholdsOut:
        limits = session.scalars(
            select(PatientThreshold).where(PatientThreshold.patient_id == patient.id).order_by(PatientThreshold.vital)
        )
        defaults = {k: [[None if u == float("inf") else u, p] for u, p in v] for k, v in BANDS.items()}
        return ThresholdsOut(
            patient_id=patient.id,
            spo2_scale=patient.spo2_scale,
            limits=[ThresholdOut.model_validate(t) for t in limits],
            defaults=defaults,
        )

    @app.get("/patients/{patient_id}/thresholds", response_model=ThresholdsOut)
    def get_thresholds(patient_id: str, user: Clinician = Depends(current_user), session: Session = Depends(db)):
        patient = allowed_patient(session, user, patient_id, "thresholds.view")
        audit.record_view(session, user.id, "thresholds.view", patient_id)
        session.commit()
        return thresholds_out(session, patient)

    @app.put("/patients/{patient_id}/thresholds/{vital}", response_model=ThresholdsOut)
    def set_threshold(
        patient_id: str,
        vital: str,
        body: ThresholdIn,
        user: Clinician = Depends(current_user),
        session: Session = Depends(db),
    ):
        """Set this patient's alert limits for one vital. Applies to readings from now on, not to history."""
        patient = allowed_patient(session, user, patient_id, "threshold.set")
        if vital not in VITALS:
            raise HTTPException(status_code=422, detail=f"unknown vital; expected one of {list(VITALS)}")
        if vital == "glucose" and not patient.diabetes:
            raise HTTPException(status_code=422, detail="glucose is only monitored for patients with diabetes")
        low_ok, high_ok = PLAUSIBLE_RANGE[vital]
        if body.low is None and body.high is None:
            raise HTTPException(status_code=422, detail="give a low limit, a high limit, or both")
        for bound in (body.low, body.high):
            if bound is not None and not low_ok <= bound <= high_ok:
                raise HTTPException(status_code=422, detail=f"limits for {vital} must be within {low_ok}-{high_ok}")
        if body.low is not None and body.high is not None and body.low >= body.high:
            raise HTTPException(status_code=422, detail="the low limit must be below the high limit")
        existing = session.scalar(
            select(PatientThreshold).where(PatientThreshold.patient_id == patient_id, PatientThreshold.vital == vital)
        )
        before = _limits_text(existing.low, existing.high) if existing else "default"
        threshold = existing or PatientThreshold(patient_id=patient_id, vital=vital)
        threshold.low, threshold.high, threshold.reason = body.low, body.high, body.reason
        threshold.set_by, threshold.set_at = user.id, datetime.now(UTC).replace(tzinfo=None)
        session.add(threshold)
        audit.record(
            session,
            user.id,
            "threshold.set",
            patient_id,
            detail=f"{vital}: {before} -> {_limits_text(body.low, body.high)}; {body.reason}",
        )
        session.commit()
        return thresholds_out(session, patient)

    @app.delete("/patients/{patient_id}/thresholds/{vital}", response_model=ThresholdsOut)
    def reset_threshold(
        patient_id: str, vital: str, user: Clinician = Depends(current_user), session: Session = Depends(db)
    ):
        patient = allowed_patient(session, user, patient_id, "threshold.reset")
        existing = session.scalar(
            select(PatientThreshold).where(PatientThreshold.patient_id == patient_id, PatientThreshold.vital == vital)
        )
        if existing is None:
            raise HTTPException(status_code=404, detail="no personal limit for this vital")
        session.delete(existing)
        audit.record(session, user.id, "threshold.reset", patient_id, detail=f"{vital}: back to default")
        session.commit()
        return thresholds_out(session, patient)

    # --- admin ---------------------------------------------------------------------------------------

    @app.get("/audit", response_model=list[AuditOut])
    def read_audit(
        patient_id: str | None = None,
        limit: int = Query(200, ge=1, le=5000),
        user: Clinician = Depends(admin_only),
        session: Session = Depends(db),
    ):
        query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
        if patient_id:
            query = query.where(AuditEvent.patient_id == patient_id)
        found = session.scalars(query).all()
        audit.record_view(session, user.id, "audit.view", patient_id)
        session.commit()
        return found

    return app
