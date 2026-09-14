"""Probe research search quality and engine failures without model inference."""

import argparse
import hashlib
import json
import math
import re
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def expected_match(url, expected):
    actual = urlparse(url)
    target = urlparse(expected)
    if actual.hostname != target.hostname:
        return False
    actual_path = actual.path.rstrip("/")
    target_path = target.path.rstrip("/")
    if actual_path == target_path:
        return True
    return actual.hostname == "arxiv.org" and actual_path.startswith(target_path) and bool(
        re.fullmatch(r"v[0-9]+(?:\.pdf)?", actual_path[len(target_path):])
    )


def summarize(rows):
    durations = sorted(row["seconds"] for row in rows)
    known = [row for row in rows if row["kind"] == "known-source"]
    engine_errors = Counter()
    for row in rows:
        for engine, error, *_ in row.get("unresponsive_engines", []):
            engine_errors[f"{engine}: {error}"] += 1
    return {
        "requests": len(rows),
        "successful_json_responses": sum(row["ok"] for row in rows),
        "nonempty_responses": sum(row["result_count"] > 0 for row in rows),
        "known_source_hits_at_10": sum(row.get("expected_hit_at_10", False) for row in known),
        "known_source_requests": len(known),
        "median_seconds": statistics.median(durations),
        "p95_seconds_nearest_rank": durations[math.ceil(len(durations) * 0.95) - 1],
        "engine_errors": dict(engine_errors),
        "note": "Known-source recall is a diagnostic, not a relevance score for discovery queries.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://gameworld-searxng.gvisor-dev.svc.cluster.local:8080")
    parser.add_argument("--queries", type=Path, default=ROOT / "configs/searxng-research-queries.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engines", default="google")
    parser.add_argument("--academic-engines", default="semantic scholar")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--pause", type=float, default=2.0)
    args = parser.parse_args()
    if args.repeat < 1 or args.pause < 0:
        parser.error("repeat must be positive and pause nonnegative")
    queries = json.loads(args.queries.read_text())
    if not queries:
        parser.error("query set must not be empty")
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "base_url": args.base_url,
        "engines": args.engines,
        "repeat": args.repeat,
        "academic_engines": args.academic_engines,
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "queries_sha256": hashlib.sha256(args.queries.read_bytes()).hexdigest(),
        "settings_sha256": hashlib.sha256((ROOT / "infra/searxng/settings.yml").read_bytes()).hexdigest(),
        "queries": queries,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    rows = []
    for repetition in range(args.repeat):
        for query in queries:
            engines = query.get("engines", args.engines)
            if query["kind"] == "academic" and args.academic_engines:
                engines = args.academic_engines
            params = {"q": query["query"], "format": "json", "language": "en", "engines": engines}
            request = Request(args.base_url.rstrip("/") + "/search?" + urlencode(params), headers={"Accept": "application/json"})
            started = time.monotonic()
            row = {"id": query["id"], "kind": query["kind"], "repetition": repetition, "engines": params["engines"], "ok": False, "result_count": 0}
            try:
                with urlopen(request, timeout=30) as response:
                    payload = response.read(4 * 1024 * 1024 + 1)
                    if len(payload) > 4 * 1024 * 1024:
                        raise ValueError("response exceeds 4 MiB")
                    data = json.loads(payload)
                if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                    raise ValueError("response does not contain a results array")
                (args.output / f"{repetition}-{query['id']}.json").write_text(json.dumps(data, indent=2) + "\n")
                top = data["results"][:10]
                row.update({
                    "ok": True,
                    "result_count": len(data["results"]),
                    "unresponsive_engines": data.get("unresponsive_engines", []),
                    "top10": [{"title": result.get("title"), "url": result.get("url", ""), "engines": result.get("engines", [])} for result in top],
                    "top10_unique_domains": len({urlparse(result.get("url", "")).hostname for result in top}),
                })
                if query.get("expected_urls"):
                    row["expected_hit_at_10"] = any(expected_match(result.get("url", ""), expected) for result in top for expected in query["expected_urls"])
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
                row["error"] = str(error)
            row["seconds"] = round(time.monotonic() - started, 3)
            rows.append(row)
            with (args.output / "requests.jsonl").open("a") as output:
                output.write(json.dumps(row) + "\n")
            print(f"{repetition}/{query['id']}: {row['result_count']} results, {row['seconds']}s, expected={row.get('expected_hit_at_10', 'n/a')}, errors={row.get('unresponsive_engines', row.get('error', []))}", flush=True)
            time.sleep(args.pause)
    summary = summarize(rows)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
