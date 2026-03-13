#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HW_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$HW_DIR/config/roles.env"

for target in "AS" "NODE"; do
  host_var="${target}_HOST"
  user_var="${target}_USER"
  host="${!host_var}"
  user="${!user_var:-}"
  if [[ -z "$user" ]]; then
    user="pi"
  fi

  echo "[sync] Copying Hardware folder to ${user}@${host}:${REMOTE_BASE_DIR}"
  ssh "${user}@${host}" "mkdir -p ${REMOTE_BASE_DIR}"
  rsync -avz --delete "$HW_DIR/" "${user}@${host}:${REMOTE_BASE_DIR}/${PROJECT_DIR_NAME}/"
done

echo "[sync] Completed."
