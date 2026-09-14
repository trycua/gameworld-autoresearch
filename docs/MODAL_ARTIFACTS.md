# Modal training dataset staging and artifact export

Implemented and offline-tested; **no real Modal sandbox transfer or full-model
training has been run**. Tests use fake provider storage and synthetic checkpoint
bytes to exercise transport, not model validity.

`fps_bench/modal_artifacts.py` connects `TrainingArtifacts` to an acknowledged
`ModalTrainingLifecycle` sandbox and the existing controller job/ledger.

## Dataset staging

Call `await artifacts.stage(job_id, local_dataset)` before `run_worker`.

- Verify the dataset against the admitted dataset and contract hashes, including
  an exact match between dataset seed inventory and the admitted training seeds.
- Persist one upload attempt before touching the sandbox. Create `/dataset`
  exclusively; the reusable base image must not contain this directory.
- Upload only the inventoried dataset files, checking each digest by read-back.
  Publish `dataset.json` last, after all other writes complete.
- Mark staging ready only after the remote manifest and every listed file match.
  The worker dispatcher refuses to start without this durable receipt.
- Refuse repeated uploads or dataset replacement after worker dispatch. After a
  lost final upload acknowledgement, `reconcile_stage` performs read-only checks.
  If the final manifest is missing, discard/clean up the incomplete sandbox rather
  than starting an automatic second write attempt.

The image now needs cached model/processor weights and trusted training source,
not a separately baked dataset per experiment. Network remains blocked and no
persistent Modal volume is introduced. The SDK's filesystem write API is used;
reads use a fixed Python command bounded to 16 MiB plus one byte so an oversized
remote file cannot cause an unbounded download. Symlinks are rejected by that
reader. The installed Modal 1.5.5 async filesystem interface was inspected.

## Artifact export and recovery

After the one-shot worker finishes, call `await artifacts.export(job_id, output)`
**before terminating the sandbox**. The worker writes a completion marker last,
binding campaign/job/input identities to the training result hash. Export requires
both verified staging and a durable worker execution attempt.

The exporter checks the completion/result/adapter digest chain, exact base and
processor revisions, dataset/contract identity, and an allowlisted adapter file
inventory. It saves safetensors/config, result, loss log and telemetry outbox to a
new local directory. Files are read-only; `bundle.json` inventories their hashes.
No pickle/model deserialization is performed by this transfer module.

The export receipt is persisted before controller result ingestion. If interrupted
between those operations, `reconcile_export` revalidates all local bytes and
idempotently records the controller result. This recovery needs no running
sandbox. It refuses changed local files, and compare-and-set prevents concurrent
exports from replacing a job's established receipt.

Successful export moves the job to cleanup-pending; it does not terminate the
sandbox, settle billing, release the hold or certify a benchmark improvement.
Partial export directories are retained without a successful receipt. A new
exclusive output directory may be used while the same sandbox remains available;
this does not execute the training worker again.

The telemetry database is preserved as immutable evidence. Its events still need
validated import into the trusted writable telemetry outbox before flushing;
do not try to mutate the read-only evidence database in place.

## Checks and remaining work

```bash
python3 -m scripts.modal_artifacts_check
python3 -m scripts.modal_training_check
```

Twelve transfer tests cover staging prerequisites, partial writes, lost final
acknowledgement, preexisting destinations, input/checkpoint/local-export tampering,
missing completion, bounded/symlink reads, budget retention and recovery after
result-recording interruption. Eleven lifecycle tests remain passing.

Remaining: real prebuilt offline image/source validation, actual SDK transfer,
trusted image/trajectory provenance, real pretrained GPU update, telemetry event
import, inference adapter serving, provider cost settlement and watchdog cleanup.
These tests do not establish a safe all-in spending bound or launch readiness.

## Controller-side loss import

After export (or after recovery/termination), use
`import_training_losses(artifacts, job_id, controller_telemetry)` from
`fps_bench.training_telemetry`. This re-verifies the local bundle and imports only
cross-checked loss/step scalars with original timestamps into the trusted outbox.
Do not open or merge worker SQLite databases. Flush the controller outbox
separately. Missing timestamps require a rebuilt worker image and a new run;
historical artifacts are not silently relabeled. The post-termination path is
covered by an offline synthetic integration test, not yet a real GPU result.
