# simulator/ (R2, R9)

Your IoT-style sensor feed. Real hardware is not required: the brief allows readings to be simulated in software.

Start from your Week 4 and Week 6 code:
- one stream per patient, for example one reading a minute, with the five vital signs (glucose only for patients with diabetes) and each patient's risk group (R1)
- problems built in on purpose, so you can test R9: dropouts, delayed readings, impossible values and duplicate messages
- send readings to your API (Week 8), or publish them over MQTT (Week 6)

Record how it works, and its limits, in `data/DATA_CARD.md`.

## How to run it (Sprint 1)

```bash
python -m simulator.cli batch                  # 80 patients x 3 days, seed 42 -> data/sim_*.csv (about 3 s)
python -m simulator.cli batch --help           # patients, clinicians, days, seed, start time, output folder
python -m simulator.cli live                   # Sprint 2
python -m simulator.cli scenario               # Sprint 2
```

| File | What it does |
|---|---|
| `config.py` | Every setting: patients, days, seed, episode rates, fault rates |
| `patients.py` | Synthetic patients, risk groups (`src/risk.py`), clinicians, personal baselines |
| `physiology.py` | Hidden severity, deterioration episodes, true and observed vitals, labels (`src/labelling.py`) |
| `faults.py` | Missing vitals, silent devices, late messages, impossible values, stuck sensors, duplicates |
| `cli.py` | The command line; `run_batch()` is also used by the tests |

Details and the numbers from a real run: `data/DATA_CARD.md`. Tests: `tests/test_simulator.py`.
