# First model results (09 Nov 2026)

- Data: `sim_vitals.csv` (346418 rows, 8 feature columns)
- Predicting: `status`
- Test set: 69217 rows, from 16 patients the model never saw

| Measure | Baseline | First model |
|---|---|---|
| accuracy | 0.934 | 0.948 |
| balanced accuracy | 0.333 | 0.632 |
| precision (macro) | 0.311 | 0.698 |
| recall (macro) | 0.333 | 0.632 |
| F1 (macro) | 0.322 | 0.654 |
| recall: Critical | 0.0 | 0.621 |

My target: recall for Critical of at least 0.90 on unseen patients, with at most 5 false alarms per 100 Normal readings (assumption A5)
