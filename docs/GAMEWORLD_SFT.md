# Authenticated GameWorld SFT warm start

GameWorld SFT uses the existing screenshot/action imitation format from
`fps_bench/training_data.py`, extended with a `gameworld` provenance object in
`dataset.json`. The trusted coordinator registers the immutable dataset before it
can admit a Modal training job.

Required GameWorld metadata:

```json
{
  "gameworld": {
    "schema_version": 1,
    "tasks": ["02_game--02_01"],
    "driver_sha256": "...",
    "source_receipt_sha256": "..."
  }
}
```

Every sample ID starts with exactly one admitted train task ID followed by `:`.
Every admitted task must contribute at least one sample. The ordinary dataset
verifier also checks immutable image names/content hashes, referenced-image
coverage, the frozen evaluation contract hash and the complete file inventory.

The separate source receipt records the source kind (`human-demonstrations`,
`teacher-policy` or `state-oracle-distillation`), exact tasks, rights statement,
source artifact hash, timestamp and an explicit assertion that the evaluation
policy contains no privileged state. This receipt is a trusted-controller
attestation; the caller must verify the referenced raw artifact before registering
it. Researchers cannot self-register datasets or write the campaign database.

The pilot SFT path is intentionally a warm start from the frozen base model. It
does not silently continue an existing adapter. Modal stages and reads back the
dataset plus baseline policy identity, runs `scripts.gameworld_model_worker` with
`--objective sft`, exports the adapter before cleanup, verifies save/reload
provenance, then serves it through the same immutable candidate lifecycle used by
GRPO. Driver and benchmark identities remain fixed.

Validation:

```bash
PYTHONPATH=. .venv/bin/python scripts/gameworld_sft_check.py
```

This is offline provider-fixture evidence. A real GPU SFT update using a newly
registered GameWorld demonstration artifact is still required before launch.
