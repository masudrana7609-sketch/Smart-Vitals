"""Classifying readings with a saved model and its tuned Critical threshold. Used by the notebooks, the
tests and (from Sprint 2) the API."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.labelling import LABELS


def predict_with_threshold(model, X: pd.DataFrame, critical_threshold: float) -> np.ndarray:
    """Critical when the model's probability of Critical is at least the threshold; otherwise the more
    likely of Normal and Warning. A lower threshold finds more Critical readings and raises more false alarms."""
    proba = model.predict_proba(X)
    classes = list(model.classes_)
    p_critical = proba[:, classes.index("Critical")]
    rest = [c for c in classes if c != "Critical"]
    rest_proba = proba[:, [classes.index(c) for c in rest]]
    best_rest = np.array(rest)[rest_proba.argmax(axis=1)]
    return np.where(p_critical >= critical_threshold, "Critical", best_rest)


def load(model_path, info_path=None):
    """Load a saved model and its description file (features, labels, threshold)."""
    model_path = Path(model_path)
    info_path = Path(info_path) if info_path else model_path.with_suffix(".json")
    info = json.loads(info_path.read_text())
    if set(info["labels"]) != set(LABELS):
        raise ValueError(f"model labels {info['labels']} are not {LABELS}")
    return joblib.load(model_path), info
