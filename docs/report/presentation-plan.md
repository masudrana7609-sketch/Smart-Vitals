# Presentation and demonstration plan (Output 6, LO4)

Ten minutes, live. Rehearse with a timer, and have a recorded demo ready in case something fails on the day.

| Minutes | What | Show |
|---|---|---|
| 1 | MedLink's problem and your system in one sentence | Title slide |
| 2 | Architecture and your two key decisions | Diagram, ADRs |
| 4 | **Live demo:** readings arrive; a Critical reading raises an alert; a clinician cannot see another clinician's patient; a dropped reading causes no false alert; a threshold changed for one patient | The running system |
| 2 | Results: model metrics on unseen patients, test results | Confusion matrix, test table |
| 1 | Ethics, limitations, what you would do next | One slide |

**Questions to prepare for:** Why this model? Why this edge/cloud split? What happens when the network drops? How do you know an alert is not missed? Is any real patient data used?

---

## Run sheet *(prepared with Claude; adapt it to your own words)*

### 30 minutes before
1. Start Docker Desktop. In the project folder (with your `.env`): `sh tools/prepare_demo.sh` (about 1 minute: a fresh system with 3 simulated hours for 30 patients).
2. Open http://localhost:8080 in a browser, zoom to 125%, and log in as **C01** in one window. Keep a terminal open in the project folder.
3. Have the backup video ready to play: `docs/report/demo/smart-vitals-demo.webm` (93 s, captions, opens in Chrome or VLC).
4. Have the figures open in tabs: `docs/architecture.png`, `docs/results/model_v2_confusion.png`, `docs/results/fairness_recall.png`.

### Timing
| Clock | What | Show | Evidence to quote |
|---|---|---|---|
| 0:00-1:00 | MedLink's problem; the system in one sentence | Title slide | |
| 1:00-3:00 | Architecture; the two decisions (model; edge versus cloud) | `architecture.png` | ADR 3, 8; `approaches.md` |
| 3:00-7:00 | **Live demo** (steps below) | The running system | |
| 7:00-9:00 | Results | Model table, confusion matrix, fairness chart | below |
| 9:00-10:00 | Ethics, limitations, next steps | One slide | ADR 6-8, `assumptions.md` |

### Live demo, step by step (4 minutes)
| Time | Do | Say (the point) |
|---|---|---|
| 3:00 | C01's home page | C01 sees only their 10 patients and alerts, most urgent first |
| 3:20 | Open **P001**, choose **1 h**; in the terminal: `sh tools/prepare_demo.sh story` | Readings arrive over MQTT every few seconds (30x speed) |
| 3:50 | Point at the gap in the SpO₂ chart and the notes in the readings table | A sensor dropout and an impossible heart rate (250) are flagged; no alert (T7, T9) |
| 4:20 | Wait for the red line and the alert card (about 35 s after starting the story) | **One** alert to C01 with patient ID, vitals and time (R4, T3); the duplicate and late message raised no second alert (T8, T10) |
| 5:00 | Click **Acknowledge** | Reminders stop; the alert stays on record |
| 5:20 | Go to `#/patients/P002` | Another clinician's patient: refused (403) and logged (R5, T4) |
| 5:45 | P001, alert limits: heart rate high 110, reason "post-op tachycardia watch", **Save** | A limit for this patient only, audited (R10, T11) |
| 6:15 | Sign out; log in as **admin**; **Audit log** | Every login, view, change and refusal, including C01's refused look at P002 |
| 6:45 | (if time) `docker compose ps` | Seven containers; the database and broker are not reachable from outside (R11, T12) |

**If anything fails:** say so, play the backup video from the matching point, and carry on. Do not debug live.

### Results slide: numbers to quote
- Model v2 on patients it never saw: recall for Critical **0.979** (16 test patients), **0.970** cross-validated over all 80 (95% interval 0.955-0.981); 0.66-0.88 false alarms per 100 Normal readings (targets 0.90 and 5). Baseline: 0.
- Notebook 01's first model: 0.62. The fix was not a better algorithm but two inputs: the patient's SpO₂ scale and the last-5 median.
- The plain NEWS2-inspired rule on the median reaches 0.964: why keep ML? (a little more recall; the rule stays as safety net and explanation).
- Fairness: every group 0.937-0.982; youngest and Low-risk weakest; the 15 missed episodes all lasted 1-4 minutes.
- Testing: 113 Python tests and 7 dashboard tests; T1-T22 all pass.
- Two data-loss bugs only a real broker revealed: Mosquitto's 1,000-message queue, and a device with no offline buffer. Both fixed; 0 of 1,777 readings lost in a 20 s outage.

### Questions to prepare for (facts to use)
| Question | Facts | Where |
|---|---|---|
| Why this model? | Same recall as the forest with fewer false alarms (CV 1.0 against 2.2 per 100 Normal), 0.38 MB against 9.8 MB | `results/model_comparison.md` |
| Why this edge/cloud split? | Speed is not the issue (4-8 ms); updating, auditing and trends are; edge buffers while offline | `approaches.md`, `results/edge_cloud.md` |
| What happens when the network drops? | Device keeps readings; 0 lost in a 20 s outage; but no alert can fire until it reconnects (hybrid edge model is the next step) | `results/docker_compose.md` |
| How do you know an alert is not missed? | Recall 0.970 CV; missed episodes all 1-4 min; rule safety net; reminders until acknowledged | `results/fairness.md`, ADR 5 |
| Is any real patient data used? | No: every patient, reading and clinician is simulated | `data/DATA_CARD.md` |
| Does it work for everyone? | All groups above 0.90; small groups have wide intervals; groups not simulated (children, pregnancy, darker skin and pulse oximetry) | `results/fairness.md`, data card limitations |
| What about security? | argon2, 30-minute tokens, 403 + audit, broker logins and ACL, internal network; not yet TLS | ADR 6, 8 |
| Is the model just re-learning your rule? | Partly: labels come from the rule on true vitals; the model sees noisy readings. A real deployment would need clinician-labelled data | `assumptions.md` A2 |
