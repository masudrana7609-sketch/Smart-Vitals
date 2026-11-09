"""Command line for the simulator.

    python -m simulator.cli batch                      # 80 patients x 3 days, seed 42, into data/
    python -m simulator.cli batch --patients 10 --days 1 --seed 7 --out /tmp/sim
    python -m simulator.cli live                       # Sprint 2: publish readings over MQTT
    python -m simulator.cli scenario                   # Sprint 2: scripted demo cases (T3, T7-T11)

batch writes three files:
- sim_patients.csv      one row per patient (conditions, history, risk group, clinician, baselines)
- sim_vitals.csv        the delivered feed, in order of arrival, plus the training label `status`
- sim_ground_truth.csv  one row per expected reading: true vitals, severity, episode, fault, delay
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from simulator.config import FaultRates, SimConfig
from simulator.faults import apply_faults
from simulator.patients import generate_patients
from simulator.physiology import simulate_patient
from src.vitals import VITALS

VITALS_COLUMNS = [
    "msg_id",
    "device_id",
    "patient_id",
    "measured_at",
    "received_at",
    "risk_level",
    "diabetic",
    *VITALS,
    "status",
]
TRUTH_COLUMNS = [
    "msg_id",
    "patient_id",
    "clinician_id",
    "measured_at",
    "risk_group",
    "spo2_scale",
    *[f"true_{v}" for v in VITALS],
    "severity",
    "episode_type",
    "news_score",
    "status",
    "fault_type",
    "fault_vital",
    "delay_minutes",
    "copies",
    "delivered",
]


def _timestamps(start, minutes):
    return pd.Timestamp(start) + pd.to_timedelta(minutes, unit="m")


def run_batch(cfg: SimConfig):
    """Simulate every patient and return (patients, delivered feed, ground truth) as DataFrames."""
    rng = np.random.default_rng(cfg.seed)
    patients = generate_patients(cfg, rng)
    frames = [simulate_patient(p, cfg, rng) for _, p in patients.iterrows()]
    readings = pd.concat(frames, ignore_index=True)
    readings = apply_faults(readings, patients, cfg.faults, cfg.days, cfg.interval_minutes, rng)

    info = patients.set_index("patient_id")
    readings["msg_id"] = readings["patient_id"] + "-" + readings["minute"].astype(str).str.zfill(6)
    readings["device_id"] = readings["patient_id"].map(info["device_id"])
    readings["clinician_id"] = readings["patient_id"].map(info["clinician_id"])
    readings["risk_group"] = readings["patient_id"].map(info["risk_group"])
    readings["risk_level"] = readings["patient_id"].map(info["risk_level"])
    readings["diabetic"] = readings["patient_id"].map(info["diabetes"])
    readings["spo2_scale"] = readings["patient_id"].map(info["spo2_scale"])
    measured = _timestamps(cfg.start, readings["minute"])
    network = pd.to_timedelta(rng.uniform(0.2, 2.0, len(readings)), unit="s")  # normal network latency
    received = measured + network + pd.to_timedelta(readings["delay_minutes"], unit="m")
    readings["measured_at"] = measured.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    readings["received_ts"] = received

    sent = readings[readings["copies"] > 0]
    extra = sent[sent["copies"] == 2].copy()  # the second copy of a duplicated message arrives a little later
    extra["received_ts"] = extra["received_ts"] + pd.to_timedelta(rng.uniform(1, 30, len(extra)), unit="s")
    delivered = pd.concat([sent, extra]).sort_values(["received_ts", "msg_id"], kind="stable")
    delivered["received_at"] = delivered["received_ts"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ").str[:-4] + "Z"
    delivered = delivered[VITALS_COLUMNS].reset_index(drop=True)
    truth = readings[TRUTH_COLUMNS].reset_index(drop=True)
    return patients, delivered, truth


def summary(patients, delivered, truth) -> str:
    expected = len(truth)
    lines = [
        f"patients: {len(patients)} | clinicians: {patients['clinician_id'].nunique()}",
        "risk groups: " + ", ".join(f"{k} {v}" for k, v in patients["risk_group"].value_counts().items()),
        f"expected readings: {expected} | delivered messages: {len(delivered)}",
        "labels (expected readings): "
        + ", ".join(f"{k} {v / expected:.1%}" for k, v in truth["status"].value_counts().items()),
        "faults (share of expected readings): "
        + ", ".join(f"{k} {v / expected:.2%}" for k, v in truth["fault_type"].value_counts().items() if k != "none"),
    ]
    return "\n".join(lines)


def cmd_batch(args) -> int:
    cfg = SimConfig(
        n_patients=args.patients,
        n_clinicians=args.clinicians,
        days=args.days,
        seed=args.seed,
        start=args.start,
        faults=FaultRates(),
    )
    patients, delivered, truth = run_batch(cfg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    patients.to_csv(out / "sim_patients.csv", index=False)
    delivered.to_csv(out / "sim_vitals.csv", index=False)
    truth.to_csv(out / "sim_ground_truth.csv", index=False)
    print(summary(patients, delivered, truth))
    print(f"written: {out / 'sim_patients.csv'}, {out / 'sim_vitals.csv'}, {out / 'sim_ground_truth.csv'}")
    return 0


def cmd_not_yet(args) -> int:
    print(f"'{args.mode}' mode is built in Sprint 2 (MQTT feed and demo scenarios).", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m simulator.cli", description="Smart Vitals sensor simulator")
    modes = parser.add_subparsers(dest="mode", required=True)
    batch = modes.add_parser("batch", help="write a training dataset to CSV files")
    batch.add_argument("--patients", type=int, default=80)
    batch.add_argument("--clinicians", type=int, default=3)
    batch.add_argument("--days", type=float, default=3)
    batch.add_argument("--seed", type=int, default=42)
    batch.add_argument("--start", default="2026-01-05T00:00:00Z", help="simulated start time (UTC)")
    batch.add_argument("--out", default="data", help="folder for the CSV files")
    batch.set_defaults(func=cmd_batch)
    for mode in ("live", "scenario"):
        modes.add_parser(mode, help="Sprint 2").set_defaults(func=cmd_not_yet)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
