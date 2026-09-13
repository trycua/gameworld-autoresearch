# Autoresearch: L-platform Qwen visual pilot

Read `docs/QWEN_BASELINE.md` before starting. Do not start optimization until a
completed frozen-model/current-driver baseline has been archived. Never treat
an infrastructure failure, partial run, or mocked run as a measured score.

Run `bash .auto/measure_qwen.sh` inside the dedicated X11 desktop. The host must
have the authenticated Qwen endpoint configured. Default: five episodes. One
episode is a smoke test only. Store every candidate in a separate run directory.

Optimize one axis at a time:
- Driver: keep model revision, prompt, game, budgets and config fixed. Change
  Linux driver input behavior only; rebuild before evaluating. Use the existing
  privileged driver benchmark as an additional diagnostic.
- Model: keep driver binary and visual protocol fixed. Use a separate deployment
  and config identifying the candidate checkpoint. Training is not wired up yet;
  first establish a separate train/eval split instead of training on the pilot
  evaluation spawn.

Primary metric: success fraction. Secondary: mean progress, invalid actions,
falls, decision count, inference latency and token usage. Five episodes are only
an initial signal; repeat a candidate and its control before deciding to keep it.
Never change the evaluator, reveal hidden state/HUD to the policy, or substitute
JavaScript movement for cua-driver actions. Changes to the harness or action
contract require a new protocol version and a fresh baseline.
