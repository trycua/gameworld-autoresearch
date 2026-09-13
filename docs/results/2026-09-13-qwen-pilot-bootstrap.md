# Qwen L-platform pilot bootstrap - 2026-09-13

## Verified

- Modal app `gameworld-qwen-baseline` is deployed with a single-container L4 cap,
  300-second idle scale-down, vLLM 0.13.0, and eager execution.
- Model/tokenizer: `Qwen/Qwen3-VL-2B-Instruct`, revision
  `89644892e4d85e24eaac8bacfd4f463576704203`.
- API base: `https://cuaai--gameworld-qwen-baseline-serve.modal.run/v1`.
- Dedicated Modal secret: `gameworld-qwen-api`. The key is passed to vLLM via
  `VLLM_API_KEY`, not logged CLI arguments. Local endpoint/key exports are in
  `/home/node/.config/gameworld-autoresearch/qwen.env` (mode 0600), outside Git.
- Browser smoke: the L-platform scene renders at 800x600, the debug HUD has
  computed display `none`, and the evaluator bridge is ready.
- Live inference on that screenshot produced `{"action": "turn", "dx": 100}`.
  Usage: 688 prompt tokens,
  12 completion tokens.
- A request without the bearer key returned HTTP 401.
- Eight offline checks pass, including action validation, authenticated client
  transport, mocked rollout artifacts, evaluator isolation, and failure cleanup.

The live smoke artifact is in
`results/runs/inference-smoke-20260913/result.json`; its screenshot is
`results/runs/qwen-hud-hidden-smoke.png`. These are local, gitignored artifacts.
The smoke script is reusable: `scripts/qwen_inference_smoke.py`.

## Not measured

**No actual cua-driver game episode or baseline success score was collected.**
The smoke sends a browser-rendered screenshot to the real GPU model, but does
not execute its action. Mocked rollout tests are software checks, not scores.
This host has no X11 DISPLAY, built cua-driver, or guest desktop packages.

Next, select/provision the dedicated X11 worker using the repo's existing
Fleet/VM workflow, configure the endpoint/key there, build the current driver,
and follow `docs/QWEN_BASELINE.md`: doctor, one-episode smoke, five-episode
baseline. Archive a completed run before changing the driver or model.

## Startup choices

The first deployment exposed a missing configuration-file mount; the config is
now copied into the Modal image. Eager execution is used to avoid the observed
Torch compilation startup failure. An initial CLI-supplied API key was rotated;
the deployed key is environment-supplied and not written to repository artifacts.
