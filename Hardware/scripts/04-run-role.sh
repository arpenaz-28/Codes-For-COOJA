#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <gw|as|node>"
  exit 1
fi

ROLE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HW_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$HW_DIR/config/roles.env"
NATIVE_DIR="$HW_DIR/native"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[run] python3 is required but not found."
  exit 1
fi

case "$ROLE" in
  gw)
    echo "[run] Starting native GW on ${GW_BIND}:${GW_PORT}"
    exec python3 "$NATIVE_DIR/gw_hw.py"
    ;;
  as)
    echo "[run] Starting native AS on ${AS_BIND}:${AS_PORT}"
    exec python3 "$NATIVE_DIR/as_hw.py"
    ;;
  node)
    echo "[run] Starting native Node (device=${DEVICE_ID})"
    exec python3 "$NATIVE_DIR/node_hw.py"
    ;;
  *)
    echo "Unknown role: $ROLE"
    exit 1
    ;;
esac
