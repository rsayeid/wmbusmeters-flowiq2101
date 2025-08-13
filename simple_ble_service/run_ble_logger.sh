#!/usr/bin/env bash
# Helper script: create venv (if missing), install requirements, run interactive BLE logger.
# Usage: ./run_ble_logger.sh [--timeout 15] [--logdir ble_logs]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -q -r simple_ble_service/requirements.txt

python simple_ble_service/interactive_ble_service.py "$@"

# Cleanup note (no background processes should persist)
# To verify manually:
#   ps aux | grep -i bluetooth | grep -v grep
