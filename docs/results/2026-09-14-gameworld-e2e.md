# Updated Fleet end-to-end validation

## Deployment and custody

- Source `c80434a`, GitHub Actions image build `34906023942`: passed.
- Terraform updated `gameworld-autoresearch` in place, without recreating the
  pool: gVisor, minimum 0, maximum 20.
- Deployed image:
  `ghcr.io/trycua/gameworld-autoresearch@sha256:3e0e448ab666d2cf6b708e0f73873393d31ae98692e0da3f1a79585cb4b51e10`.
- Current contract custody:
  `/home/node/.local/state/gameworld-autoresearch/evaluation/20260914-c80434a-v10`.
- Contract anchor:
  `9bbe8eef86a9e12573b1ab620df7923846727a3cc1a79b9209d3e5e7ecee5985`.
- Campaign ledger: `campaign-v9.sqlite`; coordinator: `coordinator-v9`.

All campaign paths below are relative to
`/home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913`.
The original frozen catalog remains 34 games / 170 tasks; this is a bounded
integration test, not full-catalog coverage or a promotion run.

Prior v8 billing reconciled at 23:00 UTC on September 14: $0.176781 observed,
$15 retained without a refund or provider-finality claim. The v9 accounting fork
preserves $366.013141 committed against the $2,000 cap. The previous validation
freeze was cleared only in the new protocol ledger, with an explicit
`operator_authorized_protocol_resume` event referencing the user's request.
The prior ledger and evidence remain untouched. No LiteLLM token cap was added.

## Rollout result: passed

`vertical-slices/grpo-authenticated-v9` contains authenticated rollouts for:

- `01_2048--01_01`: four stochastic members, eight steps each.
- `05_breakout--05_01`: four stochastic members, eight steps each.

Both groups exported and registered successfully: eight trajectories, 64 steps,
one zero-variance group and one nonzero-variance group. The additional initial
state equality gate is gone; per-member raw state remains in custody. GameWorld
task evaluation, rewards, and dataset integrity verification remain unchanged.

Combined dataset SHA-256:
`bc0876eb333d8e890510e2e6db82046659d9a62c1778721cb16c9a37fa3f0895`.

Both Fleet claims were released and source serving stopped before training.

## Training bring-up

The first real L40S attempt, `grpo-authenticated-v9`, requested two optimizer
steps within 1,500 seconds. A direct authenticated progress probe observed the
first optimizer step with finite gradient norm `0.6372823119163513`, loss
`-7.916241884231567e-09`, and zero initial reference KL. This probe is partial
progress evidence, not a completed or exported training result.

The attempt returned without `/output/worker-finished.json` near the execution
deadline. The export gate rejected it, and cleanup terminated the sandbox. No
adapter was accepted from that attempt. Dedicated-app inspection confirmed no
running GPU sandboxes, and all Fleet claims were already absent.

A separate one-step validation was predeclared in `one-step-intent.json`, using
the same authenticated dataset, a 1,800-second deadline and a $10 allocation.
It is scheduled only after closed-hour reconciliation at **September 15, 2026,
00:00:05 UTC**. It does not recollect episodes, alter the GRPO objective, resume
an unexported checkpoint, or weaken artifact verification. The conditional final
check reloads the exported adapter and evaluates one frozen development Breakout
task. No candidate promotion or improvement claim is permitted.

At this checkpoint the one-step retry and adapted-policy evaluation are pending.
