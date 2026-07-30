#!/usr/bin/env bash
set -e

echo "== Deploy bl1nk-app =="

cd "$(dirname "$0")/.."

echo "Linting..."
uv run ruff check .

echo "Testing..."
uv run pytest

echo "Deploying bl1nk..."
uv run modal deploy modal_app.py --name bl1nk

echo
echo "Deploy completed."
