# Browser-backed Dynamic Workflows

GameWorld research now has two custom pi commands built on the installed
pi-dynamic-workflows runtime. Each gathering worker receives its own Playwright
MCP subprocess and fresh headless browser profile. Neither mode connects to the
GameWorld browser, Fleet desktop, personal browser or a shared CDP endpoint.

## Commands

The Pi profile now requires the controller-local metered research relay and
`GAMEWORLD_RESEARCH_TOKEN`. Direct upstream credentials are removed from the
launcher environment. The trusted relay uses a dedicated virtual key and settles
authenticated spend-log usage, including conservative hidden-retry bounds, before
replying. Live deployment evidence remains pending; see `docs/CAMPAIGN_ACCOUNTING.md`.

Install the pinned dependencies and generate the isolated pi profile:

```bash
npm ci --prefix tools/pi --ignore-scripts
node tools/pi/setup.mjs
scripts/pi_research.sh
```

In pi:

```text
/hybrid-research Find primary research on multimodal multi-turn GRPO for Qwen-VL, and propose a small GameWorld experiment.
/browser-research Inspect https://modal.com/docs/examples/grpo_trl and identify the changes needed for screenshot-based multi-turn rollouts.
/research-stop
```

Or run headlessly with a bounded one-angle pilot:

```bash
scripts/pi_research.sh research --mode hybrid --angles 1 \
  --question 'Use academic search to find primary papers on trajectory-wise GRPO for vision-language-action models.' \
  --output results/runs/my-browser-research
```

The output directory must be new. Omit `--output` to generate a run directory.
`PLAYWRIGHT_EXECUTABLE_PATH` can override `/usr/bin/chromium`; Chromium must be
installed separately. The smoke tests used the existing system Chromium. Package
versions are locked: Playwright MCP 0.0.80, MCP SDK 1.30.0, pi 0.85.1 and Dynamic
Workflows 3.11.0.

The original `/deep-research` command is preserved and still has its upstream
Bing/web-fetch implementation. The new commands use the Dynamic Workflows engine
directly; they have their own phase indicator and `/research-stop`, not the built-in
`/workflows` navigator or its pause/resume journal. An interrupted new command leaves
artifacts but is not automatically resumed.

## Tool delivery and model roles

Planning uses Luna, gathering Terra, verification Sol and reporting Astra via
`cua-litellm`. The research config pins those role aliases, not their underlying
provider deployments; server-side fallbacks still apply.

The custom agent runner explicitly injects browser tools into gathering sessions.
It does not rely on parent MCP extensions being inherited. Non-gathering workers
receive no browser or coding tools. The pi SDK's active-tool allowlist must include
custom tool names and `structured_output` when a schema is requested; an empty list
would disable them, not just remove built-in coding tools.

- Browser mode: navigate, snapshot, click, type, key press, tabs, back and close.
- Hybrid mode: those tools plus a SearXNG JSON `web_search` adapter.
- Not exposed: bash, read/write/edit, JavaScript evaluation, Playwright run-code,
  uploads, browser installation, Fleet administration or training operations.

SearXNG runs privately at
`http://gameworld-searxng.gvisor-dev.svc.cluster.local:8080`. General searches use
Google and academic searches use Semantic Scholar. Responses distinguish results,
partial failures, empty results and failures; engine errors are retained. A shared
queue spaces search calls by five seconds within one pi/CLI process. This is not a
global cross-process rate limiter or a guarantee against upstream blocking.

## Isolation, source checks and bounds

The MCP child receives a small environment without LiteLLM, Modal, Fleet or Qwen
credentials. Its HOME, caches, output and workspace root are under a fresh temporary
directory. Workers have separate MCP/browser instances; temporary browser state is
removed on normal completion, failure or cooperative cancellation.

Direct navigation rejects file URLs, HTTP, explicit IPs, local hostnames, embedded
credentials and custom ports. Arbitrary file output, evaluate/run-code and upload
tools are omitted. CAPTCHA/403/429 detection disables interaction with the blocked
page and repeat navigation to that host within that worker; it does not solve or
bypass challenges. Known primary URLs can still be visited.

These checks are **not a complete network or hostile-page security boundary**:
redirects, DNS rebinding and page-initiated requests are not fully fenced by these
URL checks. The browser runs in this gVisor workspace, but separate profiles alone
do not implement egress isolation. Unattended operation on arbitrary sites should
use dedicated browser-worker network policy/proxy enforcement. Do not supply
personal profiles, accounts or infrastructure credentials to these workers.

Playwright MCP can return snapshot artifact links instead of inline text. The
bridge reads only generated snapshot files within that worker's output directory,
rejecting traversal/symlink escapes and snapshots larger than 4MiB. Tool text is
capped at 24,000 characters; untruncated observations are kept in local artifacts.

The source gate requires an actually observed final URL and an exact short excerpt
found in the observed page. Accessible text nodes are joined for matching; JSON or
smart quotation wrappers are normalized. Altered/paraphrased excerpts are rejected.
This establishes retrieval provenance, **not the truth or entailment of every claim**.
The verifier and human review remain necessary. No accepted source produces an
explicit `insufficient_evidence` research status, not a successful evidence claim.

Defaults in `configs/pi/browser-research.json`:

- Two gathering workers at most; four-to-five total agents per workflow.
- 24 browser calls and three search calls per gathering worker.
- Three minutes per worker, ten minutes per workflow, zero automatic agent retries.
- 100,000 tokens per workflow; the local gateway separately reserves requests
  against the 1-billion-token campaign ledger. It does not meter Modal dollars.

## Artifacts and tests

Each run writes `manifest.json`, `events.jsonl`, and `result.json` or `error.json`
under `results/runs/`. Events include source URLs, browser text, provider token
usage, model-role selection and browser cleanup. Treat raw artifacts as sensitive;
they are gitignored. Integrated proposal/patch attempts emit aggregate OTel
success, failure and duration metrics, but raw browser events remain local.

```bash
node --test tools/pi/browser-research.test.mjs tools/pi/research.test.mjs
node tools/pi/browser-search-benchmark.mjs \
  --output results/runs/browser-search-comparison-new
```

The first command is offline. The second makes real web requests but no model
calls. It compares the existing research-query fixture against SearXNG and browser
Google, stopping browser search after an upstream block rather than repeatedly
probing a challenge. Different request/egress paths mean this is an operational
comparison, not a controlled ranking-quality experiment.

See `docs/results/2026-09-13-browser-research.md` for the live results, including
failed trials. Browser interaction helps verify pages; it is not a reliable
substitute for every search provider.
