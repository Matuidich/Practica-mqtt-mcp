"""Puente MQTT explícito, con confirmaciones y esperas acotadas, sin red al importar."""

from collections import OrderedDict
from dataclasses import dataclass
import copy
import json
import logging
import math
import threading
import time
from typing import Callable, Protocol

from iot_shared.config import ClientRole, Settings
from iot_shared.errors import ValidationError
from iot_shared.messages import LED_COLORS, DistanceReading, LedCommand, LedState
from iot_mcp.device_state import DeviceState


logger = logging.getLogger(__name__)
DEFAULT_COMMAND_TIMEOUT_S = 5.0
MAX_COMMAND_TIMEOUT_S = 30.0
COMMAND_HISTORY_SIZE = 128


class LedGateway(Protocol):
    def send_led_command(self, command: LedCommand,
                         timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S) -> dict: ...
    def get_last_distance(self) -> dict: ...
    def get_led_state(self) -> dict: ...


def create_paho_client(settings: Settings):
    """Construye Paho sin conectarlo. Solo start() inicia su hilo de red."""
    import paho.mqtt.client as mqtt

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.client_id(ClientRole.MCP),
        clean_session=True,
        protocol=mqtt.MQTTv311,
        transport="tcp",
        reconnect_on_failure=True,
    )
    client.connect_timeout = 5.0
    client.enable_logger(logger)
    return client


def validate_timeout(timeout_s: float) -> None:
    if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s)
            or not 0 < timeout_s <= MAX_COMMAND_TIMEOUT_S):
        raise ValidationError("timeout_s debe ser mayor que 0 y como máximo 30 segundos.")


@dataclass
class CommandRecord:
    command: LedCommand
    deadline: float
    mqtt_accepted: bool = False
    result: dict | None = None


