"""Turning delivered readings into model inputs. Shared by the notebooks and (from Sprint 2) the API, so a
reading is prepared in exactly the same way in training and in live use.

1. clean_readings: drop duplicate messages and blank out impossible values (R9).
2. add_patient_settings: add per-patient settings the API knows from the patient record (SpO2 scale).
3. add_window_features: add the median of each vital over the patient's last few readings.
"""

import numpy as np
import pandas as pd

from src.vitals import VITALS, is_plausible

SINGLE_FEATURES = ["risk_level", "diabetic", "spo2_scale", *VITALS]
WINDOW = 5  # readings: the current one and the four before it (about 5 minutes)
WINDOW_FEATURES = [f"{v}_med{WINDOW}" for v in VITALS]


def clean_readings(readings: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Keep the first copy of each msg_id, set impossible values to NaN, and sort by patient and time.
    Returns the cleaned readings and a count of what was changed."""
    before = len(readings)
    df = readings.drop_duplicates("msg_id", keep="first").copy()
    report = {"duplicates_dropped": before - len(df)}
    for vital in VITALS:
        bad = ~is_plausible(vital, df[vital])
        report[f"impossible_{vital}"] = int(bad.sum())
        df.loc[bad, vital] = np.nan
    df["measured_ts"] = pd.to_datetime(df["measured_at"])
    df = df.sort_values(["patient_id", "measured_ts"], kind="stable").reset_index(drop=True)
    return df, report


def add_patient_settings(readings: pd.DataFrame, patients: pd.DataFrame) -> pd.DataFrame:
    """Add the patient's SpO2 scale (1 or 2), set by a clinician and stored with the patient (A12, R10)."""
    scale = patients.set_index("patient_id")["spo2_scale"]
    out = readings.copy()
    out["spo2_scale"] = out["patient_id"].map(scale)
    if out["spo2_scale"].isna().any():
        missing = sorted(out.loc[out["spo2_scale"].isna(), "patient_id"].unique())
        raise ValueError(f"no SpO2 scale for patient(s) {missing}")
    return out


def add_window_features(readings: pd.DataFrame, window: int = WINDOW) -> pd.DataFrame:
    """Median of each vital over this reading and the window-1 before it, for the same patient.
    Uses only past and current readings, never later ones. Readings must be sorted by patient and time
    (clean_readings does this). Missing values are skipped; a window with no values gives NaN."""
    out = readings.copy()
    grouped = out.groupby("patient_id", sort=False)
    for vital in VITALS:
        out[f"{vital}_med{window}"] = grouped[vital].transform(lambda s: s.rolling(window, min_periods=1).median())
    return out
