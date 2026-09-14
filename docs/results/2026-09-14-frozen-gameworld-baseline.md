# Frozen GameWorld development baseline: September 14, 2026

## Result

The real pretrained Qwen3-VL-2B baseline completed **all 16 frozen development
episodes**: eight disjoint development seeds, two repetitions each, using the
unchanged 2048 tile-32 task and native cua-driver actions. All 960 steps were
replayed through the frozen evaluator on the trusted controller.

| Measurement | Result |
| --- | --- |
| Successful episodes | **0 / 16** |
| Mean steps | 60 (the frozen action limit) |
| Invalid action fraction | 0 |
| Median episode duration | 102.5191 seconds |
| Total episode duration (two lanes overlap) | 1655.1395 seconds |
| Final maximum tile | 7 episodes at 16; 9 episodes at 8 |
| Mean final target progress | 0.359375 |
| Prompt / completion tokens | 881,760 / 9,600 |
| Independent seed clusters | 8 |
| Conservative 95% seed-cluster Hoeffding interval | [0, 0.4801614] |

The uncertainty interval is deliberately conservative for only eight seed
clusters; it does not pretend the two repetitions produce 16 independent seeds.
These are gameplay failures, not invalid actions or infrastructure failures during
episodes. This is a custom screenshot/native-input 2048 pilot, not a published
GameWorld benchmark or an evaluation across all games. No model improvement,
candidate promotion, or autonomous campaign launch is claimed.

## Provenance and retained artifacts

- Frozen contract: `f2a1161156fa185ba9ad696b8bfc05369420cdde065ebd9fe7ae367faf38d5f9`.
- All 16 assignment identities/order match the original frozen development plan.
- Base model: `Qwen/Qwen3-VL-2B-Instruct`, revision
  `89644892e4d85e24eaac8bacfd4f463576704203`; no adapter for this baseline.
- Desktop image:
  `ghcr.io/trycua/gameworld-autoresearch@sha256:d626893f7bc3c42603557e8ae2d9fdf8ca6ce4c671c1c5958cdba2152674f7ed`.
- Driver SHA-256: `37f78e4db6f96e5b36a6dc2912ca6b1539bf938569967aaade99ab5fc81e0ec4`.
- Frozen modules staged separately; no frozen source bytes or driver source changed.
- vLLM 0.13.0 serving image: `im-hmkT3sdePUgwumIXCs7ErB`.
- Report SHA-256: `0d28b7b8a6194622210fc563cf3ab50de850ee78b25453dba817f045778efee2`.
- Custody registration SHA-256:
  `e54c4c96ccb71a73bcb0d1142dd8bf40bd81b0658f1949ebf29180a8ea54caca`.

Full run evidence: `results/runs/frozen-baseline-20260914-b/`.
Read-only external custody:
`/home/node/.local/state/gameworld-autoresearch/evaluation/20260913-v2-pilot-1/baseline-20260914`.
All **2080 retained artifacts** were independently reread and hash-verified after
registration. This is outside candidate repository paths, but remains same-user
filesystem custody, not a separate OS security boundary.

The controller verifies source/config/driver/assignment identity, screenshot and
response consistency, and replays every recorded state and stop decision through
the immutable evaluator. Replay validates recorded-state scoring; it is not an
independent rerun of the browser or protection against adversarial guest tampering.
No confirmation or sealed seeds were used. Development artifacts are not eligible
for the train-only exporter.

## Resources and cleanup

The successful-attempt pool was `gw-baseline-20260914-021804-a994ae`, configured
as gVisor, min 0/max 20, CPU 4/memory 16384 MiB per desktop. Two claims ran at most
two episodes concurrently. The one L4 inference sandbox,
`sb-JpegvI5YiLNIDxfMZMSCU6`, had CPU request/limit 4, memory request/limit 32768 MiB,
and a hard 7200-second lifetime. Its model cache was read-only, outbound CIDR
allowlist empty, and its encrypted endpoint required an attempt-specific key.
An unauthenticated request was independently rejected with HTTP 401.

The first attempt (`results/runs/frozen-baseline-20260914/`) failed before any
episode when serving startup reset a connection. GPU and claims were cleaned up;
a separate reservation and attempt recorded the retry. Readiness now treats
bounded startup transport errors as transient. The retry initially waited for
gVisor CPU capacity. Deleting the owned unused first-attempt pool was followed
by successful scheduling of both retry desktops; no unrelated resources changed.

All episodes completed, but the collector initially exited nonzero during cleanup
because its immediate post-delete claim lookup observed asynchronous deletion.
The original cleanup error remains preserved. Subsequent independent Fleet API
lookups confirmed **both claims absent** (`cleanup-reconciled.json`), and the
collector now polls deletion within a bounded deadline. GPU termination was
confirmed separately with return code 137. Both owned unused pools received delete
requests. No GPU or held claim from these attempts remains active. No post-release
scale-to-zero check was performed, as waived by the user.

These facts establish supervised collection and reconciled cleanup, not the final
killed-controller/watchdog campaign rehearsal.

## Accounting

Each baseline attempt retained a $25 Modal reservation. The canonical campaign
commitment is now **$106.013141**, mostly reservations, not final billed charges.
No holds were refunded or budgets reset. Earlier image/training holds have expired
while awaiting reconciliation, so **new Modal admission is currently refused** by
the ledger; completing already-admitted work did not create another reservation.
Authoritative billing reconciliation is required before further paid dispatch.
Inference tokens in this report are Modal vLLM tokens, not LiteLLM research tokens.

## Telemetry and validation

The corrected exporter uses **one experiment per candidate**, `baseline-qwen-v1`,
not an experiment for each episode. An initial per-episode diagnostic export hit
the existing 12-experiment outbox guard; that legacy outbox and partial evidence
remain intact. A distinct aggregate outbox records the corrected candidate-level
schema. No cardinality limit or budget ledger was changed to bypass the failure.
The corrected exporter emits nothing for incomplete reports.

Aggregate metrics cover success, 16 completed episodes, zero episode infrastructure
failures, mean target progress, and median episode duration. They retain the last
episode's completion timestamp. Backend verification evidence is stored alongside
the run; use the `baseline-qwen-v1` experiment rather than legacy diagnostic labels.

Validation commands:

- `scripts/frozen_baseline_check.py`: 9 artifact/claim-cleanup checks.
- `scripts/frozen_baseline_report_check.py`: 5 completeness/cluster checks.
- `scripts/frozen_baseline_telemetry_check.py`: 4 anchored aggregate-export checks.
- `scripts/frozen_baseline_register_check.py`: 4 external custody checks.
- Full controller replay: 16 real episodes, 960 steps.

## Remaining launch work

The frozen baseline gate now has real evidence. Remaining work includes shared
all-in Modal and LiteLLM accounting/enforcement, authenticated training ingestion
through the production controller, model-only/driver-only comparisons, candidate
isolation and promotion/rollback, private-use leases, deployed supervisor recovery,
and the final bounded campaign rehearsal. Do not start an unattended campaign
from this baseline result alone.

Final backend verification independently matched all five aggregate scalar values
in Prometheus and Loki: completed 16, episode infrastructure failures 0, success
0, progress 0.359375, median duration 102.519131554 seconds. Loki retains the
original completion timestamp `1789353899774873088`; Prometheus uses scrape
sample times. Exact outputs and checked values are in `backend-aggregate.json`,
`loki-aggregate.json`, and `backend-values-verified.json`. A real new-admission
attempt was refused for an expired unreconciled hold, with no ledger mutation
or provider dispatch (`admission-refused.json`).
