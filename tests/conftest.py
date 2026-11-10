"""Shared test setup: an API on an in-memory database, seeded with simulated patients and logins.
The secrets here are for tests only."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.notify import ListNotifier
from app.seed import seed
from simulator.config import SimConfig
from simulator.patients import generate_patients

TEST_SECRET = "test-secret-key-that-is-long-enough-0123456789"
TEST_INGEST_KEY = "test-ingest-key"
CLINICIAN_PASSWORD = "clinician-test-password"
ADMIN_PASSWORD = "admin-test-password"
PATIENTS = generate_patients(SimConfig(n_patients=6, seed=3), np.random.default_rng(3))


def settings_for_tests(**overrides) -> Settings:
    values = {"database_url": "sqlite://", "secret_key": TEST_SECRET, "ingest_key": TEST_INGEST_KEY}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def make_api(patients=PATIENTS, **overrides):
    """(TestClient with the device ingest key, ListNotifier)."""
    notifier = ListNotifier()
    app = create_app(settings_for_tests(**overrides), notifier=notifier)
    with app.state.sessions() as session:
        seed(session, patients, CLINICIAN_PASSWORD, ADMIN_PASSWORD)
    client = TestClient(app)
    client.headers.update({"X-Ingest-Key": TEST_INGEST_KEY})
    return client, notifier


def login(client, username, password=None) -> dict:
    """Authorization headers for this user."""
    password = password or (ADMIN_PASSWORD if username == "admin" else CLINICIAN_PASSWORD)
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def api():
    return make_api()
