"""Risk groups (R1): Low, Medium or High, from a patient's age, conditions and history.

THIS RULE WAS INVENTED FOR THIS PROJECT. IT IS NOT A VALIDATED CLINICAL TOOL.
It follows a common idea: risk of deterioration rises with age, with the number and kind of long-term
conditions (multimorbidity), and with recent hospital use.

| Factor                                         | Points        |
|------------------------------------------------|---------------|
| Age band 18-49 / 50-64 / 65-79 / 80+           | 0 / 1 / 2 / 3 |
| Hypertension, diabetes                         | +1 each       |
| Arrhythmia, COPD-like lung disease             | +2 each       |
| Hospital admissions in last 12 months: 1 / 2+  | +1 / +2       |
| A past critical event (e.g. ICU stay)          | +2            |

Low: 0-2 points · Medium: 3-5 · High: 6 or more.
"""

from collections.abc import Iterable

AGE_BANDS = ("18-49", "50-64", "65-79", "80+")
AGE_POINTS = {"18-49": 0, "50-64": 1, "65-79": 2, "80+": 3}
CONDITIONS = ("hypertension", "diabetes", "arrhythmia", "copd")
CONDITION_POINTS = {"hypertension": 1, "diabetes": 1, "arrhythmia": 2, "copd": 2}
PRIOR_CRITICAL_POINTS = 2

RISK_GROUPS = ("Low", "Medium", "High")
RISK_LEVEL = {"Low": 1, "Medium": 2, "High": 3}  # the number the model sees, as in the demo data
MEDIUM_FROM = 3
HIGH_FROM = 6


def risk_points(age_band: str, conditions: Iterable[str], admissions_12m: int, prior_critical_event: bool) -> int:
    """Total risk points for one patient (see the table above)."""
    if age_band not in AGE_POINTS:
        raise ValueError(f"unknown age band {age_band!r}; expected one of {AGE_BANDS}")
    unknown = set(conditions) - set(CONDITIONS)
    if unknown:
        raise ValueError(f"unknown condition(s) {sorted(unknown)}; expected some of {CONDITIONS}")
    if admissions_12m < 0:
        raise ValueError("admissions_12m cannot be negative")
    return (
        AGE_POINTS[age_band]
        + sum(CONDITION_POINTS[c] for c in set(conditions))
        + min(admissions_12m, 2)
        + (PRIOR_CRITICAL_POINTS if prior_critical_event else 0)
    )


def risk_group(points: int) -> str:
    """Low, Medium or High from risk points."""
    if points >= HIGH_FROM:
        return "High"
    if points >= MEDIUM_FROM:
        return "Medium"
    return "Low"
