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

## First complete non-2048 episode and measured launch adjustments

Workflow `34874772576` passed its actual computer-server HTTP smoke test and
published source `366d0fe` as
`sha256:03b7f119165360a2c2657a9fde0fa6115d25d6473146e61f426567df12d1ef30`.
Terraform deployed it, and custody `20260914-366d0fe-v6` was frozen with anchor
`54d23c8ee2a53f9419860b064d9dbaa98459b184ebc6cbceb69ce4eb5cf6dc34`.
The broad prelaunch regression passed 92 Python tests (one further test skipped)
and four JavaScript tests.

At 18:00 UTC the v4 serving obligation was reconciled: $0.189836 observed and
$10 retained. Accounting was forked to `campaign-v5.sqlite` with commitment
unchanged at $271.013141. An initial Fleet preflight returned HTTP 503 before
any job admission; the next read-only preflight recovered.

The v8 episode then completed the registered development task
`02_another-gentlemans-adventure--02_03` in 103.104659 seconds:

- 60 steps: 37 `move_right`, 21 `move_left`, one `jump`, one `wait`.
- Zero invalid actions and zero driver errors.
- Task success false, progress zero. This is measured failure evidence, not an
  improvement or promotion.
- 63,662 prompt tokens and 718 completion tokens from local Qwen serving.

The original host verifier rejected the wrapper's extra root-level `worker.log`.
Commit `ab7a367` moves transport-only logs into `transport/`, outside the frozen
scientific artifact inventory, and tests the full executor/verifier combination.
The evaluator itself is unchanged. An immutable replay projection of the captured
bundle moved only that log, retained all scientific hashes, and passed the exact
original verifier. The original controller result was not rewritten. No GPU was
needed for replay. Verified-replay metrics/logs reached OTel with zero pending logs.
Evidence: `vertical-slices/baseline-non2048-v8/replay/verification.json`.

The first real Pi browser-research attempt consumed 105,931 authenticated tokens
and stopped at its 100,000-token workflow budget before completing synthesis.
There is no registered proposal from that attempt. Commit `e00c215` raises that
bounded workflow allowance to 500,000; the shared one-billion-token limit remains.

The observed 103-second episode also makes a one-hour source-serving lease too
short for a simple 136-episode, two-desktop projection (about 117 minutes before
startup/contention). Commit `64d0fc4` sets a three-hour maximum and $15 minimum
serving reservation, with refreshed quote validation. The six-hour campaign,
two-desktop/one-training-job concurrency, $1,800 normal allowance, $200 cleanup
reserve, and $2,000 total cap are unchanged. All focused policy/coordinator/SFT/
serving/runner/research/billing/evaluation checks passed.

Builds for `64d0fc4`:
- Fleet: `34880037813`.
- Authenticated offline training image: `34880036922` (must import and pin it;
  the older training image embeds the older strict serving policy).

All claims and the serving sandbox are cleaned up. The v5 $10 serving obligation
is billing-pending for 18:00-19:00 UTC; a one-shot trusted reconciliation process
waits until 19:00:05 UTC (`/tmp/gameworld-reconcile-v5-at-1900.py`, output
`/tmp/gameworld-v5-billing-1900.log`). Current commitment is $281.013141 and
105,931 LiteLLM tokens. The completed slice watchdog and old-protocol research
relay are stopped. The source/policy changes supersede v6 custody; retain it.

Next: reconcile/fork v5 accounting, deploy/freeze the latest Fleet image, import
the current training image, and run the driver/model validation slices before
the bounded joint campaign. Do not spend on another unchanged standalone
baseline just to re-prove the captured episode; use the first paired parent
evaluation to verify the corrected live artifact packaging.

## Latest deployment and train-only source custody

Fleet workflow `34881632108` passed for source `6f08a22` and published
`sha256:447fdc533f1cdc9d0818898736a19dfb29a6cf77e457bb220a9de4cc4dd88b4b`.
Terraform applied this image in place, preserving the gVisor pool limits.
New custody `20260914-6f08a22-v7` verified against the workspace and private
splits with anchor
`9de64674bde801aced0b3588c1a87df14d610ff8c06504a9f4dfb4cb7279f15e`.

The baseline SFT exporter produced 18 train-only observations across nine games
in `sft-sources-v1`, dataset hash
`908095dc3f6eeeb02f5053648fcee6c25a5b4bfe0b6a873e8f997866d8a170cd`.
These are positive-progress base-policy self-imitation samples, not expert
demonstrations or evidence that an action caused progress. The catalog is ready
for the next coordinator, but GPU training has not yet validated this dataset.

The attempted current-image Modal import was rejected during ledger admission
because the completed v8 serving reservation had expired unreconciled. The
transaction rolled back before provider submission; there is no new import or
$25 hold. Keep the scheduled 19:00:05 UTC serving reconciliation: no image
import overlaps its window. Import the current training image only after that
reconciliation, and retain its subsequent billing obligation. Current imported
images still embed the superseded policy and must not launch new training.

## Real GPU SFT verification and research admission stop

At 19:00 UTC the v8 serving obligation reconciled: $0.264578 observed, $10
allocation retained without refund. Accounting forked to `campaign-v6.sqlite`,
campaign `gameworld-joint-20260914-v6`, preserving the $281.013141 commitment.
The current training image imported successfully as `im-gxEgf8dilLHjmc9TVBT7DF`.

Job `sft-authenticated-v6` then trained the authenticated dataset on CUDA:
two optimizer steps, losses 0.1534113 and 0.1759792, 112 updated parameter
tensors, 71.0845 seconds, and zero maximum logit error after adapter reload.
Peak CUDA allocation was 12,137,973,760 bytes. This validates the training and
artifact path only; it does not establish benchmark improvement. Adapter hash:
`f2bf639fbb443c0039de0eb55cc80f4542bfb08fc666a8bf0857f20f233012f0`.
Both scalar/log export and the copied immutable training telemetry projection
reached OTel with no errors and zero pending logs. The original artifact bundle
is unchanged. Evidence is under `vertical-slices/sft-authenticated-v6` and
`coordinator-v6/modal/sft-authenticated-v6` in the campaign state directory.

The first new Pi planning request did not produce verifiable upstream usage.
The gateway froze admission and retained all 3,342,336 reserved tokens for
`litellm:c5649cb9-aa93-4873-a203-39e8e1a8f636`. No proposal or driver patch was
registered. Authenticated spend-log queries returned no matching rows; that
does not prove zero usage. The old gateway did not persist its exception type,
HTTP status, or response call identity, so the underlying failure is not yet
established. New diagnostics retain those safe fields and failure phase without
logging credentials, request/response bodies, or exception messages. They do
not release holds, retry ambiguous requests, or unfreeze the campaign.

A planned Breakout grouped-rollout/GRPO validation stopped at admission before
any serving job or claim was created. SFT sandbox `sb-UaVZerzVrcdj34avSDLtaC`
terminated with a durable receipt; read-only checks found no running sandboxes
in either dedicated Modal app. The research relay and watchdog were stopped
after those checks. No full campaign has launched.

Current Modal commitment is $311.013141, including the $25 image-import and
$5 SFT holds. Trusted reconciliation of those two resources is scheduled for
20:00:05 UTC via `/tmp/gameworld-v6-billing-2000.py`, logging to
`/tmp/gameworld-v6-billing-2000.log`. It leaves the unresolved LiteLLM freeze
intact. The gateway diagnostics change supersedes the latest source contract;
retain its evidence and resolve the authenticated usage obligation before
freezing another protocol or admitting research. Do not reset/fork away the
freeze, discard the token hold, or repeat the completed SFT smoke test.
