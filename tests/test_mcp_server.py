"""FastMCP en memoria y STDIO real con doble MQTT; ninguna conexión al broker."""

import asyncio
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
import os
import queue
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from tests.support import LocalProjectTestCase, PROJECT_ROOT, settings
from iot_mcp.mqtt_gateway import MqttGateway
from iot_mcp.offline_check import MemoryMqttClient, check_server
from iot_mcp.server import TOOL_NAMES, build_server


HAS_FASTMCP = importlib.util.find_spec("fastmcp") is not None


@unittest.skipUnless(HAS_FASTMCP, "Instalar dependencias MCP en .venv desde requirements.txt")
class FastMcpServerTests(unittest.TestCase):
    def run_async_offline(self, function):
        # Se crea primero el event loop para permitir el IPC local de Windows;
        # solo se prohíben conexiones y DNS durante las operaciones del servidor.
        async def guarded():
            with ExitStack() as stack:
                for target in ("socket.socket.connect", "socket.socket.connect_ex",
                               "socket.create_connection", "socket.getaddrinfo"):
                    stack.enter_context(patch(target, side_effect=AssertionError("Red prohibida")))
                await function()
        asyncio.run(guarded())

    def test_offline_check_starts_exposes_all_tools_calls_them_and_closes(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            asyncio.run(check_server())
        self.assertEqual(stdout.getvalue(), "")

    def test_schema_validation_rejects_coercion_and_reads_work_while_command_waits(self):
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async def scenario():
            config = settings()
            mqtt = MemoryMqttClient(config)
            gateway = MqttGateway(config, client_factory=lambda _: mqtt)
            server = build_server(config, gateway=gateway)
            async with Client(server) as client:
                tools = {tool.name: tool for tool in await client.list_tools()}
                self.assertEqual(set(tools), set(TOOL_NAMES))
                self.assertTrue(tools["get_last_distance"].annotations.read_only_hint)
                self.assertFalse(tools["set_led"].annotations.read_only_hint)
                with self.assertLogs("fastmcp.server.server", level="WARNING"):
                    for arguments in ({"color": "red", "on": 1},
                                      {"color": "red", "on": "true"},
                                      {"color": "blue", "on": True},
                                      {"color": "red", "on": True, "unexpected": 0}):
                        with self.subTest(arguments=arguments), self.assertRaises(ToolError):
                            await client.call_tool("set_led", arguments)
                    with self.assertRaises(ToolError):
                        await client.call_tool("set_leds", {"changes": {"red": 1}})
                self.assertEqual(mqtt.publications, [])
                published = threading.Event()
                mqtt.on_publish_hook = lambda _: published.set()
                pending = asyncio.create_task(client.call_tool(
                    "set_led", {"color": "red", "on": True, "command_id": "waiting", "timeout_s": 1}))
                self.assertTrue(await asyncio.to_thread(published.wait, 2))
                reading = await asyncio.wait_for(client.call_tool("get_last_distance", {}), timeout=0.5)
                self.assertEqual(reading.data["reading"]["distance_cm"], 42.5)
                result = await pending
                self.assertEqual(result.data["status"], "timeout")
            self.assertTrue(mqtt.stopped)

        self.run_async_offline(scenario)

    def test_broker_unavailable_does_not_prevent_mcp_startup(self):
        from fastmcp import Client

        async def scenario():
            config = settings()
            mqtt = MemoryMqttClient(config)
            mqtt.auto_connect = False
            gateway = MqttGateway(config, client_factory=lambda _: mqtt)
            async with Client(build_server(config, gateway=gateway)) as client:
                self.assertEqual(len(await client.list_tools()), 6)
                reading = await client.call_tool("get_last_distance", {})
                self.assertEqual(reading.data["status"], "unknown")
                result = await client.call_tool("set_led", {"color": "red", "on": True})
                self.assertEqual(result.data["status"], "disconnected")
                self.assertEqual(mqtt.publications, [])

        self.run_async_offline(scenario)


@unittest.skipUnless(HAS_FASTMCP, "Instalar dependencias MCP en .venv desde requirements.txt")
class StdioServerTests(LocalProjectTestCase):
    def test_real_stdio_entrypoint_has_only_json_protocol_on_stdout(self):
        self.write_env()
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen(
            [sys.executable, "-B", str(PROJECT_ROOT / "tests" / "stdio_mcp_harness.py"),
             "--env-file", str(self.root / ".env")],
            cwd=self.root, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1,
        )
        messages = queue.Queue()
        stdout_lines, stderr_lines = [], []

        def read_stdout():
            for line in process.stdout:
                stdout_lines.append(line)
                try:
                    messages.put(json.loads(line))
                except json.JSONDecodeError:
                    messages.put({"invalid_stdout": line})

        def read_stderr():
            stderr_lines.extend(process.stderr)

        stdout_reader = threading.Thread(target=read_stdout, daemon=True)
        stderr_reader = threading.Thread(target=read_stderr, daemon=True)
        stdout_reader.start()
        stderr_reader.start()

        def cleanup():
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            stdout_reader.join(timeout=5)
            stderr_reader.join(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                if not stream.closed:
                    stream.close()

        self.addCleanup(cleanup)

        def send(method, *, identifier=None, params=None):
            request = {"jsonrpc": "2.0", "method": method}
            if identifier is not None:
                request["id"] = identifier
            if params is not None:
                request["params"] = params
            process.stdin.write(json.dumps(request) + "\n")
            process.stdin.flush()

        def response(identifier):
            while True:
                try:
                    message = messages.get(timeout=30)
                except queue.Empty:
                    self.fail(f"STDIO no respondió a {identifier}; stderr={''.join(stderr_lines)}")
                self.assertNotIn("invalid_stdout", message, message)
                self.assertEqual(message["jsonrpc"], "2.0")
                if message.get("id") == identifier:
                    self.assertNotIn("error", message, message)
                    return message["result"]

        send("initialize", identifier=1, params={"protocolVersion": "2025-11-25", "capabilities": {},
                                               "clientInfo": {"name": "sis234-offline-test", "version": "1"}})
        self.assertIn("serverInfo", response(1))
        send("notifications/initialized")
        send("tools/list", identifier=2)
        self.assertEqual({tool["name"] for tool in response(2)["tools"]}, set(TOOL_NAMES))
        send("tools/call", identifier=3, params={"name": "get_last_distance", "arguments": {}})
        distance = response(3)
        self.assertFalse(distance.get("isError", False))
        self.assertEqual(distance["structuredContent"]["reading"]["distance_cm"], 42.5)
        send("tools/call", identifier=4, params={"name": "set_leds", "arguments": {
            "changes": {"red": True, "green": True}, "command_id": "stdio-local"}})
        confirmed = response(4)
        self.assertFalse(confirmed.get("isError", False))
        self.assertTrue(confirmed["structuredContent"]["confirmation_verified"])
        self.assertEqual(confirmed["structuredContent"]["confirmation"]["leds"],
                         {"red": True, "yellow": False, "green": True})
        process.stdin.close()
        self.assertEqual(process.wait(timeout=15), 0)
        stdout_reader.join(timeout=5)
        stderr_reader.join(timeout=5)
        self.assertGreaterEqual(len(stdout_lines), 4)
        for line in stdout_lines:
            self.assertEqual(json.loads(line)["jsonrpc"], "2.0")
        self.assertIn("Diagnostico local STDIO: MQTT falso.", "".join(stderr_lines))
