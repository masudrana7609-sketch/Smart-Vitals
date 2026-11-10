# app/ (R4, R5, R6, R11)

From Week 8: your API. It receives each reading, classifies it with your saved model, stores readings and alerts for each patient, and raises an alert when a reading is Critical.

Notebook 01 already saved what the API needs:
- `models/first_model.joblib`: the trained pipeline
- `models/first_model.json`: the column names, the labels and one example reading

## How it works (Sprint 2)

Every reading, whether it arrives over MQTT or HTTP, goes through `pipeline.py`:

1. **Duplicate?** A `msg_id` already stored is ignored (T10, MQTT QoS 1).
2. **Known patient and device?** Otherwise rejected.
3. **Quality checks** (`quality.py`, R9): missing vitals stay missing (T7); impossible values become sensor errors (T9); late readings are flagged (T8); a heart rate, blood pressure or glucose value repeated 10 times is treated as a stuck sensor; glucose from a patient without diabetes is not stored.
4. **Classify** (`classifier.py`): model v2 on the reading plus the median of the patient's last 5 readings; the NEWS2-inspired rule on the same median is a safety net, and its points per vital are stored as the explanation.
5. **Store** the reading (R6), then apply the **alert rule** (`alerts.py`, R4, ADR 5): one open alert per patient; escalation if clearly worse; reminders every 15 minutes while the patient is not back to Normal; a short quiet period after acknowledgement.
6. **Commit, then notify** the assigned clinician (`notify.py`), so no message is ever sent for a reading that was not stored.

| File | What it does |
|---|---|
| `main.py` | FastAPI app: `POST /readings`, `GET /patients`, `GET /patients/{id}`, `GET /patients/{id}/history`, `GET /alerts`, `POST /alerts/{id}/acknowledge`, `GET /health` |
| `mqtt_ingest.py` | The ingest service: subscribes to `smartvitals/readings/#` (QoS 1), acknowledges each message only after storing it |
| `pipeline.py`, `quality.py`, `classifier.py`, `alerts.py`, `notify.py` | The steps above |
| `tables.py`, `db.py`, `schemas.py`, `config.py`, `seed.py` | Database tables, connection, message shapes, settings, loading patients |

## Security (Sprint 3, R5)

- **Logins** (`auth.py`): passwords stored only as argon2 hashes; signed tokens (JWT, HS256) that expire after 30 minutes; 5 failed logins for a name lock it for 15 minutes. The API refuses to start without a real `SECRET_KEY`.
- **Access control** (`main.py`): a clinician sees only their own patients, their history, thresholds and alerts (403 otherwise, T4) and acknowledges only their own alerts. An `admin` sees every patient, manages thresholds and reads the audit log.
- **Devices** post readings with `X-Ingest-Key` (`INGEST_KEY`), never with a clinician login.
- **Audit log** (`audit.py`, `GET /audit`, admin only): every login (and failed login), view, change and refused access. Repeated views are logged once per 5 minutes so the dashboard's refreshes do not bury the rest.
- **Per-patient alert limits** (R10): `GET/PUT/DELETE /patients/{id}/thresholds/{vital}`, with a required reason; see ADR 7.

Not in the prototype (see the report): HTTPS/TLS between services (Sprint 4 notes), multi-factor login, token revocation, encryption of the database at rest.

## Run it

```bash
cp .env.example .env                                # then set SECRET_KEY, INGEST_KEY and the demo passwords
python -m simulator.cli patients                    # 30 demo patients -> data/demo/sim_patients.csv
python -m app.seed data/demo/sim_patients.csv       # load them, with logins C01-C03 and admin
uvicorn app.main:create_app --factory --reload      # the API on http://localhost:8000 (docs at /docs)

# in a second terminal: stream readings
python -m simulator.cli live --transport http       # 30 patients, 1 simulated day, 60x speed
python -m simulator.cli scenario --transport http   # the scripted T3, T7-T10 story for P001

# or over MQTT, with a broker on localhost:1883 (Mosquitto in Docker, Sprint 4)
python -m app.mqtt_ingest
python -m simulator.cli live --transport mqtt
```
