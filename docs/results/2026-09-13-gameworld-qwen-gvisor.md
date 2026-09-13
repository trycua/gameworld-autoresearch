# GameWorld / Qwen / gVisor pilot

## Published environment

This is the GameWorld environment, not the L-platform pilot. The image includes
all 34 upstream game snapshots and the catalog; the implemented Qwen adapter
currently supports 2048 task `01_01` (reach a 32 tile).

- Image: `ghcr.io/trycua/gameworld-autoresearch@sha256:d626893f7bc3c42603557e8ae2d9fdf8ca6ce4c671c1c5958cdba2152674f7ed`.
- Convenience tag: `ghcr.io/trycua/gameworld-autoresearch:gameworld`.
- Source commit: `9460b936b94d12644b82aa281fe08c23d3cb6a68`.
- Successful Actions run: `34776176440`; job: `103774586773`.
- Dockerfile: `image/Dockerfile.gameworld`.
- Workflow: `.github/workflows/gameworld-image.yml`.
- GameWorld revision: `3c26bdab436800fd61ef40543b64ca40d12c7e4a`.
- Game library revision: `55322928fa8bd51cb1719bd3807a32634aa5d3cb`.

Anonymous GHCR access was verified before provisioning. Upstream rights notices
remain in the image; public availability does not remove their restrictions.

## Baked driver and rebuild checks

The image builds this repo's vendored cua-driver 0.22.2 during Docker build,
before publication, and installs it at `/usr/local/bin/cua-driver`. It retains
source at `/opt/gameworld-autoresearch/cua-driver`, the pinned Rust toolchain,
Cargo registry/git dependencies, and `/opt/gameworld-target` release/incremental
artifacts. No initial boot-time compilation is needed.

The published image passed network-disabled CI rebuild checks:

- Fresh-container warm rebuild: **3 seconds**, without rebuilding third-party dependencies.
- Trivial source-edit probe (append a newline to the CLI entrypoint): **1 second**.
- These are cache probes, not a guarantee that substantive edits take one second.
- Initial container revalidation is explained by source timestamp precision
  changing during image serialization, as shown in Cargo fingerprint logs.

Both CI and the live gVisor worker verified four trusted browser arrow-key events
and actual changes to the 2048 board. Seven offline GameWorld checks pass; the
nine existing L-platform protocol checks also pass locally.

## Final pristine-image episode

The final episode ran from **19:12:24 to 19:14:00 UTC on September 13, 2026**.
Its manifest reports `image_source_modified=false`, and the guest source revision
was explicitly checked against the published image artifact before starting.

| Metric | Result |
| --- | --- |
| Protocol | gameworld-2048-cua-qwen-v2 |
| Model | Qwen/Qwen3-VL-2B-Instruct |
| Model revision | 89644892e4d85e24eaac8bacfd4f463576704203 |
| Game / task | 01_2048 / 01_01 |
| Game seed | 42 |
| Steps / valid actions | 60 / 60 |
| Invalid actions | 0 |
| Maximum tile / target | 16 / 32 |
| Native game score | 152 |
| Evaluator progress | 0.5 |
| Task success metric | 0.0 (not passed) |
| Termination | max_steps_exhausted |
| Episode seconds | 94.918 |
| Prompt / completion tokens | 55110 / 600 |

Qwen chose 35 right moves and 25 left moves, never up or down. This is a completed
integration test and an initial policy result, not a successful task solution.
The runtime, inference endpoint, action delivery and evaluator all completed.

Driver binary SHA256:
`37f78e4db6f96e5b36a6dc2912ca6b1539bf938569967aaade99ab5fc81e0ec4`.

## Preserved earlier trials

| Trial | Source state | Invalid actions | Max tile | Game score | Task passed |
| --- | --- | --- | --- | --- | --- |
| Raw v1 output | Unmodified first GameWorld image | 60/60 | 2 | 0 | No |
| Schema v2 validation | Patched first GameWorld image | 0/60 | 8 | 80 | No |
| Final v2 | Unmodified published v2 image | 0/60 | 16 | 152 | No |

Raw v1 responses contained Markdown fences and an invalid `action` value. Protocol
v2 constrains output with a JSON schema while leaving all four directions to the
model. Do not merge v1/v2 results or interpret differences between the two v2
smokes as evidence of a driver/model improvement. These are single episodes;
desktop observations are not bit-for-bit deterministic despite a fixed game seed.
Screenshots include the driver's cursor/session badge, which partly covers the
board. That is a recorded perception condition, not hidden evaluator data.

Other integration fixes were explicit foreground native input for Chromium,
waiting for X11 readiness, and an ephemeral local game-server port with cleanup.
No gameplay inputs use Playwright/CDP; Playwright handles browser lifecycle and
evaluator reads. Qwen receives screenshots and four previous responses only.

## Fleet and artifacts

- Final pool: `qwen-gameworld-v2-20260913-a368b3`; claim: `baseline`.
- Runtime: gVisor; 4 CPU / 16384 MiB; minimum 0 / maximum 20.
- Pool created September 13 at 19:06:20 UTC; six-hour TTL expires approximately
  **September 14, 2026 at 01:06:20 UTC**. The claim had a four-hour TTL.
- The final claim was released after artifacts were retrieved and verified.
- At 19:21:15 UTC, one warm replica still remained despite no claims. Minimum 0 /
  maximum 20 remain configured; zero current replicas was requested explicitly,
  but the autoscaler retained warm capacity. Controller source uses a five-minute
  recent-demand window plus a default five-minute cooldown, so scale-down is not
  immediate. Actual zero capacity was not yet observed at that snapshot.
- Scale-down observation: `results/runs/fleet-gameworld-v2-20260913/scale-down.json`.
- Superseded pool `qwen-gameworld-20260913-18c894` was deleted after confirming it
  had no remaining claims and copying its trial artifacts locally. An attempted
  template update briefly returned an older warm worker; the source-version
  guard rejected and released it. The final run uses a fresh pool instead.
- The temporary debugging claim on the earlier L-platform pool was also released.

Local, gitignored artifacts:

- `results/runs/gameworld-pristine-v2/`: final manifest, summary, screenshots,
  responses, native driver calls, transitions, evaluator output and deployment metadata.
- `results/runs/gameworld-smoke/`: raw v1 trial.
- `results/runs/gameworld-schema-smoke/`: patched v2 validation trial.
- `results/runs/gameworld-image-v2-20260913/fleet-image.json`: published digest.
- Final archive SHA256: `1eb782ed7ac62bf39fe5eebcf885d55cb0097b409a2c43a61c689f3a6d0cace2`.

For subsequent driver edits inside a dedicated claimed worker, use
`bash .auto/measure_gameworld.sh --output results/runs/<experiment>`.
It rebuilds offline, installs the binary atomically, and starts a new isolated
driver daemon for the episode. See `docs/GAMEWORLD_FLEET.md` for setup details.
