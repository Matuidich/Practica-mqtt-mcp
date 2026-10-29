"""Mensajes tipados y JSON estricto: sin clientes MQTT, sockets ni hardware."""

from dataclasses import asdict, dataclass
import json
import math
import re
from typing import Any

from .angles import ServoLimits
from .config import Settings
from .errors import ValidationError


MAX_PAYLOAD_BYTES = 1024
MAX_UPTIME_MS = 4294967295


def _identifier(value: object, field: str) -> None:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value) is None
    ):
        raise ValidationError(f"{field} debe ser un identificador ASCII de 1 a 64 caracteres.")


def _uptime(value: object) -> None:
    if type(value) is not int or not 0 <= value <= MAX_UPTIME_MS:
        raise ValidationError("uptime_ms debe ser un entero de 0 a 4294967295.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Campo JSON duplicado: {key}.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValidationError(f"Constante no permitida en JSON: {value}.")


def _decode(payload: str | bytes, fields: set[str]) -> dict[str, Any]:
    if not isinstance(payload, (str, bytes)):
        raise ValidationError("El payload debe ser texto o bytes UTF-8.")
    try:
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        if len(data) > MAX_PAYLOAD_BYTES:
            raise ValidationError(f"El payload supera {MAX_PAYLOAD_BYTES} bytes.")
        text = data.decode("utf-8")
    except UnicodeError as error:
        raise ValidationError("El payload no es UTF-8 válido.") from error
    try:
        result = json.loads(
            text, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except ValidationError:
        raise
    except (ValueError, RecursionError) as error:
        raise ValidationError("El payload no es JSON válido.") from error
    if not isinstance(result, dict):
        raise ValidationError("El mensaje debe ser un objeto JSON.")
    missing, extra = fields - result.keys(), result.keys() - fields
    if missing or extra:
        raise ValidationError(
            f"Campos faltantes: {sorted(missing)}; desconocidos: {sorted(extra)}."
        )
    return result


def _encode(message: object) -> str:
    return json.dumps(asdict(message), allow_nan=False, separators=(",", ":"))


@dataclass(frozen=True)
class DistanceReading:
    distance_cm: float
    device_id: str
    uptime_ms: int

    def __post_init__(self) -> None:
        try:
            valid = (
                type(self.distance_cm) in (int, float)
                and math.isfinite(self.distance_cm)
                and self.distance_cm > 0
            )
        except OverflowError:
            valid = False
        if not valid:
            raise ValidationError("distance_cm debe ser un número finito mayor que cero.")
        _identifier(self.device_id, "device_id")
        _uptime(self.uptime_ms)

    @classmethod
    def from_json(cls, payload: str | bytes) -> "DistanceReading":
        return cls(**_decode(payload, {"distance_cm", "device_id", "uptime_ms"}))

    def to_json(self) -> str:
        return _encode(self)


@dataclass(frozen=True)
class ServoCommand:
    angle: int
    command_id: str

    def __post_init__(self) -> None:
        ServoLimits().validate(self.angle)
        _identifier(self.command_id, "command_id")

    @classmethod
    def from_json(
        cls, payload: str | bytes, limits: ServoLimits = ServoLimits()
    ) -> "ServoCommand":
        fields = _decode(payload, {"angle", "command_id"})
        limits.validate(fields["angle"])
        return cls(**fields)

    def to_json(self, limits: ServoLimits = ServoLimits()) -> str:
        limits.validate(self.angle)
        return _encode(self)


@dataclass(frozen=True)
class ServoState:
    angle: int
    command_id: str
    device_id: str
    uptime_ms: int
    status: str = "applied"

    def __post_init__(self) -> None:
        ServoLimits().validate(self.angle)
        _identifier(self.command_id, "command_id")
        _identifier(self.device_id, "device_id")
        _uptime(self.uptime_ms)
        if self.status != "applied":
            raise ValidationError("La confirmación de estado requiere status=applied.")

    @classmethod
    def from_json(
        cls, payload: str | bytes, limits: ServoLimits = ServoLimits()
    ) -> "ServoState":
        fields = _decode(
            payload, {"angle", "command_id", "device_id", "uptime_ms", "status"}
        )
        limits.validate(fields["angle"])
        return cls(**fields)

    def to_json(self, limits: ServoLimits = ServoLimits()) -> str:
        limits.validate(self.angle)
        return _encode(self)


LED_COLORS = ("red", "yellow", "green")


@dataclass(frozen=True)
class LedValues:
    red: bool = False
    yellow: bool = False
    green: bool = False

    def __post_init__(self) -> None:
        if any(type(value) is not bool for value in asdict(self).values()):
            raise ValidationError("Los estados LED deben ser booleanos JSON.")


@dataclass(frozen=True)
class LedCommand:
    command_id: str
    red: bool | None = None
    yellow: bool | None = None
    green: bool | None = None

    def __post_init__(self) -> None:
        _identifier(self.command_id, "command_id")
        values = (self.red, self.yellow, self.green)
        if all(value is None for value in values):
            raise ValidationError("La orden debe indicar al menos un LED.")
        if any(value is not None and type(value) is not bool for value in values):
            raise ValidationError("Cada cambio LED debe ser un booleano.")

    @classmethod
    def from_json(cls, payload: str | bytes) -> "LedCommand":
        fields = _decode(payload, {"command_id", "leds"})
        changes = fields["leds"]
        if (not isinstance(changes, dict) or not changes or
                changes.keys() - set(LED_COLORS) or
                any(type(value) is not bool for value in changes.values())):
            raise ValidationError("leds requiere uno a tres colores conocidos con booleanos.")
        return cls(fields["command_id"], **changes)

    def to_json(self) -> str:
        changes = {color: getattr(self, color) for color in LED_COLORS
                   if getattr(self, color) is not None}
        return json.dumps({"command_id": self.command_id, "leds": changes}, separators=(",", ":"))

    def apply(self, previous: LedValues) -> LedValues:
        if not isinstance(previous, LedValues):
            raise ValidationError("El estado previo debe ser LedValues.")
        return LedValues(**{color: getattr(previous, color) if getattr(self, color) is None
                            else getattr(self, color) for color in LED_COLORS})


@dataclass(frozen=True)
class LedState:
    leds: LedValues
    command_id: str
    device_id: str
    uptime_ms: int
    status: str = "applied"

    def __post_init__(self) -> None:
        if not isinstance(self.leds, LedValues):
            raise ValidationError("La confirmación requiere los tres estados LED.")
        _identifier(self.command_id, "command_id")
        _identifier(self.device_id, "device_id")
        _uptime(self.uptime_ms)
        if self.status != "applied":
            raise ValidationError("La confirmación requiere status=applied.")

    @classmethod
    def from_json(cls, payload: str | bytes) -> "LedState":
        fields = _decode(payload, {"leds", "command_id", "device_id", "uptime_ms", "status"})
        values = fields["leds"]
        if not isinstance(values, dict) or set(values) != set(LED_COLORS):
            raise ValidationError("El estado debe incluir red, yellow y green.")
        return cls(**{**fields, "leds": LedValues(**values)})

    def to_json(self) -> str:
        return _encode(self)


def parse_message(
    topic: str, payload: str | bytes, settings: Settings
) -> DistanceReading | LedCommand | LedState | ServoCommand | ServoState:
    """Selecciona el esquema por tópico exacto y aplica los límites comunes."""
    topics = settings.topics
    if topic == topics.distance:
        return DistanceReading.from_json(payload)
    if topic == topics.led_command:
        return LedCommand.from_json(payload)
    if topic == topics.led_state:
        return LedState.from_json(payload)
    # Compatibilidad histórica: estos tópicos nunca se reutilizan para LEDs.
    if topic == topics.servo_command:
        return ServoCommand.from_json(payload, settings.servo_limits)
    if topic == topics.servo_state:
        return ServoState.from_json(payload, settings.servo_limits)
    raise ValidationError("El tópico no pertenece al contrato de este proyecto.")
