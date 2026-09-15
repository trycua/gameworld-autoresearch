# GameWorld v9 campaign monitoring

Campaign: `gameworld-joint-20260914-v9`.
State root: `/home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/coordinator-v9`.
Database: the adjacent `campaign-v9.sqlite`.

## First monitoring pass

The original runner started at approximately 00:46 UTC on September 15, 2026.
Research produced a driver proposal and a model proposal. The runner exited at
approximately 00:55 UTC, before starting the model's source-serving job.

The failure was operational, not a benchmark outcome:

- `driver-release-report-boundary` was marked rejected after `begin_dispatch`
  refused an expired, unreconciled reservation. Its driver build never ran.
  This must not be interpreted as evidence against the driver hypothesis.
- `model-2048-minimal-grpo` remained queued in `starting_source_serving`.
  `admit_ready` propagated `BudgetRefused` and terminated the runner.
- The expired reservation belonged to the earlier bounded GPU validation.
  Its provider had already been stopped; closed-hour accounting was pending.

No ledger history, candidate outcome, frozen evaluator, reward, source hash,
task split, budget limit, or reservation was rewritten to bypass this failure.
The runner's source is included in the frozen contract. A permanent change to
its billing-wait handling requires an explicit protocol transition rather than
editing the source underneath this campaign.

## Reconciliation and resume

The scheduled authenticated reconciliation completed at approximately 01:00:07
UTC. The receipt `billing-0100-result.json` reports:

- Outcome: `complete`.
- Jobs: `grpo-adapter-serving-v9` and `grpo-one-step-v9`.
- Observed cost: $1.508724.
- Retained commitment: $25, without a refund or provider-finality claim.
- `billing-0100-telemetry.json`: logs and metrics acknowledged, no errors,
  zero pending logs.

A detached operational launcher, `/tmp/gameworld-v9-resume.py`, waited for
expired holds to clear and checked that the campaign was not stopped, frozen,
or past its deadline. It then resumed the existing runner and research gateway
at approximately 01:00:09 UTC. It does not retry failed candidates or loop on
runner failures. Credentials are read/generated at runtime and are not logged.

Process receipt: `resume-0100-process.json`.
Launcher log: `resume-0100.log`.
Runner output: `campaign.log` (includes the earlier traceback).
On exit, the launcher writes `resume-0100-result.json` and stops its gateway.
The independent cleanup watchdog remains responsible for resource recovery.

At approximately 01:02 UTC, direct Modal inspection confirmed that sandbox
`sb-LmiIRdKA4wUF0mtV4zCtL1` was live. Its `/output/server.log` showed vLLM
application startup complete and successful `/v1/models` requests.
The ledger then recorded successful source-serving dispatch and advanced the
model workflow to `collecting_rollouts`. Rollout job
`gw-ff12babc2e5445c487f6965e533d3f64` is running in Fleet claim
`gameworld-autoresearch/gw-e7bf0f7e6c609cb071e9152e`.

This is progress evidence, not a completed campaign, training result,
benchmark improvement, full-catalog coverage, or final cleanup receipt.
The monitoring goal remains active. The existing $2,000 Modal cap is unchanged;
LiteLLM token limits remain disabled.

## Dataset handoff and first model outcome

At approximately 01:04 UTC, the rollout completed and the source-serving GPU
was terminated. The runner exited with code zero while the model workflow
remained `awaiting_dataset`: its research worker handles driver patches and SFT
datasets, but does not handle the coordinator's `register-training-dataset`
action. This is an incomplete automation handoff, not campaign completion.

The monitoring operator invoked the existing, frozen
`GameWorldCoordinator.prepare_training_dataset` method for the queued action.
It authenticated the rollout receipts, exported dataset
`4e3a4330655923423e4b200ced54c1ee69a70a503f6b96ff3c4cf8d6f8f4847e`, and
queued training without changing the proposal or evaluation rules. Evidence:
`operator-dataset-registration.json` and ledger events 547-549.

