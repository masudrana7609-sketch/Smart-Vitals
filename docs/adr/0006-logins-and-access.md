# ADR 6: Logins, roles and the audit log

**Status:** accepted
**Date:** 10 Nov 2026

## Context
R5: data stored securely and access-controlled; clinicians see only their own patients. R7: UK GDPR treats health data as special category data, so access must be limited and accountable. The ethics checklist asks for hashed passwords, keys outside the repository, and a log of who viewed or changed what.

## Options considered
- **Sessions in the API's memory (cookies)**: simple, but every service would need to share session state.
- **Signed tokens (JWT)**: any service can check a token with the shared secret; nothing to store; but a token cannot be withdrawn before it expires.
- **An identity provider (e.g. NHS Care Identity Service, OpenID Connect)**: what a real deployment needs; too much for a prototype.

## Decision
Signed tokens (HS256) that expire after 30 minutes, with argon2 password hashes (pwdlib's recommended settings). Two roles: **clinician** (own patients only) and **admin** (all patients, thresholds, audit log). Devices use a separate ingest key. Every login, view, change and refused access goes to an audit table, written in the same transaction as the action; repeated views are logged once per 5 minutes.

## Evidence
`tests/test_security.py` (21 tests): every patient endpoint needs a login; forged, expired and malformed tokens are refused; wrong passwords are refused and audited; 5 failures lock the name; passwords are stored only as argon2 hashes; the API will not start with a placeholder secret; devices need the ingest key; T4 (403 and an audit entry for another clinician's patient); lists and alerts show only one's own patients; only admins read the audit log. Screenshot: `docs/results/screenshots/denied_P002.png`, `audit.png`.

## Consequences
- **Better:** access is enforced in one place (the API); every access is accountable; no passwords in the database or repository.
- **Worse:** a stolen token works until it expires (30 minutes) and cannot be revoked; the login throttle is in memory (lost on restart, not shared between API copies); traffic is not yet encrypted (HTTPS/TLS: Sprint 4 and the report); no multi-factor login. A real deployment would use the NHS's identity service instead.
