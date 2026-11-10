# Report outline (Output 5)

Start this now and add to it every week: each ADR, result and reflection has a place here. The headings follow the assessment brief; the brief's learning outcome for each part is in brackets. Use **Harvard referencing** throughout (`references.md`).

1. **Introduction:** MedLink's problem, the aim of your IPMS, and its scope.
2. **Critical evaluation of approaches (Output 1, LO1):** at least two approaches compared with evidence; your choice justified against the alternatives (`docs/approaches.md`).
3. **Requirements, assumptions and data:** how you meet R1 to R11 (`requirements-checklist.md`); your assumptions (`assumptions.md`); your data and how labels were made (`DATA_CARD.md`).
4. **System design and architecture (LO2):** the architecture diagram; edge/cloud split, APIs, containers; key decisions as ADRs (R11).
5. **Implementation (Output 2, LO2):** ingestion pipeline, model, alerts, storage, access control, dashboard.
6. **Testing and evaluation (Output 4):** test cases and screenshots (`test-plan.md`); model metrics (accuracy, precision, recall, F1, confusion matrix) on unseen patients; what the results mean.
7. **Ethical, security, privacy, sustainability and societal implications (Output 3, LO3):** from your checklist, and how your design addresses each.
8. **Limitations and critical reflection (LO4):** what works, what does not, what you would change, and what a real deployment would need.
9. **References** (Harvard).

**Appendices:** user guide (how to run it), extra test evidence, progress log.

---

## Evidence map *(prepared with Claude: where to find the evidence for each section; the writing is yours)*

| Section | Questions the section should answer | Evidence, numbers and figures |
|---|---|---|
| 1. Introduction | What problem does MedLink have? What does the IPMS do, and what is out of scope (prototype, not a medical device)? | README "What it does"; requirements checklist |
| 2. Critical evaluation (Output 1) | Which approaches did you compare, on what criteria, and why did you choose yours? Where does your choice lose? | `docs/approaches.md` (both comparisons); `results/model_comparison.md`; `results/edge_cloud.md`; notebook 02; ADR 1, 3 |
| 3. Requirements, assumptions, data | How is each of R1-R11 met and tested? Which assumptions matter most? How were data and labels made, and what does that limit? | `requirements-checklist.md`; `assumptions.md` (A1-A32); `data/DATA_CARD.md`; notebook 01 (0.62 and why) |
| 4. Design and architecture (LO2) | What runs where, what crosses each arrow, and why? | `docs/architecture.png`; ADRs 2-8; `docker-compose.yml` |
| 5. Implementation (Output 2) | How does a reading become an alert? How are access and thresholds handled? | `app/README.md` (pipeline steps); `simulator/README.md`; dashboard screenshots; ADR 5, 6, 7 |
| 6. Testing and evaluation (Output 4) | Do the tests prove each requirement? How good is the model on unseen patients, and for whom? What failed during testing, and what did you change? | `test-plan.md` (T1-T22); `results/model_v2_confusion.png`; `results/fairness.md` and `fairness_recall.png`; `results/docker_compose.md` (the two data-loss bugs); screenshots |
| 7. Ethics, security, privacy, sustainability (Output 3) | Which risks did you find, and what does the design do about each? Which trade-off (missed alerts against alarm fatigue; trends against data sent) did you choose, and why? | `ethics-security-checklist.md`; ADR 5 (alarm fatigue), 6 (access, audit), 7 (limits), 8 (no TLS yet); A7/A31 (retention); fairness results; `edge_cloud.md` (data per patient) |
| 8. Limitations and reflection (LO4) | What works, what does not, what would you change, and what would a real deployment need? | Labels from our own rule (A2); simulated physiology; no breathing rate (A14); threshold varies by fold (0.157-0.327); no TLS; in-memory device buffer; AI use (`ai-use-log.md`) |
| 9. References | | `references.md` |

Figures ready to use: `docs/architecture.png` (or `.svg`), `docs/results/first_model_confusion_sim.png`, `model_v2_confusion.png`, `fairness_recall.png`, `docs/results/screenshots/*.png`.
