# Dedicated Modal pilot environment

## Manager action required

On September 14, 2026, the current credentials were denied creation of a
restricted environment: `Must be workspace manager to create a restricted
environment.` A subsequent authenticated listing confirmed that the intended
`gameworld-joint-20260913-pilot` environment does not exist. No workload was
started and the existing `main` environment was not modified. Evidence:
`results/runs/modal-environment-20260914/setup-denied.json`.

A Modal workspace manager must configure the dedicated environment. From this
repository with manager-authorized Modal credentials and Modal 1.5.5 installed:

```bash
python -m scripts.modal_environment_setup \
  --workspace cuaai --name gameworld-joint-20260913-pilot \
  --output /home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/modal-environment-manager
```

The command creates **only a new** `gameworld-` environment, restricted with
`no-access` as the default member role. It sets a $25 monthly compute budget,
maximum one GPU and two concurrent tasks, and verifies the resulting settings.
It refuses existing names and preexisting output directories; it never silently
adopts a collision or overwrites an existing environment. A failed/ambiguous
creation must be inspected manually before retrying. Do not bypass the manager
permission failure by creating an unrestricted environment or using `main`.
Workspace managers retain their administrative privileges; default member access
is not isolation from workspace administrators.

The $25 pilot budget is a conservative extra provider backstop, **not a change
to the approved $2,000 cumulative campaign cap**. Environment budgets operate within a monthly billing cycle and cover compute
rather than all costs. This is not a cumulative, all-in campaign cap. The
read-back alone also does not prove reporting latency or cleanup behavior for
already-admitted jobs; those require independent runtime evidence. The durable campaign ledger, bounded shapes/timeouts, independent cleanup,
noncompute allowances and authoritative billing reconciliation are still needed.
The six-hour campaign must not cross a billing-cycle reset without a separate
guard; no launch command is enabled by this setup.

Official reference: https://modal.com/docs/guide/budgets

## Admission and cleanup

`ModalTrainingLifecycle.prepare` requires the exact environment name **and ID**.
It retains a fresh read-back of the restriction, default role, budget and
concurrency settings in the immutable launch plan. Before sandbox creation and
worker execution, the lifecycle obtains another fresh read-back and refuses
missing, stale, replaced, exhausted or changed settings. Actual SDK creation
also rechecks the environment. Termination does not require this admission guard:
a budget/access-policy change must not prevent cleanup of existing owned work.
Provider permissions can still prevent termination; the watchdog retains that
unresolved obligation and its budget hold rather than claiming cleanup.

The implementation uses environment budget/concurrency RPCs from Modal 1.5.5
because those settings lack a public high-level method in the installed SDK.
The SDK version is checked before setup or read-back. This mapping is tested
locally but restricted-environment read-back remains unverified until a manager
completes creation. No claim is made that every failure mode is provider-tested.

Checks: `scripts/modal_environment_check.py`, `scripts/modal_training_check.py`,
`scripts/modal_artifacts_check.py`, and `scripts/campaign_watchdog_check.py`.
