# AI use log

A record of where and how AI assistants were used in this project, following the university's regulations on the use of AI. It feeds the *Use of AI tools* section of `README.md` and the report. Every row says what the tool produced and what **I** decided, checked or changed.

| Date | Task | What Claude did | What I decided/changed |
|---|---|---|---|
| 2026-11-09 | Project kick-off: read the starter repo and plan the build | Claude Code (Opus 5.5) read the starter files (README, START_HERE, docs/, notebook 01, tests, data card). It summarised the requirements against R1–R11 and Outputs 1–6, proposed a folder structure, dependencies and build order, and listed the open design decisions with options. It wrote setup files only, no features: `requirements.txt`, `pyproject.toml` (ruff and pytest config), `.env.example`, `.gitignore`, `docs/dev-setup.md` and this log. | Accepted all the recommended options (30 patients / 3 clinicians, 60× speed, recall ≥ 0.90, acknowledge-based alerts, 30-day / 1-year retention, SQLite + Postgres, React, MQTT, Git). |
| 2026-11-09 | Record the agreed design decisions | I accepted all of Claude's recommendations. Claude then wrote `CLAUDE.md` (rules, decisions, sprint plan), added assumptions A3–A8, drafted ADRs 2–5 (database, MQTT and edge/cloud split, React dashboard, alert rule), turned on the Postgres driver in `requirements.txt`, updated `.env.example`, and set up Git. | *(to fill in: what I checked or reworded in the ADRs and assumptions)* |
