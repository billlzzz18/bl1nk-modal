#!/usr/bin/env bash
set -euo pipefail

# Resolve paths relative to this script's location, not a hardcoded clone
# path — works on any OS (Linux, macOS, Termux, WSL) regardless of where
# the repo lives, matching the SCRIPT_DIR pattern already used in
# modal-apps/modal-agy/run.sh.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SANDBOX_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SANDBOX_DIR/../.." && pwd)"
IMAGES_DIR="$REPO_ROOT/modal-images"

echo "== Building Modal Sandbox Image v2.1 =="
echo ""

# Check if bl1nk-rust image exists, if not build it first
echo "Checking bl1nk-rust image..."
if ! modal image list 2>/dev/null | grep -q "bl1nk-rust"; then
    echo "bl1nk-rust image not found. Building it first..."
    (cd "$IMAGES_DIR" && modal run build_bl1nk_rust.py)
else
    echo "bl1nk-rust image found."
fi

echo ""
echo "Building modal-sandbox..."

# Build the sandbox image
modal run "$SANDBOX_DIR/modal_app.py" --build

echo ""
echo "Build completed."