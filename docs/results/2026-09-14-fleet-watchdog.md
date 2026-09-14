# Live Fleet watchdog recovery: September 14, 2026

A real claim reached the GameWorld desktop and returned `Linux` from a shell
probe. Its controller persisted a stop request, disconnected without releasing
the claim, and exited. A separate `fps_bench.campaign_watchdog --once` process
then verified ownership, released the claim, observed its absence and recorded
the job as cleaned. A second watchdog process found no remaining work.

- Source: `1e27615ebd22d890dd599f0055b93fc44cd3abd4`.
- Pool: `qwen-gameworld-v2-20260913-a368b3`, gVisor, min 0/max 20, 4 CPU/16384Mi.
- Claim: `gw-903859f46f27c06632032092`, created 00:47:39 UTC with 300-second TTL.
- Cleanup acknowledged: 00:51:14 UTC, before TTL expiry at 00:52:39 UTC.
- Campaign: `fleet-watchdog-20260914`, isolated Fleet-only probe database.
- Evidence: `results/runs/fleet-watchdog-20260914/` contains template preflight,
  claim identity, shell/source receipt, controller-exit snapshot, watchdog pass,
  cleanup receipt, empty replay and final controller snapshot.

Acquisition was initially pending but completed normally. An attempted interrupt
found the controller had already exited; this was **not** a forced-kill test.
The claim deletion was verified before automatic TTL expiry. This establishes
cleanup by an independent process after controller exit, not host-failure
recovery or an always-running supervisor. No model inference, training, benchmark
or new Modal operation occurred. No post-release scale-to-zero check was run.
The full evaluation/research cleanup paths and real GPU failure cleanup remain
launch gates.
