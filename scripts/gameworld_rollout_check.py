"""Offline checks for GameWorld rollout assignment and policy-message boundaries."""

import unittest

from fps_bench.gameworld_research import load_policy
from fps_bench.gameworld_rollout import training_messages, validate_assignment


class RolloutTests(unittest.TestCase):
    def setUp(self):
        self.policy, self.context = load_policy()
        game, task = self.context["splits"]["train"][0].split("--")
        self.assignment = {"schema_version": 1, "group_id": "group-one", "game": game, "task": task,
                           "seed": 42, "members": 2, "max_steps": 4,
                           "catalog_manifest_sha256": self.context["catalog_manifest_sha256"],
                           "driver_sha256": "a" * 64}

    def test_accepts_bounded_train_group(self):
        self.assertEqual(validate_assignment(self.assignment, self.policy, self.context), self.assignment)

    def test_rejects_development_task_and_single_member(self):
        game, task = self.context["splits"]["development"][0].split("--")
        invalid = {**self.assignment, "game": game, "task": task}
        with self.assertRaises(ValueError):
            validate_assignment(invalid, self.policy, self.context)
        with self.assertRaises(ValueError):
            validate_assignment({**self.assignment, "members": 1}, self.policy, self.context)

    def test_training_messages_keep_state_outside_policy_context(self):
        value = training_messages("system", ["old-0", "old-1"], "images/" + "a" * 64 + ".png")
        self.assertEqual(value[0], {"role": "system", "content": "system"})
        self.assertEqual(value[1]["content"][1]["type"], "image")
        self.assertNotIn("evaluation", str(value).lower())
        self.assertNotIn("game_state", str(value).lower())


if __name__ == "__main__":
    unittest.main()
