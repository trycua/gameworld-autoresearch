"""Offline train-only data boundary tests with synthetic hash-anchored receipts."""

import copy
import json
import unittest

from PIL import Image

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.training_data import export_dataset, verify_dataset
import scripts.evaluation_contract_check as contract_fixtures


class TrainingDataTests(unittest.TestCase):
    def setUp(self):
        self.fixture = contract_fixtures.ContractTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.home / "episode"
        self.root.mkdir()
        self.output = self.fixture.home / "dataset"
        self.contract = self.fixture.contract
        self.hash = self.fixture.hash
        self.config = {**self.contract["episode_template"], "seed": 42}
        self.manifest = {"status": "complete", "contract_sha256": self.hash, "config": self.config,
                         "config_sha256": digest(canonical(self.config)), "driver_sha256": "a" * 64,
                         "source": {"frozen_hashes": self.contract["source_hashes"]},
                         **{name: self.contract["spec"]["provenance"][name]
                            for name in ("gameworld_revision", "games_revision")}}
        self.rows = []
        for index in range(6):
            name = f"{index:03d}.png"
            Image.new("RGB", tuple(self.contract["spec"]["geometry"]["desktop"]), (index, 0, 0)).save(self.root / name)
            self.rows.append({"step": index, "observation": name,
                              "observation_sha256": digest((self.root / name).read_bytes()),
                              "response": '{"action":"key","key":"left"}',
                              "action": {"action": "key", "key": "left"}, "invalid_action": None,
                              "before": {"hidden_state": "MUST_NOT_LEAK"},
                              "after": {"hidden_state": "MUST_NOT_LEAK"},
                              "evaluation": {"reward": "MUST_NOT_LEAK"}})
        self.summary = {"status": "complete", "steps": 6, "invalid_actions": 0, "success": False}
        self.receipt = {"episode_id": "train-42", "split": "train", "seed": 42,
                        "contract_sha256": self.hash, "driver_sha256": "a" * 64,
                        "served_model": self.config["served_model"], "files": {}}
        self.refresh()

    def refresh(self):
        (self.root / "manifest.json").write_bytes(canonical(self.manifest))
        (self.root / "summary.json").write_bytes(canonical(self.summary))
        (self.root / "trajectory.jsonl").write_bytes(b"".join(canonical(row) for row in self.rows))
        self.receipt["files"] = {path.name: digest(path.read_bytes()) for path in self.root.iterdir()}

    def export(self, episodes=None):
        return export_dataset(self.fixture.custody / "contract.json", self.hash,
                              episodes or [(self.root, self.receipt)], self.output)

    def test_export_screenshot_only_and_last_four_responses(self):
        result = self.export()
        manifest, verified = verify_dataset(self.output, result["dataset_sha256"], self.hash)
        self.assertEqual(len(verified), manifest["samples"])
        self.assertEqual(result["samples"], 6)
        self.assertEqual(result["seeds"], [42])
        payload = (self.output / "samples.jsonl").read_text()
        self.assertNotIn("MUST_NOT_LEAK", payload)
        self.assertNotIn('"seed"', payload)
        samples = [json.loads(line) for line in payload.splitlines()]
        self.assertEqual(samples[-1]["messages"][1]["content"][0]["text"].count('"action"'), 4)
        image = samples[0]["messages"][1]["content"][1]
        self.assertEqual(image["type"], "image")
        self.assertTrue((self.output / image["image"]).is_file())
        self.assertEqual(digest((self.output / "dataset.json").read_bytes()), result["dataset_sha256"])
        self.assertFalse(json.loads((self.output / "dataset.json").read_bytes())["episodes"][0]["success"])

    def test_development_seed_cannot_be_relabelled_train(self):
        self.receipt["seed"] = self.contract["public_splits"]["development"]["seeds"][0]
        with self.assertRaises(ValueError):
            self.export()
        self.assertFalse(self.output.exists())

    def test_all_nontrain_labels_rejected(self):
        for split in ("development", "confirmation", "sealed"):
            with self.subTest(split=split):
                self.receipt["split"] = split
                with self.assertRaises(ValueError):
                    self.export()

    def test_receipt_cannot_relabel_manifest_seed(self):
        self.receipt["seed"] = next(seed for seed in self.contract["public_splits"]["train"]["seeds"] if seed != 42)
        with self.assertRaises(ValueError):
            self.export()

    def test_tampered_artifact_rejected(self):
        with (self.root / "trajectory.jsonl").open("ab") as handle:
            handle.write(b" ")
        with self.assertRaises(ValueError):
            self.export()

    def test_symlink_image_rejected(self):
        image = self.root / "000.png"
        target = self.fixture.home / "elsewhere.png"
        image.rename(target)
        image.symlink_to(target)
        with self.assertRaises(ValueError):
            self.export()

    def test_geometry_mismatch_even_with_updated_hash_rejected(self):
        Image.new("RGB", (1, 1)).save(self.root / "000.png")
        self.rows[0]["observation_sha256"] = digest((self.root / "000.png").read_bytes())
        self.refresh()
        with self.assertRaises(ValueError):
            self.export()

    def test_invalid_action_not_a_target_but_remains_history(self):
        self.rows[0].update(response="bad action", action=None, invalid_action="invalid")
        self.summary["invalid_actions"] = 1
        self.refresh()
        self.assertEqual(self.export()["samples"], 5)
        samples = [json.loads(line) for line in (self.output / "samples.jsonl").read_text().splitlines()]
        self.assertIn("bad action", samples[0]["messages"][1]["content"][0]["text"])
        self.assertEqual(samples[0]["id"], "train-42:1")

    def test_action_response_mismatch_rejected(self):
        self.rows[0]["action"]["key"] = "right"
        self.refresh()
        with self.assertRaises(ValueError):
            self.export()

    def test_partial_and_unfrozen_episodes_rejected(self):
        for key, value in (("status", "running"), ("contract_sha256", None), ("driver_sha256", "b" * 64)):
            original = copy.deepcopy(self.manifest)
            self.manifest[key] = value
            self.refresh()
            with self.assertRaises(ValueError):
                self.export()
            self.manifest = original

    def test_duplicate_seed_rejected(self):
        second = copy.deepcopy(self.receipt)
        second["episode_id"] = "another"
        with self.assertRaises(ValueError):
            self.export([(self.root, self.receipt), (self.root, second)])

    def test_training_worker_rejects_copied_artifact_tampering(self):
        result = self.export()
        samples = self.output / "samples.jsonl"
        samples.chmod(0o600)
        samples.write_bytes(samples.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            verify_dataset(self.output, result["dataset_sha256"], self.hash)

    def test_training_worker_rejects_wrong_contract_or_anchor(self):
        result = self.export()
        with self.assertRaises(ValueError):
            verify_dataset(self.output, result["dataset_sha256"], "f" * 64)
        with self.assertRaises(ValueError):
            verify_dataset(self.output, "f" * 64, self.hash)

    def test_missing_step_rejected(self):
        self.rows.pop(2)
        self.refresh()
        with self.assertRaises(ValueError):
            self.export()


if __name__ == "__main__":
    unittest.main()
