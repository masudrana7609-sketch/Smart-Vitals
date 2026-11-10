"""Load simulated patients and their clinicians into the database.

python -m simulator.cli patients --patients 30 --seed 7 --out data/demo
python -m app.seed data/demo/sim_patients.csv
"""

import argparse
import sys

import pandas as pd

from app.config import get_settings
from app.db import init_db, make_engine, make_session_factory
from app.tables import Clinician, Patient


def seed(session, patients: pd.DataFrame) -> int:
    for clinician_id in sorted(patients["clinician_id"].unique()):
        session.merge(Clinician(id=clinician_id, name=f"Clinician {clinician_id}"))
    for p in patients.to_dict("records"):
        session.merge(
            Patient(
                id=p["patient_id"],
                device_id=p["device_id"],
                clinician_id=p["clinician_id"],
                age_band=p["age_band"],
                hypertension=bool(p["hypertension"]),
                diabetes=bool(p["diabetes"]),
                arrhythmia=bool(p["arrhythmia"]),
                copd=bool(p["copd"]),
                admissions_12m=int(p["admissions_12m"]),
                prior_critical_event=bool(p["prior_critical_event"]),
                risk_group=p["risk_group"],
                risk_level=int(p["risk_level"]),
                spo2_scale=int(p["spo2_scale"]),
            )
        )
    session.commit()
    return len(patients)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__)
    parser.add_argument("patients_csv")
    args = parser.parse_args(argv)
    engine = make_engine(get_settings().database_url)
    init_db(engine)
    with make_session_factory(engine)() as session:
        count = seed(session, pd.read_csv(args.patients_csv))
    print(f"seeded {count} patients")
    return 0


if __name__ == "__main__":
    sys.exit(main())
