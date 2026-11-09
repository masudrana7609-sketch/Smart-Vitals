"""Each patient's hidden state over time, and the vitals it produces.

    true vital = personal baseline + circadian drift + slow random walk + episode effects
    observed vital = true vital + sensor noise

The hidden severity s(t) (0 = well, 1 = the worst an episode gets) comes from deterioration episodes.
Episodes start at random, more often for higher risk groups, ramp up, stay at their worst for a while and
recover. The label for each minute is the NEWS2-inspired label of the TRUE vitals (src/labelling.py), so
the model must recover it from noisy, imperfect observations.

Everything is invented for teaching and testing. It is not a physiological model.
"""

import numpy as np
import pandas as pd
from scipy.signal import lfilter

from simulator.config import SimConfig
from src.labelling import label
from src.vitals import PLAUSIBLE_RANGE, VITALS

# Slow random walk around the baseline: typical size (standard deviation) and time constant
WALK_SD = {"heart_rate": 4.0, "spo2": 0.5, "systolic_bp": 5.0, "diastolic_bp": 3.0, "temperature": 0.12, "glucose": 0.8}
WALK_MINUTES = 60

# Sensor noise (standard deviation); glucose noise is a share of the value (about 8%, like a CGM)
NOISE_SD = {"heart_rate": 2.0, "spo2": 1.0, "systolic_bp": 5.0, "diastolic_bp": 4.0, "temperature": 0.1}
GLUCOSE_NOISE_SHARE = 0.08

# Limits of the TRUE values, so overlapping episodes stay physiologically possible
TRUE_LIMITS = {
    "heart_rate": (30, 200),
    "spo2": (70, 100),
    "systolic_bp": (60, 240),
    "diastolic_bp": (30, 140),
    "temperature": (34.0, 41.5),
    "glucose": (1.5, 33.0),
}

# How each episode moves the vitals at full severity (s = 1). None: worked out per patient below.
EPISODES = {
    "sepsis_like": {"heart_rate": 45, "temperature": 2.6, "systolic_bp": -45, "diastolic_bp": -25, "spo2": -4},
    "hypoxic": {"spo2": -12, "heart_rate": 30},
    "hypertensive_crisis": {"systolic_bp": 95, "diastolic_bp": 45, "heart_rate": 12},
    "arrhythmia": {"heart_rate": None, "systolic_bp": -15, "diastolic_bp": -8},
    "hypoglycaemia": {"glucose": None, "heart_rate": 25},
    "hyperglycaemia": {"glucose": 18, "heart_rate": 10},
}
# Worst severity an episode reaches: mostly moderate, sometimes severe
PEAK_MIN = 0.2
PEAK_BETA = (1.6, 2.0)
MEALS_HOUR = (8, 13, 19)
MEAL_RISE = 2.5  # mmol/L at the peak, about 45 minutes after a meal


def episode_weights(patient) -> dict:
    """Relative chance of each episode type for this patient: conditions make some much more likely."""
    weights = {
        "sepsis_like": 1.0,
        "hypoxic": 3.0 if patient["copd"] else 1.0,
        "hypertensive_crisis": 3.0 if patient["hypertension"] else 0.5,
        "arrhythmia": 4.0 if patient["arrhythmia"] else 0.7,
    }
    if patient["diabetes"]:
        weights["hypoglycaemia"] = 1.5
        weights["hyperglycaemia"] = 1.5
    return weights


def _walk(rng, n, sd, tau=WALK_MINUTES):
    """A random walk that is pulled back towards 0 (Ornstein-Uhlenbeck), with standard deviation sd."""
    theta = 1.0 / tau
    sigma = sd * np.sqrt(2 * theta - theta**2)
    start = rng.normal(0, sd)
    steps = rng.normal(0, sigma, n)
    steps[0] += start
    return lfilter([1.0], [1.0, -(1 - theta)], steps)