The runner resumed at approximately 01:06 UTC. The training job
`gw-9e83ad9c9b21d48a54c2e5d9e1b98616` launched in Modal sandbox
`sb-k2xx8K9nNO3nEmsy5ewafc` with a $5 reservation and 1,800-second deadline.
The attempt failed with `ValueError`; no adapter was accepted. The sandbox was
terminated and the workflow rejected at approximately 01:07 UTC. Direct Modal
inspection confirmed the sandbox was terminal. Its billing is still pending.

The exported dataset independently shows two 12-step trajectories, all 24
actions invalid, with identical rewards (-0.08437500000000002). The inspected
responses wrap JSON in Markdown fences, which the frozen parser rejects.
The existing trainer refuses datasets where every group has zero reward
variance. This is consistent with the failed attempt, but the runner retained
only the exception type, not enough detail to prove the precise exception
site. No parser relaxation, reward modification, or successful update is
claimed.

The loop automatically proceeded to research round 3 on the driver track.
This is measured feedback for subsequent research, not a reason to patch game
controls outside the research loop. The missing dataset handoff and incomplete
failure detail remain controller automation issues for a future protocol fix.

At the next telemetry check, logs and metrics were acknowledged with zero
pending logs (`monitor-0108-telemetry.json`). Conservative Modal commitment is
$431.013141 of $2,000, not an actual-billed-spend claim. The independent
watchdog remains active. The monitoring goal remains open.

## Round 3 and successful round 4 training

Round 3, `driver-startup-readiness-barrier`, produced a no-op diff after its
patch researcher found the proposed readiness behavior already implemented.
The Fleet worker rejected that diff at `git apply --check`; no changed driver
was built. The error reproduces locally. The Fleet claim was released and the
loop continued to round 4 without operator changes to the patch or history.
Evidence: `fleet/gw-8faf0e1a27407bced3c52641ef59a466/error.json` and
`research/gw-research-e4414b4a3e1c3b35e51f98e952d80e1e/result.json`.

Round 4, `model-breakout-action-lora-grpo`, chose two one-step Breakout train
rollouts and one optimizer step. Both rollouts completed. Their rewards differ:
one invalid response has reward -0.07500000000000001; one valid response has
reward 0.008333333333333331. The operator completed the same existing dataset
handoff after the runner exited idle, then resumed the unchanged campaign.
Dataset: `8860457e1e933017ec14289396a156998400cef0a8b485bed3cc67fdb899c9eb`.
Receipts: `operator-dataset-registration-breakout.json` and
`resume-breakout-0119-process.json`.

Training job `gw-9297fcda74939acf7bae1c5479e64d7d` completed and exported an
accepted adapter. Its authenticated `modal/<job>/result.json` reports:

- One optimizer step; two trajectories; zero zero-variance groups.
- 56 updated parameter tensors and gradient norm 1.8144479990005493.
- Initial-step loss 0.0; this is not a loss-improvement claim.
- Reload maximum log-probability error 0.0.
- Adapter manifest SHA-256:
  `8bd17928d74ce3b5f0b9d32d69c173d651e8f2680bab96a6c1bb9fb442d1d81d`.

By 01:25 UTC, candidate `model-8cbe4b79d50f8e412fbcd519` was serving and
the coordinator queued 136 development episodes: two repeats for candidate
and parent across all 34 games. Two Fleet evaluation jobs were running.
Training success does not imply successful evaluation or promotion.

Pending operational risk: the old failed-training reservation expires at
approximately 01:36 UTC while its provider is already terminated. The current
reconciler waits for closed billing hours and refuses reconciliation while
another GPU job is active. The runner can consequently encounter the same
billing-wait defect during evaluation. No reservation deadline, ledger state,
or frozen controller source has been changed to hide this risk.

## Operational wrapper handover

The billing risk was addressed through a separate host-side operational
entrypoint, `scripts/gameworld_campaign_operator.py`. It invokes the existing
coordinator, provider runner, and conservative reconciliation APIs. It does
not replace the evaluator or change any frozen source file. A full workspace
verification against the existing contract passed after the change.

The wrapper:

- Waits before dispatch when a held reservation is expired or within 30 seconds
  of expiry, instead of turning an accounting wait into a candidate failure.
- Continues cleanup and authenticated billing checks during that wait.
- Registers completed GRPO datasets using the existing coordinator action.
- Selects completed billing scopes per app, allowing the stopped training app
  to reconcile while the separate serving app remains live. It still requires
  a completed UTC billing hour, authenticated provider closure, no active
  resources within the selected app, and full retained allocations without
  refunds. Unknown/unbound holds prevent reconciliation.
