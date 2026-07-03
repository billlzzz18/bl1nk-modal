#!/usr/bin/env bash
set -euo pipefail

echo "== Building Modal Sandbox Image v2.1 =="
echo ""

# Check if bl1nk-rust image exists, if not build it first
echo "Checking bl1nk-rust image..."
if ! modal image list 2>/dev/null | grep -q "bl1nk-rust"; then
    echo "bl1nk-rust image not found. Building it first..."
    cd /data/data/com.termux/files/home/modal/modal-images
    modal run build_bl1nk_rust.py
else
    echo "bl1nk-rust image found."
fi

echo ""
echo "Building modal-sandbox..."

# Build the sandbox image
modal run /data/data/com.termux/files/home/modal/modal-apps/modal-sandbox/modal_app.py --build

echo ""
echo "Build completed."