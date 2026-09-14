"""Offline checks for GameWorld rollout assignment and policy-message boundaries."""

import asyncio
import json
import unittest
from unittest.mock import patch

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_research import load_policy
from fps_bench.gameworld_rollout import collect, training_messages, validate_assignment
import scripts.gameworld_grpo_check as grpo_fixtures


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

    def test_collect_keeps_distinct_initial_states_without_rejecting_group(self):
        fixture = grpo_fixtures.GrpoTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        _, manifest = fixture.build()
        driver = fixture.root / "driver"
        driver.write_bytes(b"test-driver")
        assignment = {**self.assignment, "driver_sha256": digest(driver.read_bytes())}
        assignment_path = fixture.root / "assignment.json"
        assignment_path.write_bytes(canonical(assignment))
        endpoint = "https://example.test/v1"
        identity = fixture.policy_identity
        identity["deployment"]["endpoint_sha256"] = digest(endpoint.encode())
        identity_path = fixture.root / "policy.json"
        identity_path.write_bytes(canonical(identity))
        states = [{"board": [2, 0, 2, 0], "timestampMs": stamp} for stamp in (100, 200)]

        async def member(_assignment, _policy, _driver, dataset, custody, index):
            result = manifest["groups"][0]["members"][index]
            for name in manifest["files"]:
                (dataset / name).write_bytes((fixture.root / name).read_bytes())
            runtime = custody / result["id"]
            runtime.mkdir()
            (runtime / "initial-state.json").write_bytes(canonical(states[index]))
            return result, {"id": result["id"], "initial_state_sha256": digest(canonical(states[index])),
                            "usage": {"prompt_tokens": 0, "completion_tokens": 0}, "seconds": 1}

        output = fixture.root / "output"
        with patch("fps_bench.gameworld_rollout.collect_member", side_effect=member), \
                patch("fps_bench.gameworld_rollout.endpoint", return_value=endpoint), \
                patch("fps_bench.gameworld_rollout.request", return_value={"data": [{"id": identity["served_model"]}]}):
            result = asyncio.run(collect(assignment_path, identity_path, output, driver))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["trajectories"], 2)
        custody = json.loads((output / "custody-manifest.json").read_bytes())
        self.assertEqual([entry["initial_state_sha256"] for entry in custody["members"]],
                         [digest(canonical(state)) for state in states])
        dataset = json.loads((output / "dataset/rollouts.json").read_bytes())
        self.assertEqual(dataset["groups"][0]["initial_state_sha256"], digest(canonical(states[0])))


if __name__ == "__main__":
    unittest.main()
