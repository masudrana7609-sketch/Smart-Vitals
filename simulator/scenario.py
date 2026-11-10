"""A scripted 26-minute story for one patient that shows each requirement in the demo and the tests.

| Minute | What happens | Test | Expected |
|---|---|---|---|
| 0-9 | normal readings | | stored, Normal |
| 10 | SpO2 missing (sensor dropout) | T7 | stored, flagged, no alert |
| 11 | heart rate 250 (impossible) | T9 | flagged as a sensor error, no alert |
| 12, 14 | normal | | |
| 13 | measured at minute 13 but delivered at minute 20 | T8 | stored in time order, flagged late |
| 15-25 | deteriorating: SpO2 well below the red band, fast pulse | T3 | ONE alert to the assigned clinician |
| 17 | delivered twice (same msg_id) | T10 | stored once, still one alert |
"""

import numpy as np
import pandas as pd

from src.vitals import VITALS

CRITICAL_FROM, CRITICAL_TO = 15, 25
LATE_MINUTE, LATE_ARRIVES = 13, 20
DUPLICATE_MINUTE = 17


def _iso(t: pd.Timestamp) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


JITTER = {"heart_rate": 2, "spo2": 0.6, "systolic_bp": 3, "diastolic_bp": 2, "temperature": 0.1, "glucose": 0.2}


def build(patient: dict, start: str = "2026-01-06T00:00:00Z", seed: int = 1) -> list[dict]:
    """Messages for one patient (a row of sim_patients.csv), in the order they arrive. Values vary a little
    (seeded), as real readings do, so the stuck-sensor check is not triggered."""
    t0 = pd.Timestamp(start)
    rng = np.random.default_rng(seed)
    normal = {
        "heart_rate": round(patient["base_heart_rate"]),
        "spo2": round(patient["base_spo2"]),
        "systolic_bp": round(patient["base_systolic_bp"]),
        "diastolic_bp": round(patient["base_diastolic_bp"]),
        "temperature": round(patient["base_temperature"], 1),
    }
    if patient["diabetes"]:
        normal["glucose"] = round(patient["base_glucose"], 1)
    critical = dict(normal, heart_rate=118, spo2=80 if patient["spo2_scale"] == 2 else 84)

    messages = []
    for minute in range(CRITICAL_TO + 1):
        values = dict(critical if minute >= CRITICAL_FROM else normal)
        for k in values:
            decimals = 1 if k in ("temperature", "glucose") else 0
            values[k] = round(values[k] + rng.normal(0, JITTER[k]), decimals)
        values["spo2"] = min(values["spo2"], 100)
        if minute == 10:
            values.pop("spo2")
        if minute == 11:
            values["heart_rate"] = 250
        measured = t0 + pd.Timedelta(minutes=minute)
        arrives = t0 + pd.Timedelta(minutes=LATE_ARRIVES if minute == LATE_MINUTE else minute, seconds=1)
        message = {
            "msg_id": f"{patient['patient_id']}-S{minute:04d}",
            "device_id": patient["device_id"],
            "patient_id": patient["patient_id"],
            "measured_at": _iso(measured),
            "sent_at": _iso(arrives),
            **{k: float(v) for k, v in values.items() if k in VITALS},
        }
        messages.append(message)
        if minute == DUPLICATE_MINUTE:
            messages.append(dict(message, sent_at=_iso(arrives + pd.Timedelta(seconds=5))))
    return sorted(messages, key=lambda m: m["sent_at"])
