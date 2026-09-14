# Campaign accounting

## Status

The controller-side ledger is implemented and tested. **Campaign enforcement is
not complete:** Pi routes through a local admission relay, and the GameWorld Modal
runner admits, cleans and conservatively reconciles training/serving resources.
Other provider paths, remote admission and live
campaign evidence remain incomplete. Do not launch an unattended campaign on the
strength of this module alone. Linear: CUA-1167.

`fps_bench/campaign_ledger.py` uses stdlib SQLite with full synchronous commits,
foreign keys, and immediate write transactions. The database belongs on durable
local storage on a single trusted controller host. Concurrent controller processes
on that host share the same database. Do not place it on NFS or copy it per worker.
Agents must never receive database write access or provider-admin credentials.

## Units and limits

- `modal_micro_usd`: integer millionths of USD; total 2,000,000,000 ($2,000),
  normal work 1,800,000,000 ($1,800), shutdown work 200,000,000 ($200).
- LiteLLM has no campaign token budget or reservations. Existing LiteLLM telemetry
  is monitored by the user; historical token records remain auditable.
- Outstanding holds and settled actual usage both consume allowance.
- Initialization cannot reset an existing campaign or change its limits.
- Reservation IDs are immutable idempotency keys. A repeated reservation returns
  its existing state; **it is not permission to dispatch a second provider job**.
- Expiration does not refund Modal money. Any expired unresolved hold blocks
  new admission until reconciled. Provider cancellation alone is not reconciliation.
- Settlement requires a unique receipt reference, including zero-cost cancellation.
  The controller must authenticate and validate receipts; the ledger cannot prove
  that a caller-supplied receipt string is genuine.
- Missing usage stays reserved. Actual usage above the reservation is still recorded
  and freezes new admission, rather than silently discarding an overrun.
- Freeze does not prevent reconciliation. There is intentionally no reset/unfreeze
  API for Modal incidents. The explicit token-policy migration only retires legacy
  token holds and clears their token-only freeze. Reserve bounded cleanup capacity before starting work: fresh admission can
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
6. Update each enforcement status only when its implementation and live evidence
   support the narrower claim; do not infer readiness for unrelated providers.

## Research relay

`fps_bench/research_gateway.py` exposes authenticated `/v1/models` and
`/v1/chat/completions` on loopback port 8765. Requests receive durable dispatch
IDs but no token reservations. Usage records are optional observations, not a
condition for forwarding responses. The user monitors existing LiteLLM telemetry.
Transport failures return errors without creating holds or freezing admission.
The relay still respects campaign stops/deadlines and unrelated budget freezes.
It rejects alternate upstreams, unapproved models, researcher metadata and
oversized requests, and retains request/output/time limits.

The relay needs only `GAMEWORLD_RESEARCH_TOKEN` and `LITELLM_RESEARCH_KEY`.
It no longer needs `LITELLM_MASTER_KEY` or authenticated spend-log access.
Researchers still receive only the local bearer credential. Legacy spend-log
verification helpers remain for historical audit, not live token enforcement.

Existing ledgers require the explicit user-authorized migration:

```bash
python -m scripts.remove_token_budget --database /durable/campaign.sqlite \
  --output /durable/token-policy-removal --authorize-removal
```

The migration writes a SQLite backup and before/after receipts, retires token
holds without fabricating measured usage, and preserves all Modal limits,
reservations, billing groups and prior usage. Retired amounts are reported
separately from currently reserved tokens. Only a matching token-uncertainty
freeze can be cleared; a Modal freeze is preserved. Protocol forks carry the
removed-token-policy marker forward. New GameWorld coordinators disable token
budgeting during initialization; legacy generic ledger limits are audit-only
for those campaigns and cannot accept new token reservations.

Offline checks (no inference spend):

```bash
python -m unittest scripts.campaign_ledger_check scripts.research_gateway_check
node --test tools/pi/research.test.mjs tools/pi/browser-research.test.mjs
```

The controller now shares atomic admission/settlement transactions with this
ledger; see `docs/CAMPAIGN_CONTROLLER.md`. Research proposals declare bounds, while
actual LiteLLM requests reserve independently through the relay. Authenticated
upstream token settlement and retry attribution are implemented; deployment and
continuous campaign evidence remain launch gates. The successful dedicated-key
probe is recorded in `docs/results/2026-09-14-litellm-reconciliation.md`.


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

## Protocol-boundary fork

`scripts/campaign_protocol_fork.py` creates a fresh campaign database when a
new frozen controller contract replaces an initialized protocol. It refuses any
active job, held reservation, unresolved image import, unknown table, existing
destination or reused campaign ID. The SQLite backup preserves reservations,
prior usage, reconciliation groups and their receipts exactly, drops only
controller/worker protocol state, appends a fork event and emits hashes for the
source accounting snapshot and destination database. This is not a refund or a
prior-usage reclassification; the full existing commitment carries forward.

The September 14 v2 fork preserves `$206.013141` from
`gameworld-joint-20260913` in `gameworld-joint-20260914-v2`. Its private receipt
is `/home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/campaign-v2-fork.json`.
The source database remains unchanged and is no longer used for new admission.

## Completed-work conservative reconciliation

`docs/MODAL_RECONCILIATION.md` documents atomic grouped reconciliation that retains
the full original allocation without claiming final billed cost or issuing refunds.
`reconciled_retained` allocations continue consuming the cap but no longer act as
expired active holds after authenticated provider closure. Group/row overlap and
refund attempts are rejected; upward revisions are retained and overruns freeze
admission. Controller telemetry includes both observed costs and retained headroom.

`scripts/modal_reconcile_deployment.py` applies the same no-refund policy to one
stopped deployed app. It binds authenticated lifecycle and zero-task observations
to the canonical launch manifest's app, function, image and source identities,
saves a consistent private ledger backup, and records scoped app-hour billing rows.
