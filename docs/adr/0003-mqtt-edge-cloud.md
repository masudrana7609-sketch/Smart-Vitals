# ADR 3: Readings travel over MQTT; checks at the edge, the model in the cloud

**Status:** accepted
**Date:** 9 Nov 2026

## Context
R2 needs a continuous IoT-style feed; R9 needs dropouts, delays, impossible values and duplicates handled without false or missing alerts; R11 needs an edge/cloud split that is justified.

## Options considered
- HTTP POST from each simulated device straight to the API.
- MQTT: devices publish to a Mosquitto broker (QoS 1); an ingest service subscribes and passes readings on.
- Both.

Where the model runs: on the edge device, in the cloud, or split.

## Decision
MQTT with QoS 1 (it is built for small, unreliable devices, and it builds on the Week 6 lab). The **edge** (simulated wearable) does validity checks and hard safety limits and adds a unique `message_id`; the **cloud** runs the ML model, stores the data and raises alerts. QoS 1 can deliver a message twice, so the ingest service removes duplicates by `message_id` (T10).

## Evidence
- `tests/test_mqtt.py`: the scenario published over a real MQTT broker (amqtt, QoS 1), 27 messages including a duplicate: 26 stored, 1 alert.
- The ingest service acknowledges a message to the broker only after storing it, so a crash means redelivery, not loss; the duplicate check makes redelivery safe.
- Throughput over HTTP on a laptop: about 92 messages a second (10,903 in 118 s), three times what 30 patients at 60x need.
- Time from the first Critical reading to an alert: 1-3 readings (the last-5 median needs to move); in the scenario, 2 simulated minutes.
- To add in S4: behaviour when the broker restarts (Docker). Comparison table in `docs/approaches.md` (Comparison 2).

## Consequences
- **Better:** devices stay simple; the model can be updated in one place; T10 tests a real failure mode.
- **Worse:** one more service (the broker) to run and secure. Prototype runs MQTT without TLS on a private Docker network; the report explains what a real deployment needs (TLS, per-device credentials).
