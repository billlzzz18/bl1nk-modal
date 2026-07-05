#!/usr/bin/env bash
set -euo pipefail

echo "== Modal Sandbox Setup =="

if ! command -v uv >/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "Sync dependencies..."
uv sync

if ! command -v modal >/dev/null; then
    echo "Installing Modal..."
    uv tool install modal
fi

echo

echo "Checking Modal login..."

if ! modal profile current >/dev/null 2>&1; then
    echo
    echo "Run:"
    echo
    echo "    modal setup"
    echo
    exit 1
fi

echo
echo "Setup completed."
echo

if ! command -v hermes >/dev/null 2>&1; then
    echo "Optional: Hermes Agent is not installed."
    echo "Run: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
    echo "If network is blocked, retry after configuring the sandbox network."
fi
