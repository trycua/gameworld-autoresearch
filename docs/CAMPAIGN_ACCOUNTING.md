# Campaign accounting

## Status

The controller-side ledger is implemented and tested. **Campaign enforcement is
not complete:** Pi now routes through a local admission relay, but Modal adapters do not yet
require admission across all paths. Completed-work conservative app-hour reconciliation is now implemented; production-loop reconciliation and a remote admission service remain incomplete. Do not launch an
unattended campaign on the strength of this module alone. Linear: CUA-1167.

`fps_bench/campaign_ledger.py` uses stdlib SQLite with full synchronous commits,
foreign keys, and immediate write transactions. The database belongs on durable
local storage on a single trusted controller host. Concurrent controller processes
on that host share the same database. Do not place it on NFS or copy it per worker.
Agents must never receive database write access or provider-admin credentials.

## Units and limits

- `modal_micro_usd`: integer millionths of USD; total 2,000,000,000 ($2,000),
  normal work 1,800,000,000 ($1,800), shutdown work 200,000,000 ($200).
- `litellm_tokens`: cumulative prompt plus completion tokens, maximum
  1,000,000,000. Cached input counts once; no LiteLLM dollar gate.
- Outstanding holds and settled actual usage both consume allowance.
- Initialization cannot reset an existing campaign or change its limits.
- Reservation IDs are immutable idempotency keys. A repeated reservation returns
  its existing state; **it is not permission to dispatch a second provider job**.
- Expiration does not refund money or tokens. Any expired unresolved hold blocks
  new admission until reconciled. Provider cancellation alone is not reconciliation.
- Settlement requires a unique receipt reference, including zero-cost cancellation.
  The controller must authenticate and validate receipts; the ledger cannot prove
  that a caller-supplied receipt string is genuine.
- Missing usage stays reserved. Actual usage above the reservation is still recorded
  and freezes new admission, rather than silently discarding an overrun.
- Freeze does not prevent reconciliation. There is intentionally no reset/unfreeze
  API. Reserve bounded cleanup capacity before starting work: fresh admission can
  be denied during an incident, and already-incurred charges must still be tracked.

The database audit events and receipts are controller-owned, not a tamper-proof
external audit log. Back up the durable volume and export receipts/artifacts.

## Local API smoke (no provider calls)

```bash
python3 -m fps_bench.campaign_ledger --db /tmp/gameworld-ledger-smoke.sqlite \
  initialize --json '{"campaign":"local-smoke"}'
python3 -m fps_bench.campaign_ledger --db /tmp/gameworld-ledger-smoke.sqlite snapshot
python3 -m unittest discover -s scripts -p campaign_ledger_check.py -v
```

The Python API also exposes `reserve`, `settle`, and `freeze`; CLI argument objects
use those method names and parameter names. Do not use a smoke database as the
production campaign ledger.

## Required integration before CUA-1167 is complete

1. One authenticated controller admission path for every researcher, inference,
   training, storage and cleanup operation. Workers cannot choose `shutdown` to
   bypass the normal allowance. Disable alternative unmetered launch paths.
2. Provider request/job IDs persisted before dispatch, with exactly-once dispatch
   or reconciliation of ambiguous submissions. Separate admission idempotency from
   permission to launch. Process crashes must not cause duplicate paid work.
3. Conservative upper bounds per request/job, server-side duration/resource caps,
   and allowances for cooldown/idle/storage. Observe ongoing charges and reconcile
   with actual provider billing. A retrospective overrun freeze cannot undo spend.
4. Import prior campaign usage (including failed research workflows and existing
   Modal usage), deduplicated against provider records; do not silently reset to zero.
5. Provider freshness and discrepancy checks, independent cleanup watchdog,
   durable backup/recovery, and boundary/failure-injection tests across real adapters.
6. Only after these integrations are verified, update the still-pending enforcement
   statuses in `configs/pi/research-limits.json` and enable paid campaign dispatch.

## Research relay (development only)

