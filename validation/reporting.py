"""Cálculos offline sobre evidencias; ningún resultado implica aprobación física."""

from collections import Counter
import csv
import json
import math
from pathlib import Path
from statistics import mean, median, stdev


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError("Se requiere un número finito mayor que cero.")
    return number


def distribution(values):
    """p95 por interpolación lineal en la posición 0.95*(n-1)."""
    if not values:
        return {key: None for key in ("mean", "median", "p95", "min", "max", "stdev_sample")}
    ordered = sorted(values)
    position = .95 * (len(ordered) - 1)
    lo, hi = math.floor(position), math.ceil(position)
    return {
        "mean": mean(values), "median": median(values),
        "p95": ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo),
        "min": ordered[0], "max": ordered[-1],
        "stdev_sample": stdev(values) if len(values) > 1 else None,
    }


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    result = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                result.append(json.loads(line))
            except ValueError as error:
                raise ValueError(f"Registro incompleto/inválido: {path.name}, línea {line_number}.") from error
    return result


def accuracy_metrics(readings, reference_cm):
    errors = [r["distance_cm"] - reference_cm for r in readings]
    return {
        "samples": len(errors), "reference_cm": reference_cm,
        "mean_distance_cm": mean(r["distance_cm"] for r in readings) if readings else None,
        "bias_cm": mean(errors) if errors else None,
        "mae_cm": mean(abs(e) for e in errors) if errors else None,
        "rmse_cm": math.sqrt(mean(e * e for e in errors)) if errors else None,
        "max_absolute_error_cm": max(map(abs, errors)) if errors else None,
        "mae_percent_of_reference": 100 * mean(abs(e) for e in errors) / reference_cm if errors else None,
        "repeatability_stdev_cm": stdev(errors) if len(errors) > 1 else None,
    }


def _observer_coverage(events, start, end):
    """SUBACK, y no solo CONNACK, establece que el observador está listo."""
    ready, cursor, outages = False, start, []
    kinds = {"subscribed", "connected", "disconnected", "connect_failed", "subscription_failed"}
    for event in events:
        t = event["elapsed_s"]
        if t > end:
            break
        if event["kind"] not in kinds:
            continue
        new_ready = event["kind"] == "subscribed"
        if t <= start:
            ready = new_ready
        else:
            if not ready and t > cursor:
                outages.append({"start_s": cursor, "end_s": t, "duration_s": t - cursor})
            cursor, ready = t, new_ready
    if not ready and end > cursor:
        outages.append({"start_s": cursor, "end_s": end, "duration_s": end - cursor})
    return outages


def reconnection_trials(markers, readings, events, start, end, gap_s):
    trials = {}
    for marker in markers:
        trial = trials.setdefault(marker["trial_id"], [])
        trial.append(marker)
    result = []
    for trial_id, marks in trials.items():
        cuts = [m for m in marks if m["event"] == "cut"]
        restores = [m for m in marks if m["event"] == "restored"]
        row = {"trial_id": trial_id, "status": "incomplete_markers", "recovery_after_restore_s": None}
        if len(cuts) != 1 or len(restores) != 1:
            result.append(row)
            continue
        cut, restore = cuts[0], restores[0]
        c, r = cut["elapsed_s"], restore["elapsed_s"]
        if not start <= c < r <= end or cut["cause"] != restore["cause"]:
            row["status"] = "invalid_markers"
            result.append(row)
            continue
        # Cada intento acaba antes del siguiente corte. Nunca atribuir a este
        # intento una publicación recuperada durante otro ensayo posterior.
        next_cut = min((m["elapsed_s"] for m in markers if m["event"] == "cut"
                        and m["trial_id"] != trial_id and c <= m["elapsed_s"] < end), default=end)
        previous_cut_open = any(
            m["event"] == "cut" and m["trial_id"] != trial_id and start <= m["elapsed_s"] < c
            and not any(n["event"] == "restored" and n["trial_id"] == m["trial_id"]
                        and m["elapsed_s"] < n["elapsed_s"] < c for n in markers)
            for m in markers)
        if (next_cut < end and next_cut <= r) or previous_cut_open:
            row["status"] = "overlapping_trials"
            result.append(row)
            continue
        before_cut = [v for v in readings if v["elapsed_s"] < c]
        before_restore = [v for v in readings if v["elapsed_s"] <= r]
        after = next((v for v in readings if r < v["elapsed_s"] < next_cut), None)
        last = before_restore[-1] if before_restore else None
        upper = after["elapsed_s"] if after else next_cut
        observer_outages = _observer_coverage(events, c, upper)
        silence = upper - (last["elapsed_s"] if last else start)
        cut_times = [c] + [v["elapsed_s"] for v in readings if c <= v["elapsed_s"] <= r] + [r]
        silence_during_cut = max(b - a for a, b in zip(cut_times, cut_times[1:]))
        reset_seen = any(v.get("uptime_event") == "reset_or_reorder" for v in readings
                         if c <= v["elapsed_s"] <= upper)
        row.update({
            "cause_operator_label": cut["cause"], "cut_s": c, "restored_s": r,
            "intentional_outage_s": r - c,
            "first_after_restore_s": after["elapsed_s"] if after else None,
            "observed_silence_around_restore_s": silence,
            "longest_silence_during_cut_s": silence_during_cut,
            "last_before_cut_s": before_cut[-1]["elapsed_s"] if before_cut else None,
            "observation_end_s": upper,
            "observer_outages": observer_outages,
            "restore_marker_uncertainty_s": restore.get("uncertainty_s"),
            "device_reset_or_reorder_seen": reset_seen,
        })
        if not before_cut:
            row["status"] = "missing_baseline"
        elif c - before_cut[-1]["elapsed_s"] > gap_s:
            row["status"] = "baseline_not_recent"
        elif observer_outages:
            row["status"] = "observer_disconnected_inconclusive"
        elif reset_seen:
            row["status"] = "device_reset_or_reorder_inconclusive"
        elif silence_during_cut <= gap_s:
            row["status"] = "no_interruption_demonstrated"
        elif after is None:
            row["status"] = "next_trial_before_recovery" if next_cut < end else "not_recovered_in_window"
            row["recovery_lower_bound_s"] = upper - r
        else:
            row["status"] = "recovered_observed"
            row["recovery_after_restore_s"] = after["elapsed_s"] - r
            row["cut_to_first_after_restore_s"] = after["elapsed_s"] - c
            uncertainty = restore.get("uncertainty_s")
            row["recovery_marker_bounds_s"] = (
                [max(0, after["elapsed_s"] - r - uncertainty), after["elapsed_s"] - r + uncertainty]
                if uncertainty is not None else None)
        result.append(row)
    return result


