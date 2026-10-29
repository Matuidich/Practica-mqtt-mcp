"""Mensajes válidos, entradas adversas y límites específicos del modelo."""

import json

from iot_shared.angles import ServoLimits
from iot_shared.errors import ValidationError
from iot_shared.messages import (
    MAX_PAYLOAD_BYTES, DistanceReading, ServoCommand, ServoState, parse_message,
)
from tests.support import OfflineTestCase, settings


class MessageTests(OfflineTestCase):
    def test_positive_finite_distances_round_trip_as_text_and_utf8_bytes(self):
        for distance in (0.01, 42.5, 400, 500):
            reading = DistanceReading(distance, "esp32-01", 12345)
            for payload in (reading.to_json(), reading.to_json().encode("utf-8")):
                with self.subTest(distance=distance, kind=type(payload)):
                    self.assertEqual(DistanceReading.from_json(payload), reading)

    def test_invalid_distance_values_are_rejected(self):
        for value in (0, -1, True, False, "42.5", None, [], float("nan"), float("inf"), 10**400):
            payload = json.dumps({"distance_cm": value, "device_id": "esp32-01", "uptime_ms": 0})
            with self.subTest(value=str(value)[:30]), self.assertRaises(ValidationError):
                DistanceReading.from_json(payload)
        with self.assertRaises(ValidationError):
            DistanceReading.from_json('{"distance_cm":1e400,"device_id":"esp32-01","uptime_ms":0}')

    def test_identifiers_reject_empty_spaces_unicode_and_excessive_length(self):
        for value in ("", "a b", "a/b", "ñ", "-device", "a" * 65, None, True):
            with self.subTest(identifier=value):
                with self.assertRaises(ValidationError):
                    DistanceReading(42, value, 0)
                with self.assertRaises(ValidationError):
                    ServoCommand(90, value)

    def test_uptime_uses_nonnegative_uint32_including_zero_and_maximum(self):
        for value in (0, 4294967295):
            self.assertEqual(DistanceReading(42, "esp32-01", value).uptime_ms, value)
        for value in (-1, 4294967296, True, 1.0, "123", None):
            with self.subTest(uptime=value), self.assertRaises(ValidationError):
                DistanceReading(42, "esp32-01", value)

    def test_servo_command_accepts_inclusive_limits_and_preserves_correlation_id(self):
        for angle in (0, 90, 180):
            command = ServoCommand(angle, "cmd-0001")
            self.assertEqual(ServoCommand.from_json(command.to_json()), command)

    def test_angle_validation_rejects_types_that_python_might_coerce(self):
        for angle in (-1, 181, True, False, 90.0, 90.5, "90", None, [], {}):
            payload = json.dumps({"angle": angle, "command_id": "cmd-0001"})
            with self.subTest(angle=angle), self.assertRaises(ValidationError):
                ServoCommand.from_json(payload)

    def test_model_limits_apply_to_parsing_and_serializing_commands_and_state(self):
        limits = ServoLimits(15, 165)
        for angle in (15, 165):
            command = ServoCommand(angle, "cmd-0001")
            self.assertEqual(ServoCommand.from_json(command.to_json(limits), limits), command)
        for angle in (0, 14, 166, 180):
            command = ServoCommand(angle, "cmd-0001")
            state = ServoState(angle, "cmd-0001", "sim-01", 0)
            with self.subTest(angle=angle):
                with self.assertRaises(ValidationError):
                    command.to_json(limits)
                with self.assertRaises(ValidationError):
                    ServoCommand.from_json(command.to_json(), limits)
                with self.assertRaises(ValidationError):
                    state.to_json(limits)
                with self.assertRaises(ValidationError):
                    ServoState.from_json(state.to_json(), limits)

    def test_invalid_limit_types_and_ranges_are_rejected(self):
        for low, high in ((True, 180), (0, 180.0), (-1, 180), (0, 181), (90, 90), (180, 0)):
            with self.subTest(low=low, high=high), self.assertRaises(ValidationError):
                ServoLimits(low, high)

    def test_state_confirms_applied_order_with_same_id(self):
        command = ServoCommand(90, "cmd-0001")
        state = ServoState(command.angle, command.command_id, "sim-01", 15000)
        decoded = ServoState.from_json(state.to_json())
        self.assertEqual(decoded.command_id, command.command_id)
        self.assertEqual(decoded.angle, command.angle)
        self.assertEqual(decoded.status, "applied")

    def test_pending_or_rejected_status_is_not_an_applied_confirmation(self):
        for status in ("pending", "rejected", "", True, None):
            with self.subTest(status=status), self.assertRaises(ValidationError):
                ServoState(90, "cmd-0001", "esp32-01", 0, status)

    def test_each_schema_rejects_missing_and_unknown_fields(self):
        examples = (
            (DistanceReading, {"distance_cm": 42.5, "device_id": "esp32-01", "uptime_ms": 0}),
            (ServoCommand, {"angle": 90, "command_id": "cmd-0001"}),
            (ServoState, {"angle": 90, "command_id": "cmd-0001", "device_id": "esp32-01", "uptime_ms": 0, "status": "applied"}),
        )
        for model, fields in examples:
            for missing in fields:
                payload = {key: value for key, value in fields.items() if key != missing}
                with self.subTest(model=model.__name__, missing=missing):
                    with self.assertRaises(ValidationError):
                        model.from_json(json.dumps(payload))
            with self.assertRaises(ValidationError):
                model.from_json(json.dumps({**fields, "unexpected": 1}))

    def test_strict_json_rejects_nonobjects_duplicates_trailing_data_and_constants(self):
        for payload in (
            "", "null", "true", "90", "[]", '"hello"',
            '{"angle":90,}', '{"angle":90} {}',
            '{"angle":90,"angle":180,"command_id":"cmd-1"}',
            '{"angle":NaN,"command_id":"cmd-1"}',
            '{"angle":Infinity,"command_id":"cmd-1"}',
            '{"angle":-Infinity,"command_id":"cmd-1"}',
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ServoCommand.from_json(payload)

    def test_payload_requires_utf8_and_has_a_byte_limit(self):
        for payload in (b"\xff", "\ud800", None, {}, 90):
            with self.subTest(kind=type(payload)), self.assertRaises(ValidationError):
                ServoCommand.from_json(payload)
        payload = ServoCommand(90, "cmd-0001").to_json()
        padded = " " * (MAX_PAYLOAD_BYTES - len(payload.encode("utf-8"))) + payload
        self.assertEqual(ServoCommand.from_json(padded).angle, 90)
        with self.assertRaises(ValidationError):
            ServoCommand.from_json(" " + padded)

    def test_topic_dispatch_uses_configured_servo_range(self):
        config = settings(SERVO_MIN_ANGLE="15", SERVO_MAX_ANGLE="165")
        examples = (
            (config.topics.distance, DistanceReading(42.5, "sim-01", 0)),
            (config.topics.servo_command, ServoCommand(90, "cmd-0001")),
            (config.topics.servo_state, ServoState(90, "cmd-0001", "sim-01", 1000)),
        )
        for topic, message in examples:
            self.assertEqual(parse_message(topic, message.to_json(), config), message)
        with self.assertRaises(ValidationError):
            parse_message(config.topics.servo_command, ServoCommand(0, "cmd-0001").to_json(), config)
        with self.assertRaises(ValidationError):
            parse_message("other/project/commands/servo", ServoCommand(90, "cmd-0001").to_json(), config)
        with self.assertRaises(ValidationError):
            parse_message(config.topics.distance, ServoCommand(90, "cmd-0001").to_json(), config)
