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
