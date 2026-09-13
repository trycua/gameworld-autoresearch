#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DISPLAY="${DISPLAY:-:1}"
PYTHON="${QWEN_PYTHON:-python3}"
ARGS=(run --driver "${CUA_DRIVER_BIN:-cua-driver}")
if [ -n "${EPISODES:-}" ]; then ARGS+=(--episodes "$EPISODES"); fi
if [ -n "${QWEN_CONFIG:-}" ]; then ARGS+=(--config "$QWEN_CONFIG"); fi
"$PYTHON" -m fps_bench.qwen_baseline "${ARGS[@]}" "$@"
