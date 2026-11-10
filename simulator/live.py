"""Streaming readings to the system, as wearables would (R2): over MQTT (QoS 1) or HTTP.

Messages go out in order of arrival time, paced by the simulated clock divided by the speed-up (A4):
at 60x, one simulated minute takes one real second. Each message carries `sent_at`, its simulated arrival
time, so the server can measure lateness in simulated time (A20).
"""

import json
import logging
import math
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator

import pandas as pd

from src.vitals import VITALS

log = logging.getLogger("smartvitals.simulator")
PAYLOAD_FIELDS = ("msg_id", "device_id", "patient_id", "measured_at")


def payloads(delivered: pd.DataFrame) -> Iterator[dict]:
    """Messages as a wearable would send them: no label, no risk group, missing vitals as null."""
    for row in delivered.to_dict("records"):
        message = {k: row[k] for k in PAYLOAD_FIELDS}
        message["sent_at"] = row["received_at"]
        for vital in VITALS:
            value = row[vital]
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            message[vital] = float(value)
        yield message


def stream(
    messages: Iterable[dict], send: Callable[[dict], object], speedup: float, sleep=time.sleep, limit: int | None = None
) -> Counter:
    """Send messages in order, waiting (gap in simulated time) / speedup between them. speedup <= 0: no waiting."""
    results: Counter = Counter()
    previous = None
    for count, message in enumerate(messages):
        if limit is not None and count >= limit:
            break
        sent = pd.Timestamp(message["sent_at"])
        if previous is not None and speedup > 0:
            gap = (sent - previous).total_seconds() / speedup
            if gap > 0:
                sleep(gap)
        previous = sent
        results[str(send(message))] += 1
    return results


class HttpSender:
    """POST each message to the API's /readings endpoint with the device ingest key (X-Ingest-Key).
    client can be an httpx.Client or a FastAPI TestClient."""

    def __init__(self, api_url: str = "http://localhost:8000", client=None, timeout: float = 10, ingest_key: str = ""):
        import httpx

        self.client = client or httpx.Client(base_url=api_url, timeout=timeout)
        self.headers = {"X-Ingest-Key": ingest_key} if ingest_key else {}

    def __call__(self, message: dict) -> str:
        response = self.client.post("/readings", json=message, headers=self.headers)
        if response.status_code == 200:
            return response.json()["result"]
        log.warning("%s: HTTP %s %s", message["msg_id"], response.status_code, response.text[:200])
        return f"http_{response.status_code}"


class MqttSender:
    """Publish each message to <topic>/<device_id> with QoS 1 (delivered at least once)."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 1883,
        topic: str = "smartvitals/readings",
        username: str = "",
        password: str = "",
        client_id: str = "smartvitals-simulator",
    ):
        import paho.mqtt.client as mqtt

        self.topic = topic
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if username:
            self.client.username_pw_set(username, password)
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()

    def __call__(self, message: dict) -> str:
        info = self.client.publish(f"{self.topic}/{message['device_id']}", json.dumps(message), qos=1)
        info.wait_for_publish(timeout=10)
        return "published" if info.is_published() else "not_published"

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
