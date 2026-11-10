"""The MQTT path, end to end (R2, R9, T10): simulator -> broker (QoS 1) -> ingest service -> database.

Uses amqtt, a small MQTT broker written in Python, so the test needs no Docker or Mosquitto. In Docker the
real broker is Mosquitto (ADR 3).
"""

import asyncio
import socket
import threading
import time

import numpy as np
import pytest
from sqlalchemy import func, select

from app.classifier import Classifier
from app.config import Settings
from app.db import init_db, make_engine, make_session_factory
from app.mqtt_ingest import handle_payload, make_client
from app.notify import ListNotifier
from app.seed import seed
from app.tables import Alert, Reading
from simulator import scenario
from simulator.config import SimConfig
from simulator.live import MqttSender, stream
from simulator.patients import generate_patients

amqtt_broker = pytest.importorskip("amqtt.broker")
PATIENTS = generate_patients(SimConfig(n_patients=3, seed=3), np.random.default_rng(3))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def broker_port():
    port = _free_port()
    loop = asyncio.new_event_loop()
    started = threading.Event()

    def run():
        asyncio.set_event_loop(loop)
        broker = amqtt_broker.Broker(
            {"listeners": {"default": {"type": "tcp", "bind": f"127.0.0.1:{port}"}}}, loop=loop
        )
        loop.run_until_complete(broker.start())
        started.set()
        loop.run_forever()

    threading.Thread(target=run, daemon=True).start()
    assert started.wait(10), "broker did not start"
    yield port
    loop.call_soon_threadsafe(loop.stop)


@pytest.fixture
def system(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", _env_file=None)
    engine = make_engine(settings.database_url)
    init_db(engine)
    sessions = make_session_factory(engine)
    with sessions() as session:
        seed(session, PATIENTS)
    return settings, sessions, Classifier(settings.model_path), ListNotifier()


def _wait_for(condition, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.1)
    return False


def test_unreadable_payload_is_dropped_not_crashing(system):
    settings, sessions, classifier, notifier = system
    assert handle_payload(b"not json", sessions, classifier, settings, notifier) is None
    assert handle_payload(b'{"msg_id": "x"}', sessions, classifier, settings, notifier) is None


def test_scenario_over_mqtt_stores_each_message_once_and_alerts_once(system, broker_port):
    settings, sessions, classifier, notifier = system
    settings = settings.model_copy(update={"mqtt_port": broker_port, "mqtt_host": "127.0.0.1"})
    ingest = make_client(sessions, classifier, settings, notifier, client_id="test-ingest")
    ingest.connect("127.0.0.1", broker_port)
    ingest.loop_start()
    try:
        assert _wait_for(lambda: ingest.is_connected())
        time.sleep(0.5)  # let the subscription settle
        sender = MqttSender("127.0.0.1", broker_port, settings.mqtt_topic, client_id="test-simulator")
        messages = scenario.build(PATIENTS.iloc[0].to_dict())
        results = stream(messages, sender, speedup=0)
        sender.close()
        assert results == {"published": len(messages)}  # 27 messages, one of them a duplicate

        def stored():
            with sessions() as s:
                return s.scalar(select(func.count(Reading.id)))

        assert _wait_for(lambda: stored() == 26), f"stored {stored()} of 26"
        time.sleep(0.5)
        with sessions() as s:
            assert s.scalar(select(func.count(Reading.id))) == 26
            assert s.scalar(select(func.count(Alert.id))) == 1
        assert [n.kind for n in notifier.sent] == ["new"]
    finally:
        ingest.loop_stop()
        ingest.disconnect()
