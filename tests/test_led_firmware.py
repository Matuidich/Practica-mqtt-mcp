"""Integración del firmware real LED y reconexión con dobles, sin broker ni GPIO."""

import itertools
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from iot_shared.errors import ValidationError
from iot_shared.messages import LED_COLORS, LedCommand, LedState
from tests.support import OfflineTestCase, PROJECT_ROOT


@unittest.skipUnless(shutil.which("g++"), "G++ no disponible para pruebas C++ en el PC")
class LedFirmwareTests(OfflineTestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        cls.enabled = cls.compile(directory, "test_led_actuator.cpp", "enabled", True)
        cls.blocked = cls.compile(directory, "test_led_actuator.cpp", "blocked", False)
        cls.connection = cls.compile(directory, "test_connection.cpp", "connection", False)

    @classmethod
    def compile(cls, directory, source, name, enabled):
        folder = PROJECT_ROOT / "firmware/test/leds"
        executable = directory / (name + ".exe")
        command = [shutil.which("g++"), "-std=c++11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                   "-I", str(folder / "fakes"), "-I", str(PROJECT_ROOT / "firmware/include")]
        if enabled:
            command.append("-DLED_WIRING_CONFIRMED=true")
        dependencies = subprocess.run(command + [str(folder / source), "-MM"],
                                      capture_output=True, text=True, timeout=30)
        if (dependencies.returncode or "device_config.local.h" in dependencies.stdout or
                "mqtt_config.local.h" in dependencies.stdout):
            raise AssertionError("La prueba debe compilar exclusivamente con configuración ficticia.")
        result = subprocess.run(command + [str(folder / source), "-o", str(executable)],
                                capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return executable

    def execute(self, executable, *arguments, input=None):
        result = subprocess.run([str(executable), *arguments], input=input,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_real_application_outputs_confirmations_and_safety(self):
        for scenario in ("startup", "individual", "combined", "duplicates", "validation", "disconnected", "retry"):
            with self.subTest(scenario=scenario):
                self.execute(self.enabled, scenario)

    def test_default_unconfirmed_wiring_never_configures_outputs(self):
        self.execute(self.blocked, "blocked")

    def test_real_connection_reconnects_with_backoff_and_restores_led_subscription(self):
        self.execute(self.connection)

    def test_cpp_full_states_match_python_contract(self):
        lines = self.execute(self.enabled, "--encode").splitlines()
        self.assertEqual(len(lines), 8)
        for bits, line in enumerate(lines):
            state = LedState.from_json(line)
            self.assertEqual((state.leds.red, state.leds.yellow, state.leds.green),
                             tuple(bool(bits & (1 << index)) for index in range(3)))
            self.assertEqual(state.command_id, "fixture-1")
            self.assertEqual(state.uptime_ms, 4294967295)

    def test_cpp_parser_matches_python_for_partial_combinations_and_invalid_json(self):
        corpus = []
        for values in itertools.product((None, False, True), repeat=3):
            fields = {color: value for color, value in zip(LED_COLORS, values) if value is not None}
            corpus.append(json.dumps({"command_id": "cmd-1", "leds": fields}).encode())
        for value in (1, 0, "true", None, [], {}, 1.0):
            corpus.append(json.dumps({"command_id": "cmd-1", "leds": {"red": value}}).encode())
        for identifier in ("", "x" * 64, "x" * 65, "a/b", "ñ", True):
            corpus.append(json.dumps({"command_id": identifier, "leds": {"red": True}}).encode())
        corpus += [payload.encode() for payload in (
            '', 'null', '[]', '{}', '{"command_id":"x","leds":{}}',
            '{"command_id":"x","leds":{"red":true,"red":false}}',
            '{"command_id":"x","command_id":"y","leds":{"red":true}}',
            '{"command_id":"x","leds":{"blue":true}}',
            '{"command_id":"x","leds":{"red":NaN}}',
            '{"command_id":"x","leds":{"red":true},"extra":false}',
            '{"command_id":"x","leds":{"red":true,}}',
            '{"command_id":"x","leds":{"red":true}} trailing',
            r'{"command_id":"cmd-1","leds":{"\u0072ed":true}}',
        )]
        corpus += [b'\xff', b'{"command_id":"x","leds":{"red":true}}\x00', b' ' * 1025]
        result = self.execute(self.enabled, "--decode", input="\n".join(p.hex() for p in corpus) + "\n")
        self.assertEqual(len(result.splitlines()), len(corpus))
        for payload, actual in zip(corpus, result.splitlines()):
            try:
                command = LedCommand.from_json(payload)
                mask = sum(1 << i for i, c in enumerate(LED_COLORS) if getattr(command, c) is not None)
                values = sum(1 << i for i, c in enumerate(LED_COLORS) if getattr(command, c) is True)
                expected = f"OK\t{command.command_id}\t{mask}\t{values}"
            except ValidationError:
                expected = "ERR"
            with self.subTest(payload=payload):
                self.assertEqual(actual, expected)
