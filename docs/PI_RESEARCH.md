# Pi research through the Cua LiteLLM gateway

This profile is separate from the legacy L-platform pi launcher and from the
user's global pi agent profile. It does not launch Modal jobs or a research campaign.

## Setup and launch

The profile targets the controller-local authenticated relay at
`http://127.0.0.1:8765/v1`, not LiteLLM directly. The relay requires a dedicated
upstream virtual key and a distinct local client credential, not an admin key.
Usage is monitored through existing LiteLLM telemetry; there is no token budget
or reservation. See `docs/CAMPAIGN_ACCOUNTING.md`.
The commands below require a separately started relay and its client credential.

```bash
npm ci --prefix tools/pi --ignore-scripts
node tools/pi/setup.mjs
scripts/pi_research.sh
```

Pinned versions: `@earendil-works/pi-coding-agent@0.85.1` and
`@quintinshaw/pi-dynamic-workflows@3.11.0`, with the full dependency lockfile in
`tools/pi/package-lock.json`. Node 22 or newer is required.

The setup writes ignored `.pi-local/agent/` and a project-specific directory under
`~/.pi/workflows/projects/`. Existing differing generated files are not overwritten:
review and reconcile them explicitly before running setup again. Global pi settings
and unrelated project workflow configurations are left untouched. Workflow histories
are stored outside the repo; treat them as potentially sensitive research artifacts.

Authentication to the local relay uses `GAMEWORLD_RESEARCH_TOKEN`. The launcher
requires this credential and removes `LITELLM_API_KEY`, the LiteLLM master key and
known Fleet/Qwen/Modal credentials before starting pi. Only the trusted relay owns
the upstream scoped LiteLLM key. It no longer reads the upstream key file or falls
back to direct LiteLLM access. This is not isolation from the host filesystem;
untrusted researchers still need a separate OS/network boundary.

A four-model-scoped virtual key was created for this setup. It expires on
2026-09-21 at 11:44:24 UTC; renew it before later use. The launcher does not mint
keys and never falls back to the master key. No LiteLLM dollar budget was added.

## Browser-backed research

The custom `/hybrid-research` and `/browser-research` commands explicitly supply
Playwright MCP tools to each gathering worker. Hybrid mode also supplies a SearXNG
JSON search tool. The upstream `/deep-research` remains unchanged. See
`docs/BROWSER_RESEARCH.md` for commands, boundaries, test results and limitations.

## Models and research

The provider remains `cua-litellm`; its local relay forwards to the cloud gateway's public HTTPS frontend.
Select any model with `/model` or the CLI:

```bash
scripts/pi_research.sh --model cua-litellm/astra
scripts/pi_research.sh --model cua-litellm/gpt-5.6-sol
scripts/pi_research.sh --model cua-litellm/gpt-5.6-terra
scripts/pi_research.sh --model cua-litellm/gpt-5.6-luna
```

Sol is the supervisor default. Built-in `/deep-research` worker routing is:

| Role | Model |
| --- | --- |
| Plan search queries | Luna |
| Gather web sources | Terra |
| Cross-check claims | Sol |
| Write synthesis | Astra |

This routing uses the package's documented pre-spawn hook. Explicit model, tier
or phase selections take precedence; other untagged work retains upstream defaults.
Tier mapping: small=Luna, medium=Terra, big=Sol, astra=Astra. Live gateway metadata
on September 13 identifies the primary backends as GPT-6 Astra and GPT-5.6
Sol/Terra/Luna. Server fallback routing still applies; aliases are not backend pins.
128K context/16K output in this profile are conservative local settings, not claims
about every backend's maximum capacity. No invented token prices are configured.

In interactive pi, start with:

```text
/deep-research Compare multimodal multi-turn GRPO and SFT/LoRA for screenshot-only Qwen3-VL-2B GameWorld gameplay. Start with https://modal.com/docs/examples/grpo_trl and https://modal.com/docs/examples/grpo_verl, research other primary sources, and propose small falsifiable experiments with pinned dependencies.
```

