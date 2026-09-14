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
