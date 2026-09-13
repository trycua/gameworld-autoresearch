# Public GHCR worker for Fleet gVisor

The `Qwen Fleet worker image` GitHub Actions workflow builds
`image/Dockerfile.qwen` for `linux/amd64`. It runs the baseline protocol checks,
compiles the vendored driver, starts the desktop and checks the game renderer,
and only then pushes the tested image to `ghcr.io/trycua/gameworld-autoresearch`.
The worker includes the harness, compiler and driver sources for later research;
it does not contain Fleet, GitHub or model API credentials, or a `.git` directory.

## Publishing

Push relevant source changes to `main`, or run the workflow manually in Actions.
The workflow uses its scoped `GITHUB_TOKEN` with `packages: write`; no registry
password secret needs to be configured. It publishes a `sha-<full-commit>` tag,
a `main` convenience tag for main-branch builds, and a `fleet-image-<commit>`
artifact containing `fleet-image.json` with the immutable image digest.

**The image is intended to be public (approved for this project).** GitHub can
initially create a package as private even for a public repository. On first
publication, use the container package's Settings / Change visibility control
to make it public. The workflow does not pretend a push changes visibility.
The provisioner verifies anonymous GHCR pull access before creating resources.
Fleet's current admission policy does not accept a custom GHCR pull secret, so
private package publishing alone is insufficient.

Package settings:
`https://github.com/orgs/trycua/packages/container/gameworld-autoresearch/settings`

## Provision from a published digest

Set `CUA_CLIENT_ID` and `CUA_CLIENT_SECRET` in the host environment; do not place
them in source files. Download the workflow's `fleet-image.json`, then run:

```bash
IMAGE=$(python3 -c 'import json; print(json.load(open("fleet-image.json"))["image"])')
uv run scripts/qwen_fleet.py provision \
  --runtime gvisor --image "$IMAGE" \
  --state results/runs/fleet-gvisor-pilot
```

This creates a **new** pool, leaving existing VM pools/claims untouched:

- Explicit `runtime=gvisor` through native Fleet template builders.
- Anonymous public image pull, with no `imagePullSecret`.
- `server:8000` and `novnc:6080`, plus a TCP readiness probe.
- Four CPU cores and 16 GiB memory per worker.
- Minimum pool size 0, maximum 20, initial capacity 1.
- Six-hour pool TTL and four-hour claim TTL, measured from creation.

Pool size limits are not a promise of immediately available node capacity.
Releasing/expiring claims allows the demand-based autoscaler to return to zero;
scale-down is not instantaneous. The `claim.json` reconnect reference and pool
metadata are saved under the supplied, gitignored state directory.

## Verify and run

```bash
uv run scripts/qwen_fleet.py exec --state results/runs/fleet-gvisor-pilot \
  --command 'cd /opt/gameworld-autoresearch && /opt/gameworld-venv/bin/python image/smoke_qwen.py'
```

Inject `QWEN_BASE_URL` and `QWEN_API_KEY` into the claimed worker separately, in a
mode-0600 file outside the source directory. Then, from
`/opt/gameworld-autoresearch`, run `bash .auto/measure_qwen.sh` as described in
`docs/QWEN_BASELINE.md`. The image sets `QWEN_PYTHON` to its isolated virtualenv;
the computer-server and desktop retain the base image's system Python.

`image-source.json` records the build's source revision and source hashes.
The collector works without Git and detects changes to those files, so a
modified driver/harness is not silently described as the original image source.
Save the Fleet `pool.json` with the baseline artifacts to retain the image digest
and runtime. Do not combine VM and gVisor results as one baseline.

Retrieve artifacts before releasing a claim. Use `qwen_fleet.py release` when
finished; `delete-pool --confirm` is only for a pool owned by this experiment.
