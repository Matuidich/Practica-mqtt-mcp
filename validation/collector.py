"""Observador MQTT de solo suscripción, con reloj monotónico y cierre explícito."""

from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import threading
import time

from iot_shared.config import ClientRole, Settings
from iot_shared.errors import ValidationError
from iot_shared.messages import DistanceReading


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Journal:
    """Cada línea se vacía al disco; Ctrl+C conserva las evidencias parciales."""

    def __init__(self, run, metadata, *, clock=time.monotonic):
        self.run = Path(run)
        self.run.mkdir(parents=True, exist_ok=False)
        self.clock = clock
        self.origin = clock()
        self.lock = threading.RLock()
        metadata = {**metadata, "schema_version": 1, "started_utc": utc_now(),
                    "monotonic_origin_s": self.origin}
        (self.run / "session.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
                                                encoding="utf-8")
        self.stream = (self.run / "events.jsonl").open("x", encoding="utf-8")
        self.write("session_start")

    def write(self, kind, **fields):
        with self.lock:
            event = {"kind": kind, "elapsed_s": self.clock() - self.origin,
                     "utc": utc_now(), **fields}
            self.stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            self.stream.flush()
            return event

    def close(self):
        with self.lock:
            self.stream.close()


def create_client(settings):
    # Importación diferida: reportes y --help funcionan sin Paho ni red.
    import paho.mqtt.client as mqtt

    return mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.client_id(ClientRole.FIRMWARE) + "-val-" + secrets.token_hex(4),
        clean_session=True, protocol=mqtt.MQTTv311, transport="tcp", reconnect_on_failure=True,
    )


class DistanceObserver:
    """Una instancia no conecta hasta start(). Nunca se llama a publish()."""

    def __init__(self, settings: Settings, device_id, journal, *, client_factory=create_client):
        # Reutiliza también la validación del identificador sin leer archivos locales.
        DistanceReading(1, device_id, 0)
        self.settings, self.device_id, self.journal = settings, device_id, journal
        self.client_factory, self.client = client_factory, None
        self.ready = threading.Event()
        self.fatal_error = None
        self._mid = None
        self._seen = set()
        self._previous_uptime = None
        self._closing = False

    def _guard(self, callback):
        def call(*args):
            try:
                callback(*args)
            except Exception as error:
                self.fatal_error = error
                self.ready.clear()
        return call

    def start(self):
        if self.client is not None:
            raise RuntimeError("El observador ya fue iniciado.")
        self.client = self.client_factory(self.settings)
        self.client.connect_timeout = 5.0
        for name in ("connect", "connect_fail", "subscribe", "disconnect", "message"):
            setattr(self.client, "on_" + name, self._guard(getattr(self, "_on_" + name)))
        self.client.reconnect_delay_set(self.settings.reconnect_min_delay_s,
                                        self.settings.reconnect_max_delay_s)
        self.client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, self.settings.keepalive_s)
        if self.client.loop_start() != 0:
            raise RuntimeError("No se pudo iniciar el observador MQTT.")

    def close(self):
        self._closing = True
        self.ready.clear()
        client, self.client = self.client, None
        if client is not None:
            try:
                client.disconnect()
            finally:
                client.loop_stop()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        self.ready.clear()
        self._mid = None
        if reason_code != 0:
            self.journal.write("connect_failed", reason=str(reason_code))
            return
        self.journal.write("connected")
        # Tópico exacto: no se observa ni publica commands/leds.
        rc, self._mid = client.subscribe(self.settings.topics.distance, qos=0)
        if rc != 0:
            self.journal.write("subscription_failed", reason=str(rc))

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties):
        if mid != self._mid:
            return
        if len(reason_codes) != 1 or reason_codes[0] != 0:
            self.journal.write("subscription_failed", reason=str(reason_codes))
            return
        self._mid = None
        self.journal.write("subscribed")
        self.ready.set()

    def _on_connect_fail(self, client, userdata):
        self.ready.clear()
        self.journal.write("connect_failed", reason="network_unavailable")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.ready.clear()
        self._mid = None
        self.journal.write("disconnected", reason=str(reason_code), intentional_close=self._closing)

    def _on_message(self, client, userdata, message):
        if message.topic != self.settings.topics.distance:
            return
        reason = None
        reading = None
        if message.retain:
            reason = "retained"
        elif not self.ready.is_set():
            reason = "observer_not_ready"
        else:
            try:
                reading = DistanceReading.from_json(message.payload)
            except ValidationError:
                reason = "invalid_contract"
            if reading is not None and reading.device_id != self.device_id:
                reason = "other_device"
        if reason:
            self.journal.write("rejected", reason=reason,
                               payload_hex=message.payload[:1024].hex(), payload_bytes=len(message.payload))
            return
        uptime = reading.uptime_ms
        previous = self._previous_uptime
        delta, uptime_event = None, None
        # Una caída grande cerca del límite de uint32 se distingue de reinicio/reordenación.
        if previous is not None and uptime < previous:
            if previous >= 0xFFFF0000 and uptime <= 0xFFFF:
                uptime_event, delta = "wrap", (uptime - previous) % (2 ** 32)
            else:
                uptime_event = "reset_or_reorder"
            self._seen.clear()
        duplicate = uptime in self._seen
        if not duplicate:
            if previous is not None and uptime > previous:
                delta = uptime - previous
            self._seen.add(uptime)
            self._previous_uptime = uptime
        self.journal.write("reading", distance_cm=reading.distance_cm, device_id=reading.device_id,
                           uptime_ms=uptime, duplicate=duplicate, uptime_delta_ms=delta,
                           uptime_event=uptime_event, payload=message.payload.decode("utf-8"))


def capture_window(observer, journal, duration_s, ready_timeout_s, *, clock=time.monotonic,
                   wait=None, progress=print):
    """El plazo empieza tras SUBACK; preparación y cierre quedan fuera de la ventana."""
    if wait is None:
        wait = threading.Event().wait
    started, completed = None, False
    try:
        observer.start()
        deadline = clock() + ready_timeout_s
        while not observer.ready.is_set():
            if observer.fatal_error:
                raise RuntimeError("Falló el registro/callback MQTT.") from observer.fatal_error
            if clock() >= deadline:
                raise TimeoutError("El observador no recibió SUBACK a tiempo; no comenzó la prueba.")
            wait(.05)
        started = journal.write("window_start")
        progress(f"Ventana iniciada: {duration_s:g} s. El observador solo escucha distancias.")
        deadline = journal.origin + started["elapsed_s"] + duration_s
        next_progress = clock() + 30
        while clock() < deadline:
            if observer.fatal_error:
                raise RuntimeError("Falló el registro/callback MQTT.") from observer.fatal_error
            if clock() >= next_progress:
                progress(f"Restan {max(0, deadline - clock()):.0f} s. Evidencias: {journal.run}")
                next_progress = clock() + 30
            wait(min(.1, max(0, deadline - clock())))
        if observer.fatal_error:
            raise RuntimeError("Falló el registro/callback MQTT.") from observer.fatal_error
        completed = True
    except KeyboardInterrupt:
        journal.write("interrupted", reason="Ctrl+C")
    except Exception as error:
        journal.write("run_error", error_type=type(error).__name__, detail=str(error))
        raise
    finally:
        if started is not None:
            journal.write("window_end", completed=completed)
        try:
            observer.close()
        finally:
            journal.write("session_end", completed=completed)
    return completed
