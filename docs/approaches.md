# Comparing approaches (Output 1, LO1)

The brief asks you to *critically evaluate at least two approaches and justify your choice against the alternatives*. Use evidence: your own measurements first, then published sources (Harvard references).

## Comparison 1: which model?

Evidence: `notebooks/02_compare_models.ipynb` and `docs/results/model_comparison.md`. Same 16 unseen patients for every approach; thresholds tuned by 5-fold cross-validation on the 64 training patients only. Cross-validated (CV) numbers are in brackets: they are the more cautious estimate.

| Criterion | Approach A: NEWS2-inspired rule on the last-5 median (no learning) | Approach B: Random forest (+ last-5 median) | Approach C: Gradient boosting (+ last-5 median) |
|---|---|---|---|
| Recall for Critical (unseen patients) | 0.964 (CV 0.925) | 0.976 (CV 0.92, tuned) | **0.979** (CV 0.92, tuned) |
| F1 (macro) | **0.880** (CV 0.867) | 0.769 (CV 0.721) | 0.783 (CV 0.758) |
| False alarms per 100 Normal readings | **0.14** (CV 0.24) | 0.85 (CV 2.19) | 0.66 (CV 1.02) |
| Can a clinician see why it decided? | Fully: the points per vital sign | Partly: permutation importance; the rule's points can be shown alongside | Partly: as B. Most of its decision rests on the SpO₂ median, then the heart-rate median and the SpO₂ scale |
| Size and speed (could it run on the edge?) | Tiny, instant: yes | 9.8 MB, about 13 ms per reading: possible on a gateway, heavy for a wearable | **0.38 MB**, about 4 ms per reading: yes, on a phone or gateway |

Also tried (see the results file): the rule on the single reading (recall 0.929), logistic regression (recall 0.97 but about 75 false alarms per 100 Normal: straight lines cannot capture "too high or too low"), and every model on the single reading only (two to three times more false alarms than with the last-5 median). Notebook 01's random forest without the SpO₂ scale reached only 0.62.

**Decision and justification:** *(notes from Claude; rewrite in your own words)*
- Choose C, chosen on the training patients only (fewest CV false alarms at the tuned recall), and it meets A5 on unseen patients: recall 0.979, 0.66 false alarms per 100 Normal.
- Two inputs mattered more than the model type: the patient's SpO₂ scale (a per-patient setting, R10) and the last-5 median, which smooths sensor noise.
- Be honest about A: the plain rule on the median is close (recall 0.964, F1 0.880, fewer false alarms). That is expected, because our labels come from the same rule applied to the true vitals. The model's advantage is a little more recall; its cost is less transparency. A defensible design keeps the rule as a safety net and an explanation beside the model.
- 92% of the model's false alarms (388 of 422) happen during a real deterioration episode, before or after the label crosses into Critical. In practice they act more like early warnings than random noise.
- Limits: 16 test patients; CV recall (0.92) is lower than test recall (0.979), so the test patients were easier than average; Low-risk patients had only 18 Critical readings in the test set; no hypoglycaemia readings were Critical in the test set.

## Comparison 2: where does the processing happen?

Evidence: `docs/results/edge_cloud.md`, `docs/results/docker_compose.md`, `tools/edge_benchmark.py`.

| Criterion | Edge (wearable or phone) | Cloud | Split (my design) |
|---|---|---|---|
| Time from a Critical reading to an alert | Fastest: no network hop. The classifier takes about 4-8 ms per reading (84 ms at the 95th percentile on a quarter of a CPU core) | Network hop plus about 8 ms processing; about 118 readings a second through broker, ingest and Postgres | As cloud. Both wait 1-3 readings for the last-5 median (A21) |
| Works when the network drops (R9) | Yes: it can alert on the phone | No alert during the outage; nothing lost with store-and-forward (0 of 1,777 lost in a 20 s outage, against 1,420 lost without it) | Edge checks and buffering; alerts once the connection returns |
| Privacy: what raw data leaves the patient | Only alerts or summaries | Every reading (245 bytes a minute) | Every reading, over an authenticated broker; TLS needed in a real deployment |
| Battery, cost and carbon | Model is tiny (0.38 MB) but Python needs about 160 MB of memory: fine for a phone or gateway, too much for a wearable without exporting the model; phone battery used | 352 KB per patient per day sent; one shared server (a few containers, about 0.5 GB of memory in total) | As cloud; the edge does only cheap checks |
| Ease of updating the model | Hard: every device must be updated, and versions drift | Easy: one container; every reading records `model_version` | Easy for the model; device checks change rarely |

**Decision and justification:** *(notes from Claude; rewrite in your own words)*
- Keep the split design: the edge (wearable and gateway) does validity checks and **store-and-forward**; the cloud runs the model, stores history and alerts.
- Speed does not decide it (milliseconds everywhere). Updating, auditing and history do: one cloud model is easy to update and audit, and the dashboard needs every reading for trends (R6, R8).
- The outage experiment shows the cloud design's real weakness: during an outage nothing is lost, but no alert can fire. The best next step is a hybrid: the phone or gateway runs model v2 (it fits) only while offline, and the cloud stays the source of truth.
- Sending everything costs 352 KB per patient per day; an alerts-and-summaries edge design would send 92% less but lose minute-level trends and retraining data. For 30 patients that is about 10 MB a day, which is affordable, so trends win.
