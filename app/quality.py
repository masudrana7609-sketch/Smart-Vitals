"""Quality checks on each reading before it is classified (R9).

- missing vital: kept as missing; the model copes, and a gap never raises an alert by itself (T7)
- impossible value: treated as a sensor error, set to missing, never a Critical alert (T9)
- late: flagged; stored in the right time order; may raise no new alert if very old (T8)
- stuck sensor: the same value many times in a row; set to missing so a frozen normal value cannot hide a
  deterioration and a frozen abnormal one cannot raise a false alarm
- glucose from a patient without diabetes: ignored (we do not store data we do not need)
"""

import math
from dataclasses import dataclass, field
from datetime import datetime

from src.vitals import VITALS, is_plausible

# SpO2 and temperature legitimately repeat (whole percent, one decimal), so only these are checked for sticking
STUCK_CHECKED = ("heart_rate", "systolic_bp", "diastolic_bp", "glucose")


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


@dataclass
class Checked:
    values: dict
    flags: list[str] = field(default_factory=list)
    late: bool = False
    delay_minutes: float = 0.0


def check(
    values: dict, measured_at: datetime, received_at: datetime, diabetic: bool, late_after_minutes: float
) -> Checked:
    out = Checked(values=dict(values))
    for vital in VITALS:
        value = out.values.get(vital)
        if vital == "glucose" and not diabetic:
            if not _missing(value):
                out.flags.append("ignored:glucose")
            out.values[vital] = None
            continue
        if _missing(value):
            out.values[vital] = None
            out.flags.append(f"missing:{vital}")
        elif not bool(is_plausible(vital, value)):
            out.values[vital] = None
            out.flags.append(f"sensor_error:{vital}")
    out.delay_minutes = (received_at - measured_at).total_seconds() / 60
    if out.delay_minutes > late_after_minutes:
        out.late = True
        out.flags.append("late")
    if out.delay_minutes < -1:
        out.flags.append("clock:measured_after_received")
    return out


def stuck_vitals(current: dict, previous: list[dict], run: int) -> list[str]:
    """Vitals whose value equals each of the previous run-1 readings (most recent first)."""
    if len(previous) < run - 1:
        return []
    stuck = []
    for vital in STUCK_CHECKED:
        value = current.get(vital)
        if _missing(value):
            continue
        if all(p.get(vital) == value for p in previous[: run - 1]):
            stuck.append(vital)
    return stuck
