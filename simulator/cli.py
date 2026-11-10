"""Command line for the simulator.

    python -m simulator.cli batch                      # 80 patients x 3 days, seed 42, into data/
    python -m simulator.cli batch --patients 10 --days 1 --seed 7 --out /tmp/sim
    python -m simulator.cli patients                   # the live demo's 30 patients -> data/demo/
    python -m simulator.cli live --transport http      # stream them to the API (or --transport mqtt)
    python -m simulator.cli scenario --patient P001    # scripted story: T3, T7-T10

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


def _config(args) -> SimConfig:
    faults = FaultRates() if getattr(args, "faults", True) else FaultRates(0, 0, 0, 0, 0, 0)
    return SimConfig(
        n_patients=args.patients,
        n_clinicians=args.clinicians,
        days=args.days,
        seed=args.seed,
        start=args.start,
        faults=faults,
    )


def cmd_patients(args) -> int:
    from simulator.patients import generate_patients

    cfg = _config(args)
    patients = generate_patients(cfg, np.random.default_rng(cfg.seed))  # same patients as batch and live
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    patients.to_csv(out / "sim_patients.csv", index=False)
    print(f"written: {out / 'sim_patients.csv'} ({len(patients)} patients). Load them with:")
    print(f"  python -m app.seed {out / 'sim_patients.csv'}")
    return 0


def _sender(args):
    from simulator.live import HttpSender, MqttSender

    if args.transport == "mqtt":
        return MqttSender(args.mqtt_host, args.mqtt_port, args.topic)
    return HttpSender(args.api_url)


def cmd_live(args) -> int:
    from simulator.live import payloads, stream

    _, delivered, _ = run_batch(_config(args))
    print(f"streaming {len(delivered)} messages over {args.transport} at {args.speedup}x (Ctrl+C to stop)")
    try:
        results = stream(payloads(delivered), _sender(args), args.speedup, limit=args.limit)
    except KeyboardInterrupt:
        print("stopped")
        return 0
    print("results:", dict(results))
    return 0


def cmd_scenario(args) -> int:
    from simulator import scenario
    from simulator.live import stream

    patients = pd.read_csv(args.patients_csv).set_index("patient_id", drop=False)
    if args.patient not in patients.index:
        print(f"unknown patient {args.patient}", file=sys.stderr)
        return 2
    messages = scenario.build(patients.loc[args.patient].to_dict(), args.start)
    print(scenario.__doc__)
    results = stream(messages, _sender(args), args.speedup)
    print("results:", dict(results))
    return 0


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

    def population(p, patients, days):
        p.add_argument("--patients", type=int, default=patients)
        p.add_argument("--clinicians", type=int, default=3)
        p.add_argument("--days", type=float, default=days)
        p.add_argument("--seed", type=int, default=3)  # 30 patients incl. one SpO2 Scale 2
        p.add_argument("--start", default="2026-01-05T00:00:00Z", help="simulated start time (UTC)")

    def transport(p):
        p.add_argument("--transport", choices=["mqtt", "http"], default="mqtt")
        p.add_argument("--api-url", default="http://localhost:8000")
        p.add_argument("--mqtt-host", default="localhost")
        p.add_argument("--mqtt-port", type=int, default=1883)
        p.add_argument("--topic", default="smartvitals/readings")
        p.add_argument("--speedup", type=float, default=60, help="60: one simulated minute per second; 0: no waiting")

    pats = modes.add_parser("patients", help="write the live demo's patients, to load with app.seed")
    population(pats, 30, 1)
    pats.add_argument("--out", default="data/demo")
    pats.set_defaults(func=cmd_patients)

    live = modes.add_parser("live", help="stream readings to the system over MQTT or HTTP")
    population(live, 30, 1)
    transport(live)
    live.add_argument("--no-faults", dest="faults", action="store_false", help="turn off the built-in faults")
    live.add_argument("--limit", type=int, default=None, help="stop after this many messages")
    live.set_defaults(func=cmd_live)

    scen = modes.add_parser("scenario", help="scripted story for one patient: T3, T7-T10")
    scen.add_argument("--patients-csv", default="data/demo/sim_patients.csv")
    scen.add_argument("--patient", default="P001")
    scen.add_argument("--start", default="2026-01-06T00:00:00Z", help="after the live feed's last reading")
    transport(scen)
    scen.set_defaults(func=cmd_scenario)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
