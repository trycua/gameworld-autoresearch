# Bounded Modal training sandbox adapter

**Not live-launch ready.** This adapter connects the durable controller to a
one-shot training worker, but it has not created a real GPU sandbox. Its price
reservation is a compute estimate with margin, not a verified all-in billing cap.
The separate image/build, live dataset staging, artifact-export and billing gates must
pass before it is used by an unattended campaign.

## Implemented lifecycle

`fps_bench/modal_training.py` accepts only controller jobs already admitted as
`training` with a Modal budget reservation. It persists immutable launch identity
(workspace, app, environment, prebuilt image ID, dataset assignment, protocol,
deterministic sandbox name) in the controller's SQLite database.

- Only an existing `im-...` image is accepted. No image-building methods or app
  creation are called. The dedicated app must already exist.
- Sandbox shape is one L40S, CPU request/limit 4/4, memory request/limit
  32768/32768 MiB and a 60..1800-second provider timeout.
- Network access is blocked. No volumes, secrets, network filesystems, public
  ports or OIDC tokens are added. Model/processor downloads are offline-only.
- Workspace identity and sandbox-specific GPU/CPU/memory rates are checked before
  preparation; the price snapshot expires after five minutes. Creation rechecks
  workspace/prices and refuses an increase beyond the prepared reserve.
- Durable `begin_dispatch` precedes the create RPC. A lost acknowledgement can
  reconnect to the same named/tagged sandbox; unresolved absence never triggers
  recreation or a refund. Once known, provider sandbox ID is immutable.
- The worker execution attempt is recorded before the exec RPC. A lost exec
  acknowledgement is not automatically retried. The worker itself also creates
  an exclusive `/output/attempt-started` marker before loading the model.
- Termination intent persists before the RPC. A provider exit code is required
  before recording termination. **The job remains cleanup-pending and its budget
  hold remains held:** process exit is not billing reconciliation.

The current conservative state machine also retains the single training slot
while billing is unresolved. Separating verified physical cleanup from delayed
accounting is future work; silently freeing or settling either is not implemented.

## Worker contract

`scripts/qwen_lora_worker.py` runs a single pretrained image-bearing LoRA update,
then saves/reloads/verifies the adapter using `fps_bench.qwen_lora`. It expects:

- Pinned Python/CUDA/training dependencies and source under `/app`.
- The pinned pretrained Qwen model and processor already cached in the image.
- An initially absent `/dataset` directory; the controller stages and verifies
  its assigned dataset before worker dispatch.
- Writable `/output` for loss logs, checkpoint, local telemetry outbox and results.

There is no arbitrary command or hyperparameter input in the adapter. Exec gets
only controller-assigned hashes and bounded campaign/job identifiers. One worker
success code does not establish artifact integrity or mark the job complete.
The controller must export and verify artifacts before terminating the sandbox.

Loss callbacks write to `/output/telemetry.sqlite` without network export. Retain
that database as immutable evidence only; never open it in the controller.
`import_training_losses` reconstructs events from verified result/loss artifacts
with original timestamps into the trusted outbox; see `docs/TELEMETRY.md`. The
worker cannot call OTel directly because its network is blocked. A local
error-type artifact is retained for training failures. Neither a worker error
nor a successful training run automatically discards the sandbox.

## Cost evidence and limitations

A read-only call to the real Modal SDK verified workspace `cuaai` and current
rates; expected SDK async interfaces were also checked. Stored evidence:
`results/runs/modal-training-preflight-20260913/preflight.json`.

At that snapshot, the 600-second shape had a compute estimate of **547,600
micro-USD**, with a required hold of **2,095,200 micro-USD** (twice the estimate
plus USD 1). These are not observed charges or proof of an all-in maximum.
Image build/import, unreported startup/teardown charges, provider billing lag,
source/data image provenance and independent watchdog behavior remain unverified.
Do not lower the hold or enable campaign dispatch merely because this estimate
is small. Historical campaign usage remains in the canonical campaign ledger.

## Validation and remaining work

Eleven offline tests exercise real ledger admission and fake provider calls:
resource shape/rates, underfunding, frozen admission, stale rates, immutable image,
named collisions, missing/lost create acknowledgements, one-shot worker dispatch,
termination failure, and budget retention after physical shutdown. Installed
Modal 1.5.5 method availability was checked; this is not live GPU validation.

```bash
python3 -m scripts.modal_training_check
```

Still required: budgeted/prebuilt image production with immutable source/model
provenance, authenticated dataset staging, artifact export, all-in bounds and
billing settlement, independent cleanup watchdog, real GPU forward/backward,
checkpoint serving, and a real Fleet evaluation. No unattended launch command is
provided while those gates are missing.

Dataset upload and checkpoint export are now implemented with offline recovery
checks; see `docs/MODAL_ARTIFACTS.md`. Actual Modal transfers remain unverified.

## Explicit isolation policy

The selected pilot uses the contributor-authorized `app-scoped` policy described
in `docs/MODAL_APP_SCOPE.md`. It requires exact app/environment IDs and fresh
identity read-back, while retaining ledger holds, fixed resource limits,
no-network/no-secret training, and independent cleanup. It does not claim a
provider-side budget or an RBAC boundary from other workspace members.

The optional `restricted-environment` policy additionally requires the $25
compute-budget and role/concurrency read-back in `docs/MODAL_ENVIRONMENT.md`.
Its setup was denied for lack of manager permission, so it is not the selected
pilot path. Policy choice is explicit and immutable per admitted launch; there
is no silent downgrade. Neither mode substitutes for full all-in campaign
accounting or grants permission to launch the unattended campaign.
