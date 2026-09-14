# GameWorld campaign coordinator

## Status

`fps_bench/campaign_controller.py` implements durable controller state, while
`fps_bench/gameworld_coordinator.py` persists the GameWorld driver, GRPO, serving,
paired-development, qualified-factorial and protected-split workflow queues. Fleet
source-patch, rollout/evaluation, Modal training and adapter-serving adapters exist
and validate immutable results. The remaining production gap is current image and
contract publication plus bounded live provider evidence.

Do not substitute the synthetic rehearsal for the live launch rehearsal. Linear:
CUA-1172, with budget integration in CUA-1167 and the final rehearsal in CUA-1176.

## Single authority and transactions

The controller uses the campaign ledger's SQLite database on one trusted durable
host. Ledger reservations and job insertion commit in **one immediate transaction**;
a crash cannot leave one committed without the other. Cleanup confirmation and all
resource settlements are also atomic. Controller identity, contract hash, campaign
deadline, immutable candidate manifests, jobs and decision inputs are persisted.
Initialization cannot reset the campaign deadline or change its contract/duration.

Limits: six hours maximum, ten materialized non-baseline candidates, two shared
Fleet desktop slots for evaluation/build work, one training slot and two research
slots. Slots remain occupied through ambiguous submission and pending cleanup.
These are controller admission limits; provider-side limits/TTL and an independent
watchdog still need enforcement. Failed/unmaterialized research proposals also need
a proposal-attempt limit when the worker loop is added.

Materialized driver candidates must preserve model identity and identify their
patch and changed binary. Materialized model candidates must preserve driver
identity and identify a new adapter. Base model/processor revisions and image
identity remain pinned by the frozen contract. Manifest identities are declarations
until trusted build/serving adapters independently verify the actual artifacts.

## Job lifecycle

1. `admit_job`: validate registered split assignment, resource reservations, campaign
   deadline and concurrency. Reserve budget and insert a `reserved` job atomically.
2. `begin_dispatch`: atomically change exactly once to `dispatching`, **before**
   contacting a provider. A replayed admission key returns current state; it does
   not authorize a second network submission.
3. `provider_started`: store the provider identity and change to `running`. Late
   acknowledgements may still be recorded after stop so cleanup can find resources.
4. `record_result`: persist the immutable result and artifact hash, then retain the
   slot in `cleanup_pending`. Assigned evaluation metadata must match the job.
5. `cleanup_confirmed`: only a trusted provider adapter may attest stopped resources,
   exported artifacts and reconciled usage. Settle every reservation and mark the
   job `cleaned` in the same transaction. Missing/invalid usage rolls back everything.

`cancel_undispatched` can refund a reservation with zero usage only while the job
is still `reserved`. Once dispatch has been claimed, failure/timeout is ambiguous:
query the provider using the durable job identity and never blindly resubmit.
Do not interpret a transient provider lookup miss as proof that no job was created.

Training assignments require a hashed dataset manifest and only registered train
seeds. The production Modal lifecycle additionally requires controller-registered
rollout receipts and revalidates dataset/custody bytes before dispatch; see
`AUTHENTICATED_TRAINING.md`. Structural job admission alone cannot launch training.
Private jobs require a durable lease that binds candidate identities, every exact
assignment, randomized order, expiry and schedule hash. Issuance consumes one of
the predeclared confirmation/sealed uses even if the lease is later abandoned.
Abandonment waits for cleanup and records an infrastructure failure; it never grants
a retry. Public development assignment is unique per candidate/task/repetition.

## Decisions and recovery

The development decision uses only recorded, provider-cleaned jobs for the
candidate and its parent under the candidate's comparison identity. Missing or
infrastructure-failed results cannot nominate. Qualified isolated driver and model
candidates can be registered as a joint candidate and evaluated through a fresh
2x2 factorial comparison. Decision inputs and outcomes are immutable. Development
only nominates. A separate confirmation lease can mark a candidate `confirmed`;
another explicit transaction promotes it, retires stale candidates and changes the
champion. Promotion requires all leases closed and all unrelated provider work and
accounting reconciled; an attested candidate serving endpoint may remain live for
the final sealed run. Rollback restores the previous champion, retires descendants
and preserves the original decisions. The one sealed use is available only after a
confirmed promotion and records a report without selecting a candidate.

