# ADR 8: Containers, networks, and what Docker taught us

**Status:** accepted
**Date:** 10 Nov 2026

## Context
R11 asks for an architecture using emerging-technology principles (microservices, containers) with the choices justified; T12 asks for `docker compose up` to start everything on a clean machine. R5 and R7 still apply inside the containers.

## Options considered
- **One container running everything**: simplest; but one failure stops all, and parts cannot be scaled or restarted separately.
- **Separate services in Docker Compose**: db, broker, API, ingest, retention, dashboard and a demo simulator, each in its own container.
- **Kubernetes**: what a hospital-scale deployment would use; far too much for a prototype.

## Decision
Docker Compose with one Python image for the five Python services and an nginx image for the dashboard.
- **Networks:** the database and broker sit on an `internal` network with no route out; only the API (8000) and the dashboard (8080) are published, and only on 127.0.0.1.
- **Least privilege:** the Python containers run as a non-root user; Mosquitto needs a login, and its ACL lets `devices` only publish readings and `ingest` only read them.
- **Order:** a one-off `seed` job creates the tables and logins before the API and ingest start.
- **Secrets:** only in `.env` (ignored by Git); Compose refuses to start if any is missing.

## Evidence
`docs/results/docker_compose.md`: all services up in 28 s; health checks pass; ACL and anonymous-access checks; non-root user; security headers. Two problems were found **only** by running the real broker:
1. **Mosquitto silently drops messages** beyond 1,000 queued for a subscriber: a burst of 3,000 readings lost about 1,970. Fixed with `max_queued_messages 200000`; after the fix 2,960 of 2,960 arrived. MQTT QoS 1 guarantees delivery to the broker, not through it.
2. **The simulated device crashed when the broker went away**, losing 1,420 of 1,777 readings in a 20-second outage. Fixed with store-and-forward (`simulator/live.py`); after the fix 0 were lost.

## Consequences
- **Better:** one command starts the system; services restart independently; the database and broker cannot be reached from outside; a broker outage or burst loses nothing.
- **Worse:** no TLS yet. Traffic between the browser and nginx, and between services, is unencrypted (acceptable on one machine with simulated data; a real deployment needs HTTPS, MQTT over TLS and Postgres TLS, with certificates). The device's buffer is in memory, so a device restart during an outage would still lose readings (a real gateway would buffer on disk). Images are not yet scanned for vulnerabilities.
