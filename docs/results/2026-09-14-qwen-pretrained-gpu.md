# Pretrained Qwen3-VL GPU training: September 14, 2026

## Verified result

A supervised Modal run trained the actual pinned Qwen3-VL-2B-Instruct on an
NVIDIA L40S, saved the LoRA checkpoint and loaded it into a fresh pretrained
base. This was not a tiny/random model or a CPU run.

| Measurement | Result |
| --- | --- |
| GPU | NVIDIA L40S, capability 8.9 |
| Runtime | Torch 2.9.0+cu128, CUDA 12.8 |
| Optimizer updates | 1 |
| Training loss | 1.7490932941436768 |
| Preclip gradient norm | 10.447525024414062 |
| Supervised tokens | 11 |
| Updated adapter tensors | 56 |
| Train/save/fresh-base reload time | 50.796966361 seconds |
| Peak CUDA allocation | 10,434,157,056 bytes (9.717566 GiB) |
| Maximum reload logit error | 0.0 |
| Exported adapter | Approximately 6.2 MiB safetensors |

The duration excludes sandbox startup, initial base-model loading and image
integrity checks. Loss is the measured training loss for that update, not a
before/after benchmark comparison.

## Data and provenance

The sample is the actual first screenshot/action pair from the earlier
`gameworld-pristine-v2` episode, seed 42: image `000.png`, action `right`.
The image SHA-256 is
`dfc0fc41dde2c748afcedbffb91662839e72a7853ad8c299650d0c683bc32acc`.
Only the screenshot, prompt and recorded response enter the model; evaluator
before/after state is not uploaded. The data predates frozen custody and is
explicitly labeled historical compatibility data, not a frozen campaign dataset.
No benchmark improvement or candidate acceptance is claimed.

- Base revision: `89644892e4d85e24eaac8bacfd4f463576704203`.
- Public image source: `6a1309cc583cdcfb99323e084952ba7e01d5020e`.
- Registry digest: `sha256:0a55fc62e69d7a14ba9bfac9f79ba190bb1886021d27fab3b599357358533f03`.
- Imported Modal image: `im-DDd0N6Q0E4OoWi4ZH3iPhP`.
- Successful sandbox: `sb-5grJrKnnjT6E6zK6zz6a5Z`.
- Successful probe code commit: `35ab379`.
- Worker SHA-256: `9dc7cfe75247195a607678b3b6f0d9bf05baa06223985fd36af1ad6b8496296a`.
- Adapter manifest SHA-256: `fbd5589567a5235c146e87f14951e05eef06b6149c5977aaf67f4fdc54f65612`.

Evidence and exported checkpoint:
`results/runs/qwen-pretrained-gpu-20260914-b/`. The image's source/cache integrity
smoke ran inside the GPU sandbox before training. Controller read-back matched
CI provenance; exported adapter files pass the local hash/provenance verifier.
The retained worker source hashes match the actual dispatched source.

## Failure and cleanup

The first attempt created `/output` before the image-integrity smoke, which
correctly rejected it as an unexpected preexisting experiment directory. This
was a probe setup-order bug, not a model/GPU failure. It was corrected and the
second attempt received a distinct reservation and sandbox name.

Both sandboxes were explicitly terminated. Independent API polling confirmed
return code 137 for the sleeping sandbox entrypoints after termination; the
successful training subprocess itself exited zero. The first attempt's logs,
source and cleanup evidence remain under `results/runs/qwen-pretrained-gpu-20260914/`.
No GPU sandbox from these probes remains running. This verifies this supervised
probe's `finally` cleanup, not a killed-controller or full production watchdog test.

## Real loss telemetry

OTLP metrics and logs were accepted at `otel.cua.ai`. Independent Alertmanager
Prometheus and Loki queries returned the measured loss and optimizer step:

- Campaign: `gameworld-joint-20260913`.
- Experiment: `gpu-compat-20260914-b`.
- Labels: `phase=train`, `split=historical`, `objective=compatibility`.
- Prometheus returned `gameworld_train_loss=1.7490932941436768` and the step series.
- Loki retained optimizer step 1 with original timestamp `1789349510170323407`.

The first immediate Prometheus query was empty before a scrape; a subsequent
15-minute query returned five samples with the exact measured value. Prometheus
samples have scrape timestamps; the original optimizer timestamp is retained in
the local outbox and Loki. Query outputs are saved alongside the checkpoint.

## Accounting and remaining gates

The canonical campaign ledger retains $25 for image import and $10 for each GPU
attempt: **$45 reserved**, not an observed charge. Including previously imported
historical usage, current accounted commitment is $46.013141. Actual new charges
await authoritative billing reconciliation; no holds were refunded after exit.

This supervised probe deliberately uses the low-level training primitive on
historical data. Frozen train-only trajectory ingestion through the production
controller, GPU adapter serving and Fleet evaluation, multi-seed baselines,
shared all-in cost/token enforcement and the complete launch rehearsal remain
required. The unattended campaign is not launched.
