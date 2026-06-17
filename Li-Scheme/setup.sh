#!/bin/sh
# setup.sh — one-time setup for the Li-Scheme COOJA build (run on the apex host).
# Vendors micro-ecc (real ECC, secp256r1) and copies the shared hash/AES sources
# from the LAAKA folder so this scheme is self-contained.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

# 1) micro-ecc (Kenneth MacKay, BSD-2-Clause) — real ECC point multiplication
if [ ! -f uECC.c ]; then
  echo "Fetching micro-ecc..."
  rm -rf micro-ecc
  git clone --depth 1 https://github.com/kmackay/micro-ecc.git micro-ecc
  cp micro-ecc/uECC.c  ./uECC.c
  cp micro-ecc/uECC.h  ./uECC.h
  cp micro-ecc/types.h ./types.h 2>/dev/null || true
  echo "  uECC.c / uECC.h in place."
fi

# 2) shared symmetric primitives (identical to the other schemes)
for f in sha256.c sha256.h aes.c aes.h; do
  [ -f "$f" ] || cp "../LAAKA/$f" "./$f"
done
echo "Setup complete. Now: make TARGET=cooja   (or use run_li_netvar.py)"
