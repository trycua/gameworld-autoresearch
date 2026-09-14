"""Offline policy checks for dedicated Modal environment read-back."""

from datetime import datetime, timedelta, timezone
import unittest

from fps_bench.modal_environment import validate_environment


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.observed = {"workspace": "test", "name": "gameworld-test", "environment_id": "en-test",
                         "restricted": True, "default_member_role": "no-access", "max_concurrent_gpus": 1,
                         "max_concurrent_tasks": 2, "budget_dollars": "25", "effective_limit_dollars": "25",
                         "usage_dollars": "0", "spend_limit_reached": False,
                         "checked_at": datetime.now(timezone.utc).isoformat()}

    def check(self, changes=None):
        return validate_environment({**self.observed, **(changes or {})}, "gameworld-test", "en-test")

    def test_exact_pilot_policy_passes(self):
        self.assertEqual(self.check(), self.observed)

    def test_identity_drift_is_refused(self):
        for changes in ({"name": "main"}, {"environment_id": "en-replacement"}, {"environment_id": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(changes)

    def test_restriction_and_concurrency_drift_refused(self):
        for changes in ({"restricted": False}, {"default_member_role": "contributor"},
                        {"max_concurrent_gpus": 2}, {"max_concurrent_gpus": True},
                        {"max_concurrent_tasks": 3}, {"max_concurrent_tasks": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(changes)

    def test_missing_increased_or_exhausted_budget_refused(self):
        for changes in ({"budget_dollars": None}, {"budget_dollars": "26"}, {"budget_dollars": "24"},
                        {"effective_limit_dollars": "26"}, {"effective_limit_dollars": "0"},
                        {"usage_dollars": "25"}, {"spend_limit_reached": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.check(changes)

    def test_bad_money_types_refused(self):
        for value in (25, True, "NaN", "Infinity", "-1", "", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check({"budget_dollars": value})

    def test_stale_future_or_naive_observation_refused(self):
        now = datetime.now(timezone.utc)
        for timestamp in (now - timedelta(seconds=61), now + timedelta(seconds=30), now.replace(tzinfo=None)):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                self.check({"checked_at": timestamp.isoformat()})


if __name__ == "__main__":
    unittest.main()
