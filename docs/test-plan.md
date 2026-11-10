# Test plan (Output 4)

Write the tests **before** you build each part, then fill in the results with screenshots. Every requirement in `requirements-checklist.md` should have at least one test. This becomes your test evidence for the report.

| ID | Requirement | What I do | Expected | Result and evidence | Pass? |
|---|---|---|---|---|---|
| T1 | R2 | Run the simulator for 10 patients for 10 minutes | 100 readings stored | `test_T1_ten_patients_for_ten_minutes_gives_100_readings`: 100 stored | Yes |
| T2 | R3 | Notebook 01 Step 7 on unseen patients | Recall for Critical at least my target | Notebook 01: recall 0.621 (No). **Notebook 02, model v2** (gradient boosting + last-5 median + SpO₂ scale), same 16 unseen patients: recall 0.979, 0.66 false alarms per 100 Normal (`docs/results/model_comparison.md`, `model_v2_confusion.png`); checked by `tests/test_model_v2.py` | Yes |
| T3 | R4 | Send Critical readings for patient P001 (scenario minutes 15-25) | One alert to P001's clinician, with patient ID, vitals and timestamp | `test_T3_...`: one alert to C01 after 2 Critical minutes (A21); scenario over MQTT: same | Yes |
| T4 | R5 | Clinician A asks for a patient of clinician B | Refused (e.g. HTTP 403) | `test_T4_...`: 403 for the patient, history and thresholds, and recorded as `denied` in the audit log; dashboard: `screenshots/denied_P002.png` | Yes |
| T5 | R6 | Ask for P001's history | All readings and alerts, in time order | `test_T5_...`: 26 readings in measured-time order (the late one in place), 1 alert | Yes |
| T6 | R8 | Open P001 on the dashboard | Trend chart of each vital sign | `screenshots/patient_P001_light.png`, `_1h`, `_dark`, `mobile_P001.png`: a chart per vital with alert line and limits | Yes |
| T7 | R9 | One reading arrives with a vital missing (sensor dropout) | No crash, no false alert | `test_T7_...`: stored, flagged `missing:spo2`, no alert | Yes |
| T8 | R9 | A reading arrives 5 minutes late | Stored in the right time order, no duplicate alert | `test_T8_...` (two tests): flagged `late`, in order, no second alert; 50 minutes late: stored, no alert | Yes |
| T9 | R9 | An impossible value arrives (e.g. heart rate 250) | Flagged as a sensor error, no Critical alert | `test_T9_...`: HR 250 and SpO2 0 flagged `sensor_error`, stored as missing, no alert | Yes |
| T10 | R9 | The same message arrives twice (MQTT QoS 1) | One alert only (Week 7: idempotency) | `test_T10_...` (HTTP) and `test_scenario_over_mqtt_...` (real broker): stored once, one alert | Yes |
| T11 | R10 | Change the threshold for P001 only | Alerts change for P001, not for other patients | `test_T11_...`: HR limit 100 for P001: P001 alerted, P002 not, same readings; `test_personal_limits_stop_the_P005_false_alarm` | Yes |
| T12 | R11 | `docker compose up` on a clean machine | All services start; the API answers | | |
| T13 | R1 | Generate patients; recompute each risk group from the documented rule | Every patient has a risk group that matches `src/risk.py`, and a clinician (≥ 3 clinicians) | `pytest tests/test_simulator.py` | Yes |
| T14 | R2 | Run the simulator twice with the same seed, and once with another | Identical output for the same seed; one reading per patient per minute; glucose only for diabetics | `pytest tests/test_simulator.py` | Yes |
| T15 | R9 | Run the simulator with raised fault rates | Each fault happens at about its configured rate and is recorded in the ground truth; impossible values only where recorded | `pytest tests/test_simulator.py` | Yes |
| T16 | R4 | Alert rule: reminders, escalation, acknowledgement, recovery | ADR 5 behaviour | `tests/test_api.py` (5 tests) | Yes |
| T17 | R9 | 10 identical heart-rate values in a row | Flagged `stuck:heart_rate`, value ignored | `test_stuck_sensor_is_flagged_and_ignored` | Yes |
| T18 | R5 | Logins, tokens, ingest key, audit log | Unauthenticated, forged or expired access refused; passwords hashed; changes and refusals audited | `tests/test_security.py` (21 tests) | Yes |
| T19 | R8 | Dashboard components | Status shown with icon and word; patients sorted by urgency; login errors shown | `dashboard/src/__tests__` (7 tests, `npm test`) | Yes |

Automatic tests live in `tests/` and run with `pytest`. Add one each time you find a bug, so it cannot come back.
