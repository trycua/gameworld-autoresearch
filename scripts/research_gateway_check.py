"""Offline HTTP relay contract tests; no provider requests or spend."""

import json
from pathlib import Path
import tempfile
import subprocess
import threading
import time
import unittest
from urllib import request, error

from fps_bench.campaign_ledger import CampaignLedger
from fps_bench.research_gateway import (
    ATTEMPT_HOLD,
    LiteLLMSpendReconciler,
    MAX_BODY,
    ResearchGateway,
    REQUEST_HOLD,
    usage_observation,
)


class Reconciler:
    admin_key = "admin-" + "z" * 40

    def __init__(self):
        self.calls = []
        self.error = None

    def reconcile(self, call_id, usage, started_at):
        self.calls.append((call_id, usage, started_at))
        if self.error is not None:
            raise self.error
        return {"settled_tokens": usage["total_tokens"], "attempted_retries": 0,
                "failed_attempt_rows": 0, "receipt": "litellm-spend:" + call_id}


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger = CampaignLedger(Path(self.directory.name) / "ledger.sqlite")
        self.ledger.initialize("gateway-tests")
        self.ledger.remove_token_budget()
        self.calls = []
        self.response = json.dumps({"id": "test", "choices": [], "usage": {
            "prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}}).encode()
        self.reconciler = Reconciler()
        self.server = ResearchGateway(("127.0.0.1", 0), self.ledger, "client-" + "x" * 40,
                                      "upstream-secret-key", self.transport)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def transport(self, body, key, dispatch):
        self.calls.append((body, key, dispatch))
        if isinstance(self.response, Exception):
            raise self.response
        return {"payload": self.response, "headers": {"x-litellm-call-id": dispatch}}

    def post(self, body=None, token=None, route="/v1/chat/completions"):
        payload = body if body is not None else {
            "model": "gpt-5.6-sol", "messages": [{"role": "user", "content": "hello"}]}
        outgoing = request.Request(f"http://127.0.0.1:{self.server.server_port}{route}",
                                   data=json.dumps(payload).encode(), headers={
                                       "Authorization": "Bearer " + (token or self.server.client_token),
                                       "Content-Type": "application/json"})
        try:
            with request.urlopen(outgoing) as response:
                return response.status, response.read(), response.headers
        except error.HTTPError as response:
            return response.code, response.read(), response.headers

    def test_authorization_fails_before_admission(self):
        self.assertEqual(self.post(token="wrong")[0], 401)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.ledger.snapshot()["reservations"], [])

    def test_modal_freeze_never_contacts_provider(self):
        self.ledger.freeze("Provider charges exceed retained Modal allocation")
        self.assertEqual(self.post()[0], 429)
        self.assertEqual(self.calls, [])

    def test_success_does_not_reserve_or_settle_tokens(self):
        status, body, headers = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(body, self.response)
        self.assertEqual(self.ledger.snapshot()["reservations"], [])
        self.assertEqual(self.reconciler.calls, [])
        self.assertTrue(headers["X-Gameworld-Dispatch-ID"].startswith("litellm:"))
        self.assertNotIn(b"upstream-secret-key", body)

    def test_duplicate_client_requests_do_not_reserve_tokens(self):
        self.assertEqual(self.post()[0], 200)
        self.assertEqual(self.post()[0], 200)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.ledger.snapshot()["reservations"], [])

    def test_real_driver_source_fits_without_token_reservation(self):
        source = Path("cua-driver/rust/crates/platform-linux/src/input/mod.rs").read_text()
        self.assertGreater(len(source.encode()), 65_536)
        body = {"model": "gpt-5.6-sol", "messages": [{"role": "user", "content": source}]}
        self.assertLess(len(json.dumps(body).encode()), MAX_BODY)
        self.assertEqual(self.post(body)[0], 200)
        self.assertEqual(self.ledger.snapshot()["reservations"], [])

    def test_oversized_source_is_rejected_before_budget_or_provider(self):
        body = {"model": "gpt-5.6-sol", "messages": [{"role": "user", "content": "x" * MAX_BODY}]}
        self.assertEqual(self.post(body)[0], 400)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.ledger.snapshot()["reservations"], [])

    def test_timeout_does_not_freeze_or_reserve(self):
        self.response = TimeoutError("upstream-secret-key must never reach response")
        status, body, _ = self.post()
        self.assertEqual(status, 502)
        self.assertNotIn(b"upstream-secret-key", body)
        self.assertFalse(self.ledger.snapshot()["campaign"]["frozen"])
        self.assertEqual(self.ledger.snapshot()["reservations"], [])
        with self.ledger.transaction() as connection:
            failure = json.loads(connection.execute(
                "SELECT payload FROM events WHERE kind='dispatch_failed'").fetchone()[0])
        self.assertEqual(failure["phase"], "upstream_transport")
        self.assertEqual(failure["error_type"], "TimeoutError")
        self.assertNotIn("upstream-secret-key", json.dumps(failure))
        self.response = b'{"choices":[]}'
        self.assertEqual(self.post()[0], 200)

    def test_http_failure_records_status_without_response_body(self):
        self.response = error.HTTPError("https://example.com", 503, "upstream-secret-key", {}, None)
        self.assertEqual(self.post()[0], 502)
        with self.ledger.transaction() as connection:
            failure = json.loads(connection.execute(
                "SELECT payload FROM events WHERE kind='dispatch_failed'").fetchone()[0])
        self.assertEqual(failure["http_status"], 503)
        self.assertEqual(failure["phase"], "upstream_transport")
        self.assertNotIn("upstream-secret-key", json.dumps(failure))

    def test_missing_usage_is_forwarded_without_freezing(self):
        self.response = b'{"choices":[]}'
        self.assertEqual(self.post()[0], 200)
        with self.ledger.transaction() as connection:
            received = json.loads(connection.execute(
                "SELECT payload FROM events WHERE kind='upstream_response_received'").fetchone()[0])
            event = json.loads(connection.execute(
                "SELECT payload FROM events WHERE kind='usage_unavailable'").fetchone()[0])
        self.assertEqual(event["id"], received["id"])
        self.assertFalse(self.ledger.snapshot()["campaign"]["frozen"])
        self.assertEqual(self.ledger.snapshot()["reservations"], [])

    def test_stream_usage_preserves_sse_bytes(self):
        self.response = b'data: {"choices":[]}\n\ndata: {"usage":{"prompt_tokens":30,"completion_tokens":10,"total_tokens":40}}\n\ndata: [DONE]\n\n'
        status, response, headers = self.post({"model": "astra", "stream": True,
                                              "messages": [{"role": "user", "content": "hello"}]})
        self.assertEqual(status, 200)
        self.assertEqual(response, self.response)
        self.assertEqual(headers["Content-Type"], "text/event-stream")
        self.assertEqual(self.calls[0][0]["stream_options"], {"include_usage": True})

    def test_installed_pi_sdk_streams_through_gateway(self):
        chunks = [
            {"id": "offline", "object": "chat.completion.chunk", "created": 0, "model": "astra",
             "choices": [{"index": 0, "delta": {"role": "assistant", "content": "READY"}, "finish_reason": None}]},
            {"id": "offline", "object": "chat.completion.chunk", "created": 0, "model": "astra",
             "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            {"id": "offline", "object": "chat.completion.chunk", "created": 0, "model": "astra",
             "choices": [], "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}},
        ]
        self.response = ("".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks)
                         + "data: [DONE]\n\n").encode()
        script = """
          import { completeSimple } from './tools/pi/node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/dist/compat.js';
          const model = {id:'astra',name:'test',provider:'cua-litellm',api:'openai-completions',
            baseUrl:process.argv[1],reasoning:true,input:['text'],contextWindow:128000,maxTokens:16384,
            cost:{input:0,output:0,cacheRead:0,cacheWrite:0},
            compat:{supportsStore:false,maxTokensField:'max_completion_tokens'}};
          const result = await completeSimple(model, {messages:[{role:'user',content:'hello',timestamp:0}]},
            {apiKey:process.argv[2],maxTokens:16,reasoning:'low'});
          if (result.stopReason === 'error') throw Error(result.errorMessage);
          if (result.content[0]?.text !== 'READY') throw Error('Unexpected reply');
          console.log('SDK_READY');
        """
        result = subprocess.run(["node", "--input-type=module", "-e", script,
                                 f"http://127.0.0.1:{self.server.server_port}/v1", self.server.client_token],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SDK_READY", result.stdout)
        self.assertEqual(len(self.calls), 1)

    def test_partial_stream_is_not_a_complete_receipt(self):
        with self.assertRaises(ValueError):
            usage_observation(b'data: {"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}\n', True)

    def test_untrusted_routes_models_limits_and_metadata_rejected(self):
        base = {"model": "astra", "messages": [{"role": "user", "content": "hello"}]}
        for fields in [{"model": "unapproved"}, {"api_base": "https://attacker.invalid"},
                       {"metadata": {"anything": "untrusted"}}, {"max_completion_tokens": 100000},
                       {"n": 2}, {"max_tokens": True}]:
            self.assertEqual(self.post({**base, **fields})[0], 400)
        self.assertEqual(self.post(route="/key/generate")[0], 404)
        self.assertEqual(self.calls, [])

    def test_images_and_large_bodies_rejected_before_dispatch(self):
        for content in ["x" * MAX_BODY, [{"type": "image_url", "image_url": {"url": "https://example.com"}}]]:
            self.assertEqual(self.post({"model": "astra", "messages": [{"role": "user", "content": content}]})[0], 400)
        self.assertEqual(self.calls, [])


class SpendReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.alias = "gameworld-autoresearch-test"
        self.call_id = "call-1234567890123456"
        self.usage = {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}
        self.pages = []

    def transport(self, base_url, admin_key, key_alias, start_date, end_date, page):
        self.pages.append((base_url, admin_key, key_alias, start_date, end_date, page))
        return {"data": [self.row()], "page": page, "page_size": 100, "total": 1, "total_pages": 1}

    def row(self, **changes):
        row = {"request_id": "request-one", "status": "success",
               "prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40,
               "metadata": {"litellm_call_id": self.call_id,
                            "user_api_key_alias": self.alias,
                            "attempted_retries": 0, "max_retries": 2}}
        row.update(changes)
        return row

    def reconciler(self, transport=None, polls=1):
        return LiteLLMSpendReconciler(
            "admin-" + "z" * 40, self.alias, transport=transport or self.transport,
            poll_attempts=polls, poll_seconds=0)

    def test_authenticated_log_settles_exact_no_retry_usage(self):
        result = self.reconciler().reconcile(self.call_id, self.usage, time.time())
        self.assertEqual(result["settled_tokens"], 40)
        self.assertEqual(result["attempted_retries"], 0)
        self.assertTrue(result["receipt"].startswith("litellm-spend:"))
        self.assertEqual(self.pages[0][2], self.alias)

    def test_hidden_retry_reserves_conservative_attempt_upper_bound(self):
        def retried(*args):
            row = self.row()
            row["metadata"]["attempted_retries"] = 1
            return {"data": [row], "page": 1, "total_pages": 1}
        result = self.reconciler(retried).reconcile(self.call_id, self.usage, time.time())
        self.assertEqual(result["settled_tokens"], ATTEMPT_HOLD + 40)

    def test_logged_failed_attempt_usage_replaces_upper_bound(self):
        def retried(*args):
            success = self.row()
            success["metadata"]["attempted_retries"] = 1
            failure = self.row(request_id="request-failed", status="failure",
                               prompt_tokens=20, completion_tokens=0, total_tokens=20)
            return {"data": [success, failure], "page": 1, "total_pages": 1}
        result = self.reconciler(retried).reconcile(self.call_id, self.usage, time.time())
        self.assertEqual(result["settled_tokens"], 60)

    def test_usage_alias_and_retry_mismatches_fail_closed(self):
        cases = []
        wrong_usage = self.row(total_tokens=41)
        cases.append([wrong_usage])
        wrong_alias = self.row()
        wrong_alias["metadata"]["user_api_key_alias"] = "another"
        cases.append([wrong_alias])
        excessive = self.row()
        excessive["metadata"].update(attempted_retries=3, max_retries=3)
        cases.append([excessive])
        for rows in cases:
            with self.subTest(rows=rows):
                transport = lambda *args, rows=rows: {"data": rows, "page": 1, "total_pages": 1}
                with self.assertRaises(ValueError):
                    self.reconciler(transport).reconcile(self.call_id, self.usage, time.time())

    def test_every_retry_row_requires_dedicated_key_and_unique_identity(self):
        for failure_change in [
            {"metadata": {"litellm_call_id": self.call_id,
                          "user_api_key_alias": "another"}},
            {"request_id": "request-one"},
            {"request_id": None},
        ]:
            success = self.row()
            success["metadata"]["attempted_retries"] = 1
            failure = self.row(request_id="request-failed", status="failure", total_tokens=20)
            failure.update(failure_change)
            rows = [success, failure]
            with self.subTest(failure_change=failure_change):
                transport = lambda *args, rows=rows: {"data": rows, "page": 1, "total_pages": 1}
                with self.assertRaises(ValueError):
                    self.reconciler(transport).reconcile(self.call_id, self.usage, time.time())

    def test_missing_log_exhausts_bounded_poll(self):
        calls = []
        def empty(*args):
            calls.append(args)
            return {"data": [], "page": 1, "total_pages": 0}
        with self.assertRaises(ValueError):
            self.reconciler(empty, polls=3).reconcile(self.call_id, self.usage, time.time())
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
