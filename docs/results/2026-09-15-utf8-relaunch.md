# UTF-8 fix and authorized campaign relaunch

Authorization: "okay make fix and re launch".

## Fix

Driver patch generation and validation now preserve UTF-8 bodies, including
unchanged Unicode context from the vendored Rust source. Paths remain strictly
ASCII and allowlisted; binary patches, unsafe paths, invalid UTF-8, file creation,
renames, NULs, and oversized input remain rejected. Diff lines are split on LF,
not Unicode line-separator characters embedded in source text. Pi's patch prompt
now states the same encoding contract.

Sixty-six targeted offline tests pass, including UTF-8 materialization, strict
path rejection, read-only previous-campaign history, accounting forks, operator
rollover, support-file staging, and telemetry. JavaScript syntax checking passes.

## Deployment and lineage

The successful image workflow is `34975099021`, source revision
`45286f223f0ab25603463989ea1776b8cc7b2101`. Native builds, warm offline rebuilds,
and desktop smoke tests passed. Anonymous image access was checked before an
in-place Terraform update of the existing pool to:

`ghcr.io/trycua/gameworld-autoresearch@sha256:e527e7a93548c2b25e437c75fbe2fa58bf833c8dbfe3af6b0f4f63aaacc43ab8`

Runtime, maximum pool capacity 20, and autoscaling configuration are unchanged.
No scale-to-zero observation was required. The local coordinator also includes
read-only previous-history support from `a0dc14b`; that change does not affect
the image's driver build or evaluation implementation.

The old v9 campaign remains stopped. Successor `gameworld-joint-20260915-v10`
uses `campaign-v10.sqlite` and `coordinator-v10` under the existing state root:

`/home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913`

New custody: `/home/node/.local/state/gameworld-autoresearch/evaluation/20260915-utf8-v11`.
Contract SHA256: `f873791fd00fe3583800523b2b9cd959c8bcd0bdb62e3c0cb001f351fac55ddf`.
The episode template, catalog, and public/private task assignments are unchanged.
The catalog still contains 34 games and 170 tasks; development comparisons
remain 136 paired assignments, not a new 2048-only run.

The accounting fork retains $528.640341 of conservative prior commitment against
the original $2,000 Modal cap. Token enforcement remains disabled. Previous
hypotheses and results are read directly from the stopped database into the
existing research history, without rewriting prior outcomes or creating a
second hypothesis registry. Seven previous hypotheses are visible.

The prior unbuilt driver hypothesis is explicitly retested as
`driver-hold-deadline-preservation-v10`. Its last generated diff is reused
byte-for-byte after UTF-8 encoding; no gameplay patch was authored by the
operator. Its original three failed attempts remain preserved in v9. Patch
SHA256: `c25533ad755127ddc924e4d9865c5344217bb6e0989baf014691f876f15ac161`.

## Live validation

The operator started at approximately 13:47 UTC with its gateway and independent
cleanup watchdog. An initial launcher prerequisite error (missing receipt
directory) occurred before any runner or paid job started; the log is retained.
Initialization also rejected an overlong added hypothesis annotation before
registration; the original hypothesis text was retained instead, with lineage
recorded separately in the launch receipt.

Driver build `gw-991f9af2c2867e816a6413c4ee10a763` completed in 39.165 seconds
and passed all six required checks. All 15 exported artifact files were verified
against their receipt, including the exact UTF-8 patch and rebuilt binary. The
build job is cleaned. Candidate binary SHA256:
`f3ad778574077e7f36e427731ca3ec103ae242fe38070773bf33783e91e7c217`.

Qwen serving job `gw-d633db2ffc07ab98dd10e1ba748d326c` then started for the
driver comparison. Its $15 reservation brings conservative Modal commitment
to $543.640341. The operational deadline is September 16, 2026, at 01:44:34 UTC,
under the standing deadline-extension authorization. Desktop concurrency remains
two and GPU concurrency remains one. No benchmark improvement is claimed.

Receipts in successor state: `relaunch.json`, `utf8-driver-build-verified.json`,
`operational-extension.json`, and `operator-process.json`. The live log is
`coordinator-v10/operator.log`; credentials remain in the mode-0600 environment
file outside the repository. The accounting fork receipt is `accounting-fork-v10.json`.

## Large-binary transport and end-to-end verification

The first candidate evaluations exposed a separate staging limit: the rebuilt
driver is 36,839,008 bytes, while a single Fleet staging input is limited to
16 MiB. The operational backend now stages admitted candidate/rollout drivers
in 4 MiB chunks, with a 64 MiB total bound, then verifies the assembled byte
count and SHA256 before exposing the executable. It does not strip, rebuild,
or otherwise alter the approved binary. Ordinary inputs retain their existing
bounds. Transfer receipts live under the existing transport-artifact directory,
outside the evaluator's strict root-file inventory.

Four initial assignment failures are retained: three before the oversized-upload
repair and one during validation of transfer-receipt placement. No failed
assignment was retried, removed, or converted into a successful outcome. The
operator was restarted only at idle episode boundaries; serving stayed live.
The frozen evaluator, rewards, policies, binary identity, and task assignments
were unchanged. All 71 targeted offline tests now pass, including real local
chunk reassembly, mismatched-identity rejection, failed assembly, rollout
identity, and transport-receipt placement.

At 14:12:46 UTC, patched-driver episodes for both 2048 and Flappy Bird had
completed their full 60 steps and were cleaned. Their transfer receipts verify
the exact admitted binary assembled from nine chunks. Independent replay at
14:11:57 verified the six episodes available at that checkpoint and all 360
evaluator steps; logs and metrics were acknowledged with zero export errors.
By the later queue snapshot, eight assignments had completed, four were marked
failed, two were admitted, and 122 remained pending. These are partial campaign
results, not evidence of policy improvement.

The campaign is actively evaluating. Conservative commitment remains
$543.640341 of $2,000, with no LiteLLM token limit. Evidence:
`relaunch-e2e-verified.json` and `independent-replay-20260915-141157.json`.
Use the canonical `operator-process.json` rather than earlier PID records;
the resumed operator PID at this checkpoint is 55745.
