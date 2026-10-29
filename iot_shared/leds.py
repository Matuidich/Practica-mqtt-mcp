"""Modelo LED compartido por simulador y futuras herramientas, sin transporte."""

from .errors import ValidationError
from .messages import LED_COLORS, LedCommand, LedState, LedValues


def only_led(color: str, command_id: str) -> LedCommand:
    if color not in LED_COLORS:
        raise ValidationError("Color desconocido: usar red, yellow o green.")
    return LedCommand(command_id, **{name: name == color for name in LED_COLORS})


def all_off(command_id: str) -> LedCommand:
    return LedCommand(command_id, red=False, yellow=False, green=False)


class LedDevice:
    """Estado lógico con una confirmación pendiente y deduplicación de la última orden.

    El transporte debe llamar confirmation_sent solo después de aceptar el envío.
    Un envío QoS 0 no garantiza que el consumidor reciba la confirmación.
    """

    def __init__(self, device_id: str):
        # Reutiliza el validador común de identificador sin publicar un estado.
        LedState(LedValues(), "validation", device_id, 0)
        self.device_id = device_id
        self.values = LedValues()
        self.pending = False
        self.last_command: LedCommand | None = None
        self.confirmation: LedState | None = None

    def accept(self, command: LedCommand, uptime_ms: int) -> str:
        if not isinstance(command, LedCommand):
            raise ValidationError("Se requiere LedCommand.")
        if self.last_command and self.last_command.command_id == command.command_id:
            if self.last_command != command:
                return "conflicting_id"
            if self.pending:
                return "duplicate"
            self.pending = True
            return "replay"
        if self.pending:
            return "busy"
        values = command.apply(self.values)
        confirmation = LedState(values, command.command_id, self.device_id, uptime_ms)
        self.values, self.last_command, self.confirmation = values, command, confirmation
        self.pending = True
        return "applied"

    def confirmation_sent(self) -> None:
        self.pending = False
