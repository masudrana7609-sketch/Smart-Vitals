"""The ingest service: subscribes to the MQTT feed and runs every message through the same pipeline as the API.

    python -m app.mqtt_ingest

QoS 1 means a message can arrive twice (T10); the pipeline drops a repeated msg_id. Each message is
acknowledged to the broker only after it has been stored, so a crash before storing means the broker
sends it again rather than losing it.
"""

import json
import logging
import signal
import sys

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from app import pipeline
from app.classifier import Classifier
from app.config import get_settings
from app.db import init_db, make_engine, make_session_factory
from app.notify import LogNotifier
from app.schemas import ReadingIn

log = logging.getLogger("smartvitals.ingest")


def handle_payload(payload: bytes, sessions, classifier, settings, notifier):
    """Process one MQTT payload. Returns the IngestResult, or None for a message that cannot be read."""
    try:
        msg = ReadingIn.model_validate(json.loads(payload))
    except (ValueError, ValidationError) as problem:
        log.warning("dropped unreadable message: %s", str(problem)[:200])
        return None
    with sessions() as session:
        outcome = pipeline.process(session, msg, classifier, settings, notifier)
    if outcome.result.result == "rejected":
        log.warning("rejected %s: %s", msg.msg_id, outcome.result.reason)
    return outcome.result


def make_client(sessions, classifier, settings, notifier, client_id="smartvitals-ingest") -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=client_id,
        clean_session=False,
        protocol=mqtt.MQTTv311,
    )
    client.manual_ack_set(True)
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    def on_connect(client, userdata, flags, reason_code, properties):
        log.info("connected (%s); subscribing to %s/#", reason_code, settings.mqtt_topic)
        client.subscribe(f"{settings.mqtt_topic}/#", qos=1)

    def on_message(client, userdata, message):
        try:
            handle_payload(message.payload, sessions, classifier, settings, notifier)
        except Exception:  # keep the service running; do not acknowledge, so the broker can redeliver
            log.exception("failed to process a message")
            return
        client.ack(message.mid, message.qos)

    client.on_connect = on_connect
    client.on_message = on_message
    return client


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    client = make_client(
        make_session_factory(engine), Classifier(settings.model_path, settings.rule_safety_net), settings, LogNotifier()
    )
    signal.signal(signal.SIGTERM, lambda *_: client.disconnect())
    client.connect(settings.mqtt_host, settings.mqtt_port, keepalive=30)
    client.loop_forever(retry_first_connection=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
