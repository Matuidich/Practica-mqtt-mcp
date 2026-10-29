"""Adaptador MCP de la configuración compartida; no inicia recursos."""

from pathlib import Path

from iot_shared.config import ClientRole, DEFAULT_ENV_FILE, Settings


CLIENT_ROLE = ClientRole.MCP


def load_settings(env_file: Path | str = DEFAULT_ENV_FILE) -> Settings:
    """Lee explícitamente el mismo .env usado por simulador y exportaciones."""
    return Settings.load(env_file)
