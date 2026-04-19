#!/usr/bin/env bash
# 01-setup-rpi.sh — Install system packages and Python dependencies.
# Run this on EACH RPi (and optionally on the laptop for the GW).
set -euo pipefail

echo "[setup] Updating apt and installing system packages..."
sudo apt update
sudo apt install -y python3 python3-pip rsync openssh-client

echo "[setup] Installing Python dependencies..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HW_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
python3 -m pip install --upgrade pip
python3 -m pip install -r "$HW_DIR/requirements.txt"

echo "[setup] Done."
