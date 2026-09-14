"""Local research relay with durable admission and authenticated settlement."""

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import ssl
import time
from urllib import parse, request
from uuid import uuid4

from fps_bench.campaign_ledger import BudgetRefused, CampaignLedger


MODELS = ("astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
UPSTREAM_ROOT = "https://litellm-public.tail204509.ts.net"
UPSTREAM = UPSTREAM_ROOT + "/v1/chat/completions"
MAX_BODY = 65_536
MAX_RESPONSE = 8 * 1024 * 1024
ATTEMPT_HOLD = 144_384
MAX_UPSTREAM_RETRIES = 2
REQUEST_HOLD = ATTEMPT_HOLD * (MAX_UPSTREAM_RETRIES + 1)
MAX_SPEND_LOG_PAGES = 10
ALLOWED = {"model", "messages", "tools", "tool_choice", "stream", "stream_options",
           "max_completion_tokens", "max_tokens", "temperature", "top_p", "reasoning_effort",
           "response_format", "stop", "parallel_tool_calls", "store"}


def validated_request(body):
    if not isinstance(body, dict) or set(body) - ALLOWED:
        raise ValueError("Unsupported request fields")
    if body.get("model") not in MODELS:
        raise ValueError("Model is not admitted")
    messages = body.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 64:
        raise ValueError("Expected 1-64 messages")
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in ("system", "developer", "user", "assistant", "tool"):
            raise ValueError("Invalid message")
        content = message.get("content")
        if content is not None and not isinstance(content, (str, list)):
            raise ValueError("Invalid message content")
        if isinstance(content, list) and any(
            not isinstance(part, dict) or set(part) != {"type", "text"}
            or part["type"] != "text" or not isinstance(part["text"], str) for part in content
        ):
            raise ValueError("Research gateway currently accepts text only")
    if "max_tokens" in body and "max_completion_tokens" in body:
        raise ValueError("Specify only one output limit")
    maximum = body.get("max_completion_tokens", body.get("max_tokens", 16384))
    if type(maximum) is not int or not 1 <= maximum <= 16384:
        raise ValueError("Output limit must be 1-16384 tokens")
    if "stream" in body and type(body["stream"]) is not bool:
        raise ValueError("stream must be boolean")
    result = dict(body)
    result.pop("max_tokens", None)
    result["max_completion_tokens"] = maximum
    result.pop("store", None)
    if result.get("stream"):
        result["stream_options"] = {"include_usage": True}
    else:
        result.pop("stream_options", None)
    return result


def usage_observation(payload, streaming):
    objects = []
    if streaming:
        done = False
        for line in payload.decode("utf-8").splitlines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                done = True
            else:
                objects.append(json.loads(data))
        if not done:
            raise ValueError("Incomplete event stream")
    else:
        objects.append(json.loads(payload))
    usages = [entry["usage"] for entry in objects if isinstance(entry, dict) and entry.get("usage")]
    if len(usages) != 1 or not isinstance(usages[0], dict):
        raise ValueError("Expected exactly one final usage observation")
    usage = usages[0]
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if type(usage.get(name)) is not int or usage[name] < 0:
            raise ValueError("Missing or invalid token usage")
    if usage["prompt_tokens"] + usage["completion_tokens"] != usage["total_tokens"]:
        raise ValueError("Inconsistent token usage")
    return {name: usage[name] for name in ("prompt_tokens", "completion_tokens", "total_tokens")}


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def upstream_request(body, api_key, dispatch_id):
    opener = request.build_opener(NoRedirect(), request.HTTPSHandler(context=ssl.create_default_context()))
    outgoing = request.Request(UPSTREAM, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "X-Gameworld-Dispatch-ID": dispatch_id,
    })
    with opener.open(outgoing, timeout=120) as response:
        payload = response.read(MAX_RESPONSE + 1)
        if len(payload) > MAX_RESPONSE:
            raise ValueError("Upstream response too large")
        return {"payload": payload, "headers": {name.lower(): value for name, value in response.headers.items()}}


