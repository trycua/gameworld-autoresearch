#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -x "$ROOT/tools/pi/node_modules/.bin/pi" || ! -f "$ROOT/.pi-local/agent/settings.json" ]]; then
  echo 'Run npm ci --prefix tools/pi --ignore-scripts && node tools/pi/setup.mjs first.' >&2
  exit 1
fi
if [[ -z "${GAMEWORLD_RESEARCH_TOKEN:-}" ]]; then
  echo 'Set GAMEWORLD_RESEARCH_TOKEN to the local authenticated gateway credential; direct LiteLLM access is disabled.' >&2
  exit 1
fi
unset LITELLM_API_KEY LITELLM_MASTER_KEY CUA_CLIENT_ID CUA_CLIENT_SECRET QWEN_API_KEY MODAL_TOKEN_ID MODAL_TOKEN_SECRET
export PI_CODING_AGENT_DIR="$ROOT/.pi-local/agent"
if [[ "${1:-}" == "research" ]]; then
  shift
  exec node "$ROOT/tools/pi/browser-research-cli.mjs" "$@"
fi
exec "$ROOT/tools/pi/node_modules/.bin/pi" "$@"
