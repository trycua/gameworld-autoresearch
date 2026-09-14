# Train-only multimodal data bridge

The trusted-controller exporter is implemented; **no real training job has run**.
This is action-imitation input for a first LoRA save/reload/serve smoke, not GRPO
or evidence of policy improvement. The planned research campaign still includes
online game rewards and GRPO experiments based on the saved Modal TRL/VERL
references. A failed episode's valid actions can exercise the plumbing but must
not be called expert demonstrations or successful policy training.

## Trust boundary

`fps_bench.training_data.export_dataset` requires the frozen contract plus an
externally held contract hash and trusted episode receipts. Each receipt contains:

- `episode_id`, `split` (exactly `train`), `seed`, `contract_sha256`.
- The controller-assigned `driver_sha256` and `served_model`.
- `files`: SHA-256 digests of `manifest.json`, `summary.json`,
  `trajectory.jsonl`, and each `000.png`, `001.png`, ... observation.

These receipts must be produced by authenticated controller artifact ingestion,
not accepted from researchers as their own authority. The digest is an integrity
anchor, **not a signature or proof of authentic execution**. Producing trustworthy
receipts and wiring this exporter into live controller dispatch are still pending.

The exporter checks train membership, exact frozen episode configuration, source
hashes, upstream revisions, driver/model identities, completion, trajectory length
and ordering, response/action consistency, invalid totals, screenshot digests,
PNG validity and desktop geometry. Duplicate seeds and episode IDs are refused.
Development/confirmation/sealed labels and seeds outside train are rejected.
Paths cannot escape the artifact directory or traverse symlinks.

The original seed-42 pilot predates guarded frozen manifests and is intentionally
not admissible merely because seed 42 belongs to train. Collect fresh, guarded
train episodes; do not retrofit a contract hash into historical evidence.

## Output and worker verification

- `samples.jsonl`: prompt `messages` and assistant `completion`, using screenshot
  image references plus the exact frozen prompt and previous four responses.
- `images/<sha256>.png`: content-addressed screenshots used by valid targets.
- `dataset.json`: contract, receipt hashes, seeds, episode-level outcomes, sample
  count, and complete hashes for the training files.

Evaluator before/after state and reward objects are never serialized into model
inputs. Invalid responses remain in subsequent observation history, matching the
benchmark, but are not action-imitation targets. Episode outcomes stay only in
provenance, not in `messages` or `completion`.

The return value gives `dataset_sha256`, `samples`, and `seeds`. A worker must call
`verify_dataset(root, expected_dataset_hash, expected_contract_hash)` with hashes
received through the trusted job assignment **before** constructing its loader.
It verifies copied bytes, image membership and inventory; it does not authenticate
who supplied the external hash. Resolve relative image paths under that verified
root when adapting the records to the trainer. Do not load arbitrary extra files.

Pilot limits: 1..256 unique-seed episodes, 16 MiB per input file/text dataset,
64 MiB screenshots per episode, 256 MiB distinct screenshots per dataset. Output
is exclusive and read-only, with the manifest written last. An interrupted export
may leave an incomplete directory; without a verified final manifest it is not
eligible for training. Filesystem modes do not isolate same-user researchers.

## Local checks

Install the existing `baseline` extra (Pillow 11.3.0), then run:

```bash
python -m scripts.training_data_check
```

Fourteen synthetic checks cover the data boundary and worker-side tampering.
They are not evidence of a real dataset, training, loss, adapter reload, serving,
or benchmark improvement. No provider calls are performed.
