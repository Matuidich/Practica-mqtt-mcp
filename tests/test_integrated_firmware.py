"""Entorno integrated real con ISR, colas y tarea MQTT sustituidas en el PC."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from iot_shared.messages import DistanceReading, LedState, LedValues
from tests.support import OfflineTestCase, PROJECT_ROOT


@unittest.skipUnless(shutil.which("g++"), "G++ no disponible para pruebas C++ en el PC")
class IntegratedFirmwareTests(OfflineTestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        cls.enabled = cls.compile(directory, True)
        cls.blocked = cls.compile(directory, False)

    @classmethod
    def compile(cls, directory, enabled):
        folder = PROJECT_ROOT / "firmware/test/integrated"
        source = folder / "test_integrated.cpp"
        executable = directory / ("enabled.exe" if enabled else "blocked.exe")
        command = [shutil.which("g++"), "-std=c++11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                   "-I", str(folder / "fakes"), "-I", str(PROJECT_ROOT / "firmware/include")]
        if enabled:
            command.append("-DLED_WIRING_CONFIRMED=true")
        dependencies = subprocess.run(command + [str(source), "-MM"],
                                      capture_output=True, text=True, timeout=30)
        if (dependencies.returncode or "device_config.local.h" in dependencies.stdout or
                "mqtt_config.local.h" in dependencies.stdout):
            raise AssertionError("La prueba integrated debe usar solo configuración ficticia.")
        result = subprocess.run(command + [str(source), "-o", str(executable)],
                                capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return executable

    def scenario(self, name, *, enabled=True):
        executable = self.enabled if enabled else self.blocked
        result = subprocess.run([str(executable), name], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_unconfirmed_leds_stay_blocked_while_distance_is_published(self):
        self.scenario("blocked", enabled=False)

    def test_led_commands_are_confirmed_while_waiting_for_echo_on_one_mqtt_client(self):
        self.scenario("coexistence")

    def test_slow_network_keeps_sensor_running_and_sends_only_latest_fresh_sample(self):
        self.scenario("latest")

    def test_reconnection_preserves_led_ack_and_discards_offline_measurements(self):
        self.scenario("reconnect")

    def test_failed_led_ack_retries_without_blocking_telemetry(self):
        self.scenario("retry")

    def test_invalid_duplicate_conflicting_and_busy_commands_preserve_outputs(self):
        self.scenario("validation")

    def test_interrupt_sensor_bounds_timeouts_late_poll_and_micros_wrap(self):
        self.scenario("sonar")
        self.scenario("no-echo")

    def test_millis_wrap_preserves_measurement_schedule_and_telemetry(self):
        self.scenario("wrap")

    def test_queue_or_task_allocation_failure_keeps_outputs_off_and_network_stopped(self):
        self.scenario("fail-queue")
        self.scenario("fail-task")

    def test_integrated_messages_match_existing_python_contracts(self):
        lines = self.scenario("contracts").splitlines()
        self.assertEqual(len(lines), 3)
        led_states, distances = [], []
        for line in lines:
            topic, payload = line.split("\t", 1)
            if topic == "offline/state/leds":
                led_states.append(LedState.from_json(payload))
            else:
                self.assertEqual(topic, "offline/telemetry/distance")
                distances.append(DistanceReading.from_json(payload))
        self.assertEqual(distances[0].distance_cm, 100)
        self.assertEqual(distances[0].device_id, "offline-sensor")
        self.assertEqual([state.command_id for state in led_states], ["coexist", "yellow"])
        self.assertEqual([state.leds for state in led_states],
                         [LedValues(True, False, False), LedValues(True, True, False)])
