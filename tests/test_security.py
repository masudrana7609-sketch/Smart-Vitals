"""Security, access control, audit and per-patient thresholds: T4 (R5), T11 (R10)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from conftest import PATIENTS, TEST_SECRET, login, make_api

from simulator import scenario

P001, P002 = PATIENTS.iloc[0].to_dict(), PATIENTS.iloc[1].to_dict()
P005 = PATIENTS[PATIENTS["patient_id"] == "P005"].iloc[0].to_dict()
T0 = "2026-01-06T00:"


def reading(patient, minute, **vitals):
    values = {
        "heart_rate": 76.0 + minute % 3,
        "spo2": 97.0,
        "systolic_bp": 121.0 + minute % 4,
        "diastolic_bp": 79.0 + minute % 2,
        "temperature": 36.8,
    }
    values.update(vitals)
    return {
        "msg_id": f"{patient['patient_id']}-K{minute:04d}",
        "device_id": patient["device_id"],
        "patient_id": patient["patient_id"],
        "measured_at": f"{T0}{minute:02d}:00Z",
        "sent_at": f"{T0}{minute:02d}:01Z",
        **values,
    }


def audit_rows(client, **params):
    return client.get("/audit", params=params, headers=login(client, "admin")).json()


# --- Logins and tokens ---------------------------------------------------------------------------


def test_every_patient_endpoint_needs_a_login(api):
    client, _ = api
    for url in [
        "/patients",
        f"/patients/{P001['patient_id']}",
        f"/patients/{P001['patient_id']}/history",
        "/alerts",
        f"/patients/{P001['patient_id']}/thresholds",
        "/audit",
        "/me",
    ]:
        assert client.get(url).status_code == 401, url
    assert client.get("/health").status_code == 200


def test_wrong_password_is_refused_and_audited(api):
    client, _ = api
    response = client.post("/auth/login", json={"username": "C01", "password": "not-the-password"})
    assert response.status_code == 401
    assert client.post("/auth/login", json={"username": "nobody", "password": "x" * 12}).status_code == 401
    failed = [r for r in audit_rows(client) if r["action"] == "login" and r["outcome"] == "failed"]
    assert {r["actor"] for r in failed} == {"C01", "nobody"}


def test_repeated_failures_lock_the_login(api):
    client, _ = api
    for _ in range(5):
        client.post("/auth/login", json={"username": "C02", "password": "wrong-password!"})
    response = client.post("/auth/login", json={"username": "C02", "password": "clinician-test-password"})
    assert response.status_code == 429


def test_forged_or_expired_tokens_are_refused(api):
    client, _ = api
    now = datetime.now(UTC)
    forged = jwt.encode({"sub": "admin", "role": "admin", "exp": now + timedelta(minutes=5)}, "x" * 40, "HS256")
    expired = jwt.encode({"sub": "C01", "role": "clinician", "exp": now - timedelta(minutes=1)}, TEST_SECRET, "HS256")
    for token in (forged, expired, "not-a-token"):
        assert client.get("/patients", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_passwords_are_stored_only_as_argon2_hashes(api):
    client, _ = api
    from app.tables import Clinician

    with client.app.state.sessions() as session:
        stored = session.get(Clinician, "C01").password_hash
    assert stored.startswith("$argon2") and "clinician-test-password" not in stored


def test_api_refuses_to_start_without_a_real_secret():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        make_api(secret_key="change-me")


def test_devices_need_the_ingest_key(api):
    client, _ = api
    message = reading(P001, 0)
    assert client.post("/readings", json=message, headers={"X-Ingest-Key": "wrong"}).status_code == 401
    client.headers.pop("X-Ingest-Key")
    assert client.post("/readings", json=message).status_code == 401
    assert client.post("/readings", json=message, headers=login(client, "C01")).status_code == 401  # not a device


# --- T4 (R5): clinicians see only their own patients ------------------------------------------


def test_T4_clinician_cannot_see_another_clinicians_patient(api):
    client, _ = api
    other = next(p for p in PATIENTS.to_dict("records") if p["clinician_id"] != P001["clinician_id"])
    headers = login(client, P001["clinician_id"])
    for url in [
        f"/patients/{other['patient_id']}",
        f"/patients/{other['patient_id']}/history",
        f"/patients/{other['patient_id']}/thresholds",
    ]:
        assert client.get(url, headers=headers).status_code == 403, url
    assert (
        client.put(
            f"/patients/{other['patient_id']}/thresholds/heart_rate",
            headers=headers,
            json={"high": 110, "reason": "trying"},
        ).status_code
        == 403
    )
    denied = audit_rows(client, patient_id=other["patient_id"])
    assert {r["outcome"] for r in denied if r["actor"] == P001["clinician_id"]} == {"denied"}


def test_patient_list_and_alerts_show_only_my_patients(api):
    client, _ = api
    for minute in range(10):
        client.post("/readings", json=reading(P002, minute, spo2=84.0, heart_rate=118.0))
    mine = {p["patient_id"] for p in PATIENTS.to_dict("records") if p["clinician_id"] == P001["clinician_id"]}
    headers = login(client, P001["clinician_id"])
    assert {p["id"] for p in client.get("/patients", headers=headers).json()} == mine
    alerts = client.get("/alerts", headers=headers).json()
    assert all(a["patient_id"] in mine for a in alerts)
    assert P002["clinician_id"] != P001["clinician_id"] and alerts == []
    assert len(client.get("/patients", headers=login(client, "admin")).json()) == len(PATIENTS)


def test_only_admins_read_the_audit_log(api):
    client, _ = api
    assert client.get("/audit", headers=login(client, "C01")).status_code == 403


def test_views_and_changes_are_audited(api):
    client, _ = api
    headers = login(client, P001["clinician_id"])
    client.get(f"/patients/{P001['patient_id']}/history", headers=headers)
    client.put(
        f"/patients/{P001['patient_id']}/thresholds/heart_rate",
        headers=headers,
        json={"high": 100, "reason": "post-op, keep a close eye"},
    )
    actions = [(r["actor"], r["action"], r["patient_id"]) for r in audit_rows(client, patient_id=P001["patient_id"])]
    assert (P001["clinician_id"], "history.view", P001["patient_id"]) in actions
    assert (P001["clinician_id"], "threshold.set", P001["patient_id"]) in actions


# --- T11 (R10): per-patient thresholds ---------------------------------------------------------


def test_T11_a_threshold_changes_alerts_for_that_patient_only(api):
    client, notifier = api
    headers = login(client, P001["clinician_id"])
    response = client.put(
        f"/patients/{P001['patient_id']}/thresholds/heart_rate",
        headers=headers,
        json={"high": 100, "reason": "post-op tachycardia watch"},
    )
    assert response.status_code == 200 and response.json()["limits"][0]["high"] == 100
    for patient in (P001, P002):  # the same fast pulse (about 106) for both patients
        for minute in range(8):
            client.post("/readings", json=reading(patient, minute, heart_rate=105.0 + minute % 3))
    alerted = {n.message.split("patient ")[1].split(" ")[0] for n in notifier.sent}
    assert alerted == {P001["patient_id"]}


def test_personal_limits_stop_the_P005_false_alarm():
    """P005's usual systolic BP is about 95. Without limits the scenario's normal phase raises a false alarm;
    with a personal range set by the clinician it does not, and real deterioration still alerts."""
    messages = scenario.build(P005)
    client, notifier = make_api()
    for m in messages:
        client.post("/readings", json=m)
    early = [n for n in notifier.sent if int(n.message.split(" at ")[1][14:16]) < scenario.CRITICAL_FROM]
    assert early, "expected the known false alarm without personal limits"

    client, notifier = make_api()
    response = client.put(
        f"/patients/{P005['patient_id']}/thresholds/systolic_bp",
        headers=login(client, "admin"),
        json={"low": 85, "high": 150, "reason": "usual SBP 90-100, asymptomatic"},
    )
    assert response.status_code == 200
    results = [client.post("/readings", json=m).json() for m in messages]
    assert [n.kind for n in notifier.sent] == ["new"]
    first = next(r for r in results if r.get("alerts_raised"))
    assert int(first["msg_id"][-2:]) >= scenario.CRITICAL_FROM


@pytest.mark.parametrize(
    ("vital", "body"),
    [
        ("pulse", {"high": 100, "reason": "ok"}),
        ("heart_rate", {"reason": "no limits given"}),
        ("heart_rate", {"low": 100, "high": 90, "reason": "backwards"}),
        ("heart_rate", {"high": 400, "reason": "impossible"}),
        ("heart_rate", {"high": 100, "reason": ""}),
        ("glucose", {"low": 4, "reason": "patient has no diabetes"}),
    ],
)
def test_bad_thresholds_are_refused(api, vital, body):
    client, _ = api
    patient = PATIENTS[PATIENTS["diabetes"] == 0].iloc[0].to_dict()
    response = client.put(
        f"/patients/{patient['patient_id']}/thresholds/{vital}",
        json=body,
        headers=login(client, patient["clinician_id"]),
    )
    assert response.status_code == 422


def test_threshold_reset_returns_to_defaults(api):
    client, _ = api
    headers = login(client, P001["clinician_id"])
    url = f"/patients/{P001['patient_id']}/thresholds/heart_rate"
    client.put(url, headers=headers, json={"high": 100, "reason": "temporary"})
    assert client.delete(url, headers=headers).json()["limits"] == []
    assert client.delete(url, headers=headers).status_code == 404


def test_repeated_views_are_logged_once_but_refusals_every_time(api):
    client, _ = api
    headers = login(client, P001["clinician_id"])
    other = next(p for p in PATIENTS.to_dict("records") if p["clinician_id"] != P001["clinician_id"])
    for _ in range(5):  # the dashboard refreshing
        client.get(f"/patients/{P001['patient_id']}/history", headers=headers)
        client.get(f"/patients/{other['patient_id']}/history", headers=headers)
    rows = audit_rows(client)
    views = [r for r in rows if r["action"] == "history.view" and r["patient_id"] == P001["patient_id"]]
    denied = [r for r in rows if r["action"] == "history.view" and r["outcome"] == "denied"]
    assert len(views) == 1 and len(denied) == 5
