"""Contrato de configuración y sincronización de consumidores, todo sin red."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError
import io
import json
import os
from pathlib import Path
import re
import runpy
from unittest.mock import patch
from uuid import UUID

from iot_shared.__main__ import main
from iot_shared.angles import ServoLimits
from iot_shared.config import ClientRole, Settings, parse_env
from iot_shared.errors import ConfigurationError
from iot_shared.local_config import (
    check_local_config, initialize_local_config, sync_local_config,
)
from tests.support import (
    LocalProjectTestCase, OfflineTestCase, PROJECT_ROOT, TEST_UUID,
    config_values, example_text, settings,
)


class ConfigurationTests(OfflineTestCase):
    def test_template_requires_local_uuid(self):
        with self.assertRaises(ConfigurationError):
            Settings.from_text(example_text())

    def test_uuid_must_be_canonical_v4_and_match_prefix(self):
        for value in ("", "invalid", "0" * 32, TEST_UUID.upper(), TEST_UUID.replace("-", "")):
            with self.subTest(uuid=value), self.assertRaises(ConfigurationError):
                settings(PROJECT_UUID=value)
        with self.assertRaises(ConfigurationError):
            settings(MQTT_TOPIC_PREFIX="sis234/2026/3f8f8573-5640-4be0-adfa-0cc387447ade")

    def test_unsafe_or_unreplaced_prefixes_are_rejected(self):
        for prefix in (
            "", f"/sis234/{TEST_UUID}", f"sis234//{TEST_UUID}",
            f"sis234/{TEST_UUID}/", f"sis234/+/{TEST_UUID}",
            f"sis234/#/{TEST_UUID}", f"sis 234/{TEST_UUID}",
            f"sis234/\x00/{TEST_UUID}", f"{'a' * 201}/{TEST_UUID}",
            f"REEMPLAZAR_CON_UUID/{TEST_UUID}",
        ):
            with self.subTest(prefix=prefix), self.assertRaises(ConfigurationError):
                settings(MQTT_TOPIC_PREFIX=prefix)

    def test_custom_namespace_host_and_port_are_configurable(self):
        config = settings(
            MQTT_TOPIC_PREFIX=f"laboratorio/grupo-7/{TEST_UUID}",
            MQTT_HOST="localhost", MQTT_PORT="2883",
        )
        self.assertEqual(config.mqtt_host, "localhost")
        self.assertEqual(config.mqtt_port, 2883)
        self.assertEqual(config.topics.distance, f"laboratorio/grupo-7/{TEST_UUID}/telemetry/distance")
        self.assertTrue(config.topics.servo_command.endswith("/commands/servo"))
        self.assertTrue(config.topics.servo_state.endswith("/state/servo"))
        self.assertTrue(config.topics.led_command.endswith("/commands/leds"))
        self.assertTrue(config.topics.led_state.endswith("/state/leds"))
        self.assertNotEqual(config.topics.led_command, config.topics.servo_command)

    def test_clients_share_topics_but_have_distinct_ids(self):
        config = settings()
        identities = {config.client_id(role) for role in ClientRole}
        self.assertEqual(len(identities), 6)
        self.assertTrue(all(UUID(TEST_UUID).hex in value for value in identities))
        with self.assertRaises(ConfigurationError):
            config.client_id("unknown")

    def test_ports_times_and_intervals_are_positive_bounded_integers(self):
        for field, value in (
            ("MQTT_PORT", "0"), ("MQTT_PORT", "65536"),
            ("MQTT_PORT", "1883.0"), ("MQTT_PORT", "True"),
            ("MQTT_HOST", "mqtt://broker.hivemq.com"),
            ("MQTT_KEEPALIVE_S", "0"), ("MQTT_KEEPALIVE_S", "65536"),
            ("MQTT_RECONNECT_MIN_DELAY_S", "0"),
            ("MQTT_RECONNECT_MAX_DELAY_S", "4294968"),
            ("DISTANCE_PUBLISH_INTERVAL_MS", "-1"),
            ("DISTANCE_PUBLISH_INTERVAL_MS", "4294967296"),
            ("DISTANCE_STALE_AFTER_S", "0"),
        ):
            with self.subTest(field=field, value=value):
                with self.assertRaises(ConfigurationError):
                    settings(**{field: value})
        with self.assertRaises(ConfigurationError):
            settings(MQTT_RECONNECT_MIN_DELAY_S="33", MQTT_RECONNECT_MAX_DELAY_S="32")

    def test_servo_limits_can_be_reduced_but_not_inverted_or_expanded(self):
        config = settings(SERVO_MIN_ANGLE="15", SERVO_MAX_ANGLE="165")
        self.assertEqual(config.servo_limits, ServoLimits(15, 165))
        for low, high in (("-1", "180"), ("0", "181"), ("90", "90"), ("165", "15"), ("0.0", "180")):
            with self.subTest(low=low, high=high), self.assertRaises(ConfigurationError):
                settings(SERVO_MIN_ANGLE=low, SERVO_MAX_ANGLE=high)

    def test_missing_and_unknown_settings_fail_instead_of_using_hidden_defaults(self):
        missing = config_values()
        del missing["MQTT_PORT"]
        with self.assertRaises(ConfigurationError):
            Settings.from_mapping(missing)
        with self.assertRaises(ConfigurationError):
            settings(MQTT_P0RT="1883")

    def test_env_format_accepts_bom_comments_and_crlf(self):
        parsed = parse_env("\ufeff# Comentario\r\n MQTT_PORT = 1883 \r\n\r\n")
        self.assertEqual(parsed, {"MQTT_PORT": "1883"})

    def test_env_rejects_ambiguous_syntax_and_duplicates(self):
        for content in (
            "MQTT_PORT=1883\nMQTT_PORT=1884", "MQTT_PORT:1883",
            "export MQTT_PORT=1883", 'MQTT_PORT="1883"',
            "MQTT_PORT=1883 # comentario", "MQTT_PORT=${OTHER}",
        ):
            with self.subTest(content=content), self.assertRaises(ConfigurationError):
                parse_env(content)

    def test_settings_are_immutable(self):
        config = settings()
        with self.assertRaises(FrozenInstanceError):
            config.mqtt_port = 1884


class LocalConfigurationTests(LocalProjectTestCase):
    def test_init_generates_uuid_locally_and_synchronizes_all_outputs(self):
        config = initialize_local_config(self.root)
        self.assertEqual(config.project_uuid.version, 4)
        self.assertTrue(config.topic_prefix.endswith(str(config.project_uuid)))
        self.assertNotIn("REEMPLAZAR_CON_UUID", (self.root / ".env").read_text(encoding="utf-8"))
        check_local_config(self.root, config)
        self.assert_exported_values(config)

    def assert_exported_values(self, config):
        header = (self.root / "firmware/include/mqtt_config.local.h").read_text(encoding="utf-8")
        text_constants = {
            name: json.loads(value)
            for name, value in re.findall(r'constexpr char (\w+)\[\] = ("[^"]*");', header)
        }
        numbers = {
            name: int(value)
            for name, value in re.findall(r"constexpr (?:int|unsigned long) (\w+) = ([0-9]+)(?:UL)?;", header)
        }
        mobile = json.loads((self.root / "config/mobile.local.json").read_text(encoding="utf-8"))
        self.assertEqual(text_constants["MQTT_HOST"], config.mqtt_host)
        self.assertEqual(text_constants["MQTT_TOPIC_PREFIX"], mobile["mqtt"]["topic_prefix"])
        self.assertEqual(text_constants["MQTT_TOPIC_DISTANCE"], config.topics.distance)
        self.assertEqual(text_constants["MQTT_TOPIC_LED_COMMAND"], mobile["led_control"]["topic"])
        self.assertEqual(text_constants["MQTT_TOPIC_LED_STATE"], mobile["led_confirmation"]["topic"])
        self.assertEqual(text_constants["MQTT_TOPIC_SERVO_COMMAND"], config.topics.servo_command)
        self.assertEqual(text_constants["MQTT_TOPIC_SERVO_STATE"], config.topics.servo_state)
        self.assertEqual(numbers["MQTT_PORT"], mobile["mqtt"]["port"])
        self.assertEqual(mobile["led_control"]["colors"], ["red", "yellow", "green"])
        self.assertNotIn("servo_control", mobile)
        self.assertEqual(numbers["SERVO_MAX_ANGLE"], config.servo_limits.maximum)
        self.assertEqual(numbers["DISTANCE_PUBLISH_INTERVAL_MS"], config.distance_publish_interval_ms)
        self.assertEqual(numbers["MQTT_RECONNECT_MAX_DELAY_MS"], config.reconnect_max_delay_s * 1000)
        self.assertNotEqual(text_constants["MQTT_CLIENT_ID"], mobile["mqtt"]["client_id"])
        self.assertEqual(text_constants["MQTT_CLIENT_ID_SENSOR"], config.client_id(ClientRole.SENSOR))
        self.assertEqual(text_constants["MQTT_CLIENT_ID_ACTUATOR"], config.client_id(ClientRole.ACTUATOR))
        self.assertNotEqual(text_constants["MQTT_CLIENT_ID_SENSOR"], text_constants["MQTT_CLIENT_ID_ACTUATOR"])
        self.assertFalse(mobile["mqtt"]["retain"])

    def test_repeated_init_preserves_uuid_and_user_edits(self):
        original = self.write_env(SERVO_MIN_ANGLE="15", SERVO_MAX_ANGLE="165")
        content = (self.root / ".env").read_bytes()
        first = initialize_local_config(self.root)
        second = initialize_local_config(self.root)
        self.assertEqual(first, original)
        self.assertEqual(first.project_uuid, second.project_uuid)
        self.assertEqual((self.root / ".env").read_bytes(), content)

    def test_separate_projects_receive_different_uuids(self):
        first = initialize_local_config(self.root)
        other = self.root / "other"
        other.mkdir()
        (other / ".env.example").write_text(example_text(), encoding="utf-8")
        second = initialize_local_config(other)
        self.assertNotEqual(first.project_uuid, second.project_uuid)

    def test_init_does_not_replace_an_invalid_existing_env(self):
        env_file = self.root / ".env"
        env_file.write_text("MQTT_PORT=wrong\n", encoding="utf-8")
        original = env_file.read_bytes()
        with self.assertRaises(ConfigurationError):
            initialize_local_config(self.root)
        self.assertEqual(env_file.read_bytes(), original)
        self.assertFalse((self.root / "firmware").exists())

    def test_invalid_template_does_not_create_a_partial_env(self):
        template = example_text().replace("MQTT_PORT=1883", "MQTT_PORT=0")
        (self.root / ".env.example").write_text(template, encoding="utf-8")
        with self.assertRaises(ConfigurationError):
            initialize_local_config(self.root)
        self.assertFalse((self.root / ".env").exists())

    def test_sync_updates_shared_values_and_preserves_wifi_and_pins(self):
        initialize_local_config(self.root)
        local_header = self.root / "firmware/include/config.h"
        local_header.write_text("// Datos privados y pines del usuario\n", encoding="utf-8")
        original = local_header.read_bytes()
        device_header = self.root / "firmware/include/device_config.local.h"
        device_header.write_text(
            '#define LED_WIRING_CONFIRMED false\n#define LED_RED_PIN 25\n'
            'namespace device_config { constexpr char WIFI_SSID[] = "offline-test"; }\n',
            encoding="utf-8",
        )
        device_original = device_header.read_bytes()
        config = self.write_env(
            MQTT_HOST="localhost", MQTT_PORT="2883", SERVO_MIN_ANGLE="15",
            SERVO_MAX_ANGLE="165", MQTT_RECONNECT_MAX_DELAY_S="64",
            DISTANCE_PUBLISH_INTERVAL_MS="2000",
        )
        with self.assertRaises(ConfigurationError):
            check_local_config(self.root, config)
        sync_local_config(self.root, config)
        check_local_config(self.root, config)
        self.assert_exported_values(config)
        self.assertEqual(local_header.read_bytes(), original)
        self.assertEqual(device_header.read_bytes(), device_original)

    def test_check_reports_modified_or_missing_outputs_without_repairing_them(self):
        config = initialize_local_config(self.root)
        mobile = self.root / "config/mobile.local.json"
        mobile.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(ConfigurationError):
            check_local_config(self.root, config)
        self.assertEqual(mobile.read_text(encoding="utf-8"), "{}\n")
        mobile.unlink()
        with self.assertRaises(ConfigurationError):
            check_local_config(self.root, config)
        self.assertFalse(mobile.exists())

    def test_load_uses_explicit_path_and_ignores_environment_overrides(self):
        expected = self.write_env()
        other = self.root / "cwd"
        other.mkdir()
        original_directory = Path.cwd()
        try:
            os.chdir(other)
            with patch.dict(os.environ, {"MQTT_PORT": "9999", "SERVO_MAX_ANGLE": "5"}):
                self.assertEqual(Settings.load(self.root / ".env"), expected)
        finally:
            os.chdir(original_directory)

    def test_mcp_and_simulator_use_the_same_loader_and_different_identities(self):
        expected = self.write_env()
        mcp = runpy.run_path(str(PROJECT_ROOT / "mcp-server/iot_mcp/config.py"))
        simulator = runpy.run_path(str(PROJECT_ROOT / "simulator/iot_simulator/config.py"))
        self.assertIs(mcp["Settings"], simulator["Settings"])
        self.assertEqual(mcp["load_settings"](self.root / ".env"), expected)
        self.assertEqual(simulator["load_settings"](self.root / ".env"), expected)
        self.assertNotEqual(expected.client_id(mcp["CLIENT_ROLE"]), expected.client_id(simulator["CLIENT_ROLE"]))

    def test_cli_init_show_check_and_error_paths_are_offline(self):
        for action in ("init", "init", "show", "check", "sync"):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main(["--root", str(self.root), action])
            self.assertEqual(result, 0)
            self.assertEqual(stderr.getvalue(), "")
            if action == "show":
                summary = json.loads(stdout.getvalue())
                self.assertEqual(len(set(summary["client_ids"].values())), 6)
                self.assertTrue(summary["topics"]["servo_state"].endswith("/state/servo"))
                self.assertTrue(summary["topics"]["led_state"].endswith("/state/leds"))
        (self.root / ".env").unlink()
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(main(["--root", str(self.root), "check"]), 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertTrue(stderr.getvalue())
