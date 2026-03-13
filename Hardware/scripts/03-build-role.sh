#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <gw|as|node>"
  exit 1
fi

ROLE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NATIVE_DIR="$(cd "$SCRIPT_DIR/../native" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[build] python3 is required but not found."
  exit 1
fi

python3 - <<'PY'
import importlib.util
missing = [m for m in ("numpy", "pypuf") if importlib.util.find_spec(m) is None]
if missing:
    raise SystemExit("[build] Missing Python modules: " + ", ".join(missing) + ". Run scripts/01-setup-rpi.sh")
PY

case "$ROLE" in
  gw)
    echo "[build] Validating native GW script syntax."
    python3 -m py_compile "$NATIVE_DIR/common.py" "$NATIVE_DIR/gw_hw.py"
    ;;
  as)
    echo "[build] Validating native AS script syntax."
    python3 -m py_compile "$NATIVE_DIR/common.py" "$NATIVE_DIR/as_hw.py"
    ;;
  node)
    echo "[build] Validating native Node script syntax."
    python3 -m py_compile "$NATIVE_DIR/common.py" "$NATIVE_DIR/node_hw.py"
    ;;
  *)
    echo "Unknown role: $ROLE"
    exit 1
    ;;
esac

echo "[build] Native runtime ready for role: $ROLE"
