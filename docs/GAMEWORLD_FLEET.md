# GameWorld Qwen / cua-driver research image

The full game environment is `image/Dockerfile.gameworld`, published by
`.github/workflows/gameworld-image.yml` as `ghcr.io/trycua/gameworld-autoresearch:gameworld`.
Use the workflow's `gameworld-fleet-image-<commit>` artifact to provision by digest.

Production campaign capacity is the Terraform-managed `gameworld-autoresearch`
pool in `infra/fleet/main.tf`. Campaign code claims from that stable pool and
must not create, reconcile, resize, or delete the pool through the SDK.
Update the pinned digest in that Terraform resource, review the plan against the
private state path documented in `infra/fleet/README.md`, and apply it there.
The public GHCR image requires `image_pull_secret = ""` and a provider release
containing the anonymous-pull serialization fix; registry version `0.2.0` does
not contain that fix.
The earlier `Dockerfile.qwen` and its `main` tag remain the L-platform pilot.

The GameWorld image contains the upstream runtime/catalog and all 34 game
snapshots, pinned to commits in the Dockerfile. Upstream rights notices remain
with the snapshots. The upstream library is research/education-only and includes
third-party rights restrictions; public image availability does not grant
commercial-use rights. The first supported Qwen adapter is GameWorld 2048 task
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
network-disabled warm rebuild and rejects third-party dependency compilation
or a warm rebuild taking 60 seconds or more. A fresh-container check can still
revalidate local workspace crates (3.3 seconds observed in the first CI run).
It then edits the driver entrypoint in a disposable container, measures the
source-edit rebuild, and rejects dependency recompilation. There is
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
60-step budget, and 900-second timeout. Protocol v2 requests server-side JSON
schema-constrained decoding: exactly one of four arrow actions, with no extra
fields. The model still chooses the direction. Raw protocol v1 produced malformed
JSON actions; those results must be kept separate from v2. Qwen sees only a desktop screenshot and
its four previous responses. All gameplay input is native cua-driver input;
Playwright launches the visible browser and accesses evaluator state, never
sends gameplay keys/clicks. The unmodified upstream task evaluator scores state.

This is a custom visual cua-driver pilot, not an official GameWorld leaderboard
result or a reproduction of upstream timing/action protocols. 2048 uses 80ms
arrow presses with explicit `delivery_mode=foreground` (native XTest), and
fresh browser storage with seed 42. The game server binds an ephemeral local
port. The default background input path did not deliver Chromium key events
in the first integration test; the driver binary itself is not patched for this. Invalid responses consume
a decision without input; infrastructure failures produce a failed manifest,
not a completed zero score. The run stops at a terminal failure instead of
resetting and combining multiple attempts into the one requested episode.

CI checks trusted native arrow events and actual GameWorld state changes without
inference credentials. Live Qwen testing additionally records screenshots,
responses, native driver calls, transitions, upstream evaluator output and
provenance. One episode is only an integration check, not a reliable comparison
for accepting an autoresearch change.
