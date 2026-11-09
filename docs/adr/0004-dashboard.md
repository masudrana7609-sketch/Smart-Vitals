# ADR 4: A React dashboard on top of the API

**Status:** accepted
**Date:** 9 Nov 2026

## Context
R8 needs vital-sign trend charts; R5 needs clinicians to see only their own patients; R10 needs a view to set thresholds for each patient.

## Options considered
- Streamlit (Python): quickest to build; login and per-user pages are awkward.
- React + Vite + TypeScript + Recharts: more work; a clean, separate front end.

## Decision
React. The dashboard holds no data of its own: every request goes to the API with the clinician's token, and **the API enforces access control**, so a mistake in the front end cannot leak another clinician's patients (T4).

## Evidence
To add in S3: T4, T6 and T11 results and screenshots.

## Consequences
- **Better:** a clear front end / back end split (R11); the security boundary is in one place.
- **Worse:** a second language and build tool. Managed by keeping the dashboard small: login, patient list, patient detail with charts and alerts, thresholds form.
