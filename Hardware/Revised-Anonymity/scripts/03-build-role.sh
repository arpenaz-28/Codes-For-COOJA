#!/usr/bin/env bash
# 03-build-role.sh — No-op for Python runtime (no compilation needed).
# Kept for workflow parity with the COOJA C-based scheme.
set -euo pipefail

ROLE="${1:-}"
echo "[build] Role '${ROLE}': Python runtime requires no build step. OK."
