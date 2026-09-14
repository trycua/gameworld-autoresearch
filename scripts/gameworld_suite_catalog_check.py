"""Checks for the pinned 34-game, 170-task research scope."""

import copy
import json
from pathlib import Path
import unittest

from fps_bench.gameworld_suite_catalog import load, validate


ROOT = Path(__file__).resolve().parents[1]


class SuiteCatalogTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.summary = load(ROOT / "configs/evaluation/gameworld-suite-v1.json")

    def test_complete_catalog(self):
        self.assertEqual(self.summary["game_count"], 34)
        self.assertEqual(self.summary["task_count"], 170)
        self.assertEqual({item["game"] for item in self.manifest["games"]},
                         {f"{index:02d}_{item['game'].split('_', 1)[1]}"
                          for index, item in enumerate(self.manifest["games"], 1)})

    def test_every_game_has_five_unique_tasks(self):
        identities = {(game["game"], task["task"])
                      for game in self.manifest["games"] for task in game["tasks"]}
        self.assertEqual(len(identities), 170)
        self.assertTrue(all(len(game["tasks"]) == 5 for game in self.manifest["games"]))

    def test_missing_game_or_task_is_refused(self):
        for mutation in ("game", "task"):
            changed = copy.deepcopy(self.manifest)
            if mutation == "game":
                changed["games"].pop()
                changed["game_count"] -= 1
                changed["task_count"] -= 5
            else:
                changed["games"][0]["tasks"].pop()
                changed["task_count"] -= 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(changed)

    def test_fleet_image_pins_same_revisions(self):
        dockerfile = (ROOT / "image/Dockerfile.gameworld").read_text()
        self.assertIn("ARG GAMEWORLD_REVISION=" + self.manifest["gameworld_revision"], dockerfile)
        self.assertIn("ARG GAMEWORLD_GAMES_REVISION=" + self.manifest["games_revision"], dockerfile)

    def test_pilot_does_not_claim_full_suite_support(self):
        self.assertEqual(self.manifest["pilot"]["protocol"], "existing-frozen-2048-v2")
        self.assertIn("research work", self.manifest["pilot"]["note"])


if __name__ == "__main__":
    unittest.main()
