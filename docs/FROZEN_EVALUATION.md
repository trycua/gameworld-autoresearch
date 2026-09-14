# Frozen GameWorld pilot evaluation

## Status and custody

The controller-side contract and seed sets are frozen. The 16-episode development
baseline completed on September 14, 2026: **0/16 successes**, with all 960 steps
replayed by the trusted controller and 2080 artifacts registered in external
read-only custody. See `docs/results/2026-09-14-frozen-gameworld-baseline.md`.
Production coordinator integration, OS isolation and persistent confirmation-use
enforcement remain required. Linear: CUA-1168/CUA-1171.

Suite: `gameworld-2048-cua-qwen-v2-pilot-1`.
Contract SHA-256: `f2a1161156fa185ba9ad696b8bfc05369420cdde065ebd9fe7ae367faf38d5f9`.
Controller custody: `/home/node/.local/state/gameworld-autoresearch/evaluation/20260913-v2-pilot-1`.
Baseline assignment plan: `results/runs/frozen-baseline-plan-20260913/plan.json`.
Plan SHA-256: `fc6538348c4e4a355ccb196b55e0a068f853bccab60647a62861c9a13cabccd3`.

The custody directory contains the public contract, a separate private split file,
read-only copies of the evaluator source, the three upstream evaluator/task/random
files, and the 2048 game assets. Public contract data contains training and
development seeds only, plus a salted commitment to the private sets. Private
seed values are not in this document, the repository, or the Linear ticket.

Custody is outside the repository and mode 0700; files are mode 0400. **This is not
an OS security boundary against another process running as the same Unix user.**
Before researchers can patch code autonomously, deploy the controller/snapshots
under a separate identity and do not mount private seeds, the trust anchor, provider
credentials, or writable evaluator files into candidate workspaces. A hash check
inside an agent-writable guest does not independently prove integrity. Verify on
the trusted controller too. Hash checks before/after episodes do not prevent
transient tampering; read-only deployment and isolated writers remain required.

The frozen source matches the current code at initial freeze time. Future evaluator
changes must create a new contract/version; never overwrite this custody directory
or silently recompute its anchor. Driver changes do not alter frozen evaluator
files. The original GHCR image does not yet contain these new modules: verified
controller snapshot staging was used for the completed baseline; production
coordinator staging still needs integration.

## Protocol and splits

The frozen spec is `configs/evaluation/gameworld-2048-v2.json`:

- 2048 task `01_01`, tile-32 success target, 60 actions, 900-second episode timeout.
- Screenshot plus last four responses only; native foreground keys held 80 ms,
  300 ms settle, temperature 0, schema-constrained output, 128 output tokens.
- Desktop 1024x768 (observed in the pristine pilot), browser window 1000x740,
  viewport 980x620; unchanged driver overlay. Geometry changes require a new baseline.
- Train: 256 seeds, including the already-seen pilot seed 42.
- Development: 8 different seeds, two repetitions per candidate (16 episodes).
- Confirmation: 24 private fresh seeds, one repetition per candidate.
- Sealed: 32 further private seeds, one final reporting use, not candidate selection.

All seeds are unique uint32 values, disjoint across splits. The seed-set sizes are
pilot choices, not a power guarantee. They test new starts of one task, not
cross-game generalization. Do not describe the bundled 34 games as evaluated.

## Planning and guarded execution

`fps_bench.evaluation_contract` supports `freeze`, `verify`, and `plan-development`.
Planning writes per-episode seed configurations and stable episode IDs, randomizes
baseline/candidate order within seed/repetition pairs, and supports one baseline,
a two-candidate comparison, or a four-combination factorial schedule. Planning makes
no inference or Fleet calls. Its output explicitly says `execution_status=not_started`.

Example verification against the external anchor:

```bash
python3 -m fps_bench.evaluation_contract verify \
  --contract /home/node/.local/state/gameworld-autoresearch/evaluation/20260913-v2-pilot-1/contract.json \
  --expected-hash f2a1161156fa185ba9ad696b8bfc05369420cdde065ebd9fe7ae367faf38d5f9 \
  --workspace . --upstream /tmp/gameworld-upstream --games /tmp/gameworld-games
```

The episode CLI now accepts `--config` for a registered seed. Frozen runs also
require all of `--contract`, `--contract-sha256`, `--expected-driver-sha256`, and
`--expected-served-model`. It checks evaluator/upstream/game file hashes,
configuration equality except assigned seed/serving identity, upstream revisions,
driver binary identity before and after gameplay, and input screenshot dimensions.
Manifest data includes contract/config hashes. These flags do not perform provider
admission: only the future trusted coordinator may issue paid campaign runs.

Keep the base model revision fixed when varying only driver code. A trained adapter
may have a new serving identity, but its immutable adapter and processor hashes
must be verified by the future serving adapter/coordinator, not inferred from an
arbitrary model name. The worker sees only its assigned private seed when a private
split is dispatched; it must not receive the whole private split file.

## Paired result gate

`paired_decision` is a controller-side pure calculation over **already verified**
episode records; it does not authenticate arbitrary worker summaries or attest
image/model identity. Record ingestion and independent evaluator replay are still
required. Records must match the contract hash, expected seeds/repetitions and
candidate IDs. Duplicate, cross-contract or unexpected records are rejected.
Missing episodes are incomplete; any infrastructure failure blocks a decision and
is not treated as a game loss or silently removed. No automatic retry is specified.

Development can only nominate. Candidate improvement must be at least 0.125 in
absolute task-success rate, with no more than 0.05 increased invalid-action rate
and at most 1.5x median episode latency. Confirmation additionally needs a one-sided
exact sign-test probability <= 0.025 (0.05 divided by two allowed confirmations).
Repeat observations are grouped by seed before the sign test; they are not counted
as independent samples. Ties are omitted from the directional test. This tests
which direction seed-level differences favor; it is not proof that the population
mean effect exceeds 0.125. The reported paired mean-difference Hoeffding interval
is conservative and assumes independent seed clusters. Small samples can remain
inconclusive even with positive point estimates.

The pure function returns `confirmation_pass`, not permission to promote. The
controller now durably limits confirmation leases to two across the campaign,
allows one sealed lease only after a confirmed promotion, binds every private job
to an immutable schedule and records abandoned attempts without retry. Promotion
and rollback are separate atomic transitions with immutable receipts/history.
Sealed/train data remain refused for candidate selection by this function.

## Checks

```bash
python3 -m unittest discover -s scripts -p evaluation_contract_check.py -v
python3 scripts/gameworld_baseline_check.py
```

15 offline contract checks and the 7 existing episode checks pass. They cover split
custody/commitments, source/asset tampering, symlink escape, no-overwrite freezes,
paired/factorial scheduling, guarded configuration rejection before gameplay,
missing/failed/duplicate results, regression gates and inconclusive outcomes.
No synthetic fixture result is presented as a real benchmark result.
