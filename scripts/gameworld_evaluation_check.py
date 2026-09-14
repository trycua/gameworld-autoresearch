"""Offline checks for the all-catalog GameWorld evaluation contract."""

import json
from pathlib import Path
import tempfile
import unittest

from fps_bench.evaluation_contract import canonical, digest, schedule
from fps_bench.gameworld_evaluation import SOURCE_FILES, build_contract, validate_contract
from fps_bench.gameworld_research import load_policy


ROOT = Path(__file__).resolve().parents[1]


class GameWorldEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.policy, self.context = load_policy()
        self.baseline = {"baseline_sha256": "a" * 64,
                         "catalog_manifest_sha256": self.context["catalog_manifest_sha256"],
                         "totals": {"assignments": 170}}
        self.image = "ghcr.io/trycua/gameworld-autoresearch@sha256:" + "b" * 64
        source_hashes = {name: digest(name.encode()) for name in SOURCE_FILES}
        self.contract, self.private = build_contract(
            self.policy, self.context, self.baseline, self.image, source_hashes)
        self.contract_hash = digest(canonical(self.contract))

    def test_contract_covers_every_game_in_disjoint_task_splits(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.json"
            private.write_bytes(canonical(self.private))
            validate_contract(self.contract, self.contract_hash, private)
        self.assertEqual(len(self.contract["public_splits"]["train"]["tasks"]), 68)
        self.assertEqual(len(self.contract["public_splits"]["development"]["tasks"]), 34)
        self.assertNotIn("sealed", self.contract["public_splits"])

    def test_development_schedule_is_paired_across_all_games(self):
        runs = schedule(self.contract, "development", ["baseline", "candidate"], 9)
        self.assertEqual(len(runs), 136)
        self.assertEqual(len({run["task_id"] for run in runs}), 34)
        self.assertEqual(len({run["game"] for run in runs}), 34)

    def test_contract_rejects_mutable_or_wrong_registry_images(self):
        for image in ("ghcr.io/trycua/gameworld-autoresearch:gameworld",
                      "ghcr.io/example/gameworld@sha256:" + "b" * 64):
            with self.assertRaises(ValueError):
                build_contract(self.policy, self.context, self.baseline, image,
                               {name: digest(name.encode()) for name in SOURCE_FILES})

    def test_private_split_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.json"
            changed = json.loads(canonical(self.private))
            changed["splits"]["sealed"]["tasks"].pop()
            private.write_bytes(canonical(changed))
            with self.assertRaises(ValueError):
                validate_contract(self.contract, self.contract_hash, private)


if __name__ == "__main__":
    unittest.main()
