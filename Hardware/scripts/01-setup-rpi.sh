#!/usr/bin/env bash
set -euo pipefail

echo "[setup] Updating apt and installing toolchain..."
sudo apt update
sudo apt install -y build-essential cmake git pkg-config python3 python3-pip rsync openssh-client

echo "[setup] Optional CoAP packages (if available on distro)..."
sudo apt install -y libcoap3 libcoap3-dev || true

echo "[setup] Installing Python dependencies for native runtime..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HW_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
python3 -m pip install --upgrade pip
python3 -m pip install -r "$HW_DIR/requirements.txt"

echo "[setup] Done."
