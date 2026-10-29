"""Herramientas de validación SIS-234. Solo capture --live puede abrir MQTT."""

import argparse
import csv
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import sys
import time

from iot_shared.config import DEFAULT_ENV_FILE, Settings
from iot_shared.errors import ConfigurationError
from iot_shared.messages import DistanceReading
from .collector import DistanceObserver, Journal, capture_window, utc_now
from .reporting import (LATENCY_FIELDS, aggregate_accuracy, build_report, latency_report,
                        positive, read_jsonl)


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def positive_arg(value):
    try:
        return positive(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Comprueba configuración y Paho SIN red.")
    check.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    capture = commands.add_parser("capture", help="Observa solo telemetry/distance; requiere --live.")
    capture.add_argument("--live", action="store_true", help="Habilita explícitamente esta captura real MQTT.")
    capture.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    capture.add_argument("--output", type=Path, required=True, help="Carpeta NUEVA para conservar evidencias.")
    capture.add_argument("--purpose", choices=("stability", "frequency", "accuracy", "reconnect"), default="stability")
    capture.add_argument("--duration-s", type=positive_arg, default=600)
    capture.add_argument("--ready-timeout-s", type=positive_arg, default=30)
    capture.add_argument("--gap-s", type=positive_arg, default=3,
                         help="Silencio a señalar en segundos; NO es un umbral de aprobación (por defecto 3).")
    capture.add_argument("--device-id", required=True, help="device_id del sensor, por ejemplo sensor-01.")
    capture.add_argument("--reference-cm", type=positive_arg, help="Distancia medida con cinta, solo para exactitud.")
    capture.add_argument("--reference-uncertainty-cm", type=positive_arg,
                         help="Incertidumbre estimada de colocación/cinta (no se inventa si falta).")
    capture.add_argument("--notes", default="", help="Condiciones, geometría, red y evidencia externa.")
    report = commands.add_parser("report", help="Recalcula un reporte desde los registros, SIN red.")
    report.add_argument("--run", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True, help="JSON nuevo, nunca sobrescribe resultados.")
    mark = commands.add_parser("mark", help="Marca una acción MANUAL en otra terminal; SIN red.")
    mark.add_argument("--run", type=Path, required=True)
    mark.add_argument("--trial-id", required=True)
    mark.add_argument("--event", choices=("cut", "restored"), required=True)
    mark.add_argument("--cause", choices=("wifi", "mqtt"), required=True)
    mark.add_argument("--uncertainty-s", type=positive_arg, help="Incertidumbre humana estimada de esta marca.")
    mark.add_argument("--wait-enter", action="store_true",
                      help="Prepara la marca y toma el instante al pulsar Enter junto a la acción física.")
    mark.add_argument("--notes", default="")
    accuracy = commands.add_parser("accuracy", help="Agrupa puntos con referencia, SIN red.")
    accuracy.add_argument("--run", type=Path, action="append", required=True)
    accuracy.add_argument("--output", type=Path, required=True)
    templates = commands.add_parser("templates", help="Crea planilla vacía de latencia y ficha de condiciones.")
    templates.add_argument("--output", type=Path, required=True)
    latency = commands.add_parser("latency", help="Calcula latencia FÍSICA desde fotogramas anotados; SIN red.")
    latency.add_argument("--input", type=Path, required=True)
    latency.add_argument("--output", type=Path, required=True)
    return root


def run_capture(args):
    if not args.live:
        raise ValueError("No se abrió ninguna conexión. Para una prueba real, especificar capture --live.")
    if args.purpose == "accuracy" and args.reference_cm is None:
        raise ValueError("Exactitud requiere --reference-cm medido con cinta antes de capturar.")
    if args.purpose != "accuracy" and (args.reference_cm is not None or args.reference_uncertainty_cm is not None):
        raise ValueError("Las referencias con cinta corresponden a --purpose accuracy.")
    DistanceReading(1, args.device_id, 0)
    settings = Settings.load(args.env_file)
    paho_version = version("paho-mqtt")
    metadata = {
        "mode": "live_mqtt_observation", "purpose": args.purpose,
        "device_id": args.device_id, "requested_duration_s": args.duration_s,
        "gap_s": args.gap_s, "reference_cm": args.reference_cm,
        "reference_uncertainty_cm": args.reference_uncertainty_cm,
        "configured_interval_ms_reference_only": settings.distance_publish_interval_ms,
        "configured_keepalive_s_reference_only": settings.keepalive_s,
        "configured_reconnect_min_s_reference_only": settings.reconnect_min_delay_s,
        "configured_reconnect_max_s_reference_only": settings.reconnect_max_delay_s,
        "distance_topic": settings.topics.distance, "qos": 0,
        "paho_mqtt_version": paho_version, "python_version": sys.version.split()[0],
        "notes": args.notes,
    }
    journal = Journal(args.output, metadata)
    observer = DistanceObserver(settings, args.device_id, journal)
    failure = None
    try:
        capture_window(observer, journal, args.duration_s, args.ready_timeout_s)
    except Exception as error:
        failure = error
    finally:
        journal.close()
    report = build_report(args.output)
    save_json(args.output / "summary.json", report)
    print(f"Reporte conservado en {args.output / 'summary.json'}")
    if failure:
        raise failure
    if report.get("data_observed"):
        print(f"Lecturas únicas: {report['unique_readings']}; frecuencia observada: "
              f"{report['frequency_hz_whole_window']:.6f} Hz; estado: {report['measurement_status']}.")
    else:
        print("No se observaron lecturas válidas. Esto no constituye una validación exitosa.")
    return 0 if report.get("data_observed") and report["measurement_status"] == "completed" else 2


def add_marker(args):
    metadata = json.loads((args.run / "session.json").read_text(encoding="utf-8"))
    if metadata["mode"] != "live_mqtt_observation" or metadata["purpose"] != "reconnect":
        raise ValueError("Las marcas requieren una captura real con --purpose reconnect.")
    def active_window_start():
        events = read_jsonl(args.run / "events.jsonl")
        if not any(e["kind"] == "window_start" for e in events) or any(
                e["kind"] in {"window_end", "session_end"} for e in events):
            raise ValueError("La ventana no está activa; no se añaden marcas retroactivas.")
        markers = read_jsonl(args.run / "markers.jsonl")
        trial = [m for m in markers if m["trial_id"] == args.trial_id]
        if args.event == "cut":
            if trial or any(not any(n["trial_id"] == m["trial_id"] and n["event"] == "restored"
                                    for n in markers) for m in markers if m["event"] == "cut"):
                raise ValueError("Usar un trial-id nuevo y cerrar primero el corte anterior con restored.")
        elif len(trial) != 1 or trial[0]["event"] != "cut" or trial[0]["cause"] != args.cause:
            raise ValueError("restored requiere un cut previo del mismo trial-id y causa.")
        return next(e["elapsed_s"] for e in events if e["kind"] == "window_start")

    active_window_start()
    if args.wait_enter:
        input(f"Preparar {args.event}; pulsar Enter al realizar la acción manual (no se automatiza): ")
    # time.monotonic de Python 3.11 usa el mismo reloj para procesos en este PC.
    elapsed = time.monotonic() - metadata["monotonic_origin_s"]
    # Revalidar DESPUÉS de Enter: la captura puede haber terminado mientras
    # el operador se preparaba. Una marca tardía no debe parecer válida.
    start = active_window_start()
    if not start <= elapsed < start + metadata["requested_duration_s"]:
        raise ValueError("Marca fuera de la ventana prevista o reloj de otro equipo/reinicio.")
    marker = {"trial_id": args.trial_id, "event": args.event, "cause": args.cause,
              "elapsed_s": elapsed, "utc": utc_now(), "uncertainty_s": args.uncertainty_s,
              "notes": args.notes}
    with (args.run / "markers.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(marker, ensure_ascii=False, allow_nan=False) + "\n")
    print(f"Marca manual {args.event}: {elapsed:.3f} s. No se modificó ninguna conexión ni hardware.")


def make_templates(output):
    output.mkdir(parents=True, exist_ok=False)
    with (output / "latency.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LATENCY_FIELDS)
        writer.writeheader()
        for i in range(20):
            writer.writerow({"trial_id": f"L{i + 1:02}", "color": "red", "transition": "on" if i % 2 == 0 else "off"})
    (output / "conditions.md").write_text(
        "# Ficha por completar; NO contiene resultados\n\n"
        "- Fecha/hora y operador:\n- Versión/revisión de código y firmware cargado:\n"
        "- Placa y alimentación:\n- Red del ESP32 y red independiente del observador:\n"
        "- Versión de IoT MQTT Panel y ajustes MQTT:\n- Cinta, resolución e incertidumbre:\n"
        "- Plano de referencia, objeto, alineación y temperatura ambiente:\n"
        "- Cámara, FPS real de captura, exposición y archivos originales:\n"
        "- Corte WiFi / bloqueo MQTT utilizado y duración prevista:\n"
        "- Referencias del docente (NO umbrales obligatorios):\n"
        "- Criterios de interpretación elegidos ANTES de la prueba:\n"
        "- Incidencias y limitaciones observadas:\n", encoding="utf-8")
    print(f"Plantillas vacías creadas en {output}; faltan todas las mediciones físicas.")


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "check":
            Settings.load(args.env_file)
            paho = version("paho-mqtt")
            if not paho.startswith("2."):
                raise ValueError("El observador requiere Paho 2.x; usar requirements.txt existente.")
            print(f"Configuración válida; Paho {paho}; comprobación SIN red. No se modificó .env.")
        elif args.command == "capture":
            return run_capture(args)
        elif args.command == "mark":
            add_marker(args)
        elif args.command == "templates":
            make_templates(args.output)
        else:
            if args.command == "report":
                report = build_report(args.run)
            elif args.command == "accuracy":
                report = aggregate_accuracy(args.run)
            else:
                report = latency_report(args.input)
            save_json(args.output, report)
            print(f"Reporte offline guardado en {args.output}")
        return 0
    except (ValueError, ConfigurationError, OSError, RuntimeError, PackageNotFoundError, ImportError) as error:
        print(f"No se pudo completar: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
