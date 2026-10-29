"""Últimas observaciones del dispositivo, independientes del transporte MQTT."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Generic, TypeVar

from iot_shared.messages import DistanceReading, LedState


Message = TypeVar("Message", DistanceReading, LedState)


@dataclass
class Observation(Generic[Message]):
    message: Message
    monotonic_s: float
    received_at: str
    current_connection: bool = True

    def snapshot(self, now: float) -> dict:
        return {
            "message": json.loads(self.message.to_json()),
            "age_s": round(max(0.0, now - self.monotonic_s), 3),
            "received_at": self.received_at,
            "current_connection": self.current_connection,
        }


class DeviceState:
    """El gateway protege todas las llamadas con su Condition compartida."""

    def __init__(self) -> None:
        self.distance: Observation[DistanceReading] | None = None
        self.leds: Observation[LedState] | None = None

    def receive(self, message: DistanceReading | LedState, now: float) -> None:
        observed = Observation(message, now, datetime.now(timezone.utc).isoformat())
        if isinstance(message, DistanceReading):
            self.distance = observed
        else:
            self.leds = observed

    def disconnected(self) -> None:
        for observed in (self.distance, self.leds):
            if observed is not None:
                observed.current_connection = False

    def distance_snapshot(self, now: float, stale_after_s: float) -> dict:
        if self.distance is None:
            return {"status": "unknown", "reading": None, "age_s": None}
        snapshot = self.distance.snapshot(now)
        stale = (not self.distance.current_connection or
                 now - self.distance.monotonic_s >= stale_after_s)
        return {"status": "stale" if stale else "fresh",
                "reading": snapshot.pop("message"), **snapshot}

    def leds_snapshot(self, now: float) -> dict:
        if self.leds is None:
            return {"status": "unknown", "state": None, "age_s": None}
        snapshot = self.leds.snapshot(now)
        return {"status": "observed" if self.leds.current_connection else "stale",
                "state": snapshot.pop("message"), **snapshot}
