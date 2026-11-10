# ADR 7: Per-patient alert limits, and how they combine with the model

**Status:** accepted
**Date:** 10 Nov 2026

## Context
R10: a clinician or admin can set alert thresholds for each patient. Sprint 2 found a real need: P005's usual systolic blood pressure is about 95 mmHg, so ordinary readings score points and one reading of 91 pushed the model over its threshold, raising a false alarm. The model itself cannot be told a patient's personal normal.

## Options considered
- **A per-patient model threshold** ("alert sensitivity"): one number, but clinicians do not think in probabilities and it cannot say which vital matters.
- **Per-patient limits on each vital, used only by the rule**: easy to explain, but the model would still raise P005's false alarm.
- **Per-patient limits on each vital that adjust both**: inside the limits a vital scores 0; outside them it is a red score; and a model Critical is downgraded to Warning when every vital is inside this patient's limits.

## Decision
The third. Limits have a low and/or high bound and a required reason, apply to new readings only, and are audited. Patients without limits behave exactly as before, so notebook 02's results still hold. A downgraded reading is stored with `decided_by = "personal limits"`.

## Evidence
`tests/test_security.py`: T11 (a heart-rate limit of 100 for P001 alerts P001 but not P002 on the same readings); P005's false alarm happens without limits and disappears with an SBP range of 85-150, while real deterioration still alerts; bad limits (unknown vital, reversed, impossible, no reason, glucose for a patient without diabetes) are refused.

## Consequences
- **Better:** fewer false alarms for patients whose normal is unusual; more sensitive alerts where a clinician wants them; every change has a name, a time and a reason.
- **Worse:** a limit set too wide could hide a real deterioration in that vital; the safety net still applies to the other vitals. A real system would review limits regularly and expire temporary ones.
