"""Proceso STDIO de prueba: entrada real, FastMCP real y MQTT siempre falso."""

from contextlib import ExitStack
import logging
from pathlib import Path
import runpy
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "mcp-server"))


def main() -> int:
    from iot_mcp.mqtt_gateway import MqttGateway
    from iot_mcp.offline_check import MemoryMqttClient
    from iot_mcp import server

    real_build = server.build_server

    def build_with_fake_mqtt(settings):
        logging.getLogger("sis234.stdio_test").warning("Diagnostico local STDIO: MQTT falso.")
        mqtt = MemoryMqttClient(settings)
        gateway = MqttGateway(settings, client_factory=lambda _: mqtt)
        return real_build(settings, gateway=gateway)

    entry = runpy.run_path(str(PROJECT_ROOT / "mcp-server" / "main.py"), run_name="stdio_test")
    with ExitStack() as stack:
        stack.enter_context(patch("iot_mcp.server.build_server", side_effect=build_with_fake_mqtt))
        # Windows necesita sockets locales para el Proactor. Se bloquean DNS,
        # creación de conexiones MQTT y cualquier construcción del cliente real.
        for target in ("socket.create_connection", "socket.getaddrinfo",
                       "socket.gethostbyname", "socket.gethostbyname_ex",
                       "paho.mqtt.client.Client"):
            stack.enter_context(patch(target, side_effect=AssertionError("Red real prohibida en prueba STDIO")))
        return entry["main"](sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
