# Research telemetry

## Status

OTLP HTTP/protobuf metrics and logs have been sent to `https://otel.cua.ai` and
verified in Prometheus, Loki and Grafana's read-only datasource API. All current
GameWorld telemetry is **synthetic smoke data**, not training, benchmark or billing
results. Actual coordinator/trainer integration is still required.

The dashboard definition is `infra/grafana/gameworld-autoresearch.json`. Its
publication was denied: the available Grafana identity lacks `dashboards:create`
or `dashboards:write`. The public UI also requires sign-in. The dashboard is **not
published or visually verified**. An authorized Grafana editor can import this
JSON; datasource UIDs `prometheus` and `loki` were verified against the server.
Do not report CUA-1170 complete before the dashboard and real-run integrations work.

## Install and use

Install the `telemetry` extra from `pyproject.toml`: `opentelemetry-proto==1.37.0`
and `protobuf==6.33.6`. `fps_bench.telemetry.ResearchTelemetry` is a controller/worker
utility, not a replacement for the shared campaign ledger.

```python
from fps_bench.telemetry import ResearchTelemetry

telemetry = ResearchTelemetry("/durable/campaign/telemetry.sqlite", "campaign-id")
telemetry.record(
    "candidate-01-train-step-10",
    "gameworld-train",
    {"experiment": "candidate-01", "phase": "train", "objective": "sft"},
    {"gameworld_train_loss": 1.4, "gameworld_train_step": 10},
    step=10,
)
export_status = telemetry.flush()
```

Use actual optimizer-step-aligned loss values in training. The example numbers
are illustrative. Negative policy loss is supported. Never invent unavailable
signals such as KL or reward variance. The trainer/coordinator must call `flush`
periodically (for example every 15 seconds) and at shutdown/checkpoints; no implicit
background thread or process is started. Integrations should isolate telemetry
recording failures from training and preserve cleanup, while retaining a local
warning/error artifact. Export errors are returned without upstream exception text;
record validation and disk failures may raise and must be handled by the caller.

## Durability, replay and privacy

- A SQLite outbox stores every scalar event with its stable ID, timestamp and
  optional optimizer step. Full synchronous transactions survive process restart.
- Reusing an event ID with the same payload is a no-op; a changed payload is an
  error. The source must also deduplicate evaluation attempts before emitting
  aggregate counts. The exporter does not infer which retries are benchmark results.
- Metrics are latest-value **gauges**, including cumulative counts and ledger
  snapshots. Re-exporting a gauge does not increment it. Do not apply `rate()` to
  these totals or interpret a gauge snapshot as complete provider billing.
- Logs retain individual events/steps. Up to 100 pending records are exported per
  flush; acknowledged logs are not intentionally sent again. Lost acknowledgements
  can still duplicate remote log records. This is at-least-once delivery, not a
  promise of exactly-once ingestion; use the stable event ID when replaying analysis.
- OTLP partial-success responses are not treated as full acknowledgements. Network
  failure keeps pending events; old steps stay in the outbox. Retrying gauges sends
  the latest value, not a reconstruction of missed historical scrape points.
- A local advisory lock serializes exporters using the same outbox. Use durable
  local storage and one writer authority per metric series; do not share SQLite
  over a network filesystem or run independent hosts exporting conflicting values
  under the same labels.
- Metric names and attribute keys are allowlisted, labels are bounded identifiers,
  and each outbox allows at most 12 experiments and 512 metric series. Step, seed,
  full hashes, URLs and event IDs are not metric labels. Counts and fractions are
  separate signals. Caller-supplied labels/IDs must not contain secrets.
- No prompt, screenshot, arbitrary error message or free-form text field is
  accepted. Logs carry only scalar values, approved labels, event ID and step.
- Endpoint and optional runtime headers are constructor inputs, never stored in
  events. TLS is required except for localhost tests; redirects are refused.
  Requests use `User-Agent: gameworld-autoresearch-otel/0.1` because the endpoint's
  Cloudflare policy rejected Python's default User-Agent (403/error 1010).