- Uses a single-operator lock and prints structured progress to `operator.log`.

Seven new offline checks cover waits without dispatch/rejection, dataset
handoff, independent-app reconciliation, same-app exclusion, unknown holds,
open-hour refusal, and unexpected live-provider refusal. These plus existing
runner and billing checks passed: 20 tests total.

Both first paired evaluation results were durable before the old runner was
paused. The remaining claim was released through the existing lifecycle API;
both claims were confirmed cleaned. The old runner and gateway were then
stopped, and a replacement gateway and operational entrypoint started with the
same serving credential. No episode was rerun during handover. The old process
exit is an intentional handover, not an experiment failure.

Receipts: `operator-pause.json`, `operator-process.json`, and the existing
Fleet release receipts. The replacement is supervised by
`/tmp/gameworld-v9-operator-launch.py`; its log is `operator-launch.log`.
The runtime credential environment is stored outside the repo in a mode-0600
file and must not be printed or committed.

At 01:36 UTC the wrapper reported `waiting-billing`, preserving the pending
evaluation queue and the $2,000 cap. Earliest training-app reconciliation is
02:00 UTC. The serving GPU remains live under its existing reservation; its
idle time still incurs cost. This wait does not extend its resource deadline.

At 02:00:04 UTC, the operational wrapper successfully reconciled both training
jobs against the closed training-app hour while the serving GPU remained
live. The authenticated receipt observed $0.149678 and retained the full $10
allocation without refund. Both training jobs became `cleaned`; no held
reservation expiry was extended or ignored. The wrapper automatically
dispatched the next two evaluation episodes at 02:00:06 UTC.

Evidence: `billing/gw-modal-billing-8311f4186b51129e4248eb9bf5b3a96b/`,
`operator.log`, and ledger events 724-734. The first completed parent/candidate
pair remains preserved: both executed 60 actions on Captain Callisto, with
zero invalid actions and zero driver errors, but neither succeeded or made
reported progress. This does not establish a candidate improvement.

The post-reconciliation OTel export (`operator-0200-telemetry.json`) acknowledged
logs and metrics with no errors and zero pending logs. Evaluation and monitoring
remain active; full campaign completion and final cleanup are not yet proved.

## Independent evaluation replay during collection

By approximately 02:22 UTC, 13 completed development episodes independently
replayed through the pinned upstream evaluator: 780 steps and each final
evaluation matched their recorded results. The audit also verified controller
receipt bindings, every exported artifact hash, frozen catalog/task hashes,
and agreement between exported summaries and controller scalars.

One additional baseline episode on `34_worlds-hardest-game-2--34_03` failed
before evaluation: Playwright timed out after 30 seconds waiting for the local
game page's `load` event. Its failed artifact bundle is retained and verified;
it is not included in the 13 successful replays. No retry or parser/navigation
change was introduced. The candidate episode on the same task completed, so
this observation alone does not show that the game is unsupported.

Receipt: `independent-replay-20260915-022201.json`. The independent audit script
is `/tmp/gameworld-v9-replay.py`; it does not launch games or modify campaign
decisions. Verified per-episode progress and infrastructure failures are
exported to OTel with phase `development-progress`, separate from final
comparison metrics. Stable event IDs prevent duplicate log events on repeated
audits. No full-suite score or improvement claim is made from partial results.

## Continued monitoring through 03:49 UTC

The operator and independent cleanup watchdog remained live throughout the
subsequent checks. At 03:49 UTC, 66 development jobs had returned, two were
active, and 68 remained pending. Independent replay verified 64 completed
episodes across 33 games, including 3,840 recorded steps and final results.
The two other returned jobs are preserved infrastructure failures, not
successful evaluations: the earlier World's Hardest Game 2 baseline page-load
timeout and a Vex 3 candidate game-initialization failure.

Receipt: `independent-replay-20260915-034949.json`. OTel acknowledged the
verified progress and failure events with no errors and zero pending logs.
Observed concurrency remained at most two desktop evaluation jobs and one
serving GPU. No candidate promotion or complete benchmark score is claimed.

