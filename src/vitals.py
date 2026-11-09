"""The vital signs Smart Vitals measures, their units, and the range a working sensor can report.

A value outside PLAUSIBLE_RANGE is treated as a sensor error, not as a patient getting worse (R9, test T9).
The ranges are deliberately wide: they reject impossible values, not abnormal ones.
"""

import numpy as np

VITALS = ("heart_rate", "spo2", "systolic_bp", "diastolic_bp", "temperature", "glucose")

UNITS = {
    "heart_rate": "beats/min",
    "spo2": "%",
    "systolic_bp": "mmHg",
    "diastolic_bp": "mmHg",
    "temperature": "°C",
    "glucose": "mmol/L",  # UK units; only for patients with diabetes
}

# (lowest, highest) value a working sensor could report for a living patient
PLAUSIBLE_RANGE = {
    "heart_rate": (20, 230),
    "spo2": (50, 100),
    "systolic_bp": (50, 260),
    "diastolic_bp": (25, 160),
    "temperature": (30.0, 43.0),
    "glucose": (1.0, 40.0),
}


def is_plausible(vital, value):
    """True where the value could come from a working sensor. Missing values (NaN) count as plausible:
    a dropout is a different problem from a sensor error. Works on a number or a numpy/pandas array."""
    low, high = PLAUSIBLE_RANGE[vital]
    value = np.asarray(value, dtype=float)
    return np.isnan(value) | ((value >= low) & (value <= high))
