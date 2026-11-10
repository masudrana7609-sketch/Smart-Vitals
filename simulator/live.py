"""Streaming readings to the system, as wearables would (R2): over MQTT (QoS 1) or HTTP.

Messages go out in order of arrival time, paced by the simulated clock divided by the speed-up (A4):
at 60x, one simulated minute takes one real second. Each message carries `sent_at`, its simulated arrival
time, so the server can measure lateness in simulated time (A20).
"""

import json
import logging
import math
import threading
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
    """Publish each message to <topic>/<device_id> with QoS 1 (delivered at least once).

    Store-and-forward: if the broker cannot be reached, messages are kept on the device (in memory) and sent
    once the connection comes back (paho reconnects by itself). close() waits until the broker has
    acknowledged every message. A real wearable or gateway would keep this buffer on disk."""

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
        self.mqtt = mqtt
        self.unacked: set[int] = set()  # message IDs the broker has not yet acknowledged
        self.lock = threading.Lock()

        self.acked_early: set[int] = set()  # acknowledged before __call__ recorded them

        def on_publish(client, userdata, mid, reason_code, properties):
            with self.lock:
                if mid in self.unacked:
                    self.unacked.discard(mid)
                else:
                    self.acked_early.add(mid)

        self.client.on_publish = on_publish
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()

    def __call__(self, message: dict) -> str:
        # never hold self.lock while publishing: paho's network thread needs it to report acknowledgements
        info = self.client.publish(f"{self.topic}/{message['device_id']}", json.dumps(message), qos=1)
        if info.rc in (self.mqtt.MQTT_ERR_SUCCESS, self.mqtt.MQTT_ERR_NO_CONN):
            with self.lock:
                if info.mid in self.acked_early:
                    self.acked_early.discard(info.mid)
                else:
                    self.unacked.add(info.mid)
        if info.rc == self.mqtt.MQTT_ERR_SUCCESS:
            return "sent"
        if info.rc == self.mqtt.MQTT_ERR_NO_CONN:
            return "buffered"  # kept by the client and sent after reconnecting
        return f"error_{info.rc}"

    def unacknowledged(self) -> int:
        with self.lock:
            return len(self.unacked)

    def close(self, timeout: float = 120) -> int:
        """Wait until the broker has acknowledged everything (or timeout). Returns how many were not."""
        end = time.monotonic() + timeout
        while self.unacknowledged() and time.monotonic() < end:
            time.sleep(0.2)
        left = self.unacknowledged()
        self.client.loop_stop()
        self.client.disconnect()
        return left
