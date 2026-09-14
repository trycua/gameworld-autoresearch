"""Offline tests for the GameWorld joint autoresearch supervisor."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fps_bench.campaign_ledger import LedgerConflict
from fps_bench.evaluation_contract import canonical, digest
from fps_bench.gameworld_research import GameWorldResearchSupervisor, load_baseline
from fps_bench.gameworld_suite_catalog import GAMEWORLD_REVISION, GAMES_REVISION


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog = self.root / "catalog.json"
        games = []
        for game_index in range(1, 35):
            game = f"{game_index:02d}_game-{game_index}"
            games.append({
                "game": game,
                "game_spec_sha256": digest(game.encode()),
                "tasks": [
                    {"task": f"{game_index:02d}_{task_index:02d}",
                     "task_spec_sha256": digest(f"{game}:{task_index}".encode())}
                    for task_index in range(1, 6)
                ],
            })
        manifest = {
            "schema_version": 1,
            "gameworld_revision": GAMEWORLD_REVISION,
            "games_revision": GAMES_REVISION,
            "scope": "all-gameworld-catalog-tasks",
            "games": games,
            "game_count": 34,
            "task_count": 170,
            "pilot": {
                "protocol": "existing-frozen-2048-v2",
                "game": "01_2048",
                "task": "01_01",
                "note": "The initial live test uses current settings; broader action support is research work.",
            },
        }
        self.catalog.write_bytes(canonical(manifest))
        self.catalog_hash = digest(canonical(manifest))
        self.policy = self.root / "policy.json"
        policy = json.loads((Path(__file__).resolve().parents[1] / "configs/gameworld-autoresearch.json").read_bytes())
        policy["catalog_manifest_sha256"] = self.catalog_hash
        self.policy.write_bytes(canonical(policy))
        self.baseline = self.root / "baseline"
        (self.baseline / "episodes").mkdir(parents=True)
        observations = []
        for game in games:
            for task in game["tasks"]:
                identity = f"{game['game']}--{task['task']}"
                episode = self.baseline / "episodes" / identity
                episode.mkdir()
                archive = f"archive:{identity}".encode()
                (episode / "artifacts.tar.gz").write_bytes(archive)
                if identity == "30_game-30--30_02":
                    payload = {"id": identity, "game": game["game"], "task": task["task"],
                               "returncode": 1, "stdout": "", "stderr": "GameWorld init failed",
                               "archive_sha256": digest(archive)}
                    (episode / "error.json").write_bytes(canonical(payload))
                    observations.append("error")
                else:
                    status = "driver_error" if identity == "01_game-1--01_01" else "executed"
                    summary = {"status": "complete", "success": False, "steps": 1, "invalid_actions": 0,
                               "execution_status": status, "progress": 0.1,
                               "usage": {"prompt_tokens": 10, "completion_tokens": 2}, "seconds": 1.0,
                               "evaluation": {}}
                    payload = {"id": identity, "game": game["game"], "task": task["task"],
                               "summary": summary, "archive_sha256": digest(archive)}
                    (episode / "receipt.json").write_bytes(canonical(payload))
                    observations.append("receipt")
        intent = {"phase": "all-catalog-one-step-compatibility-baseline",
                  "catalog_manifest_sha256": self.catalog_hash}
        self.baseline.joinpath("intent.json").write_bytes(canonical(intent))
        report = {"assignments": 170, "completed": observations.count("receipt"),
                  "failed": observations.count("error"), "pending": 0}
        report_bytes = canonical(report)
        self.baseline.joinpath("report.json").write_bytes(report_bytes)
        verification = {"status": "complete", "catalog": {"games": 34, "assignments": 170},
                        "results": {"report_sha256": digest(report_bytes)}}
        self.baseline.joinpath("completion-verification.json").write_bytes(canonical(verification))
        self.supervisor = GameWorldResearchSupervisor(
            self.root / "campaign.sqlite", self.baseline, self.policy, self.catalog)
        self.supervisor.initialize("test-gameworld")

    def reference(self):
        return [{"url": "https://example.com/paper", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                 "note": "Primary source with explicit transfer limitations."}]

    def driver_proposal(self, identity="driver-input"):
        return {
            "id": identity,
            "track": "driver",
            "hypothesis": "Foreground delivery failures come from the Linux input path.",
            "evidence": [{"task_id": "01_game-1--01_01", "signal": "driver_error"}],
            "references": self.reference(),
            "experiment": {
                "kind": "driver",
                "target_paths": ["cua-driver/rust/crates/platform-linux/src/input/mod.rs"],
                "contract_tests": ["build", "focus", "held-keys", "key-release", "mouse-delivery"],
                "evaluation_tasks": list(self.supervisor.context["splits"]["development"]),
            },
            "budget": {"modal_micro_usd": 0, "modal_training_micro_usd": 0,
                       "modal_serving_micro_usd": 0,
                       "desktop_episodes": 68, "timeout_seconds": 600},
        }

    def model_proposal(self, identity="model-grpo"):
        return {
            "id": identity,
            "track": "model",
            "hypothesis": "Grouped rollout rewards improve action selection on low-progress tasks.",
            "evidence": [{"task_id": "02_game-2--02_03", "signal": "low_progress"}],
            "references": self.reference(),
            "experiment": {
                "kind": "model", "objective": "grpo",
                "training_tasks": ["02_game-2--02_01"],
                "evaluation_tasks": list(self.supervisor.context["splits"]["development"]),
                "rollouts_per_task": 2, "max_trajectory_steps": 4, "optimizer_steps": 2,
                "sft_source_id": None,
            },
            "budget": {"modal_micro_usd": 20_000_000,
                       "modal_training_micro_usd": 5_000_000,
                       "modal_serving_micro_usd": 15_000_000,
                       "desktop_episodes": 68,
                       "timeout_seconds": 600},
        }

    def finish(self, hypothesis, action, qualified=True):
        self.supervisor.begin(hypothesis, action)
        self.supervisor.provider_started(action, "provider-" + action)
        self.supervisor.finish(action, {"candidate_id": hypothesis + "-candidate", "qualified": qualified,
                                        "artifact_sha256": "a" * 64, "metrics": {"success_rate": 0.1}})
        self.supervisor.cleanup_confirmed(action, "cleanup-" + action)

    def test_baseline_imports_all_tasks_and_signals(self):
        baseline = load_baseline(self.baseline, self.catalog, self.catalog_hash)
        self.assertEqual(baseline["totals"]["assignments"], 170)
        self.assertEqual(baseline["totals"]["errors"], 1)
        self.assertEqual(baseline["totals"]["signals"]["game_init_failure"], 1)
        self.assertEqual(baseline["totals"]["signals"]["driver_error"], 1)

    def test_scheduler_requires_both_isolated_tracks(self):
        self.supervisor.register(self.driver_proposal())
        self.supervisor.register(self.driver_proposal("driver-second"))
        self.supervisor.register(self.model_proposal())
        self.assertEqual(self.supervisor.next()["id"], "driver-input")
        self.finish("driver-input", "driver-action")
        self.assertEqual(self.supervisor.next()["id"], "model-grpo")
        self.finish("model-grpo", "model-action")
        snapshot = self.supervisor.snapshot()
        self.assertTrue(snapshot["joint_ready"])
        self.assertEqual(snapshot["next"], "driver-second")

    def test_training_and_evaluation_splits_are_enforced(self):
        proposal = self.model_proposal()
        proposal["experiment"]["training_tasks"] = ["02_game-2--02_03"]
        with self.assertRaises(ValueError):
            self.supervisor.register(proposal)

    def test_model_modal_split_and_sft_source_are_explicit(self):
        proposal = self.model_proposal("bad-modal-split")
        proposal["budget"]["modal_training_micro_usd"] -= 1
        with self.assertRaises(ValueError):
            self.supervisor.register(proposal)
        proposal = self.model_proposal("grpo-with-sft-source")
        proposal["experiment"]["sft_source_id"] = "unexpected-source"
        with self.assertRaises(ValueError):
            self.supervisor.register(proposal)
        proposal = self.model_proposal("sft-without-source")
        proposal["experiment"]["objective"] = "sft"
        proposal["experiment"]["rollouts_per_task"] = 1
        with self.assertRaises(ValueError):
            self.supervisor.register(proposal)
        proposal = self.model_proposal("sealed-eval")
        proposal["experiment"]["evaluation_tasks"] = ["02_game-2--02_05"]
        with self.assertRaises(ValueError):
            self.supervisor.register(proposal)

    def test_driver_source_scope_is_enforced(self):
        proposal = self.driver_proposal()
        proposal["experiment"]["target_paths"] = ["fps_bench/gameworld_suite_episode.py"]
        with self.assertRaises(ValueError):
            self.supervisor.register(proposal)

    def test_proposal_evidence_must_be_observed(self):
        proposal = self.driver_proposal()
        proposal["evidence"][0]["signal"] = "unsupported_current_driver"
        with self.assertRaises(ValueError):
            self.supervisor.register(proposal)

    def test_hypothesis_and_results_are_immutable(self):
        proposal = self.driver_proposal()
        self.supervisor.register(proposal)
        changed = self.driver_proposal()
        changed["hypothesis"] = "Different claim"
        with self.assertRaises(LedgerConflict):
            self.supervisor.register(changed)
        self.finish("driver-input", "driver-action", qualified=False)
        with self.assertRaises(LedgerConflict):
            self.supervisor.finish("driver-action", {"candidate_id": "other", "qualified": False,
                                                       "artifact_sha256": "b" * 64, "metrics": {}})

    def test_begin_is_idempotent_after_scheduler_advances(self):
        self.supervisor.register(self.driver_proposal())
        first = self.supervisor.begin("driver-input", "driver-action")
        self.supervisor.register(self.model_proposal())
        self.assertEqual(self.supervisor.begin("driver-input", "driver-action"), first)

    def test_provider_cleanup_and_recovery_are_explicit(self):
        self.supervisor.register(self.model_proposal())
        action = self.supervisor.begin("model-grpo", "model-action")
        self.assertEqual(action["state"], "dispatching")
        self.assertEqual(json.loads(action["reservations"]), {})
        self.assertEqual(self.supervisor.recovery_actions()[0]["action"], "reconcile-provider-submission")
        self.supervisor.provider_started("model-action", "sb-provider")
        self.assertEqual(self.supervisor.recovery_actions()[0]["action"], "inspect-export-and-request-cleanup")
        self.supervisor.finish("model-action", {"candidate_id": "model-candidate", "qualified": True,
                                                "artifact_sha256": "a" * 64, "metrics": {}})
        self.assertEqual(self.supervisor.recovery_actions()[0]["action"], "release-provider-and-record-receipt")
        self.supervisor.cleanup_confirmed("model-action", "terminated-sb-provider")
        self.assertEqual(self.supervisor.recovery_actions(), [])
        self.assertEqual(self.supervisor.snapshot()["budget"]["reservations"], [])

    def test_reinitialize_migrates_old_actions_and_reattaches_telemetry(self):
        telemetry = self.root / "telemetry.sqlite"
        reopened = GameWorldResearchSupervisor(
            self.root / "campaign.sqlite", self.baseline, self.policy, self.catalog, telemetry)
        reopened.initialize("test-gameworld")
        self.assertIsNotNone(reopened.telemetry)
        with sqlite3.connect(self.root / "campaign.sqlite") as connection:
            connection.execute("DROP TABLE gameworld_actions")
            connection.execute("CREATE TABLE gameworld_actions ("
                               "id TEXT PRIMARY KEY, hypothesis TEXT NOT NULL, kind TEXT NOT NULL, "
                               "state TEXT NOT NULL, result TEXT)")
            connection.execute("INSERT INTO gameworld_actions VALUES ('old-action','old-hypothesis',"
                               "'driver_build','running',NULL)")
        reopened.initialize("test-gameworld")
        action = reopened.recovery_actions()[0]
        self.assertEqual(action["state"], "dispatching")
        self.assertEqual(action["reservations"], {})
        self.assertGreater(action["deadline"], 0)

    def test_duplicate_evidence_and_references_are_rejected(self):
        proposal = self.driver_proposal()
        proposal["evidence"].append(dict(proposal["evidence"][0]))
        with self.assertRaises(ValueError):
            self.supervisor.register(proposal)
        proposal = self.driver_proposal("duplicate-reference")
        proposal["references"].append(dict(proposal["references"][0]))
        with self.assertRaises(ValueError):
            self.supervisor.register(proposal)


if __name__ == "__main__":
    unittest.main()