def build_report(run):
    run = Path(run)
    metadata = json.loads((run / "session.json").read_text(encoding="utf-8"))
    events = read_jsonl(run / "events.jsonl")
    starts = [e for e in events if e["kind"] == "window_start"]
    ends = [e for e in events if e["kind"] == "window_end"]
    report = {
        "schema_version": 1, "mode": metadata["mode"],
        "measurement_status": "not_started", "metadata": metadata,
        "acceptance": "No se aplica ningún umbral de aprobación del docente.",
    }
    if not starts or not ends:
        if starts:
            report["measurement_status"] = "open_or_incomplete_window"
        report["detail"] = "Falta una ventana cerrada; no se inventan resultados. Conservar el registro parcial."
        return report
    start, end = starts[0]["elapsed_s"], ends[-1]["elapsed_s"]
    duration = end - start
    if duration <= 0:
        raise ValueError("La ventana de medición debe tener duración positiva.")
    window = [e for e in events if start <= e["elapsed_s"] < end]
    readings = [e for e in window if e["kind"] == "reading" and not e["duplicate"]]
    intervals = [b["elapsed_s"] - a["elapsed_s"] for a, b in zip(readings, readings[1:])]
    gap_s = metadata["gap_s"]
    times = [start] + [r["elapsed_s"] for r in readings] + [end]
    gaps = [{"start_s": a, "end_s": b, "duration_s": b - a,
             "boundary": "whole_window" if not readings else "start" if i == 0 else
             "end" if i == len(times) - 2 else "between_readings"}
            for i, (a, b) in enumerate(zip(times, times[1:])) if b - a > gap_s]
    observer_outages = _observer_coverage(events, start, end)
    bins = []
    for index in range(math.ceil(duration / 60)):
        a, b = start + index * 60, min(end, start + (index + 1) * 60)
        n = sum(a <= r["elapsed_s"] < b for r in readings)
        bins.append({"start_s": a, "duration_s": b - a, "unique_readings": n, "hz": n / (b - a)})
    source_intervals = [r["uptime_delta_ms"] / 1000 for r in readings if r.get("uptime_delta_ms") is not None]
    # El primer delta podría referirse a una publicación anterior a la ventana.
    if readings and readings[0].get("uptime_delta_ms") is not None:
        source_intervals = source_intervals[1:]
    report.update({
        "measurement_status": "completed" if ends[-1]["completed"] else "interrupted",
        "window_start_s": start, "window_end_s": end, "actual_duration_s": duration,
        "valid_messages": sum(e["kind"] == "reading" for e in window),
        "distance_messages_received": sum(e["kind"] in {"reading", "rejected"} for e in window),
        "unique_readings": len(readings),
        "duplicate_messages": sum(e["kind"] == "reading" and e["duplicate"] for e in window),
        "rejected_messages": dict(Counter(e["reason"] for e in window if e["kind"] == "rejected")),
        "frequency_hz_whole_window": len(readings) / duration,
        "frequency_hz_first_to_last": (len(readings) - 1) / (readings[-1]["elapsed_s"] - readings[0]["elapsed_s"])
            if len(readings) > 1 and readings[-1]["elapsed_s"] > readings[0]["elapsed_s"] else None,
        "receive_interval_s": distribution(intervals), "device_uptime_interval_s": distribution(source_intervals),
        "per_minute": bins, "silence_detection_gap_s": gap_s, "long_silences": gaps,
        "observer_outages": observer_outages,
        "device_uptime_events": dict(Counter(r["uptime_event"] for r in readings if r.get("uptime_event"))),
        "data_observed": bool(readings),
        "frequency_scope": "Recepciones MQTT del observador; no cuenta intentos del ESP32 ni pérdida exacta QoS 0.",
        "reconnection": reconnection_trials(read_jsonl(run / "markers.jsonl"), readings, events, start, end, gap_s),
    })
    if metadata.get("reference_cm") is not None:
        report["accuracy"] = accuracy_metrics(readings, metadata["reference_cm"])
    return report


