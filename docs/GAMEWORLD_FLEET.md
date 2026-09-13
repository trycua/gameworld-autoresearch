# GameWorld Qwen / cua-driver research image

The full game environment is `image/Dockerfile.gameworld`, published by
`.github/workflows/gameworld-image.yml` as `ghcr.io/trycua/gameworld-autoresearch:gameworld`.
Use the workflow's `gameworld-fleet-image-<commit>` artifact to provision by digest.
The earlier `Dockerfile.qwen` and its `main` tag remain the L-platform pilot.

The GameWorld image contains the upstream runtime/catalog and all 34 game
snapshots, pinned to commits in the Dockerfile. Upstream rights notices remain
with the snapshots. The first supported Qwen adapter is GameWorld 2048 task
`01_01` (reach a 32 tile); this is not a claim of 34-game agent coverage.

## Driver build and patch loop

The image copies **this repository's** `cua-driver/`, not an upstream replacement,
to `/opt/gameworld-autoresearch/cua-driver`. Docker builds it natively before
publishing and installs it as `/usr/local/bin/cua-driver`.

Unlike the L-platform image's BuildKit-only caches, the GameWorld image retains:

- `/opt/gameworld-target`: release artifacts, dependency fingerprints and
  incremental artifacts (`CARGO_INCREMENTAL=1`).
- `/opt/gameworld-rust/cargo`: downloaded registry and git dependencies.
- `/opt/gameworld-rust/rustup`: the pinned toolchain.
- Build tools and native headers needed for source edits.

Build and runtime use the same source/target paths and Cargo profile. CI runs a
network-disabled rebuild and rejects it if Cargo recompiles anything. There is
no boot-time initial compile. Source edits still compile their affected crates;
new dependencies require an intentional online fetch/image rebuild.

Inside a claimed, dedicated game worker:

```bash
cd /opt/gameworld-autoresearch
# Edit cua-driver/ here, or apply your patch relative to this directory.
git apply --check /tmp/driver.diff
git apply /tmp/driver.diff
source /root/.config/qwen-baseline.env
bash .auto/measure_gameworld.sh --output results/runs/my-experiment
```

The measure script rebuilds offline, installs the new binary atomically, then
starts an isolated driver daemon for the episode. It neither resets source edits
nor reuses an old running daemon. The manifest records source hashes and the
actual driver binary SHA256. Copy artifacts out before releasing the claim.
For a rebuild without an episode: `bash image/rebuild_driver.sh`.

## Episode contract and validation

`configs/qwen-gameworld-baseline.json` fixes the model revision, game/task, seed,
60-step budget, and 900-second timeout. Qwen sees only a desktop screenshot and
its four previous responses. All gameplay input is native cua-driver input;
Playwright launches the visible browser and accesses evaluator state, never
sends gameplay keys/clicks. The unmodified upstream task evaluator scores state.

This is a custom visual cua-driver pilot, not an official GameWorld leaderboard
result or a reproduction of upstream timing/action protocols. 2048 uses 80ms
arrow presses and fresh browser storage with seed 42. Invalid responses consume
a decision without input; infrastructure failures produce a failed manifest,
not a completed zero score. The run stops at a terminal failure instead of
resetting and combining multiple attempts into the one requested episode.

CI checks trusted native arrow events and actual GameWorld state changes without
inference credentials. Live Qwen testing additionally records screenshots,
responses, native driver calls, transitions, upstream evaluator output and
provenance. One episode is only an integration check, not a reliable comparison
for accepting an autoresearch change.
