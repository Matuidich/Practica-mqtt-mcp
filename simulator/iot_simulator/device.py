"""Simulación LED en memoria, sin cliente MQTT, sockets ni hardware."""

from iot_shared.config import Settings
from iot_shared.errors import ValidationError
from iot_shared.leds import LedDevice
from iot_shared.messages import DistanceReading, LedCommand, LedState


class SimulatedDevice:
    def __init__(self, settings: Settings, device_id: str = "sim-01"):
        self.settings = settings
        self.leds = LedDevice(device_id)

    def handle_command(self, topic: str, payload: str | bytes, uptime_ms: int) -> LedState | None:
        if topic != self.settings.topics.led_command:
            raise ValidationError("El simulador LED solo acepta su tópico commands/leds.")
        decision = self.leds.accept(LedCommand.from_json(payload), uptime_ms)
        return self.leds.confirmation if decision in ("applied", "replay") else None

    def confirmation_sent(self) -> None:
        self.leds.confirmation_sent()

    def distance_reading(self, centimeters: float, uptime_ms: int) -> DistanceReading:
        return DistanceReading(centimeters, self.leds.device_id, uptime_ms)
