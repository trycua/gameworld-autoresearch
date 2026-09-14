# Browser-backed research integration and live tests

Date: September 13, 2026 (UTC).
Outcome: browser-only and hybrid Dynamic Workflows run with real per-worker
Playwright MCP tools and verified source observations. Browser search is not a
reliable wholesale replacement for search APIs; use it as a complementary path.

## Implemented

- `/browser-research`: gathering workers use browser tools, without web_search.
- `/hybrid-research`: SearXNG JSON discovery plus browser source inspection.
- `/research-stop`: cooperative cancellation, including browser cleanup.
- CLI: `scripts/pi_research.sh research --mode browser|hybrid --question ...`.
- Luna planning, Terra gathering, Sol verification, Astra reporting through the
  existing Cua LiteLLM aliases. No Qwen inference or Modal training was launched.
- One fresh MCP process/browser profile per gathering worker; no connection to the
  evaluation desktop or personal browser. Explicit subagent tool injection avoids
  the package's parent-extension inheritance limitation.

Pinned dependencies and operational/security limits are documented in
`docs/BROWSER_RESEARCH.md`; implementation lives under `tools/pi/`.

## Search comparison

The no-model comparison reused all 11 queries in
`configs/searxng-research-queries.json` against the running SearXNG service and a
browser Google search path. It used real browser navigation and accessibility
snapshots, not a simulated browser response.

| Measure | Result |
| --- | ---: |
| Fixture queries | 11 |
| SearXNG responses with results | 3/11 |
| Browser Google queries actually attempted | 1 |
| Browser queries blocked by Google | 1 |
| Remaining browser queries skipped after the block | 10 |
| Browser queries with observed source links | 0 |
| Model tokens used by this comparison | 0 |

Google returned HTTP 429 and a reCAPTCHA page. The comparison stopped querying
that browser engine rather than solving or bypassing the challenge. The ten
skipped queries are not ten separately observed failures.

The SearXNG Google engine also encountered CAPTCHA/suspension during this testing
period; its three nonempty responses were academic searches. This is a degradation
from the earlier SearXNG pilot, not a replacement of its recorded results. Different
clients/request shapes and potentially different egress paths prevent attributing
the difference solely to browser-versus-HTTP transport.

Separate single-query browser diagnostics found a DuckDuckGo human challenge and
a Bing page without result links in its initial snapshot. Those were diagnostics,
not a complete comparative benchmark or a sustained availability estimate.

## Successful workflow runs

| Run | Agents | Duration | Reported total tokens | Accepted source observations |
| --- | ---: | ---: | ---: | ---: |
| Browser-only, supplied Modal recipe URL | 4 | 87.234 s | 40,171 | 1 |
| Hybrid, TGRPO paper discovery and inspection | 4 | 136.276 s | 48,715 | 1 |

Both complete with `sources_observed_needs_review`, not a claim that their proposed
training techniques have been validated experimentally.

The browser-only run directly opened the user-provided Modal GRPO TRL page and
returned a short excerpt verified against the observed document. This validates
browser source inspection, **not discovery of an unknown URL**.

The hybrid run initially received an irrelevant academic search result, then a
Semantic Scholar parsing error on its bounded reformulation. It recovered by
browsing arXiv's search interface, inspecting snapshots after an initial navigation
error, and opening the primary HTML paper at `https://arxiv.org/html/2506.08440`.
Its final source excerpt matched the observed page. This demonstrates useful
browser fallback, but a single successful recovery is not a reliability estimate.

The report's connection to Qwen3-VL/GameWorld is explicitly a transfer hypothesis:
no post-training, driver patch or benchmark episode was performed by these workers.

## Failed trials retained

Earlier development runs remain in `results/runs/` and were not silently promoted:

- Initial workflow metadata omitted the required description and failed before
  model calls; the script generator was corrected.
- The first full run exposed a pi SDK integration error: `session.tools: []`
  disabled custom tools as well as coding tools. The runner now explicitly allows
  the browser/search tools and schema tool while excluding coding tools.
- Source validation initially rejected literal excerpts wrapped in JSON quotation
  marks or split across accessible inline nodes. Matching now reconstructs the
  observed accessible text and normalizes quotation wrappers, with regression tests.
- One later paper trial genuinely changed punctuation in a purported verbatim
  excerpt. It was correctly rejected and returned `insufficient_evidence`; the
  check was not weakened to accept the altered quote.

The seven completed development/smoke workflows reported 243,802 total tokens,
including unsuccessful evidence trials. This is the sum of their terminal usage
records, including cache-read usage once, not an enforced campaign ledger. The
metadata-validation failure made no model calls. Search-only diagnostics made no
model calls. No Modal GPU jobs were started.

## Checks and remaining risks

- Eighteen offline pi/browser tests pass, covering command loading, phase execution,
  custom-tool allowlists, separate worker browsers, cancellation, URL restrictions,
  snapshot-path/symlink rejection and source observation checks.
- Live workers called actual browser/search tools; loading extensions alone was
  not treated as proof of integration.
- After the completed trials, no pilot-owned MCP browser processes or temporary
  browser-profile directories remained. SearXNG remains running in `gvisor-dev`.
- A source's observed URL and matching excerpt do not automatically prove every
  associated claim. Verification and human review are still needed.
- No CAPTCHA bypass, IP rotation, login, personal profile or shared GameWorld
  browser was used. Direct-URL checks and isolated profiles are not full network
  confinement; redirected/page-initiated requests need separate egress hardening
  before arbitrary-site unattended use.
- Per-workflow limits and per-process pacing are implemented. Cross-process token
  accounting, campaign-dollar enforcement, OTel export and resumable browser-run
  journals remain separate work.

## Artifacts

- Search comparison: `results/runs/browser-vs-searxng-20260913/`.
- Successful browser-only: `results/runs/browser-only-source-final-20260913/`.
- Successful hybrid: `results/runs/browser-hybrid-verified-20260913/`.
- Earlier trials: `browser-hybrid-smoke-20260913`, `browser-hybrid-smoke-v2-20260913`,
  `browser-hybrid-smoke-v3-20260913`, `browser-hybrid-academic-20260913`,
  `browser-only-source-smoke-20260913`, and `browser-hybrid-academic-final-20260913`
  beneath `results/runs/`.

Each workflow directory contains a manifest, model/tool usage and source events,
and a result or error. Artifacts are gitignored and retain raw third-party page
text; handle them as sensitive research data rather than public release material.