class MqttGateway:
    """Paho posee la red; una Condition protege cachés y correlación entre hilos.

    Se permite una orden pendiente, igual que en el firmware. Los últimos 128
    resultados evitan republicar duplicados durante esta ejecución del servidor.
    """

    def __init__(self, settings: Settings, *,
                 client_factory: Callable = create_paho_client,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.settings = settings
        self._client_factory = client_factory
        self._clock = clock
        self._condition = threading.Condition()
        self._state = DeviceState()
        self._history: OrderedDict[str, CommandRecord] = OrderedDict()
        self._pending: CommandRecord | None = None
        self._client = None
        self._started = False
        self._ready = False
        self._subscription_mid: int | None = None
        self._connection_status = "stopped"

    def start(self) -> None:
        """Inicia conexión asíncrona; MCP puede responder aunque el broker no esté."""
        with self._condition:
            if self._started:
                return
            self._started = True
            self._connection_status = "connecting"
        try:
            client = self._client_factory(self.settings)
            with self._condition:
                self._client = client
            client.on_connect = self._on_connect
            client.on_connect_fail = self._on_connect_fail
            client.on_subscribe = self._on_subscribe
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
            client.reconnect_delay_set(self.settings.reconnect_min_delay_s,
                                       self.settings.reconnect_max_delay_s)
            client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port,
                                 self.settings.keepalive_s)
            if client.loop_start() != 0:
                raise RuntimeError("No se pudo iniciar el hilo MQTT.")
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        """Despierta las esperas y cierra recursos, también si falló el inicio."""
        with self._condition:
            self._started = False
            self._ready = False
            self._subscription_mid = None
            self._connection_status = "stopped"
            self._state.disconnected()
            if self._pending is not None:
                self._complete(self._pending, "disconnected", "El servidor se cerró; resultado no confirmado.")
            client, self._client = self._client, None
            self._condition.notify_all()
        if client is not None:
            try:
                client.disconnect()
            finally:
                client.loop_stop()

    def _connection_lost(self, status: str) -> None:
        self._ready = False
        self._subscription_mid = None
        self._connection_status = status
        self._state.disconnected()
        if self._pending is not None:
            self._complete(self._pending, "disconnected",
                           "Conexión perdida; la orden podría haberse aplicado. No se reenvía.")
        self._condition.notify_all()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        with self._condition:
            if not self._started:
                return
            if reason_code != 0:
                self._connection_lost("connection_failed")
                logger.warning("MQTT rechazó la conexión: %s", reason_code)
                return
            self._connection_status = "subscribing"
            self._ready = False
            rc, mid = client.subscribe([(self.settings.topics.distance, 0),
                                        (self.settings.topics.led_state, 0)])
            if rc != 0:
                self._connection_lost("subscription_failed")
                logger.warning("MQTT no aceptó la suscripción: %s", rc)
                return
            self._subscription_mid = mid

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties) -> None:
        with self._condition:
            if not self._started or mid != self._subscription_mid:
                return
            if len(reason_codes) != 2 or any(code != 0 for code in reason_codes):
                self._connection_lost("subscription_failed")
                logger.warning("MQTT rechazó una suscripción QoS 0.")
                return
            self._subscription_mid = None
            self._ready = True
            self._connection_status = "ready"
            self._condition.notify_all()

    def _on_connect_fail(self, client, userdata) -> None:
        with self._condition:
            if self._started:
                self._connection_lost("connection_failed")
        logger.warning("MQTT no disponible; Paho reintentará con espera progresiva limitada.")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        with self._condition:
            if self._started:
                self._connection_lost("disconnected")

    def _on_message(self, client, userdata, message) -> None:
        # Un retained antiguo no puede certificar ni una medición reciente ni una orden.
        if message.retain:
            logger.warning("Se ignoró un mensaje retained; el contrato usa retain=false.")
            return
        try:
            if message.topic == self.settings.topics.distance:
                parsed = DistanceReading.from_json(message.payload)
            elif message.topic == self.settings.topics.led_state:
                parsed = LedState.from_json(message.payload)
            else:
                return
        except ValidationError as error:
            logger.warning("Se ignoró un mensaje MQTT inválido: %s", error)
            return
        with self._condition:
            if not self._started or not self._ready:
                return
            now = self._clock()
            record = self._history.get(parsed.command_id) if isinstance(parsed, LedState) else None
            if record is not None:
                # Duplicados o confirmaciones tardías de una llamada terminada
                # no sustituyen el estado más reciente ni renuevan su edad.
                if record.result is not None:
                    return
                if now >= record.deadline:
                    self._complete(record, "timeout", "Confirmación tardía; venció la espera de la orden.")
                    return
                matches = all(getattr(record.command, color) is None or
                              getattr(record.command, color) == getattr(parsed.leds, color)
                              for color in LED_COLORS)
                if not matches:
                    if record is self._pending:
                        self._complete(record, "confirmation_mismatch",
                                       "El ID coincide, pero los colores solicitados no coinciden con state/leds.")
                    logger.warning("Confirmación LED incompatible con la orden del mismo ID.")
                    return
            self._state.receive(parsed, now)
            if record is not None and record is self._pending:
                self._complete(record, "applied",
                               "state/leds confirmó los niveles GPIO lógicos; no mide luz.", parsed)
            self._condition.notify_all()

    def _complete(self, record: CommandRecord, status: str, detail: str,
                  confirmation: LedState | None = None) -> None:
        if record.result is not None:
            return
        record.result = {
            "status": status,
            "command_id": record.command.command_id,
            "mqtt_accepted": record.mqtt_accepted,
            "confirmation_verified": confirmation is not None,
            "confirmation": json.loads(confirmation.to_json()) if confirmation else None,
            "detail": detail,
        }
        if record is self._pending:
            self._pending = None
        self._condition.notify_all()

    def send_led_command(self, command: LedCommand,
                         timeout_s: float = DEFAULT_COMMAND_TIMEOUT_S) -> dict:
        if not isinstance(command, LedCommand):
            raise ValidationError("Se requiere LedCommand validado.")
        validate_timeout(timeout_s)
        with self._condition:
            record = self._history.get(command.command_id)
            if record is not None and record.command != command:
                return self._rejected(command, "conflicting_id", "El ID ya corresponde a otra orden.")
            if record is None:
                if not self._ready or self._client is None:
                    return self._rejected(command, "disconnected", "MQTT no está conectado y suscrito; no se publicó.")
                if self._pending is not None:
                    return self._rejected(command, "busy", "Hay otra orden pendiente; no se encoló ni publicó.")
                while len(self._history) >= COMMAND_HISTORY_SIZE:
                    self._history.popitem(last=False)
                record = CommandRecord(command, self._clock() + timeout_s)
                self._history[command.command_id] = record
                self._pending = record
                try:
                    # QoS 0 evita una cola de retransmisión de órdenes al reconectar.
                    record.mqtt_accepted = True
                    info = self._client.publish(self.settings.topics.led_command,
                                                command.to_json(), qos=0, retain=False)
                    if info.rc != 0:
                        record.mqtt_accepted = False
                        self._complete(record, "publish_failed", "Paho rechazó la publicación; no se reintenta.")
                except (OSError, RuntimeError, ValueError):
                    record.mqtt_accepted = False
                    self._complete(record, "publish_failed", "Falló la publicación; no hay confirmación.")
            # Un duplicado pendiente comparte la espera original; nunca republica.
            while record.result is None:
                remaining = record.deadline - self._clock()
                if remaining <= 0:
                    self._complete(record, "timeout",
                                   "No llegó confirmación a tiempo; la orden podría haberse aplicado. No se reenvía.")
                    break
                self._condition.wait(remaining)
            return copy.deepcopy(record.result)

    @staticmethod
    def _rejected(command: LedCommand, status: str, detail: str) -> dict:
        return {"status": status, "command_id": command.command_id,
                "mqtt_accepted": False, "confirmation_verified": False,
                "confirmation": None, "detail": detail}

    def get_last_distance(self) -> dict:
        with self._condition:
            return {"connected": self._ready, "connection_status": self._connection_status,
                    **self._state.distance_snapshot(self._clock(), self.settings.distance_stale_after_s)}

    def get_led_state(self) -> dict:
        with self._condition:
            return {"connected": self._ready, "connection_status": self._connection_status,
                    **self._state.leds_snapshot(self._clock())}
