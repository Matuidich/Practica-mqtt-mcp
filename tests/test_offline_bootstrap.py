"""Importaciones inertes y entradas explícitas, siempre sin broker."""

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import runpy
import unittest
from unittest.mock import Mock, patch

from tests.support import OfflineTestCase, network_forbidden


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = (
    PROJECT_ROOT / "mcp-server" / "main.py",
    PROJECT_ROOT / "simulator" / "main.py",
)


class OfflineBootstrapTests(OfflineTestCase):
    def test_imports_are_silent_and_do_not_use_network(self):
        for entrypoint in ENTRYPOINTS:
            with self.subTest(component=entrypoint.parent.name):
                stdout, stderr = io.StringIO(), io.StringIO()
                with (
                    network_forbidden(),
                    redirect_stdout(stdout),
                    redirect_stderr(stderr),
                ):
                    runpy.run_path(str(entrypoint), run_name="offline_import")
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "")

    def test_simulator_preparation_still_refuses_startup(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with (redirect_stdout(stdout), redirect_stderr(stderr),
              self.assertRaises(SystemExit) as stopped):
            runpy.run_path(str(ENTRYPOINTS[1]), run_name="__main__")
        self.assertNotEqual(stopped.exception.code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertTrue(stderr.getvalue().strip())

    def test_mcp_missing_configuration_reports_only_to_stderr(self):
        entry = runpy.run_path(str(ENTRYPOINTS[0]), run_name="offline_import")
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = entry["main"](["--env-file", str(PROJECT_ROOT / "tests" / "missing.env")])
        self.assertEqual(result, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("No se pudo", stderr.getvalue())

    def test_mcp_entrypoint_delegates_to_stdio_with_explicit_configuration(self):
        from tests.support import settings
        entry = runpy.run_path(str(ENTRYPOINTS[0]), run_name="offline_import")
        server = Mock()
        with (patch("iot_mcp.config.load_settings", return_value=settings()) as load,
              patch("iot_mcp.server.build_server", return_value=server)):
            self.assertEqual(entry["main"](["--env-file", "fixture.env"]), 0)
        load.assert_called_once_with(Path("fixture.env"))
        server.run.assert_called_once_with(transport="stdio", show_banner=False, log_level="WARNING")


if __name__ == "__main__":
    unittest.main()
