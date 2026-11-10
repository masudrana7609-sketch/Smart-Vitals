"""Deleting old records (R7, A7: storage limitation under UK GDPR).

- readings older than READINGS_RETENTION_DAYS (30): enough for trends, not kept for ever
- alerts and their notifications older than ALERTS_RETENTION_DAYS (365); an alert keeps its own copy of the
  vitals, so deleting the reading behind it does not lose what the clinician was told
- audit events older than AUDIT_RETENTION_DAYS (365)

Each run is itself recorded in the audit log. "Now" follows the same clock as the rest of the system (A20).

    python -m app.retention              # once
    python -m app.retention --every 3600 # every hour (the Docker service does this)
"""

import argparse
import logging
import sys
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update

from app import audit
from app.config import get_settings
from app.db import init_db, make_engine, make_session_factory
from app.tables import Alert, AuditEvent, Notification, Reading

log = logging.getLogger("smartvitals.retention")


def _now(session, clock: str) -> datetime:
    if clock == "feed":
        latest = session.scalar(select(func.max(Reading.received_at)))
        if latest is not None:
            return latest
    return datetime.now(UTC).replace(tzinfo=None)


def purge(session, settings) -> dict:
    """Delete records past their retention period. Returns how many of each were deleted."""
    now = _now(session, settings.clock)
    wall = datetime.now(UTC).replace(tzinfo=None)  # the audit log uses the server's real clock
    readings_before = now - timedelta(days=settings.readings_retention_days)
    alerts_before = now - timedelta(days=settings.alerts_retention_days)
    audit_before = wall - timedelta(days=settings.audit_retention_days)

    old_alerts = select(Alert.id).where(Alert.raised_at < alerts_before)
    counts = {
        "notifications": session.execute(delete(Notification).where(Notification.alert_id.in_(old_alerts))).rowcount
    }
    counts["alerts"] = session.execute(delete(Alert).where(Alert.raised_at < alerts_before)).rowcount
    old_readings = select(Reading.id).where(Reading.measured_at < readings_before)
    session.execute(update(Alert).where(Alert.reading_id.in_(old_readings)).values(reading_id=None))
    counts["readings"] = session.execute(delete(Reading).where(Reading.measured_at < readings_before)).rowcount
    counts["audit_events"] = session.execute(delete(AuditEvent).where(AuditEvent.at < audit_before)).rowcount
    audit.record(session, "system", "retention.purge", detail=", ".join(f"{k} {v}" for k, v in counts.items()))
    session.commit()
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.retention", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--every", type=float, default=0, help="repeat every N seconds (0: run once)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    sessions = make_session_factory(engine)
    while True:
        with sessions() as session:
            log.info("deleted %s", purge(session, settings))
        if args.every <= 0:
            return 0
        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
