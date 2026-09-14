# SearXNG research pilot

Private Kubernetes deployment in the existing `gvisor-dev` namespace, tested on
September 13, 2026. See `docs/results/2026-09-13-searxng-research-pilot.md` for the
query results and limitations. The custom pi `/hybrid-research` command now uses this JSON endpoint; upstream
`/deep-research` still uses its original toolset. See `docs/BROWSER_RESEARCH.md`.

## Deploy

The service-account used for this pilot can deploy in `gvisor-dev` but cannot
create workloads in arbitrary new namespaces. No namespace or RBAC resources are
managed here. All workload names use `gameworld-searxng` to avoid collisions.

Create the secret once, skipping this command if it already exists:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32), end="")' | \
  kubectl -n gvisor-dev create secret generic gameworld-searxng-secret \
  --from-file=secret=/dev/stdin
kubectl apply -k infra/searxng
kubectl -n gvisor-dev rollout status deployment/gameworld-searxng --timeout=180s
```

The image is pinned by digest; settings changes generate a new ConfigMap name and
trigger a rollout. gVisor is required by this namespace's admission policy. The
pod runs as UID/GID 977, with no service-account token, dropped capabilities,
read-only root filesystem and bounded ephemeral cache/tmp volumes.

One replica requests 100m CPU and 256Mi memory, with limits of one CPU and 1Gi.
There is no Redis/Valkey dependency: rate limiting and image proxying are disabled
for this private pilot. This deployment is not autoscaled and has no automatic TTL.

## Use and test

From a pod in `gvisor-dev`, including this workspace:

```bash
curl -f http://gameworld-searxng.gvisor-dev.svc.cluster.local:8080/healthz
curl -fsS -G http://gameworld-searxng.gvisor-dev.svc.cluster.local:8080/search \
  --data-urlencode 'q=Qwen3 VL LoRA multimodal GRPO' \
  --data-urlencode 'format=json' \
  --data-urlencode 'engines=google'
python3 scripts/searxng_research_check.py \
  --repeat 2 --pause 5 --output results/runs/searxng-new-probe
python3 scripts/searxng_research_unit_check.py
```

Use `engines=semantic scholar` for academic queries. Read `unresponsive_engines`
as well as `results`: HTTP 200 is not proof of useful or complete retrieval.
The checked-in engine list is Google plus Semantic Scholar, not the original
all-engine experiment. The test defaults match the deployed configuration.

There is no public ingress or authentication. NetworkPolicy permits application
ingress from this namespace and egress to public HTTP(S) plus kube-system DNS;
private IPv4 ranges and link-local metadata addresses are excluded from public
egress. Policy manifests are applied, but packet-level isolation was not audited.
Do not expose this unauthenticated, limiter-disabled pilot publicly.

`kubectl port-forward` failed against this gVisor pod's host-netns loopback while
ClusterIP and pod-local requests worked. Use cluster DNS from this workspace;
from an external operator machine, `kubectl exec` into the deployment can issue
requests using `/usr/local/searxng/.venv/bin/python`. Do not rely on port-forward
until that runtime issue is resolved.

## Lifecycle

The pilot is left running for follow-up testing. Pause it without removing config:

```bash
kubectl -n gvisor-dev scale deployment/gameworld-searxng --replicas=0
```

Resume with `kubectl apply -k infra/searxng`. Remove only this pilot's resources:

```bash
kubectl delete -k infra/searxng
kubectl -n gvisor-dev delete secret gameworld-searxng-secret
```

Older generated ConfigMaps can remain after rollouts; inspect names beginning
`gameworld-searxng-settings-` and delete only those not referenced by retained
ReplicaSets when cleanup is desired. Never delete the shared `gvisor-dev` namespace.
