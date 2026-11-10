"""Settings, read from environment variables or the .env file (see .env.example). No secrets in code."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/smartvitals.db"
    model_path: str = "models/model_v2.joblib"

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic: str = "smartvitals/readings"  # devices publish to <topic>/<device_id>
    mqtt_username: str = ""
    mqtt_password: str = ""

    # Alerts (ADR 5, A6) and R9 handling. Times are in simulated minutes when clock = "feed".
    alert_reminder_minutes: float = 15
    escalation_settle_minutes: float = 5  # worse readings this soon after an alert update it quietly
    late_after_minutes: float = 2  # a reading arriving later than this is flagged "late"
    late_alert_max_minutes: float = 30  # a reading older than this on arrival is stored but raises no new alert
    stuck_readings: int = 10  # this many identical values in a row: the sensor is treated as stuck
    rule_safety_net: bool = True  # the NEWS2-inspired rule on the last-5 median can also call Critical

    # "feed": the simulator's clock (sent_at in each message) drives lateness and reminders (A20).
    # "wall": the server's own clock, for real devices.
    clock: Literal["feed", "wall"] = "feed"


@lru_cache
def get_settings() -> Settings:
    return Settings()