`fps_bench/research_gateway.py` exposes authenticated `/v1/models` and
`/v1/chat/completions` on loopback port 8765. Each HTTP inference attempt receives
a fresh durable reservation and dispatch ID before the relay contacts LiteLLM.
Retries by Pi therefore get separate reservations. The relay itself performs no
retry and refuses redirects, alternate upstreams, unknown model aliases, image
inputs, multiple completions and arbitrary metadata. It caps request/response
bytes, output tokens and socket waits. SSE is buffered until its final usage and
DONE marker are observed, then returned unchanged to the Pi client. This increases
time-to-first-token; real end-to-end client timeouts still need live verification.

Successful streamed/nonstreamed usage is an **observation**, not a reconciled
receipt. The original hold remains charged. Timeout, incomplete stream, absent or
inconsistent usage, or an observed overrun freezes further admission; client error
responses and audit events omit upstream exception strings, secrets and prompts.
Disconnects never refund holds. Holds expire after ten minutes, at which point
new admission stops unless a trusted reconciler has settled them.

**The 144,384-token per-request development reservation is not a verified bound
on all cloud backend attempts.** The local cloud config at
`nixos/litellm/config.yaml` contains `num_retries: 2` and alias fallbacks. Response
usage alone cannot prove accounting for every failed or hidden attempt. Live route
configuration, hard retry bounds, provider usage reconciliation and prior campaign
usage must be established before production admission can be enabled. The default
CLI refuses to start; `--development-unreconciled` is an explicit development-only
acknowledgement, not campaign launch approval or cap enforcement certification.

The Pi profile now reads `$GAMEWORLD_RESEARCH_TOKEN` and uses the loopback relay.
The launcher strips the upstream `$LITELLM_API_KEY` rather than loading it from
its key file. The trusted relay separately receives both credentials from its
supervisor environment; it refuses identical upstream and client credentials.
Do not grant researcher containers access to upstream credential files or the
ledger. This loopback service is not yet a remotely deployed authentication or
network-isolation boundary.

Offline checks (no inference spend):

```bash
python3 -m unittest discover -s scripts -p research_gateway_check.py -v
node --test tools/pi/research.test.mjs tools/pi/browser-research.test.mjs
```

The gateway suite drives real local HTTP requests and the installed Pi SDK against
a fake upstream, including admission refusal before any upstream call. This is
SDK compatibility evidence, not real LiteLLM billing validation.

The controller now shares atomic admission/settlement transactions with this
ledger; see `docs/CAMPAIGN_CONTROLLER.md`. This does not yet unify job-envelope
research reservations with the relay's per-request holds or add provider billing
reconciliation. Both remain launch blockers.


## Historical Modal import (real provider evidence)

The canonical campaign ledger now includes prior GameWorld app-hour charges.
See `docs/results/2026-09-13-modal-history.md` for scope, ledger path and exact
provider evidence. `scripts/modal_billing_import.py` authenticates directly to
Modal, verifies workspace identity, captures only explicitly scoped app IDs, and
writes evidence before importing. It does not accept a researcher-supplied billing
file as authoritative. The lower-level API still trusts its controller caller.

`CampaignLedger.record_prior_usage` stores the maximum observed cost for each
stable external identity, counts it against normal allowance, and freezes on
exceeded limits. It permits late revisions even when frozen. Historical rows do
not settle or release job reservations. Never use this API for work already
accounted for by the job ledger; that requires provider/job reconciliation.

Initial historical scope is immutable and must be registered before the first
Modal reservation. Imports may be partially applied if interrupted; replay is
idempotent. An importer completion is not a provider completeness certificate.
Admission still needs a freshness/completeness gate, imported LiteLLM history,
reserved bounds for unreported usage, storage/idle allowances and a watchdog.

Validation: `python3 -m scripts.modal_billing_check`.

## Completed-work conservative reconciliation

`docs/MODAL_RECONCILIATION.md` documents atomic grouped reconciliation that retains
the full original allocation without claiming final billed cost or issuing refunds.
`reconciled_retained` allocations continue consuming the cap but no longer act as
expired active holds after authenticated provider closure. Group/row overlap and
refund attempts are rejected; upward revisions are retained and overruns freeze
admission. Controller telemetry includes both observed costs and retained headroom.
