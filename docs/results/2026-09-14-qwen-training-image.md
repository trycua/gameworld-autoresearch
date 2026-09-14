# First published offline Qwen training image

GitHub Actions run `34793067743` completed successfully on September 14, 2026.
It built the pinned dependencies and cached public model, ran offline cached
processor/source checks and tiny-model LoRA tests, then published and anonymously
pulled the image. No pretrained GPU training ran in this workflow.

- Source: `1348ac7831a4ad7251b6631f2c34237a09074a66`.
- Image: `ghcr.io/trycua/gameworld-autoresearch@sha256:84e5bd5857c8c8caf78c0abef02dc2fb9119bd4128dca57a189dfdc139c728d2`.
- Retrieved GitHub artifact: `10328931798`.
- All 13 source hashes independently match committed Git objects.
- An anonymous registry token retrieved the manifest; its response digest and
  independently calculated SHA-256 both match the published image digest.
- Local evidence: `results/runs/qwen-training-image-1348ac7/` includes original
  provenance, registry manifest and verification receipt.

This is the first image, not the timestamp-enabled worker added in `bb2326d`.
Build a newer source revision before using the trusted loss-import path; old
loss records do not contain original optimizer timestamps. Modal image import,
pretrained GPU training and memory measurement, adapter serving/evaluation,
all-in budget reconciliation and GPU-loss backend observation remain unverified.
