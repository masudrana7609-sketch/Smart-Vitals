"""API and pipeline tests: T1, T3, T5, T7-T10 from docs/test-plan.md, plus the alert rule (ADR 5)."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.notify import ListNotifier
from app.seed import seed
from simulator import scenario
from simulator.cli import run_batch
from simulator.config import FaultRates, SimConfig
from simulator.live import HttpSender, payloads, stream
from simulator.patients import generate_patients

PATIENTS = generate_patients(SimConfig(n_patients=6, seed=3), np.random.default_rng(3))
P001 = PATIENTS.iloc[0].to_dict()
T0 = "2026-01-06T00:"


@pytest.fixture
def api():
    notifier = ListNotifier()
    app = create_app(Settings(database_url="sqlite://", _env_file=None), notifier=notifier)
    with app.state.sessions() as session:
        seed(session, PATIENTS)
    return TestClient(app), notifier


def reading(minute, patient=P001, sent_minute=None, msg=None, **vitals):
    values = {"heart_rate": 76.0, "spo2": 97.0, "systolic_bp": 121.0, "diastolic_bp": 79.0, "temperature": 36.8}
    values.update(vitals)
    jitter = {"heart_rate": minute % 3, "systolic_bp": minute % 4, "diastolic_bp": minute % 2}  # not a stuck sensor
    for k, v in jitter.items():
        if values.get(k) is not None:
            values[k] += v
    sent = minute if sent_minute is None else sent_minute
    return {
        "msg_id": msg or f"{patient['patient_id']}-T{minute:04d}",
        "device_id": patient["device_id"],
        "patient_id": patient["patient_id"],
        "measured_at": f"{T0}{minute:02d}:00Z",
        "sent_at": f"{T0}{sent:02d}:01Z",
        **{k: v for k, v in values.items() if v is not None},
    }


CRITICAL = {"spo2": 84.0, "heart_rate": 118.0}


def send_all(client, messages):
    return [client.post("/readings", json=m).json() for m in messages]


def alerts_sent(notifier, kind=None):
    return [n for n in notifier.sent if kind is None or n.kind == kind]


# --- T3 (R4): a Critical reading alerts the assigned clinician ----------------------------------


def test_T3_one_alert_with_patient_id_vitals_and_time(api):
    client, notifier = api
    send_all(client, scenario.build(P001))
    new = alerts_sent(notifier, "new")
    assert len(notifier.sent) == 1 and len(new) == 1
    note = new[0]
    assert note.clinician_id == P001["clinician_id"]
    assert P001["patient_id"] in note.message and "SpO2" in note.message and "2026-01-06" in note.message
    alert = client.get("/alerts", params={"state": "open"}).json()[0]
    assert alert["patient_id"] == P001["patient_id"] and alert["clinician_id"] == P001["clinician_id"]
    assert alert["vitals"]["spo2"] <= 91 and alert["raised_at"].startswith("2026-01-06T00:1")
    assert "spo2" in alert["red_vitals"] or alert["decided_by"] == "model"


# --- T5 (R6): history in time order, with alerts ------------------------------------------------


def test_T5_history_has_all_readings_and_alerts_in_time_order(api):
    client, _ = api
    messages = scenario.build(P001)
    send_all(client, messages)
    history = client.get(f"/patients/{P001['patient_id']}/history").json()
    times = [r["measured_at"] for r in history["readings"]]
    assert len(times) == len({m["msg_id"] for m in messages}) == 26
    assert times == sorted(times)
    assert len(history["alerts"]) == 1
    assert client.get("/patients/P999/history").status_code == 404


# --- T7 (R9): a missing vital ------------------------------------------------------------------


def test_T7_missing_vital_is_stored_without_crash_or_alert(api):
    client, notifier = api
    send_all(client, [reading(m) for m in range(8)])
    result = client.post("/readings", json=reading(8, spo2=None)).json()
    assert result["result"] == "stored" and "missing:spo2" in result["flags"]
    assert result["status"] != "Critical"
    assert notifier.sent == []


# --- T8 (R9): a late reading ----------------------------------------------------------------------


def test_T8_late_reading_is_stored_in_order_and_flagged(api):
    client, _ = api
    send_all(client, [reading(m) for m in range(10) if m != 4])
    result = client.post("/readings", json=reading(4, sent_minute=9)).json()
    assert "late" in result["flags"]
    times = [r["measured_at"] for r in client.get(f"/patients/{P001['patient_id']}/history").json()["readings"]]
    assert times == sorted(times) and len(times) == 10


def test_T8_late_critical_reading_raises_no_duplicate_alert(api):
    client, notifier = api
    send_all(client, [reading(m) for m in range(10)] + [reading(m, **CRITICAL) for m in range(10, 16) if m != 12])
    assert len(alerts_sent(notifier, "new")) == 1
    client.post("/readings", json=reading(12, sent_minute=18, **CRITICAL))
    assert len(alerts_sent(notifier, "new")) == 1


def test_very_late_reading_is_stored_but_raises_no_alert(api):
    client, notifier = api
    send_all(client, [reading(m) for m in range(5)])
    old = [reading(m, sent_minute=55, **CRITICAL) for m in range(5, 10)]
    results = send_all(client, old)
    assert all(r["result"] == "stored" for r in results)
    assert notifier.sent == []


# --- T9 (R9): an impossible value ----------------------------------------------------------------


def test_T9_impossible_value_is_a_sensor_error_not_an_alert(api):
    client, notifier = api
    send_all(client, [reading(m) for m in range(8)])
    result = client.post("/readings", json=reading(8, heart_rate=250.0, spo2=0.0)).json()
    assert {"sensor_error:heart_rate", "sensor_error:spo2"} <= set(result["flags"])
    assert result["status"] != "Critical" and notifier.sent == []
    stored = client.get(f"/patients/{P001['patient_id']}/history").json()["readings"][-1]
    assert stored["heart_rate"] is None and stored["spo2"] is None


# --- T10 (R9): the same message twice ----------------------------------------------------------


def test_T10_duplicate_message_is_stored_once(api):
    client, notifier = api
    send_all(client, [reading(m) for m in range(10)] + [reading(m, **CRITICAL) for m in range(10, 14)])
    again = client.post("/readings", json=reading(13, **CRITICAL)).json()
    assert again["result"] == "duplicate"
    assert len(client.get(f"/patients/{P001['patient_id']}/history").json()["readings"]) == 14
    assert len(alerts_sent(notifier, "new")) == 1


# --- Other R9 cases and validation --------------------------------------------------------------


def test_unknown_patient_or_wrong_device_is_rejected(api):
    client, _ = api
    assert client.post("/readings", json=reading(0, msg="X-1") | {"patient_id": "P999"}).status_code == 422
    assert client.post("/readings", json=reading(0, msg="X-2") | {"device_id": "W999"}).status_code == 422
    assert client.post("/readings", json={"msg_id": "bad id!"}).status_code == 422


def test_stuck_sensor_is_flagged_and_ignored(api):
    client, _ = api
    messages = [reading(m) for m in range(12)]
    for m in messages:
        m["heart_rate"] = 77.0
    results = send_all(client, messages)
    assert "stuck:heart_rate" not in results[8]["flags"]
    assert "stuck:heart_rate" in results[9]["flags"] and "stuck:heart_rate" in results[11]["flags"]


def test_glucose_from_a_patient_without_diabetes_is_not_stored(api):
    client, _ = api
    patient = PATIENTS[PATIENTS["diabetes"] == 0].iloc[0].to_dict()
    result = client.post("/readings", json=reading(0, patient=patient, glucose=6.0)).json()
    assert "ignored:glucose" in result["flags"]
    assert client.get(f"/patients/{patient['patient_id']}/history").json()["readings"][0]["glucose"] is None


# --- Alert rule (ADR 5) -------------------------------------------------------------------------


def test_open_alert_is_reminded_after_15_minutes(api):
    client, notifier = api
    send_all(client, [reading(m) for m in range(10)] + [reading(m, **CRITICAL) for m in range(10, 30)])
    assert len(alerts_sent(notifier, "new")) == 1
    assert len(alerts_sent(notifier, "reminder")) == 1
    assert client.get("/alerts", params={"state": "open"}).json()[0]["reminders"] == 1


def test_much_worse_reading_escalates_after_the_settling_period(api):
    client, notifier = api
    worse = {"spo2": 78.0, "heart_rate": 135.0, "systolic_bp": 88.0, "temperature": 39.4}
    send_all(
        client,
        [reading(m) for m in range(10)]
        + [reading(m, **CRITICAL) for m in range(10, 18)]
        + [reading(m, **worse) for m in range(18, 24)],
    )
    assert [n.kind for n in notifier.sent] == ["new", "escalation"]
    states = sorted(a["state"] for a in client.get("/alerts").json())
    assert states == ["open", "superseded"]


def test_only_the_assigned_clinician_can_acknowledge(api):
    client, notifier = api
    send_all(client, [reading(m) for m in range(10)] + [reading(m, **CRITICAL) for m in range(10, 15)])
    alert = client.get("/alerts", params={"state": "open"}).json()[0]
    other = next(c for c in PATIENTS["clinician_id"].unique() if c != alert["clinician_id"])
    url = f"/alerts/{alert['id']}/acknowledge"
    assert client.post(url, json={"clinician_id": other}).status_code == 403
    assert client.post(url, json={"clinician_id": alert["clinician_id"]}).json()["state"] == "acknowledged"
    assert client.post(url, json={"clinician_id": alert["clinician_id"]}).status_code == 409

    send_all(client, [reading(m, **CRITICAL) for m in range(15, 25)])  # still Critical, no worse: quiet period
    assert len(alerts_sent(notifier, "new")) == 1
    send_all(client, [reading(m, **CRITICAL) for m in range(25, 32)])  # quiet period over: a new alert
    assert len(alerts_sent(notifier, "new")) == 2


# --- T1 (R2): the simulator feeds the API -------------------------------------------------------


def test_T1_ten_patients_for_ten_minutes_gives_100_readings():
    cfg = SimConfig(
        n_patients=10, days=10 / (24 * 60), seed=3, start="2026-01-05T00:00:00Z", faults=FaultRates(0, 0, 0, 0, 0, 0)
    )
    patients, delivered, _ = run_batch(cfg)
    app = create_app(Settings(database_url="sqlite://", _env_file=None), notifier=ListNotifier())
    with app.state.sessions() as session:
        seed(session, patients)
    client = TestClient(app)
    results = stream(payloads(delivered), HttpSender(client=client), speedup=0)
    assert results == {"stored": 100}
    assert client.get("/health").json()["readings"] == 100


def test_payloads_carry_no_label_or_risk_group():
    _, delivered, _ = run_batch(SimConfig(n_patients=2, days=0.01, seed=3))
    message = next(payloads(delivered))
    assert {"status", "risk_level", "diabetic"}.isdisjoint(message)
    assert {"msg_id", "device_id", "patient_id", "measured_at", "sent_at"} <= set(message)


def test_no_reminders_once_the_patient_is_normal_again(api):
    client, notifier = api
    send_all(client, [reading(m) for m in range(10)] + [reading(m, **CRITICAL) for m in range(10, 16)]
             + [reading(m) for m in range(16, 45)])
    assert [n.kind for n in notifier.sent] == ["new"]
    assert client.get("/alerts", params={"state": "open"}).json()[0]["reminders"] == 0  # still open for review
