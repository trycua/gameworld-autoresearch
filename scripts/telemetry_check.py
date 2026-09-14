"""Offline protobuf/outbox checks; run in the telemetry optional-dependency environment."""

import math
from pathlib import Path
import tempfile
import unittest

from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest, ExportLogsServiceResponse
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest, ExportMetricsServiceResponse
from fps_bench.telemetry import ResearchTelemetry


class TelemetryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "telemetry.sqlite"
        self.calls = []
        self.response = b""
        self.telemetry = ResearchTelemetry(self.path, "offline-tests", transport=self.transport)

    def transport(self, url, payload, headers):
        self.calls.append((url, payload))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def record(self, event="step-1", loss=2.0, step=1):
        return self.telemetry.record(event, "gameworld-train", {"experiment": "smoke", "phase": "train"},
                                     {"gameworld_train_loss": loss, "gameworld_train_step": step}, step)

    def test_original_time_survives_replay_and_out_of_order_import(self):
        attributes = {"experiment": "smoke", "phase": "train"}
        self.telemetry.record("new", "gameworld-train", attributes,
                              {"gameworld_train_loss": 1.0}, timestamp_ns=2000)
        self.telemetry.record("old", "gameworld-train", attributes,
                              {"gameworld_train_loss": 2.0}, timestamp_ns=1000)
        self.assertFalse(self.telemetry.record("old", "gameworld-train", attributes,
                                             {"gameworld_train_loss": 2.0}, timestamp_ns=1000))
        with self.assertRaises(ValueError):
            self.telemetry.record("old", "gameworld-train", attributes,
                                  {"gameworld_train_loss": 2.0}, timestamp_ns=1001)
        payload = ExportMetricsServiceRequest.FromString(self.telemetry.export_metrics(self.telemetry.snapshot()))
        point = payload.resource_metrics[0].scope_metrics[0].metrics[0].gauge.data_points[0]
        self.assertEqual((point.time_unix_nano, point.as_double), (2000, 1.0))
        for invalid in (True, 0, -1, 1.5, 2**63):
            with self.assertRaises(ValueError):
                self.telemetry.record("invalid", "gameworld-train", attributes,
                                      {"gameworld_train_loss": 1.0}, timestamp_ns=invalid)

    def test_negative_policy_loss_is_preserved(self):
        self.record(loss=-0.25)
        self.telemetry.record("policy-step", "gameworld-train", {"experiment": "smoke", "phase": "train"},
                              {"gameworld_train_policy_loss": -0.5,
                               "gameworld_train_clip_fraction": 0.25})
        self.assertTrue(self.telemetry.flush()["metrics"])
        self.assertEqual(self.telemetry.snapshot()[0]["values"]["gameworld_train_loss"], -0.25)
        with self.assertRaises(ValueError):
            self.telemetry.record("bad-clip", "gameworld-train", {"experiment": "smoke"},
                                  {"gameworld_train_clip_fraction": 1.01})

    def test_event_identity_is_immutable_and_deduplicated(self):
        self.assertTrue(self.record())
        self.assertFalse(self.record())
        with self.assertRaises(ValueError):
            self.record(loss=3)
        self.assertEqual(len(self.telemetry.snapshot()), 1)

    def test_restart_preserves_events_and_campaign_identity(self):
        self.record()
        reopened = ResearchTelemetry(self.path, "offline-tests", transport=self.transport)
        self.assertEqual(len(reopened.snapshot()), 1)
        with self.assertRaises(ValueError):
            ResearchTelemetry(self.path, "wrong-campaign")

    def test_metrics_replay_latest_gauges_without_counting_twice(self):
        self.record()
        self.record("step-2", loss=1.5, step=2)
        self.assertTrue(self.telemetry.flush()["metrics"])
        first = ExportMetricsServiceRequest.FromString(self.calls[0][1])
        values = {metric.name: metric.gauge.data_points[0].as_double
                  for resource in first.resource_metrics for scope in resource.scope_metrics for metric in scope.metrics}
        self.assertEqual(values, {"gameworld_train_loss": 1.5, "gameworld_train_step": 2})
        self.telemetry.flush()
        self.assertEqual(self.calls[0][1], self.calls[2][1])
        self.assertEqual(len(self.calls), 3)

    def test_logs_retain_optimizer_steps_without_metric_label(self):
        self.record()
        self.telemetry.flush()
        metrics = ExportMetricsServiceRequest.FromString(self.calls[0][1])
        for resource in metrics.resource_metrics:
            for scope in resource.scope_metrics:
                for metric in scope.metrics:
                    self.assertNotIn("step", {attribute.key for attribute in metric.gauge.data_points[0].attributes})
        logs = ExportLogsServiceRequest.FromString(self.calls[1][1])
        body = logs.resource_logs[0].scope_logs[0].log_records[0].body.string_value
        self.assertIn('"step": 1', body)
        self.assertIn('"event_id": "step-1"', body)

    def test_network_failure_preserves_pending_data_and_omits_secrets(self):
        self.record()
        self.response = TimeoutError("secret credential must not escape")
        result = self.telemetry.flush()
        self.assertFalse(result["metrics"])
        self.assertEqual(result["pending_logs"], 1)
        self.assertNotIn("secret", str(result))
        self.response = b""
        self.assertEqual(self.telemetry.flush()["pending_logs"], 0)

    def test_partial_success_does_not_acknowledge_logs(self):
        self.record()
        response = ExportLogsServiceResponse()
        response.partial_success.rejected_log_records = 1
        self.response = response.SerializeToString()
        result = self.telemetry.flush()
        self.assertFalse(result["logs"])
        self.assertEqual(result["pending_logs"], 1)

    def test_log_batch_is_bounded(self):
        for index in range(105):
            self.record(f"step-{index}", step=index)
        self.assertEqual(self.telemetry.flush()["pending_logs"], 5)
        self.assertEqual(self.telemetry.flush()["pending_logs"], 0)

    def test_labels_metrics_and_nonfinite_values_are_rejected(self):
        for values in [{"password": 1}, {"gameworld_train_loss": math.nan}, {"gameworld_eval_success_rate": 2},
                       {"gameworld_train_loss": True}]:
            with self.assertRaises(ValueError):
                self.telemetry.record("bad", "gameworld-train", {"experiment": "smoke"}, values)
        for attributes in [{"experiment": "smoke", "prompt": "secret"}, {"experiment": "https://example.com"}]:
            with self.assertRaises(ValueError):
                self.telemetry.record("bad", "gameworld-train", attributes, {"gameworld_train_loss": 1})

    def test_experiment_cardinality_is_bounded(self):
        for index in range(12):
            self.telemetry.record(str(index), "gameworld-train", {"experiment": f"candidate-{index}"},
                                  {"gameworld_train_loss": 1})
        with self.assertRaises(ValueError):
            self.telemetry.record("extra", "gameworld-train", {"experiment": "extra"}, {"gameworld_train_loss": 1})

    def test_endpoint_credentials_and_remote_plaintext_rejected(self):
        for endpoint in ["http://example.com", "https://user:secret@example.com", "https://example.com?token=x"]:
            with self.assertRaises(ValueError):
                ResearchTelemetry(self.path, "offline-tests", endpoint=endpoint)


if __name__ == "__main__":
    unittest.main()
