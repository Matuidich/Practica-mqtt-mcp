"""Inicialización y exportación de archivos locales; sin dependencias de red."""

import json
from pathlib import Path
from uuid import uuid4

from .config import ClientRole, Settings
from .errors import ConfigurationError
from .topics import DISTANCE_SUFFIX, LED_COMMAND_SUFFIX, LED_STATE_SUFFIX


def render_firmware(settings: Settings) -> str:
    """Solo constantes compartidas: nunca escribe credenciales Wi-Fi ni pines."""
    texts = {
        "PROJECT_UUID": str(settings.project_uuid),
        "MQTT_HOST": settings.mqtt_host,
        "MQTT_TOPIC_PREFIX": settings.topic_prefix,
        "MQTT_CLIENT_ID": settings.client_id(ClientRole.FIRMWARE),
        "MQTT_CLIENT_ID_SENSOR": settings.client_id(ClientRole.SENSOR),
        "MQTT_CLIENT_ID_ACTUATOR": settings.client_id(ClientRole.ACTUATOR),
        "MQTT_TOPIC_DISTANCE": settings.topics.distance,
        "MQTT_TOPIC_LED_COMMAND": settings.topics.led_command,
        "MQTT_TOPIC_LED_STATE": settings.topics.led_state,
        "MQTT_TOPIC_SERVO_COMMAND": settings.topics.servo_command,
        "MQTT_TOPIC_SERVO_STATE": settings.topics.servo_state,
    }
    integers = {
        "MQTT_PORT": settings.mqtt_port,
        "MQTT_KEEPALIVE_S": settings.keepalive_s,
        "SERVO_MIN_ANGLE": settings.servo_limits.minimum,
        "SERVO_MAX_ANGLE": settings.servo_limits.maximum,
    }
    milliseconds = {
        "DISTANCE_PUBLISH_INTERVAL_MS": settings.distance_publish_interval_ms,
        "DISTANCE_STALE_AFTER_MS": settings.distance_stale_after_s * 1000,
        "MQTT_RECONNECT_MIN_DELAY_MS": settings.reconnect_min_delay_s * 1000,
        "MQTT_RECONNECT_MAX_DELAY_MS": settings.reconnect_max_delay_s * 1000,
    }
    lines = [
        "#pragma once", "", "// Generado desde .env; usar python -m iot_shared sync.",
        "// No editar ni versionar este archivo.", "namespace project_config {",
    ]
    for name, value in texts.items():
        lines.append(f"constexpr char {name}[] = {json.dumps(value)};")
    for name, value in integers.items():
        lines.append(f"constexpr int {name} = {value};")
    for name, value in milliseconds.items():
        lines.append(f"constexpr unsigned long {name} = {value}UL;")
    lines.extend(["}  // namespace project_config", ""])
    return "\n".join(lines)


def mobile_reference(settings: Settings) -> dict:
    """Referencia para la futura app, no un formato propietario importable."""
    return {
        "template_note": "Referencia generada desde .env; no importar en una app concreta.",
        "mqtt": {
            "host": settings.mqtt_host, "port": settings.mqtt_port,
            "transport": "tcp", "topic_prefix": settings.topic_prefix,
            "client_id": settings.client_id(ClientRole.MOBILE),
            "keepalive_s": settings.keepalive_s,
            "reconnect_min_delay_s": settings.reconnect_min_delay_s,
            "reconnect_max_delay_s": settings.reconnect_max_delay_s,
            "qos": 0, "retain": False,
        },
        "distance_widget": {
            "type": "gauge", "topic": settings.topics.distance,
            "topic_suffix": DISTANCE_SUFFIX, "json_field": "distance_cm",
            "unit": "cm", "display_min": 0, "display_max": 400,
            "stale_after_s": settings.distance_stale_after_s,
        },
        "led_control": {
            "type": "independent_switches", "topic": settings.topics.led_command,
            "topic_suffix": LED_COMMAND_SUFFIX, "json_field": "leds",
            "command_id_field": "command_id",
            "colors": ["red", "yellow", "green"],
            "omitted_colors": "unchanged",
            "exclusive_requires_all_colors": True,
            "all_off": {"red": False, "yellow": False, "green": False},
        },
        "led_confirmation": {
            "topic": settings.topics.led_state, "topic_suffix": LED_STATE_SUFFIX,
            "json_field": "leds", "command_id_field": "command_id",
            "status_field": "status", "expected_status": "applied",
        },
    }


def generated_files(root: Path, settings: Settings) -> dict[Path, str]:
    return {
        root / "firmware/include/mqtt_config.local.h": render_firmware(settings),
        root / "config/mobile.local.json": json.dumps(
            mobile_reference(settings), indent=2, ensure_ascii=False
        ) + "\n",
    }


def sync_local_config(root: Path, settings: Settings) -> None:
    """Actualiza exclusivamente los dos archivos derivados, sin tocar Wi-Fi."""
    for path, content in generated_files(root, settings).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8", newline="\n")


def check_local_config(root: Path, settings: Settings) -> None:
    """Detecta cambios sin sincronizar; no modifica ningún archivo."""
    for path, expected in generated_files(root, settings).items():
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            raise ConfigurationError(
                f"Archivo desactualizado: {path.relative_to(root)}; ejecutar sync."
            )


def initialize_local_config(root: Path) -> Settings:
    """Genera UUID v4 una vez; conserva un .env existente, incluso si es inválido."""
    env_file = root / ".env"
    if env_file.exists():
        settings = Settings.load(env_file)
    else:
        template = (root / ".env.example").read_text(encoding="utf-8-sig")
        content = template.replace("REEMPLAZAR_CON_UUID", str(uuid4()))
        settings = Settings.from_text(content)
        # El modo x impide sobrescribir un .env creado mientras se validaba.
        with env_file.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    sync_local_config(root, settings)
    return settings
