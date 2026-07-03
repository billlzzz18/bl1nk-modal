#!/usr/bin/env bash
set -e

TARGET=${1:-dev}

modal shell modal_app.py::$TARGET
