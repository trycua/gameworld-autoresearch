# Modal completed-work reconciliation: September 14, 2026

## Provider observation and retained budget

Fresh authenticated Modal billing for dedicated app
`ap-t8r2bbtsLKNVZP86TmksuX`, covering 00:00--03:00 UTC, reports:

| Hour | Reported USD |
| --- | --- |
| 01:00 | 0.18659213 |
| 02:00 | 0.60627336 |
| Total | **0.79286549** |

This is an app-hour aggregate covering image import, GPU training probes, adapter
serving and baseline attempts. It does not support inventing separate per-job bills
or treating missing storage rows as zero. Per-row upward rounding yields 792,867
micro-dollars for accounting.

All **six existing allocations, totaling $105**, remain charged against the cap.
They are now `reconciled_retained`, not active expired holds or claimed actual
bills. Group identity:
`modal-retained:286fa47a6d843228350544de9db33e78d261e97d2634272397c35d4edb873516`.
The canonical ledger remains the original `gameworld-joint-20260913` database.
No refunds, limit changes or budget resets occurred.

Including historical usage, total commitment is unchanged at **$106.013141**:
$1.806008 observed/high-water accounting plus $104.207133 retained headroom.
Expired held reservations are now empty. A real admission check succeeded inside
an explicitly rolled-back transaction; the ledger remained unchanged and no
provider dispatch occurred. This tests the ledger gate, not every launch gate.

## Authenticated closure and replay

The reconciler fetched provider billing, independently polled all five sandbox
IDs, compared their tags with original dispatch records and confirmed terminal
return codes. It verified the image import against the durable journal and the
provider image lookup. The dedicated app had no running sandboxes.

Evidence: `results/runs/modal-retained-reconciliation-20260914/`.
Fresh-provider replay evidence:
`results/runs/modal-retained-reconciliation-replay-20260914/`.
Original historical/failed-run evidence was not overwritten. A SQLite backup was
created in the private campaign state's `backups/` directory before reconciliation;
it is a recovery artifact, not a substitute spending ledger.

The group rejects scope overlap, reservation reuse, changed resource identities,
nonterminal resources, stale closure observations and direct settlement refunds.
Late upward revisions count only once and freeze admission if they exceed the
retained allocation. Lower/missing revised rows cannot free budget.

## Remaining footprint

The legacy `gameworld-qwen-baseline` function app
`ap-t3o23ALu2dMMQEYY7TUX0B` was observed idle, stopped, and then independently
listed as **stopped with zero tasks** at 03:22:59 UTC. The old public inference
endpoint is retired; future inference must use the bounded controller path.
The dedicated empty training app remains available with zero tasks.

The model-cache volume `vo-uM708PZGwMrEmXJH5IyNM6` remains. Its recursive inventory
reports 53 entries totaling 4,266,769,788 listed bytes. No volume billing row
appeared in this report; that is not evidence of a permanent zero charge. Cache
storage lifetime and the new campaign's all-in serving/training bounds remain
part of admission/cleanup work. The retained headroom has not been refunded on
the assumption that unreported charges are zero.

## Validation and launch boundary

15 reconciliation checks cover no-refund closure, replay, per-hour high-water
revisions, overage/freeze, prior/group deduplication, immutable provider bindings,
terminal/freshness checks and telemetry totals. Existing ledger, controller and
historical billing suites also pass. No workspace-manager operation was needed.

This resolves the completed-work expired-hold gate and records provider costs
conservatively. Authenticated training-data integration, production lifecycle
execution, remaining cost/usage coverage, isolation/recovery checks and the
bounded test campaign still need completion. No test campaign was launched here.

## Telemetry read-back

Prometheus independently returned `gameworld_modal_spend_USD=1.806008` and
`gameworld_modal_reserved_USD=104.207133` for the canonical campaign. Loki
returned the matching `retained-reconciliation-20260914` event at timestamp
`1789356203850490268`. These are observed accounting and retained headroom,
respectively, not a claim that $106.013141 has been billed by Modal.
