"""Tests for src/features.py, src/evaluation.py and src/model.py: preparing readings (R9) and scoring models."""

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

from src.evaluation import critical_threshold_for_recall, scores
from src.features import WINDOW_FEATURES, add_patient_settings, add_window_features, clean_readings
from src.model import predict_with_threshold


def readings(**overrides):
    base = {
        "msg_id": ["P1-1", "P1-2", "P1-2", "P1-3", "P2-1"],
        "patient_id": ["P1", "P1", "P1", "P1", "P2"],
        "measured_at": [
            "2026-01-05T00:01:00Z",
            "2026-01-05T00:02:00Z",
            "2026-01-05T00:02:00Z",
            "2026-01-05T00:03:00Z",
            "2026-01-05T00:01:00Z",
        ],
        "heart_rate": [70.0, 80.0, 80.0, 250.0, 60.0],
        "spo2": [97.0, 96.0, 96.0, 95.0, 98.0],
        "systolic_bp": [120.0, 122.0, 122.0, 124.0, 110.0],
        "diastolic_bp": [80.0, 81.0, 81.0, 82.0, 70.0],
        "temperature": [36.8, 36.9, 36.9, 37.0, 36.5],
        "glucose": [np.nan] * 5,
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_duplicates_are_dropped():
    df, report = clean_readings(readings())
    assert df["msg_id"].is_unique
    assert report["duplicates_dropped"] == 1


def test_impossible_values_become_missing_not_alerts():
    df, report = clean_readings(readings())
    assert np.isnan(df.loc[df["msg_id"] == "P1-3", "heart_rate"]).all()
    assert report["impossible_heart_rate"] == 1


def test_late_readings_are_put_back_in_time_order():
    shuffled = readings().iloc[[3, 0, 4, 1]]  # P1-3 arrived first
    df, _ = clean_readings(shuffled)
    p1 = df[df["patient_id"] == "P1"]
    assert list(p1["msg_id"]) == ["P1-1", "P1-2", "P1-3"]


def test_patient_settings_are_required():
    df, _ = clean_readings(readings())
    with_scale = add_patient_settings(df, pd.DataFrame({"patient_id": ["P1", "P2"], "spo2_scale": [1, 2]}))
    assert with_scale.set_index("msg_id").at["P2-1", "spo2_scale"] == 2
    with pytest.raises(ValueError, match="P2"):
        add_patient_settings(df, pd.DataFrame({"patient_id": ["P1"], "spo2_scale": [1]}))


def test_window_uses_only_past_readings_of_the_same_patient():
    df, _ = clean_readings(readings())
    out = add_window_features(df, window=2).set_index("msg_id")
    assert out.at["P1-1", "heart_rate_med2"] == 70  # nothing earlier
    assert out.at["P1-2", "heart_rate_med2"] == 75  # median of 70 and 80
    assert out.at["P1-3", "heart_rate_med2"] == 80  # the impossible 250 was removed, so only 80 is left
    assert out.at["P2-1", "heart_rate_med2"] == 60  # never mixes patients


def test_window_does_not_look_ahead():
    """Changing a later reading must not change an earlier reading's window value (no leakage)."""
    df, _ = clean_readings(readings())
    first = add_window_features(df).set_index("msg_id")
    df.loc[df["msg_id"] == "P1-3", "spo2"] = 70.0
    second = add_window_features(df).set_index("msg_id")
    assert first.at["P1-2", "spo2_med5"] == second.at["P1-2", "spo2_med5"]
    assert set(WINDOW_FEATURES) <= set(first.columns)


def test_scores_count_false_alarms_per_100_normal():
    truth = ["Normal"] * 100 + ["Critical"] * 10
    pred = ["Critical"] * 3 + ["Normal"] * 97 + ["Critical"] * 9 + ["Normal"]
    s = scores(truth, pred)
    assert s["false alarms /100 Normal"] == pytest.approx(3.0)
    assert s["recall Critical"] == pytest.approx(0.9)


def test_threshold_meets_the_recall_target():
    y = np.array(["Critical"] * 10 + ["Normal"] * 10)
    p = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05] + [0.01] * 10)
    t = critical_threshold_for_recall(y, p, target=0.8)
    assert (p[:10] >= t).mean() >= 0.8
    assert t == pytest.approx(0.2)  # the highest threshold that still finds 8 of 10


def test_lower_threshold_never_finds_fewer_critical():
    X = pd.DataFrame({"x": np.zeros(20)})
    y = ["Normal"] * 14 + ["Warning"] * 2 + ["Critical"] * 4
    model = DummyClassifier(strategy="prior").fit(X, y)  # P(Critical) = 0.2 for every reading
    assert (predict_with_threshold(model, X, 0.5) == "Critical").sum() == 0
    assert (predict_with_threshold(model, X, 0.2) == "Critical").all()
    assert set(predict_with_threshold(model, X, 0.9)) == {"Normal"}
