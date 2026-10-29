"""Regresión de la referencia histórica SG90; no prueba el actuador LED activo."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.support import OfflineTestCase, PROJECT_ROOT


@unittest.skipUnless(shutil.which("g++"), "G++ no disponible para pruebas C++ en el PC")
class ActuatorApplicationTests(OfflineTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        cls.confirmed = cls.compile(directory, confirmed=True)
        cls.blocked = cls.compile(directory, confirmed=False)

    @classmethod
    def compile(cls, directory, *, confirmed):
        source = PROJECT_ROOT / "firmware/test/actuator/test_actuator.cpp"
        executable = directory / ("actuator-confirmed.exe" if confirmed else "actuator-blocked.exe")
        result = subprocess.run(
            [shutil.which("g++"), "-std=c++11", "-Wall", "-Wextra", "-Werror", "-pedantic",
             f"-DTEST_ACTUATOR_WIRING_CONFIRMED={int(confirmed)}",
             "-I", str(source.parent / "fakes"),
             "-I", str(PROJECT_ROOT / "firmware/include"),
             str(source), "-o", str(executable)],
            capture_output=True, text=True, timeout=90,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return executable

    def run_scenario(self, scenario, *, confirmed=True):
        executable = self.confirmed if confirmed else self.blocked
        result = subprocess.run(
            [str(executable), scenario], capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_startup_does_not_attach_or_move_automatically(self):
        self.run_scenario("startup")

    def test_pwm_holds_after_ramp_settle_and_applied(self):
        self.run_scenario("hold")

    def test_consecutive_commands_keep_pwm_without_reattaching(self):
        self.run_scenario("consecutive")

    def test_duplicate_and_busy_commands_preserve_pwm_and_confirmation(self):
        self.run_scenario("duplicates")

    def test_invalid_messages_and_angles_do_not_change_pwm(self):
        self.run_scenario("validation")

    def test_attach_failure_disables_output_without_applied_and_allows_retry(self):
        self.run_scenario("failure")

    def test_disconnect_keeps_pwm_and_pending_confirmation_until_reconnected(self):
        self.run_scenario("disconnected")

    def test_failed_publications_retry_with_backoff_while_holding_pwm(self):
        self.run_scenario("publish-retry")

    def test_clock_wrap_preserves_settle_confirmation_and_pwm(self):
        self.run_scenario("clock-wrap")

    def test_unconfirmed_wiring_blocks_pwm_and_false_confirmation(self):
        self.run_scenario("wiring", confirmed=False)
