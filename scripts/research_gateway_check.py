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
from fps_bench.research_gateway import ResearchGateway, REQUEST_HOLD, usage_observation


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.ledger = CampaignLedger(Path(self.directory.name) / "ledger.sqlite")
        self.ledger.initialize("gateway-tests")
        self.calls = []
        self.response = json.dumps({"id": "test", "choices": [], "usage": {
            "prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}}).encode()
        self.server = ResearchGateway(("127.0.0.1", 0), self.ledger, "client-" + "x" * 40,
                                      "upstream-secret", self.transport)
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
        return self.response

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

    def test_budget_refusal_never_contacts_provider(self):
        self.ledger.reserve("existing", "litellm_tokens", 1_000_000_000, int(time.time()) + 3600)
        self.assertEqual(self.post()[0], 429)
        self.assertEqual(self.calls, [])

    def test_success_retains_hold_until_provider_reconciliation(self):
        status, body, headers = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(body, self.response)
        held = self.ledger.snapshot()["reservations"]
        self.assertEqual(len(held), 1)
        self.assertEqual(held[0]["amount"], REQUEST_HOLD)
        self.assertEqual(held[0]["state"], "held")
        self.assertEqual(held[0]["id"], headers["X-Gameworld-Dispatch-ID"])
        self.assertEqual(self.calls[0][1], "upstream-secret")
        self.assertNotIn(b"upstream-secret", body)

    def test_duplicate_client_requests_are_separately_reserved(self):
        self.assertEqual(self.post()[0], 200)
        self.assertEqual(self.post()[0], 200)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(self.ledger.snapshot()["reservations"]), 2)

    def test_timeout_freezes_and_keeps_reservation(self):
        self.response = TimeoutError("upstream-secret must never reach response")
        status, body, _ = self.post()
        self.assertEqual(status, 502)
        self.assertNotIn(b"upstream-secret", body)
        self.assertTrue(self.ledger.snapshot()["campaign"]["frozen"])
        self.assertEqual(self.post()[0], 429)
        self.assertEqual(len(self.calls), 1)

    def test_missing_usage_fails_closed(self):
        self.response = b'{"choices":[]}'
        self.assertEqual(self.post()[0], 502)
        self.assertTrue(self.ledger.snapshot()["campaign"]["frozen"])

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
        for content in ["x" * 70000, [{"type": "image_url", "image_url": {"url": "https://example.com"}}]]:
            self.assertEqual(self.post({"model": "astra", "messages": [{"role": "user", "content": content}]})[0], 400)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
