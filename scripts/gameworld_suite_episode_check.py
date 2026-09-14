"""Offline checks for current-driver multi-game semantic actions."""

import json
from pathlib import Path
import unittest

import yaml

from fps_bench.gameworld_suite_episode import (
    CATALOG_MANIFEST_SHA256,
    SERVED_MODEL,
    prompt,
    resolve_action,
    semantic_controls,
    validate_assignment,
)


CATALOG = Path("/tmp/gameworld-upstream-catalog/catalog")


class SuiteEpisodeTests(unittest.TestCase):
    def game(self, name):
        return yaml.safe_load((CATALOG / "games" / f"{name}.yaml").read_text())

    def task(self, game, task):
        return yaml.safe_load((CATALOG / "tasks" / game / f"{task}.yaml").read_text())

    def test_all_catalog_controls_are_represented(self):
        games = sorted((CATALOG / "games").glob("[0-9][0-9]_*.yaml"))
        self.assertEqual(len(games), 34)
        self.assertTrue(all(semantic_controls(yaml.safe_load(path.read_text())) for path in games))

    def test_single_role_action(self):
        controls = semantic_controls(self.game("01_2048"))
        result = resolve_action('{"tool_name":"move_left","arguments":{}}', controls)
        self.assertEqual(result["binding"]["key"], "ArrowLeft")

    def test_multi_role_actions_are_distinct(self):
        controls = semantic_controls(self.game("12_fireboy-and-watergirl"))
        self.assertIn("watergirl.move_left", controls)
        self.assertIn("fireboy.move_left", controls)
        self.assertNotEqual(controls["watergirl.move_left"]["binding"]["key"],
                            controls["fireboy.move_left"]["binding"]["key"])

    def test_minesweeper_cell_is_catalog_bounded(self):
        controls = semantic_controls(self.game("19_minesweeper"))
        result = resolve_action('{"tool_name":"reveal_cell","arguments":{"cell":"a1"}}', controls)
        self.assertEqual((result["binding"]["x"], result["binding"]["y"]), (539, 146))
        with self.assertRaises(ValueError):
            resolve_action('{"tool_name":"reveal_cell","arguments":{"cell":"z9"}}', controls)

    def test_wordle_requires_text(self):
        controls = semantic_controls(self.game("32_wordle"))
        with self.assertRaises(ValueError):
            resolve_action('{"tool_name":"type_text","arguments":{}}', controls)
        result = resolve_action('{"tool_name":"type_text","arguments":{"text":"crane"}}', controls)
        self.assertEqual(result["binding"]["text"], "crane")

    def test_prompt_has_task_and_registered_actions(self):
        game = self.game("17_mario-game")
        task = self.task("17_mario-game", "17_01")
        text = prompt(game, task, semantic_controls(game))
        self.assertIn(task["task_prompt"].strip(), text)
        self.assertIn("jump_right", text)
        self.assertNotIn("game_state", text)

    def test_assignment_is_bound_to_the_pinned_catalog(self):
        assignment = {"game": "01_2048", "task": "01_01", "seed": 42,
                      "served_model": SERVED_MODEL,
                      "catalog_manifest_sha256": CATALOG_MANIFEST_SHA256}
        self.assertEqual(validate_assignment(assignment), assignment)
        with self.assertRaises(ValueError):
            validate_assignment({**assignment, "catalog_manifest_sha256": "0" * 64})


if __name__ == "__main__":
    unittest.main()
