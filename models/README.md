# models/

Saved models and their description files, written by the notebooks. GitHub refuses files over 100 MB and warns above 50 MB: keep big models out of the repository (add them to `.gitignore`) and say in the README how to rebuild them.

## Rebuilding the models

`first_model.joblib` is not in the repository: trained on the simulator data it is about 260 MB, over GitHub's 100 MB limit. Rebuild it in about a minute:

```bash
python -m simulator.cli batch                                  # writes data/sim_*.csv (seed 42)
jupyter nbconvert --execute --to notebook --inplace notebooks/01_first_model.ipynb
```

`first_model.json` (column names, labels, an example reading) is small and stays in the repository. Until the model is rebuilt, `tests/test_model.py` skips its two tests.

## model_v2 (the model the API uses)

`model_v2.joblib` (0.4 MB, in the repository) is the gradient boosting model chosen in `notebooks/02_compare_models.ipynb`. `model_v2.json` lists its inputs in order, its labels, its Critical threshold (0.153), the window size, and its test results. Prepare readings with `src/features.py` and load and use it with `src/model.py`:

```python
from src.model import load, predict_with_threshold
model, info = load("models/model_v2.joblib")
labels = predict_with_threshold(model, X[info["features"]], info["critical_threshold"])
```

Rebuild it by running notebook 02 (about 90 seconds) after the simulator batch.
