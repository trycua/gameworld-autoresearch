# GameWorld workflow coordinator

`fps_bench/gameworld_coordinator.py` is the trusted restart-safe bridge between
the GameWorld research supervisor and the canonical campaign controller. Both
components use the same local SQLite ledger; researchers and Fleet/Modal workers
must not receive direct database access.

The coordinator currently persists and validates these paths:

- Driver proposal -> allowlisted patch -> Fleet build/contract job -> immutable
  driver candidate -> 68 candidate plus 68 paired-baseline development episodes.
- GRPO proposal -> one grouped Fleet rollout per selected train task -> authenticated
  combined dataset -> Modal training -> immutable adapter serving -> the same 136
  paired development episodes.
- Qualified driver plus live qualified model -> fresh comparison identity -> all
  272 cells of the 2x2 baseline/driver/model/joint development schedule.
- SFT proposals accept only task-prefixed train-split demonstrations with an
  immutable source receipt, explicit rights, a privileged-state exclusion and a
  frozen driver/contract identity. They then use the same Modal export, adapter
  serving and paired evaluation path as GRPO.

Fleet build, rollout and evaluation jobs do not reserve Modal dollars. The Modal
training or serving resource that actually owns the GPU lifetime holds and later
reconciles that allocation. This avoids both unaccounted driver proposals and
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
`dataset`, `attach-sft`, `joint` and `close-model` for individual state transitions. `status`
returns `required_actions`, including exactly-once dispatchable job IDs. Reopening
the coordinator with the same campaign, contract, baseline policy and state root
preserves queues and does not duplicate jobs.

`fps_bench/gameworld_runner.py` is the separate credentialed execution process.
It consumes stable job IDs, resumes `dispatching`, `running` and `cleanup_pending`
work without blind resubmission, invokes Fleet build/rollout/evaluation adapters,
performs Modal SFT/GRPO stage-run-export-cleanup, keeps model serving alive through
isolated and factorial evaluation, and terminates it after the decision. Model
proposals carry exact training and serving reservation splits, so no operator can
choose a different allocation after proposal approval. Baseline
credentials come from `QWEN_BASE_URL` and `QWEN_API_KEY`; an optional
`QWEN_CANDIDATE_API_KEY` isolates candidate endpoints. No secret is written to the
ledger.

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

Use one bounded pass during supervised bring-up, then `run` only with the
independent watchdog active:

```bash
PYTHONPATH=. python3 -m fps_bench.gameworld_runner once \
  --database /durable/campaign.sqlite \
  --contract /trusted/contract.json --contract-sha256 "$CONTRACT_SHA256" \
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
node --test tools/pi/gameworld-proposal.test.mjs
```

The offline checks cover driver/GRPO routing, the full 34-game paired and factorial
queue sizes, comparison isolation, explicit model budget ownership, failed-rollout
rejection, authenticated SFT training/serving, proposal/patch materialization,
credential filtering and restart idempotency. They do not
constitute a live Fleet or Modal campaign. Remaining gates are current image/
contract publication, production watchdog deployment, live billing reconciliation,
private split leases, promotion/rollback and bounded real vertical slices.
