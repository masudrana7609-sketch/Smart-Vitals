"""The measures used to compare models (Output 4). Recall for Critical comes first: a missed Critical is a
missed alert (R4). False alarms per 100 Normal readings measures alarm fatigue (assumption A5)."""

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, precision_score, recall_score


def scores(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    normal = y_true == "Normal"
    false_alarms = (normal & (y_pred == "Critical")).sum()
    return {
        "recall Critical": recall_score(y_true, y_pred, labels=["Critical"], average="macro", zero_division=0),
        "false alarms /100 Normal": 100 * false_alarms / max(normal.sum(), 1),
        "precision Critical": precision_score(y_true, y_pred, labels=["Critical"], average="macro", zero_division=0),
        "recall Warning": recall_score(y_true, y_pred, labels=["Warning"], average="macro", zero_division=0),
        "F1 (macro)": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "balanced accuracy": balanced_accuracy_score(y_true, y_pred),
        "accuracy": accuracy_score(y_true, y_pred),
    }


def critical_threshold_for_recall(y_true, p_critical, target: float) -> float:
    """The highest threshold whose recall for Critical is at least the target, so the fewest false alarms
    that still meet it. Readings with P(Critical) >= threshold are called Critical."""
    y_true, p_critical = np.asarray(y_true), np.asarray(p_critical)
    p = np.sort(p_critical[y_true == "Critical"])
    if len(p) == 0:
        raise ValueError("no Critical readings to tune on")
    # at most k Critical readings may fall below the threshold (the tiny margin absorbs float rounding,
    # e.g. (1 - 0.8) * 10 = 1.9999999999999996)
    k = int(np.floor((1 - target) * len(p) + 1e-9))
    return float(p[min(k, len(p) - 1)])
