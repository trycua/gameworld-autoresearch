#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export DISPLAY="${DISPLAY:-:1}"
bash image/rebuild_driver.sh
"${QWEN_PYTHON:-/opt/gameworld-venv/bin/python}" -m fps_bench.gameworld_baseline "$@"
