"""Entrada stdio de FastMCP. Solo ejecutar main() inicia recursos."""

import argparse
import logging
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    # Rutas absolutas: Codex puede lanzar este archivo desde cualquier carpeta.
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from iot_shared.errors import ConfigurationError
    from iot_mcp.config import load_settings

    parser = argparse.ArgumentParser(description="Puente MCP/MQTT SIS-234 para distancia y tres LEDs.")
    parser.add_argument("--env-file", type=Path, default=project_root / ".env",
                        help="Archivo .env explícito; no se usan sobrescrituras del proceso.")
    parser.add_argument("--check-offline", action="store_true",
                        help="Comprueba arranque y herramientas con MQTT falso, sin broker ni hardware.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    try:
        if args.check_offline:
            from iot_mcp.offline_check import run_check
            run_check()
            print("MCP local OK: arranque, seis herramientas y confirmaciones con MQTT falso; sin red.",
                  file=sys.stderr)
        else:
            from iot_mcp.server import build_server
            server = build_server(load_settings(args.env_file))
            server.run(transport="stdio", show_banner=False, log_level="WARNING")
        return 0
    except (ConfigurationError, ImportError, OSError, RuntimeError, ValueError) as error:
        print(f"No se pudo iniciar/verificar MCP: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
