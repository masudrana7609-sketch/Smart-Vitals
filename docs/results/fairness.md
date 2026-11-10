# Fairness check (10 Nov 2026)

Notebook `03_fairness.ipynb`. Nested 5-fold cross-validation over all 80 simulated patients (seed 42): every patient is tested once while unseen; thresholds tuned inside each fold's training patients only (thresholds 0.165, 0.327, 0.158, 0.266, 0.157). Scored: the deployed decision (model v2 recipe + rule safety net). Intervals: 95%, from resampling patients.

| group | value | patients | Critical readings | recall Critical (95% CI) | false alarms /100 Normal (95% CI) | episodes found |
|---|---|---|---|---|---|---|
| everyone | all | 80 | 15055 | 0.970 (0.955-0.981) | 0.88 (0.60-1.20) | 186 of 201 |
| risk group | High | 16 | 6139 | 0.982 (0.969-0.990) | 1.65 (1.04-2.33) | 55 of 55 |
| risk group | Low | 36 | 3956 | 0.947 (0.908-0.977) | 0.86 (0.39-1.43) | 93 of 103 |
| risk group | Medium | 28 | 4960 | 0.972 (0.952-0.986) | 0.50 (0.24-0.81) | 38 of 43 |
| diabetes | 0 | 60 | 10407 | 0.974 (0.962-0.984) | 0.86 (0.52-1.27) | 123 of 135 |
| diabetes | 1 | 20 | 4648 | 0.959 (0.918-0.984) | 0.94 (0.56-1.36) | 63 of 66 |
| SpO₂ scale | 1 | 73 | 13781 | 0.969 (0.954-0.981) | 0.90 (0.59-1.24) | 173 of 188 |
| SpO₂ scale | 2 | 7 | 1274 | 0.974 (0.911-0.994) | 0.72 (0.23-1.27) | 13 of 13 |
| age band | 18-49 | 25 | 3164 | 0.937 (0.893-0.976) | 0.56 (0.24-0.94) | 64 of 71 |
| age band | 50-64 | 20 | 3068 | 0.970 (0.947-0.991) | 1.31 (0.58-2.31) | 53 of 56 |
| age band | 65-79 | 21 | 3847 | 0.982 (0.965-0.990) | 0.54 (0.27-0.90) | 30 of 35 |
| age band | 80+ | 14 | 4976 | 0.980 (0.962-0.990) | 1.37 (0.67-2.15) | 39 of 39 |
| hypertension | 0 | 57 | 11332 | 0.966 (0.948-0.980) | 0.87 (0.54-1.26) | 147 of 159 |
| hypertension | 1 | 23 | 3723 | 0.980 (0.963-0.989) | 0.91 (0.47-1.47) | 39 of 42 |
| arrhythmia | 0 | 74 | 13163 | 0.968 (0.952-0.980) | 0.76 (0.50-1.04) | 161 of 175 |
| arrhythmia | 1 | 6 | 1892 | 0.978 (0.948-0.998) | 2.52 (1.25-3.75) | 25 of 26 |
| COPD-like | 0 | 69 | 10767 | 0.965 (0.946-0.980) | 0.86 (0.56-1.22) | 153 of 168 |
| COPD-like | 1 | 11 | 4288 | 0.980 (0.960-0.991) | 1.06 (0.50-1.79) | 33 of 33 |

## Episodes by type

| kind | episodes | found | median_minutes | share found |
|---|---|---|---|---|
| arrhythmia | 34 | 29 | 16.5 | 0.853 |
| hyperglycaemia | 4 | 4 | 73.0 | 1.0 |
| hypertensive_crisis | 12 | 12 | 83.5 | 1.0 |
| hypoglycaemia | 8 | 8 | 13.5 | 1.0 |
| hypoxic | 54 | 53 | 110.5 | 0.981 |
| none | 59 | 52 | 6.0 | 0.881 |
| sepsis_like | 30 | 28 | 93.5 | 0.933 |

Figure: `fairness_recall.png`.
