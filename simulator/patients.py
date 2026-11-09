"""Synthetic patients: conditions, age band, history, personal baselines and an assigned clinician.

Every patient is invented. No real patient data is used at any stage (R7).
"""

import numpy as np
import pandas as pd

from simulator.config import SimConfig
from src.risk import AGE_BANDS, RISK_LEVEL, risk_group, risk_points

AGE_BAND_SHARE = (0.30, 0.30, 0.25, 0.15)

# Chance of each condition in the youngest band, and how much it rises with each older band
CONDITION_CHANCE = {
    "hypertension": (0.12, 0.12),
    "diabetes": (0.18, 0.06),  # about 25% overall (assumption A17)
    "arrhythmia": (0.04, 0.05),
    "copd": (0.03, 0.05),
}
# Hospital admissions in the last 12 months (Poisson mean) and chance of a past critical event:
# (base, added per older age band, added per condition)
ADMISSION_RATE = (0.2, 0.2, 0.35)
PRIOR_CRITICAL_CHANCE = (0.06, 0.05, 0.07)
SCALE2_SHARE_OF_COPD = 0.5  # COPD-like patients with a clinician-set 88-92% SpO2 target (assumption A12)


def clinician_ids(n_clinicians: int) -> list[str]:
    return [f"C{i:02d}" for i in range(1, n_clinicians + 1)]


def generate_patients(cfg: SimConfig, rng: np.random.Generator) -> pd.DataFrame:
    """One row per patient. Uses rng in a fixed order, so the same seed gives the same patients."""
    if cfg.n_clinicians < 1:
        raise ValueError("at least one clinician is needed")
    clinicians = clinician_ids(cfg.n_clinicians)
    rows = []
    for i in range(cfg.n_patients):
        band_index = int(rng.choice(len(AGE_BANDS), p=AGE_BAND_SHARE))
        has = {c: bool(rng.random() < base + step * band_index) for c, (base, step) in CONDITION_CHANCE.items()}
        conditions = [c for c, yes in has.items() if yes]
        a0, a_band, a_cond = ADMISSION_RATE
        admissions = int(min(rng.poisson(a0 + a_band * band_index + a_cond * len(conditions)), 3))
        c0, c_band, c_cond = PRIOR_CRITICAL_CHANCE
        prior_critical = bool(rng.random() < c0 + c_band * band_index + c_cond * len(conditions))
        points = risk_points(AGE_BANDS[band_index], conditions, admissions, prior_critical)
        group = risk_group(points)
        scale2 = has["copd"] and rng.random() < SCALE2_SHARE_OF_COPD

        # Personal baselines: the patient's usual values on a good day
        base_sbp = rng.normal(118, 9) + (16 if has["hypertension"] else 0) + 3 * band_index
        if has["copd"]:
            base_spo2 = rng.normal(90.5, 0.8) if scale2 else rng.normal(94.8, 0.6)
        else:
            base_spo2 = rng.normal(97.4, 0.7)
        rows.append(
            {
                "patient_id": f"P{i + 1:03d}",
                "device_id": f"W{i + 1:03d}",
                "clinician_id": clinicians[i % len(clinicians)],
                "age_band": AGE_BANDS[band_index],
                **{c: int(v) for c, v in has.items()},
                "admissions_12m": admissions,
                "prior_critical_event": int(prior_critical),
                "risk_points": points,
                "risk_group": group,
                "risk_level": RISK_LEVEL[group],
                "spo2_scale": 2 if scale2 else 1,
                "base_heart_rate": rng.normal(72, 7) + (4 if has["arrhythmia"] else 0),
                "base_spo2": min(base_spo2, 99.0),
                "base_systolic_bp": base_sbp,
                "base_diastolic_bp": 0.55 * base_sbp + rng.normal(13, 4),
                "base_temperature": rng.normal(36.7, 0.15),
                "base_glucose": rng.normal(7.5, 1.0) if has["diabetes"] else np.nan,
            }
        )
    patients = pd.DataFrame(rows)
    base_cols = [c for c in patients.columns if c.startswith("base_")]
    patients[base_cols] = patients[base_cols].round(2)
    return patients
