"""Transport tests with synthetic dataset/checkpoint bytes; no model or provider execution."""

import asyncio
import json
import time
from pathlib import Path
import unittest
import subprocess
import sys
from unittest.mock import patch

import scripts.campaign_controller_check as fixtures
from scripts.modal_training_check import FakeModal
from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.modal_artifacts import READ_FILE, TrainingArtifacts
from fps_bench.modal_training import ModalTrainingLifecycle
from fps_bench.qwen_lora import BASE_MODEL, BASE_REVISION


class FakeFiles:
    def __init__(self):
        self.data = {}
        self.writes = 0
        self.root_exists = False
        self.fail_name = None
        self.fail_after_write = False

    async def begin_stage(self):
        if self.root_exists:
            raise ValueError("destination already exists")
        self.root_exists = True

    async def write(self, name, data):
        self.writes += 1
        if name == self.fail_name and not self.fail_after_write:
            raise TimeoutError("interrupted upload")
        self.data["/dataset/" + name] = data
        if name == self.fail_name:
            raise TimeoutError("lost upload acknowledgement")

    async def read(self, path, limit=16 * 1024 * 1024):
        if path not in self.data:
            raise FileNotFoundError(path)
        if len(self.data[path]) > limit:
            raise ValueError("oversized")
        return self.data[path]


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ControllerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.controller = self.fixture.controller
        self.root = self.fixture.home / "dataset"
        self.root.mkdir()
        (self.root / "images").mkdir()
        image = b"synthetic-image-bytes-for-transport-only"
        name = "images/" + digest(image) + ".png"
        (self.root / name).write_bytes(image)
        samples = canonical({"id": "train-42:0", "messages": [{"role": "system", "content": "fixture"},
                             {"role": "user", "content": [{"type": "text", "text": "fixture"},
                             {"type": "image", "image": name}]}], "completion": [{"role": "assistant", "content": "fixture"}]})
        (self.root / "samples.jsonl").write_bytes(samples)
        manifest = {"schema_version": 1, "purpose": "train-only-action-imitation", "contract_sha256": self.fixture.hash,
                    "samples": 1, "episodes": [{"seed": 42}],
                    "files": {"samples.jsonl": digest(samples), name: digest(image)}}
        payload = canonical(manifest)
        (self.root / "dataset.json").write_bytes(payload)
        self.dataset_hash = digest(payload)
        self.controller.admit_job("train", "baseline", "training",
                                  {"split": "train", "seeds": [42], "dataset_sha256": self.dataset_hash},
                                  {"modal_micro_usd": 10_000_000}, 600)
        self.backend = FakeModal()
        self.lifecycle = ModalTrainingLifecycle(self.controller, self.backend)
        registry_check = patch.object(self.lifecycle.training_registry, "authenticate", return_value={})
        registry_check.start()
        self.addCleanup(registry_check.stop)
        self.run_async(self.lifecycle.prepare("train", workspace="test", app="test", environment="gameworld-test", environment_id="en-test", image_id="im-test"))
        self.run_async(self.lifecycle.start("train"))
        self.files = FakeFiles()
        self.artifacts = TrainingArtifacts(self.lifecycle, self.files)

    def run_async(self, call):
        return asyncio.run(call)

    def completed_worker_fixture(self):
        with self.controller.ledger.transaction() as connection:
            attempted = connection.execute("SELECT 1 FROM modal_training_attempts WHERE job_id='train'").fetchone()
        if not attempted:
            self.run_async(self.lifecycle.run_worker("train"))
        weights = b"synthetic-weights-for-transport-only"
        config = b"{}"
        manifest = {"schema_version": 1, "base_model": BASE_MODEL, "base_revision": BASE_REVISION,
                    "processor_revision": BASE_REVISION, "dataset_sha256": self.dataset_hash,
                    "contract_sha256": self.fixture.hash,
                    "files": {"adapter_config.json": digest(config), "adapter_model.safetensors": digest(weights)}}
        payload = canonical(manifest)
        result = canonical({"status": "complete", "steps": 1, "adapter_manifest_sha256": digest(payload)})
        self.files.data.update({"/output/training/adapter/adapter-manifest.json": payload,
                               "/output/training/adapter/adapter_config.json": config,
                               "/output/training/adapter/adapter_model.safetensors": weights,
                               "/output/training/result.json": result, "/output/training/loss.jsonl": b"{}\n",
                               "/output/telemetry.sqlite": b"synthetic-outbox",
                               "/output/worker-finished.json": canonical({"job_id": "train", "campaign": "offline-controller", "dataset_sha256": self.dataset_hash,
                                    "contract_sha256": self.fixture.hash, "result_sha256": digest(result)})})

    def test_stage_required_before_worker_and_readback_matches(self):
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.run_worker("train"))
        receipt = self.run_async(self.artifacts.stage("train", self.root))
        self.assertEqual(receipt["dataset_sha256"], self.dataset_hash)
        self.run_async(self.lifecycle.run_worker("train"))
        with self.assertRaises(LedgerConflict):
            self.run_async(self.artifacts.stage("train", self.root))

    def test_partial_upload_never_enables_worker_or_retries_writes(self):
        self.files.fail_name = "samples.jsonl"
        with self.assertRaises(TimeoutError):
            self.run_async(self.artifacts.stage("train", self.root))
        self.assertNotIn("/dataset/dataset.json", self.files.data)
        with self.assertRaises(LedgerConflict):
            self.run_async(self.lifecycle.run_worker("train"))
        writes = self.files.writes
        with self.assertRaises(LedgerConflict):
            self.run_async(self.artifacts.stage("train", self.root))
        self.assertEqual(self.files.writes, writes)

    def test_lost_final_ack_reconciles_without_new_writes(self):
        self.files.fail_name = "dataset.json"
        self.files.fail_after_write = True
        with self.assertRaises(TimeoutError):
            self.run_async(self.artifacts.stage("train", self.root))
        writes = self.files.writes
        self.run_async(self.artifacts.reconcile_stage("train"))
        self.assertEqual(self.files.writes, writes)
        self.run_async(self.lifecycle.run_worker("train"))

    def test_preexisting_dataset_root_refused(self):
        self.files.root_exists = True
        with self.assertRaises(ValueError):
            self.run_async(self.artifacts.stage("train", self.root))
        self.assertEqual(self.files.writes, 0)

    def test_no_export_before_worker_dispatch(self):
        self.run_async(self.artifacts.stage("train", self.root))
        with self.assertRaises(LedgerConflict):
            self.run_async(self.artifacts.export("train", self.fixture.home / "export"))

    def test_remote_reader_bounds_bytes_and_rejects_symlinks(self):
        target = self.fixture.home / "reader-target"
        target.write_bytes(b"abcdefgh")
        result = subprocess.run([sys.executable, "-c", READ_FILE, str(target), "4"], capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"abcde")
        link = self.fixture.home / "reader-link"
        link.symlink_to(target)
        result = subprocess.run([sys.executable, "-c", READ_FILE, str(link), "4"], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")

    def test_local_input_tampering_prevents_upload(self):
        (self.root / "samples.jsonl").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.run_async(self.artifacts.stage("train", self.root))
        self.assertEqual(self.files.writes, 0)

    def test_verified_export_imports_loss_after_termination(self):
        from fps_bench.telemetry import ResearchTelemetry
        from fps_bench.training_telemetry import import_training_losses
        self.run_async(self.artifacts.stage("train", self.root))
        self.completed_worker_fixture()
        row = {"step": 1, "loss": 1.25, "gradient_norm": 2.0, "supervised_tokens": 11,
               "timestamp_ns": time.time_ns()}
        result = json.loads(self.files.data["/output/training/result.json"])
        result["losses"] = [row]
        self.files.data["/output/training/result.json"] = canonical(result)
        self.files.data["/output/training/loss.jsonl"] = canonical(row)
        completion = json.loads(self.files.data["/output/worker-finished.json"])
        completion["result_sha256"] = digest(canonical(result))
        self.files.data["/output/worker-finished.json"] = canonical(completion)
        self.run_async(self.artifacts.export("train", self.fixture.home / "export"))
        self.run_async(self.lifecycle.terminate("train"))
        telemetry = ResearchTelemetry(self.fixture.home / "trusted.sqlite", "offline-controller")
        self.assertEqual(import_training_losses(self.artifacts, "train", telemetry)["inserted"], 1)
        self.assertEqual(import_training_losses(self.artifacts, "train", telemetry)["inserted"], 0)
        self.assertEqual(telemetry.snapshot()[0]["timestamp"], row["timestamp_ns"])

    def test_successful_export_records_result_but_keeps_budget_hold(self):
        self.run_async(self.artifacts.stage("train", self.root))
        self.run_async(self.lifecycle.run_worker("train"))
        self.completed_worker_fixture()
        output = self.fixture.home / "export"
        receipt = self.run_async(self.artifacts.export("train", output))
        self.assertTrue((output / "adapter/adapter_model.safetensors").is_file())
        self.assertEqual(receipt["dataset_sha256"], self.dataset_hash)
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "cleanup_pending")
        self.assertEqual(self.controller.snapshot()["budget"]["reservations"][0]["state"], "held")
        self.run_async(self.lifecycle.terminate("train"))
        self.assertEqual(self.artifacts.reconcile_export("train"), receipt)

    def test_export_recovers_after_local_receipt_before_controller_result(self):
        self.run_async(self.artifacts.stage("train", self.root))
        self.completed_worker_fixture()
        with patch.object(self.controller, "record_result", side_effect=RuntimeError("controller interrupted")):
            with self.assertRaises(RuntimeError):
                self.run_async(self.artifacts.export("train", self.fixture.home / "export"))
        self.artifacts.reconcile_export("train")
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "cleanup_pending")

    def test_tampered_checkpoint_rejected_without_completion(self):
        self.run_async(self.artifacts.stage("train", self.root))
        self.completed_worker_fixture()
        self.files.data["/output/training/adapter/adapter_model.safetensors"] = b"changed"
        with self.assertRaises(ValueError):
            self.run_async(self.artifacts.export("train", self.fixture.home / "export"))
        self.assertEqual(self.controller.snapshot()["jobs"][0]["state"], "running")

    def test_missing_completion_marker_cannot_export(self):
        self.run_async(self.artifacts.stage("train", self.root))
        self.run_async(self.lifecycle.run_worker("train"))
        with self.assertRaises(FileNotFoundError):
            self.run_async(self.artifacts.export("train", self.fixture.home / "export"))

    def test_local_export_tampering_prevents_reconciliation(self):
        self.run_async(self.artifacts.stage("train", self.root))
        self.completed_worker_fixture()
        output = self.fixture.home / "export"
        self.run_async(self.artifacts.export("train", output))
        (output / "result.json").chmod(0o600)
        (output / "result.json").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.artifacts.reconcile_export("train")


if __name__ == "__main__":
    unittest.main()
