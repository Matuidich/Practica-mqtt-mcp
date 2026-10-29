"""Tópicos derivados de un solo prefijo; ninguna función publica mensajes."""

from dataclasses import dataclass
import re

from .errors import ConfigurationError


DISTANCE_SUFFIX = "telemetry/distance"
SERVO_COMMAND_SUFFIX = "commands/servo"
SERVO_STATE_SUFFIX = "state/servo"
LED_COMMAND_SUFFIX = "commands/leds"
LED_STATE_SUFFIX = "state/leds"


@dataclass(frozen=True)
class Topics:
    prefix: str

    def __post_init__(self) -> None:
        # Convención del proyecto: ASCII, niveles no vacíos y hasta 200 caracteres.
        if (
            not isinstance(self.prefix, str)
            or len(self.prefix) > 200
            or re.fullmatch(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*", self.prefix)
            is None
            or "REEMPLAZAR" in self.prefix.upper()
        ):
            raise ConfigurationError("MQTT_TOPIC_PREFIX no es un prefijo válido.")

    @property
    def distance(self) -> str:
        return f"{self.prefix}/{DISTANCE_SUFFIX}"

    @property
    def led_command(self) -> str:
        return f"{self.prefix}/{LED_COMMAND_SUFFIX}"

    @property
    def led_state(self) -> str:
        return f"{self.prefix}/{LED_STATE_SUFFIX}"

    @property
    def servo_command(self) -> str:
        return f"{self.prefix}/{SERVO_COMMAND_SUFFIX}"

    @property
    def servo_state(self) -> str:
        return f"{self.prefix}/{SERVO_STATE_SUFFIX}"
