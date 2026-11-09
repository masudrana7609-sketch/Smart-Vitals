# Data card

It becomes the *Data* part of the report. **No real patient data is used** (brief, requirement 7). Every patient, reading and clinician is invented by our own code.

All numbers below come from the standard batch run: `python -m simulator.cli batch` (80 patients, 3 clinicians, 3 days, seed 42, started 9 Nov 2026). The same seed always gives exactly the same files.

| | |
|---|---|
| **Type** | Simulated by our own code (`simulator/`, `src/`). No external dataset, so no licence or attribution needed |
| **Licence** (for an open dataset) and attribution | Not applicable. Label bands are inspired by NEWS2 (Royal College of Physicians, 2017) |
| **How readings are made** | One reading per patient per minute (A1), simulated clock starting 2026-01-05 00:00 UTC. Each patient has personal baselines. True vitals = baseline + daily (circadian) rhythm + a slow random walk + the effects of deterioration episodes. Observed vitals = true vitals + sensor noise (SD: HR 2 bpm, SpO₂ 1 %, BP 5/4 mmHg, temperature 0.1 °C, glucose about 8 %). See `simulator/physiology.py` |
| **Deterioration episodes** | Sepsis-like, hypoxic, hypertensive crisis, arrhythmia, and (diabetics only) hypo- and hyperglycaemia. 0.4 / 1.0 / 2.0 episodes per patient per day for Low / Medium / High risk (A13). Conditions make matching episodes more likely (COPD: hypoxic ×3; hypertension: crisis ×3; arrhythmia ×4). Each lasts about 1.5 to 10 hours: it ramps up, stays at its worst, then recovers |
| **How labels are made** (Normal / Warning / Critical) | From the **true** vitals, not the noisy ones, using a partial NEWS2-inspired points score (`src/labelling.py`). Critical: total ≥ 5, or any single parameter scores 3. Warning: total 3–4. Otherwise Normal (A10). Glucose bands are our own (A11). **Not a clinical score** |
| **Patients and risk groups** | 80 patients. Low 36, Medium 28, High 16 (rule in `src/risk.py`, A9). Ages: 18–49: 25, 50–64: 20, 65–79: 21, 80+: 14. Conditions: hypertension 23, diabetes 20 (raised to about 25% on purpose, so the fairness check has enough diabetic patients), COPD-like 11 (7 of them on SpO₂ Scale 2, A12), arrhythmia 6. Past critical event: 14. Clinicians C01 / C02 / C03 have 27 / 27 / 26 patients |
| **Problems built in to test R9** | Share of expected readings: missing vital 1.96 %, duplicate message 1.01 %, late or out of order (2–15 min) 0.99 %, silent device (5–60 min gaps) 0.77 %, impossible value 0.31 %, stuck sensor (10–40 min) 0.30 %. At most one fault per reading. Recorded only in the ground-truth file |
| **Rows and columns** | `sim_vitals.csv`: 346,418 delivered messages × 14 columns (345,600 expected − 2,669 never sent + 3,487 duplicate copies). `sim_ground_truth.csv`: 345,600 × 21. `sim_patients.csv`: 80 × 20 |
| **Label balance** | Normal 93.9 %, Critical 4.4 %, Warning 1.7 % (delivered messages: 325,312 / 15,227 / 5,879). Share not Normal by risk group: Low 4.1 %, Medium 5.8 %, High 11.4 %. Diabetic patients: 7.7 %; others: 5.6 % |
| **Where it is stored** | `data/sim_patients.csv` is in Git (6 KB). `sim_vitals.csv` (37 MB) and `sim_ground_truth.csv` (41 MB) are ignored by Git: rebuild them with the command above |

## Columns: `sim_vitals.csv` (the delivered feed, in order of arrival)
| Column | Meaning | Units | Notes |
|---|---|---|---|
| msg_id | Message ID, unique per reading | | `P001-000123` = patient P001, minute 123. A duplicate copy has the same ID |
| device_id | The patient's wearable | | `W001` … |
| patient_id | Simulated patient | | `P001` … `P080`. Never a model input |
| measured_at | When the sensor took the reading | ISO 8601, UTC | |
| received_at | When the message arrived | ISO 8601, UTC, ms | Later than measured_at by 0.2–2 s, or by 2–15 min if late |
| risk_level | Risk group | 1 Low, 2 Medium, 3 High | From `src/risk.py` |
| diabetic | Has diabetes | 0 / 1 | |
| heart_rate | Pulse | beats/min | whole numbers |
| spo2 | Oxygen saturation | % | whole numbers, at most 100 |
| systolic_bp, diastolic_bp | Blood pressure | mmHg | whole numbers |
| temperature | Body temperature | °C | 1 decimal place |
| glucose | Blood glucose | mmol/L | 1 decimal place; **empty for every patient without diabetes** |
| status | Training label: Normal, Warning or Critical | | From the true vitals. The live feed (Sprint 2) does not send it |

## Columns: `sim_ground_truth.csv` (one row per expected reading)
`msg_id, patient_id, clinician_id, measured_at, risk_group, spo2_scale`, the six `true_*` vitals, `severity` (0–1), `episode_type`, `news_score`, `status`, `fault_type` (none, missing_vital, impossible, late, duplicate, silent, stuck), `fault_vital`, `delay_minutes`, `copies` (0 = never sent, 2 = duplicated), `delivered`.

## Columns: `sim_patients.csv`
`patient_id, device_id, clinician_id, age_band`, one 0/1 column per condition (`hypertension, diabetes, arrhythmia, copd`), `admissions_12m, prior_critical_event, risk_points, risk_group, risk_level, spo2_scale`, and the personal baselines `base_*`.

## Known limitations
- **The labels come from a rule we wrote.** A model trained on them learns our rule, not real clinical judgement. Because the rule is applied to the *true* vitals while the model sees *noisy* ones, the model cannot simply copy the rule. It still cannot be better than the rule.
- **A partial NEWS2.** Breathing rate, consciousness and supplemental oxygen are not measured (A14). Real NEWS2 would score some patients higher.
- **NEWS2 ignores high blood pressure below 220 mmHg.** Most hypertensive-crisis minutes are therefore labelled Normal. We keep NEWS2 as published rather than invent a band (A16).
- **Small subgroups.** 20 diabetic, 11 COPD-like and 7 Scale 2 patients: results for these groups rest on few unseen patients (6, 3 and 2 in notebook 01's test set). Severe hyperglycaemia (glucose ≥ 20) is rare: 176 Critical minutes in the whole batch.
- **Not real physiology.** Episodes are simple curves. Real deterioration is messier, and events (falls, medication, exercise, a device worn loosely) are missing.
- **One reading a minute is highly repetitive.** Neighbouring readings are nearly identical, so 346,000 rows carry far less information than the number suggests. That is why the model is tested on unseen *patients*.
- **Who is missing:** children, pregnancy, people with several devices, and anyone whose readings a wrist sensor gets wrong (for example, pulse oximeters are known to overestimate SpO₂ on darker skin). Nothing here tests that bias.
