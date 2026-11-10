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
- T6: `docs/results/screenshots/patient_P001_light.png` (24 h), `patient_P001_1h.png`, `patient_P001_dark.png`, `mobile_P001.png`: one chart per vital, default band, personal limit, alert line, Critical points.
- T4: `denied_P002.png` (the API's 403 shown as "Not your patient"); T11: the limits panel on the patient page.
- 7 dashboard tests (`npm test`); type-check and production build pass. Checked in Chrome at desktop and phone width (no horizontal scrolling), light and dark.
- Built with React 19.3, Vite 8.3, TypeScript 5.9 (not 7.0, too new for the tooling), Recharts 3.10, TanStack Query 5.

## Consequences
- **Better:** a clear front end / back end split (R11); the security boundary is in one place.
- **Worse:** a second language and build tool. Managed by keeping the dashboard small: login, patient list, patient detail with charts and alerts, thresholds form.
