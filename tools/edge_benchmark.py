"""Could the classifier run at the edge (a phone or home gateway)? Output 1, Comparison 2.

Measures, for the full per-reading decision (last-5 median + model v2 + rule, app/classifier.py):
- time to load the model, and the process's peak memory
- time per reading (median and 95th percentile) over 1,000 readings
- the size of one reading message, and the data per patient per day

    python tools/edge_benchmark.py
    # a constrained "gateway": a quarter of one CPU core and 256 MB of memory
    docker run --rm --cpus 0.25 --memory 256m -v "$PWD/tools:/srv/tools:ro" smartvitals-python:0.4 \
        python tools/edge_benchmark.py
"""

import json
import resource
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.classifier import Classifier  # noqa: E402
from simulator.cli import run_batch  # noqa: E402
from simulator.config import SimConfig  # noqa: E402
from simulator.live import payloads  # noqa: E402
from src.vitals import VITALS  # noqa: E402


def peak_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1e6 if sys.platform == "darwin" else peak / 1e3  # bytes on macOS, KB on Linux


def main() -> None:
    start = time.perf_counter()
    classifier = Classifier("models/model_v2.joblib")
    load_s = time.perf_counter() - start

    patients, delivered, _ = run_batch(SimConfig(n_patients=3, days=0.25, seed=3))
    messages = list(payloads(delivered))
    patient = SimpleNamespace(**patients.iloc[0].to_dict())
    patient.diabetes = bool(patient.diabetes)
    rows = [{v: m.get(v) for v in VITALS} for m in messages if m["patient_id"] == patient.patient_id][:1000]

    times = []
    for i, row in enumerate(rows):
        previous = rows[max(0, i - 4) : i][::-1]
        t = time.perf_counter()
        classifier.classify(patient, row, previous)
        times.append(time.perf_counter() - t)

    sizes = [len(json.dumps(m).encode()) for m in messages]
    result = {
        "model file MB": round(Path("models/model_v2.joblib").stat().st_size / 1e6, 2),
        "load seconds": round(load_s, 2),
        "peak memory MB": round(peak_mb(), 1),
        "readings timed": len(times),
        "ms per reading (median)": round(1000 * float(np.median(times)), 2),
        "ms per reading (95th percentile)": round(1000 * float(np.percentile(times, 95)), 2),
        "bytes per message (mean)": round(float(np.mean(sizes))),
        "KB per patient per day (1 reading a minute)": round(float(np.mean(sizes)) * 1440 / 1000, 1),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
