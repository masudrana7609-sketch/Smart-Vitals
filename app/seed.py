"""Load simulated patients, their clinicians and an admin into the database.

    python -m simulator.cli patients --out data/demo
    python -m app.seed data/demo/sim_patients.csv

Clinician logins are their IDs (C01, C02, ...); the admin's is "admin". Passwords come from
DEMO_CLINICIAN_PASSWORD and DEMO_ADMIN_PASSWORD in .env (at least 12 characters) and are stored only as
argon2 hashes. Every person here is invented.
"""

import argparse
import sys

import pandas as pd

from app.auth import hash_password
from app.config import get_settings
from app.db import init_db, make_engine, make_session_factory
from app.tables import Clinician, Patient


def seed(session, patients: pd.DataFrame, password: str | None = None, admin_password: str | None = None) -> int:
    """Add or update the clinicians, the admin and the patients. Without passwords nobody can log in."""
    for clinician_id in sorted(patients["clinician_id"].unique()):
        existing = session.get(Clinician, clinician_id)
        clinician = existing or Clinician(id=clinician_id, name=f"Clinician {clinician_id}", role="clinician")
        if password:
            clinician.password_hash = hash_password(password)
        session.add(clinician)
    if admin_password:
        admin = session.get(Clinician, "admin") or Clinician(id="admin", name="Administrator", role="admin")
        admin.password_hash = hash_password(admin_password)
        session.add(admin)
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
    parser = argparse.ArgumentParser(
        prog="python -m app.seed", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("patients_csv")
    args = parser.parse_args(argv)
    settings = get_settings()
    if not settings.demo_clinician_password or not settings.demo_admin_password:
        print("Set DEMO_CLINICIAN_PASSWORD and DEMO_ADMIN_PASSWORD in .env first (12+ characters).", file=sys.stderr)
        return 2
    engine = make_engine(settings.database_url)
    init_db(engine)
    with make_session_factory(engine)() as session:
        count = seed(
            session, pd.read_csv(args.patients_csv), settings.demo_clinician_password, settings.demo_admin_password
        )
    print(f"seeded {count} patients, their clinicians and the admin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