def aggregate_accuracy(runs):
    rows, all_errors, modes = [], [], set()
    for run in runs:
        report = build_report(run)
        modes.add(report["mode"])
        if report.get("accuracy") is None or not report["data_observed"]:
            raise ValueError(f"{run}: falta una referencia o lecturas válidas.")
        if report["measurement_status"] != "completed":
            raise ValueError(f"{run}: la captura está interrumpida; conservarla y repetir el punto.")
        if report["observer_outages"]:
            raise ValueError(f"{run}: hubo cortes del observador; repetir el punto de exactitud.")
        rows.append({"run": str(run), **report["accuracy"]})
        reference = report["accuracy"]["reference_cm"]
        all_errors.extend(e["distance_cm"] - reference for e in read_jsonl(Path(run) / "events.jsonl")
                          if e["kind"] == "reading" and not e["duplicate"] and
                          report["window_start_s"] <= e["elapsed_s"] < report["window_end_s"])
    if not rows or len(modes) != 1:
        raise ValueError("Se requieren capturas del mismo modo; no mezclar simulaciones y mediciones reales.")
    return {"mode": modes.pop(), "per_run": rows, "pooled_samples": len(all_errors),
            "pooled_bias_cm": mean(all_errors), "pooled_mae_cm": mean(map(abs, all_errors)),
            "pooled_rmse_cm": math.sqrt(mean(e * e for e in all_errors)),
            "weighting": "Cada lectura pesa igual; consultar también cada punto por separado."}


LATENCY_FIELDS = ["trial_id", "video_file", "color", "transition", "status", "start_frame",
                  "end_frame", "fps", "observation_s", "notes"]


def latency_report(path):
    rows, seen, latencies = [], set(), []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != LATENCY_FIELDS:
            raise ValueError("Las columnas de latencia deben conservar la plantilla.")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Fila CSV incompleta o con columnas extra; entrecomillar las notas con comas.")
            trial_id = row["trial_id"]
            if not trial_id or trial_id in seen:
                raise ValueError("trial_id vacío o repetido.")
            seen.add(trial_id)
            if row["color"] not in {"red", "yellow", "green"} or row["transition"] not in {"on", "off"}:
                raise ValueError(f"{trial_id}: color o transición inválidos.")
            if row["status"] not in {"measured", "no_change", "unusable"}:
                raise ValueError(f"{trial_id}: completar status con measured, no_change o unusable.")
            if not row["video_file"]:
                raise ValueError(f"{trial_id}: falta el archivo de evidencia.")
            if row["status"] == "measured":
                fps = positive(row["fps"])
                a, b = int(row["start_frame"]), int(row["end_frame"])
                if not 0 <= a <= b:
                    raise ValueError(f"{trial_id}: fotogramas fuera de orden.")
                value = (b - a) * 1000 / fps
                latencies.append(value)
                row.update({"latency_ms": value, "conservative_frame_uncertainty_ms": 2000 / fps,
                            "lower_ms": max(0, value - 2000 / fps), "upper_ms": value + 2000 / fps})
            elif not row["notes"]:
                raise ValueError(f"{trial_id}: explicar el cambio no observado o video inutilizable.")
            if row["status"] == "no_change":
                row["observation_s"] = positive(row["observation_s"])
            rows.append(row)
    if not rows:
        raise ValueError("La planilla no contiene intentos.")
    groups = []
    for color, transition in sorted({(r["color"], r["transition"]) for r in rows}):
        group = [r for r in rows if r["color"] == color and r["transition"] == transition]
        values = [r["latency_ms"] for r in group if r["status"] == "measured"]
        groups.append({"color": color, "transition": transition, "attempts": len(group),
                       "statuses": dict(Counter(r["status"] for r in group)),
                       "measured_trials": len(values), "latency_ms": distribution(values)})
    return {"measurement": "physical_video_touch_to_light", "attempts": len(rows),
            "statuses": dict(Counter(r["status"] for r in rows)), "measured_trials": len(latencies),
            "latency_ms": distribution(latencies), "by_color_and_transition": groups, "trials": rows,
            "uncertainty": "Cota conservadora de dos fotogramas; no incluye ambigüedad humana adicional."}
