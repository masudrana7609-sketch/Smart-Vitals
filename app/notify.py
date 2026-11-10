"""Sending alert messages to clinicians. The prototype logs them and keeps them in the database; a real
deployment would page or message the clinician (and must not put patient data in an insecure channel)."""

import logging

log = logging.getLogger("smartvitals.notify")


class LogNotifier:
    def send(self, notification) -> None:
        log.warning("ALERT to %s: %s", notification.clinician_id, notification.message)


class ListNotifier:
    """Collects messages in a list: used by the tests and handy in a demo."""

    def __init__(self):
        self.sent = []

    def send(self, notification) -> None:
        self.sent.append(notification)
