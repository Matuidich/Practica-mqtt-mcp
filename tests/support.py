"""Aislamiento de red y proyectos temporales para probar sin datos locales."""

from contextlib import ExitStack, contextmanager
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from iot_shared.config import Settings, parse_env


PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Permite probar las fuentes sin exigir una instalación editable del proyecto.
MCP_SOURCE_ROOT = PROJECT_ROOT / "mcp-server"
if str(MCP_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_SOURCE_ROOT))
TEST_UUID = "123e4567-e89b-42d3-a456-426614174000"


def example_text() -> str:
    return (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")


def config_values(**updates) -> dict[str, str]:
    values = parse_env(example_text().replace("REEMPLAZAR_CON_UUID", TEST_UUID))
    values.update(updates)
    return values


def settings(**updates) -> Settings:
    return Settings.from_mapping(config_values(**updates))


@contextmanager
def network_forbidden():
    """Un intento de crear sockets o resolver nombres falla antes de usar la red."""
    with ExitStack() as stack:
        for target in (
            "socket.socket", "socket.create_connection", "socket.getaddrinfo",
            "socket.gethostbyname", "socket.gethostbyname_ex",
        ):
            stack.enter_context(
                patch(target, side_effect=AssertionError("Red no permitida"))
            )
        yield


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(network_forbidden())


class LocalProjectTestCase(OfflineTestCase):
    def setUp(self):
        super().setUp()
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(directory)
        (self.root / ".env.example").write_text(example_text(), encoding="utf-8")

    def write_env(self, **updates) -> Settings:
        values = config_values(**updates)
        content = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
        (self.root / ".env").write_text(content, encoding="utf-8")
        return Settings.load(self.root / ".env")
