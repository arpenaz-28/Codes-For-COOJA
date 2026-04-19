#!/usr/bin/env bash
# 04-run-role.sh — Start the specified role on this machine.
#
# Usage: ./04-run-role.sh <gw|as|node>
#
# The script sources roles.env so the Python programs can locate it
# via their own cfg_path() (they read config/roles.env relative to
# their own location — this script just starts them).
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <gw|as|node>"
  exit 1
fi

ROLE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HW_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
NATIVE_DIR="$HW_DIR/native"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[run] python3 is required but not found."
  exit 1
fi

case "$ROLE" in
  gw)
    echo "[run] Starting GW (laptop)  — listens on port 5683"
    exec python3 "$NATIVE_DIR/gw_hw.py"
    ;;
  as)
    echo "[run] Starting AS (RPi #1)  — listens on port 5684"
    exec python3 "$NATIVE_DIR/as_hw.py"
    ;;
  node)
    echo "[run] Starting Device Node (RPi #2)  — talks to AS + GW"
    exec python3 "$NATIVE_DIR/node_hw.py"
    ;;
  *)
    echo "Unknown role: $ROLE  (expected: gw | as | node)"
    exit 1
    ;;
esac
