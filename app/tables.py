"""Database tables. Only what the system needs is stored (data minimisation, R7): no names, addresses or
dates of birth for patients, only an ID, the clinical facts the risk group and model need, and readings."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Clinician(Base):
    """A user of the dashboard: a clinician, or an admin who manages thresholds and reads the audit log."""

    __tablename__ = "clinicians"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # also the login name
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(12), default="clinician")  # "clinician" or "admin"
    password_hash: Mapped[str | None] = mapped_column(String(200))  # argon2; never the password itself


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(32), unique=True)
    clinician_id: Mapped[str] = mapped_column(ForeignKey("clinicians.id"), index=True)
    age_band: Mapped[str] = mapped_column(String(8))
    hypertension: Mapped[bool] = mapped_column(Boolean, default=False)
    diabetes: Mapped[bool] = mapped_column(Boolean, default=False)
    arrhythmia: Mapped[bool] = mapped_column(Boolean, default=False)
    copd: Mapped[bool] = mapped_column(Boolean, default=False)
    admissions_12m: Mapped[int] = mapped_column(Integer, default=0)
    prior_critical_event: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_group: Mapped[str] = mapped_column(String(8))  # R1, from src/risk.py
    risk_level: Mapped[int] = mapped_column(Integer)
    spo2_scale: Mapped[int] = mapped_column(Integer, default=1)  # set by a clinician (A12)


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (Index("ix_readings_patient_time", "patient_id", "measured_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    msg_id: Mapped[str] = mapped_column(String(64), unique=True)  # idempotency key (T10)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    device_id: Mapped[str] = mapped_column(String(32))
    measured_at: Mapped[datetime] = mapped_column(DateTime)  # UTC
    received_at: Mapped[datetime] = mapped_column(DateTime)  # UTC
    heart_rate: Mapped[float | None] = mapped_column(Float)
    spo2: Mapped[float | None] = mapped_column(Float)
    systolic_bp: Mapped[float | None] = mapped_column(Float)
    diastolic_bp: Mapped[float | None] = mapped_column(Float)
    temperature: Mapped[float | None] = mapped_column(Float)
    glucose: Mapped[float | None] = mapped_column(Float)
    raw: Mapped[dict] = mapped_column(JSON)  # the values as received, before quality checks
    flags: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["missing:spo2", "late"]
    status: Mapped[str] = mapped_column(String(10))  # Normal / Warning / Critical
    p_critical: Mapped[float] = mapped_column(Float)
    decided_by: Mapped[str] = mapped_column(String(16))  # "model" or "rule"
    news_score: Mapped[int] = mapped_column(Integer)  # NEWS2-inspired score of the last-5 median
    score_parts: Mapped[dict] = mapped_column(JSON)  # points per vital: why it was flagged
    model_version: Mapped[str] = mapped_column(String(32))


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    clinician_id: Mapped[str] = mapped_column(ForeignKey("clinicians.id"), index=True)
    reading_id: Mapped[int] = mapped_column(ForeignKey("readings.id"))
    kind: Mapped[str] = mapped_column(String(12))  # "new" or "escalation"
    state: Mapped[str] = mapped_column(String(12), index=True)  # "open", "acknowledged", "superseded"
    raised_at: Mapped[datetime] = mapped_column(DateTime)  # the Critical reading's measured time
    vitals: Mapped[dict] = mapped_column(JSON)
    news_score: Mapped[int] = mapped_column(Integer)
    red_vitals: Mapped[list] = mapped_column(JSON, default=list)
    p_critical: Mapped[float] = mapped_column(Float)
    decided_by: Mapped[str] = mapped_column(String(16))
    reminders: Mapped[int] = mapped_column(Integer, default=0)
    last_notified_at: Mapped[datetime] = mapped_column(DateTime)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    acknowledged_by: Mapped[str | None] = mapped_column(String(16))


class Notification(Base):
    """Every message sent to a clinician about an alert: the evidence for R4."""

    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    clinician_id: Mapped[str] = mapped_column(ForeignKey("clinicians.id"))
    kind: Mapped[str] = mapped_column(String(12))  # "new", "reminder", "escalation"
    sent_at: Mapped[datetime] = mapped_column(DateTime)
    message: Mapped[str] = mapped_column(String(500))


class PatientThreshold(Base):
    """A clinician's personal alert limits for one vital of one patient (R10)."""

    __tablename__ = "patient_thresholds"
    __table_args__ = (Index("ux_threshold_patient_vital", "patient_id", "vital", unique=True),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    vital: Mapped[str] = mapped_column(String(16))
    low: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(300))
    set_by: Mapped[str] = mapped_column(String(16))
    set_at: Mapped[datetime] = mapped_column(DateTime)


class AuditEvent(Base):
    """Who looked at or changed what, and when (R5). Times are the server's real clock, in UTC."""

    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, index=True)
    actor: Mapped[str] = mapped_column(String(32))  # clinician ID, or the login name tried
    action: Mapped[str] = mapped_column(String(32))  # e.g. "login", "history.view", "threshold.set"
    patient_id: Mapped[str | None] = mapped_column(String(16), index=True)
    outcome: Mapped[str] = mapped_column(String(12))  # "ok", "denied", "failed"
    detail: Mapped[str] = mapped_column(String(300), default="")
