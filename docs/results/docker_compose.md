# T12: the whole system in Docker (10 Nov 2026)

`docker compose up --build` on macOS (Apple M4, Docker Desktop, engine 29.9.3, Compose 5.7.0), with a fresh `.env`.

## Every service starts, and the API answers
All services were up in **28 seconds** (images already built). The one-off `seed` job exited 0.

| Service | Image | Status | Published port |
|---|---|---|---|
| db | postgres:17-alpine | healthy | none (internal network only) |
| mqtt | eclipse-mosquitto:2.0 | up | none (internal network only) |
| seed | smartvitals-python:0.4 | exited 0 (tables, 30 patients, logins) | none |
| api | smartvitals-python:0.4 | healthy | 127.0.0.1:8000 |
| ingest | smartvitals-python:0.4 | up, connected to the broker as `ingest` | none |
| retention | smartvitals-python:0.4 | up (hourly) | none |
| dashboard | smartvitals-dashboard:0.4 (nginx) | up | 127.0.0.1:8080 |

`GET http://localhost:8000/health` and `GET http://localhost:8080/api/health` both returned `{"status":"ok","model":"model_v2"}`; the dashboard returned HTTP 200.

## Readings over the real broker
| Test | Result |
|---|---|
| 3,000 messages published at once (2,960 distinct readings + 40 duplicates) | **First run: only 1,028 stored.** Mosquitto's default queue (1,000 messages per subscriber) silently dropped the rest ("Outgoing messages are being dropped for client smartvitals-ingest"). After raising `max_queued_messages` to 200,000: **2,960 of 2,960 stored**, 0 duplicates, about 118 readings a second end to end |
| Broker stopped for 20 s while 1,800 messages streamed at 60x | **First run: the simulated device crashed** ("client is not currently connected") and only 357 of 1,777 readings arrived. After adding store-and-forward to the device: **1,777 of 1,777 stored**; 723 were kept on the device during the outage and sent after reconnecting; 0 unacknowledged; ingest reconnected by itself after 11 s |

## Security checks
| Check | Result |
|---|---|
| Anonymous MQTT connection | Refused: "Connection Refused: not authorised" |
| `devices` login subscribing to readings | Receives nothing (ACL: write only) |
| `ingest` login publishing a reading | Silently dropped by the broker (ACL: read only); the ingest service never received it |
| Containers' user | `uid=10001(smartvitals)`, not root |
| Dashboard headers | `Content-Security-Policy` (scripts from the site only), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` |
| Ports reachable from the machine | Only 8000 (API) and 8080 (dashboard), on 127.0.0.1. The broker and database are on an `internal` network |

## Not covered
HTTPS/TLS between the browser and nginx, and TLS for MQTT and Postgres, are not set up (see ADR 8). Images are not scanned for vulnerabilities.
