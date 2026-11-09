"""Every setting of the simulator in one place. Change these from the command line (see cli.py)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FaultRates:
    """How often each sensor or network problem happens (R9). Per-reading rates are shares of all
    expected readings; window faults are counted per patient per day."""

    missing_vital: float = 0.02  # one vital is null in the message
    impossible: float = 0.003  # one vital has a value no working sensor could give
    late: float = 0.01  # the message arrives 2-15 minutes late, out of order
    duplicate: float = 0.01  # the same msg_id is delivered twice (MQTT QoS 1)
    silent_per_day: float = 0.3  # the device sends nothing for a while
    stuck_per_day: float = 0.2  # one sensor repeats the same value
    late_minutes: tuple[float, float] = (2, 15)
    silent_minutes: tuple[int, int] = (5, 60)
    stuck_minutes: tuple[int, int] = (10, 40)


@dataclass(frozen=True)
class SimConfig:
    n_patients: int = 80
    n_clinicians: int = 3
    days: float = 3
    interval_minutes: int = 1  # one reading a minute (assumption A1)
    seed: int = 42
    start: str = "2026-01-05T00:00:00Z"  # simulated clock; UTC
    # Deterioration episodes per patient per day, by risk group (higher risk, more episodes)
    episode_rate_per_day: dict = field(default_factory=lambda: {"Low": 0.4, "Medium": 1.0, "High": 2.0})
    faults: FaultRates = field(default_factory=FaultRates)

    @property
    def n_readings(self) -> int:
        """Readings each patient's device should send."""
        return int(round(self.days * 24 * 60 / self.interval_minutes))
