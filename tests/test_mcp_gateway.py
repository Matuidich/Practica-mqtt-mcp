"""MQTT, concurrencia y confirmaciones con transporte falso y sockets bloqueados."""

from concurrent.futures import ThreadPoolExecutor
import itertools
import json
import threading
import time
from unittest.mock import Mock
from uuid import UUID

from tests.support import OfflineTestCase, settings
from iot_mcp.mqtt_gateway import COMMAND_HISTORY_SIZE, MqttGateway, create_paho_client
from iot_mcp.offline_check import MemoryMqttClient
from iot_mcp.tools import DeviceTools
from iot_shared.errors import ValidationError
from iot_shared.messages import DistanceReading, LedCommand, LedState, LedValues


class MqttGatewayTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.settings = settings()
        self.mqtt = MemoryMqttClient(self.settings)
        self.gateway = MqttGateway(self.settings, client_factory=lambda _: self.mqtt)
        self.addCleanup(self.gateway.close)
        self.gateway.start()
        self.tools = DeviceTools(self.gateway)

    def emit_state(self, command_id, values=LedValues(), *, retain=False):
        state = LedState(values, command_id, "fixture-esp32", 200)
        self.mqtt.emit(self.settings.topics.led_state, state.to_json(), retain=retain)
        return state

    def test_construction_startup_identity_and_shutdown_are_explicit(self):
        factory = Mock()
        gateway = MqttGateway(self.settings, client_factory=factory)
        self.assertEqual(gateway.get_last_distance()["status"], "unknown")
        self.assertEqual(gateway.get_led_state()["status"], "unknown")
        factory.assert_not_called()
        self.gateway.start()
        self.assertEqual(self.mqtt.connect_calls, 1)
        self.assertEqual(self.mqtt.delays, (self.settings.reconnect_min_delay_s,
                                          self.settings.reconnect_max_delay_s))
        self.assertEqual(self.mqtt.connection, (self.settings.mqtt_host,
                                              self.settings.mqtt_port, self.settings.keepalive_s))
        self.gateway.close()
        self.gateway.close()
        self.assertTrue(self.mqtt.stopped)
        self.assertEqual(self.mqtt.disconnect_calls, 1)

    def test_real_paho_client_can_be_constructed_without_opening_a_socket(self):
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.skipTest("Paho no instalado; usar .venv e instalar requirements.txt")
        client = create_paho_client(self.settings)
        self.assertEqual(client._client_id.decode(), self.settings.client_id("mcp"))
        self.assertEqual(client._protocol, mqtt.MQTTv311)
        self.assertEqual(client.callback_api_version, mqtt.CallbackAPIVersion.VERSION2)
        self.assertFalse(client.is_connected())

    def test_distance_age_staleness_and_new_observation_after_reconnect(self):
        now = [10.0]
        self.gateway._clock = lambda: now[0]
        reading = DistanceReading(12.75, "esp32-01", 20)
        self.mqtt.emit(self.settings.topics.distance, reading.to_json())
        now[0] += 1
        result = self.tools.get_last_distance()
        self.assertEqual(result["status"], "fresh")
        self.assertEqual(result["age_s"], 1)
        self.assertEqual(result["reading"]["distance_cm"], 12.75)
        self.assertIn("received_at", result)
        now[0] += self.settings.distance_stale_after_s
        self.assertEqual(self.tools.get_last_distance()["status"], "stale")
        self.mqtt.lose_connection()
        self.mqtt.connect()
        self.assertFalse(self.tools.get_last_distance()["current_connection"])
        self.mqtt.emit(self.settings.topics.distance, reading.to_json())
        self.assertEqual(self.tools.get_last_distance()["status"], "fresh")

    def test_all_combinations_and_partial_changes_are_confirmed(self):
        for values in itertools.product((False, True), repeat=3):
            result = self.tools.set_leds(dict(zip(("red", "yellow", "green"), values)))
            self.assertEqual(result["status"], "applied")
            self.assertTrue(result["confirmation_verified"])
            self.assertEqual(tuple(result["confirmation"]["leds"].values()), values)
            self.assertEqual(result["confirmation"]["command_id"], result["command_id"])
        result = self.tools.set_led("red", False)
        self.assertEqual(result["confirmation"]["leds"], {"red": False, "yellow": True, "green": True})
        for color in ("red", "yellow", "green"):
            result = self.tools.set_only_led(color)
            self.assertEqual(result["confirmation"]["leds"], {name: name == color for name in ("red", "yellow", "green")})
        result = self.tools.turn_off_all_leds()
        self.assertFalse(any(result["confirmation"]["leds"].values()))
        for topic, payload, qos, retain in self.mqtt.publications:
            self.assertEqual(topic, self.settings.topics.led_command)
            self.assertEqual(qos, 0)
            self.assertFalse(retain)
            self.assertEqual(UUID(json.loads(payload)["command_id"]).version, 4)

    def test_publication_acceptance_without_ack_times_out_without_claiming_applied(self):
        self.mqtt.auto_confirm = False
        result = self.tools.set_led("red", True, "lost-ack", timeout_s=0.02)
        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["mqtt_accepted"])
        self.assertFalse(result["confirmation_verified"])
        self.assertIsNone(result["confirmation"])
        self.emit_state("lost-ack", LedValues(red=True))
        self.assertEqual(self.tools.get_led_state()["status"], "unknown")
        self.assertEqual(self.tools.set_led("red", True, "lost-ack"), result)
        self.assertEqual(len(self.mqtt.publications), 1)

    def test_wrong_id_mobile_observation_does_not_confirm_a_pending_command(self):
        self.mqtt.on_publish_hook = lambda _: self.emit_state("mobile-command", LedValues(green=True))
        result = self.tools.set_led("red", True, "mcp-order", timeout_s=0.02)
        self.assertEqual(result["status"], "timeout")
        observed = self.tools.get_led_state()
        self.assertEqual(observed["state"]["command_id"], "mobile-command")
        self.assertEqual(observed["state"]["leds"]["green"], True)

    def test_same_id_with_wrong_values_is_rejected(self):
        self.mqtt.on_publish_hook = lambda cmd: self.emit_state(cmd.command_id, LedValues())
        with self.assertLogs("iot_mcp.mqtt_gateway", level="WARNING"):
            result = self.tools.set_led("red", True, "mismatch")
        self.assertEqual(result["status"], "confirmation_mismatch")
        self.assertFalse(result["confirmation_verified"])
        self.assertIsNone(result["confirmation"])

    def test_retained_malformed_and_wrong_topic_messages_are_ignored(self):
        before = self.tools.get_last_distance()
        with self.assertLogs("iot_mcp.mqtt_gateway", level="WARNING"):
            self.mqtt.emit(self.settings.topics.distance, '{"distance_cm":true}')
            self.mqtt.emit(self.settings.topics.distance, DistanceReading(99, "esp32", 1).to_json(), retain=True)
            self.emit_state("old", retain=True)
        self.mqtt.emit("other/telemetry/distance", DistanceReading(99, "esp32", 1).to_json())
        self.assertEqual(self.tools.get_last_distance()["reading"], before["reading"])
        self.assertEqual(self.tools.get_led_state()["status"], "unknown")
        self.mqtt.on_publish_hook = lambda cmd: self.emit_state(cmd.command_id, LedValues(red=True), retain=True)
        with self.assertLogs("iot_mcp.mqtt_gateway", level="WARNING"):
            result = self.tools.set_led("red", True, "retained-ack", timeout_s=0.02)
        self.assertEqual(result["status"], "timeout")

    def test_duplicate_completed_command_returns_cached_result_and_conflicts_fail(self):
        original = self.tools.set_led("red", True, "dedupe")
        result = self.tools.set_led("red", True, "dedupe")
        self.assertEqual(result, original)
        self.assertEqual(len(self.mqtt.publications), 1)
        conflict = self.tools.set_led("red", False, "dedupe")
        self.assertEqual(conflict["status"], "conflicting_id")
        self.assertEqual(len(self.mqtt.publications), 1)
        result["confirmation"]["leds"]["red"] = False
        self.assertTrue(self.tools.set_led("red", True, "dedupe")["confirmation"]["leds"]["red"])

    def test_replayed_ack_does_not_overwrite_newer_mobile_state(self):
        original = self.tools.set_led("red", True, "old-mcp")
        self.emit_state("new-mobile", LedValues(green=True))
        self.mqtt.emit(self.settings.topics.led_state, json.dumps(original["confirmation"]))
        self.assertEqual(self.tools.get_led_state()["state"]["command_id"], "new-mobile")

    def test_concurrent_duplicate_waits_for_same_ack_and_other_commands_are_busy(self):
        published = threading.Event()
        self.mqtt.on_publish_hook = lambda _: published.set()
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(self.tools.set_led, "red", True, "pending", 2.0)
            self.assertTrue(published.wait(1))
            duplicate = executor.submit(self.tools.set_led, "red", True, "pending", 2.0)
            self.assertEqual(self.tools.set_led("green", True, "other")["status"], "busy")
            self.assertEqual(self.tools.set_led("red", False, "pending")["status"], "conflicting_id")
            self.emit_state("pending", LedValues(red=True))
            self.assertEqual(first.result(2), duplicate.result(2))
        self.assertEqual(len(self.mqtt.publications), 1)

    def test_disconnect_interrupts_wait_and_reconnect_resubscribes_without_republishing(self):
        self.mqtt.on_publish_hook = lambda _: self.mqtt.lose_connection()
        started = time.monotonic()
        result = self.tools.set_led("red", True, "interrupted", timeout_s=30)
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(result["status"], "disconnected")
        self.assertFalse(result["confirmation_verified"])
        self.mqtt.connect()
        self.assertEqual(len(self.mqtt.subscriptions), 2)
        self.assertEqual(self.mqtt.subscriptions[-1], [(self.settings.topics.distance, 0),
                                                     (self.settings.topics.led_state, 0)])
        self.assertEqual(self.tools.set_led("red", True, "interrupted"), result)
        self.assertEqual(len(self.mqtt.publications), 1)
        self.assertEqual(self.tools.get_last_distance()["status"], "stale")

    def test_publish_failure_and_shutdown_never_claim_applied(self):
        self.mqtt.publish_rc = 4
        result = self.tools.set_led("red", True, "failed")
        self.assertEqual(result["status"], "publish_failed")
        self.assertFalse(result["mqtt_accepted"])
        self.mqtt.publish_rc = 0
        self.mqtt.on_publish_hook = lambda _: self.gateway.close()
        result = self.tools.set_led("red", True, "shutdown")
        self.assertEqual(result["status"], "disconnected")
        self.assertTrue(self.mqtt.stopped)

    def test_disconnected_gateway_does_not_queue_commands(self):
        self.mqtt.lose_connection()
        result = self.tools.set_led("green", True)
        self.assertEqual(result["status"], "disconnected")
        self.assertFalse(result["mqtt_accepted"])
        self.mqtt.connect()
        self.assertEqual(self.mqtt.publications, [])

    def test_subscription_ack_is_required_before_publishing(self):
        self.mqtt.lose_connection()
        self.mqtt.connect(suback=False)
        self.assertEqual(self.tools.get_led_state()["connection_status"], "subscribing")
        self.assertEqual(self.tools.set_led("red", True)["status"], "disconnected")
        self.mqtt.on_subscribe(self.mqtt, None, self.mqtt.mid + 1, [0, 0], None)
        self.assertFalse(self.tools.get_led_state()["connected"])
        with self.assertLogs("iot_mcp.mqtt_gateway", level="WARNING"):
            self.mqtt.on_subscribe(self.mqtt, None, self.mqtt.mid, [0, 128], None)
        self.assertEqual(self.tools.get_led_state()["connection_status"], "subscription_failed")

    def test_connect_failures_remain_unavailable_until_success(self):
        with self.assertLogs("iot_mcp.mqtt_gateway", level="WARNING"):
            self.mqtt.on_connect_fail(self.mqtt, None)
            self.mqtt.connect(reason_code=5)
        self.assertFalse(self.tools.get_led_state()["connected"])
        self.assertEqual(self.tools.set_led("red", True)["status"], "disconnected")
        self.mqtt.connect()
        self.assertTrue(self.tools.get_led_state()["connected"])

    def test_bounded_history_retains_only_last_128_results(self):
        for index in range(COMMAND_HISTORY_SIZE + 2):
            self.tools.set_led("red", True, f"bounded-{index}")
        self.assertEqual(len(self.gateway._history), COMMAND_HISTORY_SIZE)
        before = len(self.mqtt.publications)
        self.tools.set_led("red", True, f"bounded-{COMMAND_HISTORY_SIZE + 1}")
        self.assertEqual(len(self.mqtt.publications), before)

    def test_invalid_tool_inputs_and_timeouts_do_not_publish(self):
        for call in (lambda: self.tools.set_led("blue", True),
                     lambda: self.tools.set_led("red", 1),
                     lambda: self.tools.set_leds({}),
                     lambda: self.tools.set_leds({"red": "true"}),
                     lambda: self.tools.set_led("red", True, "")):
            with self.assertRaises(ValidationError):
                call()
        for timeout in (0, -1, 31, True, "5", float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(ValidationError):
                self.tools.set_led("red", True, timeout_s=timeout)
        self.assertEqual(self.mqtt.publications, [])

    def test_startup_failure_closes_transport(self):
        self.gateway.close()
        self.mqtt.loop_rc = 1
        with self.assertRaises(RuntimeError):
            self.gateway.start()
        self.assertTrue(self.mqtt.stopped)
        self.assertEqual(self.gateway.get_led_state()["connection_status"], "stopped")
