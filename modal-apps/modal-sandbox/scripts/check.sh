#!/usr/bin/env bash
set -e
echo "Python : $(python --version)"
echo "UV     : $(uv --version)"
echo "Modal  : $(modal version)"

echo
echo "Checking login..."

if ! modal profile current >/dev/null 2>&1; then
    echo
    echo "Run:"
    echo
    echo "    modal setup"
    echo
    exit 1
fi

echo
echo "Checking Image..."

modal image list | grep -E "modal-sandbox|v2\.1"

echo
echo "Checking modal-sandbox-v2.1 deployment..."
modal app list | grep modal-sandbox || echo "App not deployed yet"

echo
echo "OK"