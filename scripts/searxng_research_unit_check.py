"""Offline checks for the search-pilot metrics."""

import unittest

from searxng_research_check import expected_match, summarize


class SearchProbeTests(unittest.TestCase):
    def test_expected_urls_ignore_query_and_fragment(self):
        self.assertTrue(expected_match("https://modal.com/docs/examples/grpo_trl?source=test#top", "https://modal.com/docs/examples/grpo_trl"))

    def test_expected_urls_do_not_accept_other_hosts_or_prefixes(self):
        self.assertFalse(expected_match("https://other.com/docs/examples/grpo_trl", "https://modal.com/docs/examples/grpo_trl"))
        self.assertFalse(expected_match("https://modal.com/docs/examples/grpo_trl_bad", "https://modal.com/docs/examples/grpo_trl"))

    def test_arxiv_version_suffix_is_allowed(self):
        self.assertTrue(expected_match("https://arxiv.org/html/2604.07429v1", "https://arxiv.org/html/2604.07429"))
        self.assertFalse(expected_match("https://arxiv.org/html/2604.074290", "https://arxiv.org/html/2604.07429"))

    def test_failures_remain_in_denominator(self):
        rows = [
            {"kind": "known-source", "ok": True, "seconds": 1, "result_count": 5, "expected_hit_at_10": True},
            {"kind": "known-source", "ok": False, "seconds": 30, "result_count": 0},
            {"kind": "discovery", "ok": True, "seconds": 2, "result_count": 3, "unresponsive_engines": [["brave", "too many requests"]]},
        ]
        summary = summarize(rows)
        self.assertEqual(summary["requests"], 3)
        self.assertEqual(summary["successful_json_responses"], 2)
        self.assertEqual(summary["known_source_requests"], 2)
        self.assertEqual(summary["known_source_hits_at_10"], 1)
        self.assertEqual(summary["median_seconds"], 2)
        self.assertEqual(summary["p95_seconds_nearest_rank"], 30)
        self.assertEqual(summary["engine_errors"], {"brave: too many requests": 1})


if __name__ == "__main__":
    unittest.main()
