#!/usr/bin/env bash
set -e

echo "Python : $(python --version)"
echo "UV     : $(uv --version)"
echo "Modal  : $(modal version)"

echo
echo "Checking login..."

modal profile current

echo
echo "Checking Image..."

modal image list | grep bl1nk-rust

echo
echo "OK"
