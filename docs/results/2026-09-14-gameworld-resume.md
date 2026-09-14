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
