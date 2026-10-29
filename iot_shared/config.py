"""Fuente única de configuración local, con lectura explícita y sin red.

El .env utiliza deliberadamente KEY=VALUE sin comillas ni expansión de variables.
No se consultan variables del proceso: las exportaciones y los clientes leen
exactamente el mismo archivo, sin sobrescrituras ambientales invisibles.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
from typing import Mapping
from uuid import UUID

from .angles import ServoLimits
from .errors import ConfigurationError, ValidationError
from .topics import Topics


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
ENV_KEYS = frozenset(
    {
        "PROJECT_UUID", "MQTT_HOST", "MQTT_PORT", "MQTT_KEEPALIVE_S",
        "MQTT_TOPIC_PREFIX", "MQTT_RECONNECT_MIN_DELAY_S",
        "MQTT_RECONNECT_MAX_DELAY_S", "DISTANCE_PUBLISH_INTERVAL_MS",
        "DISTANCE_STALE_AFTER_S", "SERVO_MIN_ANGLE", "SERVO_MAX_ANGLE",
    }
)


class ClientRole(str, Enum):
    MCP = "mcp"
    SIMULATOR = "simulator"
    FIRMWARE = "firmware"
    MOBILE = "mobile"
    SENSOR = "sensor"
    ACTUATOR = "actuator"


CLIENT_SUFFIXES = {
    ClientRole.MCP: "mcp",
    ClientRole.SIMULATOR: "sim",
    ClientRole.FIRMWARE: "esp32",
    ClientRole.MOBILE: "movil",
    ClientRole.SENSOR: "sensor",
    ClientRole.ACTUATOR: "actuator",
}


def parse_env(text: str) -> dict[str, str]:
    """Lee el formato reducido documentado y detecta claves duplicadas."""
    values: dict[str, str] = {}
    for number, raw_line in enumerate(text.removeprefix("\ufeff").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if (
            not separator
            or re.fullmatch(r"[A-Z][A-Z0-9_]*", key) is None
            or any(character in value for character in "\"'#$\x00")
        ):
            raise ConfigurationError(f"Formato KEY=VALUE inválido en línea {number}.")
        if key in values:
            raise ConfigurationError(f"Clave duplicada en .env: {key}.")
        values[key] = value
    return values


def _integer(values: Mapping[str, str], key: str) -> int:
    raw = values[key]
    if not isinstance(raw, str) or re.fullmatch(r"-?[0-9]{1,10}", raw) is None:
        raise ConfigurationError(f"{key} debe contener un entero.")
    return int(raw)


@dataclass(frozen=True)
class Settings:
    project_uuid: UUID
    mqtt_host: str
    mqtt_port: int
    topic_prefix: str
    keepalive_s: int
    reconnect_min_delay_s: int
    reconnect_max_delay_s: int
    distance_publish_interval_ms: int
    distance_stale_after_s: int
    servo_limits: ServoLimits  # Compatibilidad con .env y referencia histórica; no controla LEDs.

    def __post_init__(self) -> None:
        if not isinstance(self.project_uuid, UUID) or self.project_uuid.version != 4:
            raise ConfigurationError("PROJECT_UUID debe ser un UUID v4.")
        if (
            not isinstance(self.mqtt_host, str)
            or len(self.mqtt_host) > 253
            or re.fullmatch(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*", self.mqtt_host)
            is None
        ):
            raise ConfigurationError("MQTT_HOST debe ser un nombre de host o IPv4.")
        Topics(self.topic_prefix)
        if self.topic_prefix.split("/")[-1] != str(self.project_uuid):
            raise ConfigurationError("El último nivel del prefijo debe ser PROJECT_UUID.")
        ranges = {
            "MQTT_PORT": (self.mqtt_port, 65535),
            "MQTT_KEEPALIVE_S": (self.keepalive_s, 65535),
            # Los segundos exportados como milisegundos deben caber en uint32.
            "MQTT_RECONNECT_MIN_DELAY_S": (self.reconnect_min_delay_s, 4294967),
            "MQTT_RECONNECT_MAX_DELAY_S": (self.reconnect_max_delay_s, 4294967),
            "DISTANCE_PUBLISH_INTERVAL_MS": (self.distance_publish_interval_ms, 4294967295),
            "DISTANCE_STALE_AFTER_S": (self.distance_stale_after_s, 4294967),
        }
        for name, (value, maximum) in ranges.items():
            if type(value) is not int or not 1 <= value <= maximum:
                raise ConfigurationError(f"{name} debe estar entre 1 y {maximum}.")
        if self.reconnect_min_delay_s > self.reconnect_max_delay_s:
            raise ConfigurationError("La espera mínima no puede superar la máxima.")
        if not isinstance(self.servo_limits, ServoLimits):
            raise ConfigurationError("Los límites del servo deben ser ServoLimits.")

    @property
    def topics(self) -> Topics:
        return Topics(self.topic_prefix)

    def client_id(self, role: ClientRole | str) -> str:
        """Deriva identidades diferentes sin repetirlas manualmente en el .env."""
        try:
            suffix = CLIENT_SUFFIXES[ClientRole(role)]
        except (ValueError, TypeError) as error:
            raise ConfigurationError("Rol de cliente MQTT desconocido.") from error
        return f"sis234-{self.project_uuid.hex}-{suffix}"

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> "Settings":
        missing, extra = ENV_KEYS - values.keys(), values.keys() - ENV_KEYS
        if missing or extra:
            raise ConfigurationError(
                f"Claves .env faltantes: {sorted(missing)}; desconocidas: {sorted(extra)}."
            )
        try:
            project_uuid = UUID(values["PROJECT_UUID"])
            if str(project_uuid) != values["PROJECT_UUID"]:
                raise ValueError("UUID no canónico")
        except (ValueError, TypeError, AttributeError) as error:
            raise ConfigurationError("PROJECT_UUID debe ser un UUID v4 canónico.") from error
        try:
            limits = ServoLimits(
                _integer(values, "SERVO_MIN_ANGLE"),
                _integer(values, "SERVO_MAX_ANGLE"),
            )
        except ValidationError as error:
            raise ConfigurationError(str(error)) from error
        return cls(
            project_uuid=project_uuid,
            mqtt_host=values["MQTT_HOST"],
            mqtt_port=_integer(values, "MQTT_PORT"),
            topic_prefix=values["MQTT_TOPIC_PREFIX"],
            keepalive_s=_integer(values, "MQTT_KEEPALIVE_S"),
            reconnect_min_delay_s=_integer(values, "MQTT_RECONNECT_MIN_DELAY_S"),
            reconnect_max_delay_s=_integer(values, "MQTT_RECONNECT_MAX_DELAY_S"),
            distance_publish_interval_ms=_integer(values, "DISTANCE_PUBLISH_INTERVAL_MS"),
            distance_stale_after_s=_integer(values, "DISTANCE_STALE_AFTER_S"),
            servo_limits=limits,
        )

    @classmethod
    def from_text(cls, text: str) -> "Settings":
        return cls.from_mapping(parse_env(text))

    @classmethod
    def load(cls, env_file: Path | str = DEFAULT_ENV_FILE) -> "Settings":
        try:
            text = Path(env_file).read_text(encoding="utf-8-sig")
        except FileNotFoundError as error:
            raise ConfigurationError(
                "Falta .env; ejecutar python -m iot_shared init desde la raíz."
            ) from error
        except UnicodeError as error:
            raise ConfigurationError("El .env debe estar codificado en UTF-8.") from error
        return cls.from_text(text)
