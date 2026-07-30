#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
CONDA_ENV="${HAVC_CONDA_ENV:-havc-agent}"
if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  eval "$(conda shell.bash hook)"
  conda activate "$CONDA_ENV"
fi
exec python -m havc_agent.app_cli "$@"
