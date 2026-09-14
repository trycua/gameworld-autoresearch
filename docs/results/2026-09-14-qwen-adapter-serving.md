# Real Qwen3-VL adapter serving: September 14, 2026

## Result

The actual pretrained GPU checkpoint from the September 14 training probe
loads as a static LoRA in **vLLM 0.13.0 on an NVIDIA L4**. Both the base model
and adapter return a valid structured GameWorld action for the historical
screenshot. This is a serving compatibility result, not a benchmark or
candidate acceptance decision.

| Measurement | Base | Trained adapter |
| --- | --- | --- |
| Action | `{"action":"key","key":"right"}` | `{"action":"key","key":"right"}` |
| Request duration | 15.6446 seconds | 10.3386 seconds |
| Prompt / completion tokens | 884 / 10 | 884 / 10 |
| Finish reason | stop | stop |
| Reported `right` token log probability | -0.39476049 | -0.48140699 |

The different reported token probabilities provide additional evidence that
requests reached distinct base/adapter paths. They do not demonstrate an
improvement; the trained action's probability is lower in this one observation.
Latency is not a controlled comparison: requests are sequential, base first.
Worker startup plus both requests took 140.104 seconds, excluding sandbox
acquisition/upload and final sandbox termination.

## Provenance and isolation

- Base: `Qwen/Qwen3-VL-2B-Instruct`, revision
  `89644892e4d85e24eaac8bacfd4f463576704203`.
- Adapter manifest SHA-256:
  `fbd5589567a5235c146e87f14951e05eef06b6149c5977aaf67f4fdc54f65612`.
- Existing baseline image reused: `im-hmkT3sdePUgwumIXCs7ErB`, read from
  deployed function `fu-DqjdVABG8sf1lX2EIt7NHw` and checked before dispatch.
- Dedicated app: `gameworld-joint-20260913-training` in `cuaai/main`.
- Sandbox: `sb-JkfpQyhLMzuBfIAHrMDjEa`.
- L4, CPU request/limit 4, memory request/limit 32768 MiB; 900-second lifetime.
- Cached model volume mounted read-only. Network blocked, no external ports,
  no injected secrets or OIDC identity. Localhost server uses a random API key.
- Static `trained=/input/adapter` registration; no dynamic loading enabled.
- Frozen harness generates the screenshot-only request with JSON schema,
  temperature zero and maximum 128 tokens; no frozen source files changed.

The shared cache is not a new independently immutable image/model-cache
attestation. Existing deployed image identity and pinned revision are checked,
but this probe is not production serving admission. The baseline deployment
was not updated and no new serving image was built.

Evidence: `results/runs/qwen-serving-gpu-20260914/` contains the exact dispatched
worker, request, intent, responses with log probabilities, server logs and
termination receipts. The runner verifies adapter file hashes/provenance
before upload; the worker rechecks adapter file hashes and runtime version.
The screenshot is the historical training-compatibility sample, not a held-out
benchmark. No Fleet episode was run by this probe.

## Cleanup and costs

The worker stopped its server, the controller explicitly terminated the
sandbox, and an independent API poll confirmed return code 137. The worker
itself exited zero. Shutdown logs include nanobind leaked-reference warnings;
these did not prevent successful responses or confirmed sandbox termination.
No serving probe GPU remains running.

The canonical ledger retains a **$10 reservation**, not a measured charge.
Total commitment after this probe is **$56.013141**, including previous holds
and historical imported costs. No termination-triggered refund occurred.
Provider billing reconciliation and all-in campaign enforcement remain open.

## Validation and next gates

- `python3 scripts/qwen_serving_probe_check.py`: five CPU checks pass for
  base/adapter requests, missing adapter, corrupt payload, wrong runtime and
  server startup failure/cleanup.
- Actual L4 integration: base and adapter responses valid; cleanup confirmed.
- Still needed: production training-data/controller route, immutable serving
  admission, fresh Fleet episodes and frozen multi-seed evaluation, shared
  budget/token enforcement, supervisor recovery and final campaign rehearsal.
- Unattended autoresearch has **not** been launched.

At 02:01:54 UTC, a fresh Modal hourly report for this dedicated app over
00:00--02:00 returned **$0.18659213** for the 01:00 hour. This is a provider
observation, not a final all-in charge or independent per-probe attribution.
The image import and GPU probes share this app/hour. No ledger settlement or
refund was made from this potentially delayed aggregate. Raw evidence:
`results/runs/modal-training-app-billing-20260914-0201/provider-report.json`.
