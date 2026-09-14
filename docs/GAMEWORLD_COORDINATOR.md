# GameWorld workflow coordinator

`fps_bench/gameworld_coordinator.py` is the trusted restart-safe bridge between
the GameWorld research supervisor and the canonical campaign controller. Both
components use the same local SQLite ledger; researchers and Fleet/Modal workers
must not receive direct database access.

The coordinator currently persists and validates these paths:

- Driver proposal -> allowlisted patch -> Fleet build/contract job -> controller-owned
  base-model serving -> immutable driver candidate -> 68 candidate plus 68 paired-baseline
  development episodes -> serving termination and billing reconciliation.
- GRPO proposal -> controller-owned base-model serving -> one grouped Fleet rollout per
  selected train task -> serving termination -> authenticated combined dataset -> Modal
  training -> immutable adapter serving -> the same 136 paired development episodes.
- Qualified driver plus live qualified model -> fresh comparison identity -> all
  272 cells of the 2x2 baseline/driver/model/joint development schedule.
- Nominated isolated or joint candidate -> controller-issued private confirmation
  lease -> exact protected task queue -> immutable confirmation decision -> explicit
  promotion after provider cleanup, with reversible champion history.
- Promoted champion -> one controller-issued sealed lease -> 34-task final report
  that cannot select or promote a candidate, followed by candidate-serving cleanup.
- SFT proposals accept only task-prefixed train-split demonstrations with an
  immutable source receipt, explicit rights, a privileged-state exclusion and a
  frozen driver/contract identity. They then use the same Modal export, adapter
  serving and paired evaluation path as GRPO.

Fleet build, rollout and evaluation jobs do not reserve Modal dollars. A distinct
controller-admitted serving job owns each base-model or adapter GPU lifetime and
later reconciles that allocation. Base serving has a fixed `$10` hold and one-hour
maximum, stops before training, and restarts for protected driver evaluations.
Adapter vLLM advertises both the frozen base name and candidate LoRA name so paired
and factorial cells share one GPU. This avoids unaccounted inference and
unreconcilable per-Fleet-job Modal reservations.

The coordinator CLI is a durable, credential-free control-plane interface:

```bash
PYTHONPATH=. python3 -m fps_bench.gameworld_coordinator initialize \
  --database /durable/campaign.sqlite \
  --contract /trusted/contract.json --contract-sha256 "$CONTRACT_SHA256" \
  --baseline /trusted/suite-baseline-v1 --baseline-policy /trusted/policy.json \
  --state-root /durable/coordinator --campaign gameworld-joint-YYYYMMDD

PYTHONPATH=. python3 -m fps_bench.gameworld_coordinator status \
  --database /durable/campaign.sqlite \
  --contract /trusted/contract.json --contract-sha256 "$CONTRACT_SHA256" \
  --baseline /trusted/suite-baseline-v1 --state-root /durable/coordinator
```

Use `register`, `start`, `attach-patch`, `allocate`, `admit`, `advance`,
`dataset`, `attach-sft`, `joint`, `confirm`, `promote`, `sealed`, `rollback`,
`abandon-lease` and `close-serving` for individual state transitions. `status`
returns `required_actions`, including exactly-once dispatchable job IDs. Reopening
the coordinator with the same campaign, contract, baseline policy and state root
preserves queues and does not duplicate jobs.

Production initialization also validates the GameWorld contract schema and compares
every frozen controller-source hash with the current repository before opening any
workflow. Synthetic tests disable that host-source comparison explicitly; neither
the coordinator CLI nor the provider runner exposes a production bypass.

`fps_bench/gameworld_runner.py` is the separate credentialed execution process.
It consumes stable job IDs, resumes `dispatching`, `running` and `cleanup_pending`
work without blind resubmission, invokes Fleet build/rollout/evaluation adapters,
performs Modal SFT/GRPO stage-run-export-cleanup, starts and stops budgeted baseline
serving around driver/rollout work, keeps candidate serving alive through isolated
and factorial evaluation, and terminates it after the decision. Model proposals
carry exact training and serving reservation splits, so no operator can choose a
different allocation after proposal approval. `QWEN_API_KEY` authenticates all
controller-created endpoints; optional `QWEN_CANDIDATE_API_KEY` uses a distinct key
for them. No external baseline URL or secret is written to the ledger.

With `--enable-research`, the runner invokes the isolated Pi research profile when
the campaign is idle. Browser-verified sources feed one schema-constrained
proposal, and driver proposals receive a second schema-constrained patch pass over
only their approved source bytes. The child environment excludes Fleet, Modal,
Qwen and GitHub credentials. Attempts and output hashes are durable; three
consecutive failures freeze the campaign. Model proposals default to GRPO unless
`--sft-source-catalog` names trusted, already-custodied SFT datasets.

The SFT catalog has schema version 1 and a `sources` array. Each source contains
`id`, `tasks`, `dataset_root`, `dataset_sha256` and `source_receipt`. Paths stay in
the trusted runner; researchers receive only the source ID, task IDs and hashes.
The authenticated SFT registry re-verifies the selected dataset before any Modal
job is admitted.

Every runner cycle also checks completed Modal training and serving jobs for a
fully closed billing-hour window. It authenticates workspace billing, verifies no
sandbox remains active in the dedicated apps, rechecks each sandbox's terminal
status and immutable tags, retains the full reservation without a refund, and then
closes the controller jobs. Overlapping active holds defer reconciliation rather
than inventing per-job shares of an aggregate app-hour bill. Three consecutive
billing failures stop the campaign.

Use one bounded pass during supervised bring-up, then `run` only with the
independent watchdog active:

```bash
PYTHONPATH=. python3 -m fps_bench.gameworld_runner once \
  --database /durable/campaign.sqlite \
  --contract /trusted/contract.json --contract-sha256 "$CONTRACT_SHA256" \
  --private-splits /trusted/private-splits.json \
  --baseline /trusted/suite-baseline-v1 --baseline-policy /trusted/policy.json \
  --state-root /durable/coordinator --policy configs/gameworld-autoresearch.json \
  --catalog configs/evaluation/gameworld-suite-v1.json \
  --campaign gameworld-joint-YYYYMMDD --pool gameworld-autoresearch \
  --workspace cuaai --environment main --environment-id "$MODAL_ENVIRONMENT_ID" \
  --training-app gameworld-training --training-app-id "$TRAINING_APP_ID" \
  --training-image-id "$TRAINING_IMAGE_ID" \
  --serving-app gameworld-serving --serving-app-id "$SERVING_APP_ID" \
  --serving-image-id "$SERVING_IMAGE_ID" \
  --enable-research --sft-source-catalog /trusted/sft-sources.json
```

Validation:

```bash
PYTHONPATH=. .venv/bin/python scripts/gameworld_coordinator_check.py
PYTHONPATH=. .venv/bin/python scripts/gameworld_runner_check.py
PYTHONPATH=. .venv/bin/python scripts/gameworld_research_worker_check.py
PYTHONPATH=. .venv/bin/python scripts/gameworld_billing_check.py
node --test tools/pi/gameworld-proposal.test.mjs
```

The offline checks cover driver/GRPO routing, the full 34-game paired and factorial
queue sizes, comparison isolation, explicit model budget ownership, failed-rollout
rejection, authenticated SFT training/serving, proposal/patch materialization,
credential filtering, closed-hour billing recovery and restart idempotency. They do not
constitute a live Fleet or Modal campaign. Protected-split tests cover all 34
confirmation tasks and all 34 sealed tasks, promotion and rollback. Remaining gates
are current image/contract publication, production watchdog deployment, authenticated
provider campaign evidence and bounded real vertical slices.
