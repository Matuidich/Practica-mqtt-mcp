"""Adaptador del simulador para la misma configuración usada por MCP y firmware."""

from pathlib import Path

from iot_shared.config import ClientRole, DEFAULT_ENV_FILE, Settings


CLIENT_ROLE = ClientRole.SIMULATOR


def load_settings(env_file: Path | str = DEFAULT_ENV_FILE) -> Settings:
    """Carga configuración sin crear clientes MQTT ni simular hardware."""
    return Settings.load(env_file)
