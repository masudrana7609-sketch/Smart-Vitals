# ADR 5: One open alert per patient until acknowledged

**Status:** accepted
**Date:** 9 Nov 2026

## Context
R4: a Critical reading must alert the assigned clinician. R9: no false or missing alerts. Alerting on every Critical reading of a deteriorating patient (one a minute) floods the clinician: alarm fatigue is a recognised safety risk.

## Options considered
- Alert on every Critical reading.
- A fixed 15-minute quiet period per patient.
- One open alert per patient until a clinician acknowledges it; a reminder after 15 (simulated) minutes; a new alert at once if the reading gets worse.

## Decision
The third option. "Worse" means a higher points score or a new vital sign out of range. Duplicate messages are a separate problem, solved by `message_id` (ADR 3).

## Evidence
To add in S2: tests for T3 and T10, and an "escalation during an open alert" test.

## Consequences
- **Better:** fewer repeated alarms, without hiding a deterioration.
- **Worse:** needs an acknowledge action in the dashboard and an alert state (open, acknowledged). A real system would escalate to a second clinician if nobody acknowledges.
