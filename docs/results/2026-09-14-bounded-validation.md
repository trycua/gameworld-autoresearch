# Bounded deployment validation, 2026-09-14

This is supervised bring-up, not a full campaign launch or an improvement claim.
The frozen catalog remains 34 games / 170 tasks. The existing compatibility
baseline and SFT validation were not repeated. LiteLLM token admission remains
disabled; the inherited Modal cap remains $2,000.

## Deployment

- Training build: GitHub Actions run `34898572251`, source `55be8ce`.
- Training image: `ghcr.io/trycua/gameworld-autoresearch@sha256:38e3043e5adb7f4f2a152bd630b49aba756f142184c4faa00af242d327fc151c`.
- Authenticated Modal image import: `im-REkDQRIEBY2qhy86FHlQiH`.
- Fixed Fleet build: GitHub Actions run `34900205082`, source `5b69da3`.
- Fleet image: `ghcr.io/trycua/gameworld-autoresearch@sha256:8d47c4a4e11cdedb89a8f657e3e4c480dd2007b1c2aadf48f7dc99d5d62e3812`.
- Terraform updated the existing gVisor pool in place: zero creates/deletes,
  maximum 20, minimum 0. No separate scale-to-zero test was run.

The first rollout worker failed before collecting data with
`ModuleNotFoundError: No module named 'fps_bench'`. Executing a Python script by
absolute path does not add its repository parent to the import path. The image
now sets `PYTHONPATH=/opt/gameworld-autoresearch`. Its build invokes both rollout
and driver worker `--help` entrypoints from `/tmp`, catching this packaging defect
before publication. Offline Rust rebuild and desktop smoke checks also passed.

## Researcher validation

The original browser gatherers timed out establishing MCP sessions and yielded
no verified sources. Local navigation with the system Chromium also timed out.
The installed Playwright headless shell passed concurrent navigation and source
snapshot probes for the Modal TRL and verl examples. A retry using the existing
`PLAYWRIGHT_EXECUTABLE_PATH` override completed browser-verified research.

Research attempt `gw-research-09ebece44eff7bf39abc17c901b5b10c` registered
`linux-input-report-framing`. Its patch attempt
`gw-research-9e79dfcb51016ee901323b89fa4d1e36` failed with `UnicodeEncodeError`:
the generated diff included non-ASCII existing source context, while the patch
contract requires ASCII. The researcher also concluded that the proposed report
framing behavior was already present and produced documentation-only changes.
No driver patch was applied or promoted; no driver build or paired evaluation
was submitted. This is a measured unsuccessful hypothesis/materialization, not
evidence of a driver improvement. A future loop should handle already-satisfied
hypotheses explicitly rather than forcing a non-behavioral candidate.

## Custody and accounting

Durable root:
`/home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913`.

The first failed rollout's Fleet claim was released and its Modal source-serving
sandbox terminated. At 22:00 UTC the authenticated closed-hour reconciliation
observed $0.137812 for the new image import and source serving, retaining the
full $40 allocation with no refund or finality claim. Inherited committed Modal
accounting became $351.013141, with no expired holds.

The updated image is frozen under custody
`/home/node/.local/state/gameworld-autoresearch/evaluation/20260914-5b69da3-v9`,
anchor `2fa93b679bf3e079a605824ec6af95d8d2ca0c1f0413c58f460210a91e7c14b6`.
`campaign-v8.sqlite` inherits reconciled accounting from v7; original failed
research/rollout evidence remains in `coordinator-v7`. An independently running
authenticated watchdog protects v8 jobs.

## Bounded GRPO validation

The updated-image attempt is `vertical-slices/grpo-authenticated-v8`:
two train-only tasks (`01_2048--01_01`, `05_breakout--05_01`), four stochastic
members per task, eight steps per member, maximum 64 rollout steps. A subsequent
two-step GPU update is permitted only if the authenticated exported dataset
contains nonzero reward variance. Source serving terminates before training.

The updated-image run reached Qwen inference and completed four stochastic
trajectories / 32 steps for the first train task. Group registration then failed:
the initial-state identity hashes differed. Examination of all four retained
initial states found that only `timestampMs` and `gameTimeMs` differed; the board,
seed, metrics, debug fields, and remaining state matched. The check hashes the
entire state, including volatile clock fields. This is a state-identity contract
defect, not evidence that this task's seeded board differed.

The frozen check was not bypassed, and the rejected artifact was not converted
into an accepted dataset after the fact. The second task and GPU optimizer update
were not submitted. No adapter, training loss, or benchmark improvement is
claimed. The next protocol needs an explicit initial-state equivalence rule
that distinguishes observation clocks from task-relevant time/state, with tests
that still reject actual state divergence.

The Fleet cleanup receipt confirms the claim is absent. Authenticated Modal
checks confirm no running sandboxes in either dedicated app; source serving
terminated with return code 137. The controller is stopped to prevent further
paid admission until a new protocol is prepared. The independent watchdog
remains available for cleanup.

OTel accepted the zero-optimizer-step validation result and accounting metrics:
`telemetry-export.json` reports logs and metrics sent, no errors, and no pending
logs. This is not a training-loss or benchmark-success result.

The latest serving allocation retains another $15, making conservative committed
accounting $366.013141 of the $2,000 cap. Its final closed-hour reconciliation is
scheduled for **2026-09-14 23:00:05 UTC**, not yet completed at this checkpoint.
`coordinator-v8/billing-process.json` records the local reconciliation process;
`billing-2300-result.json` and `billing-2300-telemetry.json` are its expected
receipts. No GPU or desktop remains running while that billing window closes.

Run evidence is in `vertical-slices/grpo-authenticated-v8/bounded-result.json`,
`provider-cleanup-verified.json`, `controller-after.json`, and the immutable
`coordinator-v8/fleet/grpo-rollout-v8-0` artifact bundle.

## Local checks

Follow-up: at the user's direction, removed the extra cross-member initial-state
hash equality gate rather than introducing replacement equivalence rules. Raw
per-member state hashes remain in custody; the dataset's existing group field
records the first member's hash for provenance, not an equality assertion.
GameWorld evaluation, seeding, reward calculation, and dataset integrity checks
remain unchanged. Research continues to use the existing history; no separate
history or hypothesis-rejection system was added. This source change does not
retroactively accept the failed frozen run or restart the campaign.

- Image input/provenance checks and both worker entrypoint import probes passed.
- Browser research tests: 12 passed.
- Fleet executor tests: 6 passed.
- Provider runner tests: 8 passed.
- Training registry tests: 12 passed.
- GRPO tests: 7 passed, 1 skipped (GPU-dependent).
