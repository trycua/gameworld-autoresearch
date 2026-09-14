# Contributor-authorized Modal app scope

The active pilot path uses an explicit `app-scoped` policy in the existing
`main` environment. It does not require a workspace manager or change any
workspace/environment budget, role or concurrency setting. The optional
restricted-environment policy remains available, but it is not a launch
prerequisite for this selected path.

## Live scope

Created and independently resolved September 14, 2026 using current credentials:

- Workspace: `cuaai`.
- Environment: `main`, ID `en-LdP2zqiTcFtf0kTiiJUDNd`.
- Dedicated app: `gameworld-joint-20260913-training`.
- App ID: `ap-t8r2bbtsLKNVZP86TmksuX`.
- Trusted state: `/home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/modal-app/`.

`intent.json`, `scope.json`, and `verified.json` preserve the requested and
observed identity. Setup created only the empty app record, not a Sandbox,
Function deployment, image build/import, or GPU worker. No privileged
restricted-environment operation was retried after its permission denial.

For another campaign, `scripts/modal_app_setup.py` can create a new dedicated
app with existing contributor-authorized APIs. It refuses existing names and
records intent before creation. An ambiguous response is not automatically
retried. Keep its state private to the trusted controller, not researchers.

## Training admission

Pass the pinned scope explicitly to `ModalTrainingLifecycle.prepare`:

```python
await lifecycle.prepare(
    job_id,
    workspace="cuaai",
    environment="main",
    environment_id="en-LdP2zqiTcFtf0kTiiJUDNd",
    app="gameworld-joint-20260913-training",
    app_id="ap-t8r2bbtsLKNVZP86TmksuX",
    isolation_policy="app-scoped",
    image_id=verified_prebuilt_modal_image_id,
)
```

This is an API example, not a ready campaign launch command. The job must already
be admitted against the canonical campaign ledger with its data/contract hashes
and reservation. Image production/import must receive its own cost accounting.

Before preparation, creation, and training exec, read-back checks the exact
workspace, environment name/ID and app name/ID, with a 60-second freshness limit.
The selected policy and scope are bound into immutable launch identity/tags.
The SDK checks the looked-up app ID again immediately before Sandbox creation.
Unknown modes, changed IDs and attempts to switch an admitted job's scope fail.
There is no automatic downgrade from the restricted-environment mode.

## Controls retained

- Canonical $2,000 Modal ledger: $1,800 normal work plus $200 shutdown reserve;
  the full hold persists through ambiguous submissions and until billing settles.
- Atomic one-training-job admission; hard Sandbox lifetime of at most 1,800s,
  one L40S, CPU limit 4 and memory limit 32GiB.
- Offline training Sandbox: no network, injected secrets, volumes, network
  filesystems or OIDC identity token; no arbitrary researcher command dispatch.
- Verified dataset staging, immutable artifact export, and independent
  cleanup-only watchdog. Cleanup remains callable if scope verification fails.

The lifecycle does not supply a researcher with the controller's Modal
credentials. Deployment must also prevent researcher access to credential files,
controller state, and direct provider APIs; this containment is not yet complete.

## Honest limits

An app groups and identifies resources; it is **not** an RBAC boundary against
other authorized workspace members. This path supplies no provider-side budget
or environment-wide concurrency guarantee. Existing `main` settings and other
apps are unchanged. Controller limits cover controller-admitted work, not jobs
someone submits directly with the same credentials.

The $2,000 campaign limit is unchanged, but complete all-in enforcement still
needs image/import and serving cost envelopes, residual/historical usage,
authoritative settlement, credential containment and failure rehearsal. Do not
claim the local ledger is a provider-enforced hard cutoff or launch unattended
before those gates pass. The previously proposed $25 environment budget was
never configured and is not relied upon here.

Focused tests: `scripts/modal_scope_check.py` verifies identity/policy drift,
resource/network invariants, no privileged environment queries, and cleanup
without refunds after scope-check failure. Existing training, artifact and
watchdog checks also pass. A real GPU run remains a separate gate.
