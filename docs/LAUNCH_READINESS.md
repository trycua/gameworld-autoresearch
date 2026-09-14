# GameWorld joint autoresearch launch readiness

Last updated: September 14, 2026. **Not ready; no autonomous campaign launched.**

Linear project: GameWorld Joint Autoresearch - Launch Readiness.
Parent gate: CUA-1166. Repository plan:
`docs/plans/2026-09-13-gameworld-joint-autoresearch.md`.

| Issue | Gate | Current evidence | Still required |
| --- | --- | --- | --- |
| CUA-1167 | Shared budgets | Atomic ledger; development relay; real historical Modal app-hour import and replay; usage metrics verified; real expired-hold admission refusal with unchanged ledger | Verified upstream bounds, remaining historical usage, live all-in billing reconciliation, production admission and trusted controller |
| CUA-1168 | Frozen evaluation | Frozen source/assets/seeds; paired calculations; all 960 baseline steps independently replayed; 2080 external read-only artifacts hash-verified | Separate-identity custody deployment and durable confirmation/sealed-use limits |
| CUA-1169 | Fleet lifecycle | Pinned gVisor min0/max20; two-desktop frozen harness staging; 4.87s warm driver rebuild; live independent watchdog release; completed baseline cleanup reconciled after asynchronous deletion | Isolated patch worker and supervised watchdog deployment; post-release scale-to-zero check waived |
| CUA-1170 | Telemetry | Actual pretrained GPU loss and full 16-episode benchmark aggregates verified in Prometheus/Loki; durable outboxes; external artifact custody; dashboard JSON | Production-loop integration and dashboard publication/rendered verification (write access denied) |
| CUA-1171 | Multi-seed baseline | COMPLETE: 16/16 development episodes, 0 successes, 0 invalid actions, median102.519s; seed-cluster interval; full replay/custody | Reuse this pinned baseline in production candidate comparisons; no benchmark improvement claimed |
| CUA-1172 | Coordinator | Durable joint workflow coordinator; isolated driver and GRPO queues; immutable patch/build, rollout, training, serving and paired/factorial identities; restart-safe exactly-once job admission | Credentialed provider runner, SFT ingestion, private leases, promotion/rollback and live watchdog evidence |
| CUA-1173 | Research integration | Browser tools, evidence checks and development relay | Campaign-integrated proposals, full egress containment and complete usage accounting |
| CUA-1174 | Multimodal training | Actual pretrained L40S LoRA update: loss1.749093, peak9.72GiB, exact reload; exported adapter served through vLLM on L4; verified public image/import and real telemetry | Authenticated train-only live ingestion through production lifecycle; immutable serving admission; model-only evaluation; all-in accounting |
| CUA-1175 | Joint comparison | Fresh comparison IDs; full 136-episode isolated and 272-episode qualified 2x2 GameWorld queues; immutable paired/factorial decisions | Real model-only and driver-only comparisons, then a live qualified factorial run |
| CUA-1176 | Launch rehearsal | Persisted 32-episode synthetic controller round plus budget/restart/stop/cleanup checks | Full bounded live rehearsal, stop/resume cleanup, evidence audit and executable launch command |

Approved limits remain $2,000 Modal ($1,800 normal/$200 shutdown) and 1B cumulative
LiteLLM tokens. Configured limits are not a claim of full provider enforcement.
Pilot target: two desktops, one training job, at most ten candidates/six hours;
Fleet min 0/max 20. No changes to this plan authorize exceeding those limits.

See `docs/CAMPAIGN_ACCOUNTING.md` and `docs/FROZEN_EVALUATION.md` for implementation
boundaries and exact frozen artifact identities. Keep this status separate from
claims about a running campaign or benchmark improvements.

Live Fleet-only probe details: `docs/results/2026-09-13-fleet-controller-probe.md`.

Selected Modal isolation uses the dedicated app-scoped policy in
`docs/MODAL_APP_SCOPE.md`; workspace-manager access is not a prerequisite. This
is not provider-side dollar enforcement or isolation from workspace members.
The timestamp-enabled image is source `6a1309c`; a supervised, journaled Modal
import has a $25 hold in the canonical campaign ledger. See
`docs/MODAL_IMAGE_IMPORT.md` for retry, billing and timeout limitations. The hold
is not an observed charge or proof of an all-in maximum.

Measured baseline: `docs/results/2026-09-14-frozen-gameworld-baseline.md`.
The canonical ledger retains $106.013141 in commitments, mostly reservations,
not final billed charges. Expired earlier holds currently refuse new Modal
admission; reconcile them before further paid dispatch. No budgets were reset.
