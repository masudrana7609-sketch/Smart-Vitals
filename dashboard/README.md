# dashboard/ (R5, R8, R10)

The clinician-facing dashboard: log in, see only your own patients, view each patient's vital-sign trends and alerts, and set alert thresholds for a patient.

Your Week 5 charts are the starting point. A Python dashboard framework (for example Streamlit or Dash) talking to your API is a quick route; say in an ADR why you chose yours.

## What it does (Sprint 3)

React 19 + Vite + TypeScript + Recharts, talking only to the API (ADR 4). The API decides who sees what (R5); the dashboard shows what it is given.

- **Sign in** as a clinician (`C01`, `C02`, `C03`) or `admin`. The token lasts 30 minutes and is kept in `sessionStorage`, so it ends when the tab closes.
- **My patients**: open alerts (acknowledge them here) and the patient list, most urgent first. Refreshes every 5 seconds.
- **Patient page**: one trend chart per vital (R8, T6) over 1, 6 or 24 hours, with the default normal band (grey), the patient's personal limits (dashed), alerts (red line) and Critical readings where that vital scored (red dot); hover for exact values. The "why" line shows which vitals scored. Below: the patient's alerts, their **alert limits** (R10, T11) and a table of the latest readings with any quality flags.
- **Another clinician's patient** shows "Not your patient" (the API returned 403, and the attempt is in the audit log: T4).
- **Admin**: every patient, thresholds, and the **audit log**.

Status is never shown by colour alone (icon + word); light and dark mode follow the system setting; the layout works down to phone width. Screenshots: `docs/results/screenshots/`.

## Run it

```bash
cd dashboard
npm install
npm run dev          # http://localhost:5173, forwarding /api to the API on http://localhost:8000
npm test             # 7 tests (Vitest + Testing Library)
npm run build        # type-check and production build into dashboard/dist
```

Use Node 22 or 24 (LTS). `API_URL=http://localhost:8765 npm run dev` points it at an API on another port.
