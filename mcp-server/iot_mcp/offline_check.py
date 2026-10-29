"""Autocomprobación explícita: FastMCP real y doble MQTT, sin broker ni hardware."""

import asyncio
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from iot_shared.config import PROJECT_ROOT, Settings, parse_env
from iot_shared.leds import LedDevice
from iot_shared.messages import DistanceReading, LedCommand


class MemoryMqttClient:
    """Doble local de Paho usado únicamente por --check-offline y pruebas."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.device = LedDevice("offline-esp32")
        self.auto_confirm = True
        self.auto_connect = True
        self.publish_rc = 0
        self.subscribe_rc = 0
        self.loop_rc = 0
        self.on_publish_hook = None
        self.publications = []
        self.subscriptions = []
        self.mid = 0
        self.stopped = False
        self.disconnect_calls = 0
        self.connect_calls = 0

    def reconnect_delay_set(self, minimum, maximum):
        self.delays = (minimum, maximum)

    def connect_async(self, host, port, keepalive):
        self.connect_calls += 1
        self.connection = (host, port, keepalive)

    def loop_start(self):
        if self.auto_connect:
            self.connect()
            self.emit(self.settings.topics.distance,
                      DistanceReading(42.5, self.device.device_id, 100).to_json())
        return self.loop_rc

    def connect(self, reason_code=0, *, suback=True):
        self.on_connect(self, None, None, reason_code, None)
        if reason_code == 0 and self.subscribe_rc == 0 and suback:
            self.on_subscribe(self, None, self.mid, [0, 0], None)

    def subscribe(self, topics):
        self.mid += 1
        self.subscriptions.append(topics)
        return self.subscribe_rc, self.mid

    def publish(self, topic, payload, qos, retain):
        self.publications.append((topic, payload, qos, retain))
        command = LedCommand.from_json(payload)
        if self.on_publish_hook is not None:
            self.on_publish_hook(command)
        elif self.auto_confirm and self.publish_rc == 0:
            self.device.accept(command, len(self.publications) * 100)
            self.emit(self.settings.topics.led_state, self.device.confirmation.to_json())
            self.device.confirmation_sent()
        return SimpleNamespace(rc=self.publish_rc)

    def emit(self, topic, payload, *, retain=False):
        self.on_message(self, None, SimpleNamespace(topic=topic, payload=payload, retain=retain))

    def lose_connection(self):
        self.on_disconnect(self, None, None, 1, None)

    def disconnect(self):
        self.disconnect_calls += 1
        self.on_disconnect(self, None, None, 0, None)
        return 0

    def loop_stop(self):
        self.stopped = True
        return 0


def offline_settings() -> Settings:
    """Usa solo la plantilla con UUID ficticio; no lee ni modifica .env real."""
    text = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
    return Settings.from_mapping(parse_env(text.replace(
        "REEMPLAZAR_CON_UUID", "123e4567-e89b-42d3-a456-426614174000")))


async def check_server() -> None:
    from fastmcp import Client
    from iot_mcp.mqtt_gateway import MqttGateway
    from iot_mcp.server import TOOL_NAMES, build_server

    # Se bloquean conexiones y DNS además de inyectar el doble. Se conserva la
    # clase socket para las comprobaciones internas del Proactor de Windows.
    with ExitStack() as stack:
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection", "socket.getaddrinfo",
                       "socket.gethostbyname", "socket.gethostbyname_ex"):
            stack.enter_context(patch(target, side_effect=RuntimeError("Red prohibida en check-offline")))
        settings = offline_settings()
        mqtt = MemoryMqttClient(settings)
        gateway = MqttGateway(settings, client_factory=lambda _: mqtt)
        server = build_server(settings, gateway=gateway)
        async with Client(server) as client:
            names = {tool.name for tool in await client.list_tools()}
            if names != set(TOOL_NAMES):
                raise RuntimeError("Catálogo MCP incompleto.")
            distance = await client.call_tool("get_last_distance", {})
            if distance.data["reading"]["distance_cm"] != 42.5:
                raise RuntimeError("La lectura MQTT no llegó a la herramienta MCP.")
            for name, arguments in (
                ("set_led", {"color": "red", "on": True}),
                ("set_leds", {"changes": {"yellow": True, "green": True}}),
                ("set_only_led", {"color": "green"}),
                ("turn_off_all_leds", {}),
            ):
                result = await client.call_tool(name, arguments)
                if result.data["status"] != "applied" or not result.data["confirmation_verified"]:
                    raise RuntimeError(f"No se verificó la confirmación local de {name}.")
            state = await client.call_tool("get_led_state", {})
            if any(state.data["state"]["leds"].values()):
                raise RuntimeError("El modelo local no terminó con los tres LEDs apagados.")
        if not mqtt.stopped:
            raise RuntimeError("El cierre MCP no liberó el transporte local.")


def run_check() -> None:
    asyncio.run(check_server())
