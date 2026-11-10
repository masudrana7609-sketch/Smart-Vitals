# CLAUDE.md: Smart Vitals IPMS

Context for AI assistants (and humans) working in this repo. Assessment: CMS22301, Ravensbourne University London. **Deadline: Fri 11 Dec 2026, 4 pm** (report + repo link on Canvas, plus a 10-minute live demo).

## Non-negotiable rules
1. **No real patient data, ever** (R7). Simulated or open, anonymised data only.
2. **No secrets in the repo.** Use `.env` (ignored); `.env.example` holds placeholders only.
3. **Log every AI-assisted task** as a new row in `docs/ai-use-log.md` (Date | Task | What Claude did | What I decided/changed). Leave the last column for the student.
4. **Every requirement R1–R11 gets a test** from `docs/test-plan.md`; write the test with (or before) the feature.
5. Keep all starter files. The `___` blanks in notebook 01 were filled by Claude at the student's request (logged); the written "Your answer" cells stay the student's.
6. Small commits with clear messages ("Add Critical alert to API", not "update").

## Agreed decisions (9 Nov 2026)
| Topic | Decision | Recorded in |
|---|---|---|
| Patients / clinicians | 30 live demo patients, 3 clinicians (10 each); 80 simulated patients × 3 days for the training set | A3 |
| Simulation speed | Configurable `SIM_SPEEDUP`, default 60× (1 simulated minute per real second); timestamps are simulated time | A4 |
| Model target | Recall for Critical ≥ 0.90 on unseen patients, with ≤ 5 false alarms per 100 Normal readings | A5, ADR 1 |
| Alert rule | One open alert per patient until acknowledged; reminder after 15 min; new alert at once if worse. Duplicate messages removed by `message_id` | A6, ADR 5 |
| Retention | Readings 30 days; alerts and audit log 365 days; automatic purge job | A7 |
| Database | SQLAlchemy; SQLite for tests and local work, Postgres 17 in Docker (`DATABASE_URL`) | ADR 2 |
| Ingestion / edge–cloud | Simulator → MQTT (Mosquitto, QoS 1) → ingest service. Edge: validity checks and hard limits. Cloud: ML model, storage, alerts | ADR 3 |
| Dashboard | React + Vite + TypeScript + Recharts, talking to the FastAPI API (the API enforces all access control) | ADR 4 |
| Python | 3.13 locally and in Docker | `docs/dev-setup.md` |

## Sprint plan
| Sprint | Dates | Build | Requirements / tests |
|---|---|---|---|
| S0 | 9–10 Nov | Setup, decisions, git, notebook 01 (student), ADR 1, design plan | — |
| S1 | 11–17 Nov | `src/` labelling rule and validity checks; simulator (risk groups, faults); training dataset; notebook 02 comparing models | R1, R2, R3, R9; T1, T2; Output 1 |
| S2 | 18–24 Nov | API: MQTT ingest, classify, store, alerts, de-duplication, late and invalid readings | R4, R6, R9; T3, T5, T7–T10 |
| S3 | 25 Nov–1 Dec | Login (argon2 + JWT), per-clinician access, audit log, per-patient thresholds, React dashboard | R5, R8, R10; T4, T6, T11 |
| S4 | 2–6 Dec | docker compose, retention job, fairness check by risk group and diabetes, screenshots | R7, R11; T12; Outputs 3–4 |
| S5 | 7–11 Dec | Report, slides, recorded backup demo | Outputs 5–6 |

Stop for the student's review at the end of each sprint.

## Layout
`src/` shared functions · `simulator/` sensor feed · `app/` FastAPI API and ingest · `dashboard/` React app · `models/` saved models · `notebooks/` experiments · `tests/` pytest · `docs/` checklist, ADRs, assumptions, test plan, results, report.

## Commands
```bash
source .venv/bin/activate      # setup: docs/dev-setup.md
pytest                         # tests
ruff check . && ruff format .  # lint and format
python -m simulator.cli batch                                   # training data (seed 42)
python -m simulator.cli patients && python -m app.seed data/demo/sim_patients.csv
uvicorn app.main:create_app --factory --reload                  # API
python -m simulator.cli live --transport http                   # or: scenario; or --transport mqtt + app.mqtt_ingest
```
