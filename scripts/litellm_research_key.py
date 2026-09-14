"""Create or verify the dedicated LiteLLM key used by the research relay."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import ssl
from urllib import parse, request

from fps_bench.evaluation_contract import canonical, exclusive_write
from fps_bench.research_gateway import MAX_RESPONSE, MODELS, NoRedirect, UPSTREAM_ROOT


ROOT = Path(__file__).resolve().parents[1]


def api_request(path, admin_key, body=None):
    url = UPSTREAM_ROOT + path
    headers = {"Authorization": f"Bearer {admin_key}", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    outgoing = request.Request(url, data=data, method="POST" if body is not None else "GET", headers=headers)
    opener = request.build_opener(NoRedirect(), request.HTTPSHandler(context=ssl.create_default_context()))
    with opener.open(outgoing, timeout=30) as response:
        payload = response.read(MAX_RESPONSE + 1)
    if len(payload) > MAX_RESPONSE:
        raise ValueError("LiteLLM key-management response is too large")
    return json.loads(payload)


def validate_output(path):
    path = Path(path).expanduser().resolve()
    if path.is_relative_to(ROOT):
        raise ValueError("LiteLLM virtual-key custody must remain outside the repository")
    return path


def same_expiry(left, right):
    try:
        parsed = [datetime.fromisoformat(value.replace("Z", "+00:00")) for value in (left, right)]
    except (AttributeError, TypeError, ValueError):
        return False
    if any(value.tzinfo is None for value in parsed):
        return False
    return int(parsed[0].timestamp() * 1000) == int(parsed[1].timestamp() * 1000)


def create(path, alias, duration, admin_key):
    path = validate_output(path)
    if (not isinstance(alias, str) or not alias.startswith("gameworld-autoresearch-")
            or len(alias) > 128):
        raise ValueError("Dedicated key alias must use the GameWorld autoresearch prefix")
    if not isinstance(duration, str) or not duration.endswith("d") or not duration[:-1].isdigit():
        raise ValueError("Key duration must be an explicit number of days")
    response = api_request("/key/generate", admin_key, {
        "key_alias": alias,
        "duration": duration,
        "models": list(MODELS),
        "max_parallel_requests": 4,
        "metadata": {"consumer": "gameworld-autoresearch", "accounting": "authenticated-spend-logs-v2"},
        "key_type": "llm_api",
    })
    key = response.get("key")
    if (not isinstance(key, str) or len(key) < 16 or response.get("key_alias") != alias
            or sorted(response.get("models") or []) != sorted(MODELS)):
        raise ValueError("LiteLLM returned an incomplete or mismatched virtual key")
    manifest = {
        "schema_version": 1,
        "endpoint": UPSTREAM_ROOT,
        "key_alias": alias,
        "key": key,
        "expires": response.get("expires"),
        "models": list(MODELS),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    exclusive_write(path, canonical(manifest), 0o600)
    return {key: manifest[key] for key in ("endpoint", "key_alias", "expires", "models")}


def verify(path, admin_key):
    path = validate_output(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("LiteLLM key custody file must be regular and mode 0600")
    data = path.read_bytes()
    manifest = json.loads(data)
    if (not isinstance(manifest, dict) or manifest.get("schema_version") != 1
            or manifest.get("endpoint") != UPSTREAM_ROOT
            or not isinstance(manifest.get("key"), str)
            or not isinstance(manifest.get("key_alias"), str) or canonical(manifest) != data):
        raise ValueError("LiteLLM key custody manifest is invalid")
    models = api_request("/v1/models", manifest["key"])
    available = {row.get("id") for row in models.get("data", []) if isinstance(row, dict)}
    query = parse.urlencode({"key_alias": manifest["key_alias"], "return_full_object": "true",
                             "page": 1, "size": 10})
    listing = api_request("/key/list?" + query, admin_key)
    keys = listing.get("keys")
    if (not set(MODELS) <= available or listing.get("total_count") != 1
            or not isinstance(keys, list) or len(keys) != 1):
        raise ValueError("LiteLLM virtual-key lookup is incomplete or ambiguous")
    payload = keys[0]
    key_name = payload.get("key_name")
    if (payload.get("key_alias") != manifest["key_alias"]
            or sorted(payload.get("models") or []) != sorted(MODELS)
            or not same_expiry(payload.get("expires"), manifest.get("expires"))
            or payload.get("blocked") is True or payload.get("max_parallel_requests") != 4
            or not isinstance(key_name, str) or not key_name.endswith(manifest["key"][-4:])):
        raise ValueError("LiteLLM virtual-key identity or policy changed")
    return {"verified": True, "endpoint": manifest["endpoint"],
            "key_alias": manifest["key_alias"], "expires": payload.get("expires")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["create", "verify"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alias")
    parser.add_argument("--duration", default="7d")
    args = parser.parse_args()
    if args.operation == "create":
        if not args.alias:
            parser.error("create requires --alias")
        admin_key = os.environ.get("LITELLM_MASTER_KEY", "")
        if len(admin_key) < 16:
            parser.error("LITELLM_MASTER_KEY is required to create a key")
        result = create(args.output, args.alias, args.duration, admin_key)
    else:
        admin_key = os.environ.get("LITELLM_MASTER_KEY", "")
        if len(admin_key) < 16:
            parser.error("LITELLM_MASTER_KEY is required to verify key policy")
        result = verify(args.output, admin_key)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