`recovery_actions` reports actionable states:

- Reserved: eligible for one dispatch, or cancel undispatched if stopped/expired.
- Dispatching: reconcile ambiguous submission; never auto-retry.
- Running: poll provider, or cancel and reconcile if stopped/expired.
- Cleanup pending: export artifacts and cleanup before freeing its slot.

A local `stop` command freezes admission and records obligations. It **does not
execute provider cancellation**; the future watchdog/provider adapters must consume
those obligations. Do not report physical cleanup from the stop flag alone.

```bash
python3 -m fps_bench.campaign_controller status \
  --db /durable/campaign/controller.sqlite \
  --contract /controller/contract.json --expected-hash TRUSTED_SHA256
python3 -m fps_bench.campaign_controller recovery \
  --db /durable/campaign/controller.sqlite \
  --contract /controller/contract.json --expected-hash TRUSTED_SHA256
```

The CLI intentionally exposes no production launch command. `stop` additionally
requires `--reason` and clearly reports `provider_cleanup_not_executed=true`.

## Budget and telemetry integration boundaries

GameWorld training and serving admission need a Modal reservation; research
requests use external LiteLLM telemetry without token reservations. Fleet driver builds, rollouts and
evaluations carry no Modal reservation because their claims cannot authenticate or
reconcile Modal billing. Their shared Qwen inference deployment must instead be
covered once by its owning serving admission. Fleet jobs still require a desktop
slot, campaign deadline and provider cleanup receipt. The user capped Modal, not
Fleet billing; Fleet costs are not silently relabeled as Modal spend.

All receipt arguments are trusted-controller inputs, not cryptographic evidence.
Live adapters must authenticate/validate usage, handle bounded upstream retries,
import historical campaign usage and reserve cleanup overhead. There is no safe
production cap merely because these transaction tests pass.

In particular, the current development research relay independently reserves each
request. Before combining it with a research job reservation, implement parent
allocation/reconciliation or a single accounting owner: otherwise envelope and
request reservations double-count the same work. Do not settle both as independent
actual usage. This integration remains open in CUA-1167.

`emit_telemetry` converts ledger state into separate settled and reserved USD/tokens,
known active resources, and held concurrency slots. It checks campaign identity and
returns false instead of breaking cleanup on telemetry errors. Reserved slots are
not mislabeled as active provider resources. The caller must schedule recording and
flush, handle failures visibly, and avoid claiming accounting is complete before
provider reconciliation exists.

## Offline evidence

```bash
python3 -m unittest discover -s scripts -p campaign_controller_check.py -v
python3 -m unittest discover -s scripts -p campaign_ledger_check.py -v
python3 -m unittest discover -s scripts -p research_gateway_check.py -v
```

24 controller checks cover multi-process concurrency, atomic admission/cleanup,
immutable manifests/results, model/driver separation, train-only assignments,
ambiguous dispatch after restart, zero-cost undispatched cancellation, deadline and
budget refusal, stop/cleanup, exact protected-split leases, bounded abandonment,
paired and factorial confirmation, sealed reporting, promotion and rollback.

Persisted rehearsal: `results/runs/controller-offline-20260913/report.json`.
It uses the real frozen development schedule but **fabricated provider results**:
32 synthetic episode records, a development nomination with unchanged baseline,
budget refusal, ambiguous-submission recovery, cleanup-slot retention and zero
remaining synthetic cleanup obligations. All costs in this isolated rehearsal
database are synthetic; no provider calls, model training or real benchmark result
occurred. This does not fulfill the live end-to-end launch gate.
