# Offline Qwen training image

The first Docker build, offline container checks, GHCR publication and anonymous
access passed in GitHub Actions run `34793067743` on September 14, 2026.
See `docs/results/2026-09-14-qwen-training-image.md` for the digest and independent
source/registry verification. The newer timestamp-enabled source `6a1309c` has
now been imported into Modal and used successfully for a pretrained L40S update,
checkpoint reload and loss telemetry. See
`docs/results/2026-09-14-qwen-pretrained-gpu.md`. This does not establish the full
frozen-data controller/serving/evaluation lifecycle.

## Contents and isolation

`image/Dockerfile.qwen-training` uses a digest-pinned Python 3.12.13 Debian base.
Dependencies are pinned, including transitive CUDA/PyTorch dependencies, with
package hashes in `image/qwen-training/requirements.lock`. Installation requires
those hashes. The existing public GameWorld desktop image is unchanged; this
separate image runs only the GPU training worker, not Fleet desktops/cua-driver.

A Dockerfile-specific deny-by-default build context and explicit COPY file list
include only 13 public source/lock files. No datasets, results, credentials,
private evaluation splits, git metadata or researcher state are copied. Runtime
`/dataset` and `/output` are absent so staging/one-shot checks can create them
exclusively later.

The image caches public Qwen3-VL-2B-Instruct weights and processor at revision
`89644892e4d85e24eaac8bacfd4f463576704203`. The download explicitly disables Hugging
Face credentials, checks upstream revision/license metadata, and verifies LFS
weight digests. Model card, license text, file hashes and source/package
provenance are retained. Runtime Hugging Face/Transformers access is offline-only.

## Workflow

`.github/workflows/qwen-training-image.yml` is manual-only to avoid starting large
image rebuilds for every experimental patch. It:

1. Validates the public source allowlist and pinned inputs.
2. Builds a Linux/amd64 image without pushing it yet.
3. Runs model/source-integrity and cached-processor checks with network disabled.
4. Runs the tiny-model LoRA update/reload checks in a separate network-disabled
   container. This does not establish pretrained CUDA training compatibility.
5. Pushes `ghcr.io/<repository>:qwen-training-sha-<commit>` only after those checks.
6. Logs out of GHCR and pulls by digest to verify anonymous access.
7. Exports the digest and provenance as a workflow artifact.

The tag uses the existing repository container package, whose visibility must
permit anonymous pulls. Nothing in this workflow changes the existing Fleet pool
or baseline inference deployment. Image build time is not Modal GPU time, but
GitHub Actions resource usage still applies; no claim of zero total build cost
is made.

## Current local evidence

- The base-image digest resolves from Docker Hub.
- The pinned model downloaded locally; 11 files and the upstream LFS weight hash
  were verified without Hugging Face credentials.
- The dependency lock resolves from the public PyPI index with hashes.
- `python3 scripts/qwen_training_image_check.py` verifies the 13-file COPY/context
  allowlist and required offline/hash settings.
- `actionlint` accepts the workflow.
- The same model cache supports a complete local pretrained 2B CPU update/reload
  on a synthetic image; see `docs/results/2026-09-14-qwen-pretrained-cpu.md`.
  This is not a Docker or CUDA validation.

The first image has now passed Docker/offline container validation, with its
source hashes checked against the published commit. The newer timestamp-enabled
image and supervised pretrained GPU probe now pass as well. Frozen-data
controller ingestion, adapter serving/evaluation and billing settlement remain
pending. Keep the launch-readiness gate closed.
