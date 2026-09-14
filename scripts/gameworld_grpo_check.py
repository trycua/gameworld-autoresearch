"""Offline tests for GameWorld GRPO rewards and rollout custody."""

import json
import importlib.util
from pathlib import Path
import tempfile
import unittest

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_grpo import group_advantages, reward_components, verify_rollout_dataset
from fps_bench.gameworld_research import load_policy


class GrpoTests(unittest.TestCase):
    def setUp(self):
        self.policy, self.context = load_policy()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "images").mkdir()
        (self.root / "trajectories").mkdir()
        self.policy_identity = {
            "base_model": self.policy["model"]["base_model"],
            "base_revision": self.policy["model"]["base_revision"],
            "adapter_sha256": None,
            "served_model": "qwen3-vl-2b-instruct-89644892e4d8",
            "deployment": {"app_id": "ap-Test", "function_id": "fu-Test", "image_id": "im-Test",
                           "endpoint_sha256": "c" * 64},
            "generation": {"temperature": 0.8, "top_p": 0.95, "max_tokens": 128,
                           "response_format": "unconstrained-json-text"},
        }
        self.driver = "a" * 64

    def build(self, rewards=(0.0, 0.25)):
        files, members = {}, []
        task = self.context["splits"]["train"][0]
        game, task_name = task.split("--")
        for index, progress in enumerate(rewards):
            image = f"image-{index}".encode()
            image_name = f"images/{digest(image)}.png"
            (self.root / image_name).write_bytes(image)
            files[image_name] = digest(image)
            response = '{"tool_name":"wait","arguments":{}}'
            row = {"step": 0,
                   "messages": [{"role": "system", "content": "play"},
                                {"role": "user", "content": [{"type": "text", "text": "act"},
                                                               {"type": "image", "image": image_name}]}],
                   "response": response, "observation": image_name, "observation_sha256": digest(image),
                   "action": {"tool_name": "wait", "arguments": {}}, "invalid_action": None}
            data = canonical(row)
            trajectory_id = f"trajectory-{index}"
            trajectory = f"trajectories/{trajectory_id}.jsonl"
            (self.root / trajectory).write_bytes(data)
            files[trajectory] = digest(data)
            summary = {"steps": 1, "success": False, "progress": progress,
                       "invalid_actions": 0, "driver_errors": 0}
            components = reward_components(summary, self.policy["model"]["grpo"])
            members.append({"id": trajectory_id, "trajectory": trajectory,
                            "trajectory_sha256": digest(data), **summary,
                            "reward_components": components, "reward": components["total"]})
        manifest = {"schema_version": 1, "purpose": "gameworld-interactive-grpo-v1",
                    "catalog_manifest_sha256": self.context["catalog_manifest_sha256"],
                    "policy": self.policy_identity, "driver_sha256": self.driver,
                    "reward": self.policy["model"]["grpo"],
                    "groups": [{"id": "group-one", "game": game, "task": task_name, "seed": 42,
                                "initial_state_sha256": "b" * 64, "members": members}],
                    "files": files}
        payload = canonical(manifest)
        (self.root / "rollouts.json").write_bytes(payload)
        return digest(payload), manifest

    def test_reward_components_are_bounded_and_reproducible(self):
        values = reward_components({"steps": 4, "success": True, "progress": 0.5,
                                    "invalid_actions": 1, "driver_errors": 1}, self.policy["model"]["grpo"])
        self.assertAlmostEqual(values["total"], 1.075)
        with self.assertRaises(ValueError):
            reward_components({"steps": 0, "success": False, "progress": 0,
                               "invalid_actions": 0, "driver_errors": 0}, self.policy["model"]["grpo"])

    def test_group_advantages_and_zero_variance(self):
        result = group_advantages([1.0, 3.0])
        self.assertEqual(result["advantages"], [-1.0, 1.0])
        self.assertTrue(group_advantages([2.0, 2.0])["zero_variance"])

    def test_verified_rollout_dataset_has_no_privileged_state(self):
        identity, _ = self.build()
        result = verify_rollout_dataset(self.root, identity, policy=self.policy, context=self.context,
                                        expected_policy=self.policy_identity, expected_driver_sha256=self.driver)
        self.assertEqual(result["trajectories"], 2)
        self.assertEqual(result["zero_variance_groups"], 0)

    def test_tampered_reward_and_wrong_split_are_rejected(self):
        identity, manifest = self.build()
        manifest["groups"][0]["members"][0]["reward"] = 10
        payload = canonical(manifest)
        (self.root / "rollouts.json").write_bytes(payload)
        with self.assertRaises(ValueError):
            verify_rollout_dataset(self.root, digest(payload), policy=self.policy, context=self.context,
                                    expected_policy=self.policy_identity, expected_driver_sha256=self.driver)
        manifest["groups"][0]["members"][0]["reward"] = manifest["groups"][0]["members"][0]["reward_components"]["total"]
        sealed = self.context["splits"]["sealed"][0].split("--")
        manifest["groups"][0].update(game=sealed[0], task=sealed[1])
        payload = canonical(manifest)
        (self.root / "rollouts.json").write_bytes(payload)
        with self.assertRaises(ValueError):
            verify_rollout_dataset(self.root, digest(payload), policy=self.policy, context=self.context,
                                    expected_policy=self.policy_identity, expected_driver_sha256=self.driver)

    def test_privileged_message_data_and_unused_files_are_rejected(self):
        _, manifest = self.build()
        trajectory = manifest["groups"][0]["members"][0]["trajectory"]
        row = json.loads((self.root / trajectory).read_bytes())
        row["messages"][1]["content"][0]["evaluation"] = {"success": True}
        data = canonical(row)
        (self.root / trajectory).write_bytes(data)
        manifest["files"][trajectory] = digest(data)
        manifest["groups"][0]["members"][0]["trajectory_sha256"] = digest(data)
        payload = canonical(manifest)
        (self.root / "rollouts.json").write_bytes(payload)
        with self.assertRaises(ValueError):
            verify_rollout_dataset(self.root, digest(payload), policy=self.policy, context=self.context,
                                    expected_policy=self.policy_identity, expected_driver_sha256=self.driver)

    @unittest.skipUnless(importlib.util.find_spec("torch"), "training extra is not installed")
    def test_grpo_tensor_objective_backpropagates(self):
        import torch
        from fps_bench.gameworld_grpo import grpo_loss

        current = torch.tensor([[-0.5, -0.7], [-0.4, -0.9]], requires_grad=True)
        old = current.detach().clone()
        reference = old.clone()
        mask = torch.tensor([[True, True], [True, False]])
        advantages = torch.tensor([1.0, -1.0])
        loss, metrics = grpo_loss(current, old, reference, mask, advantages, clip_epsilon=0.2, beta=0.01)
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertTrue(torch.isfinite(current.grad).all())
        self.assertEqual(set(metrics), {"policy_loss", "reference_kl", "clip_fraction"})


if __name__ == "__main__":
    unittest.main()
