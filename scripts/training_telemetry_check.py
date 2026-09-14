"""Offline import/replay checks; synthetic scalars, no model or provider execution."""

import copy
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.telemetry import ResearchTelemetry
from fps_bench.training_data import checked_bytes
from fps_bench.training_telemetry import import_training_losses


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.telemetry = ResearchTelemetry(self.root / "trusted.sqlite", "offline-import")
        self.rows = [{"step": 1, "loss": 1.25, "gradient_norm": 2.0, "supervised_tokens": 11,
                      "timestamp_ns": time.time_ns() - 1_000_000}]
        self.receipt = {"output": str(self.root), "files": {}, "adapter_manifest_sha256": "a" * 64}
        self.artifacts = SimpleNamespace(
            lifecycle=SimpleNamespace(stored=lambda job: (
                {"kind": "training", "deadline": int(time.time()) + 60}, {},
                {"tags": {"campaign": "offline-import"}})),
            reconcile_export=self.reconcile)
        self.write_bundle()

    def write_bundle(self, result_rows=None):
        payloads = {"loss.jsonl": b"".join(canonical(row) for row in self.rows),
                    "result.json": canonical({"status": "complete", "steps": len(self.rows),
                                               "losses": self.rows if result_rows is None else result_rows}),
                    "telemetry.sqlite": b"not SQLite: never open this"}
        for name, data in payloads.items():
            (self.root / name).write_bytes(data)
            self.receipt["files"][name] = digest(data)

    def reconcile(self, job):
        for name, expected in self.receipt["files"].items():
            checked_bytes(self.root, name, expected)
        return self.receipt

    def test_import_replay_restart_preserve_time_without_worker_sqlite(self):
        result = import_training_losses(self.artifacts, "train", self.telemetry)
        self.assertEqual(result["inserted"], 1)
        reopened = ResearchTelemetry(self.telemetry.path, "offline-import")
        self.assertEqual(import_training_losses(self.artifacts, "train", reopened)["inserted"], 0)
        event = reopened.snapshot()[0]
        self.assertEqual(event["timestamp"], self.rows[0]["timestamp_ns"])
        self.assertEqual(event["values"]["gameworld_train_loss"], 1.25)
        self.assertEqual(event["attributes"]["campaign"], "offline-import")

    def test_different_campaign_refused_before_reconciliation(self):
        self.artifacts.reconcile_export = Mock(side_effect=AssertionError("must not reconcile"))
        wrong = ResearchTelemetry(self.root / "wrong.sqlite", "wrong-campaign")
        with self.assertRaises(ValueError):
            import_training_losses(self.artifacts, "train", wrong)

    def test_tampered_export_or_failed_reconciliation_never_emits(self):
        (self.root / "loss.jsonl").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            import_training_losses(self.artifacts, "train", self.telemetry)
        self.assertEqual(self.telemetry.snapshot(), [])
        self.artifacts.reconcile_export = Mock(side_effect=ValueError("checkpoint mismatch"))
        with self.assertRaises(ValueError):
            import_training_losses(self.artifacts, "train", self.telemetry)
        self.assertEqual(self.telemetry.snapshot(), [])

    def test_cross_file_disagreement_refused(self):
        mismatch = copy.deepcopy(self.rows)
        mismatch[0]["loss"] = 10
        self.write_bundle(mismatch)
        with self.assertRaises(ValueError):
            import_training_losses(self.artifacts, "train", self.telemetry)
        self.assertEqual(self.telemetry.snapshot(), [])

    def test_all_rows_validated_before_any_emission(self):
        original = copy.deepcopy(self.rows[0])
        for update in ({"step": True}, {"loss": "1.0"}, {"gradient_norm": -1},
                       {"timestamp_ns": True}, {"timestamp_ns": time.time_ns() + 10**12},
                       {"supervised_tokens": 0}, {"campaign": "injected"}):
            with self.subTest(update=update):
                self.rows = [original, {**original, "step": 2,
                                       "timestamp_ns": original["timestamp_ns"] + 1, **update}]
                self.write_bundle()
                with self.assertRaises(ValueError):
                    import_training_losses(self.artifacts, "train", self.telemetry)
                self.assertEqual(self.telemetry.snapshot(), [])

    def test_missing_original_timestamp_refused(self):
        del self.rows[0]["timestamp_ns"]
        self.write_bundle()
        with self.assertRaises(ValueError):
            import_training_losses(self.artifacts, "train", self.telemetry)


if __name__ == "__main__":
    unittest.main()
