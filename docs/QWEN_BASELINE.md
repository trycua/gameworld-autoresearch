# Qwen / cua-driver pilot baseline

This is an L-platform **infrastructure pilot**, not a reproduction of the full
GameWorld benchmark. Start with frozen Qwen3-VL-2B-Instruct and the current
vendored cua-driver. Measure the joint visual policy + input stack before
changing either. The existing privileged-state benchmark and its autoresearch
loop are unchanged.

## What is fixed

`configs/qwen-lplatform-baseline.json` defines `lplatform-qwen-visual-v1`:

- Qwen model and tokenizer pinned to Hugging Face revision
  `89644892e4d85e24eaac8bacfd4f463576704203`; vLLM 0.13.0 on one Modal L4.
  Eager execution avoids compilation/graph-capture startup complexity for the pilot.
- Five episodes from the game's fixed default spawn, up to 60 decisions each.
  This is a smoke baseline, not a statistically strong model comparison.
- One current window screenshot, the fixed prompt, and four recent model
  responses. The debug HUD is hidden because it exposes coordinates, progress,
  and event counters. No JavaScript state, oracle route, or privileged evaluator
  output is included in a model request.
- Strict JSON actions: held WASD (120..500 ms), horizontal mouse turn
  (-400..400 px, nonzero), or wait (50..500 ms). No arbitrary tools or code.
  The model does not control the setup focus click. Invalid replies consume a
  decision as a no-op and are recorded, rather than silently retried.
- The existing driver's mouse-turn helper translates relative turns to bounded
  absolute cursor motions, including recentering at screen edges. Both calls
  are logged. This is a driver behavior to measure, not bypass with JavaScript.
- Success is `window.__state.reached`; progress is `window.__progress()`.
  Evaluator state stays separate from policy input. Successful terminal actions
  receive reward 1; other steps receive 0. Progress is diagnostic, not a reward.
- Real-time simulation, no pause or latency compensation. Inference latency is
  recorded; the 900-second episode safety limit is checked between decisions.
  Seeds configure inference only: identical results are not guaranteed.

This visual protocol intentionally differs from the old HUD-visible privileged
benchmark. Do not compare their scores as though they had identical perception.

## 1. Host the frozen model (Modal)

Install the optional tooling with `uv sync --extra infra` and authenticate Modal.
Create a dedicated secret named `gameworld-qwen-api` containing a random
`QWEN_API_KEY` of at least 32 characters. Keep the value out of the repository.
Then deploy:

```bash
uv run --extra infra modal deploy infra/modal_qwen.py
```

Set these variables on the **dedicated game desktop**, not in a committed file:

```bash
export QWEN_BASE_URL='https://<Modal serve endpoint>/v1'
export QWEN_API_KEY='<same key as gameworld-qwen-api>'
```

The endpoint requires a bearer key for inference, permits at most one GPU
container, and scales down after 300 idle seconds. Cold starts download/cache
weights and can take several minutes. Deploying builds an image; calling the
endpoint starts billable GPU work. Stop the Modal app when finished if no further
requests should be accepted. The shared Hugging Face cache volume persists.

To test hosting independently of the desktop/driver (this is **not a game score**):

```bash
python3 scripts/qwen_inference_smoke.py --image /path/to/game-screenshot.png
```

This checks model discovery, an image-to-action response, and rejection of an
unauthenticated request. Keep API keys in a private environment file, not logs
or command-line arguments.

For local vLLM instead, use the same model, revision, tokenizer revision, served
model name, and server arguments from `infra/modal_qwen.py`. The client accepts
HTTP only on localhost; remote endpoints require HTTPS.

## 2. Prepare a dedicated X11 desktop

Use an existing Linux Fleet/VM desktop from this repo's normal workflow. The
runner must execute **inside that desktop**, where the driver can deliver input.
Do not run this on a personal desktop with other applications: the daemon runs
with approvals bypassed and screenshots capture the game window's screen area.

Required: an accessible X11 display and authentication, WebKitGTK/GTK libraries,
`bench_ui`, `cua-bench==0.2.11`, pywebview, Pillow, and a built cua-driver binary.
The repo's guest/image bootstrap already supplies the desktop dependencies.
Add Pillow to that Python environment, or use `uv sync --extra baseline` in an
environment that can also import the system GTK bindings and `bench_ui`.

