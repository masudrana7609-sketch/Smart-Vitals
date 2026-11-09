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
To add in S2/S4: time from a Critical reading to an alert; behaviour when the broker restarts. Comparison table in `docs/approaches.md` (Comparison 2).

## Consequences
- **Better:** devices stay simple; the model can be updated in one place; T10 tests a real failure mode.
- **Worse:** one more service (the broker) to run and secure. Prototype runs MQTT without TLS on a private Docker network; the report explains what a real deployment needs (TLS, per-device credentials).
