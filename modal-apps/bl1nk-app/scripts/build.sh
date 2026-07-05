#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$APP_DIR/../.." && pwd)"
IMAGES_DIR="$REPO_ROOT/modal-images"

echo "== Building BL1NK Image bl1nk-rust:v2.2-20260705 =="
echo ""

echo "Building bl1nk-rust..."
modal run "$IMAGES_DIR/build_bl1nk_rust.py"

echo ""
echo "Build completed."
