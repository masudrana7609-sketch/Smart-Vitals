"""The shapes of messages in and out of the API."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from src.vitals import VITALS


def to_utc_naive(moment: datetime) -> datetime:
    """Store every time as UTC without a time zone. A time with no zone is taken to be UTC already."""
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment


class ReadingIn(BaseModel):
    """One message from a wearable. A missing vital is null or left out (a dropout, R9)."""

    model_config = ConfigDict(extra="ignore")
    msg_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    device_id: str = Field(min_length=1, max_length=32)
    patient_id: str = Field(min_length=1, max_length=16)
    measured_at: datetime
    sent_at: datetime | None = None  # simulated arrival time (clock = "feed", A20)
    heart_rate: float | None = None
    spo2: float | None = None
    systolic_bp: float | None = None
    diastolic_bp: float | None = None
    temperature: float | None = None
    glucose: float | None = None

    def values(self) -> dict:
        return {v: getattr(self, v) for v in VITALS}


class IngestResult(BaseModel):
    result: str  # "stored", "duplicate" or "rejected"
    msg_id: str
    reason: str | None = None
    status: str | None = None  # Normal / Warning / Critical
    flags: list[str] = []
    alerts_raised: int = 0


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    device_id: str
    clinician_id: str
    age_band: str
    hypertension: bool
    diabetes: bool
    arrhythmia: bool
    copd: bool
    risk_group: str
    risk_level: int
    spo2_scale: int


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    msg_id: str
    measured_at: datetime
    received_at: datetime
    heart_rate: float | None
    spo2: float | None
    systolic_bp: float | None
    diastolic_bp: float | None
    temperature: float | None
    glucose: float | None
    flags: list[str]
    status: str
    p_critical: float
    decided_by: str
    news_score: int
    score_parts: dict


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_id: str
    clinician_id: str
    kind: str
    state: str
    raised_at: datetime
    vitals: dict
    news_score: int
    red_vitals: list[str]
    p_critical: float
    decided_by: str
    reminders: int
    acknowledged_at: datetime | None
    acknowledged_by: str | None


class HistoryOut(BaseModel):
    patient: PatientOut
    readings: list[ReadingOut]
    alerts: list[AlertOut]


class AcknowledgeIn(BaseModel):
    clinician_id: str  # from the login token in Sprint 3