The serving deadline remains September 15 at 04:22:57 UTC and the controller
deadline remains 05:00:37 UTC. The user was asked to authorize a 12-hour total
operational window and serving replacement; no explicit answer has been
received. Neither deadline nor the $2,000 Modal cap has been changed. The
installed Modal SDK exposes no live timeout-extension method; a future
authorized extension needs an explicit, bounded serving replacement and
controller continuation mechanism, not a silent timestamp rewrite.

## Authorized operational extension at 04:39 UTC

The user subsequently explicitly authorized extending the deadline and launching
replacement capacity. The effective controller and research-supervisor deadline
is now **September 15, 2026 at 11:00:37 UTC**, twelve hours from campaign creation.
The original six-hour initialization duration remains recorded unchanged, alongside
an append-only extension receipt and ledger event. Only the running research action
deadline was extended; completed actions, job deadlines, reservations, private
leases, and evaluation inputs were not changed. There were no private leases.

Evidence: `operational-extension-20260915.json` in the coordinator state directory
and the `gameworld_operational_extensions` table. The implementation is in
`scripts/gameworld_capacity_operations.py`, outside the frozen evaluator sources.

The previous serving sandbox stopped at its existing 04:22:57 deadline. Provider
checks found no running sandboxes in either pinned Modal app, and the Fleet pool
had no claims at 04:25:44. Evidence: `monitor-0424-provider-cleanup.json` and
`monitor-0425-fleet-cleanup.json`. There are 74 returned development jobs (72
completed episodes and two infrastructure failures), with 62 pending. Independent
replay has verified all 4,320 completed steps and their final evaluations across
all 34 games. This is not completion of all 170 catalog tasks or the comparison.

The operational wrapper was restarted at 04:42 UTC with same-policy serving
replacement support. It waits for authenticated closed-hour serving reconciliation
at or after 05:00 UTC before reserving a new bounded three-hour L4 sandbox.
Replacement uses the same authenticated adapter and frozen generation settings;
the original candidate manifest and all work-item assignments remain immutable.
Only the workflow's serving pointer changes after authenticated readiness. A
coordinator view follows that pointer for cleanup without rewriting the historical
serving work item. A fresh quote and reservation must pass the existing cap and
single-GPU admission checks. There is no refund or extension of expired holds.

The $2,000 Modal cap, no LiteLLM token budget, existing history, evaluator, reward,
and episode limits remain unchanged. At this checkpoint replacement was configured
but had not launched; no new score or candidate-improvement claim is made.

## Replacement verified and evaluations resumed

At 05:00:43 UTC, authenticated serving-app reconciliation completed for all three
previous serving jobs. It observed $6.639345 and retained the entire $45 allocation
without refund. Receipt directory:
`billing/gw-modal-billing-4452b8e7201f6b3ff01b84f1e4e7b617/`.

The fresh serving job `gw-replace-eb46807e38d919c60c7358bc` passed authenticated
readiness at 05:02:55 UTC on sandbox `sb-0vdjVQmN9fjIhA2cTBwvOy`. Its new
three-hour resource deadline is **08:00:43 UTC**, separate from the extended
11:00:37 campaign deadline. Its fresh reservation is $13.813600; total conservative
Modal commitment is $479.826741 of $2,000, not a statement of actual billed spend.
Both parent and candidate policy digests match their previous serving generation.
Evidence: `capacity-replacement-verification-20260915.json`, serving launch records,
and the `serving_capacity_replaced` ledger event.

The first resumed parent/candidate pair on Cubefield completed at approximately
05:08 UTC, with 60 actions per episode, and both claims were cleaned. Independent
replay at 05:09 verified 74 completed episodes and all 4,440 steps plus final
results; the two earlier infrastructure failures remain preserved separately.
Receipt: `independent-replay-20260915-050911.json`. Runner accounting and replay
telemetry were delivered to OTel with no errors and zero pending logs.

All 25 operational, serving-identity, runner, and billing checks pass, and frozen
contract source verification passes. Commit `254c07d` contains the operational
implementation. The operator, gateway, and independent cleanup watchdog remain
active; remaining evaluations and terminal campaign cleanup are still outstanding.
