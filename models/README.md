# models/

Saved models and their description files, written by the notebooks. GitHub refuses files over 100 MB and warns above 50 MB: keep big models out of the repository (add them to `.gitignore`) and say in the README how to rebuild them.

## Rebuilding the models

`first_model.joblib` is not in the repository: trained on the simulator data it is about 260 MB, over GitHub's 100 MB limit. Rebuild it in about a minute:

```bash
python -m simulator.cli batch                                  # writes data/sim_*.csv (seed 42)
jupyter nbconvert --execute --to notebook --inplace notebooks/01_first_model.ipynb
```

`first_model.json` (column names, labels, an example reading) is small and stays in the repository. Until the model is rebuilt, `tests/test_model.py` skips its two tests.
