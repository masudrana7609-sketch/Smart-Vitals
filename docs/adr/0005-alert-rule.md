# ADR 5: One open alert per patient until acknowledged

**Status:** accepted (refined in Sprint 2)
**Date:** 9 Nov 2026

## Context
R4: a Critical reading must alert the assigned clinician. R9: no false or missing alerts. Alerting on every Critical reading of a deteriorating patient (one a minute) floods the clinician: alarm fatigue is a recognised safety risk.

## Options considered
- Alert on every Critical reading.
- A fixed 15-minute quiet period per patient.
- One open alert per patient until a clinician acknowledges it; a reminder after 15 (simulated) minutes; a new alert at once if the reading gets worse.

## Decision
The third option, refined while building it (Sprint 2):
- **"Worse"** means a NEWS2-inspired score at least **2 points** higher, or a vital sign newly in the red band. A rise of 1 happens every minute while the last-5 median climbs, so counting it re-alerted for the same event.
- **Settling period:** for 5 minutes after an alert, a worse reading only updates the open alert's details, without another message. Without it, 5 of 30 scenario patients got an escalation within a minute of the first alert.
- **Reminders stop when the patient is Normal again;** the alert stays open until a clinician reviews it. In a 6-hour live run this halved reminders (125 to 63) without hiding anyone still unwell.
- **After an acknowledgement**, no new alert for 15 minutes unless the patient is worse.
- **A reading more than 30 minutes late** is stored but raises no new alert.

Duplicate messages are a separate problem, solved by `msg_id` (ADR 3).

## Evidence
`tests/test_api.py`: T3 (one alert, with patient ID, vitals and time, to the assigned clinician), T10, reminders after 15 minutes, escalation after the settling period, acknowledgement only by the assigned clinician, the quiet period, no reminders after recovery. Scenario run for all 30 demo patients: 29 got exactly one alert; 1 got a genuine escalation; 0 alerts came from the missing, impossible, late or duplicate readings.

## Consequences
- **Better:** fewer repeated alarms, without hiding a deterioration.
- **Worse:** needs an acknowledge action in the dashboard and an alert state (open, acknowledged). A real system would escalate to a second clinician if nobody acknowledges.
