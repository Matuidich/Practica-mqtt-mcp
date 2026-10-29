"""Composición FastMCP/stdio con inicio y cierre MQTT explícitos."""

import asyncio
from contextlib import asynccontextmanager

from iot_shared.config import Settings
from iot_mcp.mqtt_gateway import MqttGateway
from iot_mcp.tools import DeviceTools


TOOL_NAMES = (
    "get_last_distance", "get_led_state", "set_led", "set_leds",
    "set_only_led", "turn_off_all_leds",
)


def build_server(settings: Settings, *, gateway: MqttGateway | None = None):
    """Construye herramientas sin conectar. El lifespan inicia y cierra el gateway."""
    from fastmcp import FastMCP

    gateway = gateway if gateway is not None else MqttGateway(settings)
    tools = DeviceTools(gateway)

    @asynccontextmanager
    async def lifespan(server):
        try:
            gateway.start()
            yield {"gateway": gateway}
        finally:
            await asyncio.to_thread(gateway.close)

    server = FastMCP(
        "SIS-234 IoT: distancia y LEDs",
        instructions=(
            "Consulta distancia y controla LEDs red/yellow/green. "
            "Usa los estados y la edad devueltos; nunca inventes una lectura. "
            "mqtt_accepted solo significa aceptación local por Paho. "
            "Solo confirmation_verified=true y status=applied confirman una orden. "
            "applied informa niveles GPIO, no luz medida. "
            "Tras timeout o disconnected el resultado es incierto; no reintentes "
            "con un ID nuevo sin indicación del usuario."
        ),
        lifespan=lifespan,
        strict_input_validation=True,
    )
    for name in TOOL_NAMES:
        read_only = name in ("get_last_distance", "get_led_state")
        server.tool(
            getattr(tools, name),
            annotations={"readOnlyHint": read_only, "destructiveHint": not read_only,
                         "idempotentHint": read_only, "openWorldHint": True},
        )
    return server
