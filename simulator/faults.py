"""Problems built in on purpose, so R9 can be tested: dropouts, silent devices, late and out-of-order
messages, impossible values, stuck sensors and duplicate messages.

Each expected reading gets at most one fault, recorded in the ground truth (fault_type, fault_vital,
delay_minutes, delivered). The delivered feed itself never says which readings are faulty: the system
has to work that out, as it would in real use.
"""

import numpy as np
import pandas as pd

from simulator.config import FaultRates
from src.vitals import VITALS

FAULT_TYPES = ("none", "missing_vital", "impossible", "late", "duplicate", "silent", "stuck")

# Values no working sensor could report (all outside src.vitals.PLAUSIBLE_RANGE)
IMPOSSIBLE_VALUES = {
    "heart_rate": (0, 250, 300),
    "spo2": (0, 104, 127),
    "systolic_bp": (0, 320),
    "diastolic_bp": (0, 250),
    "temperature": (10.0, 45.0),
    "glucose": (0.0, 60.0),
}
SENSORS_WITHOUT_GLUCOSE = tuple(v for v in VITALS if v != "glucose")


def _vitals_for(diabetic: bool) -> tuple:
    return VITALS if diabetic else SENSORS_WITHOUT_GLUCOSE


def _windows(rng, n_readings, per_day, days, length_range, interval):
    """Random [start, end) windows of readings for one patient."""
    out = []
    for _ in range(rng.poisson(per_day * days)):
        length = int(rng.integers(length_range[0], length_range[1] + 1) // interval) or 1
        start = int(rng.integers(0, max(n_readings - 1, 1)))
        out.append((start, min(start + length, n_readings)))
    return out


def apply_faults(
    readings: pd.DataFrame,
    patients: pd.DataFrame,
    rates: FaultRates,
    days: float,
    interval_minutes: int,
    rng: np.random.Generator,
):
    """Add faults to the readings of every patient.

    readings must have one row per expected reading, sorted by patient_id then minute.
    Returns (readings with fault columns, the observed values changed where a fault requires it).
    """
    df = readings.copy()
    n = len(df)
    df["fault_type"] = "none"
    df["fault_vital"] = ""
    df["delay_minutes"] = 0.0
    df["copies"] = 1
    diabetic = df["patient_id"].map(patients.set_index("patient_id")["diabetes"]).astype(bool).to_numpy()
    fault = np.array(df["fault_type"], dtype=object)  # writable copies (pandas 3 arrays are read-only)
    fault_vital = np.array(df["fault_vital"], dtype=object)

    # Window faults, patient by patient: silent devices first, then stuck sensors
    starts = df.groupby("patient_id", sort=False).indices
    for idx in starts.values():
        idx = np.sort(idx)
        n_p = len(idx)
        for a, b in _windows(rng, n_p, rates.silent_per_day, days, rates.silent_minutes, interval_minutes):
            rows = idx[a:b]
            fault[rows[fault[rows] == "none"]] = "silent"
        is_diabetic = bool(diabetic[idx[0]])
        for a, b in _windows(rng, n_p, rates.stuck_per_day, days, rates.stuck_minutes, interval_minutes):
            vital = _vitals_for(is_diabetic)[rng.integers(len(_vitals_for(is_diabetic)))]
            # skip a window that overlaps or touches an earlier stuck window: each stuck spell has one value
            if (fault[idx[max(a - 1, 0) : b + 1]] == "stuck").any():
                continue
            frozen = df.at[idx[a], vital]
            rows = idx[a + 1 : b]  # the first reading is genuine; the sensor then stops updating
            rows = rows[fault[rows] == "none"]
            df.loc[rows, vital] = frozen
            fault[rows] = "stuck"
            fault_vital[rows] = vital

    # Per-reading faults, on readings that have no fault yet (at most one fault each)
    draw = rng.random(n)
    edges = np.cumsum([rates.missing_vital, rates.impossible, rates.late, rates.duplicate])
    kind = np.select(
        [draw < edges[0], draw < edges[1], draw < edges[2], draw < edges[3]],
        ["missing_vital", "impossible", "late", "duplicate"],
        "none",
    )
    free = fault == "none"
    fault = np.where(free, kind, fault)

    for i in np.flatnonzero(free & (kind == "missing_vital")):
        options = _vitals_for(bool(diabetic[i]))
        vital = options[rng.integers(len(options))]
        df.iat[i, df.columns.get_loc(vital)] = np.nan
        fault_vital[i] = vital
    for i in np.flatnonzero(free & (kind == "impossible")):
        options = _vitals_for(bool(diabetic[i]))
        vital = options[rng.integers(len(options))]
        choices = IMPOSSIBLE_VALUES[vital]
        df.iat[i, df.columns.get_loc(vital)] = choices[rng.integers(len(choices))]
        fault_vital[i] = vital
    late = free & (kind == "late")
    delay = np.array(df["delay_minutes"], dtype=float)
    delay[late] = rng.uniform(*rates.late_minutes, late.sum())
    copies = np.array(df["copies"])
    copies[free & (kind == "duplicate")] = 2

    df["fault_type"] = fault
    df["fault_vital"] = fault_vital
    df["delay_minutes"] = np.round(delay, 2)
    df["copies"] = np.where(fault == "silent", 0, copies)
    df["delivered"] = df["copies"] > 0
    return df