Build the selected driver before collecting a baseline:

```bash
cd cua-driver/rust
cargo build --release -p cua-driver
cd ../..
export CUA_DRIVER_BIN="${CARGO_TARGET_DIR:-$PWD/cua-driver/rust/target}/release/cua-driver"
export DISPLAY=:1
# Set XAUTHORITY as appropriate for this desktop.
python3 -m fps_bench.qwen_baseline doctor --driver "$CUA_DRIVER_BIN"
```

Use the Python interpreter containing the guest packages (for example,
`.venv/bin/python` instead of `python3`). `doctor` checks imports, X11 screenshot
capture, the binary's presence, and the endpoint's advertised model name.
It does not certify GPU numerics or prove that driver input works.

## 3. Collect the baseline

```bash
# One episode to validate the full path:
EPISODES=1 bash .auto/measure_qwen.sh
# Then the configured five-episode pilot:
bash .auto/measure_qwen.sh
# Optional interpreter and run directory:
QWEN_PYTHON=.venv/bin/python bash .auto/measure_qwen.sh \
  --output results/runs/qwen-frozen-baseline
```

The runner creates a private driver socket, starts/stops its own daemon, and
opens/closes a fresh game window each episode. It never removes an existing
driver socket or kills unrelated game windows. A per-user lock prevents two
instances of this collector from sharing a desktop. Do not run another benchmark
or interact with the desktop concurrently.

Outputs live in `results/runs/` (gitignored). Existing output directories are
refused rather than overwritten:

- `manifest.json`: protocol/config, model revision, source file hashes, Git
  commit/status/diff hash, driver binary hash, environment, and completion status.
- `prompt.txt`: the exact fixed system prompt.
- `driver-server.log`, `driver-calls.jsonl`: daemon output and actual tool calls.
- `episode-NNN/NNN.png`: input screenshots; `NNN-input.json` stores history and
  evaluator state separately; `NNN-response.json` stores full inference responses.
- `episode-NNN/trajectory.jsonl`: actions, invalid responses, screenshot hashes,
  token usage, latency, evaluator transitions, sparse rewards, and success flags.
- `episode-NNN/result.json` and `summary.json`: per-episode outcomes and aggregate
  success/progress. `done` in a trajectory denotes success; budget/timeout
  truncation is reported in the episode's `termination` field.

Model, driver, or environment transport errors abort the run with nonzero status
and a `failed` manifest. Partial artifacts survive but **must not be counted as a
completed baseline**. No success metric is emitted for a failed collection.
Archive the entire directory, not only its summary; these traces are raw rollout
material, not a ready-to-train TRL/verl dataset.

## 4. Start autoresearch only after baseline collection

1. Keep a completed frozen-model/current-driver run as the reference artifact.
2. For driver research, freeze model, prompt, game, action contract and budgets;
   modify only the driver, rebuild it, rerun, and retain the diagnostic privileged
   baseline (`.auto/measure.sh`) to distinguish perception from input failures.
3. For model research, freeze driver and protocol; deploy a candidate under a
   distinct served name/revision and use a copied config via `QWEN_CONFIG`.
   Do not overwrite the baseline config or endpoint while a run is active.
4. Before SFT or GRPO, create separate train/evaluation initial states or tasks.
   Replaying the same fixed L-platform spawn is not held-out evaluation. Export
   only policy-visible observations/actions; never feed `evaluator` fields to the
   policy. TRL/verl training adapters and grouped rollout scheduling are future
   work, not part of this baseline infrastructure.

Offline checks: `python3 scripts/qwen_baseline_check.py`.

## Reference mapping

- [Qwen model card](references/qwen3-vl-2b-instruct.md): frozen visual model.
- [vLLM Qwen recipe](references/vllm-qwen3-vl.md): image-only serving configuration.
- [Modal inference](references/modal-ministral3-inference.md): GPU hosting/cache pattern;
  this pilot deliberately omits snapshot/sleep-mode complexity.
- [GameWorld](references/arxiv-2604.07429v1.md): visual policy / state-verifiable
  evaluator separation. Full GameWorld games and time-control infrastructure are
  not implemented here.
- [TRL](references/modal-grpo-trl.md) / [verl](references/modal-grpo-verl.md): future
  post-training architecture; neither training example is run by this collector.
