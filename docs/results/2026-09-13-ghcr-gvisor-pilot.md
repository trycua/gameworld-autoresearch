# Public GHCR / gVisor pilot verification

## Deployment

- Source commit: `ba54300591a7aa6bca0772050cbcd1fca2cd73b5`.
- GitHub Actions run: `34772048208`, job `103763293803`, successful.
- Workflow: `.github/workflows/qwen-worker-image.yml`.
- Public image (anonymous pull verified):
  `ghcr.io/trycua/gameworld-autoresearch@sha256:b1bf500206e200d3a87880f563a3d03e690e2ad4efa5f70b817a11fc2f7a80e6`.
- Fleet pool: `qwen-lplatform-20260913-273432`; claim: `baseline`.
- Live template verified as gVisor, 4 CPU, 16384 MiB memory.
- Minimum capacity 0, maximum 20, initial capacity 1.
- Pool created September 13, 2026 at 17:54:09 UTC, with a six-hour pool TTL
  and four-hour claim TTL.
- CI passed nine protocol checks, native driver compilation, and desktop/game
  smoke tests. Live Fleet smoke also passed with cua-driver 0.22.2 and a
  1024x768 desktop.

## One-episode smoke result

The run completed on September 13, 2026 at 18:02:20 UTC using
Qwen/Qwen3-VL-2B-Instruct revision
`89644892e4d85e24eaac8bacfd4f463576704203`, served through Modal on one L4.
The manifest reports the image source unmodified.

| Metric | Result |
| --- | --- |
| Episodes | 1 |
| Success | 0/1 |
| Progress | 0.0 |
| Steps | 60 |
| Invalid actions | 0 |
| Falls | 0 |
| Episode seconds | 151.572 |
| Termination | max_steps |
| Prompt / completion tokens | 43810 / 727 |

The model selected one wait and 59 turns, with no movement commands. Evaluator
telemetry shows yaw changes but unchanged position. This validates model
inference and turn execution through cua-driver, not keyboard movement or task
success. It is a smoke result, **not** the default five-episode baseline and not
sufficient to choose between driver changes and post-training.

The detached launch returned a shell transport error, but the process completed
with exit code 0 and a complete manifest; results were recovered successfully.

## Artifacts and lifecycle

Local, gitignored artifacts:

- `results/runs/gvisor-smoke/`: manifest, summary, screenshots, model responses,
  evaluator transitions, and driver logs.
- `results/runs/fleet-gvisor-20260913/`: pool/claim references and downloaded archive.
- Archive SHA256: `2f344ecc451bbf7d84a9173469e796d0e142e9db5dc45d43da5c0b7fd3aaa0e4`.
- `results/runs/ghcr-build-20260913/fleet-image.json`: immutable image reference.

After copying artifacts locally, both the gVisor `baseline` claim and the older
VM fallback `baseline` claim (pool `qwen-lplatform-20260913-cb2c45`) were released.
Pools were not deleted. Minimum capacity zero allows scale-down; actual zero
capacity was not observed/verified in this report. Pool TTLs remain in effect.
No Fleet, GitHub, or inference credentials are committed or baked into the image.

Next: inspect the visual/action trace, verify keyboard movement separately, and
collect the five-episode baseline before changing the driver or training policy.
