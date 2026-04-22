#!/usr/bin/env bash
# 02-sync-project.sh — Sync the Zhou folder to both RPis via rsync/scp.
#
# Run from the laptop before starting orchestration.
# Usage: ./scripts/02-sync-project.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HW_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$HW_DIR/config/roles.env"

SN_USER="${SN_USER:-pi}"
USER_USER="${USER_USER:-pi}"

REMOTE_PATH="$REMOTE_BASE_DIR/$PROJECT_DIR_NAME"

echo "[sync] Syncing to SN    ($SN_USER@$SN_HOST:$REMOTE_PATH)"
ssh "$SN_USER@$SN_HOST" "mkdir -p $REMOTE_PATH"
rsync -avz --exclude __pycache__ --exclude "*.pyc" --exclude results/ \
  "$HW_DIR/" "$SN_USER@$SN_HOST:$REMOTE_PATH/"

echo "[sync] Syncing to User  ($USER_USER@$USER_HOST:$REMOTE_PATH)"
ssh "$USER_USER@$USER_HOST" "mkdir -p $REMOTE_PATH"
rsync -avz --exclude __pycache__ --exclude "*.pyc" --exclude results/ \
  "$HW_DIR/" "$USER_USER@$USER_HOST:$REMOTE_PATH/"

echo "[sync] Done."
