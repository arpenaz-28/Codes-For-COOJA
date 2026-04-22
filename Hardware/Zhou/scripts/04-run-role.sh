#!/usr/bin/env bash
# 04-run-role.sh — Launch a single role for Zhou scheme hardware simulation.
#
# Usage:  ./04-run-role.sh <gw_server|gw_router|sn|user>
#
# Run on the correct machine:
#   Laptop  → gw_server  (listens on GW_SERVER_PORT for reg + auth)
#   Laptop  → gw_router  (listens on GW_ROUTER_PORT for token + data)
#   RPi #1  → sn         (sensor node)
#   RPi #2  → user       (user/doctor device)
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <gw_server|gw_router|sn|user>"
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
  gw_server)
    echo "[run] Starting GW_Server on ${GW_BIND}:${GW_SERVER_PORT}"
    exec python3 -u "$NATIVE_DIR/gw_server_hw.py"
    ;;
  gw_router)
    echo "[run] Starting GW_Router on ${GW_BIND}:${GW_ROUTER_PORT}"
    exec python3 -u "$NATIVE_DIR/gw_router_hw.py"
    ;;
  sn)
    echo "[run] Starting Sensor Node (SN_ID=${SN_ID}) on port ${SN_PORT}"
    exec python3 -u "$NATIVE_DIR/sn_hw.py"
    ;;
  user)
    echo "[run] Starting User Device (USER_ID=${USER_ID}) on port ${USER_PORT}"
    exec python3 -u "$NATIVE_DIR/user_hw.py"
    ;;
  *)
    echo "Unknown role: $ROLE"
    echo "Valid roles: gw_server  gw_router  sn  user"
    exit 1
    ;;
esac
