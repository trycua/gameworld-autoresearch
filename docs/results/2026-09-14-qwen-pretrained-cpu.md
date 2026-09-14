# Pretrained Qwen3-VL-2B CPU update/reload

On September 14, 2026, the pinned pretrained model completed one local
image-bearing LoRA update and adapter save/reload. This uses a synthetic blank
1024x768 image and a fixed JSON arrow action, **not a GameWorld demonstration or
benchmark episode**. It establishes a pretrained computational compatibility
check, not useful policy learning, GPU fitness, or launch readiness.

Evidence directory: `results/runs/qwen-pretrained-cpu-compatibility/`.

- Base: `Qwen/Qwen3-VL-2B-Instruct`, revision
  `89644892e4d85e24eaac8bacfd4f463576704203`.
- Cached public weights checked against upstream LFS SHA-256. Model/processor
  loading was local-only, with Hugging Face/Transformers offline flags enabled.
- PyTorch 2.9.0+cpu; Transformers 4.57.1; PEFT 0.17.1; base dtype bfloat16.
- One optimizer step, 11 supervised action/end tokens, loss **1.2284879684448242**.
- Pre-clipping gradient norm **14.913079261779785**; clipping limit 1.0.
- **56 adapter parameter tensors changed**. Only language q/v LoRA parameters
  are admitted to the optimizer by the trainer.
- Reloaded into a freshly loaded pretrained base; maximum probe logit error
  **0.0** versus the trained model before saving.
- Recorded training/save/reload phase: **326.8615 seconds**, excluding the
  initial base load. The entire subprocess had a 600-second wall timeout.
- No Modal operations were performed by this probe. No GPU memory measurement.

Adapter manifest SHA-256:
`1b1ad4b5bc1a9252545ceae67ae7e1e496f376c5ff7b1cfe2f43d67e7b6cd4a7`.

The compatibility dataset/contract hashes intentionally do not identify the
frozen campaign dataset/protocol. This adapter must not be registered as a real
campaign candidate or used to claim a benchmark improvement. Its purpose is to
validate image-bearing forward/backward computation and serialization on the
actual pretrained model before a budget-bounded Modal GPU run.

`source-evidence.json` records the local training source and model-cache manifest
hashes. Those source files are still uncommitted; this is not published-image
provenance. The prepared training-image workflow must still build, verify and
publish an image from committed source, followed by actual CUDA/Modal and Fleet
validation.
