#!/bin/bash
# =============================================================================
# setup_miracl_rpi.sh  —  Install MIRACL Core on Raspberry Pi 4B
# =============================================================================
# Replicates the exact library used by:
#   Kim et al., "A Privacy-Preserving Authentication Scheme Using PUF and
#   Biometrics for IoT-Enabled Smart Cities," Electronics 2025, 14, 1953.
#   [ref 51]: https://github.com/miracl/MIRACL
#
# Run this ONCE on the RPi before building the benchmark:
#   chmod +x setup_miracl_rpi.sh
#   ./setup_miracl_rpi.sh
# =============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "====================================================================="
echo "  MIRACL Core Setup for RPi 4B (ARM Cortex-A72, Ubuntu 20.04 64-bit)"
echo "====================================================================="

# ── 1. System dependencies ────────────────────────────────────────────
echo ""
echo "[1/5] Installing system dependencies..."
sudo apt-get update -q
sudo apt-get install -y git gcc make python3 libssl-dev

# ── 2. Clone MIRACL Core ──────────────────────────────────────────────
echo ""
echo "[2/5] Cloning MIRACL Core from github.com/miracl/core ..."
cd "$SCRIPT_DIR"
if [ -d "miracl_core_src" ]; then
    echo "      Directory exists — pulling latest..."
    cd miracl_core_src && git pull && cd ..
else
    git clone https://github.com/miracl/core.git miracl_core_src
fi

# ── 3. Configure MIRACL Core for ARM64 + NIST P-256 ──────────────────
echo ""
echo "[3/5] Configuring MIRACL Core (NIST P-256, 64-bit ARM)..."
cd "$SCRIPT_DIR/miracl_core_src/c"

# config.py is interactive. We automate it by feeding selections:
#   - '1'  : select 64-bit word size (MR_W64 limbs)
#   - '18' : select NIST256 curve (secp256r1 / P-256)
#   - '0'  : done selecting curves
# NOTE: if the menu numbers differ on your version of MIRACL Core,
#       run `python3 config.py` manually, select '64' word size and
#       'NIST256', then re-run `make` in this directory.
printf "1\n18\n0\n" | python3 config.py || {
    echo ""
    echo "  [!] Automated config failed — running interactive mode."
    echo "      When prompted:"
    echo "        - Select word size: 64"
    echo "        - Select curve: NIST256 (secp256r1)"
    echo "        - Select 0 to finish"
    python3 config.py
}

# ── 4. Build MIRACL Core library ──────────────────────────────────────
echo ""
echo "[4/5] Building MIRACL Core library (core.a)..."
make clean 2>/dev/null || true
make

# ── 5. Copy artefacts to benchmark directory ──────────────────────────
echo ""
echo "[5/5] Copying headers and library to $SCRIPT_DIR/miracl_core/ ..."
mkdir -p "$SCRIPT_DIR/miracl_core"
cp *.h  "$SCRIPT_DIR/miracl_core/"
cp core.a "$SCRIPT_DIR/miracl_core/"

echo ""
echo "====================================================================="
echo "  MIRACL Core installed successfully."
echo "  Headers + library: $SCRIPT_DIR/miracl_core/"
echo ""
echo "  Now build the benchmark:"
echo "    cd $SCRIPT_DIR"
echo "    make"
echo "    ./benchmark_miracl"
echo "====================================================================="
