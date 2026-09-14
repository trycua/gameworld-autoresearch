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

The CLI is a durable control-plane interface. It admits work but intentionally
does not yet contain secrets or automatically dispatch provider calls:

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

Validation:

```bash
PYTHONPATH=. .venv/bin/python scripts/gameworld_coordinator_check.py
```

The offline checks cover driver/GRPO routing, the full 34-game paired and factorial
queue sizes, comparison isolation, model budget allocation, failed-rollout
rejection, authenticated SFT training/serving and restart idempotency. They do not
constitute a live Fleet or Modal campaign. Remaining gates are a credentialed
provider runner/watchdog, current image/contract publication, live billing
reconciliation and bounded real vertical slices.
