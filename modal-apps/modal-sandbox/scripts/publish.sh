#!/usr/bin/env bash
set -e

echo "== Modal Sandbox v2.1 Publish =="

ruff check .

pytest

echo "Deploying modal-sandbox-v2.1..."
modal deploy modal_app.py --name modal-sandbox-v2.1

echo
echo "Publish completed."