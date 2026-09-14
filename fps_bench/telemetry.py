"""Durable scalar research events with bounded OTLP HTTP/protobuf export."""

from contextlib import contextmanager
import fcntl
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from urllib import request
from urllib.parse import urlsplit


METRICS = {
    "gameworld_train_loss": "", "gameworld_train_step": "",
    "gameworld_eval_success_rate": "1", "gameworld_eval_completed_episodes": "",
    "gameworld_eval_failed_episodes": "", "gameworld_eval_mean_progress": "1",
    "gameworld_eval_seconds": "s", "gameworld_modal_spend": "USD",
    "gameworld_modal_reserved": "USD", "gameworld_litellm_tokens": "", "gameworld_litellm_reserved_tokens": "",
    "gameworld_active_claims": "", "gameworld_active_training_jobs": "",
    "gameworld_desktop_slots_reserved": "", "gameworld_training_slots_reserved": "",
}
SERVICES = {"gameworld-research", "gameworld-eval", "gameworld-train"}
ATTRIBUTES = {"experiment", "phase", "split", "task", "change_class", "outcome", "objective"}
LABEL = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def post_protobuf(url, payload, headers):
    outgoing = request.Request(url, data=payload, method="POST", headers={
        "User-Agent": "gameworld-autoresearch-otel/0.1", **headers, "Content-Type": "application/x-protobuf"})
    with request.build_opener(NoRedirect()).open(outgoing, timeout=5) as response:
        body = response.read(65537)
        if len(body) > 65536:
            raise ValueError("Oversized OTLP response")
        return body


def text_attributes(destination, values):
    for name, value in sorted(values.items()):
        attribute = destination.add(key=name)
        attribute.value.string_value = value


