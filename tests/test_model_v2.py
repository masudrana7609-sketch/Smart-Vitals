"""Checks the model the API will use (models/model_v2, from notebook 02): it loads, answers with a known label,
copes with missing values (R9), and its saved test results meet the target (A5, T2)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.labelling import LABELS
from src.model import load, predict_with_threshold

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models" / "model_v2.joblib"


@pytest.fixture(scope="module")
def saved():
    if not MODEL.exists():
        pytest.skip("no model_v2 yet: run notebooks/02_compare_models.ipynb")
    return load(MODEL)


def example(info):
    return pd.DataFrame([info["example_row"]], columns=info["features"]).astype(float)


def test_answers_with_a_known_label(saved):
    model, info = saved
    assert predict_with_threshold(model, example(info), info["critical_threshold"])[0] in LABELS


def test_handles_every_vital_missing(saved):
    """R9: a reading with no usable values must not crash the model."""
    model, info = saved
    row = example(info)
    row.loc[:, [c for c in info["features"] if c not in ("risk_level", "diabetic", "spo2_scale")]] = np.nan
    assert predict_with_threshold(model, row, info["critical_threshold"])[0] in LABELS


def test_obvious_critical_reading_is_critical(saved):
    model, info = saved
    row = example(info)
    for col in ("spo2", "spo2_med5"):
        row[col] = 80.0  # far below the Scale 1 red band (91 or lower)
    row["spo2_scale"] = 1.0
    assert predict_with_threshold(model, row, info["critical_threshold"])[0] == "Critical"


def test_saved_results_meet_the_target(saved):
    _, info = saved
    assert info["test"]["recall Critical"] >= 0.90
    assert info["test"]["false alarms /100 Normal"] <= 5


def test_model_is_small_enough_for_git_and_the_edge():
    if not MODEL.exists():
        pytest.skip("no model_v2 yet")
    assert MODEL.stat().st_size < 20e6
