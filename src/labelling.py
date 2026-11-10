"""Normal / Warning / Critical labels from a NEWS2-inspired points score.

INSPIRED BY NEWS2 (Royal College of Physicians, 2017). THIS IS NOT A CLINICAL SCORE.
- Pulse, systolic BP, temperature and SpO2 (Scales 1 and 2) use the NEWS2 bands, checked against the
  RCP 2017 chart.
- NEWS2 also scores breathing rate, consciousness and supplemental oxygen. Smart Vitals does not measure
  them, so this is a partial score (a limitation: see docs/assumptions.md).
- Glucose is not part of NEWS2. Its bands are this project's own invention (assumption A11).
- Per-patient limits (R10, apply_personal_limits) replace the default bands for the vitals they cover.
- Mapping to labels (agreed 9 Nov 2026, assumption A10): Critical if the total is 5 or more (the NEWS2
  "urgent response" threshold) or any single parameter scores 3 (a NEWS2 "red" score); Warning if the
  total is 3 or 4; otherwise Normal.

A missing value scores 0: it adds no evidence either way. Glucose is missing for patients without diabetes.
"""

import numpy as np

LABELS = ("Normal", "Warning", "Critical")

# Each band list is (highest value in the band, points), in rising order. Values are rounded first:
# whole numbers for pulse, SpO2 and blood pressure; one decimal place for temperature and glucose.
BANDS = {
    "heart_rate": [(40, 3), (50, 1), (90, 0), (110, 1), (130, 2), (np.inf, 3)],
    "systolic_bp": [(90, 3), (100, 2), (110, 1), (219, 0), (np.inf, 3)],
    "temperature": [(35.0, 3), (36.0, 1), (38.0, 0), (39.0, 1), (np.inf, 2)],
    "spo2_scale1": [(91, 3), (93, 2), (95, 1), (np.inf, 0)],
    # Scale 2 is for a 88-92% target (e.g. hypercapnic respiratory failure); on air, 93% or more scores 0
    "spo2_scale2": [(83, 3), (85, 2), (87, 1), (np.inf, 0)],
    "glucose": [(2.9, 3), (3.9, 2), (13.9, 0), (19.9, 2), (np.inf, 3)],  # mmol/L, project's own bands
}
DECIMALS = {"heart_rate": 0, "systolic_bp": 0, "temperature": 1, "spo2": 0, "glucose": 1}

CRITICAL_TOTAL = 5
WARNING_TOTAL = 3
RED_SCORE = 3


def band_points(value, bands):
    """Points for each value from a band list. NaN scores 0."""
    value = np.atleast_1d(np.asarray(value, dtype=float))
    uppers = np.array([upper for upper, _ in bands])
    points = np.array([pts for _, pts in bands])
    index = np.searchsorted(uppers, np.nan_to_num(value, nan=0.0), side="left")
    return np.where(np.isnan(value), 0, points[np.minimum(index, len(points) - 1)])


def score_parts(heart_rate, spo2, systolic_bp, temperature, glucose=np.nan, spo2_scale=1):
    """Points for each parameter (arrays of the same length). Diastolic BP is not scored, as in NEWS2."""
    values = {
        "heart_rate": heart_rate,
        "spo2": spo2,
        "systolic_bp": systolic_bp,
        "temperature": temperature,
        "glucose": glucose,
    }
    n = max(np.size(v) for v in values.values())
    rounded = {k: np.round(np.broadcast_to(np.asarray(v, dtype=float), (n,)), DECIMALS[k]) for k, v in values.items()}
    scale = np.broadcast_to(np.asarray(spo2_scale), (n,))
    spo2_points = np.where(
        scale == 2,
        band_points(rounded["spo2"], BANDS["spo2_scale2"]),
        band_points(rounded["spo2"], BANDS["spo2_scale1"]),
    )
    return {
        "heart_rate": band_points(rounded["heart_rate"], BANDS["heart_rate"]),
        "spo2": spo2_points,
        "systolic_bp": band_points(rounded["systolic_bp"], BANDS["systolic_bp"]),
        "temperature": band_points(rounded["temperature"], BANDS["temperature"]),
        "glucose": band_points(rounded["glucose"], BANDS["glucose"]),
    }


def status_from_parts(parts):
    """Total score and label for each reading."""
    stacked = np.vstack(list(parts.values()))
    total = stacked.sum(axis=0)
    red = stacked.max(axis=0) >= RED_SCORE
    status = np.where(
        (total >= CRITICAL_TOTAL) | red, "Critical", np.where(total >= WARNING_TOTAL, "Warning", "Normal")
    )
    return total, status


def label(heart_rate, spo2, systolic_bp, temperature, glucose=np.nan, spo2_scale=1):
    """Convenience: (total score, label) for one reading or arrays of readings."""
    return status_from_parts(score_parts(heart_rate, spo2, systolic_bp, temperature, glucose, spo2_scale))


def apply_personal_limits(parts: dict, values: dict, limits: dict) -> dict:
    """Per-patient alert limits set by a clinician (R10) replace the default bands for those vitals:
    a value inside [low, high] scores 0, a value outside scores 3 (a red score). A missing bound means no
    limit on that side; a missing value scores 0. limits: {vital: (low, high)}."""
    out = dict(parts)
    for vital, (low, high) in limits.items():
        value = values.get(vital)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            out[vital] = 0
            continue
        inside = (low is None or value >= low) and (high is None or value <= high)
        out[vital] = 0 if inside else RED_SCORE
    return out


def status_from_points(points: dict) -> tuple[int, str]:
    """(total, label) from points per vital, one reading."""
    total = int(sum(points.values()))
    if total >= CRITICAL_TOTAL or max(points.values(), default=0) >= RED_SCORE:
        return total, "Critical"
    return total, ("Warning" if total >= WARNING_TOTAL else "Normal")
