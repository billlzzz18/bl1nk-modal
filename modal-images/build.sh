#!/bin/bash
# Build script for bl1nk-rust image

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Build image
modal run build_bl1nk_rust.py 2>&1