## Verified Prometheus names

The collector removes resource `service.name` from metrics. Use the explicit
campaign/experiment/phase/split/task/objective labels to group results. Loki retains
`service_name`. Verified signal names after collector unit normalization:

| Source metric | Prometheus series | Meaning |
| --- | --- | --- |
| `gameworld_train_loss` | unchanged | Objective-specific loss; can be negative |
| `gameworld_train_step` | unchanged | Optimizer step |
| `gameworld_eval_success_rate` | `gameworld_eval_success_rate_ratio` | Success fraction, with sample counts |
| `gameworld_eval_mean_progress` | `gameworld_eval_mean_progress_ratio` | Secondary progress fraction |
| `gameworld_eval_completed_episodes` | unchanged | Cumulative completed episode count |
| `gameworld_eval_failed_episodes` | unchanged | Cumulative infrastructure failure count |
| `gameworld_modal_spend` | `gameworld_modal_spend_USD` | Reconciled accrued USD, when wired to ledger |
| `gameworld_modal_reserved` | `gameworld_modal_reserved_USD` | Outstanding USD reservations |
| `gameworld_litellm_tokens` | unchanged | Cumulative accounted tokens, when wired to ledger |
| `gameworld_active_claims` | unchanged | Active desktop count |
| `gameworld_active_training_jobs` | unchanged | Active training job count |

`gameworld_eval_seconds` uses seconds and is also supported, but was not included
in the live smoke. Per-step losses are additionally retained in Loki JSON events;
Prometheus scrapes may miss intermediate optimizer steps. Inspect raw events when
plotting loss versus optimizer step, not only wall time.

## Validation

```bash
python -m unittest discover -s scripts -p telemetry_check.py -v
python -m scripts.telemetry_smoke --campaign unique-synthetic-smoke \
  --output results/runs/new-telemetry-smoke
```

The first command is offline. The second sends explicitly synthetic records to
public OTLP ingestion; it does not start inference, training, Fleet claims or an
unattended process. It requires a new output directory. See
`docs/results/2026-09-13-otel-smoke.md` for verified artifact references and limitations.

The controller adapter also supports `gameworld_litellm_reserved_tokens`,
`gameworld_desktop_slots_reserved` and `gameworld_training_slots_reserved` as
unitless gauges. These distinguish held admission capacity from known active
provider resources. They are locally tested but not yet live-smoke verified.

## Offline training artifact import

`fps_bench.training_telemetry.import_training_losses(artifacts, job_id, telemetry)`
imports completed training losses into the controller-owned outbox. It first
calls `TrainingArtifacts.reconcile_export`, which verifies the durable export
receipt, bundle hashes and adapter identity. It never opens the exported worker
SQLite database; that file remains immutable evidence only.

The importer requires the controller campaign identity, cross-checks every loss
row against the hashed completed result, and validates all rows before recording
anything. Labels are reconstructed from the controller job, not supplied by the
worker. Only loss and optimizer-step metrics are admitted. Stable event IDs make
retries idempotent, including after sandbox termination. A subsequent trusted
`telemetry.flush()` performs export; importing never sends network traffic.

Optimizer rows now contain `timestamp_ns`. The outbox preserves that original
time through replay and rejects event-ID reuse with a changed timestamp. Gauge
export selects the newest measurement by event time rather than import order.
Older artifacts lacking original timestamps are rejected rather than assigned
fabricated optimizer times. Rebuild the training image before using this path.

Offline checks: `scripts/training_telemetry_check.py` exercises six importer
cases; `scripts/modal_artifacts_check.py` includes verified export/import after
termination using synthetic provider/checkpoint fixtures. These do not establish
GPU-worker telemetry or a live end-to-end campaign result. Public image source
trust, real GPU staging/training/export and query-side observation remain gates.
