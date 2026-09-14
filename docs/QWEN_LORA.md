# Qwen3-VL multimodal LoRA compatibility slice

Status: CPU architecture update/reload and real 2B processor checks pass.
**The pretrained 2B model has now completed one local CPU compatibility update
on a synthetic blank image. GPU memory has not been measured, and no adapter
has been served or evaluated in Fleet.** This is not the completed
Modal training vertical slice and does not authorize campaign launch.

## Implementation

`fps_bench/qwen_lora.py` supplies:

- `action_batch`: processes one screenshot plus frozen conversation context and
  assistant completion. Tokenizes the prompt and full conversation with identical
  image inputs, verifies an exact prefix, then masks every prompt/image/padding
  token from loss. Overlength examples are refused, not silently truncated.
- `train_and_reload`: 1..32 optimizer steps, batch size one, context at most 4096,
  language-attention q/v LoRA only (rank 8, alpha 16), AdamW and finite clipped
  gradients. Base and visual parameters remain frozen. Requires a measurable
  adapter parameter update before writing a successful result.
- `verify_adapter`: checks a controller-supplied external manifest hash, pinned
  base/processor/data/contract identities, and adapter file digests before reload.
- `run_verified_dataset`: verifies exported training data and constructs batches
  using the pinned pretrained model/processor. Requires CUDA. This is a worker
  primitive, **not** a budget-admitted launch command.

After saving safetensors, the primitive constructs a fresh base, reloads the
adapter and compares image-bearing logits against the pre-save model. It retains
loss/gradient/token records plus versions, hyperparameters and content hashes.
A final successful result is written only after reload comparison passes.

Optional durable telemetry callbacks record each optimizer step. Outbox errors
are summarized by exception type without dumping provider text; they do not
remove training/checkpoint artifacts. The caller must flush/retry export outside
the training loop. This primitive has no provider watchdog or process timeout;
those belong to the still-pending trusted Modal launcher.

Direct dependencies are pinned in the `training` extra: Torch 2.9.0,
Torchvision 0.24.0, Transformers 4.57.1, PEFT 0.17.1, Accelerate 1.10.1 and Pillow
11.3.0. CPU tests use the matching `+cpu` Torch/Torchvision wheels. This does not
establish a CUDA/vLLM compatibility matrix. Both the pretrained base and processor
use revision `89644892e4d85e24eaac8bacfd4f463576704203`; no remote Python model code
is trusted.

## Observed local evidence

`results/runs/qwen-lora-cpu-otel-20260913/rehearsal.json` records two separate tests:

1. Real pinned Qwen3-VL-2B processor, synthetic 1024x768 screenshot: 895 input
   tokens, 11 supervised tokens. The decoded targets contain only the JSON arrow
   action plus assistant end-of-message/newline, not prompt or vision tokens.
2. Tiny randomly initialized Qwen3-VL architecture (321,760 base parameters),
   synthetic image tensor: two optimizer updates, eight updated adapter tensors,
   unchanged base parameters in the unit test and maximum save/reload logit error
   **0.0**. CPU float32 losses were 5.7450103759765625 and 5.74045991897583.

The tiny architecture intentionally uses a different local model identity and
fixture hashes; its adapter cannot qualify as a real frozen-campaign candidate.
The real processor and tiny training test use separate examples. They do not
prove a complete pretrained image-to-loss path or policy improvement.

Four tests exercise real image-bearing forward/backward updates, frozen base
weights, adapter save/reload/tampering, loss masking, bounds, and telemetry failure
retention:

```bash
python -m scripts.qwen_lora_check
```

Reproduce the local rehearsal after caching the pinned processor (no pretrained
weights are downloaded), using an environment with the `training` extra:

```bash
python -m scripts.qwen_lora_rehearsal --output results/runs/new-local-lora-check
```

The rehearsal loads its processor with `local_files_only=True`; an empty cache
fails rather than changing revision. Add `--emit-telemetry` with the existing
`telemetry` extra only when intentionally testing the real OTel endpoint.

## Verified loss telemetry

Campaign `gw-qwen-lora-cpu-20260913`, experiment `tiny-random-cpu` is deliberately
separate from the paid campaign. The actual tiny-model loss callback reached
`otel.cua.ai`. An independent Prometheus query returned the final loss
5.74045991897583; Loki returned both step 1 and step 2 with their measured losses.
Evidence is in `prometheus-verification.json` and `loki-verification.json` under
the rehearsal directory. These are measured architecture-test losses on synthetic
data, not invented scalar smoke values and not full-model training results.

## Remaining launch gates

Budget-bounded Modal image/build/job lifecycle, authenticated dataset ingestion,
new guarded train episodes, a pretrained image-bearing update and GPU memory
measurement, checkpoint serving compatibility, a real Fleet episode, accounting
reconciliation, and failure cleanup are all still required. SFT here is the
approved compatibility warm-start, not a replacement for the planned GRPO/
interactive reward research track.

A subsequent full pretrained CPU compatibility result is documented in
`docs/results/2026-09-14-qwen-pretrained-cpu.md`; it is separate from the tiny
architecture and processor-only checks described above.
