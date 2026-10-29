"""Herramientas LED y transformaciones puras; no abren recursos al importar."""

import json
from typing import TYPE_CHECKING
from uuid import uuid4

from iot_shared.errors import ValidationError
from iot_shared.leds import all_off, only_led
from iot_shared.messages import LED_COLORS, LedCommand

if TYPE_CHECKING:
    from iot_mcp.mqtt_gateway import LedGateway


def prepare_set_led(color: str, on: bool, command_id: str) -> LedCommand:
    if color not in LED_COLORS:
        raise ValidationError("Color desconocido.")
    return prepare_set_leds({color: on}, command_id)


def prepare_set_leds(changes: dict[str, bool], command_id: str) -> LedCommand:
    return LedCommand.from_json(json.dumps({"command_id": command_id, "leds": changes}))


def prepare_only_led(color: str, command_id: str) -> LedCommand:
    return only_led(color, command_id)


def prepare_all_off(command_id: str) -> LedCommand:
    return all_off(command_id)


class DeviceTools:
    """Interfaz de aplicación. El transporte se inyecta y puede ser un doble local."""

    def __init__(self, gateway: "LedGateway"):
        self.gateway = gateway

    @staticmethod
    def _command_id(command_id: str | None) -> str:
        # Un valor vacío explícito debe fallar en el validador, no generar otro ID.
        return str(uuid4()) if command_id is None else command_id

    def get_last_distance(self) -> dict:
        """Lee la última distancia recibida, con edad y estado fresh/stale/unknown.

        No solicita una medición nueva. Tras iniciar, espera la siguiente
        publicación del HC-SR04; el contrato no utiliza mensajes retained.
        """
        return self.gateway.get_last_distance()

    def get_led_state(self) -> dict:
        """Lee el último state/leds observado, también si la orden vino del móvil.

        Es una observación de niveles GPIO lógicos, no una medición de luz.
        unknown indica que aún no se recibió ninguna confirmación válida.
        """
        return self.gateway.get_led_state()

    def set_led(self, color: str, on: bool, command_id: str | None = None,
                timeout_s: float = 5.0) -> dict:
        """Enciende o apaga red, yellow o green; conserva los otros dos LEDs.

        Espera state/leds con el mismo ID y los valores solicitados.
        command_id se genera si se omite; reutilizarlo deduplica la llamada
        dentro del historial de esta ejecución. timeout_s: mayor que 0, máximo 30.
        Un timeout o desconexión deja el resultado incierto y no reenvía la orden.
        """
        command = prepare_set_led(color, on, self._command_id(command_id))
        return self.gateway.send_led_command(command, timeout_s)

    def set_leds(self, changes: dict[str, bool], command_id: str | None = None,
                 timeout_s: float = 5.0) -> dict:
        """Controla cualquier combinación con booleanos red/yellow/green.

        Los colores omitidos conservan su estado. Publica un único mensaje,
        sin retain. Solo devuelve applied tras verificar la confirmación MQTT.
        Reutiliza command_id únicamente para consultar la misma orden; no reenvía.
        """
        command = prepare_set_leds(changes, self._command_id(command_id))
        return self.gateway.send_led_command(command, timeout_s)

    def set_only_led(self, color: str, command_id: str | None = None,
                     timeout_s: float = 5.0) -> dict:
        """Enciende solo red, yellow o green y apaga los otros en una sola orden.

        Espera confirmación con ID y tres valores coincidentes; no reintenta.
        """
        command = prepare_only_led(color, self._command_id(command_id))
        return self.gateway.send_led_command(command, timeout_s)

    def turn_off_all_leds(self, command_id: str | None = None,
                          timeout_s: float = 5.0) -> dict:
        """Apaga los tres LEDs y espera state/leds correlacionado; no reintenta."""
        command = prepare_all_off(self._command_id(command_id))
        return self.gateway.send_led_command(command, timeout_s)
