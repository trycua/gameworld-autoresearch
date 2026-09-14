"""Local research relay with durable admission; billing reconciliation is separate."""

import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import ssl
import time
from urllib import request
from uuid import uuid4

from fps_bench.campaign_ledger import BudgetRefused, CampaignLedger


MODELS = ("astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
UPSTREAM = "https://litellm-public.tail204509.ts.net/v1/chat/completions"
MAX_BODY = 65_536
MAX_RESPONSE = 8 * 1024 * 1024
REQUEST_HOLD = 144_384
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
        return payload


class ResearchGateway(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, ledger, client_token, upstream_key, transport=upstream_request):
        if not client_token or len(client_token) < 32 or not upstream_key:
            raise ValueError("Gateway requires separate client and upstream credentials")
        if client_token == upstream_key:
            raise ValueError("Client credential must not be the upstream credential")
        self.ledger = ledger
        self.client_token = client_token
        self.upstream_key = upstream_key
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
            response = self.server.transport(body, self.server.upstream_key, dispatch_id)
            observation = usage_observation(response, body.get("stream", False))
            self.server.event("usage_observed", {"id": dispatch_id, **observation,
                                                "reconciled": False})
            if observation["total_tokens"] > REQUEST_HOLD:
                raise ValueError("Observed usage exceeds hold")
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
    parser.add_argument("--development-unreconciled", action="store_true",
                        help="Explicitly acknowledge missing upstream retry/billing reconciliation")
    args = parser.parse_args()
    if not args.development_unreconciled:
        parser.error("Production admission is disabled until upstream retry bounds and billing reconciliation are verified")
    server = ResearchGateway(("127.0.0.1", args.port), CampaignLedger(args.db),
                             os.environ.get("GAMEWORLD_RESEARCH_TOKEN", ""),
                             os.environ.get("LITELLM_API_KEY", ""))
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
