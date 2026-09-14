"""Offline contract, private split, schedule and paired-decision checks."""

import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fps_bench.evaluation_contract import (
    SOURCE_FILES, UPSTREAM_FILES, canonical, digest, freeze, paired_decision,
    schedule, split_for_controller, validate_episode_config, verify, write_development_plan,
)

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.workspace = self.home / "workspace"
        self.upstream = self.home / "upstream"
        self.games = self.home / "games"
        for name in SOURCE_FILES:
            path = self.workspace / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / name).read_bytes())
        for name in UPSTREAM_FILES:
            path = self.upstream / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture:" + name)
        index = self.games / "benchmark/01_2048/index.html"
        index.parent.mkdir(parents=True)
        index.write_text("offline game fixture")
        self.custody = self.home / "custody"
        result = freeze(self.workspace, self.upstream, self.custody, self.games)
        self.hash = result["contract_sha256"]
        self.contract = verify(self.custody / "contract.json", self.hash,
                               self.workspace, self.upstream, self.games)
        self.private = self.custody / "private-splits.json"

    def rows(self, split="development", wins=None, losses=0):
        settings = split_for_controller(self.contract, split, self.private)
        wins = len(settings["seeds"]) if wins is None else wins
        rows = []
        for index, seed in enumerate(settings["seeds"]):
            for repeat in range(settings["repeats"]):
                for candidate in ("baseline", "candidate"):
                    success = index < wins if candidate == "candidate" else wins <= index < wins + losses
                    rows.append({"contract_sha256": self.hash, "candidate": candidate, "split": split,
                                 "seed": seed, "repeat": repeat, "status": "complete", "success": success,
                                 "steps": 60, "invalid_actions": 0, "seconds": 100.0})
        return rows

    def decide(self, rows, split="development"):
        return paired_decision(self.contract, split, rows, "baseline", "candidate", self.private)

    def test_disjoint_splits_private_custody_and_pilot_seed(self):
        splits = {name: split_for_controller(self.contract, name, self.private)
                  for name in ("train", "development", "confirmation", "sealed")}
        flattened = [seed for split in splits.values() for seed in split["seeds"]]
        self.assertEqual(len(flattened), len(set(flattened)))
        self.assertIn(42, splits["train"]["seeds"])
        self.assertEqual(len(splits["train"]["seeds"]), 256)
        self.assertNotIn("sealed", self.contract["public_splits"])
        self.assertNotIn("confirmation", self.contract["public_splits"])
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o400)
        self.assertEqual(self.custody.stat().st_mode & 0o777, 0o700)
        with self.assertRaises(ValueError):
            split_for_controller(self.contract, "sealed")

    def test_cannot_reinitialize_or_freeze_inside_researcher_tree(self):
        with self.assertRaises(FileExistsError):
            freeze(self.workspace, self.upstream, self.custody, self.games)
        with self.assertRaises(ValueError):
            freeze(self.workspace, self.upstream, self.workspace / "custody", self.games)

    def test_contract_tampering_fails_against_external_anchor(self):
        modified = copy.deepcopy(self.contract)
        modified["spec"]["rules"]["minimum_absolute_improvement"] = -1
        path = self.home / "modified.json"
        path.write_bytes(canonical(modified))
        with self.assertRaises(ValueError):
            verify(path, self.hash)

    def test_source_and_game_tampering_fail(self):
        for root, name in [(self.workspace, SOURCE_FILES[1]),
                           (self.upstream, UPSTREAM_FILES[0]),
                           (self.games, "benchmark/01_2048/index.html")]:
            path = root / name
            original = path.read_bytes()
            path.write_bytes(original + b"tampered")
            with self.assertRaises(ValueError):
                verify(self.custody / "contract.json", self.hash, self.workspace, self.upstream, self.games)
            path.write_bytes(original)

    def test_source_symlink_escape_is_rejected(self):
        path = self.workspace / SOURCE_FILES[1]
        original = path.read_bytes()
        outside = self.home / "outside.py"
        outside.write_bytes(original)
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaises(ValueError):
            verify(self.custody / "contract.json", self.hash, self.workspace)

    def test_private_split_commitment_rejects_modification(self):
        private = json.loads(self.private.read_bytes())
        private["splits"]["sealed"]["seeds"][0] = 42
        modified = self.home / "private-modified.json"
        modified.write_bytes(canonical(private))
        with self.assertRaises(ValueError):
            split_for_controller(self.contract, "sealed", modified)

    def test_schedule_reproducibility_pairing_and_factorial_coverage(self):
        first = schedule(self.contract, "development", ["baseline", "candidate"], 7)
        self.assertEqual(first, schedule(self.contract, "development", ["baseline", "candidate"], 7))
        self.assertEqual(len(first), 32)
        self.assertEqual(len({run["episode_id"] for run in first}), 32)
        orders = set()
        for index in range(0, len(first), 2):
            left, right = first[index:index + 2]
            self.assertEqual((left["seed"], left["repeat"]), (right["seed"], right["repeat"]))
            orders.add(left["candidate"])
        self.assertEqual(orders, {"baseline", "candidate"})
        self.assertEqual(len(schedule(self.contract, "development", ["bb", "bm", "db", "dm"], 7)), 64)

    def test_plan_writes_seed_configs_without_dispatch(self):
        output = self.home / "plan"
        result = write_development_plan(self.custody / "contract.json", self.hash, output, ["baseline"], 1)
        self.assertEqual(result["episodes"], 16)
        plan = json.loads((output / "plan.json").read_bytes())
        self.assertEqual(plan["execution_status"], "not_started")
        for run in plan["runs"]:
            config = json.loads((output / run["config_file"]).read_bytes())
            self.assertEqual(config["seed"], run["seed"])
            self.assertEqual(config["max_steps"], 60)
        with self.assertRaises(FileExistsError):
            write_development_plan(self.custody / "contract.json", self.hash, output, ["baseline"], 1)

    def test_development_nominates_but_does_not_promote(self):
        result = self.decide(self.rows())
        self.assertEqual(result["decision"], "nominate")
        self.assertEqual(result["independent_seeds"], 8)
        self.assertEqual(result["episodes_per_candidate"], 16)
        self.assertEqual(result["one_sided_sign_p"], 1 / 256)

    def test_confirmation_requires_both_effect_and_significance(self):
        result = self.decide(self.rows("confirmation"), "confirmation")
        self.assertEqual(result["decision"], "confirmation_pass")
        result = self.decide(self.rows("confirmation", wins=3), "confirmation")
        self.assertEqual(result["absolute_improvement"], 0.125)
        self.assertEqual(result["decision"], "inconclusive")
        self.assertEqual(result["one_sided_sign_p"], 0.125)
        self.assertEqual(self.decide(self.rows(wins=0))["decision"], "no_improvement")

    def test_missing_failed_duplicate_and_cross_contract_results(self):
        rows = self.rows()
        self.assertEqual(self.decide(rows[:-1])["decision"], "incomplete")
        broken = copy.deepcopy(rows)
        broken[0]["status"] = "timeout"
        del broken[0]["success"]
        result = self.decide(broken)
        self.assertEqual(result["decision"], "infrastructure_failure")
        self.assertIsNone(result["success_rate"])
        with self.assertRaises(ValueError):
            self.decide(rows + [rows[0]])
        rows[0]["contract_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.decide(rows)

    def test_invalid_metrics_and_regressions_fail(self):
        rows = self.rows()
        rows[0]["seconds"] = math.nan
        with self.assertRaises(ValueError):
            self.decide(rows)
        for metric, value in [("seconds", 200), ("invalid_actions", 10)]:
            rows = self.rows()
            for row in rows:
                if row["candidate"] == "candidate":
                    row[metric] = value
            self.assertEqual(self.decide(rows)["decision"], "regression")

    def test_sealed_and_training_cannot_select_candidates(self):
        for split in ("train", "sealed"):
            with self.assertRaises(ValueError):
                self.decide([], split)

    def test_guarded_episode_rejects_config_change_before_execution(self):
        from fps_bench.gameworld_baseline import main
        config = {**self.contract["episode_template"], "seed": 7, "max_steps": 120}
        configuration = self.home / "episode.json"
        configuration.write_bytes(canonical(config))
        output = self.home / "episode-output"
        arguments = ["gameworld_baseline", "--output", str(output), "--config", str(configuration),
                     "--contract", str(self.custody / "contract.json"), "--contract-sha256", self.hash,
                     "--expected-driver-sha256", "0" * 64,
                     "--expected-served-model", self.contract["episode_template"]["served_model"]]
        with patch("sys.argv", arguments), patch("fps_bench.gameworld_baseline.verify", return_value=self.contract), \
                patch("fps_bench.gameworld_baseline.run") as execute:
            with self.assertRaises(ValueError):
                main()
            execute.assert_not_called()
        self.assertFalse(output.exists())

    def test_episode_configuration_rejects_bad_seeds_and_limits(self):
        config = json.loads((ROOT / "configs/qwen-gameworld-baseline.json").read_bytes())
        self.assertEqual(validate_episode_config(config), config)
        for field, value in [("seed", True), ("seed", -1), ("seed", 2**32),
                             ("max_steps", 0), ("hold_ms", -1), ("settle_seconds", math.nan)]:
            with self.assertRaises(ValueError):
                validate_episode_config({**config, field: value})


if __name__ == "__main__":
    unittest.main()
