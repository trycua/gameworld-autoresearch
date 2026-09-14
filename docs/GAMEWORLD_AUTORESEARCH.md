# GameWorld joint autoresearch

The GameWorld supervisor adapts the repository's original FPS driver hill-climb
into a catalog-aware OODA controller. It treats the completed 34-game,
170-task compatibility sweep as immutable observation evidence and requires
isolated `driver` and `model` experiments before any joint comparison.

The frozen policy is `configs/gameworld-autoresearch.json`. Every game contributes
two train tasks, one development task, one confirmation task and one sealed task.
Researchers may cite any compatibility observation, but model training can use
only train tasks and candidate selection can use only development tasks.
Confirmation and sealed work remain controller-owned.

Initialize a supervisor against an externally retained baseline:

```bash
python scripts/gameworld_autoresearch.py initialize \
  --database /path/to/campaign.sqlite \
  --baseline /path/to/suite-baseline-v1 \
  --campaign gameworld-joint-YYYYMMDD
```

Inspect durable OODA state:

```bash
python scripts/gameworld_autoresearch.py status \
  --database /path/to/campaign.sqlite \
  --baseline /path/to/suite-baseline-v1
```

Register a proposal emitted under `.auto/gameworld-prompt.md`, then ask the
trusted scheduler which hypothesis may run next:

```bash
python scripts/gameworld_autoresearch.py register \
  --database /path/to/campaign.sqlite \
  --baseline /path/to/suite-baseline-v1 \
  --proposal /path/to/proposal.json

python scripts/gameworld_autoresearch.py next \
  --database /path/to/campaign.sqlite \
  --baseline /path/to/suite-baseline-v1
```

The scheduler balances completed attempts across the driver and model tracks.
It refuses unobserved evidence, non-HTTPS research sources, evaluator or split
leakage, driver paths outside the allowlist, malformed GRPO group sizes, and
resource requests outside the shared campaign limits. `joint_ready` becomes true
only after at least one candidate from each isolated track qualifies.

This first slice owns trusted observation, orientation and action admission. The
provider workers added in subsequent milestones must use `begin` and `finish` so
an unselected proposal cannot consume Fleet or Modal resources. Candidate
materialization, GRPO rollout collection, paired evaluation and factorial
promotion remain separate provider-facing stages; they must not weaken this
supervisor contract or mutate the frozen compatibility evidence.
