# Supervised frozen baseline collection

This runner collects the existing 16 development assignments without modifying
the frozen source contract. It is not the autonomous campaign controller and
does not authorize researcher access to evaluator custody or provider keys.

## Execution

Use an environment with `cua-sandbox==0.7.0`, `modal==1.5.5`, and `pyyaml==6.0.2`.
Load Fleet credentials through the protected local environment, not command-line
arguments or committed files. Modal uses the existing contributor-authorized
`cuaai/main` dedicated app; workspace-manager access is not required.

```bash
PYTHONPATH=. python scripts/frozen_baseline.py \
  --database /home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/campaign.sqlite \
  --scope /home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/modal-app/scope.json \
  --custody /home/node/.local/state/gameworld-autoresearch/evaluation/20260913-v2-pilot-1 \
  --output results/runs/frozen-baseline-UNIQUE --episodes 16
```

The output must not exist. The canonical ledger admits one $25 Modal reservation
for the batch before provider creation. A failed attempt retains that hold; there
is no automatic retry, refund, or substitution of a different ledger. The runner
records resource identities and claim references before/after dispatch. Its exact
source and frozen evaluator bundle are retained alongside the intent.

The runner creates a public digest-pinned gVisor pool with min 0/max 20 and six-hour
expiry, verifies those settings, and uses at most two claims with 9000-second
expiry. Both desktops must pass frozen source/upstream/game/driver checks before
any GPU starts. Frozen modules are staged in `/tmp/frozen-evaluator`; the retained
cua-driver source/build cache and packaged baseline modules are not patched.

Inference uses the already-tested vLLM 0.13.0 image and pinned base revision on
one L4, CPU request/limit 4, memory request/limit 32768 MiB, hard lifetime 7200s.
The shared model cache is read-only. An encrypted port exposes the API with an
attempt-specific random key, while an empty outbound CIDR allowlist restricts
outbound access. No provider credentials or OIDC identity enter the serving
sandbox. The existing baseline deployment remains unchanged.

Each episode retains the frozen 900-second limit; an outer timeout and controller
poll deadline bound cleanup. It uses the frozen screenshot/action protocol and
exports every regular artifact under size/path bounds. Infrastructure failures
stop collection rather than becoming gameplay failures. Claimed desktops are
released and serving is terminated in `finally`; provider-side TTLs remain a
fallback. No post-release scale-to-zero verification is performed (user waived).

## Independent report

```bash
PYTHONPATH=. python scripts/frozen_baseline_report.py \
  --custody /home/node/.local/state/gameworld-autoresearch/evaluation/20260913-v2-pilot-1 \
  --run results/runs/frozen-baseline-UNIQUE \
  --output results/runs/frozen-baseline-UNIQUE/report.json
```

The controller checks assignment, source/driver/config identity, every screenshot
hash and response, then replays each recorded state through the frozen evaluator
from trusted custody. It checks actions, stopping, final outcomes, and usage.
This replay checks evaluator consistency, not independent physical observation
or deterministic re-execution of the browser. Same-user filesystem custody remains
insufficient for adversarial researcher isolation.

Incomplete collections receive no overall success-rate estimate. A full report
requires exactly the eight development seeds with two repetitions each. The
report gives a conservative 95% Hoeffding interval across eight seed clusters,
not an unjustified interval treating all 16 repeats as independent starts.
No promotion, private confirmation, or sealed evaluation is performed.

## Telemetry

After trusted replay, hash the report and export using
`scripts/frozen_baseline_telemetry.py --report PATH --report-sha256 HASH --outbox PATH`.
Use a Python environment containing the existing telemetry dependencies. The
exporter records one complete candidate-level aggregate (success, median duration,
progress and completion metrics), timestamped at the last episode completion.
Incomplete reports are not exported; episode identity stays in retained artifacts
rather than becoming a high-cardinality experiment label. Verify backend ingestion independently;
HTTP acceptance alone is not dashboard/result verification.

## Remaining launch boundaries

The supervised runner does not implement autonomous admission, resume/retry,
private-use leases, a separately deployed watchdog, or model/driver candidate
promotion. The model cache is shared/read-only rather than newly content-attested.
All-in billing reconciliation and the full upstream LiteLLM usage envelope remain
separate launch gates. A completed baseline alone does not make the campaign ready.

Complete reports can be retained outside candidate workspaces with
`scripts/frozen_baseline_register.py --report PATH --report-sha256 HASH --destination PATH`.
The registrar rereads all artifact hashes and writes a final registration receipt
only after every copy succeeds. See `docs/results/2026-09-14-frozen-gameworld-baseline.md`
for the measured baseline and reconciled cleanup evidence.
