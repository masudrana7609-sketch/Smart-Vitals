"""Classifies a reading with model v2 (notebook 02), using the patient's last few readings, and explains it.

The NEWS2-inspired rule runs on the same last-5 median as a safety net (rule_safety_net): if the rule says
Critical and the model does not, the reading is Critical and decided_by = "rule". The rule's points per vital
are stored with every reading, so a clinician can see why an alert fired.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.labelling import RED_SCORE, score_parts, status_from_parts
from src.model import load, predict_with_threshold
from src.vitals import VITALS


@dataclass
class Result:
    status: str
    p_critical: float
    decided_by: str
    news_score: int
    parts: dict
    red_vitals: list
    medians: dict


class Classifier:
    def __init__(self, model_path: str, rule_safety_net: bool = True):
        self.model, self.info = load(model_path)
        self.window = int(self.info["window"])
        self.threshold = float(self.info["critical_threshold"])
        self.features = list(self.info["features"])
        self.version = self.info.get("name", "model")
        self.rule_safety_net = rule_safety_net

    def classify(self, patient, current: dict, previous: list[dict]) -> Result:
        """previous: the patient's earlier readings (after quality checks), most recent first."""
        window_rows = [current, *previous[: self.window - 1]]
        medians = {}
        for vital in VITALS:
            values = [r.get(vital) for r in window_rows if r.get(vital) is not None]
            medians[vital] = float(np.median(values)) if values else np.nan

        row = {"risk_level": patient.risk_level, "diabetic": int(patient.diabetes), "spo2_scale": patient.spo2_scale}
        for vital in VITALS:
            value = current.get(vital)
            row[vital] = np.nan if value is None else float(value)
            row[f"{vital}_med{self.window}"] = medians[vital]
        X = pd.DataFrame([row], columns=self.features).astype(float)

        proba = self.model.predict_proba(X)[0]
        p_critical = float(proba[list(self.model.classes_).index("Critical")])
        status = str(predict_with_threshold(self.model, X, self.threshold)[0])

        parts = score_parts(
            medians["heart_rate"],
            medians["spo2"],
            medians["systolic_bp"],
            medians["temperature"],
            medians["glucose"],
            patient.spo2_scale,
        )
        total, rule_status = status_from_parts(parts)
        parts = {k: int(v[0]) for k, v in parts.items()}
        decided_by = "model"
        if self.rule_safety_net and rule_status[0] == "Critical" and status != "Critical":
            status, decided_by = "Critical", "rule"
        return Result(
            status=status,
            p_critical=round(p_critical, 4),
            decided_by=decided_by,
            news_score=int(total[0]),
            parts=parts,
            red_vitals=[k for k, v in parts.items() if v >= RED_SCORE],
            medians={k: (None if np.isnan(v) else round(v, 2)) for k, v in medians.items()},
        )