The package injects its real `web_search` and `web_fetch` tools into built-in deep
research. Search is best-effort Bing HTML parsing, not a guaranteed search API.
Fetch returns truncated HTML/text; it does not extract PDFs. Check tool results,
report coverage gaps and use primary HTML pages when PDF extraction is unavailable.
Do not shadow the built-in command with a saved workflow: saved commands do not
necessarily receive the same web toolset. Research instructions are installed as
profile context so subagents receive the GameWorld scope and citation requirements.

Defaults: two concurrent agents, no automatic retries, ten-minute worker timeout,
200,000 tokens per workflow, and no automatic keyword triggering. These are
operational defaults, not unchangeable global quotas. `/workflows` shows progress;
`/workflows stop <id>` cancels a run. Workers are not OS-sandboxed by this package.

The local `workflows.mjs` entry loads the package's compiled ESM extension. Its
published TypeScript entry hits a pi 0.85.1 loader alias error for `pi-ai/utils/uuid`
in this environment. The wrapper avoids that error without modifying installed
packages; an integration test verifies command registration and context loading.

## Separate campaign limits

`configs/pi/research-limits.json` records the approved limits:

- **LiteLLM: no token or dollar budget.** The user monitors existing LiteLLM telemetry.
- **Modal: USD 2,000**, with USD 1,800 for normal admission and USD 200 reserved for
  shutdown/delayed charges, focused on training and inference plus associated costs.

Neither the relay nor Pi reserves tokens or blocks on missing usage records.
Request-size, output-size, time, model-allowlist and concurrency controls remain.
Transport failures remain visible errors but do not freeze the campaign budget.
Historical token receipts remain audit evidence, not active budget requirements.
Modal training/serving reservations, provider reconciliation and shutdown checks
remain enforced before an unattended campaign launch.

## Campaign integration

`fps_bench.gameworld_research_worker` connects this profile to the durable
GameWorld coordinator. When `fps_bench.gameworld_runner` is started with
`--enable-research`, an idle campaign runs bounded browser-backed research, asks
Astra for one structured proposal, validates it against the frozen baseline and
registers its immutable bytes. Driver proposals then use Sol to produce only an
ASCII unified diff over the approved source files; the Fleet worker still performs
`git apply --check`, rebuilds the bundled driver and runs every input contract.

Before proposal synthesis or patch generation starts, the trusted worker
authenticates to the loopback relay, refuses redirects, and requires the exact four
pinned model aliases. A relay outage therefore stops the runner without consuming
one of the campaign's durable research-failure attempts.

The subprocess receives `GAMEWORLD_RESEARCH_TOKEN` and an optional
`GAMEWORLD_SEARXNG_URL`, but not Fleet, Modal, Qwen or GitHub credentials. Each
proposal and patch attempt has a durable context, output hash and terminal state
in the canonical ledger. Three consecutive research-worker failures stop and
freeze the campaign. SFT proposals are exposed only when the trusted runner is
given an authenticated source catalog; otherwise model research is constrained to
GRPO.

## Validation

```bash
node tools/pi/setup.mjs
node --test tools/pi/research.test.mjs tools/pi/browser-research.test.mjs \
  tools/pi/gameworld-proposal.test.mjs
.venv/bin/python scripts/gameworld_research_worker_check.py
scripts/pi_research.sh --list-models cua-litellm
```

The first two commands make no model inference calls. Listing models checks local
registration/auth presence, not inference availability. Before the metered-relay migration on September 13, all four aliases returned `READY` through pi in bounded live
smokes; the gateway reported its `*-backup-2` routes. A separate full-profile Luna
smoke also returned `READY`. Twenty-two offline Node checks now cover the profile,
browser workflow and structured GameWorld proposal bridge.
The package's direct recipe fetch returned HTTP 200, but its Bing search smoke
parsed zero results despite HTTP 200. Search reliability remains a known limitation;
no complete deep-research workflow or training campaign was run.

## Sources

- https://pi.dev/packages/@quintinshaw/pi-dynamic-workflows?name=deep+research
- https://github.com/QuintinShaw/pi-dynamic-workflows
- https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md
- https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/settings.md
- Cloud source: `trycua/cloud/nixos/litellm/config.yaml` and the live gateway's
  `/v1/models`, `/model/info` and `/openapi.json` (checked September 13, 2026).
