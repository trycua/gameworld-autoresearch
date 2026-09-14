# Full GameWorld auto-research scope

The Fleet desktop image contains the complete pinned GameWorld library: **34
games and 170 task definitions**. `configs/evaluation/gameworld-suite-v1.json`
is the machine-readable inventory used to keep every game and task in scope for
the auto-research loop. It pins the same upstream commits as
`image/Dockerfile.gameworld` and records hashes for every game and task YAML.

The current frozen benchmark remains `01_2048/01_01`. The first live test uses
that existing protocol so it measures the already-verified environment and
does not smuggle an unmeasured driver change into the campaign. The all-game
inventory is broader research scope, not a claim that today's 2048-only action
schema can already control every game.

The loop may propose and evaluate Cua Driver or model changes needed by the
other games. Such changes must be materialized as candidates, rebuilt in the
GameWorld image, and measured against pinned catalog tasks. They must not alter
the existing 2048 baseline evidence or its frozen contract.

## Compatibility baseline phase

`scripts/gameworld_suite_campaign.py` runs one measured Qwen action for each of
the 170 catalog tasks. This is not a claim of task completion or a replacement
for the frozen 2048 benchmark. It records whether the current model emits a
registered semantic action and whether the current Cua Driver can execute its
catalog binding. Unsupported controls, invalid model actions and infrastructure
failures remain explicit results for the research loop.

The launcher is pinned to the Terraform-managed `gameworld-autoresearch` gVisor
pool, two desktop claims, the current Qwen revision, and the catalog manifest
hash. It uses the canonical campaign ledger, retains a conservative $100 Modal
reservation until provider reconciliation, stops after three consecutive
infrastructure failures, writes resumable artifacts outside the workers, and
emits aggregate baseline metrics to `otel.cua.ai`.

Prepare the immutable intent and budget hold before deploying inference, then
start or resume the sweep:

```bash
python scripts/gameworld_suite_campaign.py \
  --database /path/to/campaign.sqlite \
  --qwen-env /path/to/qwen.env \
  --output /path/to/suite-baseline-v1 \
  --prepare-only

python scripts/gameworld_suite_campaign.py \
  --database /path/to/campaign.sqlite \
  --qwen-env /path/to/qwen.env \
  --output /path/to/suite-baseline-v1 \
  --resume
```

Regenerate the inventory only from the exact pinned repositories:

```bash
python3 -m scripts.gameworld_suite_catalog \
  --upstream /path/to/GameWorld \
  --games /path/to/GameWorld-Games \
  --output configs/evaluation/gameworld-suite-v1.json
```

The validator refuses fewer than 34 games, fewer than 170 tasks, duplicate
identities, changed source revisions, invalid hashes, or a changed pilot
boundary.