def spend_logs_request(base_url, admin_key, key_alias, start_date, end_date, page):
    query = parse.urlencode({
        "key_alias": key_alias, "start_date": start_date, "end_date": end_date,
        "page": page, "page_size": 100, "sort_by": "startTime", "sort_order": "desc",
    })
    outgoing = request.Request(base_url.rstrip("/") + "/spend/logs/v2?" + query, headers={
        "Authorization": f"Bearer {admin_key}", "Accept": "application/json",
    })
    opener = request.build_opener(NoRedirect(), request.HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(outgoing, timeout=30) as response:
        payload = response.read(MAX_RESPONSE + 1)
    if len(payload) > MAX_RESPONSE:
        raise ValueError("LiteLLM spend-log response too large")
    return json.loads(payload)


class LiteLLMSpendReconciler:
    def __init__(self, admin_key, key_alias, base_url=UPSTREAM_ROOT, transport=spend_logs_request,
                 poll_attempts=8, poll_seconds=2):
        parsed = parse.urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Spend reconciliation requires a credential-free HTTPS LiteLLM endpoint")
        if not isinstance(admin_key, str) or len(admin_key) < 16:
            raise ValueError("Spend reconciliation requires an authenticated admin credential")
        if (not isinstance(key_alias, str) or not key_alias.startswith("gameworld-autoresearch-")
                or len(key_alias) > 128):
            raise ValueError("Spend reconciliation requires a dedicated GameWorld key alias")
        if type(poll_attempts) is not int or not 1 <= poll_attempts <= 30:
            raise ValueError("Spend-log poll attempts must be 1..30")
        if type(poll_seconds) not in (int, float) or not 0 <= poll_seconds <= 30:
            raise ValueError("Spend-log poll delay must be 0..30 seconds")
        self.admin_key = admin_key
        self.key_alias = key_alias
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.poll_attempts = poll_attempts
        self.poll_seconds = poll_seconds

    def _fetch(self, started_at):
        start = datetime.fromtimestamp(started_at - 300, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        end = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        rows = []
        for page in range(1, MAX_SPEND_LOG_PAGES + 1):
            result = self.transport(
                self.base_url, self.admin_key, self.key_alias, start, end, page)
            if (not isinstance(result, dict) or not isinstance(result.get("data"), list)
                    or type(result.get("page")) is not int or type(result.get("total_pages")) is not int
                    or result["page"] != page or not 0 <= result["total_pages"] <= MAX_SPEND_LOG_PAGES):
                raise ValueError("LiteLLM spend-log pagination is invalid or exceeds its bound")
            rows.extend(result["data"])
            if page >= result["total_pages"]:
                break
        return rows

    def reconcile(self, call_id, response_usage, started_at):
        if not isinstance(call_id, str) or not 16 <= len(call_id) <= 128:
            raise ValueError("LiteLLM response omitted its immutable call identity")
        for attempt in range(self.poll_attempts):
            matches = []
            for row in self._fetch(started_at):
                metadata = row.get("metadata")
                if isinstance(metadata, dict) and metadata.get("litellm_call_id") == call_id:
                    matches.append(row)
            if matches:
                break
            if attempt + 1 < self.poll_attempts:
                time.sleep(self.poll_seconds)
        else:
            raise ValueError("Authenticated LiteLLM spend log did not materialize")
        request_ids = []
        for row in matches:
            metadata = row.get("metadata") if isinstance(row, dict) else None
            request_id = row.get("request_id") if isinstance(row, dict) else None
            if (not isinstance(metadata, dict) or metadata.get("user_api_key_alias") != self.key_alias
                    or not isinstance(request_id, str) or not 1 <= len(request_id) <= 256):
                raise ValueError("LiteLLM spend log belongs to another virtual key or lacks identity")
            request_ids.append(request_id)
        if len(set(request_ids)) != len(matches):
            raise ValueError("LiteLLM spend logs contain duplicate request identities")
        successes = [row for row in matches if row.get("status") == "success"]
        failures = [row for row in matches if row.get("status") == "failure"]
        if len(successes) != 1 or len(successes) + len(failures) != len(matches):
            raise ValueError("LiteLLM call lacks one authenticated terminal success")
        success = successes[0]
        metadata = success["metadata"]
        usage = {name: success.get(name) for name in ("prompt_tokens", "completion_tokens", "total_tokens")}
        for name, value in usage.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"LiteLLM spend log has invalid {name}")
        if usage["prompt_tokens"] + usage["completion_tokens"] != usage["total_tokens"]:
            raise ValueError("LiteLLM spend log token totals are inconsistent")
        if usage != response_usage or usage["total_tokens"] > ATTEMPT_HOLD:
            raise ValueError("Response usage differs from authenticated LiteLLM accounting")
        retries, maximum = metadata.get("attempted_retries"), metadata.get("max_retries")
        if (type(retries) is not int or type(maximum) is not int or not 0 <= retries <= maximum
                or maximum > MAX_UPSTREAM_RETRIES or len(failures) > retries):
            raise ValueError("LiteLLM retry accounting exceeds the admitted bound")
        failed_usage = 0
        for row in failures:
            total = row.get("total_tokens")
            failed_usage += total if type(total) is int and 0 <= total <= ATTEMPT_HOLD else ATTEMPT_HOLD
        actual = usage["total_tokens"] + failed_usage + (retries - len(failures)) * ATTEMPT_HOLD
        if actual > REQUEST_HOLD:
            raise ValueError("Reconciled LiteLLM usage exceeds its reservation")
        evidence = {
            "call_id": call_id, "key_alias": self.key_alias,
            "request_ids": sorted(request_ids),
            "response_usage": usage, "attempted_retries": retries,
            "failed_attempt_rows": len(failures), "settled_tokens": actual,
        }
        return {**evidence, "receipt": "litellm-spend:" + hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


class ResearchGateway(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, ledger, client_token, upstream_key, reconciler, transport=upstream_request):
        if (not client_token or len(client_token) < 32 or not upstream_key
                or len(upstream_key) < 16 or reconciler is None):
            raise ValueError("Gateway requires client, inference and reconciliation credentials")
        if len({client_token, upstream_key, reconciler.admin_key}) != 3:
            raise ValueError("Gateway client, virtual and admin credentials must be distinct")
        self.ledger = ledger
        self.client_token = client_token
        self.upstream_key = upstream_key
        self.reconciler = reconciler
        self.transport = transport
        self.ledger.snapshot()
        super().__init__(address, ResearchHandler)

    def event(self, kind, payload):
        with self.ledger.transaction() as connection:
            self.ledger._event(connection, kind, payload)


class ResearchHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        pass

    def respond(self, status, data, content_type="application/json", dispatch_id=None):
        payload = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        if dispatch_id:
            self.send_header("X-Gameworld-Dispatch-ID", dispatch_id)
        self.end_headers()
        self.wfile.write(payload)

    def authorized(self):
        expected = f"Bearer {self.server.client_token}".encode()
        supplied = self.headers.get("Authorization", "").encode()
        if not hmac.compare_digest(expected, supplied):
            self.respond(401, {"error": "Invalid research gateway credential"})
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        if self.path == "/v1/models":
            self.respond(200, {"object": "list", "data": [
                {"id": model, "object": "model", "owned_by": "cua-litellm"} for model in MODELS]})
        else:
            self.respond(404, {"error": "Unknown route"})

    def do_POST(self):
        if not self.authorized():
            return
        if self.path != "/v1/chat/completions":
            self.respond(404, {"error": "Unknown route"})
            return
        try:
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
                raise ValueError("One Content-Length is required; chunked requests are unsupported")
            size = int(lengths[0])
            if not 0 < size <= MAX_BODY:
                raise ValueError("Request body exceeds research gateway limit")
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("Incomplete request body")
            body = validated_request(json.loads(raw))
        except (ValueError, UnicodeError, socket.timeout):
            self.respond(400, {"error": "Invalid or oversized research request"})
            return
        dispatch_id = f"litellm:{uuid4()}"
        try:
            self.server.ledger.reserve(dispatch_id, "litellm_tokens", REQUEST_HOLD, int(time.time()) + 600)
        except BudgetRefused:
            self.respond(429, {"error": "Campaign admission refused"})
            return
        try:
            self.server.event("dispatch_started", {"id": dispatch_id, "model": body["model"],
                                                    "request_sha256": hashlib.sha256(raw).hexdigest()})
            started_at = time.time()
            upstream = self.server.transport(body, self.server.upstream_key, dispatch_id)
            if (not isinstance(upstream, dict) or not isinstance(upstream.get("payload"), bytes)
                    or not isinstance(upstream.get("headers"), dict)):
                raise ValueError("Upstream transport omitted response evidence")
            response = upstream["payload"]
            observation = usage_observation(response, body.get("stream", False))
            self.server.event("usage_observed", {"id": dispatch_id, **observation,
                                                "reconciled": False})
            call_id = upstream["headers"].get("x-litellm-call-id")
            settlement = self.server.reconciler.reconcile(call_id, observation, started_at)
            with self.server.ledger.transaction() as connection:
                self.server.ledger._settle_in_transaction(
                    connection, dispatch_id, settlement["settled_tokens"], settlement["receipt"])
                self.server.ledger._event(connection, "usage_reconciled", {
                    "id": dispatch_id, "call_id": call_id,
                    "response_tokens": observation["total_tokens"],
                    "settled_tokens": settlement["settled_tokens"],
                    "attempted_retries": settlement["attempted_retries"],
                    "failed_attempt_rows": settlement["failed_attempt_rows"],
                    "receipt": settlement["receipt"],
                })
        except Exception:
            self.server.ledger.freeze(f"Ambiguous upstream usage for {dispatch_id}")
            self.server.event("dispatch_unresolved", {"id": dispatch_id})
            self.respond(502, {"error": "Upstream usage unresolved; campaign frozen"}, dispatch_id=dispatch_id)
            return
        content_type = "text/event-stream" if body.get("stream") else "application/json"
        self.respond(200, response, content_type, dispatch_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    reconciler = LiteLLMSpendReconciler(
        os.environ.get("LITELLM_MASTER_KEY", ""),
        os.environ.get("LITELLM_RESEARCH_KEY_ALIAS", ""))
    server = ResearchGateway(
        ("127.0.0.1", args.port), CampaignLedger(args.db),
        os.environ.get("GAMEWORLD_RESEARCH_TOKEN", ""),
        os.environ.get("LITELLM_RESEARCH_KEY", ""), reconciler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
