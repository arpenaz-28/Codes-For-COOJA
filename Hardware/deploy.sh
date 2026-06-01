#!/usr/bin/env bash
# deploy.sh — copy Hardware/ scripts to both RPis and install dependencies
#
# Usage: ./deploy.sh <scheme>
#   scheme: proposed | base | zhou
#
# Requires: sshpass   (install with: sudo apt install sshpass)

set -e

SCHEME=${1:-proposed}
AS_USER="Pi"
AS_IP="192.168.1.113"
AS_PASS="raspberrypi"

DEV_USER="Apex"
DEV_IP="192.168.1.132"
DEV_PASS="raspberrypi"

DEPLOY_DIR="~/hw_sim"
HW_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying scheme: $SCHEME ==="

scp_to() {
    local user=$1 ip=$2 pass=$3 src=$4 dst=$5
    sshpass -p "$pass" scp -o StrictHostKeyChecking=no -r "$src" "${user}@${ip}:${dst}"
}

ssh_run() {
    local user=$1 ip=$2 pass=$3 cmd=$4
    sshpass -p "$pass" ssh -o StrictHostKeyChecking=no "${user}@${ip}" "$cmd"
}

# ── Create remote dirs ────────────────────────────────────────────────────────
echo "→ Creating $DEPLOY_DIR on RPis..."
ssh_run "$AS_USER"  "$AS_IP"  "$AS_PASS"  "mkdir -p $DEPLOY_DIR"
ssh_run "$DEV_USER" "$DEV_IP" "$DEV_PASS" "mkdir -p $DEPLOY_DIR"

# ── Copy common files to both ─────────────────────────────────────────────────
echo "→ Copying common.py and config.py..."
for node_user in "$AS_USER" "$DEV_USER"; do
    for node_ip in "$AS_IP" "$DEV_IP"; do
        # only copy to matching pair
        if [ "$node_user" = "$AS_USER" ] && [ "$node_ip" = "$AS_IP" ]; then
            scp_to "$node_user" "$node_ip" "$AS_PASS"  "$HW_DIR/common.py" "$DEPLOY_DIR/"
            scp_to "$node_user" "$node_ip" "$AS_PASS"  "$HW_DIR/config.py" "$DEPLOY_DIR/"
        elif [ "$node_user" = "$DEV_USER" ] && [ "$node_ip" = "$DEV_IP" ]; then
            scp_to "$node_user" "$node_ip" "$DEV_PASS" "$HW_DIR/common.py" "$DEPLOY_DIR/"
            scp_to "$node_user" "$node_ip" "$DEV_PASS" "$HW_DIR/config.py" "$DEPLOY_DIR/"
        fi
    done
done

# ── Copy scheme-specific scripts ──────────────────────────────────────────────
case "$SCHEME" in
    proposed)
        SCHEME_DIR="$HW_DIR/Proposed"
        AS_SCRIPT="as_node.py"
        DEV_SCRIPT="device.py"
        ;;
    base)
        SCHEME_DIR="$HW_DIR/Base-Scheme"
        AS_SCRIPT="as_node.py"
        DEV_SCRIPT="device.py"
        ;;
    zhou)
        SCHEME_DIR="$HW_DIR/Zhou"
        AS_SCRIPT="as_node.py"    # Sensor Node
        DEV_SCRIPT="device.py"    # User device
        ;;
    *)
        echo "Unknown scheme: $SCHEME (use: proposed | base | zhou)"
        exit 1
        ;;
esac

echo "→ Copying $SCHEME scheme scripts..."
scp_to "$AS_USER"  "$AS_IP"  "$AS_PASS"  "$SCHEME_DIR/$AS_SCRIPT"  "$DEPLOY_DIR/"
scp_to "$DEV_USER" "$DEV_IP" "$DEV_PASS" "$SCHEME_DIR/$DEV_SCRIPT" "$DEPLOY_DIR/"

# ── Install dependencies on both RPis ─────────────────────────────────────────
echo "→ Installing pycryptodome on RPis..."
ssh_run "$AS_USER"  "$AS_IP"  "$AS_PASS"  "pip3 install pycryptodome --quiet --break-system-packages 2>/dev/null || pip3 install pycryptodome --quiet"
ssh_run "$DEV_USER" "$DEV_IP" "$DEV_PASS" "pip3 install pycryptodome --quiet --break-system-packages 2>/dev/null || pip3 install pycryptodome --quiet"

echo ""
echo "=== Deploy complete for scheme: $SCHEME ==="
echo ""
echo "Next steps:"
echo ""
echo "  1. Find the PC's IP on the shared network:"
echo "       hostname -I"
echo ""
echo "  2. On RPi 1 (AS/SN, 192.168.1.113):"
echo "       export GW_IP=<PC_IP>"
echo "       cd ~/hw_sim && python3 $AS_SCRIPT"
echo ""
echo "  3. On RPi 2 (Device/User, 192.168.1.132):"
echo "       export GW_IP=<PC_IP>"
echo "       cd ~/hw_sim && python3 $DEV_SCRIPT"
echo ""
if [ "$SCHEME" = "zhou" ]; then
    echo "  Note: Zhou scheme — RPi1 is the Sensor Node, RPi2 is the User device."
    echo ""
fi
