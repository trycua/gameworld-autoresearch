# Conservative Modal reconciliation

## Semantics

Completed work no longer has to leave permanently expired holds or claim a final
invoice to keep the campaign moving. `fps_bench/modal_reconciliation.py` supports
**retain-full-allocation-no-refund-v1** reconciliation of a closed app/hour window:

- Fresh provider checks confirm all mapped sandboxes terminated with the original
  tags, the dedicated app has no running sandboxes, and image imports completed.
- Resource identities, reservation IDs, scope and completion times are immutable.
- App/hour rows are observed once, with a per-row high-water mark for revisions.
  Missing or downward-revised rows never refund allowance.
- Holds become `reconciled_retained`, not `settled`. Their original allocations
  continue consuming the cap. `actual` remains unset: allocation is not billed cost.
- If observed charges exceed the combined allocation, only the excess is added
  and new admission freezes. Replaying observations cannot charge the excess twice.
- Group scopes cannot overlap historical imports or other groups; a row cannot
  also be imported as prior usage. One provider resource cannot close two holds.
- Ordinary job settlement cannot refund a retained allocation. The campaign ID,
  limits, historical rows and reservation identities are not reset or replaced.

This reconciles completed resource obligations conservatively. It does **not**
claim provider finality or authorize a refund from delayed/incomplete billing.
Keep polling the same group for upward revisions. Resource/app coverage, late
non-compute charges, current serving/training bounds and credential containment
still require the campaign admission audit.

`fps_bench.gameworld_billing.GameWorldModalReconciler` derives a closed-hour plan
directly from `billing_pending` training and serving jobs, their immutable launch
plans, termination receipts and reservation events. It refuses to close an hour
while another held Modal reservation overlaps that window. After authenticated
provider observation, it calls the same no-refund reconciler and atomically moves
each matching controller job to `cleaned` only after its reservation is proven to
belong to the retained group. It waits while any Modal job is active and applies
bounded exponential backoff to provider errors. A crash after ledger
reconciliation is recovered without a second provider allocation or refund.

## Trusted CLI

`scripts/modal_reconcile_completed.py` obtains billing directly through authenticated
`Workspace.billing.report`, polls the pinned provider IDs and tags, checks image
identity and the durable import record, then writes evidence before the atomic
ledger transaction. It requires the existing canonical GameWorld ledger; it does
not initialize a replacement. Plans belong to the trusted controller, not workers.
The GameWorld runner performs the equivalent flow automatically for its own
training/serving jobs once their billing hours are complete; the manual CLI remains
for historical probes, image imports and explicit revision polling.

```bash
PYTHONPATH=. python scripts/modal_reconcile_completed.py \
  --database /home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/campaign.sqlite \
  --scope /home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/modal-app/scope.json \
  --plan configs/modal/completed-work-20260914.json \
  --output results/runs/modal-reconciliation-UNIQUE
```

Use a fresh output directory for another provider observation. Revisions use the
same plan/group, rather than extending a closed scope or inventing per-job shares
of an aggregate app-hour bill. Subsequent campaign work needs a distinct covered
window/app and its own admissions.

## Telemetry

`accounting_totals()` separates observed high-water usage from retained headroom:

- Observed = settled jobs + historical usage + group observed charges.
- Reserved = active holds + the unspent part of retained group allocations.
- Their sum must exactly equal ledger commitment or telemetry refuses to emit.

Thus a retained $105 allocation with $0.792867 observed is represented as $0.792867
observed and $104.207133 retained headroom, not $105 billed, and not both the full
allocation and the same provider charges added twice. These are conservative
micro-dollar accounting values, rounded upward per provider row.

## Live evidence

See `docs/results/2026-09-14-modal-reconciliation.md`. All six completed probe/
baseline/import holds were closed without refunds, while the total commitment
remained $106.013141. No GPU work was dispatched by reconciliation.

Offline coverage: `scripts/gameworld_billing_check.py` verifies automatic plan
derivation, overlap waiting, retained job closure, crash recovery and the
three-failure stop gate.