class ResearchTelemetry:
    def __init__(self, path, campaign, endpoint="https://otel.cua.ai", headers=None, transport=post_protobuf):
        if not LABEL.fullmatch(campaign):
            raise ValueError("Invalid campaign label")
        parsed = urlsplit(endpoint)
        if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or (parsed.scheme != "https" and not (
                    parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")))):
            raise ValueError("OTLP endpoint requires HTTPS, except loopback tests")
        self.path, self.campaign = Path(path), campaign
        self.endpoint, self.headers, self.transport = endpoint.rstrip("/"), headers or {}, transport
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS identity (campaign TEXT PRIMARY KEY)")
            connection.execute("CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, "
                               "id TEXT UNIQUE NOT NULL, timestamp INTEGER NOT NULL, payload TEXT NOT NULL, "
                               "logs_sent INTEGER NOT NULL DEFAULT 0)")
            connection.execute("CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY)")
            connection.execute("CREATE TABLE IF NOT EXISTS series (id TEXT PRIMARY KEY)")
            existing = connection.execute("SELECT campaign FROM identity").fetchone()
            if existing and existing[0] != campaign:
                raise ValueError("Telemetry database belongs to another campaign")
            connection.execute("INSERT OR IGNORE INTO identity VALUES (?)", (campaign,))

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            with connection:
                yield connection
        finally:
            connection.close()

    def record(self, event_id, service, attributes, values, step=None):
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 128:
            raise ValueError("Stable event ID required")
        if service not in SERVICES or set(attributes) - ATTRIBUTES or "experiment" not in attributes:
            raise ValueError("Unsupported service or labels")
        if any(not isinstance(value, str) or not LABEL.fullmatch(value) for value in attributes.values()):
            raise ValueError("Labels must be bounded identifiers, never payloads or URLs")
        if not values or set(values) - METRICS.keys():
            raise ValueError("Unsupported metric")
        for name, value in values.items():
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Metrics must be finite scalars")
            if name != "gameworld_train_loss" and value < 0:
                raise ValueError("Only training loss may be negative")
            if name in ("gameworld_eval_success_rate", "gameworld_eval_mean_progress") and value > 1:
                raise ValueError("Evaluation ratios must be in [0,1]")
        if step is not None and (type(step) is not int or step < 0):
            raise ValueError("Optimizer step must be a nonnegative integer")
        payload = json.dumps({"service": service, "attributes": {"campaign": self.campaign, **attributes},
                              "values": values, "step": step}, sort_keys=True, allow_nan=False)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT payload FROM events WHERE id=?", (event_id,)).fetchone()
            if existing:
                if existing[0] != payload:
                    raise ValueError("Event ID reused with different telemetry")
                return False
            experiments = {row[0] for row in connection.execute("SELECT id FROM experiments")}
            if attributes["experiment"] not in experiments and len(experiments) >= 12:
                raise ValueError("Campaign experiment cardinality exceeded")
            existing_series = {row[0] for row in connection.execute("SELECT id FROM series")}
            new_series = {json.dumps([service, attributes, name], sort_keys=True) for name in values}
            if len(existing_series | new_series) > 512:
                raise ValueError("Campaign metric series cardinality exceeded")
            connection.execute("INSERT OR IGNORE INTO experiments VALUES (?)", (attributes["experiment"],))
            connection.executemany("INSERT OR IGNORE INTO series VALUES (?)", [(key,) for key in new_series])
            connection.execute("INSERT INTO events(id,timestamp,payload) VALUES (?,?,?)",
                               (event_id, time.time_ns(), payload))
        return True

    def snapshot(self):
        with self.connect() as connection:
            rows = connection.execute("SELECT sequence,id,timestamp,payload,logs_sent FROM events ORDER BY sequence").fetchall()
        return [{"sequence": row[0], "id": row[1], "timestamp": row[2], **json.loads(row[3]),
                 "logs_sent": bool(row[4])} for row in rows]

    def export_metrics(self, events):
        from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
        result = ExportMetricsServiceRequest()
        latest = {}
        for event in events:
            for name, value in event["values"].items():
                key = (event["service"], json.dumps(event["attributes"], sort_keys=True), name)
                latest[key] = (event, value)
        for (_, _, name), (event, value) in latest.items():
            resource = result.resource_metrics.add()
            text_attributes(resource.resource.attributes, {"service.name": event["service"]})
            scope = resource.scope_metrics.add()
            scope.scope.name = "gameworld-autoresearch"
            metric = scope.metrics.add(name=name, unit=METRICS[name])
            point = metric.gauge.data_points.add(time_unix_nano=event["timestamp"], as_double=value)
            text_attributes(point.attributes, event["attributes"])
        return result.SerializeToString()

    def export_logs(self, events):
        from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
        result = ExportLogsServiceRequest()
        for event in events:
            resource = result.resource_logs.add()
            text_attributes(resource.resource.attributes, {"service.name": event["service"]})
            scope = resource.scope_logs.add()
            scope.scope.name = "gameworld-autoresearch"
            record = scope.log_records.add(time_unix_nano=event["timestamp"], observed_time_unix_nano=time.time_ns(),
                                          severity_number=9, severity_text="INFO")
            record.body.string_value = json.dumps({"event_id": event["id"], "step": event["step"],
                                                   "values": event["values"], **event["attributes"]}, sort_keys=True)
            text_attributes(record.attributes, event["attributes"])
        return result.SerializeToString()

    def flush(self):
        try:
            with self.path.with_suffix(self.path.suffix + ".export.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self._flush_locked()
        except Exception as error:
            return {"metrics": False, "logs": False, "errors": [{"signal": "lock", "type": type(error).__name__}]}

    def _flush_locked(self):
        result = {"metrics": False, "logs": False, "errors": []}
        try:
            events = self.snapshot()
            pending = [event for event in events if not event["logs_sent"]][:100]
            for signal in ("metrics", "logs"):
                selected = events if signal == "metrics" else pending
                if not selected:
                    result[signal] = True
                    continue
                try:
                    from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceResponse
                    from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceResponse
                    payload = self.export_metrics(selected) if signal == "metrics" else self.export_logs(selected)
                    response = self.transport(f"{self.endpoint}/v1/{signal}", payload, self.headers)
                    message = ExportMetricsServiceResponse() if signal == "metrics" else ExportLogsServiceResponse()
                    message.ParseFromString(response)
                    rejected = (message.partial_success.rejected_data_points if signal == "metrics"
                                else message.partial_success.rejected_log_records)
                    if rejected or message.partial_success.error_message:
                        raise ValueError("OTLP partial success; retain events for replay")
                    if signal == "logs":
                        with self.connect() as connection:
                            connection.executemany("UPDATE events SET logs_sent=1 WHERE id=?",
                                                   [(event["id"],) for event in selected])
                    result[signal] = True
                except Exception as error:
                    result["errors"].append({"signal": signal, "type": type(error).__name__})
            result["pending_logs"] = sum(not event["logs_sent"] for event in self.snapshot())
        except Exception as error:
            result["errors"].append({"signal": "outbox", "type": type(error).__name__})
        return result
