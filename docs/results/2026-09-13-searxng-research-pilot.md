# SearXNG research-query pilot on gVisor

Date: September 13, 2026 (UTC).
Verdict: viable for a bounded research pilot with explicit empty/error handling;
not proven reliable enough to be the sole unattended research search provider.

## Deployment

- Namespace: `gvisor-dev`; Deployment/Service: `gameworld-searxng`.
- Runtime: `gvisor`; one healthy non-root replica, no public ingress.
- Image: `docker.io/searxng/searxng@sha256:d0a4ca04e68c6d57fe45509ad5a6b10c890350724762ade3abea5363571aa29a`.
- SearXNG version: `2026.9.13-230c3632d`.
- Upstream source revision: `230c3632d927599c4a8f6bf109bc094f95598181`.
- Endpoint inside the namespace: `http://gameworld-searxng.gvisor-dev.svc.cluster.local:8080`.
- Manifests and lifecycle instructions: `infra/searxng/`.

The initial local Docker experiment was stopped when the user requested Kubernetes.
A dedicated test namespace could be created but workload RBAC denied deployment;
that empty namespace was deleted. The user selected the authorized `gvisor-dev`
namespace. Admission required `runtimeClassName: gvisor`; the corrected deployment
rolled out successfully. kubectl port-forward failed on host-netns loopback, but
ClusterIP access and pod-local health checks worked.

## Protocol

The probe uses the SearXNG JSON API directly, with no model inference. Eleven
queries cover two supplied Modal recipes, the Qwen model card, the vLLM recipe,
the GameWorld paper, Qwen fine-tuning, visual-agent RL, native X11 input and three
academic searches. Five queries have predeclared exact target URLs. Each request
retains its full response, top ten titles/URLs, engine errors and latency.

First pass: one repetition, general engines Google/Bing/Brave/DuckDuckGo, academic
engines arXiv/Semantic Scholar/Google Scholar, two seconds between requests.
Second pass: Google for general queries and Semantic Scholar for academic queries,
two repetitions with five seconds between requests. No CAPTCHA solving, IP rotation
or bypass was attempted. Failing engines were removed instead of force-retried.

| Measure | Initial engine set | Filtered engine set |
| --- | ---: | ---: |
| Requests | 11 | 22 |
| Successful JSON responses | 11/11 | 22/22 |
| Nonempty results | 11/11 | 21/22 |
| Exact known-source URL hits in top 10 | 4/5 | 8/10 |
| Median request latency | 0.651 s | 0.271 s |
| Nearest-rank p95 latency | 10.013 s | 0.964 s |
| Reported engine-error entries | 10 | 0 |

The filtered 8/10 known-source count is four of five unique sources found on both
repetitions, not ten independent source-discovery trials. The strict vLLM target
was the `/en/latest/` recipe URL; the first pass returned its `/en/stable/` page and
the filtered pass returned the upstream Qwen3-VL recipe source on GitHub. We retain
the exact-match failure rather than changing the expected URL after observing it.

One repeated visual-RL discovery query returned zero results without an engine
error. Therefore an empty response must not be interpreted as absence of literature.
These small sequential samples from one cluster egress do not establish sustained
throughput, independence between repeats or long-term block/rate-limit behavior.
The two passes also differ in pacing and engine selection, so latency differences
are descriptive rather than a controlled attribution to any one engine.

## Engine and relevance findings

- Google found the two Modal recipes, exact Qwen model card and GameWorld paper.
  It also surfaced upstream fine-tuning code, a Hugging Face VLM fine-tuning guide
  and GUI-agent research sources. Some results concerned newer Qwen variants rather
  than Qwen3-VL; version relevance still needs researcher review.
- Brave contributed useful results initially, then returned a rate-limit error
  after a small number of queries and was suspended by SearXNG.
- DuckDuckGo initially raised a parser IndexError and a CAPTCHA error, though some
  later queries returned relevant results. It was not consistently reliable.
- Bing returned unrelated Gmail/Play Store pages for the exact Modal queries and
  broad dictionary-style results for technical searches, polluting merged rankings.
- arXiv's search engine timed out and Google Scholar returned HTTP 403. Their
  subsequent suspended-engine statuses were retained rather than hidden.
- Semantic Scholar returned results without reported engine errors. The multimodal
  and GRPO queries surfaced potentially useful papers including OpenWebRL,
  EvoCUA-1.5 and trajectory-wise GRPO. The generic GUI-agent query instead surfaced
  manufacturing/vehicular multi-agent RL: a nonempty response is not a relevance
  guarantee, and source/paper applicability has not been established by this test.

A separate workspace-side source-fetch check obtained HTTP 200 for six of seven
selected pages: both Modal recipes, Qwen model card, stable vLLM recipe, GameWorld
HTML and EvoCUA-1.5 HTML. OpenWebRL HTML reset the connection. Fetches read at most
2MiB each; HTTP availability is not full-text extraction or source verification.

## Current state and recommendation

The deployed default engine set is **Google plus Semantic Scholar**. One replica
is left running for follow-up testing. A post-probe resource snapshot was 2m CPU
and 143Mi memory; this is a point-in-time observation, not a capacity estimate.
No pi tool has been switched to this endpoint yet, and no paid search API or model
was used for the probe.

Recommended next integration: replace the package's Bing-only HTML scraper with a
SearXNG JSON adapter, return provider errors/empty responses explicitly, preserve
source URLs and query provenance, and add a bounded retry or query-reformulation
path with backoff. Cache/deduplicate requests subject to upstream terms. Retain a
separate fallback for prolonged upstream failures; do not treat a self-hosted
metasearch frontend as an independent search index or an uptime guarantee.

Before scaling: test actual pi subagent tool injection, source extraction including
PDFs, longer-duration query diversity, budgeted rate limits and cancellation. The
current pod is private and limiter-disabled; public exposure requires separate
access control and abuse protection.

## Artifacts and checks

- Initial run: `results/runs/searxng-20260913-all-engines/`.
- Filtered repeats: `results/runs/searxng-20260913-filtered/`.
- Source retrieval: initial run's `source-fetches.json`.
- Each run includes manifests, response JSON, `requests.jsonl`, `summary.json`,
  settings and Kubernetes deployment/pod snapshots. Raw artifacts are gitignored.
- Query fixture: `configs/searxng-research-queries.json`.
- Probe: `scripts/searxng_research_check.py`.
- Four offline metric/URL-matching checks pass via
  `python3 scripts/searxng_research_unit_check.py`.
- Kubernetes server-side dry-run accepts the final manifests.

Upstream setup references consulted:
https://docs.searxng.org/admin/installation-docker.html and the pinned source's
`container/entrypoint.sh`, `container/dist.dockerfile` and `searx/settings.yml`.
