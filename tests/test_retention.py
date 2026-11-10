"""Storage limitation (R7, A7): old readings, alerts and audit events are deleted; recent ones are kept."""

from conftest import PATIENTS, login, make_api
from sqlalchemy import func, select

from app.retention import purge
from app.tables import Alert, AuditEvent, Reading

P001 = PATIENTS.iloc[0].to_dict()


def reading(day, minute, **vitals):
    values = {
        "heart_rate": 76.0 + minute % 3,
        "spo2": 97.0,
        "systolic_bp": 121.0 + minute % 4,
        "diastolic_bp": 79.0 + minute % 2,
        "temperature": 36.8,
        **vitals,
    }
    stamp = f"2026-01-{day:02d}T00:{minute:02d}:00Z"
    return {
        "msg_id": f"P001-D{day}-{minute:02d}",
        "device_id": P001["device_id"],
        "patient_id": "P001",
        "measured_at": stamp,
        "sent_at": stamp,
        **values,
    }


def count(session, table):
    return session.scalar(select(func.count()).select_from(table))


def test_old_readings_go_but_alerts_keep_their_vitals():
    client, _ = make_api()
    for minute in range(10):  # day 1: a Critical episode, with an alert
        client.post("/readings", json=reading(1, minute, **({"spo2": 84.0, "heart_rate": 118.0} if minute > 4 else {})))
    for minute in range(5):  # 40 days later: normal readings
        client.post("/readings", json=reading(10, minute))
    sessions, settings = client.app.state.sessions, client.app.state.settings
    with sessions() as session:
        assert count(session, Alert) == 1
        settings = settings.model_copy(update={"readings_retention_days": 5})
        deleted = purge(session, settings)
        assert deleted["readings"] == 10 and deleted["alerts"] == 0
        assert count(session, Reading) == 5
        alert = session.scalars(select(Alert)).one()
        assert alert.reading_id is None and alert.vitals["spo2"] == 84.0  # what the clinician was told survives
        assert session.scalars(select(AuditEvent).where(AuditEvent.action == "retention.purge")).one().actor == "system"
    history = client.get("/patients/P001/history", headers=login(client, P001["clinician_id"])).json()
    assert len(history["readings"]) == 5 and len(history["alerts"]) == 1


def test_old_alerts_and_audit_events_go_too():
    client, _ = make_api()
    for minute in range(10):
        client.post("/readings", json=reading(1, minute, spo2=84.0, heart_rate=118.0))
    client.post("/readings", json=reading(10, 0))
    login(client, "admin")  # an audit event
    with client.app.state.sessions() as session:
        settings = client.app.state.settings.model_copy(
            update={"readings_retention_days": 5, "alerts_retention_days": 5, "audit_retention_days": -1}
        )
        deleted = purge(session, settings)
        assert deleted["alerts"] == 1 and deleted["notifications"] >= 1 and deleted["audit_events"] >= 1
        assert count(session, Alert) == 0


def test_default_periods_keep_recent_data():
    client, _ = make_api()
    for minute in range(10):
        client.post("/readings", json=reading(1, minute))
    with client.app.state.sessions() as session:
        assert purge(session, client.app.state.settings)["readings"] == 0
        assert count(session, Reading) == 10
