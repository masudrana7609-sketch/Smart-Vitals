"""Classifies a reading with model v2 (notebook 02), using the patient's last few readings, and explains it.

Decision, in order:
1. The model gives a probability of Critical; at or above its tuned threshold the reading is Critical.
2. The NEWS2-inspired rule scores the last-5 median. Where a clinician has set personal limits for this
   patient (R10), those limits replace the default bands for that vital (src/labelling.apply_personal_limits).
3. Personal limits can lower sensitivity: if the model says Critical but every vital is inside the limits set
   for this patient (personal rule score 0), the reading is Warning, decided_by = "personal limits".
4. Safety net (rule_safety_net): if the rule says Critical and the model does not, the reading is Critical,
   decided_by = "rule". A value outside a personal limit is a red score, so limits can also raise sensitivity.
The rule's points per vital are stored with every reading, so a clinician can see why an alert fired.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.labelling import RED_SCORE, apply_personal_limits, score_parts, status_from_points
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

    def classify(self, patient, current: dict, previous: list[dict], limits: dict | None = None) -> Result:
        """previous: the patient's earlier readings (after quality checks), most recent first.
        limits: the patient's personal alert limits, {vital: (low, high)}."""
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
        decided_by = "model"

        parts = score_parts(
            medians["heart_rate"],
            medians["spo2"],
            medians["systolic_bp"],
            medians["temperature"],
            medians["glucose"],
            patient.spo2_scale,
        )
        parts = {k: int(v[0]) for k, v in parts.items()}
        if limits:
            parts = apply_personal_limits(parts, medians, limits)
        total, rule_status = status_from_points(parts)

        if limits and status == "Critical" and total == 0:
            status, decided_by = "Warning", "personal limits"
        if self.rule_safety_net and rule_status == "Critical" and status != "Critical":
            status, decided_by = "Critical", "rule"
        return Result(
            status=status,
            p_critical=round(p_critical, 4),
            decided_by=decided_by,
            news_score=total,
            parts=parts,
            red_vitals=[k for k, v in parts.items() if v >= RED_SCORE],
            medians={k: (None if np.isnan(v) else round(v, 2)) for k, v in medians.items()},
        )
