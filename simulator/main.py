"""Punto de entrada reservado para el futuro simulador de dispositivo MQTT."""

import sys


def main() -> int:
    """Explica el estado de preparación sin conectar ni publicar mensajes."""
    print(
        "Etapa 2: configuración disponible; el simulador MQTT aún no está implementado.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
