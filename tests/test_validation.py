"""Mediciones con reloj y MQTT dobles; sockets/DNS prohibidos por caso."""

from contextlib import redirect_stderr, redirect_stdout
import csv
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from tests.support import OfflineTestCase, settings
from iot_shared.messages import DistanceReading
from validation.__main__ import main, make_templates
from validation.collector import DistanceObserver, Journal, capture_window, create_client
from validation.reporting import (LATENCY_FIELDS, aggregate_accuracy, build_report,
                                  distribution, latency_report, positive, read_jsonl)


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def at(self, elapsed):
        self.now = 100.0 + elapsed


class SubscriberDouble:
    """No tiene método publish: cualquier intento de publicar haría fallar el caso."""

    def __init__(self):
        self.mid, self.subscriptions, self.closed = 0, [], False
        self.auto_connect, self.ack = True, 0

    def reconnect_delay_set(self, minimum, maximum):
        self.delays = (minimum, maximum)

    def connect_async(self, *args):
        self.connection = args

    def loop_start(self):
        if self.auto_connect:
            self.reconnect()
        return 0

    def reconnect(self):
        self.on_connect(self, None, None, 0, None)
        self.on_subscribe(self, None, self.mid, [self.ack], None)

    def subscribe(self, topic, qos):
        self.mid += 1
        self.subscriptions.append((topic, qos))
        return 0, self.mid

    def disconnect(self):
        self.on_disconnect(self, None, None, 0, None)

    def loop_stop(self):
        self.closed = True


class ValidationTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.clock = Clock()
        self.settings = settings()
        self.metadata = {"mode": "offline_fixture", "purpose": "accuracy", "gap_s": 3,
                         "requested_duration_s": 10, "reference_cm": 10, "device_id": "sensor-01"}
        self.journal = Journal(self.root / "run", self.metadata, clock=self.clock)
        self.addCleanup(self.journal.close)
        self.client = SubscriberDouble()
        self.observer = DistanceObserver(self.settings, "sensor-01", self.journal,
                                          client_factory=lambda _: self.client)
        self.addCleanup(self.observer.close)
        # Cierre de observador antes de cierre del archivo (LIFO).
        self.run = self.root / "run"

    def emit(self, elapsed, distance=10, uptime=1000, *, device="sensor-01", retain=False, payload=None):
        self.clock.at(elapsed)
        if payload is None:
            payload = DistanceReading(distance, device, uptime).to_json().encode()
        self.client.on_message(self.client, None, SimpleNamespace(
            topic=self.settings.topics.distance, payload=payload, retain=retain))

    def sample_run(self):
        self.observer.start()
        self.clock.at(1)
        self.journal.write("window_start")
        self.emit(2, 10.5, 1000)
        self.emit(2.2, 10.5, 1000)
        self.emit(2.3, payload=b'{"bad": 1}')
        self.emit(3, device="other-device")
        self.emit(3.2, retain=True)
        self.emit(4, 9.5, 2000)
        self.emit(10, 10, 8000)
        self.clock.at(11)
        self.journal.write("window_end", completed=True)

    def write_markers(self, markers):
        (self.run / "markers.jsonl").write_text(
            "".join(json.dumps(m) + "\n" for m in markers), encoding="utf-8")

    def reconnect_run(self, *, recover=True, observer_outage=False, recovery_uptime=25000):
        self.observer.start()
        self.clock.at(1)
        self.journal.write("window_start")
        self.emit(2, uptime=1000)
        self.emit(3, uptime=2000)
        if observer_outage:
            self.clock.at(5)
            self.client.on_disconnect(self.client, None, None, 1, None)
            self.clock.at(25)
            self.client.reconnect()
        if recover:
            self.emit(26, uptime=recovery_uptime)
            self.emit(27, uptime=recovery_uptime + 1000)
        self.clock.at(31)
        self.journal.write("window_end", completed=True)
        self.write_markers([
            {"event": "cut", "cause": "wifi", "trial_id": "w1", "elapsed_s": 4},
            {"event": "restored", "cause": "wifi", "trial_id": "w1", "elapsed_s": 24,
             "uncertainty_s": .5},
        ])
        return build_report(self.run)["reconnection"][0]

    def test_constructor_is_inert_and_capture_requires_explicit_live_flag(self):
        self.assertIsNone(self.observer.client)
        err = io.StringIO()
        with redirect_stderr(err), patch("validation.__main__.Settings.load") as load:
            result = main(["capture", "--device-id", "sensor-01", "--output", str(self.root / "refused")])
        self.assertEqual(result, 1)
        self.assertIn("--live", err.getvalue())
        load.assert_not_called()
        self.assertFalse((self.root / "refused").exists())

    def test_paho_clients_are_distinct_and_construct_without_sockets(self):
        try:
            import paho.mqtt.client  # noqa: F401
        except ImportError:
            self.skipTest("Paho no instalado; usar .venv.")
        first, second = create_client(self.settings), create_client(self.settings)
        self.assertNotEqual(first._client_id, second._client_id)
        self.assertNotEqual(first._client_id.decode(), self.settings.client_id("firmware"))
        self.assertNotEqual(first._client_id.decode(), self.settings.client_id("mcp"))
        self.assertFalse(first.is_connected())

    def test_read_only_subscription_is_restored_after_disconnect(self):
        self.observer.start()
        self.assertTrue(self.observer.ready.is_set())
        self.client.on_disconnect(self.client, None, None, 1, None)
        self.assertFalse(self.observer.ready.is_set())
        self.client.reconnect()
        self.assertTrue(self.observer.ready.is_set())
        self.assertEqual(self.client.subscriptions, [(self.settings.topics.distance, 0)] * 2)
        self.assertEqual(self.client.delays, (self.settings.reconnect_min_delay_s,
                                             self.settings.reconnect_max_delay_s))

    def test_subscription_ack_is_required(self):
        self.client.ack = 128
        self.observer.start()
        self.emit(2)
        self.assertFalse(self.observer.ready.is_set())
        self.assertEqual(read_jsonl(self.run / "events.jsonl")[-1]["reason"], "observer_not_ready")

    def test_frequency_counts_and_exactitude_use_only_valid_new_readings(self):
        self.sample_run()
        report = build_report(self.run)
        self.assertEqual(report["mode"], "offline_fixture")
        self.assertEqual(report["actual_duration_s"], 10)
        self.assertEqual(report["valid_messages"], 4)
        self.assertEqual(report["distance_messages_received"], 7)
        self.assertEqual(report["unique_readings"], 3)
        self.assertEqual(report["duplicate_messages"], 1)
        self.assertEqual(report["frequency_hz_whole_window"], .3)
        self.assertEqual(report["frequency_hz_first_to_last"], .25)
        self.assertEqual(report["receive_interval_s"]["mean"], 4)
        self.assertAlmostEqual(report["receive_interval_s"]["p95"], 5.8)
        self.assertEqual(report["device_uptime_interval_s"]["mean"], 3.5)
        self.assertEqual(report["rejected_messages"], {"invalid_contract": 1, "other_device": 1, "retained": 1})
        self.assertEqual(report["long_silences"][0]["duration_s"], 6)
        self.assertEqual(report["observer_outages"], [])
        self.assertEqual(report["accuracy"]["bias_cm"], 0)
        self.assertAlmostEqual(report["accuracy"]["mae_cm"], 1 / 3)
        self.assertAlmostEqual(report["accuracy"]["rmse_cm"], (1 / 6) ** .5)
        self.assertEqual(report["accuracy"]["repeatability_stdev_cm"], .5)
        pooled = aggregate_accuracy([self.run])
        self.assertEqual(pooled["pooled_samples"], 3)

    def test_no_readings_reports_whole_silence_and_no_accuracy_result(self):
        self.observer.start()
        self.clock.at(1)
        self.journal.write("window_start")
        self.clock.at(601)
        self.journal.write("window_end", completed=True)
        report = build_report(self.run)
        self.assertFalse(report["data_observed"])
        self.assertIsNone(report["accuracy"]["mae_cm"])
        self.assertEqual(report["long_silences"], [{"start_s": 1, "end_s": 601,
                                                   "duration_s": 600, "boundary": "whole_window"}])
        with self.assertRaises(ValueError):
            aggregate_accuracy([self.run])

    def test_silence_detection_includes_start_and_end_boundaries(self):
        self.observer.start()
        self.clock.at(1)
        self.journal.write("window_start")
        self.emit(5)
        self.clock.at(11)
        self.journal.write("window_end", completed=True)
        report = build_report(self.run)
        self.assertEqual([g["boundary"] for g in report["long_silences"]], ["start", "end"])
        self.assertEqual(report["frequency_hz_whole_window"], .1)
        self.assertIsNone(report["frequency_hz_first_to_last"])

    def test_wrap_and_reset_are_reported_without_negative_intervals(self):
        self.observer.start()
        self.emit(1, uptime=4294967200)
        self.emit(2, uptime=100)
        self.emit(3, uptime=2000)
        self.emit(4, uptime=10)
        readings = [e for e in read_jsonl(self.run / "events.jsonl") if e["kind"] == "reading"]
        self.assertEqual(readings[1]["uptime_event"], "wrap")
        self.assertEqual(readings[1]["uptime_delta_ms"], 196)
        self.assertEqual(readings[-1]["uptime_event"], "reset_or_reorder")
        self.assertIsNone(readings[-1]["uptime_delta_ms"])

    def test_reconnection_uses_manual_restore_and_first_post_restore_publication(self):
        result = self.reconnect_run()
        self.assertEqual(result["status"], "recovered_observed")
        self.assertEqual(result["recovery_after_restore_s"], 2)
        self.assertEqual(result["observed_silence_around_restore_s"], 23)
        self.assertEqual(result["restore_marker_uncertainty_s"], .5)

    def test_observer_disconnection_makes_reconnection_inconclusive(self):
        result = self.reconnect_run(observer_outage=True)
        self.assertEqual(result["status"], "observer_disconnected_inconclusive")
        self.assertIsNone(result["recovery_after_restore_s"])

    def test_continuous_publications_do_not_prove_a_reconnection(self):
        self.observer.start()
        self.clock.at(1)
        self.journal.write("window_start")
        for t in (2, 4, 6, 8, 10):
            self.emit(t, uptime=t * 1000)
        self.clock.at(11)
        self.journal.write("window_end", completed=True)
        self.write_markers([
            {"event": "cut", "cause": "mqtt", "trial_id": "m1", "elapsed_s": 3},
            {"event": "restored", "cause": "mqtt", "trial_id": "m1", "elapsed_s": 7},
        ])
        trial = build_report(self.run)["reconnection"][0]
        self.assertEqual(trial["status"], "no_interruption_demonstrated")
        self.assertIsNone(trial["recovery_after_restore_s"])

    def test_missing_recovery_keeps_a_lower_bound_instead_of_fake_time(self):
        result = self.reconnect_run(recover=False)
        self.assertEqual(result["status"], "not_recovered_in_window")
        self.assertEqual(result["recovery_lower_bound_s"], 7)
        self.assertIsNone(result["recovery_after_restore_s"])
        markers = read_jsonl(self.run / "markers.jsonl")
        markers[1]["elapsed_s"] = 31
        self.write_markers(markers)
        result = build_report(self.run)["reconnection"][0]
        self.assertEqual(result["status"], "not_recovered_in_window")
        self.assertEqual(result["recovery_lower_bound_s"], 0)

    def test_late_silence_after_restore_does_not_prove_the_intended_cut(self):
        self.observer.start()
        self.clock.at(1)
        self.journal.write("window_start")
        for t in range(2, 25, 2):
            self.emit(t, uptime=t * 1000)
        self.emit(30, uptime=30000)
        self.clock.at(31)
        self.journal.write("window_end", completed=True)
        self.write_markers([
            {"event": "cut", "cause": "mqtt", "trial_id": "m1", "elapsed_s": 3},
            {"event": "restored", "cause": "mqtt", "trial_id": "m1", "elapsed_s": 23},
        ])
        trial = build_report(self.run)["reconnection"][0]
        self.assertEqual(trial["longest_silence_during_cut_s"], 2)
        self.assertEqual(trial["status"], "no_interruption_demonstrated")
        self.assertIsNone(trial["recovery_after_restore_s"])

    def test_recovery_in_later_trial_is_not_attributed_to_previous_trial(self):
        self.reconnect_run()
        self.write_markers([
            {"event": "cut", "cause": "wifi", "trial_id": "w1", "elapsed_s": 4},
            {"event": "restored", "cause": "wifi", "trial_id": "w1", "elapsed_s": 24},
            {"event": "cut", "cause": "wifi", "trial_id": "w2", "elapsed_s": 25},
            {"event": "restored", "cause": "wifi", "trial_id": "w2", "elapsed_s": 25.5},
        ])
        trial = build_report(self.run)["reconnection"][0]
        self.assertEqual(trial["status"], "next_trial_before_recovery")
        self.assertEqual(trial["recovery_lower_bound_s"], 1)
        self.assertIsNone(trial["recovery_after_restore_s"])

    def test_overlapping_trials_are_both_inconclusive(self):
        self.reconnect_run()
        for first_restore, second_restore in ((24, 29), (29, 24)):
            with self.subTest(first_restore=first_restore, second_restore=second_restore):
                self.write_markers([
                    {"event": "cut", "cause": "wifi", "trial_id": "w1", "elapsed_s": 4},
                    {"event": "restored", "cause": "wifi", "trial_id": "w1", "elapsed_s": first_restore},
                    {"event": "cut", "cause": "wifi", "trial_id": "w2", "elapsed_s": 20},
                    {"event": "restored", "cause": "wifi", "trial_id": "w2", "elapsed_s": second_restore},
                ])
                trials = build_report(self.run)["reconnection"]
                self.assertEqual([t["status"] for t in trials], ["overlapping_trials"] * 2)
                self.assertTrue(all(t["recovery_after_restore_s"] is None for t in trials))

    def test_stale_baseline_does_not_demonstrate_a_new_network_cut(self):
        self.reconnect_run()
        markers = read_jsonl(self.run / "markers.jsonl")
        markers[0]["elapsed_s"] = 10
        self.write_markers(markers)
        trial = build_report(self.run)["reconnection"][0]
        self.assertEqual(trial["status"], "baseline_not_recent")
        self.assertIsNone(trial["recovery_after_restore_s"])

    def test_reset_during_cut_is_not_reported_as_isolated_reconnection(self):
        trial = self.reconnect_run(recovery_uptime=500)
        self.assertTrue(trial["device_reset_or_reorder_seen"])
        self.assertEqual(trial["status"], "device_reset_or_reorder_inconclusive")
        self.assertIsNone(trial["recovery_after_restore_s"])

    def test_ten_minutes_of_simulated_time_count_non_two_hz_and_interruption(self):
        # 1 lectura cada 1.25 s; se omiten 8 durante un corte ficticio.
        # Solo avanza Clock; no hay esperas, sockets ni resultados físicos.
        scheduled = iter(1.25 * k for k in range(1, 480) if not 240 <= 1.25 * k < 250)
        upcoming = next(scheduled, None)

        def wait(seconds):
            nonlocal upcoming
            target = self.clock.now + seconds
            while upcoming is not None and 100 + upcoming <= target:
                self.emit(upcoming, uptime=int(upcoming * 1000))
                upcoming = next(scheduled, None)
            self.clock.now = target

        capture_window(self.observer, self.journal, 600, 2,
                       clock=self.clock, wait=wait, progress=lambda _: None)
        report = build_report(self.run)
        self.assertEqual(report["mode"], "offline_fixture")
        self.assertEqual(report["measurement_status"], "completed")
        self.assertEqual(report["actual_duration_s"], 600)
        self.assertEqual(report["unique_readings"], 471)
        self.assertEqual(report["frequency_hz_whole_window"], 471 / 600)
        self.assertEqual(report["receive_interval_s"]["median"], 1.25)
        self.assertEqual(len(report["per_minute"]), 10)
        self.assertEqual(sum(b["unique_readings"] for b in report["per_minute"]), 471)
        self.assertEqual([s["duration_s"] for s in report["long_silences"]], [11.25])

    def test_capture_lifecycle_advances_fake_time_and_closes_without_real_wait(self):
        def wait(seconds):
            self.clock.now += seconds
            self.emit(self.clock.now - 100, uptime=int((self.clock.now - 100) * 1000))

        result = capture_window(self.observer, self.journal, .5, 2,
                                clock=self.clock, wait=wait, progress=lambda _: None)
        self.assertTrue(result)
        self.assertTrue(self.client.closed)
        report = build_report(self.run)
        self.assertEqual(report["measurement_status"], "completed")
        self.assertGreaterEqual(report["actual_duration_s"], .5)

    def test_ready_timeout_does_not_start_measurement_window(self):
        self.client.auto_connect = False
        def wait(seconds):
            self.clock.now += seconds
        with self.assertRaises(TimeoutError):
            capture_window(self.observer, self.journal, 600, .2,
                           clock=self.clock, wait=wait, progress=lambda _: None)
        self.assertEqual(build_report(self.run)["measurement_status"], "not_started")
        self.assertTrue(self.client.closed)

    def test_open_recording_is_not_reported_as_a_completed_measurement(self):
        self.observer.start()
        self.clock.at(1)
        self.journal.write("window_start")
        self.emit(2)
        report = build_report(self.run)
        self.assertEqual(report["measurement_status"], "open_or_incomplete_window")
        self.assertNotIn("frequency_hz_whole_window", report)

    def test_ctrl_c_conserves_a_closed_partial_window(self):
        def interrupt(_):
            self.clock.now += .2
            raise KeyboardInterrupt
        result = capture_window(self.observer, self.journal, 600, 2,
                                clock=self.clock, wait=interrupt, progress=lambda _: None)
        self.assertFalse(result)
        self.assertEqual(build_report(self.run)["measurement_status"], "interrupted")

    def test_callback_recording_error_cannot_be_reported_as_completed(self):
        original = self.journal.write
        def fail_reading(kind, **fields):
            if kind == "reading":
                raise OSError("Fallo de escritura ficticio")
            return original(kind, **fields)
        def wait(seconds):
            self.clock.now += seconds
            self.emit(self.clock.now - 100)
        with patch.object(self.journal, "write", side_effect=fail_reading):
            with self.assertRaises(RuntimeError):
                capture_window(self.observer, self.journal, .1, 2,
                               clock=self.clock, wait=wait, progress=lambda _: None)
        self.assertEqual(build_report(self.run)["measurement_status"], "interrupted")
        self.assertTrue(self.client.closed)

    def test_existing_run_directory_and_report_files_are_never_overwritten(self):
        with self.assertRaises(FileExistsError):
            Journal(self.run, self.metadata, clock=self.clock)
        self.sample_run()
        output = self.root / "result.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["report", "--run", str(self.run), "--output", str(output)]), 0)
        before = output.read_bytes()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["report", "--run", str(self.run), "--output", str(output)]), 1)
        self.assertEqual(output.read_bytes(), before)

    def test_marker_cli_records_only_local_time_and_refuses_duplicates(self):
        path = self.run / "session.json"
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta.update(mode="live_mqtt_observation", purpose="reconnect")
        path.write_text(json.dumps(meta), encoding="utf-8")
        self.observer.start()
        self.clock.at(1)
        self.journal.write("window_start")
        base = ["mark", "--run", str(self.run), "--trial-id", "wifi-01", "--cause", "wifi"]
        with patch("validation.__main__.time.monotonic", return_value=102), redirect_stdout(io.StringIO()):
            self.assertEqual(main(base + ["--event", "cut"]), 0)
        with patch("validation.__main__.time.monotonic", return_value=103), redirect_stderr(io.StringIO()):
            self.assertEqual(main(base + ["--event", "cut"]), 1)
        self.assertEqual(len(read_jsonl(self.run / "markers.jsonl")), 1)

    def test_marker_waiting_for_enter_rechecks_that_capture_is_still_active(self):
        path = self.run / "session.json"
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta.update(mode="live_mqtt_observation", purpose="reconnect")
        path.write_text(json.dumps(meta), encoding="utf-8")
        self.observer.start()
        self.clock.at(1)
        self.journal.write("window_start")

        def end_while_waiting(_):
            self.clock.at(2)
            self.journal.write("window_end", completed=False)
            return ""

        with (patch("builtins.input", side_effect=end_while_waiting),
              patch("validation.__main__.time.monotonic", return_value=103),
              redirect_stderr(io.StringIO())):
            result = main(["mark", "--run", str(self.run), "--trial-id", "w1",
                           "--cause", "wifi", "--event", "cut", "--wait-enter"])
        self.assertEqual(result, 1)
        self.assertFalse((self.run / "markers.jsonl").exists())

    def test_physical_video_latency_preserves_failures_and_frame_uncertainty(self):
        path = self.root / "latency.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=LATENCY_FIELDS)
            writer.writeheader()
            writer.writerow(dict(trial_id="L01", video_file="take.mp4", color="red", transition="on",
                                 status="measured", start_frame=10, end_frame=16, fps=120))
            writer.writerow(dict(trial_id="L02", video_file="take.mp4", color="red", transition="off",
                                 status="no_change", observation_s=5, notes="No se vio apagar en cinco segundos."))
        report = latency_report(path)
        self.assertEqual(report["attempts"], 2)
        self.assertEqual(report["statuses"], {"measured": 1, "no_change": 1})
        self.assertEqual(report["latency_ms"]["mean"], 50)
        self.assertAlmostEqual(report["trials"][0]["conservative_frame_uncertainty_ms"], 1000 / 60)
        groups = {g["transition"]: g for g in report["by_color_and_transition"]}
        self.assertEqual(groups["on"]["latency_ms"]["mean"], 50)
        self.assertEqual(groups["off"]["statuses"], {"no_change": 1})
        self.assertIsNone(groups["off"]["latency_ms"]["mean"])

    def test_empty_latency_templates_are_not_mistaken_for_results(self):
        with redirect_stdout(io.StringIO()):
            make_templates(self.root / "manual")
        with self.assertRaises(ValueError):
            latency_report(self.root / "manual/latency.csv")

    def test_malformed_csv_and_reversed_frames_are_rejected(self):
        path = self.root / "invalid.csv"
        header = ",".join(LATENCY_FIELDS) + "\n"
        for line in (
            "L01,take.mp4,red,on,measured,16,10,120,,\n",
            "L01,take.mp4,red,on,measured,10,16,nan,,\n",
            "L01,take.mp4,red,on,measured,10,16,120,,note,extra\n",
        ):
            with self.subTest(line=line):
                path.write_text(header + line, encoding="utf-8")
                with self.assertRaises(ValueError):
                    latency_report(path)

    def test_invalid_and_truncated_input_is_rejected(self):
        for value in ("nan", "inf", "-1", "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                positive(value)
        self.assertIsNone(distribution([])["mean"])
        (self.root / "bad.jsonl").write_text('{"kind":', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_jsonl(self.root / "bad.jsonl")
