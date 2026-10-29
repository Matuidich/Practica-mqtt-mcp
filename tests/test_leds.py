"""Contrato, modelo y composición futura MCP/simulador, exclusivamente sin red."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
import io
import itertools
import json
import runpy

from iot_shared.errors import ValidationError
from iot_shared.leds import LedDevice, all_off, only_led
from iot_shared.messages import LED_COLORS, LedCommand, LedState, LedValues, parse_message
from tests.support import OfflineTestCase, PROJECT_ROOT, settings


class LedMessageTests(OfflineTestCase):
    def test_every_partial_command_round_trips_and_preserves_omitted_colors(self):
        for values in itertools.product((None, False, True), repeat=3):
            if all(value is None for value in values):
                continue
            command = LedCommand("cmd-1", *values)
            self.assertEqual(LedCommand.from_json(command.to_json()), command)
            previous = LedValues(True, True, True)
            self.assertEqual(command.apply(previous), LedValues(*(
                True if value is None else value for value in values)))

    def test_individual_off_exclusive_and_all_off(self):
        previous = LedValues(True, True, True)
        self.assertEqual(LedCommand("off-red", red=False).apply(previous), LedValues(False, True, True))
        for index, color in enumerate(LED_COLORS):
            self.assertEqual(only_led(color, "only").apply(previous),
                             LedValues(*(position == index for position in range(3))))
        self.assertEqual(all_off("off").apply(previous), LedValues())
        with self.assertRaises(ValidationError):
            only_led("blue", "bad")

    def test_invalid_commands_reject_unknown_missing_null_and_nonboolean_fields(self):
        for fields in ({}, {"leds": {}}, {"command_id": "x", "leds": {}},
                       {"command_id": "x", "leds": {"blue": True}},
                       {"command_id": "x", "leds": {"red": True}, "extra": False}):
            with self.subTest(fields=fields), self.assertRaises(ValidationError):
                LedCommand.from_json(json.dumps(fields))
        for value in (0, 1, 1.0, "true", None, [], {}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                LedCommand.from_json(json.dumps({"command_id": "x", "leds": {"red": value}}))
        for payload in (b'\xff', ' ' * 1025, '{"leds":{"red":true,"red":false},"command_id":"x"}',
                        '{"leds":{"red":true},"command_id":"x","command_id":"y"}',
                        '{"leds":{"red":NaN},"command_id":"x"}'):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                LedCommand.from_json(payload)

    def test_invalid_identifiers_and_direct_construction_are_rejected(self):
        for identifier in ("", "a/b", "a b", "ñ", "x" * 65, True, None):
            with self.subTest(identifier=identifier), self.assertRaises(ValidationError):
                LedCommand(identifier, red=True)
        with self.assertRaises(ValidationError):
            LedCommand("empty")
        with self.assertRaises(ValidationError):
            LedValues(red=1)
        with self.assertRaises(FrozenInstanceError):
            LedValues().red = True

    def test_states_require_all_colors_and_round_trip_every_combination(self):
        for values in itertools.product((False, True), repeat=3):
            state = LedState(LedValues(*values), "cmd-1", "actuator-01", 4294967295)
            self.assertEqual(LedState.from_json(state.to_json()), state)
        base = {"leds": {"red": True, "yellow": False, "green": False},
                "command_id": "cmd-1", "device_id": "actuator-01", "uptime_ms": 0, "status": "applied"}
        for changes in ({"leds": {"red": True}}, {"leds": {"red": True, "yellow": False, "green": 1}},
                        {"status": "pending"}, {"uptime_ms": True}, {"uptime_ms": -1},
                        {"uptime_ms": 4294967296}, {"device_id": "bad/id"}, {"extra": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                LedState.from_json(json.dumps({**base, **changes}))

    def test_led_topic_dispatch_is_distinct_from_servo_and_other_prefixes(self):
        config = settings()
        command = only_led("red", "cmd-1")
        state = LedState(command.apply(LedValues()), "cmd-1", "actuator-01", 1)
        self.assertEqual(parse_message(config.topics.led_command, command.to_json(), config), command)
        self.assertEqual(parse_message(config.topics.led_state, state.to_json(), config), state)
        for topic in (config.topics.servo_command, config.topics.distance, "other/commands/leds"):
            with self.subTest(topic=topic), self.assertRaises(ValidationError):
                parse_message(topic, command.to_json(), config)


class LedModelTests(OfflineTestCase):
    def test_pending_duplicates_conflicts_and_replay_preserve_original_state_and_uptime(self):
        device = LedDevice("actuator-01")
        command = only_led("red", "original")
        self.assertEqual(device.values, LedValues())
        self.assertEqual(device.accept(command, 100), "applied")
        self.assertEqual(device.accept(command, 200), "duplicate")
        self.assertEqual(device.accept(all_off("original"), 200), "conflicting_id")
        self.assertEqual(device.accept(only_led("green", "other"), 200), "busy")
        device.confirmation_sent()
        self.assertEqual(device.accept(command, 300), "replay")
        self.assertEqual(device.confirmation.uptime_ms, 100)
        self.assertEqual(device.values, LedValues(True, False, False))

    def test_new_command_after_confirmation_changes_only_selected_color(self):
        device = LedDevice("sim-01")
        device.accept(only_led("red", "first"), 0)
        device.confirmation_sent()
        self.assertEqual(device.accept(LedCommand("next", yellow=True), 10), "applied")
        self.assertEqual(device.values, LedValues(True, True, False))
        self.assertEqual(LedDevice("sim-01").values, LedValues())


class LedInterfacesTests(OfflineTestCase):
    def load_module(self, relative):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = runpy.run_path(str(PROJECT_ROOT / relative))
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        return result

    def test_future_mcp_preparation_simulator_and_ack_contract_integrate_offline(self):
        tools = self.load_module("mcp-server/iot_mcp/tools.py")
        simulation = self.load_module("simulator/iot_simulator/device.py")
        self.load_module("mcp-server/iot_mcp/mqtt_gateway.py")
        config = settings()
        device = simulation["SimulatedDevice"](config)
        command = tools["prepare_only_led"]("red", "mcp-1")
        state = device.handle_command(config.topics.led_command, command.to_json(), 123)
        decoded = parse_message(config.topics.led_state, state.to_json(), config)
        self.assertEqual(decoded.command_id, "mcp-1")
        self.assertEqual(decoded.leds, LedValues(True, False, False))
        self.assertIsNone(device.handle_command(config.topics.led_command,
                         tools["prepare_all_off"]("mcp-2").to_json(), 124))
        device.confirmation_sent()
        for index, color in enumerate(LED_COLORS):
            command = tools["prepare_set_led"](color, False, f"off-{index}")
            self.assertIsNotNone(device.handle_command(config.topics.led_command, command.to_json(), 200 + index))
            device.confirmation_sent()
        self.assertEqual(device.leds.values, LedValues())
        self.assertEqual(device.distance_reading(42.5, 300).distance_cm, 42.5)

    def test_simulator_rejects_servo_topic_and_mcp_uses_shared_validation(self):
        tools = self.load_module("mcp-server/iot_mcp/tools.py")
        simulation = self.load_module("simulator/iot_simulator/device.py")
        config = settings()
        device = simulation["SimulatedDevice"](config)
        with self.assertRaises(ValidationError):
            device.handle_command(config.topics.servo_command, only_led("red", "x").to_json(), 0)
        for changes in ({"blue": True}, {"red": 1}, {"red": None}, {}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                tools["prepare_set_leds"](changes, "bad")
