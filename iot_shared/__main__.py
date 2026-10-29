"""CLI local: genera, sincroniza e inspecciona configuración sin conectar a MQTT."""

import argparse
import json
from pathlib import Path
import sys

from .config import ClientRole, PROJECT_ROOT, Settings
from .errors import ConfigurationError
from .local_config import (
    check_local_config, initialize_local_config, sync_local_config,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("action", choices=("init", "sync", "check", "show"))
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    try:
        if arguments.action == "init":
            settings = initialize_local_config(root)
        else:
            settings = Settings.load(root / ".env")
            if arguments.action == "sync":
                sync_local_config(root, settings)
            elif arguments.action == "check":
                check_local_config(root, settings)
        if arguments.action == "show":
            print(json.dumps({
                "project_uuid": str(settings.project_uuid),
                "topic_prefix": settings.topic_prefix,
                "topics": {
                    "distance": settings.topics.distance,
                    "led_command": settings.topics.led_command,
                    "led_state": settings.topics.led_state,
                    "servo_command": settings.topics.servo_command,
                    "servo_state": settings.topics.servo_state,
                },
                "client_ids": {role.value: settings.client_id(role) for role in ClientRole},
                "servo_limits": {
                    "minimum": settings.servo_limits.minimum,
                    "maximum": settings.servo_limits.maximum,
                },
            }, indent=2))
        else:
            print(f"Configuración local válida ({arguments.action}): {settings.topic_prefix}")
        return 0
    except (ConfigurationError, OSError, UnicodeError) as error:
        print(f"Error de configuración: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