def _smooth(x):
    """0 to 1 with a gentle start and finish."""
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def _episodes(patient, cfg, rng, minutes):
    """Draw this patient's episodes. Returns a list of (type, severity curve, offsets)."""
    rate = cfg.episode_rate_per_day[patient["risk_group"]]
    count = rng.poisson(rate * cfg.days)
    weights = episode_weights(patient)
    types = list(weights)
    probs = np.array(list(weights.values())) / sum(weights.values())
    out = []
    for _ in range(count):
        kind = types[rng.choice(len(types), p=probs)]
        onset = rng.uniform(0, minutes[-1])
        ramp, plateau, recovery = rng.uniform(30, 180), rng.uniform(30, 240), rng.uniform(30, 180)
        peak = PEAK_MIN + (1 - PEAK_MIN) * rng.beta(*PEAK_BETA)
        t = minutes - onset
        curve = peak * np.where(
            t < ramp, _smooth(t / ramp), np.where(t < ramp + plateau, 1.0, 1 - _smooth((t - ramp - plateau) / recovery))
        )
        curve = np.where(t < 0, 0.0, curve)
        offsets = dict(EPISODES[kind])
        if kind == "sepsis_like" and rng.random() < 0.15:
            offsets["temperature"] = -1.8  # some septic patients get cold, not hot
        if kind == "arrhythmia":
            fast = rng.random() < 0.7
            offsets["heart_rate"] = rng.uniform(60, 95) if fast else -(patient["base_heart_rate"] - 38)
        if kind == "hypoglycaemia":
            offsets["glucose"] = -(patient["base_glucose"] - 2.0)
        out.append((kind, curve, offsets))
    return out


def simulate_patient(patient, cfg: SimConfig, rng: np.random.Generator) -> pd.DataFrame:
    """Every expected reading for one patient: true vitals, observed vitals, severity and label."""
    n = cfg.n_readings
    minutes = np.arange(n, dtype=float) * cfg.interval_minutes
    hour = (minutes / 60) % 24
    diabetic = bool(patient["diabetes"])

    def daily(amplitude, peak_hour):
        return amplitude * np.cos(2 * np.pi * (hour - peak_hour) / 24)

    true = {
        "heart_rate": patient["base_heart_rate"] + daily(5, 15),
        "spo2": patient["base_spo2"] + daily(0.3, 14),
        "systolic_bp": patient["base_systolic_bp"] + daily(7, 14),
        "diastolic_bp": patient["base_diastolic_bp"] + daily(4, 14),
        "temperature": patient["base_temperature"] + daily(0.25, 18),
    }
    if diabetic:
        meals = np.zeros(n)
        for meal in MEALS_HOUR:
            since = (hour - meal) % 24 * 60  # minutes since the last such meal
            meals += np.where(since < 300, MEAL_RISE * (since / 45) * np.exp(1 - since / 45), 0)
        true["glucose"] = patient["base_glucose"] + meals
    else:
        true["glucose"] = np.full(n, np.nan)

    for vital in VITALS:
        if vital == "glucose" and not diabetic:
            continue
        true[vital] = true[vital] + _walk(rng, n, WALK_SD[vital])

    severity = np.zeros(n)
    episode_type = np.full(n, "none", dtype=object)
    for kind, curve, offsets in _episodes(patient, cfg, rng, minutes):
        for vital, offset in offsets.items():
            if vital == "glucose" and not diabetic:
                continue
            true[vital] = true[vital] + curve * offset
        stronger = curve > severity
        episode_type = np.where(stronger & (curve > 0.01), kind, episode_type)
        severity = np.maximum(severity, curve)

    for vital, (low, high) in TRUE_LIMITS.items():
        true[vital] = np.clip(true[vital], low, high)

    observed = {}
    for vital in VITALS:
        if vital == "glucose":
            noisy = true[vital] * (1 + rng.normal(0, GLUCOSE_NOISE_SHARE, n)) if diabetic else true[vital]
        else:
            noisy = true[vital] + rng.normal(0, NOISE_SD[vital], n)
        low, high = PLAUSIBLE_RANGE[vital]
        observed[vital] = np.clip(noisy, low, high)  # a real sensor saturates at the end of its range

    score, status = label(
        true["heart_rate"],
        true["spo2"],
        true["systolic_bp"],
        true["temperature"],
        true["glucose"],
        patient["spo2_scale"],
    )

    frame = pd.DataFrame({"patient_id": patient["patient_id"], "minute": minutes.astype(int)})
    for vital in VITALS:
        frame[f"true_{vital}"] = np.round(true[vital], 2)
    frame["heart_rate"] = np.round(observed["heart_rate"])
    frame["spo2"] = np.round(observed["spo2"])
    frame["systolic_bp"] = np.round(observed["systolic_bp"])
    frame["diastolic_bp"] = np.round(observed["diastolic_bp"])
    frame["temperature"] = np.round(observed["temperature"], 1)
    frame["glucose"] = np.round(observed["glucose"], 1)
    frame["severity"] = np.round(severity, 3)
    frame["episode_type"] = episode_type
    frame["news_score"] = score
    frame["status"] = status
    return frame
