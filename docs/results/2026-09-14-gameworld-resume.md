# GameWorld launch recovery, September 14

## Verified recovery

- Accepted `24e9d85` as the intended reconciliation checkpoint.
- Image workflow `34863072601` passed for source `7c465c7`.
- Terraform applied image digest
  `sha256:30859cb6d7d2013a3d2f80ea3a70d43aa5a67ee69d4e18359364e93a2b617ac9`
  in place. No pool replacement or capacity-policy change was required.
- The live Fleet probe verified the pinned source, bundled driver version
  `0.22.2`, unchanged binary identity, and a 3.50-second offline rebuild.
  Claim release was confirmed. This was not a benchmark episode.
- Both completed Modal resources in the 15:00-16:00 UTC window were reconciled
  atomically across training and serving apps. The $35 allocation was retained,
  with $0.003238 observed in that window and no refund or finality claim.
- The failed serving job is cleaned. Protocol fork v3 preserves all historical
  accounting and the $241.013141 total commitment, not $241 of billed usage.
- Accounting telemetry reached `otel.cua.ai`: metrics and logs succeeded,
  with zero pending logs. Cumulative observed usage was $2.156807 and retained
  headroom $238.856334 at export.

## Newly measured startup defect

The previous command used `mkdir ... && nohup ... & echo ...`. Bash backgrounds
the entire AND-list, so the PID-file redirection could execute before directory
creation. A local regression with delayed `mkdir` reproduced exit status 1 and
a missing PID file without allocating a GPU.

Commit `ad95277` completes directory creation synchronously and exits on failure
before backgrounding vLLM. The shell regression and serving/runner tests pass.
Image workflow `34869776324` builds this correction. No new GPU work was admitted
during this recovery.

The immutable `20260914-7c465c7-v3` contract has the correct 68/34/34/34 task
split, with all 34 games in every split, but is superseded by this controller
source change. Do not overwrite it or launch against it. Publish the corrected
image, apply its digest, and freeze a new contract before continuing.

## Remaining launch gates

Run a bounded non-2048 baseline episode, a reversible driver candidate, and a
real authenticated model-training slice. Keep all failures as evidence, verify
cleanup and telemetry, reconcile billing, and then launch the measured joint
campaign. No additional unchanged 2048 episode or speculative game-control
patch is warranted.

Durable receipts are under
`/home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/`:
`billing/v2-completed-20260914-1632`, `campaign-v3-fork.json`, and
`vertical-slices/fleet-7c465c7-v3`.

## Subsequent live validation

Workflow `34869776324` passed. Terraform deployed the corrected image
`sha256:b399c4f404b2b67abd70bed2e88343f606dbae1d53d79edc687757d8eb094000`.
The new immutable contract is `20260914-ad95277-v4`, anchored at
`c5406b5d14dcd276b7f2a02e431eb79c6b9b7b1dc6981b8e6d5bec58715665cd`.

Source Qwen serving became healthy in two controller-owned GPU launches. The
first validation helper incorrectly submitted catalog `id` rather than the
normalized `task_id`; admission rejected it before any evaluation dispatch.
The helper was corrected to use `split_units` and admit the assignment before
GPU allocation. This was a helper defect, not a model or evaluator failure.

The next attempt dispatched the non-2048 development task
`02_another-gentlemans-adventure--02_03`, but the synchronous Fleet shell request
failed with `SdkError.Transport: ReadTimeout`. No complete benchmark artifact
was exported. Claim release and both GPU terminations were confirmed, with
successful cleanup telemetry exports. These attempts are not scored results.

Commit `c3c09b8` replaces the long HTTP shell call with a detached, remotely
time-bounded worker and short completion probes. Atomic completion receipts
retain the worker exit code; worker logs are included in exported artifacts.
Local subprocess tests cover launch latency, nonzero worker exit, enforced
timeout, and launch failure. Fleet and runner tests pass. Workflow
`34872017224` builds the corrected image. This source change supersedes the
v4 contract; retain it rather than modifying its trust anchor.

At 17:00 UTC the canonical automatic reconciler closed both serving jobs for
the 16:00-17:00 window: $0.321535 observed, $20 retained, no refund. All v3 jobs
are cleaned. Total inherited commitment is now $261.013141, leaving
$1,538.986859 normal allowance plus the untouched $200 cleanup reserve.

Next: publish/apply the transport-fix image, fork terminal v3 accounting,
freeze a new contract, and repeat the bounded non-2048 vertical slice. The
driver/model validation and full joint campaign remain uncompleted.

## Fleet shell detachment and research request bounds

Image `c3c09b8` was published by workflow `34872017224` and deployed at
`sha256:d4ef8af68b678ed96206e849be6886548dae55c4d9eb8dd4f4b0d6f0f43befba`.
The terminal v3 ledger was forked to `campaign-v4.sqlite` without resetting
allowance. Custody `20260914-c3c09b8-v5` has anchor
`33797460769057756bc9001118e7985315f807eed19fafbd48971913052ac37b`.

The v6 source-serving endpoint became ready, but the computer-server shell
rejected the background shell launch with an empty remote error. The episode
did not export a scored result. Its claim was released and sandbox
`sb-QH5rNEZxd1sMFFHErjcC9k` was terminated at 17:17:24 UTC. Its $10 reservation
remains billing-pending until the 17:00-18:00 UTC billing window closes.

Two GPU-free Fleet probes isolated and verified the correction:

- `transport-only-v1`: `nohup sleep 30 ... &` failed through the real shell;
  Python `Popen` with a new session and detached descriptors returned correctly.
- `transport-only-v2`: the complete Python-launched worker slept 20 seconds,
  exported its expected exit code 7 and log, and released the claim. No Qwen
  calls or benchmark scores were generated by these transport probes.

Commit `0ab89eb` applies that measured fix. Commit `97ddb4b` adds a 20-second
computer-server HTTP smoke check to image publication, rather than relying on
local subprocess tests alone.

A separate prelaunch check found the 64 KiB research request cap could not carry
the actual 123,450-byte Linux input source. Commit `366d0fe` raises the bounded
text envelope to 1 MiB and increases the per-request token allocation (including
two retries) to 3,342,336. Authenticated actual usage still settles each call;
the cumulative campaign limit remains 1 billion tokens. The real-source,
oversized-request, gateway and research-worker checks pass.

Workflow `34874772576` builds the combined fixes. The latest source changes
supersede the v5 contract. Do not launch further research or benchmark jobs
against it. Reconcile v4 after 18:00 UTC, fork its terminal accounting, deploy
the combined image, and freeze a new protocol. Current commitment is
$271.013141; no new training job has been dispatched.

The metered research relay passed its four-model preflight without an inference
request. It must be restarted against the next canonical ledger before launch.
The bounded baseline helper is `/tmp/gameworld-live-baseline-v6.py`; retain the
normalized `split_units` assignments when adapting its custody and campaign IDs.
