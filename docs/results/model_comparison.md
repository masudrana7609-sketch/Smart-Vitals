# Model comparison (09 Nov 2026)

Notebook `02_compare_models.ipynb`. Data: `sim_vitals.csv` (simulator seed 42), cleaned as the API will clean it.
Trained on 64 patients; tested once on 16 unseen patients (68,515 readings), the same ones as notebook 01.
Thresholds tuned by 5-fold cross-validation on the training patients only, to recall 0.92 for Critical.

## Unseen test patients

| Approach | recall Critical | false alarms /100 Normal | precision Critical | recall Warning | F1 (macro) | threshold | size MB | ms / reading | train s |
|---|---|---|---|---|---|---|---|---|---|
| NEWS2-inspired rule on the reading | 0.929 | 0.338 | 0.905 | 0.538 | 0.783 |  | 0.0 |  | 0.0 |
| NEWS2-inspired rule on the last-5 median | 0.964 | 0.142 | 0.957 | 0.711 | 0.88 |  | 0.0 |  | 0.0 |
| Logistic regression (single reading) | 0.966 | 76.847 | 0.066 | 0.009 | 0.168 | 0.042 | 0.0 | 0.3 | 0.7 |
| Random forest (single reading) | 0.979 | 2.602 | 0.64 | 0.486 | 0.664 | 0.217 | 11.82 | 13.23 | 3.7 |
| Gradient boosting (single reading) | 0.976 | 2.33 | 0.651 | 0.415 | 0.672 | 0.106 | 0.34 | 3.64 | 1.7 |
| Logistic regression (+ last-5 median) | 0.967 | 74.249 | 0.068 | 0.014 | 0.182 | 0.04 | 0.0 | 0.32 | 1.3 |
| Random forest (+ last-5 median) | 0.976 | 0.847 | 0.836 | 0.718 | 0.769 | 0.3 | 9.75 | 13.17 | 3.6 |
| Gradient boosting (+ last-5 median) | 0.979 | 0.659 | 0.84 | 0.628 | 0.783 | 0.153 | 0.38 | 4.25 | 2.0 |

**Chosen (on the training patients only): Gradient boosting (+ last-5 median).** Target (A5): recall for Critical ≥ 0.9, ≤ 5 false alarms per 100 Normal readings: met.

## Cross-validated on the training patients

| approach | recall Critical | false alarms /100 Normal | precision Critical | F1 (macro) |
|---|---|---|---|---|
| NEWS2-inspired rule on the reading | 0.886 | 0.575 | 0.818 | 0.786 |
| NEWS2-inspired rule on the last-5 median | 0.925 | 0.236 | 0.912 | 0.867 |
| Logistic regression (single reading) | 0.92 | 73.049 | 0.052 | 0.179 |
| Random forest (single reading) | 0.92 | 4.181 | 0.456 | 0.636 |
| Gradient boosting (single reading) | 0.92 | 2.943 | 0.526 | 0.661 |
| Logistic regression (+ last-5 median) | 0.92 | 69.41 | 0.054 | 0.193 |
| Random forest (+ last-5 median) | 0.92 | 2.189 | 0.616 | 0.721 |
| Gradient boosting (+ last-5 median) | 0.92 | 1.02 | 0.735 | 0.758 |

## Chosen model by risk_group

| risk_group | patients | Critical readings | recall Critical | false alarms /100 Normal |
|---|---|---|---|---|
| High | 6.0 | 2621.0 | 0.979 | 1.198 |
| Low | 4.0 | 18.0 | 0.944 | 0.177 |
| Medium | 6.0 | 996.0 | 0.982 | 0.493 |

## Chosen model by diabetic

| diabetic | patients | Critical readings | recall Critical | false alarms /100 Normal |
|---|---|---|---|---|
| 0 | 10.0 | 998.0 | 0.976 | 0.481 |
| 1 | 6.0 | 2637.0 | 0.981 | 0.982 |

## Chosen model by spo2_scale

| spo2_scale | patients | Critical readings | recall Critical | false alarms /100 Normal |
|---|---|---|---|---|
| 1 | 14.0 | 2898.0 | 0.98 | 0.712 |
| 2 | 2.0 | 737.0 | 0.976 | 0.274 |

## Chosen model by fault_type

| fault_type | patients | Critical readings | recall Critical | false alarms /100 Normal |
|---|---|---|---|---|
| duplicate | 16.0 | 47.0 | 0.957 | 0.466 |
| impossible | 16.0 | 17.0 | 1.0 | 1.064 |
| late | 16.0 | 33.0 | 0.97 | 0.759 |
| missing_vital | 16.0 | 66.0 | 0.985 | 0.914 |
| none | 16.0 | 3472.0 | 0.98 | 0.656 |
| stuck | 8.0 | 0.0 | 0.0 | 0.0 |

## Chosen model by episode_type

| episode_type | patients | Critical readings | recall Critical | false alarms /100 Normal |
|---|---|---|---|---|
| arrhythmia | 6.0 | 617.0 | 0.977 | 0.414 |
| hyperglycaemia | 2.0 | 121.0 | 0.983 | 1.058 |
| hypertensive_crisis | 7.0 | 454.0 | 0.934 | 0.868 |
| hypoglycaemia | 3.0 | 0.0 | 0.0 | 0.0 |
| hypoxic | 11.0 | 2192.0 | 0.99 | 10.853 |
| none | 16.0 | 0.0 | 0.0 | 0.065 |
| sepsis_like | 6.0 | 251.0 | 0.968 | 0.0 |

## What the chosen model relies on (permutation importance, drop in recall for Critical)

|  | drop |
|---|---|
| spo2_med5 | 0.432 |
| heart_rate_med5 | 0.093 |
| spo2_scale | 0.055 |
| systolic_bp_med5 | 0.042 |
| heart_rate | 0.039 |
| systolic_bp | 0.034 |
| glucose_med5 | 0.028 |
| spo2 | 0.018 |
| glucose | 0.013 |
| diastolic_bp_med5 | 0.004 |

Confusion matrix: `model_v2_confusion.png`.
