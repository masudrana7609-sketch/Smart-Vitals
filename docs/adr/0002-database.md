# ADR 2: SQLite for tests, Postgres in Docker

**Status:** accepted
**Date:** 9 Nov 2026

## Context
R6 needs a history of readings and alerts for each patient; R5 needs it stored securely; R11 asks for a justified, container-based architecture. Tests must stay fast and run without Docker.

## Options considered
- SQLite only: no server, one file; but only one writer at a time, and less like a real deployment.
- Postgres only: realistic, handles several services writing at once; but every test run needs a database server.
- SQLite for tests and local work, Postgres in Docker, behind SQLAlchemy (`DATABASE_URL` picks one).

## Decision
The third option. The code uses SQLAlchemy only, so changing the database is a one-line setting.

## Evidence
To add in S2/S4: test run time on SQLite; ingest rate on Postgres in Docker.

## Consequences
- **Better:** fast tests; the Docker stack looks like a real deployment; the ingest service and API can write at the same time.
- **Worse:** two databases can behave slightly differently (time zones, types). Managed by running the API tests against Postgres once before hand-in.
