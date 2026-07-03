#!/usr/bin/env bash
set -e

ruff check .

pytest

modal deploy modal_app.py

echo
echo "Publish completed."
